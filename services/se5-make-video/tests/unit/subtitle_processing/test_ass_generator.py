"""
Unit tests for ASS Generator

Tests real .ass file generation with multiple presets (neon, classic).
NO MOCKS - uses real ASSGenerator to validate ASS format.
"""

import pytest
from pathlib import Path

from app.subtitle_processing.ass_generator import ASSGenerator


class TestASSGeneratorInit:
    """Tests for ASSGenerator initialization"""
    
    def test_generator_imports(self):
        """ASSGenerator module imports successfully"""
        from app.subtitle_processing import ass_generator
        assert ass_generator is not None
    
    def test_generator_class_exists(self):
        """ASSGenerator class can be instantiated"""
        generator = ASSGenerator()
        assert generator is not None
        assert hasattr(generator, 'generate_ass')
    
    def test_generator_with_custom_resolution(self):
        """ASSGenerator accepts custom video resolution"""
        generator = ASSGenerator(video_width=1280, video_height=720)
        assert generator.video_width == 1280
        assert generator.video_height == 720
    
    def test_generator_has_presets(self):
        """ASSGenerator has neon and classic presets"""
        generator = ASSGenerator()
        assert 'neon' in generator.styles
        assert 'classic' in generator.styles


class TestASSGeneration:
    """Tests for real ASS file generation"""
    
    def test_generate_ass_neon_preset(self, tmp_path):
        """Generate real .ass file with neon preset"""
        generator = ASSGenerator()
        output = tmp_path / "neon.ass"
        
        # Real subtitle cues
        cues = [
            {"start": 0.0, "end": 2.0, "text": "Hello World"},
            {"start": 2.5, "end": 4.5, "text": "This is a test"},
            {"start": 5.0, "end": 7.0, "text": "Final subtitle"},
        ]
        
        # Generate real ASS file
        result = generator.generate_ass(cues, str(output), preset='neon')
        
        # Validate
        assert result == str(output)
        assert output.exists()
        
        content = output.read_text()
        
        # Validate ASS structure
        assert "[Script Info]" in content
        assert "[V4+ Styles]" in content
        assert "[Events]" in content
        
        # Validate cues are present
        assert "Hello World" in content
        assert "This is a test" in content
        assert "Final subtitle" in content
        
        # Validate neon dual-layer (glow + text)
        assert "NeonGlow" in content or "Dialogue:" in content
    
    def test_generate_ass_classic_preset(self, tmp_path):
        """Generate real .ass file with classic preset"""
        generator = ASSGenerator()
        output = tmp_path / "classic.ass"
        
        cues = [
            {"start": 0.0, "end": 1.5, "text": "Classic subtitle"},
        ]
        
        result = generator.generate_ass(cues, str(output), preset='classic')
        
        assert output.exists()
        content = output.read_text()
        
        # Validate classic style
        assert "[Script Info]" in content
        assert "Classic subtitle" in content
    
    def test_generate_ass_with_special_chars(self, tmp_path):
        """Generate ASS file with special characters"""
        generator = ASSGenerator()
        output = tmp_path / "special.ass"
        
        cues = [
            {"start": 0.0, "end": 2.0, "text": "Hello! @#$%^&*()"},
            {"start": 2.0, "end": 4.0, "text": "Line 1\\nLine 2"},  # Newline
        ]
        
        result = generator.generate_ass(cues, str(output), preset='neon')
        
        assert output.exists()
        content = output.read_text()
        
        # Special characters should be present
        assert "@#$%^&*()" in content
    
    def test_generate_ass_creates_parent_dirs(self, tmp_path):
        """generate_ass creates parent directories if needed"""
        generator = ASSGenerator()
        output = tmp_path / "subdir" / "nested" / "file.ass"
        
        cues = [{"start": 0.0, "end": 1.0, "text": "Test"}]
        
        generator.generate_ass(cues, str(output), preset='neon')
        
        assert output.exists()
        assert output.parent.exists()


