"""VoiceOver TTS sidecar server.

FastAPI server providing transcription, voice generation, profile management,
and model downloads. Designed to be frozen with PyInstaller and run as a Tauri
sidecar process.

Usage:
    python server.py --port 8123 --data-dir /path/to/data --parent-pid 12345
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import threading
import time
import uuid
from pathlib import Path

import numpy as np
from contextlib import asynccontextmanager

# Monkey-patch transformers.check_model_inputs to handle both @decorator and
# @decorator() call styles. qwen-tts 0.1.1 uses @check_model_inputs() (with
# parens) but transformers 4.56+ defines it as a plain decorator.
import transformers.utils.generic as _tug

_original_cmi = _tug.check_model_inputs


def _flexible_check_model_inputs(func=None):
    if func is not None:
        return _original_cmi(func)
    # Called as @check_model_inputs() — return the decorator
    return _original_cmi


_tug.check_model_inputs = _flexible_check_model_inputs

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
# Global state
# ---------------------------------------------------------------------------

DATA_DIR: Path = Path("/tmp/voiceover-tts")

# Generation queue: serial processing to prevent GPU contention
_generation_queue: asyncio.Queue = asyncio.Queue()
_generations: dict = {}  # id -> {status, error, audio_path}

@asynccontextmanager
async def lifespan(app):
    asyncio.create_task(_generation_worker())
    yield


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


async def _generation_worker():
    """Process generation requests one at a time."""
    while True:
        gen_id, coro = await _generation_queue.get()
        try:
            _generations[gen_id]["status"] = "generating"
            await coro
            _generations[gen_id]["status"] = "completed"
        except Exception as e:
            logger.error(f"Generation {gen_id} failed: {e}")
            _generations[gen_id]["status"] = "failed"
            _generations[gen_id]["error"] = str(e)
        finally:
            _generation_queue.task_done()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def _is_model_downloaded(models_dir: Path, keyword: str) -> bool:
    """Check if a model matching keyword is in the HF cache."""
    try:
        from huggingface_hub import scan_cache_dir

        if models_dir.exists():
            cache_info = scan_cache_dir(str(models_dir))
            for repo in cache_info.repos:
                if keyword in repo.repo_id.lower():
                    return True
    except Exception:
        pass
    return False


@app.get("/health")
async def health():
    """Health check with model availability."""
    from tts import is_qwen_loaded

    models_dir = DATA_DIR / "models"
    return {
        "status": "healthy",
        "models": {
            "whisper": _is_model_downloaded(models_dir, "whisper"),
            "qwen": is_qwen_loaded() or _is_model_downloaded(models_dir, "qwen"),
        },
    }


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Transcribe audio using MLX Whisper."""
    temp_path = DATA_DIR / "temp" / f"{uuid.uuid4()}.wav"
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        logger.info(f"Transcribing: {temp_path} ({len(content) // 1024}KB)")

        from tts import transcribe as do_transcribe

        result = do_transcribe(str(temp_path), str(DATA_DIR / "models"))
        logger.info(
            f"Transcribed: {result['duration']:.1f}s audio -> "
            f"{len(result['text'])} chars"
        )
        return result
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/transcribe-path")
async def transcribe_path(request: dict):
    """Transcribe audio from a file already on disk (used after YouTube extraction)."""
    audio_path = request.get("audio_path", "")
    if not audio_path or not Path(audio_path).exists():
        return JSONResponse(status_code=400, content={"error": "audio_path not found"})

    try:
        logger.info(f"Transcribing from path: {audio_path}")
        from tts import transcribe as do_transcribe

        result = do_transcribe(audio_path, str(DATA_DIR / "models"))
        logger.info(f"Transcribed: {result['duration']:.1f}s -> {len(result['text'])} chars")
        return result
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


@app.post("/generate")
async def generate(request: dict):
    """Start voice generation. Returns immediately with a generation ID."""
    profile_id = request.get("profile_id", "")
    text = request.get("text", "")
    language = request.get("language", "en")

    if not profile_id or not text:
        return JSONResponse(
            status_code=400,
            content={"error": "profile_id and text are required"},
        )

    gen_id = str(uuid.uuid4())
    _generations[gen_id] = {"status": "queued", "error": None, "audio_path": None}

    async def _do_generate():
        from profiles import get_samples
        from tts import (
            combine_voice_prompts,
            generate_speech,
            load_qwen_model,
        )
        from chunked_tts import (
            concatenate_audio_chunks,
            split_text_into_chunks,
        )

        models_dir = str(DATA_DIR / "models")
        cache_dir = str(DATA_DIR / "cache")

        # Load model if needed
        _generations[gen_id]["status"] = "loading_model"
        await load_qwen_model(models_dir)

        # Get voice samples for profile
        samples = get_samples(DATA_DIR, profile_id)
        if not samples:
            raise ValueError(f"No samples found for profile {profile_id}")

        # Create voice prompt from samples
        _generations[gen_id]["status"] = "preparing_voice"
        audio_paths = [s["audio_path"] for s in samples]
        ref_texts = [s["reference_text"] for s in samples]
        voice_prompt = await combine_voice_prompts(audio_paths, ref_texts, cache_dir)

        # Generate speech (with chunking for long text)
        _generations[gen_id]["status"] = "generating"
        chunks = split_text_into_chunks(text)

        if len(chunks) <= 1:
            audio, sample_rate = await generate_speech(text, voice_prompt, language)
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

        # Save to file
        import soundfile as sf

        gen_dir = DATA_DIR / "generations"
        gen_dir.mkdir(parents=True, exist_ok=True)
        audio_path = gen_dir / f"{gen_id}.wav"
        sf.write(str(audio_path), audio, sample_rate)
        _generations[gen_id]["audio_path"] = str(audio_path)
        logger.info(f"Generation {gen_id}: saved {audio_path} ({len(audio)} samples)")

    await _generation_queue.put((gen_id, _do_generate()))
    return {"id": gen_id}


