"""VoiceOver TTS sidecar server.

FastAPI server providing transcription, voice generation, profile management,
and model downloads. Designed to be frozen with PyInstaller and run as a Tauri
sidecar process.

Usage:
    python server.py --port 8123 --data-dir /path/to/data --parent-pid 12345
"""

import sys
import os

# ---------------------------------------------------------------------------
# PyInstaller frozen-binary guards — MUST run before any heavy imports.
#
# 1. Protect stdout/stderr: in frozen builds (especially Windows --noconsole)
#    these can be None, causing crashes from print/logging/tqdm.
# 2. freeze_support(): when multiprocessing spawns a child, PyInstaller
#    re-executes this binary from the top. Without freeze_support() before
#    heavy imports, torch/transformers run in the child, fail to find CLI
#    args, and silently degrade (e.g. MPS → CPU fallback).
# 3. Early-exit for frozen children invoked without sidecar CLI flags.
# ---------------------------------------------------------------------------


def _is_writable(stream):
    """Check if a stream is usable for writing."""
    if stream is None:
        return False
    try:
        stream.write("")
        return True
    except Exception:
        return False


if not _is_writable(sys.stdout):
    sys.stdout = open(os.devnull, "w")
if not _is_writable(sys.stderr):
    sys.stderr = open(os.devnull, "w")

import multiprocessing
multiprocessing.freeze_support()

# In frozen builds, child processes re-enter this binary with no sidecar
# flags (just the executable path). Exit immediately before heavy imports.
if getattr(sys, "frozen", False) and len(sys.argv) == 1:
    sys.exit(0)

# ---------------------------------------------------------------------------
# All other imports — safe now that freeze_support has run.
# ---------------------------------------------------------------------------

import argparse
import asyncio
import functools
import logging
import signal
import threading
import time
import uuid
from pathlib import Path

import numpy as np
from contextlib import asynccontextmanager

# Monkey-patch transformers.check_model_inputs to a no-op decorator.
# qwen-tts 0.1.1 uses @check_model_inputs() (with parens as a decorator factory)
# but the actual implementation in transformers 4.56-4.57 does complex kwargs
# inspection that is incompatible with qwen-tts's forward() signatures.
# We don't need its functionality (attention capture, cache management).
import transformers.utils.generic as _tug


def _noop_check_model_inputs(*args, **kwargs):
    if args and callable(args[0]):
        return args[0]  # @check_model_inputs without parens
    def decorator(func):
        return func
    return decorator  # @check_model_inputs() with parens


_tug.check_model_inputs = _noop_check_model_inputs

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("voiceover-tts")

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

MODEL_REGISTRY = {
    # Whisper variants (transcription)
    "whisper-small": {
        "repo_id": "mlx-community/whisper-small-mlx",
        "display_name": "Whisper Small",
        "category": "transcription",
        "recommended": False,
    },
    "whisper-medium": {
        "repo_id": "mlx-community/whisper-medium-mlx",
        "display_name": "Whisper Medium",
        "category": "transcription",
        "recommended": False,
    },
    "whisper-large-v3-turbo": {
        "repo_id": "mlx-community/whisper-large-v3-turbo",
        "display_name": "Whisper Large v3 Turbo",
        "category": "transcription",
        "recommended": True,
    },
    # TTS
    "qwen-tts-1.7B": {
        "repo_id": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "display_name": "Qwen TTS 1.7B",
        "category": "tts",
        "recommended": False,
    },
    # Voice conversion
    "cosyvoice3-0.5B": {
        "repo_id": "mlx-community/Fun-CosyVoice3-0.5B-2512-8bit",
        "display_name": "CosyVoice3 0.5B",
        "category": "voice-conversion",
        "recommended": False,
    },
}

# Legacy short names -> canonical model names for /models/download compatibility
_LEGACY_MODEL_ALIASES = {
    "whisper": "whisper-large-v3-turbo",
    "qwen": "qwen-tts-1.7B",
    "qwen-tts-1.7b": "qwen-tts-1.7B",
    "cosyvoice3": "cosyvoice3-0.5B",
    "cosyvoice3-0.5b": "cosyvoice3-0.5B",
}

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

DATA_DIR: Path = Path("/tmp/voiceover-tts")


def error_response(status_code: int, message: str) -> JSONResponse:
    """Standardized JSON error response."""
    return JSONResponse(status_code=status_code, content={"error": message})


import tempfile

def _validate_path(path_str: str, allowed_parents: list) -> Path:
    """Validate a file path is within allowed directories.

    Rejects null bytes, path traversal, and symlink escape.
    Raises ValueError if the path is not within any allowed parent.
    """
    if not path_str or '\x00' in path_str:
        raise ValueError("Invalid path")
    resolved = Path(path_str).resolve()
    for parent in allowed_parents:
        if str(resolved).startswith(str(Path(parent).resolve())):
            return resolved
    raise ValueError("Path not within allowed directories")

