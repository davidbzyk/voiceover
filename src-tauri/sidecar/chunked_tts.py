"""Chunked TTS generation and timed audio assembly utilities.

Splits long text into sentence-boundary chunks, generates audio per-chunk,
and concatenates with crossfade. Ported from Voicebox with minimal changes.

Also provides timestamp-aware audio assembly: placing TTS segments at their
original timestamps with silence gaps.

Short text (≤ max_chunk_chars) uses the single-shot fast path with zero overhead.
"""

from __future__ import annotations

import logging
import re

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


def split_text_into_chunks(text: str, max_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> list[str]:
    """Split text at natural boundaries into chunks of at most max_chars."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
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
    chunks: list[np.ndarray],
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


def _fix_degenerate_timestamps(word_timing: list) -> list:
    """Interpolate timestamps for words where Whisper gave zero duration.

    Whisper sometimes collapses multiple words to the same timestamp when it
    loses track (common with repetitive content). This estimates real timing
    by chaining degenerate words sequentially using the average valid word
    duration from the same segment.
    """
    if not word_timing or len(word_timing) < 2:
        return word_timing

    # Calculate average duration from words with valid timestamps
    valid_durations = [
        w["end"] - w["start"]
        for w in word_timing
        if w["end"] - w["start"] > 0.01
    ]
    if not valid_durations:
        return word_timing

    avg_duration = sum(valid_durations) / len(valid_durations)
    avg_gap = avg_duration * 0.15  # ~15% of word duration as inter-word gap

    fixed = []
    for w in word_timing:
        fw = dict(w)
        dur = w["end"] - w["start"]
        if dur < 0.01:  # degenerate zero-duration word
            if fixed:
                fw["start"] = fixed[-1]["end"] + avg_gap
            fw["end"] = fw["start"] + avg_duration
        fixed.append(fw)

    return fixed


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

    # Fix degenerate timestamps before calculating gaps
    word_timing = _fix_degenerate_timestamps(word_timing)

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
    # boundaries and inserting silence proportional to original gaps.
    # Apply short crossfades at boundaries for smooth transitions.
    fade_samples = min(int(sample_rate * 0.025), 400)  # 25ms fade

    pieces = []
    audio_pos = 0

    for i, char_count in enumerate(char_counts):
        # Proportion of TTS audio this word occupies
        proportion = char_count / total_chars
        word_samples = int(proportion * len(audio))

        # Extract this word's audio
        word_end = min(audio_pos + word_samples, len(audio))
        word_piece = np.array(audio[audio_pos:word_end], dtype=np.float32, copy=True)
        audio_pos = word_end

        # Apply crossfades at boundaries where we'll insert silence
        if i < len(gaps) and gaps[i] > 0.01 and len(word_piece) > fade_samples * 2:
            # Fade out end of this word piece
            fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
            word_piece[-fade_samples:] *= fade_out

        pieces.append(word_piece)

        # Insert silence matching the original gap after this word
        if i < len(gaps) and gaps[i] > 0.01:
            silence_samples = int(gaps[i] * sample_rate)
            pieces.append(np.zeros(silence_samples, dtype=np.float32))

            # Fade in the start of the next word piece (applied on next iteration)
            # — handled by peeking at the next piece after the loop

    # Append any remaining audio
    if audio_pos < len(audio):
        pieces.append(audio[audio_pos:])

    if not pieces:
        return audio

    # Apply fade-in to each word piece that follows a silence gap
    result_pieces = []
    for j, piece in enumerate(pieces):
        if j > 0 and len(piece) > fade_samples * 2:
            # Check if previous piece was silence (all zeros)
            prev = result_pieces[-1] if result_pieces else None
            if prev is not None and len(prev) > 0 and np.max(np.abs(prev)) < 1e-6:
                piece = np.array(piece, dtype=np.float32, copy=True)
                fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
                piece[:fade_samples] *= fade_in
        result_pieces.append(piece)

    return np.concatenate(result_pieces)


# ---------------------------------------------------------------------------
# Pad / truncate to target duration
# ---------------------------------------------------------------------------


def pad_or_truncate_to_duration(audio: np.ndarray, sample_rate: int, target_duration: float, fade_ms: float = 300) -> np.ndarray:
    """Pad (with fade-out) or truncate audio to match target duration."""
    if target_duration <= 0 or not sample_rate:
        return audio
    target_samples = int(target_duration * sample_rate)
    if len(audio) < target_samples:
        fade_samples = min(int(fade_ms / 1000 * sample_rate), len(audio) // 2)
        if fade_samples > 0:
            fade = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
            audio = audio.copy()
            audio[-fade_samples:] *= fade
        audio = np.pad(audio, (0, target_samples - len(audio)))
    elif len(audio) > target_samples:
        audio = audio[:target_samples]
    return audio


# ---------------------------------------------------------------------------
# Timestamp-aware audio assembly
# ---------------------------------------------------------------------------


def assemble_timed_segments(
    tts_segments: list[tuple[np.ndarray, float, float]],
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
