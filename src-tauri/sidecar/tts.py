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


def _find_speech_regions(
    rms: np.ndarray,
    threshold: float,
    min_gap_frames: int,
) -> list:
    """Find contiguous speech regions in an RMS energy array.

    Groups speech frames that are separated by fewer than min_gap_frames
    of silence into the same region. Returns list of (onset_frame, offset_frame).
    """
    speech_mask = rms > threshold
    regions = []
    in_speech = False
    onset = 0
    silent_count = 0

    for i, is_speech in enumerate(speech_mask):
        if is_speech:
            if not in_speech:
                onset = i
                in_speech = True
            silent_count = 0
        else:
            if in_speech:
                silent_count += 1
                if silent_count >= min_gap_frames:
                    regions.append((onset, i - silent_count + 1))
                    in_speech = False
                    silent_count = 0

    if in_speech:
        # Find last speech frame
        last_speech = len(rms) - 1
        while last_speech >= onset and not speech_mask[last_speech]:
            last_speech -= 1
        regions.append((onset, last_speech + 1))

    return regions


def _refine_segment_timestamps(audio_path: str, segments: list) -> list:
    """Refine and split Whisper segments using energy-based voice activity detection.

    Whisper often groups multiple speech bursts (separated by pauses) into a
    single segment. This analyzes the actual audio waveform to:
    1. Find precise speech onset/offset (trim leading/trailing silence)
    2. Split segments that contain internal silence gaps into sub-segments

    Text is split proportionally by speech duration when a segment is split.
    """
    import soundfile as sf

    audio, sr = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio[:, 0]  # mono

    frame_ms = 20
    frame_len = int(sr * frame_ms / 1000)
    n_frames = len(audio) // frame_len
    if n_frames == 0:
        return segments

    # RMS energy per frame
    rms = np.array([
        np.sqrt(np.mean(audio[i * frame_len:(i + 1) * frame_len] ** 2))
        for i in range(n_frames)
    ], dtype=np.float32)

    # Adaptive threshold: 3x the estimated noise floor
    nonzero_rms = rms[rms > 0]
    if len(nonzero_rms) == 0:
        return segments
    threshold = float(np.percentile(nonzero_rms, 15)) * 3
    threshold = max(threshold, 0.005)

    # Minimum silence gap to trigger a split (300ms)
    min_gap_frames = int(0.3 * sr / frame_len)

    refined = []
    for seg in segments:
        start_frame = int(seg["start"] * sr / frame_len)
        end_frame = int(seg["end"] * sr / frame_len)
        end_frame = min(end_frame, n_frames)

        if start_frame >= end_frame:
            refined.append(seg)
            continue

        seg_rms = rms[start_frame:end_frame]
        regions = _find_speech_regions(seg_rms, threshold, min_gap_frames)

        if not regions:
            refined.append(seg)
            continue

        if len(regions) == 1:
            # Single speech region — just refine start/end
            onset, offset = regions[0]
            refined_start = round((start_frame + onset) * frame_len / sr, 3)
            refined_end = round((start_frame + offset) * frame_len / sr, 3)
            refined.append({
                "start": refined_start,
                "end": refined_end,
                "text": seg["text"],
            })
        else:
            # Multiple speech regions — split segment at silence gaps
            # Divide text proportionally by speech duration
            region_durations = [(off - on) for on, off in regions]
            total_speech = sum(region_durations)
            text = seg["text"].strip()
            text_pos = 0

            for idx, (onset, offset) in enumerate(regions):
                refined_start = round((start_frame + onset) * frame_len / sr, 3)
                refined_end = round((start_frame + offset) * frame_len / sr, 3)

                if idx == len(regions) - 1:
                    # Last region gets remaining text
                    sub_text = text[text_pos:].strip()
                else:
                    # Split text proportionally by speech duration
                    proportion = region_durations[idx] / total_speech
                    char_end = text_pos + int(len(text) * proportion)
                    # Try to split at a word/sentence boundary
                    split_at = char_end
                    for offset_search in range(min(20, char_end - text_pos)):
                        check = char_end + offset_search
                        if check < len(text) and text[check] in " .,;!?":
                            split_at = check + 1
                            break
                        check = char_end - offset_search
                        if check > text_pos and text[check] in " .,;!?":
                            split_at = check + 1
                            break
                    sub_text = text[text_pos:split_at].strip()
                    text_pos = split_at

                if sub_text:
                    logger.info(
                        "Split segment [%.1f-%.1f] -> sub %d/%d [%.1f-%.1f] '%s'",
                        seg["start"], seg["end"],
                        idx + 1, len(regions),
                        refined_start, refined_end,
                        sub_text[:40],
                    )
                    refined.append({
                        "start": refined_start,
                        "end": refined_end,
                        "text": sub_text,
                    })

    return refined


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
        if seg.get("no_speech_prob", 0) > 0.6:
            continue
        if seg.get("compression_ratio", 0) > 2.4:
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

    result = _whisper_model.generate(str(audio_path))

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
        # Generator of results — collect all text
        collected = list(result)
        text = " ".join(
            s.text.strip() if hasattr(s, "text") else str(s).strip()
            for s in collected
        ).strip()

    # Get precise duration from audio file
    duration = 0.0
    try:
        import soundfile as sf

        info = sf.info(audio_path)
        duration = info.duration
    except Exception:
        pass

    segments = _filter_segments(raw_segments)
    segments = _refine_segment_timestamps(audio_path, segments)
    logger.info(
        "Transcribed: %.1fs audio -> %d chars, %d segments (from %d raw)",
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
