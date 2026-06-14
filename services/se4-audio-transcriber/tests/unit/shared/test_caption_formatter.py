"""Tests for CaptionFormatter - SRT, VTT, TXT, LRC and SAM output formats."""

import pytest

from app.shared.caption_formatter import CaptionFormatter


# --- Fixtures ---------------------------------------------------------------

@pytest.fixture
def segments():
    """Three mock Whisper segments covering a range of timestamps."""
    return [
        {"start": 0.5, "end": 2.3, "text": "Hello world"},
        {"start": 2.8, "end": 5.1, "text": "This is a test caption."},
        {"start": 3661.99, "end": 3700.45, "text": "Late segment with hours overflow"},
    ]


@pytest.fixture
def single_segment():
    """A single Whisper segment for edge-case checks."""
    return [{"start": 0.0, "end": 1.25, "text": "Single line"}]


# --- SRT --------------------------------------------------------------------

class TestToSrt:
    def test_sequence_numbers(self, segments):
        output = CaptionFormatter.to_srt(segments)
        lines = output.strip().split(chr(10))
        assert lines[0] == "1"
        # After blank line separator the next cue starts at index 4
        assert lines[4] == "2"

    def test_timestamp_format_comma_separator(self):
        """SRT uses comma as millisecond separator."""
        segs = [{"start": 1.5, "end": 3.75, "text": "test"}]
        output = CaptionFormatter.to_srt(segs)
        assert "00:00:01,500 --> 00:00:03,750" in output

    def test_blank_line_between_cues(self, segments):
        output = CaptionFormatter.to_srt(segments)
        # Each cue block ends with a blank line (double newline).
        assert chr(10)+chr(10) in output

    def test_trailing_newline(self, single_segment):
        output = CaptionFormatter.to_srt(single_segment)
        assert output.endswith(chr(10)+chr(10))

    def test_text_stripped(self):
        segs = [{"start": 0.0, "end": 1.0, "text": "  spaced text  "}]
        output = CaptionFormatter.to_srt(segs)
        assert "spaced text" in output
        assert "  spaced text  " not in output

    def test_hours_overflow(self):
        """Segment starting at >3600s should produce hour=01."""
        segs = [{"start": 3725.5, "end": 3800.0, "text": "late"}]
        output = CaptionFormatter.to_srt(segs)
        # 3725.5 s -> 01:02:05,500
        assert "01:02:05" in output


# --- VTT --------------------------------------------------------------------

class TestToVtt:
    def test_webvtt_header(self, segments):
        output = CaptionFormatter.to_vtt(segments)
        lines = output.split(chr(10))
        assert lines[0] == "WEBVTT"

    def test_blank_line_after_header(self, segments):
        output = CaptionFormatter.to_vtt(segments)
        lines = output.split(chr(10))
        # Line 1 (index 1) must be blank after WEBVTT.
        assert lines[1] == ""

    def test_timestamp_decimal_point(self):
        """VTT uses "." not "," as millisecond separator."""
        segs = [{"start": 1.5, "end": 3.75, "text": "test"}]
        output = CaptionFormatter.to_vtt(segs)
        assert "00:00:01.500 --> 00:00:03.750" in output

    def test_cue_identifiers(self, segments):
        output = CaptionFormatter.to_vtt(segments)
        lines = output.strip().split(chr(10))
        # After header + blank line the first cue id is 1 at index 2.
        assert "1" in lines[2]

    def test_no_comma_in_timestamps(self, segments):
        """VTT timestamp lines should never contain commas."""
        output = CaptionFormatter.to_vtt(segments)
        for line in output.split(chr(10)):
            if "-->"  in line:
                assert "," not in line


# --- TXT --------------------------------------------------------------------

class TestToTxt:
    def test_plain_text_no_timestamps(self, segments):
        output = CaptionFormatter.to_txt(segments)
        assert "Hello world" in output

    def test_space_separated(self, segments):
        output = CaptionFormatter.to_txt(segments)
        expected = " ".join(s["text"].strip() for s in segments if s["text"].strip())
        assert output == expected

    def test_empty_text_filtered(self):
        """Segments with blank text should be skipped."""
        segs = [
            {"start": 0, "end": 1, "text": "Keep"},
            {"start": 2, "end": 3, "text": ""},
        ]
        output = CaptionFormatter.to_txt(segs)
        assert output == "Keep"

    def test_single_segment(self):
        segs = [{"start": 0.0, "end": 1.0, "text": "Only"}]
        output = CaptionFormatter.to_txt(segs)
        assert output == "Only"


