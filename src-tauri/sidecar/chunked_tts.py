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
# Proportional silence insertion
# ---------------------------------------------------------------------------


def pad_audio_to_match_timing(
    audio: np.ndarray,
    sample_rate: int,
    word_timing: list,
) -> np.ndarray:
    """Insert silence between words in TTS audio to match original speech pacing.

    TTS generates continuous speech without the natural micro-pauses between
    words that the original speaker had. This estimates where each word boundary
    falls in the TTS output (proportional by character count), then inserts
    silence at those points to match the original inter-word gaps.

    Args:
        audio: TTS-generated audio for the phrase.
        sample_rate: Audio sample rate.
        word_timing: List of {"word": str, "start": float, "end": float}
                     from the original Whisper transcription.
    """
    if not word_timing or len(word_timing) < 2 or len(audio) == 0:
        return audio

    # Calculate original inter-word gaps (the pauses TTS didn't reproduce)
    gaps = []
    for i in range(1, len(word_timing)):
        gap = word_timing[i]["start"] - word_timing[i - 1]["end"]
        gaps.append(max(0.0, gap))

    total_gap = sum(gaps)
    if total_gap < 0.05:
        # Less than 50ms total gap — not worth inserting
        return audio

    # Estimate word boundaries in TTS audio proportional to character count
    words_text = [w["word"] for w in word_timing]
    char_counts = [len(w) for w in words_text]
    total_chars = sum(char_counts)
    if total_chars == 0:
        return audio

    # Build the padded output by splitting TTS audio at estimated word
    # boundaries and inserting silence proportional to original gaps
    pieces = []
    audio_pos = 0

    for i, char_count in enumerate(char_counts):
        # Proportion of TTS audio this word occupies
        proportion = char_count / total_chars
        word_samples = int(proportion * len(audio))

        # Extract this word's audio
        word_end = min(audio_pos + word_samples, len(audio))
        pieces.append(audio[audio_pos:word_end])
        audio_pos = word_end

        # Insert silence matching the original gap after this word
        if i < len(gaps) and gaps[i] > 0.01:  # skip tiny gaps < 10ms
            silence_samples = int(gaps[i] * sample_rate)
            pieces.append(np.zeros(silence_samples, dtype=np.float32))

    # Append any remaining audio
    if audio_pos < len(audio):
        pieces.append(audio[audio_pos:])

    return np.concatenate(pieces) if pieces else audio


# ---------------------------------------------------------------------------
# Timestamp-aware audio assembly
# ---------------------------------------------------------------------------


def assemble_timed_segments(
    tts_segments: List[Tuple[np.ndarray, float, float]],
    original_duration: float,
    sample_rate: int,
) -> np.ndarray:
    """Assemble TTS audio segments at original timestamps with silence gaps.

    Follows the open-dubbing approach: each segment's available window extends
    to the START of the next segment (not its own end). TTS plays at natural
    speed with no truncation or fading — it finishes when it finishes, and
    silence fills the remaining gap. Only truncates if TTS would actually
    overlap the next segment.

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

    for i, (audio, start_sec, _end_sec) in enumerate(tts_segments):
        if len(audio) == 0:
            continue

        start_sample = int(start_sec * sample_rate)

        # Available window extends to the start of the NEXT segment,
        # not this segment's end. This gives TTS room to breathe.
        if i + 1 < len(tts_segments):
            next_start_sec = tts_segments[i + 1][1]  # next segment's start
            max_end_sample = int(next_start_sec * sample_rate)
        else:
            max_end_sample = total_samples

        available_samples = max_end_sample - start_sample
        if available_samples <= 0:
            continue

        # Only truncate if TTS would overlap the next segment
        if len(audio) > available_samples:
            audio = audio[:available_samples]

        # Place in output buffer — no fading, natural TTS start and end
        end_sample = min(start_sample + len(audio), total_samples)
        place_len = end_sample - start_sample
        if place_len > 0:
            output[start_sample:end_sample] = audio[:place_len]

    return output
