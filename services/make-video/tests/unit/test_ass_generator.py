"""
Unit tests for ASS Generator

Tests neon/classic presets, dual-layer rendering, color formats, and validation.
Sprint: S-105 to S-118
"""

import pytest
from pathlib import Path

from app.ass_generator import (
    ASSGenerator,
    ASSStyle,
    generate_subtitles_with_style
)


class TestASSStyle:
    """Test ASSStyle dataclass"""
    
    def test_style_creation(self):
        """Test style dataclass instantiation"""
        style = ASSStyle(
            name='Test',
            fontname='Arial',
            fontsize=48,
            primary_colour='&H00FFFFFF&',
            outline_colour='&H00000000&',
            back_colour='&H00000000&',
            bold=-1,
            border_style=1,
            outline=3.0,
            shadow=1.0,
            alignment=5,
            margin_v=0
        )
        
        assert style.name == 'Test'
        assert style.fontsize == 48
        assert style.alignment == 5


class TestASSGenerator:
    """Test ASS Generator main class"""
    
    def test_initialization_default(self):
        """Test generator initialization with defaults"""
        gen = ASSGenerator()
        
        assert gen.video_width == 1080
        assert gen.video_height == 1920
        assert 'neon' in gen.styles
        assert 'classic' in gen.styles
    
    def test_initialization_custom_resolution(self):
        """Test generator with custom resolution"""
        gen = ASSGenerator(video_width=1920, video_height=1080)
        
        assert gen.video_width == 1920
        assert gen.video_height == 1080
    
    def test_color_format_8_digits(self):
        """Test that colors are 8-digit format (&HAABBGGRR&)"""
        gen = ASSGenerator()
        
        # Check predefined colors
        assert gen.COLORS['white'] == '&H00FFFFFF&'
        assert gen.COLORS['cyan'] == '&H00FFFF00&'
        assert gen.COLORS['black'] == '&H00000000&'
        
        # Verify format (starts with &H, ends with &, 8 hex digits)
        for color_name, color_value in gen.COLORS.items():
            assert color_value.startswith('&H')
            assert color_value.endswith('&')
            hex_part = color_value[2:-1]  # Remove &H and &
            assert len(hex_part) == 8, f"{color_name} should have 8 hex digits"


class TestNeonPreset:
    """Test neon preset with dual-layer rendering"""
    
    def test_neon_preset_exists(self):
        """Test neon preset is created"""
        gen = ASSGenerator()
        
        assert 'neon' in gen.styles
        neon = gen.styles['neon']
        
        assert 'glow' in neon
        assert 'text' in neon
    
    def test_neon_glow_layer(self):
        """Test glow layer configuration"""
        gen = ASSGenerator()
        glow = gen.styles['neon']['glow']
        
        assert glow.name == 'NeonGlow'
        assert glow.outline == 6.0  # Thick for glow
        assert glow.alignment == 5  # Middle-center
        assert glow.bold == -1  # Bold
        assert glow.border_style == 1  # Outline + shadow
    
    def test_neon_text_layer(self):
        """Test text layer configuration"""
        gen = ASSGenerator()
        text = gen.styles['neon']['text']
        
        assert text.name == 'NeonText'
        assert text.outline == 2.0  # Thinner for sharpness
        assert text.alignment == 5  # Middle-center
    
    def test_neon_dual_layer_generation(self):
        """Test dual-layer event generation"""
        gen = ASSGenerator()
        cues = [
            {'start': 1.0, 'end': 3.0, 'text': 'Hello World'}
        ]
        
        events = gen._generate_events_dual_layer(cues)
        
        # Should have both layers
        assert 'NeonGlow' in events
        assert 'NeonText' in events
        
        # Should have 2 dialogue lines (glow + text)
        dialogue_lines = [line for line in events.split('\n') if line.startswith('Dialogue:')]
        assert len(dialogue_lines) == 2
        
        # Layer 0 is glow, Layer 1 is text
        assert 'Dialogue: 0,' in events  # Glow
        assert 'Dialogue: 1,' in events  # Text