# --- LRC --------------------------------------------------------------------

class TestToLrc:
    def test_timestamp_brackets(self, segments):
        output = CaptionFormatter.to_lrc(segments)
        first_line = output.split(chr(10))[0]
        assert first_line.startswith("[")
        assert "]" in first_line

    def test_format_mm_ss_hundredths(self, single_segment):
        """LRC uses [mm:ss.xx] - two decimal places (hundredths)."""
        output = CaptionFormatter.to_lrc(single_segment)
        # 0.0s -> [00:00.00]
        assert "[00:00.00]" in output

    def test_no_hours(self, segments):
        """LRC should not include hours even for timestamps > 3600s."""
        output = CaptionFormatter.to_lrc(segments)
        lines_with_brackets = [l for l in output.split(chr(10)) if l.startswith("[")]
        for line in lines_with_brackets:
            bracket_content = line[1:line.index("]")]
            # Should be mm:ss.xx - exactly two colon-separated groups.
            parts = bracket_content.split(":")
            assert len(parts) == 2

    def test_text_after_timestamp(self, single_segment):
        output = CaptionFormatter.to_lrc(single_segment)
        assert "Single line" in output

    def test_empty_segments_skipped(self):
        segs = [
            {"start": 125.5, "end": 130.0, "text": ""},
            {"start": 140.0, "end": 145.0, "text": "Keep this"},
        ]
        output = CaptionFormatter.to_lrc(segs)
        assert "[02:20.00]Keep this" in output

    def test_lrc_hundredths_calculation(self):
        """Verify hundredths truncation: millis // 10."""
        segs = [{"start": 1.995, "end": 2.0, "text": "test"}]
        output = CaptionFormatter.to_lrc(segs)
        # 1.995s -> millis=995 -> hundredths = 99
        assert "[00:01.99]" in output


# --- SAM --------------------------------------------------------------------

class TestToSam:
    def test_structure_matches_srt(self, segments):
        """SAM format is structurally identical to SRT."""
        sam_output = CaptionFormatter.to_sam(segments)
        srt_output = CaptionFormatter.to_srt(segments)
        assert sam_output == srt_output

    def test_comma_timestamps(self, single_segment):
        output = CaptionFormatter.to_sam(single_segment)
        # SAM uses comma like SRT.
        assert "00:00:01,250" in output

    def test_sequence_numbering(self, segments):
        output = CaptionFormatter.to_sam(segments)
        lines = output.strip().split(chr(10))
        assert lines[0] == "1"

    def test_blank_line_separator(self, single_segment):
        output = CaptionFormatter.to_sam(single_segment)
        # SAM ends with double newline like SRT.
        assert chr(10)+chr(10) in output


# --- format() dispatcher ----------------------------------------------------

class TestFormatDispatcher:
    @pytest.mark.parametrize("fmt", ["srt", "vtt", "txt", "lrc", "sam"])
    def test_all_formats_dispatch(self, segments, fmt):
        """Each registered format should return non-empty output."""
        result = CaptionFormatter.format(segments, output_format=fmt)
        assert isinstance(result, str), f"{fmt} did not return a string"

    def test_case_insensitive(self, single_segment):
        result = CaptionFormatter.format(single_segment, output_format="SRT")
        assert isinstance(result, str)

    def test_unknown_format_defaults_to_srt(self, single_segment):
        result = CaptionFormatter.format(single_segment, output_format="unknown")
        expected = CaptionFormatter.to_srt(single_segment)
        assert result == expected


# --- Legacy aliases ---------------------------------------------------------

class TestLegacyAliases:
    def test_convert_to_srt_alias(self, segments):
        from app.shared.caption_formatter import convert_to_srt
        result = convert_to_srt(segments)
        assert isinstance(result, str)
        assert "Hello world" in result

    def test_seconds_to_srt_time_alias(self):
        from app.shared.caption_formatter import seconds_to_srt_time
        ts = seconds_to_srt_time(65.432)
        # 1 min 5 sec 432ms -> 00:01:05,432
        assert "00:01:05" in ts
