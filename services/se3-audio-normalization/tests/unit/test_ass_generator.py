"""
Unit tests for ASS Generator

Tests SRT parsing, ASS conversion, style application, and positioning.
Sprint: S-105 to S-118
"""

import pytest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch, mock_open

from app.ass_generator import (
    ASSGenerator,
    ASSStyle,
    SRTSubtitle
)


class TestASSStyle:
    """Test ASS style dataclass"""
    
    def test_default_style(self):
        """Test default style values"""
        style = ASSStyle()
        
        assert style.name == "Default"
        assert style.font_name == "Arial"
        assert style.font_size == 20
        assert style.alignment == 2  # Bottom-center
        assert style.margin_v == 0  # Must be 0
        assert style.outline == 2.0
        assert style.shadow == 1.0
    
    def test_custom_style(self):
        """Test custom style values"""
        style = ASSStyle(
            name="Custom",
            font_name="Verdana",
            font_size=24,
            alignment=2
        )
        
        assert style.name == "Custom"
        assert style.font_name == "Verdana"
        assert style.font_size == 24
        assert style.alignment == 2
    
    def test_style_to_ass_line(self):
        """Test conversion of style to ASS format"""
        style = ASSStyle()
        ass_line = style.to_ass_line()
        
        assert ass_line.startswith("Style: Default,Arial,20")
        assert "&H00FFFFFF" in ass_line  # White color
        assert ",2," in ass_line  # Alignment=2
        assert ",0,1" in ass_line  # MarginV=0


class TestASSGenerator:
    """Test ASS Generator main class"""
    
    def test_initialization_default(self):
        """Test generator initialization with defaults"""
        generator = ASSGenerator()
        
        assert generator.style.alignment == 2
        assert generator.style.margin_v == 0
        assert generator.video_width == 1920
        assert generator.video_height == 1080
    
    def test_initialization_custom_style(self):
        """Test generator initialization with custom style"""
        custom_style = ASSStyle(name="MyStyle", font_size=24)
        generator = ASSGenerator(style=custom_style)
        
        assert generator.style.name == "MyStyle"
        assert generator.style.font_size == 24
        assert generator.style.margin_v == 0  # Still enforced
    
    def test_margin_v_auto_correction(self):
        """Test that MarginV is automatically corrected to 0"""
        style = ASSStyle(margin_v=50)  # Invalid value
        generator = ASSGenerator(style=style)
        
        # Should be auto-corrected to 0
        assert generator.style.margin_v == 0


class TestSRTParsing:
    """Test SRT parsing functionality"""
    
    def test_parse_simple_srt(self):
        """Test parsing of simple SRT content"""
        srt_content = """1
00:00:20,000 --> 00:00:24,400
This is the first subtitle

2
00:00:24,600 --> 00:00:27,800
This is the second subtitle
"""
        
        generator = ASSGenerator()
        subtitles = generator.parse_srt(srt_content)
        
        assert len(subtitles) == 2
        
        # First subtitle
        assert subtitles[0].index == 1
        assert subtitles[0].start_time == timedelta(seconds=20)
        assert subtitles[0].end_time == timedelta(seconds=24, milliseconds=400)
        assert subtitles[0].text == "This is the first subtitle"
        
        # Second subtitle
        assert subtitles[1].index == 2
        assert subtitles[1].start_time == timedelta(seconds=24, milliseconds=600)
        assert subtitles[1].end_time == timedelta(seconds=27, milliseconds=800)
        assert subtitles[1].text == "This is the second subtitle"
    
    def test_parse_multiline_text(self):
        """Test parsing subtitle with multiple text lines"""
        srt_content = """1
00:00:01,000 --> 00:00:03,000
First line
Second line
Third line
"""
        
        generator = ASSGenerator()
        subtitles = generator.parse_srt(srt_content)
        
        assert len(subtitles) == 1
        assert subtitles[0].text == "First line\nSecond line\nThird line"
    
    def test_parse_with_hours(self):
        """Test parsing timestamp with hours"""
        srt_content = """1
01:30:45,123 --> 01:30:48,456
Long video subtitle
"""
        
        generator = ASSGenerator()
        subtitles = generator.parse_srt(srt_content)
        
        assert len(subtitles) == 1
        assert subtitles[0].start_time == timedelta(
            hours=1, minutes=30, seconds=45, milliseconds=123
        )
        assert subtitles[0].end_time == timedelta(
            hours=1, minutes=30, seconds=48, milliseconds=456
        )
    
    def test_parse_empty_content(self):
        """Test parsing empty SRT content"""
        generator = ASSGenerator()
        subtitles = generator.parse_srt("")
        
        assert len(subtitles) == 0
    
    def test_parse_invalid_block(self):
        """Test parsing with invalid blocks (should skip them)"""
        srt_content = """1
00:00:01,000 --> 00:00:02,000
Valid subtitle

invalid block

2
00:00:03,000 --> 00:00:04,000
Another valid subtitle
"""
        
        generator = ASSGenerator()
        subtitles = generator.parse_srt(srt_content)
        
        # Should skip invalid block
        assert len(subtitles) == 2
        assert subtitles[0].index == 1
        assert subtitles[1].index == 2
    
    def test_parse_invalid_timestamp(self):
        """Test parsing with invalid timestamp format"""
        srt_content = """1
invalid timestamp
Text here

2
00:00:01,000 --> 00:00:02,000
Valid subtitle
"""
        
        generator = ASSGenerator()
        subtitles = generator.parse_srt(srt_content)
        
        # Should skip invalid block, keep valid one
        assert len(subtitles) == 1
        assert subtitles[0].index == 2