# Generation queue: serial processing to prevent GPU contention
_generation_queue: asyncio.Queue = asyncio.Queue()
_generations: dict = {}  # id -> {status, error, audio_path, completed_at}


def _cleanup_generations():
    """Remove completed generations older than 1 hour."""
    now = time.time()
    expired = [gid for gid, gen in _generations.items()
               if gen.get("completed_at", now) < now - 3600
               and gen.get("status") in ("completed", "error")]
    for gid in expired:
        audio_path = _generations[gid].get("audio_path")
        if audio_path and Path(audio_path).exists():
            Path(audio_path).unlink(missing_ok=True)
        del _generations[gid]
    if expired:
        logger.info(f"Cleaned up {len(expired)} old generation(s)")


async def _periodic_cleanup():
    """Run generation cleanup every 5 minutes."""
    while True:
        await asyncio.sleep(300)
        _cleanup_generations()


@asynccontextmanager
async def lifespan(app):
    _cleanup_generations()  # Sweep stale generations from prior session
    asyncio.create_task(_generation_worker())
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    yield
    cleanup_task.cancel()


app = FastAPI(title="VoiceOver TTS Sidecar", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Parent PID watchdog (ported from Voicebox server.py pattern)
# ---------------------------------------------------------------------------


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID exists."""
    try:
        if sys.platform == "win32":
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                exit_code = ctypes.c_ulong()
                result = kernel32.GetExitCodeProcess(
                    handle, ctypes.byref(exit_code)
                )
                kernel32.CloseHandle(handle)
                if result and exit_code.value == 259:  # STILL_ACTIVE
                    return True
                return False
            error = ctypes.GetLastError()
            if error == 5:  # ACCESS_DENIED — process exists
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except (OSError, PermissionError):
        return False


def _start_parent_watchdog(parent_pid: int) -> None:
    """Monitor parent process and exit if it dies."""
    watchdog_logger = logging.getLogger("watchdog")

    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / "watchdog.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    watchdog_logger.addHandler(fh)
    watchdog_logger.setLevel(logging.INFO)

    def _watch() -> None:
        watchdog_logger.info(
            f"Watchdog started: parent={parent_pid}, self={os.getpid()}"
        )
        if not _is_pid_alive(parent_pid):
            watchdog_logger.warning(
                f"Parent PID {parent_pid} not found on first check — disabling"
            )
            return
        while True:
            if not _is_pid_alive(parent_pid):
                watchdog_logger.info(
                    f"Parent {parent_pid} gone, waiting 1s grace period..."
                )
                time.sleep(1)
                if not _is_pid_alive(parent_pid):
                    watchdog_logger.info("Shutting down server.")
                    if sys.platform == "win32":
                        os._exit(0)
                    else:
                        os.kill(os.getpid(), signal.SIGTERM)
                    return
            time.sleep(2)

    t = threading.Thread(target=_watch, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Generation worker (serial queue)
# ---------------------------------------------------------------------------


async def _run_generation(gen_id: str, generate_fn):
    """Shared lifecycle for TTS/VC generation tasks.

    Calls generate_fn() which must return (audio_data, sample_rate, log_label).
    Handles saving the WAV, marking status as completed/error, and logging.
    """
    import soundfile as sf

    try:
        audio, sample_rate, log_label = await generate_fn()

        # Save to file
        gen_dir = DATA_DIR / "generations"
        gen_dir.mkdir(parents=True, exist_ok=True)
        audio_path = gen_dir / f"{gen_id}.wav"
        sf.write(str(audio_path), audio, sample_rate)
        _generations[gen_id]["audio_path"] = str(audio_path)
        _generations[gen_id]["status"] = "completed"
        _generations[gen_id]["completed_at"] = time.time()
        logger.info(f"{log_label} {gen_id}: saved {audio_path} ({len(audio)} samples, {len(audio)/sample_rate:.1f}s)")
    except Exception as e:
        logger.error(f"Generation {gen_id} failed: {e}", exc_info=True)
        _generations[gen_id]["status"] = "error"
        _generations[gen_id]["error"] = str(e)
        _generations[gen_id]["completed_at"] = time.time()


async def _generation_worker():
    """Process generation requests one at a time."""
    while True:
        gen_id, coro = await _generation_queue.get()
        try:
            await coro
        except Exception as e:
            logger.error(f"Generation {gen_id} failed (unhandled): {e}", exc_info=True)
            _generations[gen_id]["status"] = "error"
            _generations[gen_id]["error"] = str(e)
            _generations[gen_id]["completed_at"] = time.time()
        finally:
            _generation_queue.task_done()


# ---------------------------------------------------------------------------
# Generation business logic
# ---------------------------------------------------------------------------


async def _do_generate(
    *,
    set_status,
    data_dir: Path,
    profile_id: str,
    text: str,
    language: str,
    segments: list,
    original_duration: float,
):
    """Generate speech audio from text using Qwen TTS.

    Returns (audio_data, sample_rate, log_label) for _run_generation.
    Calls set_status(str) to report progress.
    """
    from profiles import get_samples
    from tts import (
        combine_voice_prompts,
        generate_speech,
        load_qwen_model,
    )
    from chunked_tts import (
        assemble_timed_segments,
        concatenate_audio_chunks,
        pad_audio_to_match_timing,
        split_text_into_chunks,
    )

    models_dir = str(data_dir / "models")
    cache_dir = str(data_dir / "cache")

    # Load model if needed
    set_status("loading_model")
    await load_qwen_model(models_dir)

    # Get voice samples for profile
    samples = get_samples(data_dir, profile_id)
    if not samples:
        raise ValueError(f"No samples found for profile {profile_id}")

    # Create voice prompt from samples
    set_status("preparing_voice")
    audio_paths = [s["audio_path"] for s in samples]
    ref_texts = [s["reference_text"] for s in samples]
    voice_prompt = await combine_voice_prompts(audio_paths, ref_texts, cache_dir)

    set_status("generating")

    if segments and original_duration > 0:
        # --- Timestamp-synchronized generation ---
        logger.info(
            f"Segment-aware generation: {len(segments)} segments, "
            f"original_duration={original_duration:.1f}s"
        )
        tts_segments = []
        sample_rate = None

        for i, seg in enumerate(segments):
            seg_text = seg.get("text", "").strip()
            seg_start = float(seg.get("start", 0))
            seg_end = float(seg.get("end", 0))
            if not seg_text or seg_end <= seg_start:
                logger.info("Skipping segment %d: %s", i, "empty text" if not seg_text else f"end ({seg_end}) <= start ({seg_start})")
                continue

            logger.info(
                f"Generating segment {i + 1}/{len(segments)}: "
                f"[{seg_start:.1f}s-{seg_end:.1f}s] "
                f"({len(seg_text)} chars)"
            )

            # Sub-chunk long segments (>800 chars) and crossfade
            sub_chunks = split_text_into_chunks(seg_text)
            if len(sub_chunks) <= 1:
                seg_audio, seg_sr = await generate_speech(
                    seg_text, voice_prompt, language, seed=i
                )
            else:
                logger.info(
                    f"  Sub-chunking segment {i + 1}: "
                    f"{len(sub_chunks)} sub-chunks"
                )
                sub_audios = []
                seg_sr = None
                for j, sub_text in enumerate(sub_chunks):
                    sub_audio, sub_sr = await generate_speech(
                        sub_text, voice_prompt, language, seed=i * 100 + j
                    )
                    sub_audios.append(sub_audio)
                    if seg_sr is None:
                        seg_sr = sub_sr
                seg_audio = concatenate_audio_chunks(sub_audios, seg_sr)

            # Insert proportional silences between words to match
            # original speaker's pacing (TTS always runs faster)
            word_timing = seg.get("words", [])
            if word_timing and seg_sr:
                seg_audio = pad_audio_to_match_timing(
                    seg_audio, seg_sr, word_timing
                )

            tts_segments.append((seg_audio, seg_start, seg_end))
            if sample_rate is None:
                sample_rate = seg_sr

        if sample_rate is None:
            raise ValueError("No segments produced audio")

        audio = assemble_timed_segments(
            tts_segments, original_duration, sample_rate
        )
    else:
        # --- Original character-based chunked generation ---
        chunks = split_text_into_chunks(text)

        if len(chunks) <= 1:
            audio, sample_rate = await generate_speech(
                text, voice_prompt, language
            )
        else:
            logger.info(f"Chunked generation: {len(chunks)} chunks")
            audio_chunks = []
            sample_rate = None
            for i, chunk_text in enumerate(chunks):
                chunk_seed = i  # Deterministic per chunk
                chunk_audio, chunk_sr = await generate_speech(
                    chunk_text, voice_prompt, language, seed=chunk_seed
                )
                audio_chunks.append(chunk_audio)
                if sample_rate is None:
                    sample_rate = chunk_sr
            audio = concatenate_audio_chunks(audio_chunks, sample_rate)

        # Pad or truncate to match original duration with smooth fade-out
        if original_duration > 0 and sample_rate:
            target_samples = int(original_duration * sample_rate)
            if len(audio) < target_samples:
                # Fade out last 300ms before silence padding
                fade_samples = min(int(0.3 * sample_rate), len(audio) // 2)
                if fade_samples > 0:
                    fade = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
                    audio[-fade_samples:] *= fade
                audio = np.pad(audio, (0, target_samples - len(audio)))
            elif len(audio) > target_samples:
                audio = audio[:target_samples]

    return audio, sample_rate, "Generation"


_vc_model = None
_vc_model_name = None


async def _do_voice_convert(
    *,
    set_status,
    data_dir: Path,
    profile_id: str,
    source_audio_path: str,
    original_duration: float,
):
    """Convert source audio to target voice using CosyVoice3.

    Returns (audio_data, sample_rate, log_label) for _run_generation.
    Calls set_status(str) to report progress.
    Mutates module globals _vc_model and _vc_model_name for model caching.
    """
    import asyncio
    import mlx.core as mx
    from mlx_audio.tts.utils import load_model
    from mlx_audio.tts.generate import load_audio
    from profiles import get_samples

    models_dir = str(data_dir / "models")

    # Load CosyVoice3 model
    set_status("loading_model")
    global _vc_model, _vc_model_name

    vc_model_id = "mlx-community/Fun-CosyVoice3-0.5B-2512-8bit"
    if _vc_model is None or _vc_model_name != vc_model_id:
        logger.info(f"Loading voice conversion model: {vc_model_id}")
        os.environ["HF_HUB_CACHE"] = models_dir

        def _load():
            global _vc_model, _vc_model_name
            try:
                model = load_model(vc_model_id)
                _vc_model = model
                _vc_model_name = vc_model_id
            except Exception:
                _vc_model = None
                _vc_model_name = None
                raise

        await asyncio.to_thread(_load)
        logger.info("Voice conversion model loaded")

    # Get reference audio from voice profile — use all samples up to 30s
    set_status("preparing_voice")
    samples = get_samples(data_dir, profile_id)
    if not samples:
        raise ValueError(f"No samples found for profile {profile_id}")

    model_sr = _vc_model.sample_rate
    max_ref_samples = int(30 * model_sr)  # CosyVoice3 accepts up to 30s ref

    ref_parts = []
    ref_texts = []
    total_ref = 0
    all_have_text = True
    for sample in samples:
        if total_ref >= max_ref_samples:
            break
        part = load_audio(sample["audio_path"], sample_rate=model_sr, volume_normalize=False)
        remaining = max_ref_samples - total_ref
        was_truncated = len(part) > remaining
        if was_truncated:
            part = part[:remaining]
        ref_parts.append(part)
        total_ref += len(part)

        sample_text = sample.get("reference_text", "").strip()
        if sample_text and not was_truncated:
            ref_texts.append(sample_text)
        elif was_truncated:
            # Audio was truncated — omit transcript to avoid text/audio mismatch
            all_have_text = False
            logger.info(f"  Truncated sample — omitting transcript to avoid mismatch")
        else:
            all_have_text = False

        logger.info(f"  Loaded ref sample: {sample['audio_path']} ({len(part)/model_sr:.1f}s)")

    if not ref_parts:
        raise ValueError("No reference audio samples loaded successfully")

    ref_audio = mx.concatenate(ref_parts) if len(ref_parts) > 1 else ref_parts[0]
    # Only use ref_text if ALL included samples have full (non-truncated) transcripts.
    # Partial text causes voice cloning degradation. When ref_text is None and
    # stt_model is set, CosyVoice3 will auto-transcribe the reference audio.
    ref_text = " ".join(ref_texts) if ref_texts and all_have_text else None
    logger.info(
        f"Voice conversion: {len(samples)} samples -> {len(ref_audio)/model_sr:.1f}s ref audio, "
        f"ref_text={'yes' if ref_text else 'no'}, source={source_audio_path}"
    )

    source_audio = load_audio(source_audio_path, sample_rate=model_sr, volume_normalize=False)

    chunk_duration = 25  # CosyVoice3 limit is 30s, use 25 for safety
    chunk_samples = int(chunk_duration * model_sr)

    set_status("generating")

    def _convert_chunk(chunk_audio):
        """Run voice conversion on a single chunk (blocking, for thread pool)."""
        # When ref_text is available, skip auto-transcription (faster).
        # When ref_text is None, let the model auto-transcribe for best quality.
        results = _vc_model.generate(
            text="",
            ref_audio=ref_audio,
            ref_text=ref_text,
            source_audio=chunk_audio,
            stt_model=None if ref_text else "mlx-community/whisper-large-v3-turbo-4bit",
            verbose=False,
        )
        audio_parts = []
        for result in results:
            audio_parts.append(np.array(result.audio, dtype=np.float32).flatten())
        if not audio_parts:
            return np.array([], dtype=np.float32)
        return np.concatenate(audio_parts)

    source_np = np.array(source_audio) if isinstance(source_audio, mx.array) else source_audio

    if len(source_np) <= chunk_samples:
        logger.info(f"Voice conversion: single chunk ({len(source_np)/model_sr:.1f}s)")
        audio = await asyncio.to_thread(_convert_chunk, source_audio)
        if len(audio) == 0:
            raise ValueError("Voice conversion produced empty audio for single chunk")
        sample_rate = model_sr
    else:
        # Chunk and stitch for long recordings
        total_samples = len(source_np)
        overlap_samples = int(1.0 * model_sr)
        step = chunk_samples - overlap_samples
        n_chunks = max(1, (total_samples - overlap_samples + step - 1) // step)
        logger.info(f"Voice conversion: {n_chunks} chunks ({total_samples/model_sr:.1f}s total)")

        converted_pieces = []
        pos = 0
        for i in range(n_chunks):
            end = min(pos + chunk_samples, total_samples)
            chunk = mx.array(source_np[pos:end], dtype=mx.float32)
            logger.info(f"  Converting chunk {i+1}/{n_chunks} ({(end-pos)/model_sr:.1f}s)")
            piece = await asyncio.to_thread(_convert_chunk, chunk)
            if len(piece) > 0:
                converted_pieces.append(piece)
            else:
                logger.warning(f"  Chunk {i+1}/{n_chunks} produced empty audio")
            pos += step
            if pos >= total_samples:
                break

        if not converted_pieces:
            raise ValueError("Voice conversion produced no audio")

        from chunked_tts import concatenate_audio_chunks
        audio = concatenate_audio_chunks(converted_pieces, model_sr, crossfade_ms=500)
        sample_rate = model_sr

    # Pad or truncate to match original duration with a smooth fade-out
    if original_duration > 0 and sample_rate:
        target_samples = int(original_duration * sample_rate)
        if len(audio) < target_samples:
            # Fade out last 300ms before silence padding
            fade_samples = min(int(0.3 * sample_rate), len(audio) // 2)
            if fade_samples > 0:
                fade = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
                audio[-fade_samples:] *= fade
            audio = np.pad(audio, (0, target_samples - len(audio)))
        elif len(audio) > target_samples:
            audio = audio[:target_samples]

    return audio, sample_rate, "Voice conversion"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


_model_cache: dict = {}  # repo_id -> (is_available, timestamp)
_MODEL_CACHE_TTL = 30  # seconds


def _is_model_downloaded(models_dir: Path, repo_id: str) -> bool:
    """Check if a model with the exact repo_id is in the HF cache."""
    cache_key = repo_id
    now = time.time()
    if cache_key in _model_cache:
        cached_result, cached_time = _model_cache[cache_key]
        if now - cached_time < _MODEL_CACHE_TTL:
            return cached_result

    result = False
    try:
        from huggingface_hub import scan_cache_dir

        if models_dir.exists():
            cache_info = scan_cache_dir(str(models_dir))
            for repo in cache_info.repos:
                if repo.repo_id == repo_id:
                    result = True
                    break
    except Exception as e:
        logger.warning(f"Error scanning model cache for {repo_id}: {e}")
    _model_cache[cache_key] = (result, now)
    return result


@app.get("/health")
async def health():
    """Health check with model availability."""
    from tts import is_qwen_loaded

    models_dir = DATA_DIR / "models"
    return {
        "status": "healthy",
        "models": {
            "whisper": _is_model_downloaded(models_dir, "mlx-community/whisper-large-v3-turbo"),
            "qwen": is_qwen_loaded() or _is_model_downloaded(models_dir, "Qwen/Qwen3-TTS-12Hz-1.7B-Base"),
            "cosyvoice": _vc_model is not None or _is_model_downloaded(models_dir, "mlx-community/Fun-CosyVoice3-0.5B-2512-8bit"),
        },
    }


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), model_name: str = Form(None)):
    """Transcribe audio using MLX Whisper."""
    temp_path = DATA_DIR / "temp" / f"{uuid.uuid4()}.wav"
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        logger.info(f"Transcribing: {temp_path} ({len(content) // 1024}KB)")

        from tts import transcribe as do_transcribe

        kwargs = {}
        if model_name:
            kwargs["model_name"] = model_name

        result = do_transcribe(str(temp_path), str(DATA_DIR / "models"), **kwargs)
        logger.info(
            f"Transcribed: {result['duration']:.1f}s audio -> "
            f"{len(result['text'])} chars"
        )
        return result
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return error_response(500, str(e))
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/transcribe-path")
async def transcribe_path(request: dict):
    """Transcribe audio from a file already on disk (used after YouTube extraction)."""
    audio_path = request.get("audio_path", "")
    model_name = request.get("model_name")
    try:
        _validate_path(audio_path, [DATA_DIR, Path(tempfile.gettempdir())])
    except ValueError as e:
        return error_response(400, str(e))
    if not Path(audio_path).exists():
        return error_response(400, "audio_path not found")

    try:
        logger.info(f"Transcribing from path: {audio_path}")
        from tts import transcribe as do_transcribe

        kwargs = {}
        if model_name:
            kwargs["model_name"] = model_name

        result = do_transcribe(audio_path, str(DATA_DIR / "models"), **kwargs)
        logger.info(f"Transcribed: {result['duration']:.1f}s -> {len(result['text'])} chars")
        return result
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return error_response(500, str(e))


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


@app.post("/generate")
async def generate(request: dict):
    """Start voice generation. Returns immediately with a generation ID.

    When ``segments`` (with timestamps) and ``original_duration`` are provided,
    generates TTS per-segment and assembles at original timestamps with silence
    gaps. Without segments, falls back to character-based chunked generation.
    """
    _cleanup_generations()
    profile_id = request.get("profile_id", "")
    text = request.get("text", "")
    language = request.get("language", "en")
    segments = request.get("segments", []) or []
    original_duration = request.get("original_duration", 0.0)

    if not profile_id or not text:
        return error_response(400, "profile_id and text are required")

    gen_id = str(uuid.uuid4())
    _generations[gen_id] = {"status": "queued", "error": None, "audio_path": None}

    generate_fn = functools.partial(
        _do_generate,
        set_status=lambda s: _generations[gen_id].__setitem__("status", s),
        data_dir=DATA_DIR,
        profile_id=profile_id,
        text=text,
        language=language,
        segments=segments,
        original_duration=original_duration,
    )
    await _generation_queue.put((gen_id, _run_generation(gen_id, generate_fn)))
    return {"id": gen_id}


@app.get("/generate/{gen_id}/status")
async def generation_status(gen_id: str):
    """Poll generation status (plain JSON)."""
    gen = _generations.get(gen_id)
    if gen is None:
        return error_response(404, "Generation not found")
    return {"status": gen["status"], "error": gen["error"]}


@app.get("/audio/{gen_id}")
async def get_audio(gen_id: str):
    """Download generated audio."""
    gen = _generations.get(gen_id)
    if gen is None:
        return error_response(404, "Generation not found")
    if gen["status"] != "completed" or not gen["audio_path"]:
        return error_response(400, f"Generation not ready: {gen['status']}")

    audio_path = Path(gen["audio_path"])
    if not audio_path.exists():
        return error_response(404, "Audio file not found")

    return Response(
        content=audio_path.read_bytes(),
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename={gen_id}.wav"},
    )


# ---------------------------------------------------------------------------
# Voice Conversion (Speech-to-Speech)
# ---------------------------------------------------------------------------


@app.post("/voice-convert")
async def voice_convert(request: dict):
    """Start voice conversion (speech-to-speech). Preserves original timing.

    Uses CosyVoice3 via mlx-audio to convert the source audio to the target
    voice while keeping the exact pacing, pauses, and prosody of the original.
    For recordings longer than 25s, processes in overlapping chunks.
    """
    _cleanup_generations()
    profile_id = request.get("profile_id", "")
    source_audio_path = request.get("source_audio_path", "")
    original_duration = float(request.get("original_duration", 0))

    if not profile_id or not source_audio_path:
        return error_response(400, "profile_id and source_audio_path are required")

    try:
        _validate_path(source_audio_path, [DATA_DIR, Path(tempfile.gettempdir())])
    except ValueError as e:
        return error_response(400, str(e))
    if not Path(source_audio_path).exists():
        return error_response(400, f"Source audio file not found: {source_audio_path}")

    gen_id = str(uuid.uuid4())
    _generations[gen_id] = {"status": "queued", "error": None, "audio_path": None}

    convert_fn = functools.partial(
        _do_voice_convert,
        set_status=lambda s: _generations[gen_id].__setitem__("status", s),
        data_dir=DATA_DIR,
        profile_id=profile_id,
        source_audio_path=source_audio_path,
        original_duration=original_duration,
    )
    await _generation_queue.put((gen_id, _run_generation(gen_id, convert_fn)))
    return {"id": gen_id}


# ---------------------------------------------------------------------------
# YouTube extraction
# ---------------------------------------------------------------------------


@app.post("/extract-youtube")
async def extract_youtube(request: dict):
    """Download a YouTube video, extract audio, and clip to duration.

    Returns the path to a 16kHz mono WAV file suitable for voice cloning.
    """
    url = request.get("url", "")
    start = request.get("start", "0")
    duration = request.get("duration", 30)

    if not url:
        return error_response(400, "url is required")

    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"):
        return error_response(400, "Invalid YouTube URL")

    temp_dir = DATA_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_id = str(uuid.uuid4())
    output_wav = temp_dir / f"{output_id}.wav"

    try:
        import subprocess

        # Step 1: Download video with yt-dlp (as library, not subprocess)
        logger.info(f"Downloading YouTube video: {url}")
        video_path = temp_dir / f"{output_id}.video"

        def _download():
            import yt_dlp as ydl

            opts = {
                "outtmpl": str(video_path),
                "quiet": True,
                "no_warnings": True,
            }
            with ydl.YoutubeDL(opts) as dl:
                dl.download([url])

        try:
            await asyncio.to_thread(_download)
        except Exception as e:
            return error_response(400, f"Download failed: {e}")

        # Find the actual downloaded file (yt-dlp may add extension)
        actual_video = None
        for f in temp_dir.glob(f"{output_id}.*"):
            if f.suffix != ".wav":
                actual_video = f
                break
        if not actual_video or not actual_video.exists():
            return error_response(500, "Downloaded video file not found")

        # Step 2: Extract audio with ffmpeg (16kHz mono WAV, clipped)
        logger.info(f"Extracting {duration}s audio starting at {start}")
        ffmpeg_args = [
            "ffmpeg", "-y", "-i", str(actual_video),
            "-ss", str(start), "-t", str(duration),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(output_wav),
        ]
        ff_result = await asyncio.to_thread(
            subprocess.run,
            ffmpeg_args,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Clean up video file
        actual_video.unlink(missing_ok=True)

        if ff_result.returncode != 0:
            return error_response(500, f"Audio extraction failed: {ff_result.stderr.strip()[:200]}")

        if not output_wav.exists():
            return error_response(500, "Output WAV not created")

        # Get duration of the output
        import wave
        with wave.open(str(output_wav), "rb") as wf:
            wav_duration = wf.getnframes() / wf.getframerate()

        logger.info(f"Extracted: {output_wav} ({wav_duration:.1f}s)")
        return {
            "audio_path": str(output_wav),
            "duration": wav_duration,
            "id": output_id,
        }

    except Exception as e:
        logger.error(f"YouTube extraction failed: {e}")
        output_wav.unlink(missing_ok=True)
        return error_response(500, str(e))


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


@app.get("/profiles")
async def list_profiles():
    """List all voice profiles."""
    from profiles import list_profiles as _list

    return _list(DATA_DIR)


@app.post("/profiles")
async def create_profile(request: dict):
    """Create a new voice profile."""
    from profiles import create_profile as _create

    name = request.get("name", "")
    language = request.get("language", "en")
    if not name:
        return error_response(400, "name is required")
    return _create(DATA_DIR, name, language)


@app.post("/profiles/{profile_id}/samples")
async def upload_sample(
    profile_id: str,
    audio: UploadFile = File(...),
    reference_text: str = Form(""),
):
    """Upload a voice sample to a profile."""
    from profiles import add_sample

    content = await audio.read()
    try:
        return add_sample(DATA_DIR, profile_id, content, reference_text)
    except ValueError as e:
        return error_response(404, str(e))


@app.post("/profiles/{profile_id}/samples/from-path")
async def add_sample_from_path(profile_id: str, request: dict):
    """Add a voice sample from a file already on disk (used after YouTube extraction)."""
    from profiles import add_sample

    audio_path = request.get("audio_path", "")
    reference_text = request.get("reference_text", "")

    try:
        _validate_path(audio_path, [DATA_DIR, Path(tempfile.gettempdir())])
    except ValueError as e:
        return error_response(400, str(e))
    if not audio_path or not Path(audio_path).exists():
        return error_response(400, "audio_path not found")

    try:
        audio_bytes = Path(audio_path).read_bytes()
        return add_sample(DATA_DIR, profile_id, audio_bytes, reference_text)
    except ValueError as e:
        return error_response(404, str(e))


@app.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    """Delete a voice profile."""
    from profiles import delete_profile as _delete

    if _delete(DATA_DIR, profile_id):
        return {"ok": True}
    return error_response(404, "Profile not found")


# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------


@app.get("/models/status")
async def models_status():
    """Get model download/load status for all registered models."""
    from tts import is_qwen_loaded, _whisper_model, _whisper_model_name

    models_dir = DATA_DIR / "models"
    result = []

    for model_name, entry in MODEL_REGISTRY.items():
        repo_id = entry["repo_id"]
        downloaded = _is_model_downloaded(models_dir, repo_id)

        # Determine loaded status per category
        category = entry["category"]
        if category == "transcription":
            loaded = _whisper_model is not None and _whisper_model_name == model_name
        elif category == "tts":
            loaded = is_qwen_loaded()
        elif category == "voice-conversion":
            loaded = _vc_model is not None
        else:
            loaded = False

        result.append({
            "model_name": model_name,
            "display_name": entry["display_name"],
            "category": category,
            "recommended": entry["recommended"],
            "downloaded": downloaded,
            "loaded": loaded,
        })

    return {"models": result}


@app.post("/models/download")
async def download_model(request: dict):
    """Download a model from HuggingFace. Streams progress as SSE."""
    # Accept both "model" and "model_name" keys (Voicebox compat)
    model = request.get("model_name", "") or request.get("model", "")

    # Resolve legacy short names to canonical model names
    if model in _LEGACY_MODEL_ALIASES:
        model = _LEGACY_MODEL_ALIASES[model]

    if model not in MODEL_REGISTRY:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown model: {model}"},
        )

    repo_id = MODEL_REGISTRY[model]["repo_id"]
    models_dir = str(DATA_DIR / "models")

    async def _stream():
        import json

        from huggingface_hub import snapshot_download

        yield f"data: {json.dumps({'progress': 0.0, 'status': f'Starting download of {model}...'})}\n\n"

        try:
            # snapshot_download is blocking — run in thread
            def _download():
                os.environ["HF_HUB_CACHE"] = models_dir
                return snapshot_download(
                    repo_id,
                    cache_dir=models_dir,
                )

            path = await asyncio.to_thread(_download)
            # Invalidate the model cache so /models/status returns fresh results
            _model_cache.pop(repo_id, None)
            yield f"data: {json.dumps({'progress': 1.0, 'status': 'Download complete', 'path': str(path)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'progress': -1, 'status': f'Download failed: {e}', 'error': str(e)})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.delete("/models/{model_name}")
async def delete_model(model_name: str):
    """Delete a downloaded model from the HuggingFace cache and clear in-memory references."""
    # Resolve legacy short names to canonical model names
    canonical = _LEGACY_MODEL_ALIASES.get(model_name, model_name)
    if canonical not in MODEL_REGISTRY:
        return error_response(400, f"Unknown model: {model_name}")

    entry = MODEL_REGISTRY[canonical]
    repo_id = entry["repo_id"]
    category = entry["category"]

    models_dir = DATA_DIR / "models"

    try:
        from huggingface_hub import scan_cache_dir

        if not models_dir.exists():
            return error_response(404, "Model not downloaded")

        cache_info = scan_cache_dir(str(models_dir))

        # Find the repo matching the exact repo_id
        target_repo = None
        for repo in cache_info.repos:
            if repo.repo_id == repo_id:
                target_repo = repo
                break

        if target_repo is None:
            return error_response(404, "Model not downloaded")

        # Collect all revision hashes and delete them
        revision_hashes = [rev.commit_hash for rev in target_repo.revisions]
        delete_strategy = cache_info.delete_revisions(*revision_hashes)
        freed_size = delete_strategy.expected_freed_size
        delete_strategy.execute()

        logger.info(
            f"Deleted model {canonical} (repo_id={repo_id}), "
            f"freed {freed_size / (1024 * 1024):.1f} MB"
        )

        # Clear in-memory model references based on category
        if category == "transcription":
            import tts as _tts_module
            _tts_module._whisper_model = None
            _tts_module._whisper_model_name = None
        elif category == "tts":
            import tts as _tts_module
            _tts_module._qwen_model = None
            _tts_module._qwen_model_size = None
        elif category == "voice-conversion":
            global _vc_model, _vc_model_name
            _vc_model = None
            _vc_model_name = None

        # Invalidate the model cache entry so _is_model_downloaded() doesn't return stale results
        if repo_id in _model_cache:
            del _model_cache[repo_id]

        return {"deleted": model_name, "freed_bytes": freed_size}

    except Exception as e:
        logger.error(f"Failed to delete model {canonical}: {e}", exc_info=True)
        return error_response(500, f"Failed to delete model: {e}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="VoiceOver TTS sidecar server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, required=True, help="Bind port")
    parser.add_argument(
        "--data-dir", type=str, required=True, help="Data directory"
    )
    parser.add_argument(
        "--parent-pid",
        type=int,
        required=True,
        help="Parent process PID for watchdog",
    )
    parser.add_argument(
        "--ffmpeg",
        type=str,
        default="",
        help="Path to ffmpeg binary (bundled in .app)",
    )
    args = parser.parse_args()

    global DATA_DIR
    DATA_DIR = Path(args.data_dir)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Set HuggingFace cache to our data directory
    models_dir = DATA_DIR / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HUB_CACHE"] = str(models_dir)

    # If a bundled ffmpeg path is provided, add its directory to PATH
    # so that mlx-whisper and subprocess calls can find it.
    if args.ffmpeg and Path(args.ffmpeg).exists():
        ffmpeg_dir = str(Path(args.ffmpeg).parent)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        logger.info(f"Added bundled ffmpeg to PATH: {ffmpeg_dir}")

    logger.info(
        f"Starting VoiceOver TTS sidecar: "
        f"port={args.port}, data_dir={DATA_DIR}, parent_pid={args.parent_pid}"
    )

    # Start watchdog
    _start_parent_watchdog(args.parent_pid)

    # Run server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
