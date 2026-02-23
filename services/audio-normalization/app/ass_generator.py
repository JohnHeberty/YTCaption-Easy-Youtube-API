"""
ASS Subtitle Generator

Converts SRT subtitles to ASS format with proper positioning and styling.
Implements bottom-center alignment (Alignment=2) and customizable styles.

Sprint: S-105 to S-118
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from datetime import timedelta

from common.log_utils.structured import get_logger

logger = get_logger(__name__)


@dataclass
class SRTSubtitle:
    """Represents a single SRT subtitle entry"""
    index: int
    start_time: timedelta
    end_time: timedelta
    text: str


@dataclass
class ASSStyle:
    """ASS subtitle style configuration"""
    name: str = "Default"
    font_name: str = "Arial"
    font_size: int = 20
    primary_color: str = "&H00FFFFFF"  # White
    secondary_color: str = "&H000000FF"  # Red
    outline_color: str = "&H00000000"  # Black
    back_color: str = "&H00000000"  # Black
    bold: int = -1  # -1 = true, 0 = false
    italic: int = 0
    underline: int = 0
    strike_out: int = 0
    scale_x: float = 100.0
    scale_y: float = 100.0
    spacing: float = 0.0
    angle: float = 0.0
    border_style: int = 1  # 1 = Outline + drop shadow
    outline: float = 2.0
    shadow: float = 1.0
    alignment: int = 2  # Bottom-center
    margin_l: int = 10
    margin_r: int = 10
    margin_v: int = 0  # Explicitly set to 0 as per requirements
    encoding: int = 1

    def to_ass_line(self) -> str:
        """Convert style to ASS format line"""
        return (
            f"Style: {self.name},{self.font_name},{self.font_size},"
            f"{self.primary_color},{self.secondary_color},{self.outline_color},{self.back_color},"
            f"{self.bold},{self.italic},{self.underline},{self.strike_out},"
            f"{self.scale_x},{self.scale_y},{self.spacing},{self.angle},"
            f"{self.border_style},{self.outline},{self.shadow},{self.alignment},"
            f"{self.margin_l},{self.margin_r},{self.margin_v},{self.encoding}"
        )


class ASSGenerator:
    """
    Generates ASS subtitle files from SRT input
    
    Features:
    - Parses SRT format
    - Converts to ASS with proper positioning (Alignment=2)
    - Applies customizable styles
    - Ensures MarginV=0 for bottom positioning
    """
    
    # SRT timestamp regex: 00:00:20,000 --> 00:00:24,400
    SRT_TIMESTAMP_PATTERN = re.compile(
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*'
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})'
    )
    
    def __init__(
        self,
        style: Optional[ASSStyle] = None,
        video_width: int = 1920,
        video_height: int = 1080
    ):
        """
        Initialize ASS generator
        
        Args:
            style: Custom ASS style (uses default if None)
            video_width: Video resolution width
            video_height: Video resolution height
        """
        self.style = style or ASSStyle()
        self.video_width = video_width
        self.video_height = video_height
        
        # Ensure MarginV is 0 as per requirements
        if self.style.margin_v != 0:
            logger.warning(
                "style_margin_v_corrected",
                old_value=self.style.margin_v,
                new_value=0,
                message="MarginV must be 0, correcting automatically"
            )
            self.style.margin_v = 0
        
        logger.info(
            "ass_generator_initialized",
            video_width=video_width,
            video_height=video_height,
            style_name=self.style.name,
            alignment=self.style.alignment
        )
    
    def parse_srt(self, srt_content: str) -> List[SRTSubtitle]:
        """
        Parse SRT content into subtitle objects
        
        Args:
            srt_content: Raw SRT file content
            
        Returns:
            List of SRTSubtitle objects
            
        Raises:
            ValueError: If SRT format is invalid
        """
        subtitles = []
        
        # Split by double newline (subtitle separator)
        blocks = re.split(r'\n\s*\n', srt_content.strip())
        
        for block in blocks:
            if not block.strip():
                continue
            
            lines = block.strip().split('\n')
            
            if len(lines) < 3:
                logger.warning(
                    "srt_block_invalid",
                    block=block[:100],
                    message="SRT block has less than 3 lines, skipping"
                )
                continue
            
            try:
                # Line 1: Index
                index = int(lines[0].strip())
                
                # Line 2: Timestamps
                timestamp_line = lines[1].strip()
                match = self.SRT_TIMESTAMP_PATTERN.match(timestamp_line)
                
                if not match:
                    logger.warning(
                        "srt_timestamp_invalid",
                        line=timestamp_line,
                        message="Could not parse timestamp"
                    )
                    continue
                
                # Parse start time
                start_h, start_m, start_s, start_ms = map(int, match.groups()[:4])
                start_time = timedelta(
                    hours=start_h,
                    minutes=start_m,
                    seconds=start_s,
                    milliseconds=start_ms
                )
                
                # Parse end time
                end_h, end_m, end_s, end_ms = map(int, match.groups()[4:])
                end_time = timedelta(
                    hours=end_h,
                    minutes=end_m,
                    seconds=end_s,
                    milliseconds=end_ms
                )
                
                # Lines 3+: Text (can be multi-line)
                text = '\n'.join(lines[2:])
                
                subtitles.append(SRTSubtitle(
                    index=index,
                    start_time=start_time,
                    end_time=end_time,
                    text=text
                ))
                
            except (ValueError, IndexError) as e:
                logger.error(
                    "srt_block_parse_error",
                    block=block[:100],
                    error=str(e)
                )
                continue
        
        logger.info(
            "srt_parsed",
            subtitle_count=len(subtitles),
            total_blocks=len(blocks)
        )
        
        return subtitles
    
    def _format_ass_timestamp(self, td: timedelta) -> str:
        """
        Convert timedelta to ASS timestamp format (H:MM:SS.CC)
        
        Args:
            td: timedelta object
            
        Returns:
            ASS formatted timestamp string
        """
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        centiseconds = td.microseconds // 10000
        
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
    
    def generate_ass_header(self) -> str:
        """
        Generate ASS file header with script info and styles
        
        Returns:
            ASS header string
        """
        header = [
            "[Script Info]",
            "; Generated by YTCaption ASS Generator",
            "Title: YTCaption Subtitles",
            "ScriptType: v4.00+",
            f"PlayResX: {self.video_width}",
            f"PlayResY: {self.video_height}",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "YCbCr Matrix: None",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding",
            self.style.to_ass_line(),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        
        return '\n'.join(header)
    
    def generate_ass_event(self, subtitle: SRTSubtitle) -> str:
        """
        Generate ASS event line for a subtitle
        
        Args:
            subtitle: SRTSubtitle object
            
        Returns:
            ASS event line string
        """
        start = self._format_ass_timestamp(subtitle.start_time)
        end = self._format_ass_timestamp(subtitle.end_time)
        
        # Clean text: replace SRT line breaks with ASS format
        text = subtitle.text.replace('\n', '\\N')
        
        # ASS event format
        event = (
            f"Dialogue: 0,{start},{end},{self.style.name},,0,0,0,,{text}"
        )
        
        return event
    
    def convert_srt_to_ass(
        self,
        srt_content: str,
        output_path: Optional[Path] = None
    ) -> str:
        """
        Convert SRT content to ASS format
        
        Args:
            srt_content: Raw SRT file content
            output_path: Optional path to write ASS file
            
        Returns:
            ASS formatted content as string
            
        Raises:
            ValueError: If SRT parsing fails
        """
        # Parse SRT
        subtitles = self.parse_srt(srt_content)
        
        if not subtitles:
            raise ValueError("No valid subtitles found in SRT content")
        
        # Generate ASS
        ass_lines = [self.generate_ass_header()]
        
        for subtitle in subtitles:
            ass_lines.append(self.generate_ass_event(subtitle))
        
        ass_content = '\n'.join(ass_lines)
        
        # Write to file if path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(ass_content, encoding='utf-8')
            
            logger.info(
                "ass_file_written",
                path=str(output_path),
                size_bytes=len(ass_content),
                subtitle_count=len(subtitles)
            )
        
        return ass_content
    
    def convert_srt_file_to_ass_file(
        self,
        srt_path: Path,
        ass_path: Optional[Path] = None
    ) -> Path:
        """
        Convert SRT file to ASS file
        
        Args:
            srt_path: Path to input SRT file
            ass_path: Path to output ASS file (auto-generated if None)
            
        Returns:
            Path to generated ASS file
            
        Raises:
            FileNotFoundError: If SRT file doesn't exist
            ValueError: If SRT parsing fails
        """
        srt_path = Path(srt_path)
        
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT file not found: {srt_path}")
        
        # Auto-generate output path
        if ass_path is None:
            ass_path = srt_path.with_suffix('.ass')
        else:
            ass_path = Path(ass_path)
        
        # Read SRT content
        srt_content = srt_path.read_text(encoding='utf-8')
        
        # Convert and write
        self.convert_srt_to_ass(srt_content, ass_path)
        
        logger.info(
            "srt_to_ass_conversion_complete",
            input=str(srt_path),
            output=str(ass_path)
        )
        
        return ass_path
