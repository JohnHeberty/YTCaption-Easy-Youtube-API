"""
ASS Subtitle Generator with Neon/Glow Presets

Generates Advanced SubStation Alpha (.ass) subtitle files with custom styling
optimized for YouTube Shorts. Supports dual-layer rendering for neon effects.

Sprint: S-105 to S-118
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ASSStyle:
    """ASS subtitle style configuration"""
    name: str
    fontname: str
    fontsize: int
    primary_colour: str  # Format: &HAABBGGRR&
    outline_colour: str
    back_colour: str
    bold: int
    border_style: int
    outline: float
    shadow: float
    alignment: int
    margin_v: int


class ASSGenerator:
    """
    Generates ASS subtitles with custom presets
    
    Presets:
    - neon: Dual-layer (glow + text) for vibrant shorts
    - classic: Single-layer traditional subtitles
    
    Features:
    - 8-digit color format (&HAABBGGRR&) for consistency
    - Alignment=5 (middle-center) for shorts
    - Font fallback: Montserrat → Arial → Sans
    - Dual-layer rendering for neon effects
    """
    
    # Color format: &HAABBGGRR& (alpha, blue, green, red)
    COLORS = {
        'white': '&H00FFFFFF&',
        'cyan': '&H00FFFF00&',  # Neon cyan for outline
        'black': '&H00000000&',
        'yellow': '&H0000FFFF&',
        'magenta': '&H00FF00FF&',
    }
    
    def __init__(self, video_width: int = 1080, video_height: int = 1920):
        """
        Initialize ASS generator
        
        Args:
            video_width: Video resolution width (default: 1080 for 9:16)
            video_height: Video resolution height (default: 1920 for 9:16)
        """
        self.video_width = video_width
        self.video_height = video_height
        
        # Define presets
        self.styles = {
            'neon': self._create_neon_preset(),
            'classic': self._create_classic_preset(),
        }
        
        logger.info(
            f"ASSGenerator initialized (resolution={video_width}x{video_height})"
        )
    
    def _create_neon_preset(self) -> Dict[str, ASSStyle]:
        """
        Create neon preset with dual layers (glow + text)
        
        Layers:
        - Layer 0 (NeonGlow): Large outline with blur for glow effect
        - Layer 1 (NeonText): Sharp text on top
        """
        return {
            'glow': ASSStyle(
                name='NeonGlow',
                fontname='Montserrat',
                fontsize=48,
                primary_colour=self.COLORS['white'],
                outline_colour=self.COLORS['cyan'],
                back_colour=self.COLORS['black'],
                bold=-1,  # -1 = bold
                border_style=1,  # Outline + drop shadow
                outline=6.0,  # Thick outline for glow
                shadow=1.0,
                alignment=5,  # Middle-center
                margin_v=0,
            ),
            'text': ASSStyle(
                name='NeonText',
                fontname='Montserrat',
                fontsize=48,
                primary_colour=self.COLORS['white'],
                outline_colour=self.COLORS['cyan'],
                back_colour=self.COLORS['black'],
                bold=-1,
                border_style=1,
                outline=2.0,  # Thinner outline for sharpness
                shadow=1.0,
                alignment=5,
                margin_v=0,
            ),
        }
    
    def _create_classic_preset(self) -> Dict[str, ASSStyle]:
        """Create classic single-layer preset"""
        return {
            'default': ASSStyle(
                name='Classic',
                fontname='Arial',
                fontsize=44,
                primary_colour=self.COLORS['white'],
                outline_colour=self.COLORS['black'],
                back_colour=self.COLORS['black'],
                bold=-1,
                border_style=1,
                outline=3.0,
                shadow=1.5,
                alignment=5,  # Middle-center
                margin_v=0,
            )
        }
    
    def generate_ass(
        self,
        cues: List[Dict],
        output_path: str,
        preset: str = 'neon'
    ) -> str:
        """
        Generate ASS subtitle file
        
        Args:
            cues: List of subtitle cues with 'start', 'end', 'text'
            output_path: Path to output .ass file
            preset: Style preset ('neon' or 'classic')
        
        Returns:
            Path to generated file
            
        Raises:
            ValueError: If preset not found or cues invalid
        """
        if preset not in self.styles:
            logger.warning(
                f"Preset '{preset}' not found, falling back to 'classic'"
            )
            preset = 'classic'
        
        if not cues:
            raise ValueError("No cues provided")
        
        logger.info(
            f"Generating ASS file (preset={preset}, cues={len(cues)})"
        )
        
        # Build ASS content
        content = []
        content.append(self._generate_header())
        content.append(self._generate_styles(preset))
        
        if preset == 'neon':
            content.append(self._generate_events_dual_layer(cues))
        else:
            content.append(self._generate_events_single_layer(cues, 'Classic'))
        
        # Write file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(''.join(content), encoding='utf-8')
        
        logger.info(
            f"ASS file generated: {output_path} ({len(content)} sections)"
        )
        
        return str(output_path)
    
    def _generate_header(self) -> str:
        """Generate ASS script info header"""
        return f"""[Script Info]