class TestClassicPreset:
    """Test classic single-layer preset"""
    
    def test_classic_preset_exists(self):
        """Test classic preset is created"""
        gen = ASSGenerator()
        
        assert 'classic' in gen.styles
        classic = gen.styles['classic']
        
        assert 'default' in classic
    
    def test_classic_style(self):
        """Test classic style configuration"""
        gen = ASSGenerator()
        style = gen.styles['classic']['default']
        
        assert style.name == 'Classic'
        assert style.fontname == 'Arial'
        assert style.alignment == 5  # Middle-center
        assert style.outline == 3.0
    
    def test_classic_single_layer_generation(self):
        """Test single-layer event generation"""
        gen = ASSGenerator()
        cues = [
            {'start': 1.0, 'end': 3.0, 'text': 'Hello World'}
        ]
        
        events = gen._generate_events_single_layer(cues, 'Classic')
        
        # Should have Classic style
        assert 'Classic' in events
        
        # Should have 1 dialogue line
        dialogue_lines = [line for line in events.split('\n') if line.startswith('Dialogue:')]
        assert len(dialogue_lines) == 1
        
        # Should be layer 0
        assert 'Dialogue: 0,' in events


class TestTimestampFormatting:
    """Test timestamp conversion"""
    
    def test_format_timestamp_simple(self):
        """Test simple timestamp formatting"""
        gen = ASSGenerator()
        
        ts = gen._format_timestamp(65.5)
        assert ts == "0:01:05.50"
    
    def test_format_timestamp_with_hours(self):
        """Test timestamp with hours"""
        gen = ASSGenerator()
        
        ts = gen._format_timestamp(3661.25)  # 1:01:01.25
        assert ts == "1:01:01.25"
    
    def test_format_timestamp_zero(self):
        """Test zero timestamp"""
        gen = ASSGenerator()
        
        ts = gen._format_timestamp(0.0)
        assert ts == "0:00:00.00"


class TestHeaderGeneration:
    """Test ASS header generation"""
    
    def test_header_contains_resolution(self):
        """Test header includes video resolution"""
        gen = ASSGenerator(video_width=1920, video_height=1080)
        header = gen._generate_header()
        
        assert 'PlayResX: 1920' in header
        assert 'PlayResY: 1080' in header
    
    def test_header_contains_script_info(self):
        """Test header contains required script info"""
        gen = ASSGenerator()
        header = gen._generate_header()
        
        assert '[Script Info]' in header
        assert 'ScriptType: v4.00+' in header
        assert 'WrapStyle: 0' in header


class TestStylesGeneration:
    """Test styles section generation"""
    
    def test_styles_section_format(self):
        """Test styles section formatting"""
        gen = ASSGenerator()
        styles = gen._generate_styles('classic')
        
        assert '[V4+ Styles]' in styles
        assert 'Format: Name' in styles
        assert 'Style: Classic' in styles
    
    def test_neon_styles_both_layers(self):
        """Test neon preset includes both layers"""
        gen = ASSGenerator()
        styles = gen._generate_styles('neon')
        
        assert 'NeonGlow' in styles
        assert 'NeonText' in styles


