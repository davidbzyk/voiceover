"""Tests for tts.py — word grouping, segment filtering, hallucination detection."""

import pytest

from tts import _filter_segments, _group_words_into_phrases, _is_hallucinated


# ---------------------------------------------------------------------------
# _is_hallucinated
# ---------------------------------------------------------------------------


class TestIsHallucinated:
    def test_normal_segment_not_hallucinated(self):
        seg = {"no_speech_prob": 0.1, "compression_ratio": 1.5}
        assert _is_hallucinated(seg) is False

    def test_high_no_speech_prob(self):
        seg = {"no_speech_prob": 0.8, "compression_ratio": 1.5}
        assert _is_hallucinated(seg) is True

    def test_boundary_no_speech_prob(self):
        assert _is_hallucinated({"no_speech_prob": 0.6}) is False
        assert _is_hallucinated({"no_speech_prob": 0.61}) is True

    def test_high_compression_ratio(self):
        seg = {"no_speech_prob": 0.1, "compression_ratio": 3.0}
        assert _is_hallucinated(seg) is True

    def test_boundary_compression_ratio(self):
        assert _is_hallucinated({"compression_ratio": 2.4}) is False
        assert _is_hallucinated({"compression_ratio": 2.41}) is True

    def test_missing_keys_default_to_zero(self):
        assert _is_hallucinated({}) is False

    def test_both_bad(self):
        seg = {"no_speech_prob": 0.9, "compression_ratio": 5.0}
        assert _is_hallucinated(seg) is True


# ---------------------------------------------------------------------------
# _filter_segments
# ---------------------------------------------------------------------------


class TestFilterSegments:
    def test_empty_input(self):
        assert _filter_segments([]) == []

    def test_filters_non_dict(self):
        assert _filter_segments(["not a dict", 42, None]) == []

    def test_filters_hallucinated_segments(self):
        segments = [
            {"start": 0, "end": 1, "text": "real", "no_speech_prob": 0.1, "compression_ratio": 1.2},
            {"start": 1, "end": 2, "text": "hallucinated", "no_speech_prob": 0.9, "compression_ratio": 1.0},
            {"start": 2, "end": 3, "text": "also real", "no_speech_prob": 0.2, "compression_ratio": 1.5},
        ]
        result = _filter_segments(segments)
        assert len(result) == 2
        assert result[0]["text"] == "real"
        assert result[1]["text"] == "also real"

    def test_filters_empty_text(self):
        segments = [
            {"start": 0, "end": 1, "text": "  ", "no_speech_prob": 0.1},
            {"start": 1, "end": 2, "text": "hello", "no_speech_prob": 0.1},
        ]
        result = _filter_segments(segments)
        assert len(result) == 1
        assert result[0]["text"] == "hello"

    def test_outputs_only_start_end_text(self):
        seg = {"start": 1.5, "end": 3.2, "text": "hi", "no_speech_prob": 0.1,
               "tokens": [1, 2], "temperature": 0.5}
        result = _filter_segments([seg])
        assert set(result[0].keys()) == {"start", "end", "text"}

    def test_converts_to_float(self):
        seg = {"start": 1, "end": 2, "text": "hi"}
        result = _filter_segments([seg])
        assert isinstance(result[0]["start"], float)
        assert isinstance(result[0]["end"], float)

    def test_clamps_overlapping_timestamps(self):
        segments = [
            {"start": 0.0, "end": 5.0, "text": "first"},
            {"start": 3.0, "end": 7.0, "text": "overlaps"},
            {"start": 6.0, "end": 10.0, "text": "also overlaps"},
        ]
        result = _filter_segments(segments)
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 5.0
        assert result[1]["start"] == 5.0  # clamped from 3.0
        assert result[2]["start"] == 7.0  # clamped from 6.0

    def test_non_overlapping_untouched(self):
        segments = [
            {"start": 0.0, "end": 2.0, "text": "a"},
            {"start": 3.0, "end": 5.0, "text": "b"},
        ]
        result = _filter_segments(segments)
        assert result[0]["start"] == 0.0
        assert result[1]["start"] == 3.0


# ---------------------------------------------------------------------------
# _group_words_into_phrases
# ---------------------------------------------------------------------------


