"""TTS inference engine for VoiceOver sidecar.

Whisper transcription (via mlx-audio) + Qwen TTS generation.
Ported from Voicebox mlx_backend.py and pytorch_backend.py patterns.
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
# Whisper transcription (using mlx-audio, same as Voicebox)
# ---------------------------------------------------------------------------

_whisper_model = None


def _group_words_into_phrases(words: list, min_pause_sec: float = 0.3) -> list:
    """Group word-level timestamps into phrases separated by pauses.

    Takes Whisper's word-level output and groups consecutive words into
    phrases wherever there's a pause >= min_pause_sec between words.
    Each phrase becomes a segment with precise start/end timestamps.
    """
    if not words:
        return []

    phrases = []
    current_words = []
    current_start = None

    for word_info in words:
        word_start = float(word_info.get("start", 0))
        word_end = float(word_info.get("end", 0))
        word_text = (word_info.get("word") or word_info.get("text") or "").strip()

        if not word_text:
            continue

        if current_start is None:
            # First word
            current_start = word_start
            current_words.append(word_info)
        else:
            # Check gap between previous word end and this word start
            prev_end = float(current_words[-1].get("end", 0))
            gap = word_start - prev_end

            if gap >= min_pause_sec:
                # Pause detected — finalize current phrase
                phrase_text = "".join(w.get("word") or w.get("text") or "" for w in current_words).strip()
                phrase_end = float(current_words[-1].get("end", 0))
                if phrase_text:
                    phrases.append({
                        "start": current_start,
                        "end": phrase_end,
                        "text": phrase_text,
                    })
                # Start new phrase
                current_start = word_start
                current_words = [word_info]
            else:
                current_words.append(word_info)

    # Finalize last phrase
    if current_words:
        phrase_text = "".join(w.get("word") or w.get("text") or "" for w in current_words).strip()
        phrase_end = float(current_words[-1].get("end", 0))
        if phrase_text:
            phrases.append({
                "start": current_start,
                "end": phrase_end,
                "text": phrase_text,
            })

    return phrases


def _is_hallucinated(seg: dict) -> bool:
    """Check if a Whisper segment is likely hallucinated."""
    return (
        seg.get("no_speech_prob", 0) > 0.6
        or seg.get("compression_ratio", 0) > 2.4
    )


def _filter_segments(raw_segments: list) -> list:
    """Filter hallucinated Whisper segments and fix overlapping timestamps.

    Removes segments with high no_speech_prob (>0.6), high compression_ratio
    (>2.4, indicates repetitive/hallucinated text), or empty text.
    Clamps overlapping timestamps so segment[n+1].start >= segment[n].end.
    """
    filtered = []
    for seg in raw_segments:
        if not isinstance(seg, dict):
            continue
        if _is_hallucinated(seg):
            continue
        text = seg.get("text", "").strip()
        if not text:
            continue
        filtered.append({
            "start": float(seg.get("start", 0)),
            "end": float(seg.get("end", 0)),
            "text": text,
        })

    # Fix overlapping timestamps
    for i in range(1, len(filtered)):
        if filtered[i]["start"] < filtered[i - 1]["end"]:
            filtered[i]["start"] = filtered[i - 1]["end"]

    return filtered


def transcribe(audio_path: str, models_dir: str) -> dict:
    """Transcribe audio file using MLX Whisper via mlx-audio.

    Uses mlx_audio.stt.load() which handles model loading correctly
    in PyInstaller binaries (unlike mlx_whisper which has npz issues).

    Returns dict with text, duration, and segments (with timestamps).
    """
    global _whisper_model

    os.environ["HF_HUB_CACHE"] = models_dir

    if _whisper_model is None:
        logger.info("Loading Whisper model (first use)...")
        from mlx_audio.stt import load

        _whisper_model = load("openai/whisper-large-v3-turbo")
        logger.info("Whisper model loaded")

    # Use word_timestamps=True for precise per-word timing
    result = _whisper_model.generate(str(audio_path), word_timestamps=True)

    # Extract text and raw segments from result
    raw_segments = []
    if isinstance(result, str):
        text = result.strip()
    elif isinstance(result, dict):
        text = result.get("text", "").strip()
        raw_segments = result.get("segments", []) or []
    elif hasattr(result, "text"):
        text = result.text.strip()
        raw_segments = getattr(result, "segments", None) or []
    else:
        # Generator of results — collect text and segments
        collected = list(result)
        text = " ".join(
            s.text.strip() if hasattr(s, "text") else str(s).strip()
            for s in collected
        ).strip()
        for s in collected:
            if hasattr(s, "segments") and s.segments:
                raw_segments.extend(s.segments)
            elif isinstance(s, dict) and s.get("segments"):
                raw_segments.extend(s["segments"])

    # Get precise duration from audio file
    duration = 0.0
    try:
        import soundfile as sf

        info = sf.info(audio_path)
        duration = info.duration
    except Exception:
        pass

    # Collect all words across segments and group into phrases by pauses
    all_words = []
    for seg in raw_segments:
        if not isinstance(seg, dict) or _is_hallucinated(seg):
            continue
        words = seg.get("words", []) or []
        all_words.extend(words)

    if all_words:
        # Word-level timestamps available — group into phrases by pauses
        segments = _group_words_into_phrases(all_words, min_pause_sec=0.3)
        logger.info(
            "Transcribed: %.1fs audio -> %d chars, %d phrases (from %d words across %d raw segments)",
            duration, len(text), len(segments), len(all_words), len(raw_segments),
        )
    else:
        # Fallback to segment-level timestamps
        segments = _filter_segments(raw_segments)
        logger.info(
            "Transcribed: %.1fs audio -> %d chars, %d segments (from %d raw, no word timestamps)",
            duration, len(text), len(segments), len(raw_segments),
        )

    return {"text": text, "duration": duration, "segments": segments}


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
) -> list:
    """Create voice prompt from reference audio.

    Returns a list of VoiceClonePromptItem (qwen-tts 0.1.x API).
    """
    if _qwen_model is None:
        raise RuntimeError("Qwen model not loaded")

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

    prompt_items = await asyncio.to_thread(_create_sync)

    if cache_dir:
        _save_cached_prompt(cache_dir, cache_key, prompt_items)

    return prompt_items


async def combine_voice_prompts(
    audio_paths: list[str],
    reference_texts: list[str],
    cache_dir: Optional[str] = None,
) -> list:
    """Combine multiple samples into a list of VoiceClonePromptItems."""
    all_items = []
    for audio_path, ref_text in zip(audio_paths, reference_texts):
        items = await create_voice_prompt(audio_path, ref_text, cache_dir)
        all_items.extend(items)
    # Use only the last sample's prompt (consistent with Voicebox behavior)
    return all_items[-1:] if all_items else []


async def generate_speech(
    text: str,
    voice_prompt: list,
    language: str = "en",
    seed: Optional[int] = None,
) -> Tuple[np.ndarray, int]:
    """Generate speech from text using voice clone prompt items."""
    if _qwen_model is None:
        raise RuntimeError("Qwen model not loaded")

    def _generate_sync():
        import torch

        if seed is not None:
            torch.manual_seed(seed)
            if torch.backends.mps.is_available():
                torch.mps.manual_seed(seed)

        # Map language code to display name (capitalize for qwen-tts 0.1.x)
        lang_name = LANGUAGE_CODE_TO_NAME.get(language, "auto")
        if lang_name != "auto":
            lang_name = lang_name.capitalize()
        else:
            lang_name = "Auto"

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
    h = hashlib.md5()
    try:
        h.update(Path(audio_path).read_bytes())
    except OSError:
        h.update(audio_path.encode())
    h.update(reference_text.encode())
    return h.hexdigest()


def _load_cached_prompt(cache_dir: str, cache_key: str) -> Optional[dict]:
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
    cache_path = Path(cache_dir) / f"{cache_key}.prompt"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import torch
        torch.save(prompt, cache_path)
        logger.info(f"Cached voice prompt: {cache_key[:12]}...")
    except Exception as e:
        logger.warning(f"Failed to cache voice prompt: {e}")
