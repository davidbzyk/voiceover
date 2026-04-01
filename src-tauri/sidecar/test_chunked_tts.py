"""Tests for chunked_tts.py — text chunking, audio concatenation, timed assembly."""

import numpy as np
import pytest

from chunked_tts import (
    assemble_timed_segments,
    concatenate_audio_chunks,
    split_text_into_chunks,
)

SR = 24000  # sample rate used throughout


# ---------------------------------------------------------------------------
# split_text_into_chunks
# ---------------------------------------------------------------------------


class TestSplitTextIntoChunks:
    def test_empty_string(self):
        assert split_text_into_chunks("") == []

    def test_whitespace_only(self):
        assert split_text_into_chunks("   ") == []

    def test_short_text_single_chunk(self):
        result = split_text_into_chunks("Hello world.")
        assert result == ["Hello world."]

    def test_exactly_at_limit(self):
        text = "a" * 800
        result = split_text_into_chunks(text, max_chars=800)
        assert len(result) == 1

    def test_splits_at_sentence_boundary(self):
        # Two sentences, each under 800 chars but combined over 800
        s1 = "A" * 400 + ". "
        s2 = "B" * 400 + "."
        result = split_text_into_chunks(s1 + s2, max_chars=500)
        assert len(result) >= 2

    def test_preserves_all_text(self):
        text = "Hello world. This is a test. Another sentence here."
        chunks = split_text_into_chunks(text, max_chars=30)
        rejoined = " ".join(c.strip() for c in chunks)
        # All words should be present
        for word in text.split():
            assert word.strip(".,") in rejoined


# ---------------------------------------------------------------------------
# concatenate_audio_chunks
# ---------------------------------------------------------------------------


class TestConcatenateAudioChunks:
    def test_empty_list(self):
        result = concatenate_audio_chunks([], SR)
        assert len(result) == 0

    def test_single_chunk(self):
        chunk = np.ones(1000, dtype=np.float32)
        result = concatenate_audio_chunks([chunk], SR)
        assert np.array_equal(result, chunk)

    def test_two_chunks_concatenated(self):
        a = np.ones(5000, dtype=np.float32)
        b = np.ones(3000, dtype=np.float32) * 0.5
        result = concatenate_audio_chunks([a, b], SR)
        # Result should be roughly len(a) + len(b) minus crossfade overlap
        crossfade_samples = int(SR * 50 / 1000)  # 50ms default
        expected = len(a) + len(b) - crossfade_samples
        assert abs(len(result) - expected) < 10

    def test_skips_empty_chunks(self):
        a = np.ones(5000, dtype=np.float32)
        empty = np.array([], dtype=np.float32)
        b = np.ones(3000, dtype=np.float32)
        result = concatenate_audio_chunks([a, empty, b], SR)
        assert len(result) > 5000

    def test_crossfade_produces_float32(self):
        a = np.ones(1000, dtype=np.float32)
        b = np.ones(1000, dtype=np.float32)
        result = concatenate_audio_chunks([a, b], SR)
        assert result.dtype == np.float32


# ---------------------------------------------------------------------------
# assemble_timed_segments
# ---------------------------------------------------------------------------


class TestAssembleTimedSegments:
    def _make_audio(self, duration_sec: float, value: float = 0.5) -> np.ndarray:
        """Create a constant-value audio array of given duration."""
        return np.full(int(SR * duration_sec), value, dtype=np.float32)

    def test_empty_segments(self):
        result = assemble_timed_segments([], 10.0, SR)
        assert len(result) == int(10.0 * SR)
        assert np.all(result == 0)

    def test_single_segment_placed_at_start(self):
        audio = self._make_audio(1.0, value=0.8)
        result = assemble_timed_segments([(audio, 0.0, 1.0)], 5.0, SR)
        assert len(result) == int(5.0 * SR)
        # First second should have audio
        assert np.mean(np.abs(result[:SR])) > 0.5
        # Rest should be silence
        assert np.all(result[int(1.1 * SR):] == 0)

    def test_single_segment_placed_at_offset(self):
        audio = self._make_audio(0.5, value=0.7)
        result = assemble_timed_segments([(audio, 2.0, 2.5)], 5.0, SR)
        # Before 2s should be silence
        assert np.all(result[:int(1.9 * SR)] == 0)
        # At 2s should have audio
        start = int(2.0 * SR)
        assert np.mean(np.abs(result[start:start + int(0.5 * SR)])) > 0.5

    def test_two_segments_with_gap(self):
        a = self._make_audio(1.0, value=0.5)
        b = self._make_audio(1.0, value=0.9)
        result = assemble_timed_segments(
            [(a, 0.0, 1.0), (b, 3.0, 4.0)], 5.0, SR
        )
        assert len(result) == int(5.0 * SR)
        # Gap between 1-3s should be silence
        gap = result[int(1.1 * SR):int(2.9 * SR)]
        assert np.all(gap == 0)
        # Second segment should be present
        seg2 = result[int(3.0 * SR):int(4.0 * SR)]
        assert np.mean(np.abs(seg2)) > 0.5

    def test_output_length_matches_duration(self):
        audio = self._make_audio(0.5)
        for duration in [1.0, 5.0, 30.0]:
            result = assemble_timed_segments([(audio, 0.0, 0.5)], duration, SR)
            assert len(result) == int(duration * SR)

    def test_skips_empty_audio(self):
        empty = np.array([], dtype=np.float32)
        real = self._make_audio(1.0, value=0.5)
        result = assemble_timed_segments(
            [(empty, 0.0, 1.0), (real, 2.0, 3.0)], 5.0, SR
        )
        # First second should be silence (empty audio skipped)
        assert np.all(result[:SR] == 0)
        # Second segment should be present
        assert np.mean(np.abs(result[int(2.0 * SR):int(3.0 * SR)])) > 0.3

    def test_truncates_when_overlapping_next_segment(self):
        # 2s of audio starting at 0, but next segment starts at 1s
        long_audio = self._make_audio(2.0, value=0.8)
        short_audio = self._make_audio(0.5, value=0.3)
        result = assemble_timed_segments(
            [(long_audio, 0.0, 2.0), (short_audio, 1.0, 1.5)], 3.0, SR
        )
        # At 1.0s the second segment should overwrite
        # Check that the second segment's value is present
        sample_at_1s = result[int(1.0 * SR)]
        assert abs(sample_at_1s - 0.3) < 0.01

    def test_last_segment_uses_full_duration_as_window(self):
        audio = self._make_audio(1.5, value=0.6)
        result = assemble_timed_segments([(audio, 3.0, 4.0)], 5.0, SR)
        # Audio should extend from 3.0 to 4.5 (not truncated at 4.0)
        # because last segment window extends to total_duration
        assert np.mean(np.abs(result[int(4.0 * SR):int(4.4 * SR)])) > 0.3

    def test_bounds_checking_near_end(self):
        # Segment placed near the end of the buffer
        audio = self._make_audio(2.0, value=0.5)
        result = assemble_timed_segments([(audio, 4.0, 6.0)], 5.0, SR)
        # Should not crash, audio truncated to fit buffer
        assert len(result) == int(5.0 * SR)
        assert np.mean(np.abs(result[int(4.0 * SR):])) > 0.3
