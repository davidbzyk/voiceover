"""Tests for chunked_tts.py — text chunking, audio concatenation, timed assembly."""

import numpy as np
import pytest

from chunked_tts import (
    ConversionCancelled,
    assemble_timed_segments,
    concatenate_audio_chunks,
    convert_in_overlapping_chunks,
    pad_audio_to_match_timing,
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


# ---------------------------------------------------------------------------
# pad_audio_to_match_timing
# ---------------------------------------------------------------------------


class TestPadAudioToMatchTiming:
    def _make_audio(self, duration_s: float, sr: int = 24000) -> np.ndarray:
        """Helper: create a non-silent audio array of given duration."""
        samples = int(duration_s * sr)
        return np.random.randn(samples).astype(np.float32)

    def test_empty_word_timing_returns_unchanged(self):
        audio = self._make_audio(1.0)
        result = pad_audio_to_match_timing(audio, 24000, [])
        np.testing.assert_array_equal(result, audio)

    def test_single_word_returns_unchanged(self):
        audio = self._make_audio(1.0)
        timing = [{"word": "Hello", "start": 0.0, "end": 1.0}]
        result = pad_audio_to_match_timing(audio, 24000, timing)
        np.testing.assert_array_equal(result, audio)

    def test_small_gap_returns_unchanged(self):
        """Total gaps under 50ms threshold should return audio unchanged."""
        audio = self._make_audio(2.0)
        timing = [
            {"word": "Hello", "start": 0.0, "end": 0.98},
            {"word": "world", "start": 1.0, "end": 2.0},  # 20ms gap
        ]
        result = pad_audio_to_match_timing(audio, 24000, timing)
        np.testing.assert_array_equal(result, audio)

    def test_gap_inserts_silence(self):
        """A significant gap between words should make output longer."""
        sr = 24000
        audio = self._make_audio(2.0, sr)
        timing = [
            {"word": "Hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 1.5, "end": 2.0},  # 500ms gap
        ]
        result = pad_audio_to_match_timing(audio, sr, timing)
        assert len(result) > len(audio), "Output should be longer due to inserted silence"

    def test_returns_ndarray(self):
        audio = self._make_audio(1.0)
        timing = [{"word": "Hi", "start": 0.0, "end": 1.0}]
        result = pad_audio_to_match_timing(audio, 24000, timing)
        assert isinstance(result, np.ndarray)

    def test_empty_audio_returns_unchanged(self):
        """Empty audio array should be returned as-is."""
        audio = np.array([], dtype=np.float32)
        timing = [
            {"word": "Hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 1.5, "end": 2.0},
        ]
        result = pad_audio_to_match_timing(audio, 24000, timing)
        np.testing.assert_array_equal(result, audio)

    def test_multiple_gaps_accumulate(self):
        """Multiple gaps should all contribute to a longer output."""
        sr = 24000
        audio = self._make_audio(3.0, sr)
        timing = [
            {"word": "Hello", "start": 0.0, "end": 0.8},
            {"word": "beautiful", "start": 1.3, "end": 2.0},  # 500ms gap
            {"word": "world", "start": 2.8, "end": 3.0},      # 800ms gap
        ]
        result = pad_audio_to_match_timing(audio, sr, timing)
        # Total gap is 1.3s which is well above 50ms threshold
        assert len(result) > len(audio)

    def test_output_dtype_is_float32(self):
        """Output should be float32 regardless of inserted silence."""
        sr = 24000
        audio = self._make_audio(2.0, sr)
        timing = [
            {"word": "Hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 1.5, "end": 2.0},
        ]
        result = pad_audio_to_match_timing(audio, sr, timing)
        assert result.dtype == np.float32


# ---------------------------------------------------------------------------
# convert_in_overlapping_chunks
# ---------------------------------------------------------------------------


class TestConvertInOverlappingChunks:
    """Voice conversion over long recordings must keep the recording's length and timing."""

    def test_every_chunk_empty_is_a_failure_not_silence(self):
        with pytest.raises(ValueError, match="no audio"):
            convert_in_overlapping_chunks(
                np.zeros(60 * 16000, dtype=np.float32), 16000,
                lambda chunk: np.zeros(0, dtype=np.float32),
            )

    def test_short_recording_honours_cancel_before_converting(self):
        calls = []
        with pytest.raises(ConversionCancelled):
            convert_in_overlapping_chunks(
                np.zeros(10 * 16000, dtype=np.float32), 16000,
                lambda chunk: calls.append(chunk) or chunk,
                should_cancel=lambda: True,
            )
        assert calls == []

    def test_identity_conversion_preserves_length_of_long_recording(self):
        # 410.3s matches the real 6m50s recording that drifted out of sync
        source = np.random.default_rng(0).standard_normal(int(410.3 * SR)).astype(np.float32)
        out = convert_in_overlapping_chunks(source, SR, lambda chunk: chunk)
        assert abs(len(out) - len(source)) <= 1

    def test_identity_conversion_keeps_late_audio_in_place(self):
        source = np.zeros(int(120 * SR), dtype=np.float32)
        marker = int(110 * SR)
        source[marker : marker + 100] = 1.0
        out = convert_in_overlapping_chunks(source, SR, lambda chunk: chunk)
        assert int(np.argmax(out)) == marker

    def test_short_recording_is_one_call(self):
        calls = []
        source = np.ones(int(5 * SR), dtype=np.float32)
        out = convert_in_overlapping_chunks(source, SR, lambda c: calls.append(len(c)) or c)
        assert calls == [len(source)]
        assert len(out) == len(source)

    def test_reports_progress_per_chunk(self):
        seen = []
        source = np.zeros(int(60 * SR), dtype=np.float32)
        convert_in_overlapping_chunks(source, SR, lambda c: c, on_progress=lambda d, t: seen.append((d, t)))
        total = seen[0][1]
        assert seen == [(i, total) for i in range(total + 1)]

    def test_cancel_stops_before_next_chunk(self):
        calls = []
        source = np.zeros(int(100 * SR), dtype=np.float32)
        with pytest.raises(ConversionCancelled):
            convert_in_overlapping_chunks(
                source, SR, lambda c: calls.append(1) or c, should_cancel=lambda: len(calls) >= 2
            )
        assert len(calls) == 2

    def test_empty_chunk_keeps_its_slot_so_later_audio_stays_in_sync(self):
        source = np.zeros(int(120 * SR), dtype=np.float32)
        marker = int(110 * SR)
        source[marker : marker + 100] = 1.0
        calls = []

        def convert(chunk):
            calls.append(1)
            return np.array([], dtype=np.float32) if len(calls) == 2 else chunk

        out = convert_in_overlapping_chunks(source, SR, convert)
        assert abs(len(out) - len(source)) <= 1
        assert int(np.argmax(out)) == marker

    def test_chunk_that_comes_back_longer_does_not_push_later_audio_out_of_sync(self):
        source = np.zeros(int(120 * SR), dtype=np.float32)
        marker = int(110 * SR)
        source[marker : marker + 100] = 1.0

        def convert(chunk):
            # A model that returns 1% more audio than it was given
            return np.concatenate([chunk, np.zeros(len(chunk) // 100, dtype=np.float32)])

        out = convert_in_overlapping_chunks(source, SR, convert)
        assert abs(len(out) - len(source)) <= 1
        assert abs(int(np.argmax(out)) - marker) <= SR // 100


def test_reinserted_gap_seconds_is_what_the_padder_adds():
    """The replace job tells MOSS to speak a phrase's length minus these gaps; if the two disagreed the
    padded phrase would overrun its slot and be cut."""
    from chunked_tts import pad_audio_to_match_timing, reinserted_gap_seconds

    sr = 24000
    words = [
        {"word": "one", "start": 0.0, "end": 0.3},
        {"word": "two", "start": 0.5, "end": 0.8},  # 0.2 s pause
        {"word": "three", "start": 0.805, "end": 1.2},  # 0.005 s, below the padder's 0.01 s floor
        {"word": "four", "start": 1.3, "end": 1.6},  # 0.1 s pause
    ]
    audio = np.ones(sr, dtype=np.float32)
    added = (len(pad_audio_to_match_timing(audio, sr, words)) - len(audio)) / sr
    assert reinserted_gap_seconds(words) == pytest.approx(added, abs=2 / sr)
    assert reinserted_gap_seconds(words[:1]) == 0.0
