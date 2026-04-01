"""Chunked TTS generation and timed audio assembly utilities.

Splits long text into sentence-boundary chunks, generates audio per-chunk,
and concatenates with crossfade. Ported from Voicebox with minimal changes.

Also provides timestamp-aware audio assembly: placing TTS segments at their
original timestamps with silence gaps and optional time-stretching.

Short text (≤ max_chunk_chars) uses the single-shot fast path with zero overhead.
"""

import logging
import re
from typing import List, Tuple

import numpy as np

logger = logging.getLogger("voiceover-tts.chunked")

DEFAULT_MAX_CHUNK_CHARS = 800

_ABBREVIATIONS = frozenset(
    {
        "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "ave", "blvd",
        "inc", "ltd", "corp", "dept", "est", "approx", "vs", "etc",
        "e.g", "i.e", "a.m", "p.m", "u.s", "u.s.a", "u.k",
    }
)

_PARA_TAG_RE = re.compile(r"\[[^\]]*\]")


def split_text_into_chunks(text: str, max_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> List[str]:
    """Split text at natural boundaries into chunks of at most max_chars."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    remaining = text

    while remaining:
        remaining = remaining.lstrip()
        if not remaining:
            break
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        segment = remaining[:max_chars]
        split_pos = _find_last_sentence_end(segment)
        if split_pos == -1:
            split_pos = _find_last_clause_boundary(segment)
        if split_pos == -1:
            split_pos = segment.rfind(" ")
        if split_pos == -1:
            split_pos = _safe_hard_cut(segment, max_chars)

        chunk = remaining[: split_pos + 1].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_pos + 1 :]

    return chunks


def _find_last_sentence_end(text: str) -> int:
    best = -1
    for m in re.finditer(r"[.!?](?:\s|$)", text):
        pos = m.start()
        char = text[pos]
        if char == ".":
            word_start = pos - 1
            while word_start >= 0 and text[word_start].isalpha():
                word_start -= 1
            word = text[word_start + 1 : pos].lower()
            if word in _ABBREVIATIONS:
                continue
            if word_start >= 0 and text[word_start].isdigit():
                continue
        if _inside_bracket_tag(text, pos):
            continue
        best = pos
    for m in re.finditer(r"[\u3002\uff01\uff1f]", text):
        if m.start() > best:
            best = m.start()
    return best


def _find_last_clause_boundary(text: str) -> int:
    best = -1
    for m in re.finditer(r"[;:,\u2014](?:\s|$)", text):
        pos = m.start()
        if _inside_bracket_tag(text, pos):
            continue
        best = pos
    return best


def _inside_bracket_tag(text: str, pos: int) -> bool:
    for m in _PARA_TAG_RE.finditer(text):
        if m.start() < pos < m.end():
            return True
    return False


def _safe_hard_cut(segment: str, max_chars: int) -> int:
    cut = max_chars - 1
    for m in _PARA_TAG_RE.finditer(segment):
        if m.start() < cut < m.end():
            return m.start() - 1 if m.start() > 0 else cut
    return cut


def concatenate_audio_chunks(
    chunks: List[np.ndarray],
    sample_rate: int,
    crossfade_ms: int = 50,
) -> np.ndarray:
    """Concatenate audio arrays with a short crossfade to eliminate clicks."""
    if not chunks:
        return np.array([], dtype=np.float32)
    if len(chunks) == 1:
        return chunks[0]

    crossfade_samples = int(sample_rate * crossfade_ms / 1000)
    result = np.array(chunks[0], dtype=np.float32, copy=True)

    for chunk in chunks[1:]:
        if len(chunk) == 0:
            continue
        overlap = min(crossfade_samples, len(result), len(chunk))
        if overlap > 0:
            fade_out = np.linspace(1.0, 0.0, overlap, dtype=np.float32)
            fade_in = np.linspace(0.0, 1.0, overlap, dtype=np.float32)
            result[-overlap:] = result[-overlap:] * fade_out + chunk[:overlap] * fade_in
            result = np.concatenate([result, chunk[overlap:]])
        else:
            result = np.concatenate([result, chunk])

    return result


# ---------------------------------------------------------------------------
# Timestamp-aware audio assembly
# ---------------------------------------------------------------------------

STRETCH_THRESHOLD = 0.15  # Only time-stretch if >15% duration mismatch
STRETCH_MIN_RATE = 0.25
STRETCH_MAX_RATE = 4.0


def apply_fade(
    audio: np.ndarray,
    sample_rate: int,
    fade_ms: int = 5,
) -> np.ndarray:
    """Apply fade-in and fade-out to prevent clicks at segment boundaries."""
    fade_samples = int(sample_rate * fade_ms / 1000)
    if len(audio) < 2 * fade_samples:
        return audio

    audio = audio.copy()
    audio[:fade_samples] *= np.linspace(0, 1, fade_samples, dtype=np.float32)
    audio[-fade_samples:] *= np.linspace(1, 0, fade_samples, dtype=np.float32)
    return audio


def time_stretch_segment(
    audio: np.ndarray,
    sample_rate: int,
    rate: float,
) -> np.ndarray:
    """Stretch or compress audio to fit a target duration without pitch change.

    Args:
        audio: Input audio array (float32).
        sample_rate: Audio sample rate.
        rate: Stretch factor. >1.0 = speed up (shorter output),
              <1.0 = slow down (longer output).
              rate = actual_duration / target_duration

    Uses pyrubberband (highest quality for speech) with librosa as fallback.
    """
    if len(audio) == 0 or abs(rate - 1.0) < 0.01:
        return audio

    rate = max(STRETCH_MIN_RATE, min(rate, STRETCH_MAX_RATE))

    try:
        import pyrubberband as pyrb
        return pyrb.time_stretch(audio, sample_rate, rate, rbargs={"-c": "6"}).astype(
            np.float32
        )
    except (ImportError, FileNotFoundError):
        pass

    try:
        import librosa
        return librosa.effects.time_stretch(audio, rate=rate).astype(np.float32)
    except ImportError:
        pass

    logger.warning("No time-stretch library available; returning audio unchanged")
    return audio


def assemble_timed_segments(
    tts_segments: List[Tuple[np.ndarray, float, float]],
    original_duration: float,
    sample_rate: int,
) -> np.ndarray:
    """Assemble TTS audio segments at original timestamps with silence gaps.

    Args:
        tts_segments: List of (audio_array, original_start_sec, original_end_sec).
        original_duration: Total duration of the original recording in seconds.
        sample_rate: Target sample rate (must match TTS output).

    Returns:
        Assembled float32 audio array padded to exactly original_duration.
    """
    total_samples = int(original_duration * sample_rate)
    output = np.zeros(total_samples, dtype=np.float32)

    if not tts_segments:
        return output

    for audio, start_sec, end_sec in tts_segments:
        if len(audio) == 0:
            continue

        start_sample = int(start_sec * sample_rate)
        target_duration = end_sec - start_sec
        if target_duration <= 0:
            continue

        target_samples = int(target_duration * sample_rate)
        actual_samples = len(audio)

        # Time-stretch if duration mismatch exceeds threshold
        if actual_samples > 0 and target_samples > 0:
            rate = actual_samples / target_samples
            if abs(rate - 1.0) > STRETCH_THRESHOLD:
                audio = time_stretch_segment(audio, sample_rate, rate)
                actual_samples = len(audio)

        # Pad or truncate to fit target duration
        if actual_samples < target_samples:
            audio = np.pad(audio, (0, target_samples - actual_samples))
        elif actual_samples > target_samples:
            audio = audio[:target_samples]

        # Apply fade to prevent clicks at boundaries
        audio = apply_fade(audio, sample_rate)

        # Place in output buffer with bounds checking
        end_sample = min(start_sample + len(audio), total_samples)
        place_len = end_sample - start_sample
        if place_len > 0:
            output[start_sample:end_sample] = audio[:place_len]

    return output
