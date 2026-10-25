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

# huggingface_hub reads HF_HUB_CACHE once, when first imported, and some engines fetch extra repos
# by themselves (CosyVoice's S3 tokenizer). Set it before any import can load the hub, so every
# model lands in the app's models folder, where the Models page lists and deletes it.
for _i, _arg in enumerate(sys.argv):
    if _arg.startswith("--data-dir="):
        os.environ["HF_HUB_CACHE"] = os.path.join(_arg.split("=", 1)[1], "models")
    elif _arg == "--data-dir" and _i + 1 < len(sys.argv):
        os.environ["HF_HUB_CACHE"] = os.path.join(sys.argv[_i + 1], "models")

# ---------------------------------------------------------------------------
# All other imports — safe now that freeze_support has run.
# ---------------------------------------------------------------------------

import argparse
import asyncio
import functools
import gc
import logging
import signal
import threading
import time
import uuid
from pathlib import Path

import numpy as np
from contextlib import asynccontextmanager

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

# TTS rows: ``ref_text`` says whether the engine gets the sample's transcript. Qwen clones from
# the speaker embedding alone (x-vector mode), which stops the transcript leaking into the output.
# ``license`` is the model card's licence id, shown before download. ``module`` is the code that
# loads the repo; ``--check-imports`` imports each one so a frozen build missing a module fails at
# build time. ``extra_repos`` lists other Hub repos the engine fetches by itself at load or generate
# time; they are downloaded, counted and deleted with the row. Find them by generating once with
# HF_HUB_OFFLINE=1 and only the row's repos in the models folder (okf/standards/engine-admission.md).
MODEL_REGISTRY = {
    # Whisper variants (transcription)
    "whisper-medium": {
        "repo_id": "mlx-community/whisper-medium-asr-fp16",
        "module": "mlx_audio.stt.models.whisper",
        "display_name": "Whisper Medium",
        "category": "transcription",
        "recommended": False,
    },
    "whisper-large-v3-turbo": {
        "repo_id": "mlx-community/whisper-large-v3-turbo-asr-fp16",
        "module": "mlx_audio.stt.models.whisper",
        "display_name": "Whisper Large v3 Turbo",
        "category": "transcription",
        "recommended": True,
    },
    # TTS
    "qwen-tts-1.7B": {
        "repo_id": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16",
        "module": "mlx_audio.tts.models.qwen3_tts",
        "display_name": "Qwen3-TTS 1.7B",
        "category": "tts",
        "recommended": False,
        "ref_text": False,
        "license": "apache-2.0",
    },
    # Voice conversion
    "cosyvoice3-0.5B": {
        "repo_id": "mlx-community/Fun-CosyVoice3-0.5B-2512-8bit",
        "extra_repos": ["mlx-community/S3TokenizerV3"],  # 1.0 GB, fetched with the tokenizers
        "module": "cosyvoice_mlx.tts.models.cosyvoice3",
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
        parent_resolved = Path(parent).resolve()
        if resolved.is_relative_to(parent_resolved):
            return resolved
    raise ValueError("Path not within allowed directories")

# Generation queue: serial processing to prevent GPU contention
_generation_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
_generations: dict = {}  # id -> {status, error, audio_path, completed_at, progress, cancel}
MAX_GENERATIONS = 1000
_FINISHED_STATUSES = ("completed", "error", "cancelled")


def _new_generation() -> str:
    """Register a queued generation and return its id."""
    gen_id = str(uuid.uuid4())
    _generations[gen_id] = {
        "status": "queued",
        "error": None,
        "audio_path": None,
        "progress": {"done": 0, "total": 0},
        "cancel": False,
    }
    return gen_id


def _mark_cancelled(gen_id: str) -> None:
    """Record that a generation stopped because it was cancelled."""
    _generations[gen_id]["status"] = "cancelled"
    _generations[gen_id]["completed_at"] = time.time()


def _cleanup_generations():
    """Remove completed generations older than 1 hour."""
    now = time.time()
    expired = [gid for gid, gen in _generations.items()
               if gen.get("completed_at", now) < now - 3600
               and gen.get("status") in _FINISHED_STATUSES]
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


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return error_response(500, str(exc))


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
    from logging.handlers import RotatingFileHandler

    watchdog_logger = logging.getLogger("watchdog")

    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "watchdog.log"
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    watchdog_logger.addHandler(handler)
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
    from chunked_tts import ConversionCancelled

    try:
        audio, sample_rate, log_label = await generate_fn()

        # Diagnostic: log audio properties before saving
        audio_duration = len(audio) / sample_rate if sample_rate else 0
        logger.info(
            f"{log_label} {gen_id}: audio_samples={len(audio)}, "
            f"sample_rate={sample_rate}, duration={audio_duration:.3f}s"
        )

        # Save to file
        gen_dir = DATA_DIR / "generations"
        gen_dir.mkdir(parents=True, exist_ok=True)
        audio_path = gen_dir / f"{gen_id}.wav"
        sf.write(str(audio_path), audio, sample_rate)

        # Verify WAV was written correctly by reading it back
        try:
            info = sf.info(str(audio_path))
            logger.info(
                f"{log_label} {gen_id}: WAV verify: sr={info.samplerate}, "
                f"frames={info.frames}, duration={info.duration:.3f}s, "
                f"format={info.subtype}"
            )
            if abs(info.duration - audio_duration) > 0.1:
                logger.warning(
                    f"{log_label} {gen_id}: WAV duration mismatch! "
                    f"expected={audio_duration:.3f}s, actual={info.duration:.3f}s"
                )
        except Exception as verify_err:
            logger.warning(f"{log_label} {gen_id}: WAV verify failed: {verify_err}")

        _generations[gen_id]["audio_path"] = str(audio_path)
        _generations[gen_id]["status"] = "completed"
        _generations[gen_id]["completed_at"] = time.time()
        logger.info(f"{log_label} {gen_id}: saved {audio_path} ({len(audio)} samples, {len(audio)/sample_rate:.1f}s)")
    except ConversionCancelled:
        logger.info(f"Generation {gen_id} cancelled")
        _mark_cancelled(gen_id)
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
            gen = _generations.get(gen_id)
            # A missing record is a cancelled job the hourly cleanup removed while it waited in the queue.
            if gen is None or gen.get("cancel"):
                coro.close()
                logger.info(f"Generation {gen_id} cancelled before it started")
                continue
            await coro
        except Exception as e:
            logger.error(f"Generation {gen_id} failed (unhandled): {e}", exc_info=True)
            if gen_id in _generations:
                _generations[gen_id]["status"] = "error"
                _generations[gen_id]["error"] = str(e)
                _generations[gen_id]["completed_at"] = time.time()
        finally:
            _generation_queue.task_done()
            if len(_generations) > 20:
                _cleanup_generations()


# ---------------------------------------------------------------------------
# Generation business logic
# ---------------------------------------------------------------------------


async def _do_generate(
    *,
    set_status,
    set_progress=lambda done, total: None,
    should_cancel=lambda: False,
    data_dir: Path,
    engine: str,
    profile_id: str,
    text: str,
    segments: list,
    original_duration: float,
):
    """Generate speech from text with the TTS engine named by ``engine`` (a registry key).

    Returns (audio_data, sample_rate, log_label) for _run_generation. Reports progress in
    segments (or text chunks) done, and stops at the next one when ``should_cancel()`` is true.
    """
    from profiles import get_samples
    from tts import generate_speech, load_tts_engine
    from chunked_tts import (
        ConversionCancelled,
        assemble_timed_segments,
        concatenate_audio_chunks,
        pad_audio_to_match_timing,
        pad_or_truncate_to_duration,
        split_text_into_chunks,
    )

    row = MODEL_REGISTRY[engine]
    samples = get_samples(data_dir, profile_id)
    if not samples:
        raise ValueError(f"No samples found for profile {profile_id}")

    set_status("loading_model")
    await load_tts_engine(str(data_dir / "models"), engine, row["repo_id"])
    # The last sample is the voice reference, as the Qwen prompt path used before.
    ref_audio_path = samples[-1]["audio_path"]
    ref_text = None
    if row["ref_text"]:
        ref_text = (samples[-1].get("reference_text") or "").strip() or None

    async def speak(chunk_text: str, seed: int | None = None):
        return await generate_speech(chunk_text, ref_audio_path, ref_text, seed=seed)

    def step(done: int, total: int) -> None:
        if should_cancel():
            raise ConversionCancelled()
        set_progress(done, total)

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
            step(i, len(segments))
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
                seg_audio, seg_sr = await speak(seg_text, seed=i)
            else:
                logger.info(
                    f"  Sub-chunking segment {i + 1}: "
                    f"{len(sub_chunks)} sub-chunks"
                )
                sub_audios = []
                seg_sr = None
                for j, sub_text in enumerate(sub_chunks):
                    sub_audio, sub_sr = await speak(sub_text, seed=i * 100 + j)
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
        set_progress(len(segments), len(segments))

        audio = assemble_timed_segments(
            tts_segments, original_duration, sample_rate
        )
    else:
        # --- Original character-based chunked generation ---
        chunks = split_text_into_chunks(text)

        if len(chunks) <= 1:
            step(0, 1)
            audio, sample_rate = await speak(text)
            set_progress(1, 1)
        else:
            logger.info(f"Chunked generation: {len(chunks)} chunks")
            audio_chunks = []
            sample_rate = None
            for i, chunk_text in enumerate(chunks):
                step(i, len(chunks))
                chunk_audio, chunk_sr = await speak(chunk_text, seed=i)  # deterministic per chunk
                audio_chunks.append(chunk_audio)
                if sample_rate is None:
                    sample_rate = chunk_sr
            audio = concatenate_audio_chunks(audio_chunks, sample_rate)
            set_progress(len(chunks), len(chunks))

        # Diagnostic: log raw TTS output before pad/truncate
        raw_duration = len(audio) / sample_rate if sample_rate else 0
        logger.info(
            f"TTS generation: raw output {len(audio)} samples, "
            f"{raw_duration:.3f}s at {sample_rate}Hz, "
            f"target={original_duration:.3f}s"
        )
        if original_duration > 0 and abs(raw_duration - original_duration) / original_duration > 0.05:
            logger.warning(
                f"TTS generation: output duration {raw_duration:.3f}s deviates "
                f"{abs(raw_duration - original_duration)/original_duration*100:.1f}% "
                f"from target {original_duration:.3f}s"
            )

        # Pad or truncate to match original duration with smooth fade-out
        audio = pad_or_truncate_to_duration(audio, sample_rate, original_duration)

    return audio, sample_rate, "Generation"


_vc_model = None
_vc_model_name = None


async def _do_voice_convert(
    *,
    set_status,
    set_progress=lambda done, total: None,
    should_cancel=lambda: False,
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
    from cosyvoice_mlx.loader import load_cosyvoice3
    from mlx_audio.utils import load_audio
    from profiles import get_samples
    from chunked_tts import convert_in_overlapping_chunks

    models_dir = str(data_dir / "models")

    # Load CosyVoice3 model
    set_status("loading_model")
    global _vc_model, _vc_model_name

    vc_model_id = MODEL_REGISTRY["cosyvoice3-0.5B"]["repo_id"]
    if _vc_model is None or _vc_model_name != vc_model_id:
        logger.info(f"Loading voice conversion model: {vc_model_id}")

        def _load():
            global _vc_model, _vc_model_name
            try:
                model = load_cosyvoice3(vc_model_id)
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
    logger.info(f"Voice conversion: model_sr={model_sr}, original_duration={original_duration:.3f}s")
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
    # Partial text causes voice cloning degradation.
    ref_text = " ".join(ref_texts) if ref_texts and all_have_text else None
    logger.info(
        f"Voice conversion: {len(samples)} samples -> {len(ref_audio)/model_sr:.1f}s ref audio, "
        f"ref_text={'yes' if ref_text else 'no'}, source={source_audio_path}"
    )

    source_audio = load_audio(source_audio_path, sample_rate=model_sr, volume_normalize=False)
    source_duration = len(source_audio) / model_sr if model_sr else 0
    logger.info(
        f"Voice conversion: source_samples={len(source_audio)}, "
        f"source_duration={source_duration:.3f}s (at model_sr={model_sr}), "
        f"original_duration={original_duration:.3f}s"
    )
    if original_duration > 0 and abs(source_duration - original_duration) > 1.0:
        logger.warning(
            f"Voice conversion: source audio duration ({source_duration:.3f}s) differs from "
            f"original_duration ({original_duration:.3f}s) by {abs(source_duration - original_duration):.1f}s"
        )

    set_status("generating")

    def _convert_chunk(chunk_audio):
        """Run voice conversion on a single chunk (blocking, for thread pool)."""
        # CosyVoice transcribes the reference only when no source_audio is given, so voice
        # conversion never uses an STT model; None keeps it from naming one.
        results = _vc_model.generate(
            text="",
            ref_audio=ref_audio,
            ref_text=ref_text,
            source_audio=mx.array(chunk_audio, dtype=mx.float32),
            stt_model=None,
            verbose=False,
        )
        audio_parts = []
        for result in results:
            audio_parts.append(np.array(result.audio, dtype=np.float32).flatten())
        if not audio_parts:
            return np.array([], dtype=np.float32)
        return np.concatenate(audio_parts)

    # CosyVoice3 accepts at most 30s of source audio per call, so 25s windows leave headroom.
    audio = await asyncio.to_thread(
        convert_in_overlapping_chunks,
        np.array(source_audio),
        model_sr,
        _convert_chunk,
        chunk_seconds=25.0,
        overlap_seconds=1.0,
        on_progress=set_progress,
        should_cancel=should_cancel,
    )
    if len(audio) == 0:
        raise ValueError("Voice conversion produced no audio")
    sample_rate = model_sr

    # Diagnostic: log raw output before pad/truncate
    raw_duration = len(audio) / sample_rate if sample_rate else 0
    logger.info(
        f"Voice conversion: raw output {len(audio)} samples, "
        f"{raw_duration:.3f}s at {sample_rate}Hz "
        f"(target: {original_duration:.3f}s, ratio: {raw_duration/original_duration:.3f})"
        if original_duration > 0 else
        f"Voice conversion: raw output {len(audio)} samples, "
        f"{raw_duration:.3f}s at {sample_rate}Hz (no target duration)"
    )
    if original_duration > 0 and abs(raw_duration - original_duration) / original_duration > 0.05:
        logger.warning(
            f"Voice conversion: output duration {raw_duration:.3f}s deviates "
            f"{abs(raw_duration - original_duration)/original_duration*100:.1f}% "
            f"from target {original_duration:.3f}s — this may cause A/V sync issues"
        )

    # Pad or truncate to match original duration with a smooth fade-out
    from chunked_tts import pad_or_truncate_to_duration
    audio = pad_or_truncate_to_duration(audio, sample_rate, original_duration)

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
        return False  # Don't cache transient errors
    _model_cache[cache_key] = (result, now)
    return result


def _row_repos(entry: dict) -> list[str]:
    """Every Hub repo a registry row needs on disk: its own repo, then the ones its engine fetches."""
    return [entry["repo_id"], *entry.get("extra_repos", [])]


def _row_downloaded(models_dir: Path, entry: dict) -> bool:
    """True only when every repo the row needs is in the models folder."""
    return all(_is_model_downloaded(models_dir, repo) for repo in _row_repos(entry))


@app.get("/health")
async def health():
    """Health check with model availability."""
    from tts import get_loaded_tts_engine

    models_dir = DATA_DIR / "models"

    def _any_downloaded(category: str) -> bool:
        return any(
            _row_downloaded(models_dir, entry)
            for entry in MODEL_REGISTRY.values()
            if entry["category"] == category
        )

    return {
        "status": "healthy",
        "models": {
            "whisper": _any_downloaded("transcription"),
            "tts": get_loaded_tts_engine() is not None or _any_downloaded("tts"),
            "cosyvoice": _vc_model is not None or _any_downloaded("voice-conversion"),
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

        result = await asyncio.to_thread(
            do_transcribe, str(temp_path), str(DATA_DIR / "models"), **kwargs
        )
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

        result = await asyncio.to_thread(
            do_transcribe, audio_path, str(DATA_DIR / "models"), **kwargs
        )
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
    """Start voice generation with the TTS engine named by ``engine``. Returns a generation ID.

    When ``segments`` (with timestamps) and ``original_duration`` are provided,
    generates TTS per-segment and assembles at original timestamps with silence
    gaps. Without segments, falls back to character-based chunked generation.
    The engines detect the language from the text, so ``language`` is not used.
    """
    _cleanup_generations()
    engine = request.get("engine", "")
    profile_id = request.get("profile_id", "")
    text = request.get("text", "")
    segments = request.get("segments", []) or []
    original_duration = request.get("original_duration", 0.0)

    if not profile_id or not text:
        return error_response(400, "profile_id and text are required")
    if MODEL_REGISTRY.get(engine, {}).get("category") != "tts":
        tts_keys = [k for k, v in MODEL_REGISTRY.items() if v["category"] == "tts"]
        return error_response(400, f"engine must be one of {tts_keys}, got {engine!r}")

    if len(_generations) >= MAX_GENERATIONS:
        _cleanup_generations()
        if len(_generations) >= MAX_GENERATIONS:
            return error_response(429, "Too many pending generations")

    gen_id = _new_generation()

    generate_fn = functools.partial(
        _do_generate,
        set_status=lambda s: _generations[gen_id].__setitem__("status", s),
        set_progress=lambda done, total: _generations[gen_id].__setitem__(
            "progress", {"done": done, "total": total}
        ),
        should_cancel=lambda: _generations[gen_id]["cancel"],
        data_dir=DATA_DIR,
        engine=engine,
        profile_id=profile_id,
        text=text,
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
    return {"status": gen["status"], "error": gen["error"], "progress": gen["progress"]}


@app.post("/generate/{gen_id}/cancel")
async def cancel_generation(gen_id: str):
    """Ask a queued or running generation to stop; a running one stops at its next chunk."""
    gen = _generations.get(gen_id)
    if gen is None:
        return error_response(404, "Generation not found")
    if gen["status"] in _FINISHED_STATUSES:
        return {"status": gen["status"]}
    gen["cancel"] = True
    if gen["status"] == "queued":
        _mark_cancelled(gen_id)
    return {"status": gen["status"]}


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

    gen_id = _new_generation()

    convert_fn = functools.partial(
        _do_voice_convert,
        set_status=lambda s: _generations[gen_id].__setitem__("status", s),
        set_progress=lambda done, total: _generations[gen_id].__setitem__(
            "progress", {"done": done, "total": total}
        ),
        should_cancel=lambda: _generations[gen_id]["cancel"],
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
                "socket_timeout": 30,
                "retries": 2,
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
    from tts import get_loaded_tts_engine, is_whisper_loaded, get_whisper_model_name

    models_dir = DATA_DIR / "models"
    result = []

    # Scan HF cache once for all models (instead of once per model)
    downloaded_repos: set = set()
    if models_dir.exists():
        try:
            from huggingface_hub import scan_cache_dir
            cache_info = scan_cache_dir(str(models_dir))
            downloaded_repos = {repo.repo_id for repo in cache_info.repos}
        except Exception:
            pass

    for model_name, entry in MODEL_REGISTRY.items():
        downloaded = all(repo in downloaded_repos for repo in _row_repos(entry))

        # Determine loaded status per category
        category = entry["category"]
        if category == "transcription":
            loaded = is_whisper_loaded() and get_whisper_model_name() == model_name
        elif category == "tts":
            loaded = get_loaded_tts_engine() == model_name
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
            "license": entry.get("license"),
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

    repos = _row_repos(MODEL_REGISTRY[model])
    models_dir = str(DATA_DIR / "models")

    async def _stream():
        import json

        from huggingface_hub import snapshot_download

        yield f"data: {json.dumps({'progress': 0.0, 'status': f'Starting download of {model}...'})}\n\n"

        try:
            path = None
            for i, repo_id in enumerate(repos):
                if i:
                    yield f"data: {json.dumps({'progress': i / len(repos), 'status': f'Downloading {repo_id}...'})}\n\n"
                # snapshot_download is blocking — run in thread
                downloaded = await asyncio.to_thread(snapshot_download, repo_id, cache_dir=models_dir)
                path = path or downloaded
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

    # --- File deletion ---
    try:
        from huggingface_hub import scan_cache_dir

        if not models_dir.exists():
            return error_response(404, "Model not downloaded")

        cache_info = scan_cache_dir(str(models_dir))

        # The row's own repo and the ones its engine fetched, except any another row also needs.
        shared = {r for name, other in MODEL_REGISTRY.items() if name != canonical for r in _row_repos(other)}
        wanted = [r for r in _row_repos(entry) if r == repo_id or r not in shared]
        target_repos = [repo for repo in cache_info.repos if repo.repo_id in wanted]

        if not target_repos:
            return error_response(404, "Model not downloaded")

        # Collect all revision hashes and delete them
        revision_hashes = [rev.commit_hash for repo in target_repos for rev in repo.revisions]
        delete_strategy = cache_info.delete_revisions(*revision_hashes)
        freed_size = delete_strategy.expected_freed_size
        delete_strategy.execute()

        logger.info(
            f"Deleted model {canonical} ({', '.join(r.repo_id for r in target_repos)}), "
            f"freed {freed_size / (1024 * 1024):.1f} MB"
        )
    except Exception as e:
        logger.error(f"Failed to delete model {canonical}: {e}", exc_info=True)
        return error_response(500, f"Failed to delete model: {e}")

    # --- In-memory cleanup (best-effort, files already deleted) ---
    try:
        if category == "transcription":
            import tts as _tts_module
            _tts_module._whisper_model = None
            _tts_module._whisper_model_name = None
            gc.collect()
            try:
                import mlx.core as mx
                mx.metal.clear_cache()
            except Exception:
                pass
        elif category == "tts":
            import tts as _tts_module
            if _tts_module.get_loaded_tts_engine() == canonical:
                _tts_module.unload_tts_engine()
        elif category == "voice-conversion":
            global _vc_model, _vc_model_name
            _vc_model = None
            _vc_model_name = None
            gc.collect()
            try:
                import mlx.core as mx
                mx.metal.clear_cache()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"In-memory cleanup failed for {canonical}: {e}")

    # Invalidate the model cache entries so _is_model_downloaded() doesn't return stale results
    for repo in _row_repos(entry):
        _model_cache.pop(repo, None)

    return {"deleted": model_name, "freed_bytes": freed_size}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def check_imports() -> int:
    """Import every registry row's model module; return 1 if any fails (used on the frozen binary)."""
    import importlib

    failed = 0
    for name, entry in MODEL_REGISTRY.items():
        try:
            importlib.import_module(entry["module"])
            print(f"ok   {name}: {entry['module']}")
        except Exception as e:  # report every failure, not just the first
            failed = 1
            print(f"FAIL {name}: {entry['module']}: {e!r}")
    return failed


def main():
    if "--check-imports" in sys.argv:
        sys.exit(check_imports())
    # No abbreviations: the HF_HUB_CACHE scan at the top of this file matches --data-dir exactly.
    parser = argparse.ArgumentParser(description="VoiceOver TTS sidecar server", allow_abbrev=False)
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