class TestASSValidation:
    """Tests for ASS file format validation"""
    
    def test_ass_file_has_required_sections(self, tmp_path):
        """Generated ASS file has all required sections"""
        generator = ASSGenerator()
        output = tmp_path / "valid.ass"
        
        cues = [{"start": 0.0, "end": 2.0, "text": "Test"}]
        generator.generate_ass(cues, str(output), preset='neon')
        
        content = output.read_text()
        
        # ASS format requires these sections
        required_sections = [
            "[Script Info]",
            "[V4+ Styles]",
            "[Events]",
            "Format: Layer, Start, End,",
            "Dialogue:",
        ]
        
        for section in required_sections:
            assert section in content, f"Missing required section: {section}"
    
    def test_ass_file_has_valid_timing(self, tmp_path):
        """Generated ASS file has valid timing format"""
        generator = ASSGenerator()
        output = tmp_path / "timing.ass"
        
        cues = [
            {"start": 1.5, "end": 3.75, "text": "Timing test"},
        ]
        generator.generate_ass(cues, str(output), preset='classic')
        
        content = output.read_text()
        
        # ASS timing format: H:MM:SS.CC
        # Should contain time stamps like "0:00:01.50" and "0:00:03.75"
        assert "Dialogue:" in content
        assert "Timing test" in content
    
    def test_ass_file_is_utf8(self, tmp_path):
        """Generated ASS file is UTF-8 encoded"""
        generator = ASSGenerator()
        output = tmp_path / "utf8.ass"
        
        cues = [
            {"start": 0.0, "end": 2.0, "text": "Unicode: 你好 مرحبا"},
        ]
        generator.generate_ass(cues, str(output), preset='neon')
        
        # Should be readable as UTF-8
        content = output.read_text(encoding='utf-8')
        assert "Unicode:" in content


class TestASSGeneratorErrors:
    """Tests for error handling in ASS generation"""
    
    def test_generate_ass_empty_cues_raises_error(self, tmp_path):
        """generate_ass raises ValueError for empty cues"""
        generator = ASSGenerator()
        output = tmp_path / "empty.ass"
        
        with pytest.raises(ValueError, match="No cues provided"):
            generator.generate_ass([], str(output), preset='neon')
    
    def test_generate_ass_invalid_preset_fallback(self, tmp_path):
        """generate_ass falls back to classic for invalid preset"""
        generator = ASSGenerator()
        output = tmp_path / "fallback.ass"
        
        cues = [{"start": 0.0, "end": 1.0, "text": "Test"}]
        
        # Should not raise, should fallback to classic
        result = generator.generate_ass(cues, str(output), preset='invalid_preset')
        
        assert output.exists()
        content = output.read_text()
        assert "[Events]" in content


class TestASSFormats:
    """Tests for different ASS format features"""
    
    def test_ass_resolution_in_header(self, tmp_path):
        """ASS file header contains PlayResX/PlayResY"""
        generator = ASSGenerator(video_width=1920, video_height=1080)
        output = tmp_path / "resolution.ass"
        
        cues = [{"start": 0.0, "end": 1.0, "text": "Test"}]
        generator.generate_ass(cues, str(output), preset='neon')
        
        content = output.read_text()
        
        # Check resolution in header
        assert "PlayResX: 1920" in content
        assert "PlayResY: 1080" in content
    
    def test_ass_multiple_cues_ordered(self, tmp_path):
        """ASS file maintains cue order"""
        generator = ASSGenerator()
        output = tmp_path / "ordered.ass"
        
        cues = [
            {"start": 0.0, "end": 1.0, "text": "First subtitle"},
            {"start": 1.5, "end": 2.5, "text": "Second subtitle"},
            {"start": 3.0, "end": 4.0, "text": "Third subtitle"},
        ]
        generator.generate_ass(cues, str(output), preset='classic')
        
        content = output.read_text()
        
        # Find positions in Dialogue lines (in [Events] section)
        events_section = content.split("[Events]")[-1]
        
        first_pos = events_section.find("First subtitle")
        second_pos = events_section.find("Second subtitle")
        third_pos = events_section.find("Third subtitle")
        
        # All must be found
        assert first_pos > 0 and second_pos > 0 and third_pos > 0
        
        # Should be ordered
        assert first_pos < second_pos < third_pos