class TestASSFormatting:
    """Test ASS format generation"""
    
    def test_format_ass_timestamp(self):
        """Test conversion of timedelta to ASS timestamp"""
        generator = ASSGenerator()
        
        # Simple case
        td = timedelta(seconds=65, milliseconds=500)
        timestamp = generator._format_ass_timestamp(td)
        assert timestamp == "0:01:05.50"
        
        # With hours
        td = timedelta(hours=1, minutes=30, seconds=45, milliseconds=123)
        timestamp = generator._format_ass_timestamp(td)
        assert timestamp == "1:30:45.12"
        
        # Zero
        td = timedelta(0)
        timestamp = generator._format_ass_timestamp(td)
        assert timestamp == "0:00:00.00"
    
    def test_generate_ass_header(self):
        """Test ASS header generation"""
        generator = ASSGenerator(video_width=1280, video_height=720)
        header = generator.generate_ass_header()
        
        assert "[Script Info]" in header
        assert "PlayResX: 1280" in header
        assert "PlayResY: 720" in header
        assert "[V4+ Styles]" in header
        assert "Style: Default" in header
        assert "[Events]" in header
        assert "Format: Layer, Start, End" in header
    
    def test_generate_ass_event(self):
        """Test ASS event line generation"""
        generator = ASSGenerator()
        
        subtitle = SRTSubtitle(
            index=1,
            start_time=timedelta(seconds=10),
            end_time=timedelta(seconds=12),
            text="Test subtitle"
        )
        
        event = generator.generate_ass_event(subtitle)
        
        assert event.startswith("Dialogue: 0,")
        assert "0:00:10.00,0:00:12.00" in event
        assert "Default" in event
        assert "Test subtitle" in event
    
    def test_generate_ass_event_multiline(self):
        """Test ASS event with multiline text"""
        generator = ASSGenerator()
        
        subtitle = SRTSubtitle(
            index=1,
            start_time=timedelta(seconds=5),
            end_time=timedelta(seconds=8),
            text="Line 1\nLine 2"
        )
        
        event = generator.generate_ass_event(subtitle)
        
        # SRT newlines should be converted to ASS format
        assert "Line 1\\NLine 2" in event
        assert "\n" not in event.split(",,")[-1]  # No literal newlines in text


