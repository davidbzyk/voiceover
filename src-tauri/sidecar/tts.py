"""TTS inference engine for VoiceOver sidecar.

Whisper transcription and text-to-speech engines, both through mlx-audio.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import os

import numpy as np

logger = logging.getLogger("voiceover-tts.engine")

# ---------------------------------------------------------------------------
# Whisper transcription (using mlx-audio, same as Voicebox)
# ---------------------------------------------------------------------------

_whisper_model = None
_whisper_model_name = None  # Track which model is loaded

# The -asr repos carry the tokenizer files mlx-audio's Whisper loads its processor from;
# the older repos without them fail with "Processor not found" (tested on 0.5.8).
WHISPER_MODELS = {
    "whisper-medium": "mlx-community/whisper-medium-asr-fp16",
    "whisper-large-v3-turbo": "mlx-community/whisper-large-v3-turbo-asr-fp16",
}


def _group_words_into_phrases(words: list, min_pause_sec: float = 0.3) -> list:
    """Group word-level timestamps into phrases separated by pauses.

    Takes Whisper's word-level output and groups consecutive words into
    phrases wherever there's a pause >= min_pause_sec between words.
    Each phrase becomes a segment with precise start/end timestamps and
    the original word timing for proportional silence insertion.
    """
    if not words:
        return []

    phrases = []
    current_words = []
    current_start = None

    def _finalize_phrase(word_list, start):
        phrase_text = "".join(
            w.get("word") or w.get("text") or "" for w in word_list
        ).strip()
        phrase_end = float(word_list[-1].get("end", 0))
        if not phrase_text:
            return None
        # Build word timing for proportional silence insertion
        word_timing = []
        for w in word_list:
            wt = (w.get("word") or w.get("text") or "").strip()
            if wt:
                word_timing.append({
                    "word": wt,
                    "start": float(w.get("start", 0)),
                    "end": float(w.get("end", 0)),
                })
        return {
            "start": start,
            "end": phrase_end,
            "text": phrase_text,
            "words": word_timing,
        }

    for word_info in words:
        word_start = float(word_info.get("start", 0))
        word_text = (word_info.get("word") or word_info.get("text") or "").strip()

        if not word_text:
            continue

        if current_start is None:
            current_start = word_start
            current_words.append(word_info)
        else:
            prev_end = float(current_words[-1].get("end", 0))
            gap = word_start - prev_end

            if gap >= min_pause_sec:
                phrase = _finalize_phrase(current_words, current_start)
                if phrase:
                    phrases.append(phrase)
                current_start = word_start
                current_words = [word_info]
            else:
                current_words.append(word_info)

    if current_words:
        phrase = _finalize_phrase(current_words, current_start)
        if phrase:
            phrases.append(phrase)

    return phrases


def _filter_segments(raw_segments: list) -> list:
    """Filter empty Whisper segments and fix overlapping timestamps.

    Clamps overlapping timestamps so segment[n+1].start >= segment[n].end.
    """
    filtered = []
    for seg in raw_segments:
        if not isinstance(seg, dict):
            continue
        text = seg.get("text", "").strip()
        if not text:
            continue
        filtered.append({
            "start": float(seg.get("start", 0)),
            "end": float(seg.get("end", 0)),
            "text": text,
            "words": [],
        })

    # Fix overlapping timestamps
    for i in range(1, len(filtered)):
        if filtered[i]["start"] < filtered[i - 1]["end"]:
            filtered[i]["start"] = filtered[i - 1]["end"]

    # Remove degenerate segments created by clamping
    filtered = [seg for seg in filtered if seg["end"] > seg["start"]]

    return filtered


def transcribe(audio_path: str, models_dir: str, model_name: str = "whisper-large-v3-turbo") -> dict:
    """Transcribe audio file using MLX Whisper via mlx-audio.

    Uses mlx_audio.stt.load() which handles model loading correctly
    in PyInstaller binaries (unlike mlx_whisper which has npz issues).

    Args:
        audio_path: Path to the audio file to transcribe.
        models_dir: Path to HuggingFace model cache directory.
        model_name: Key into WHISPER_MODELS dict (default: whisper-large-v3-turbo).

    Returns dict with text, duration, and segments (with timestamps).
    """
    global _whisper_model, _whisper_model_name

    # Resolve model_name to HuggingFace repo ID
    if model_name not in WHISPER_MODELS:
        raise ValueError(
            f"Unknown whisper model: {model_name}. "
            f"Valid: {list(WHISPER_MODELS.keys())}"
        )
    repo_id = WHISPER_MODELS[model_name]

    # Reload if a different model is requested
    if model_name != _whisper_model_name:
        _whisper_model = None
        gc.collect()
        try:
            import mlx.core as mx
            mx.metal.clear_cache()
        except Exception:
            pass

    if _whisper_model is None:
        logger.info("Loading Whisper model '%s' (%s)...", model_name, repo_id)
        from mlx_audio.stt.utils import load_model as load_stt_model

        _whisper_model = load_stt_model(repo_id)
        _whisper_model_name = model_name
        logger.info("Whisper model loaded: %s", model_name)

    # Use word_timestamps=True for precise per-word timing.
    # Disable compression_ratio and no_speech thresholds so Whisper doesn't
    # suppress repetitive content (it would collapse repeated phrases).
    result = _whisper_model.generate(
        str(audio_path),
        word_timestamps=True,
        compression_ratio_threshold=None,
        no_speech_threshold=None,
        condition_on_previous_text=False,
    )

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
    except Exception as e:
        logging.getLogger(__name__).warning("Could not read audio duration from %s: %s", audio_path, e)

    # Collect all words across segments — word timestamps are ground truth,
    # so skip the hallucination filter here (it's too aggressive for
    # repetitive content like repeated phrases).
    all_words = []
    for seg in raw_segments:
        if not isinstance(seg, dict):
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
# Text-to-speech engines (mlx-audio)
# ---------------------------------------------------------------------------

_tts_model = None
_tts_engine = None  # registry key of the loaded engine


def is_whisper_loaded() -> bool:
    return _whisper_model is not None


def get_whisper_model_name() -> str | None:
    return _whisper_model_name


def get_loaded_tts_engine() -> str | None:
    """Return the registry key of the TTS engine in memory, or None."""
    return _tts_engine


def unload_tts_engine() -> None:
    """Drop the loaded TTS engine and free its Metal memory."""
    global _tts_model, _tts_engine
    _tts_model = None
    _tts_engine = None
    gc.collect()
    try:
        import mlx.core as mx
        mx.metal.clear_cache()
    except Exception:
        pass


async def load_tts_engine(models_dir: str, engine: str, repo_id: str) -> None:
    """Load an engine's weights through mlx-audio; any other engine is unloaded first."""
    global _tts_model, _tts_engine
    if _tts_engine == engine and _tts_model is not None:
        return
    unload_tts_engine()
    def _load_sync():
        from mlx_audio.tts.utils import load_model
        return load_model(repo_id)

    logger.info("Loading TTS engine %s (%s)...", engine, repo_id)
    _tts_model = await asyncio.to_thread(_load_sync)
    _tts_engine = engine
    logger.info("TTS engine %s loaded (sr=%s)", engine, _tts_model.sample_rate)


async def generate_speech(
    text: str,
    ref_audio_path: str,
    ref_text: str | None,
    seed: int | None = None,
) -> tuple[np.ndarray, int]:
    """Speak ``text`` in the reference voice with the loaded engine's own sampling defaults.

    ``ref_text`` is None for engines that clone from the audio alone (Qwen x-vector mode).
    """
    if _tts_model is None:
        raise RuntimeError("No TTS engine loaded")
    model = _tts_model

    def _generate_sync():
        import mlx.core as mx
        from mlx_audio.utils import load_audio

        if seed is not None:
            mx.random.seed(seed)
        ref = load_audio(ref_audio_path, sample_rate=model.sample_rate)
        parts = [
            np.asarray(r.audio, dtype=np.float32).flatten()
            for r in model.generate(text=text, ref_audio=ref, ref_text=ref_text)
        ]
        if not parts:
            raise RuntimeError("TTS engine produced no audio")
        return np.concatenate(parts), model.sample_rate

    return await asyncio.to_thread(_generate_sync)