Title: YTCaption Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {self.video_width}
PlayResY: {self.video_height}

"""
    
    def _generate_styles(self, preset: str) -> str:
        """
        Generate V4+ Styles section
        
        Args:
            preset: Style preset name
        
        Returns:
            Formatted styles section
        """
        section = "[V4+ Styles]\n"
        section += (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        )
        
        styles = self.styles[preset]
        for style_key, style in styles.items():
            section += self._format_style(style)
        
        return section + "\n"
    
    def _format_style(self, style: ASSStyle) -> str:
        """Format a single style line"""
        return (
            f"Style: {style.name},{style.fontname},{style.fontsize},"
            f"{style.primary_colour},&H000000FF&,{style.outline_colour},{style.back_colour},"
            f"{style.bold},0,0,0,100,100,0,0,{style.border_style},{style.outline},{style.shadow},"
            f"{style.alignment},10,10,{style.margin_v},1\n"
        )
    
    def _generate_events_dual_layer(self, cues: List[Dict]) -> str:
        """
        Generate events with dual-layer rendering (glow + text)
        
        Layer 0: Glow effect (large outline)
        Layer 1: Sharp text on top
        """
        section = "[Events]\n"
        section += (
            "Format: Layer, Start, End, Style, Name, "
            "MarginL, MarginR, MarginV, Effect, Text\n"
        )
        
        for cue in cues:
            start = self._format_timestamp(cue['start'])
            end = self._format_timestamp(cue['end'])
            text = cue['text'].replace('\n', '\\N')  # ASS line break
            
            # Layer 0: Glow (bottom)
            section += f"Dialogue: 0,{start},{end},NeonGlow,,0,0,0,,{text}\n"
            
            # Layer 1: Text (top)
            section += f"Dialogue: 1,{start},{end},NeonText,,0,0,0,,{text}\n"
        
        return section
    
    def _generate_events_single_layer(
        self,
        cues: List[Dict],
        style_name: str
    ) -> str:
        """Generate events with single-layer rendering"""
        section = "[Events]\n"
        section += (
            "Format: Layer, Start, End, Style, Name, "
            "MarginL, MarginR, MarginV, Effect, Text\n"
        )
        
        for cue in cues:
            start = self._format_timestamp(cue['start'])
            end = self._format_timestamp(cue['end'])
            text = cue['text'].replace('\n', '\\N')
            
            section += f"Dialogue: 0,{start},{end},{style_name},,0,0,0,,{text}\n"
        
        return section
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        Convert seconds to ASS timestamp format (H:MM:SS.CC)
        
        Args:
            seconds: Time in seconds
        
        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
    def get_available_presets(self) -> List[str]:
        """Get list of available style presets"""
        return list(self.styles.keys())
    
    def validate_cues(self, cues: List[Dict]) -> bool:
        """
        Validate cue structure
        
        Args:
            cues: List of cue dictionaries
        
        Returns:
            True if valid, False otherwise
        """
        if not cues:
            return False
        
        for i, cue in enumerate(cues):
            # Check required fields
            if not all(k in cue for k in ['start', 'end', 'text']):
                logger.error(f"Cue {i} missing required fields")
                return False
            
            # Check types
            if not isinstance(cue['start'], (int, float)):
                logger.error(f"Cue {i} start must be numeric")
                return False
            
            if not isinstance(cue['end'], (int, float)):
                logger.error(f"Cue {i} end must be numeric")
                return False
            
            # Check logical order
            if cue['start'] >= cue['end']:
                logger.error(f"Cue {i} start >= end ({cue['start']} >= {cue['end']})")
                return False
        
        return True


def generate_subtitles_with_style(
    cues: List[Dict],
    output_path: str,
    style: str = 'neon',
    video_width: int = 1080,
    video_height: int = 1920
) -> str:
    """
    Convenience function to generate subtitles with style
    
    Args:
        cues: List of subtitle cues
        output_path: Output file path
        style: Style preset ('neon' or 'classic')
        video_width: Video width
        video_height: Video height
    
    Returns:
        Path to generated file
    """
    generator = ASSGenerator(video_width, video_height)
    return generator.generate_ass(cues, output_path, preset=style)