class TestConversion:
    """Test full SRT to ASS conversion"""
    
    def test_convert_srt_to_ass(self):
        """Test complete SRT to ASS conversion"""
        srt_content = """1
00:00:01,000 --> 00:00:03,000
First subtitle

2
00:00:04,000 --> 00:00:06,000
Second subtitle
"""
        
        generator = ASSGenerator()
        ass_content = generator.convert_srt_to_ass(srt_content)
        
        # Check structure
        assert "[Script Info]" in ass_content
        assert "[V4+ Styles]" in ass_content
        assert "[Events]" in ass_content
        
        # Check events
        assert "Dialogue: 0,0:00:01.00,0:00:03.00" in ass_content
        assert "First subtitle" in ass_content
        assert "Dialogue: 0,0:00:04.00,0:00:06.00" in ass_content
        assert "Second subtitle" in ass_content
    
    def test_convert_empty_srt_raises_error(self):
        """Test that empty SRT raises ValueError"""
        generator = ASSGenerator()
        
        with pytest.raises(ValueError, match="No valid subtitles"):
            generator.convert_srt_to_ass("")
    
    def test_convert_with_output_path(self, tmp_path):
        """Test conversion with file output"""
        srt_content = """1
00:00:01,000 --> 00:00:02,000
Test
"""
        
        output_path = tmp_path / "output.ass"
        generator = ASSGenerator()
        
        ass_content = generator.convert_srt_to_ass(srt_content, output_path)
        
        # File should be created
        assert output_path.exists()
        
        # Content should match
        file_content = output_path.read_text(encoding='utf-8')
        assert file_content == ass_content
        assert "Test" in file_content
    
    def test_convert_srt_file_to_ass_file(self, tmp_path):
        """Test file-to-file conversion"""
        srt_content = """1
00:00:01,000 --> 00:00:02,000
From file
"""
        
        # Create input file
        srt_path = tmp_path / "input.srt"
        srt_path.write_text(srt_content, encoding='utf-8')
        
        generator = ASSGenerator()
        ass_path = generator.convert_srt_file_to_ass_file(srt_path)
        
        # Should auto-generate output path
        assert ass_path == tmp_path / "input.ass"
        assert ass_path.exists()
        
        # Check content
        ass_content = ass_path.read_text(encoding='utf-8')
        assert "From file" in ass_content
    
    def test_convert_file_not_found(self, tmp_path):
        """Test conversion with non-existent input file"""
        generator = ASSGenerator()
        
        with pytest.raises(FileNotFoundError):
            generator.convert_srt_file_to_ass_file(tmp_path / "nonexistent.srt")
    
    def test_convert_with_custom_output_path(self, tmp_path):
        """Test conversion with custom output path"""
        srt_content = """1
00:00:01,000 --> 00:00:02,000
Custom path
"""
        
        srt_path = tmp_path / "input.srt"
        srt_path.write_text(srt_content, encoding='utf-8')
        
        custom_ass_path = tmp_path / "custom" / "output.ass"
        
        generator = ASSGenerator()
        result_path = generator.convert_srt_file_to_ass_file(srt_path, custom_ass_path)
        
        assert result_path == custom_ass_path
        assert custom_ass_path.exists()
        assert "Custom path" in custom_ass_path.read_text(encoding='utf-8')


class TestAlignment:
    """Test bottom-center alignment (Alignment=2)"""
    
    def test_alignment_in_style(self):
        """Test that alignment is set to 2 (bottom-center)"""
        generator = ASSGenerator()
        
        assert generator.style.alignment == 2
        
        ass_line = generator.style.to_ass_line()
        # Alignment should be in the correct position in the style line
        assert ",2," in ass_line
    
    def test_alignment_in_generated_header(self):
        """Test that alignment appears correctly in header"""
        generator = ASSGenerator()
        header = generator.generate_ass_header()
        
        # Find the style line
        style_lines = [line for line in header.split('\n') if line.startswith('Style:')]
        assert len(style_lines) == 1
        
        # Parse alignment (should be 18th comma-separated value)
        style_parts = style_lines[0].split(',')
        alignment_index = 18  # 0-indexed position of Alignment
        assert style_parts[alignment_index] == "2"
    
    def test_margin_v_is_zero(self):
        """Test that MarginV is 0 as required"""
        generator = ASSGenerator()
        
        assert generator.style.margin_v == 0
        
        header = generator.generate_ass_header()
        style_lines = [line for line in header.split('\n') if line.startswith('Style:')]
        
        # MarginV should be 0 (21st comma-separated value, not 19th)
        # Format: ...,Alignment,MarginL,MarginR,MarginV,Encoding
        style_parts = style_lines[0].split(',')
        margin_v_index = 21  # Fixed: was 19, should be 21
        assert style_parts[margin_v_index] == "0"