@app.get("/generate/{gen_id}/status")
async def generation_status(gen_id: str):
    """Poll generation status (plain JSON)."""
    gen = _generations.get(gen_id)
    if gen is None:
        return JSONResponse(status_code=404, content={"error": "Generation not found"})
    return {"status": gen["status"], "error": gen["error"]}


@app.get("/audio/{gen_id}")
async def get_audio(gen_id: str):
    """Download generated audio."""
    gen = _generations.get(gen_id)
    if gen is None:
        return JSONResponse(status_code=404, content={"error": "Generation not found"})
    if gen["status"] != "completed" or not gen["audio_path"]:
        return JSONResponse(status_code=400, content={"error": f"Generation not ready: {gen['status']}"})

    audio_path = Path(gen["audio_path"])
    if not audio_path.exists():
        return JSONResponse(status_code=404, content={"error": "Audio file not found"})

    return Response(
        content=audio_path.read_bytes(),
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename={gen_id}.wav"},
    )


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
        return JSONResponse(status_code=400, content={"error": "url is required"})

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
            return JSONResponse(
                status_code=400,
                content={"error": f"Download failed: {e}"},
            )

        # Find the actual downloaded file (yt-dlp may add extension)
        actual_video = None
        for f in temp_dir.glob(f"{output_id}.*"):
            if f.suffix != ".wav":
                actual_video = f
                break
        if not actual_video or not actual_video.exists():
            return JSONResponse(
                status_code=500,
                content={"error": "Downloaded video file not found"},
            )

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
            return JSONResponse(
                status_code=500,
                content={"error": f"Audio extraction failed: {ff_result.stderr.strip()[:200]}"},
            )

        if not output_wav.exists():
            return JSONResponse(
                status_code=500, content={"error": "Output WAV not created"}
            )

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
        return JSONResponse(status_code=500, content={"error": str(e)})


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
        return JSONResponse(status_code=400, content={"error": "name is required"})
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
        return JSONResponse(status_code=404, content={"error": str(e)})


@app.post("/profiles/{profile_id}/samples/from-path")
async def add_sample_from_path(profile_id: str, request: dict):
    """Add a voice sample from a file already on disk (used after YouTube extraction)."""
    from profiles import add_sample

    audio_path = request.get("audio_path", "")
    reference_text = request.get("reference_text", "")

    if not audio_path or not Path(audio_path).exists():
        return JSONResponse(status_code=400, content={"error": "audio_path not found"})

    try:
        audio_bytes = Path(audio_path).read_bytes()
        return add_sample(DATA_DIR, profile_id, audio_bytes, reference_text)
    except ValueError as e:
        return JSONResponse(status_code=404, content={"error": str(e)})


@app.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    """Delete a voice profile."""
    from profiles import delete_profile as _delete

    if _delete(DATA_DIR, profile_id):
        return {"ok": True}
    return JSONResponse(status_code=404, content={"error": "Profile not found"})


# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------


@app.get("/models/status")
async def models_status():
    """Get model download/load status."""
    from tts import is_qwen_loaded

    models_dir = DATA_DIR / "models"
    whisper_downloaded = _is_model_downloaded(models_dir, "whisper")
    qwen_downloaded = _is_model_downloaded(models_dir, "qwen")

    return {
        "models": [
            {
                "model_name": "whisper-large-v3-turbo",
                "display_name": "Whisper Large v3 Turbo",
                "downloaded": whisper_downloaded,
                "loaded": whisper_downloaded,  # Whisper loads on demand
            },
            {
                "model_name": "qwen-tts-1.7B",
                "display_name": "Qwen TTS 1.7B",
                "downloaded": qwen_downloaded,
                "loaded": is_qwen_loaded(),
            },
        ]
    }


@app.post("/models/download")
async def download_model(request: dict):
    """Download a model from HuggingFace. Streams progress as SSE."""
    # Accept both "model" and "model_name" keys (Voicebox compat)
    model = request.get("model_name", "") or request.get("model", "")

    # Accept short names ("whisper", "qwen") and full names from /models/status
    model_map = {
        "whisper": "mlx-community/whisper-large-v3-turbo",
        "whisper-large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
        "qwen": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "qwen-tts-1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "qwen-tts-1.7b": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    }

    if model not in model_map:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown model: {model}"},
        )

    repo_id = model_map[model]
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
            yield f"data: {json.dumps({'progress': 1.0, 'status': 'Download complete', 'path': str(path)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'progress': -1, 'status': f'Download failed: {e}', 'error': str(e)})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


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