class TestFileGeneration:
    """Test complete file generation"""
    
    def test_generate_ass_neon(self, tmp_path):
        """Test generating neon ASS file"""
        gen = ASSGenerator()
        cues = [
            {'start': 1.0, 'end': 3.0, 'text': 'First line'},
            {'start': 4.0, 'end': 6.0, 'text': 'Second line'}
        ]
        
        output = tmp_path / 'test.ass'
        result = gen.generate_ass(cues, str(output), preset='neon')
        
        assert result == str(output)
        assert output.exists()
        
        content = output.read_text()
        assert '[Script Info]' in content
        assert '[V4+ Styles]' in content
        assert '[Events]' in content
        assert 'First line' in content
        assert 'Second line' in content
    
    def test_generate_ass_classic(self, tmp_path):
        """Test generating classic ASS file"""
        gen = ASSGenerator()
        cues = [
            {'start': 1.0, 'end': 3.0, 'text': 'Test'}
        ]
        
        output = tmp_path / 'classic.ass'
        gen.generate_ass(cues, str(output), preset='classic')
        
        content = output.read_text()
        assert 'Classic' in content
        assert 'Test' in content
    
    def test_generate_ass_fallback_preset(self, tmp_path):
        """Test fallback to classic for unknown preset"""
        gen = ASSGenerator()
        cues = [
            {'start': 1.0, 'end': 3.0, 'text': 'Test'}
        ]
        
        output = tmp_path / 'fallback.ass'
        # Request nonexistent preset
        gen.generate_ass(cues, str(output), preset='nonexistent')
        
        # Should fall back to classic
        content = output.read_text()
        assert 'Classic' in content
    
    def test_generate_ass_empty_cues(self):
        """Test error on empty cues"""
        gen = ASSGenerator()
        
        with pytest.raises(ValueError, match="No cues provided"):
            gen.generate_ass([], 'output.ass')


class TestCueValidation:
    """Test cue validation"""
    
    def test_validate_cues_valid(self):
        """Test validation of valid cues"""
        gen = ASSGenerator()
        cues = [
            {'start': 1.0, 'end': 3.0, 'text': 'Test 1'},
            {'start': 4.0, 'end': 6.0, 'text': 'Test 2'}
        ]
        
        assert gen.validate_cues(cues) is True
    
    def test_validate_cues_empty(self):
        """Test validation of empty list"""
        gen = ASSGenerator()
        
        assert gen.validate_cues([]) is False
    
    def test_validate_cues_missing_field(self):
        """Test validation fails with missing field"""
        gen = ASSGenerator()
        cues = [
            {'start': 1.0, 'text': 'Missing end'}
        ]
        
        assert gen.validate_cues(cues) is False
    
    def test_validate_cues_invalid_type(self):
        """Test validation fails with wrong type"""
        gen = ASSGenerator()
        cues = [
            {'start': 'not_a_number', 'end': 3.0, 'text': 'Bad start'}
        ]
        
        assert gen.validate_cues(cues) is False
    
    def test_validate_cues_start_after_end(self):
        """Test validation fails when start >= end"""
        gen = ASSGenerator()
        cues = [
            {'start': 5.0, 'end': 3.0, 'text': 'Backwards'}
        ]
        
        assert gen.validate_cues(cues) is False


class TestLineBreaks:
    """Test line break handling"""
    
    def test_newline_conversion_dual_layer(self):
        """Test newline conversion in dual-layer"""
        gen = ASSGenerator()
        cues = [
            {'start': 1.0, 'end': 3.0, 'text': 'Line 1\nLine 2'}
        ]
        
        events = gen._generate_events_dual_layer(cues)
        
        # Should convert \n to \N
        assert 'Line 1\\NLine 2' in events
        assert 'Line 1\nLine 2' not in events  # Literal newline should not appear
    
    def test_newline_conversion_single_layer(self):
        """Test newline conversion in single-layer"""
        gen = ASSGenerator()
        cues = [
            {'start': 1.0, 'end': 3.0, 'text': 'Line 1\nLine 2'}
        ]
        
        events = gen._generate_events_single_layer(cues, 'Classic')
        
        assert 'Line 1\\NLine 2' in events


class TestConvenienceFunction:
    """Test convenience function"""
    
    def test_generate_subtitles_with_style(self, tmp_path):
        """Test convenience function"""
        cues = [
            {'start': 1.0, 'end': 3.0, 'text': 'Test'}
        ]
        
        output = tmp_path / 'test.ass'
        result = generate_subtitles_with_style(
            cues,
            str(output),
            style='neon',
            video_width=1080,
            video_height=1920
        )
        
        assert result == str(output)
        assert output.exists()


class TestGetAvailablePresets:
    """Test preset listing"""
    
    def test_get_available_presets(self):
        """Test getting list of available presets"""
        gen = ASSGenerator()
        presets = gen.get_available_presets()
        
        assert 'neon' in presets
        assert 'classic' in presets
        assert len(presets) >= 2
