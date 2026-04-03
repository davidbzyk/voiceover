"""Tests for tts.py — word grouping and segment filtering."""

import pytest

from tts import _filter_segments, _group_words_into_phrases


# ---------------------------------------------------------------------------
# _filter_segments
# ---------------------------------------------------------------------------


class TestFilterSegments:
    def test_empty_input(self):
        assert _filter_segments([]) == []

    def test_filters_non_dict(self):
        assert _filter_segments(["not a dict", 42, None]) == []

    def test_keeps_all_segments_with_text(self):
        segments = [
            {"start": 0, "end": 1, "text": "real", "no_speech_prob": 0.1, "compression_ratio": 1.2},
            {"start": 1, "end": 2, "text": "repetitive", "no_speech_prob": 0.9, "compression_ratio": 3.0},
            {"start": 2, "end": 3, "text": "also real", "no_speech_prob": 0.2, "compression_ratio": 1.5},
        ]
        result = _filter_segments(segments)
        assert len(result) == 3

    def test_filters_empty_text(self):
        segments = [
            {"start": 0, "end": 1, "text": "  ", "no_speech_prob": 0.1},
            {"start": 1, "end": 2, "text": "hello", "no_speech_prob": 0.1},
        ]
        result = _filter_segments(segments)
        assert len(result) == 1
        assert result[0]["text"] == "hello"

    def test_outputs_only_start_end_text_words(self):
        seg = {"start": 1.5, "end": 3.2, "text": "hi", "no_speech_prob": 0.1,
               "tokens": [1, 2], "temperature": 0.5}
        result = _filter_segments([seg])
        assert set(result[0].keys()) == {"start", "end", "text", "words"}

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

    def test_basic_filtering(self):
        segments = [{"text": "Hello", "start": 0.0, "end": 1.0}]
        result = _filter_segments(segments)
        assert len(result) == 1
        assert result[0]["text"] == "Hello"

    def test_empty_text_filtered(self):
        segments = [{"text": "", "start": 0.0, "end": 1.0}]
        result = _filter_segments(segments)
        assert len(result) == 0

    def test_overlapping_clamped(self):
        segments = [
            {"text": "First", "start": 0.0, "end": 2.0},
            {"text": "Second", "start": 1.5, "end": 3.0},
        ]
        result = _filter_segments(segments)
        assert len(result) == 2
        assert result[1]["start"] >= result[0]["end"]

    def test_nested_overlap_degenerate_removed(self):
        """Segment fully contained within previous should be discarded after clamping."""
        segments = [
            {"text": "First", "start": 0.0, "end": 5.0},
            {"text": "Nested", "start": 1.0, "end": 2.0},  # fully inside First
            {"text": "Third", "start": 6.0, "end": 7.0},
        ]
        result = _filter_segments(segments)
        # After clamping, Nested's start becomes 5.0 but end is 2.0 -> degenerate
        # Team 1 is adding a guard to remove these, so this test expects it
        texts = [s["text"] for s in result]
        assert "Nested" not in texts  # degenerate segment should be removed
        assert "First" in texts
        assert "Third" in texts

    def test_hallucination_leading_dots_kept_if_no_guard(self):
        """Segments with leading dots/ellipsis: verify normal text is always preserved.

        Note: A leading-dot filter may be added later. This test ensures the
        normal segment is always present regardless.
        """
        segments = [
            {"text": "...weird hallucination", "start": 0.0, "end": 1.0},
            {"text": "Normal text", "start": 1.0, "end": 2.0},
        ]
        result = _filter_segments(segments)
        texts = [s["text"] for s in result]
        assert "Normal text" in texts


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
        assert "words" in result[0]

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
        assert "words" in result[0]

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
        assert "words" in result[0]
        assert result[1]["text"] == "world"
        assert result[1]["start"] == 2.0
        assert result[1]["end"] == 2.5
        assert "words" in result[1]

    def test_custom_pause_threshold(self):
        words = [
            {"word": " a", "start": 0.0, "end": 0.5},
            {"word": " b", "start": 1.0, "end": 1.5},  # 0.5s gap
        ]
        # Default 0.3s threshold — should split
        split_result = _group_words_into_phrases(words, min_pause_sec=0.3)
        assert len(split_result) == 2
        assert "words" in split_result[0]
        assert "words" in split_result[1]
        # Higher threshold — should NOT split
        merged_result = _group_words_into_phrases(words, min_pause_sec=0.6)
        assert len(merged_result) == 1
        assert "words" in merged_result[0]

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
        assert "words" in result[0]
        assert "words" in result[1]
        assert "words" in result[2]

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
        assert "words" in result[0]
        assert "words" in result[1]

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
        assert "words" in result[0]

    def test_text_key_fallback(self):
        """Some Whisper implementations use 'text' instead of 'word'."""
        words = [
            {"text": " Hello", "start": 0.0, "end": 0.5},
            {"text": " world", "start": 0.6, "end": 1.0},
        ]
        result = _group_words_into_phrases(words)
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"
        assert "words" in result[0]

    def test_boundary_pause_exactly_at_threshold(self):
        words = [
            {"word": " a", "start": 0.0, "end": 1.0},
            {"word": " b", "start": 1.3, "end": 2.0},  # exactly 0.3s gap
        ]
        result = _group_words_into_phrases(words, min_pause_sec=0.3)
        assert len(result) == 2  # gap == threshold triggers split
        assert "words" in result[0]
        assert "words" in result[1]

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
        assert "words" in result[0]

    def test_words_field_contains_original_words(self):
        """The 'words' field should contain the original word timing data."""
        words = [
            {"word": " Hello", "start": 0.5, "end": 1.0},
            {"word": " world", "start": 1.0, "end": 1.5},
        ]
        result = _group_words_into_phrases(words)
        assert len(result) == 1
        assert "words" in result[0]
        assert len(result[0]["words"]) == 2
        assert result[0]["words"][0]["word"] == "Hello"
        assert result[0]["words"][1]["word"] == "world"

    def test_phrase_boundaries_correctly_partition_words(self):
        """When pauses split words into phrases, each phrase gets its own words."""
        words = [
            {"word": " Hello", "start": 0.0, "end": 0.5},
            {"word": " beautiful", "start": 0.55, "end": 1.0},
            # 1.5s gap — triggers split
            {"word": " world", "start": 2.5, "end": 3.0},
            {"word": " out", "start": 3.05, "end": 3.3},
            {"word": " there", "start": 3.35, "end": 3.6},
        ]
        result = _group_words_into_phrases(words)
        assert len(result) == 2

        # First phrase: "Hello beautiful"
        assert result[0]["text"] == "Hello beautiful"
        assert len(result[0]["words"]) == 2
        assert result[0]["words"][0]["word"] == "Hello"
        assert result[0]["words"][1]["word"] == "beautiful"
        assert result[0]["words"][0]["start"] == 0.0
        assert result[0]["words"][1]["end"] == 1.0

        # Second phrase: "world out there"
        assert result[1]["text"] == "world out there"
        assert len(result[1]["words"]) == 3
        assert result[1]["words"][0]["word"] == "world"
        assert result[1]["words"][1]["word"] == "out"
        assert result[1]["words"][2]["word"] == "there"
        assert result[1]["words"][0]["start"] == 2.5
        assert result[1]["words"][2]["end"] == 3.6