class TestGroupWordsIntoPhrases:
    def test_empty_input(self):
        assert _group_words_into_phrases([]) == []

    def test_single_word(self):
        words = [{"word": " Hello", "start": 0.5, "end": 1.0}]
        result = _group_words_into_phrases(words)
        assert len(result) == 1
        assert result[0]["text"] == "Hello"
        assert result[0]["start"] == 0.5
        assert result[0]["end"] == 1.0

    def test_continuous_words_grouped(self):
        words = [
            {"word": " Hello", "start": 0.5, "end": 0.9},
            {"word": " world", "start": 0.95, "end": 1.3},
        ]
        result = _group_words_into_phrases(words)
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"
        assert result[0]["start"] == 0.5
        assert result[0]["end"] == 1.3

    def test_pause_splits_into_two_phrases(self):
        words = [
            {"word": " Hello", "start": 0.5, "end": 1.0},
            {"word": " world", "start": 2.0, "end": 2.5},  # 1.0s gap
        ]
        result = _group_words_into_phrases(words)
        assert len(result) == 2
        assert result[0]["text"] == "Hello"
        assert result[0]["start"] == 0.5
        assert result[0]["end"] == 1.0
        assert result[1]["text"] == "world"
        assert result[1]["start"] == 2.0
        assert result[1]["end"] == 2.5

    def test_custom_pause_threshold(self):
        words = [
            {"word": " a", "start": 0.0, "end": 0.5},
            {"word": " b", "start": 1.0, "end": 1.5},  # 0.5s gap
        ]
        # Default 0.3s threshold — should split
        assert len(_group_words_into_phrases(words, min_pause_sec=0.3)) == 2
        # Higher threshold — should NOT split
        assert len(_group_words_into_phrases(words, min_pause_sec=0.6)) == 1

    def test_three_phrases_with_pauses(self):
        words = [
            {"word": " one", "start": 0.0, "end": 0.5},
            {"word": " two", "start": 0.6, "end": 1.0},
            # 1s gap
            {"word": " three", "start": 2.0, "end": 2.5},
            # 0.8s gap
            {"word": " four", "start": 3.3, "end": 3.8},
        ]
        result = _group_words_into_phrases(words)
        assert len(result) == 3
        assert result[0]["text"] == "one two"
        assert result[1]["text"] == "three"
        assert result[2]["text"] == "four"

    def test_skips_empty_word_text(self):
        # Empty word is skipped, but gap from Hello(end=0.5) to world(start=0.8)
        # is 0.3s which equals the threshold — so it splits into two phrases
        words = [
            {"word": " Hello", "start": 0.0, "end": 0.5},
            {"word": "", "start": 0.6, "end": 0.7},
            {"word": " world", "start": 0.8, "end": 1.2},
        ]
        result = _group_words_into_phrases(words)
        assert len(result) == 2
        assert result[0]["text"] == "Hello"
        assert result[1]["text"] == "world"

    def test_empty_word_no_split_when_gap_small(self):
        # Empty word skipped, small gap — stays as one phrase
        words = [
            {"word": " Hello", "start": 0.0, "end": 0.5},
            {"word": "", "start": 0.55, "end": 0.6},
            {"word": " world", "start": 0.65, "end": 1.0},
        ]
        result = _group_words_into_phrases(words)
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"

    def test_text_key_fallback(self):
        """Some Whisper implementations use 'text' instead of 'word'."""
        words = [
            {"text": " Hello", "start": 0.0, "end": 0.5},
            {"text": " world", "start": 0.6, "end": 1.0},
        ]
        result = _group_words_into_phrases(words)
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"

    def test_boundary_pause_exactly_at_threshold(self):
        words = [
            {"word": " a", "start": 0.0, "end": 1.0},
            {"word": " b", "start": 1.3, "end": 2.0},  # exactly 0.3s gap
        ]
        result = _group_words_into_phrases(words, min_pause_sec=0.3)
        assert len(result) == 2  # gap == threshold triggers split

    def test_preserves_whisper_word_spacing(self):
        """Whisper includes leading spaces in 'word' — join preserves them."""
        words = [
            {"word": " I'm", "start": 0.0, "end": 0.3},
            {"word": " coming", "start": 0.35, "end": 0.7},
            {"word": " for", "start": 0.75, "end": 0.9},
            {"word": " you", "start": 0.95, "end": 1.1},
        ]
        result = _group_words_into_phrases(words)
        assert result[0]["text"] == "I'm coming for you"
