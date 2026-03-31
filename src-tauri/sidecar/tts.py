"""TTS inference engine for VoiceOver sidecar.

Whisper transcription + Qwen TTS generation.
Ported from Voicebox pytorch_backend.py patterns.
"""

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("voiceover-tts.engine")

LANGUAGE_CODE_TO_NAME = {
    "zh": "chinese",
    "en": "english",
    "ja": "japanese",
    "ko": "korean",
    "de": "german",
    "fr": "french",
    "ru": "russian",
    "pt": "portuguese",
    "es": "spanish",
    "it": "italian",
}

# ---------------------------------------------------------------------------
# Whisper transcription
# ---------------------------------------------------------------------------

_whisper_loaded = False


def transcribe(audio_path: str, models_dir: str) -> dict:
    """Transcribe audio file using MLX Whisper."""
    global _whisper_loaded

    os.environ["HF_HUB_CACHE"] = models_dir

    import mlx_whisper

    if not _whisper_loaded:
        logger.info("Loading Whisper model (first use)...")
        _whisper_loaded = True

    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
    )

    text = result.get("text", "").strip()
    duration = 0.0
    segments = result.get("segments", [])
    if segments:
        duration = segments[-1].get("end", 0.0)

    return {"text": text, "duration": duration}


# ---------------------------------------------------------------------------
# Qwen TTS generation
# ---------------------------------------------------------------------------

_qwen_model = None
_qwen_model_size = None


def _get_device() -> str:
    """Get the best available device for PyTorch."""
    import torch

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


async def load_qwen_model(models_dir: str, model_size: str = "1.7B") -> None:
    """Load Qwen TTS model (async, runs blocking load in thread pool)."""
    global _qwen_model, _qwen_model_size

    if _qwen_model is not None and _qwen_model_size == model_size:
        return

    os.environ["HF_HUB_CACHE"] = models_dir

    def _load_sync():
        global _qwen_model, _qwen_model_size
        import torch
        from qwen_tts import Qwen3TTSModel

        hf_map = {
            "1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            "0.6B": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        }
        model_path = hf_map.get(model_size, hf_map["1.7B"])
        device = _get_device()

        logger.info(f"Loading Qwen TTS {model_size} on {device}...")
        if device == "cpu":
            _qwen_model = Qwen3TTSModel.from_pretrained(
                model_path, torch_dtype=torch.float32, low_cpu_mem_usage=False,
            )
        else:
            _qwen_model = Qwen3TTSModel.from_pretrained(
                model_path, device_map=device, torch_dtype=torch.bfloat16,
            )
        _qwen_model_size = model_size
        logger.info(f"Qwen TTS {model_size} loaded successfully")

    await asyncio.to_thread(_load_sync)


def is_qwen_loaded() -> bool:
    return _qwen_model is not None


async def create_voice_prompt(
    audio_path: str,
    reference_text: str,
    cache_dir: Optional[str] = None,
) -> dict:
    """Create voice prompt from reference audio.

    Ported from Voicebox pytorch_backend.py create_voice_prompt().
    """
    if _qwen_model is None:
        raise RuntimeError("Qwen model not loaded")

    # Check cache
    if cache_dir:
        cache_key = _cache_key(audio_path, reference_text)
        cached = _load_cached_prompt(cache_dir, cache_key)
        if cached is not None:
            logger.info(f"Using cached voice prompt: {cache_key[:12]}...")
            return cached

    def _create_sync():
        return _qwen_model.create_voice_clone_prompt(
            ref_audio=str(audio_path),
            ref_text=reference_text,
            x_vector_only_mode=False,
        )

    prompt = await asyncio.to_thread(_create_sync)

    # Cache
    if cache_dir:
        _save_cached_prompt(cache_dir, cache_key, prompt)

    return prompt


async def combine_voice_prompts(
    audio_paths: list[str],
    reference_texts: list[str],
    cache_dir: Optional[str] = None,
) -> dict:
    """Combine multiple samples into a single voice prompt."""
    if len(audio_paths) == 1:
        return await create_voice_prompt(
            audio_paths[0], reference_texts[0], cache_dir
        )

    # For multiple samples, create each prompt and average
    # Following Voicebox's combine pattern
    prompts = []
    for audio_path, ref_text in zip(audio_paths, reference_texts):
        prompt = await create_voice_prompt(audio_path, ref_text, cache_dir)
        prompts.append(prompt)

    # Use the last prompt as the base (Voicebox behavior)
    return prompts[-1]


async def generate_speech(
    text: str,
    voice_prompt: dict,
    language: str = "en",
    seed: Optional[int] = None,
) -> Tuple[np.ndarray, int]:
    """Generate speech from text using a voice prompt.

    Returns (audio_array, sample_rate).
    """
    if _qwen_model is None:
        raise RuntimeError("Qwen model not loaded")

    def _generate_sync():
        import torch

        if seed is not None:
            torch.manual_seed(seed)
            if torch.backends.mps.is_available():
                torch.mps.manual_seed(seed)

        lang_name = LANGUAGE_CODE_TO_NAME.get(language, "auto")
        wavs, sample_rate = _qwen_model.generate_voice_clone(
            text=text,
            voice_clone_prompt=voice_prompt,
            language=lang_name,
        )
        return wavs[0], sample_rate

    audio, sample_rate = await asyncio.to_thread(_generate_sync)
    return np.asarray(audio, dtype=np.float32), sample_rate


# ---------------------------------------------------------------------------
# Voice prompt caching
# ---------------------------------------------------------------------------


def _cache_key(audio_path: str, reference_text: str) -> str:
    """Generate a cache key from audio file content + reference text."""
    h = hashlib.md5()
    try:
        h.update(Path(audio_path).read_bytes())
    except OSError:
        h.update(audio_path.encode())
    h.update(reference_text.encode())
    return h.hexdigest()


def _load_cached_prompt(cache_dir: str, cache_key: str) -> Optional[dict]:
    """Load a cached voice prompt from disk."""
    cache_path = Path(cache_dir) / f"{cache_key}.prompt"
    if not cache_path.exists():
        return None
    try:
        import torch
        return torch.load(cache_path, map_location="cpu", weights_only=False)
    except Exception as e:
        logger.warning(f"Failed to load cached prompt: {e}")
        return None


def _save_cached_prompt(cache_dir: str, cache_key: str, prompt: dict) -> None:
    """Save a voice prompt to disk cache."""
    cache_path = Path(cache_dir) / f"{cache_key}.prompt"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import torch
        torch.save(prompt, cache_path)
        logger.info(f"Cached voice prompt: {cache_key[:12]}...")
    except Exception as e:
        logger.warning(f"Failed to cache voice prompt: {e}")
