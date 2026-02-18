"""
Audio-Video Synchronization Validator

Validates sync between audio and video with automatic drift correction.
Follows Netflix's approach to A/V sync quality (tolerance: 500ms).
"""

import logging
from typing import Tuple, Dict, Any, Optional
from pathlib import Path

from ..shared.exceptions_v2 import (
    SyncDriftException,
    AudioCorruptedException,
    VideoCorruptedException
)

logger = logging.getLogger(__name__)


class SyncValidator:
    """
    Validates audio-video synchronization with automatic correction
    
    Features:
    - Detects A/V drift (audio vs video duration mismatch)
    - Automatic subtitle timestamp correction
    - Configurable tolerance (default: 500ms, Netflix standard)
    - VFR (Variable Frame Rate) detection and handling
    
    Example:
        validator = SyncValidator(tolerance_seconds=0.5)
        is_valid, drift, metadata = await validator.validate_sync(
            video_path="/tmp/final.mp4",
            audio_path="/tmp/audio.mp3",
            video_builder=builder
        )
    """
    
    def __init__(self, tolerance_seconds: float = 0.5):
        """
        Initialize sync validator
        
        Args:
            tolerance_seconds: Maximum acceptable drift in seconds.
                Netflix standard: 0.5s (500ms)
                Values: 0.3-0.5s = strict, 0.5-1.0s = normal, >1.0s = lenient
        
        Raises:
            ValueError: If tolerance is negative or too large (>5s)
        """
        if tolerance_seconds < 0:
            raise ValueError(f"Tolerance must be positive, got {tolerance_seconds}")
        if tolerance_seconds > 5.0:
            logger.warning(
                f"Tolerance {tolerance_seconds}s is very high (>5s). "
                f"Consider using 0.5-1.0s for production quality."
            )
        
        self.tolerance = tolerance_seconds
        logger.info(f"SyncValidator initialized with tolerance={tolerance_seconds}s")
    
    async def validate_sync(
        self,
        video_path: str,
        audio_path: str,
        video_builder,  # VideoBuilder instance (avoid circular import)
        job_id: Optional[str] = None
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Validate synchronization between audio and video
        
        Compares audio duration with video duration to detect sync drift.
        This catches issues from:
        - Variable frame rate (VFR) videos
        - Duplicate frames during concatenation
        - FFmpeg timestamp errors
        - Keyframe rounding
        
        Args:
            video_path: Path to final video file (with subtitles burned in)
            audio_path: Path to original audio file
            video_builder: VideoBuilder instance for metadata extraction
            job_id: Optional job ID for logging/tracing
        
        Returns:
            Tuple of (is_valid, drift_seconds, metadata_dict)
            
            metadata_dict contains:
            - audio_duration: float
            - video_duration: float
            - drift: float (absolute difference)
            - drift_percentage: float (drift / audio * 100)
            - tolerance: float
            - is_valid: bool
            - needs_correction: bool
        
        Raises:
            SyncDriftException: If drift exceeds tolerance
            AudioCorruptedException: If audio file is invalid
            VideoCorruptedException: If video file is invalid
        """
        video_path_obj = Path(video_path)
        audio_path_obj = Path(audio_path)
        
        # Input validation
        if not video_path_obj.exists():
            raise VideoCorruptedException(
                video_path=str(video_path),
                reason="Video file not found for sync validation"
            )
        
        if not audio_path_obj.exists():
            raise AudioCorruptedException(
                audio_path=str(audio_path),
                reason="Audio file not found for sync validation"
            )
        
        logger.info(
            f"🔍 Validating A/V sync",
            extra={
                "video": video_path_obj.name,
                "audio": audio_path_obj.name,
                "tolerance": self.tolerance,
                "job_id": job_id
            }
        )
        
        # Get durations using ffprobe
        try:
            video_info = await video_builder.get_video_info(str(video_path))
            video_duration = float(video_info['duration'])
        except Exception as e:
            raise VideoCorruptedException(
                video_path=str(video_path),
                reason=f"Failed to extract video duration: {str(e)}",
                cause=e
            )
        
        try:
            audio_duration = await video_builder.get_audio_duration(str(audio_path))
            audio_duration = float(audio_duration)
        except Exception as e:
            raise AudioCorruptedException(
                audio_path=str(audio_path),
                reason=f"Failed to extract audio duration: {str(e)}",
                cause=e
            )
        
        # Calculate drift
        drift = abs(video_duration - audio_duration)
        drift_percentage = (drift / audio_duration * 100) if audio_duration > 0 else 0
        is_valid = drift <= self.tolerance
        needs_correction = not is_valid
        
        metadata = {
            "audio_duration": audio_duration,
            "video_duration": video_duration,
            "drift": drift,
            "drift_percentage": drift_percentage,
            "tolerance": self.tolerance,
            "is_valid": is_valid,
            "needs_correction": needs_correction,
            "job_id": job_id
        }
        
        # Log result
        if is_valid:
            logger.info(
                f"✅ A/V sync valid: drift={drift:.3f}s ({drift_percentage:.2f}%)",
                extra=metadata
            )
        else:
            logger.warning(
                f"⚠️ A/V sync drift detected: {drift:.3f}s ({drift_percentage:.2f}%) "
                f"exceeds tolerance ({self.tolerance}s)",
                extra=metadata
            )
            raise SyncDriftException(
                audio_duration=audio_duration,
                video_duration=video_duration,
                drift=drift,
                tolerance=self.tolerance,
                job_id=job_id
            )
        
        return is_valid, drift, metadata
    
    def calculate_subtitle_correction(
        self,
        drift: float,
        audio_duration: float,
        video_duration: float
    ) -> Dict[str, float]:
        """
        Calculate linear correction for subtitle timestamps
        
        When video duration != audio duration, subtitle timestamps
        need adjustment to maintain sync. This uses linear scaling:
        
        - If video > audio: stretch subtitles (multiply timestamps)
        - If video < audio: compress subtitles (divide timestamps)
        
        Formula: new_timestamp = old_timestamp * scale_factor + offset
        
        Args:
            drift: Absolute difference in seconds
            audio_duration: Original audio duration (ground truth)
            video_duration: Actual video duration (may have drift)
        
        Returns:
            Dict with:
            - scale_factor: float (multiply each timestamp by this)
            - offset: float (add this to each timestamp in seconds)
            - direction: str ("stretch" or "compress")
        
        Example:
            Audio: 60s, Video: 61s → scale_factor = 1.0167 (1.67% slower)
            Subtitle at 30s → corrected to 30.5s
        """
        if audio_duration <= 0:
            logger.error(f"Invalid audio_duration: {audio_duration}")
            return {"scale_factor": 1.0, "offset": 0.0, "direction": "none"}
        
        scale_factor = video_duration / audio_duration
        direction = "stretch" if scale_factor > 1.0 else "compress"
        
        correction_percentage = abs(scale_factor - 1.0) * 100
        
        logger.info(
            f"📐 Subtitle correction calculated",
            extra={
                "scale_factor": scale_factor,
                "correction_percentage": correction_percentage,
                "direction": direction,
                "audio_duration": audio_duration,
                "video_duration": video_duration,
                "drift": drift
            }
        )
        
        return {
            "scale_factor": scale_factor,
            "offset": 0.0,  # Linear scaling, no offset needed
            "direction": direction,
            "correction_percentage": correction_percentage
        }
    
    async def apply_subtitle_correction(
        self,
        srt_path: str,
        scale_factor: float,
        offset: float = 0.0,
        output_path: Optional[str] = None
    ) -> str:
        """
        Apply temporal correction to SRT subtitle file
        
        Adjusts all subtitle timestamps by:
        new_time = (old_time * scale_factor) + offset
        
        This corrects sync drift caused by VFR, duplicate frames,
        or FFmpeg timestamp rounding.
        
        Args:
            srt_path: Path to original SRT file
            scale_factor: Multiply all timestamps by this
            offset: Add this offset in seconds (rarely needed)
            output_path: Optional output path (default: .corrected.srt)
        
        Returns:
            Path to corrected SRT file
        
        Raises:
            FileNotFoundError: If SRT file doesn't exist
            ValueError: If scale_factor is invalid (<0.5 or >2.0)
        
        Note:
            Requires 'pysrt' library. Install with: pip install pysrt
        """
        srt_path_obj = Path(srt_path)
        
        # Validation
        if not srt_path_obj.exists():
            raise FileNotFoundError(f"SRT file not found: {srt_path}")
        
        if scale_factor < 0.5 or scale_factor > 2.0:
            raise ValueError(
                f"Scale factor {scale_factor} is out of safe range (0.5-2.0). "
                f"This indicates severe sync issues - check video processing pipeline."
            )
        
        logger.info(
            f"🔧 Applying subtitle correction",
            extra={
                "srt_file": srt_path_obj.name,
                "scale_factor": scale_factor,
                "offset": offset
            }
        )
        
        try:
            import pysrt
        except ImportError:
            logger.error(
                "pysrt library not installed. Install with: pip install pysrt"
            )
            raise ImportError(
                "pysrt library required for subtitle correction. "
                "Install with: pip install pysrt"
            )
        
        # Load SRT
        try:
            subs = pysrt.open(str(srt_path_obj), encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to parse SRT file: {e}")
            raise ValueError(f"Invalid SRT file: {e}")
        
        # Apply correction to all subtitles
        for sub in subs:
            # Start time (convert ordinal to seconds, apply correction, convert back)
            start_seconds = sub.start.ordinal / 1000.0
            new_start_seconds = (start_seconds * scale_factor) + offset
            sub.start.ordinal = int(new_start_seconds * 1000)
            
            # End time
            end_seconds = sub.end.ordinal / 1000.0
            new_end_seconds = (end_seconds * scale_factor) + offset
            sub.end.ordinal = int(new_end_seconds * 1000)
        
        # Save corrected SRT
        if output_path is None:
            output_path = str(srt_path_obj.with_suffix('.corrected.srt'))
        
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        subs.save(str(output_path_obj), encoding='utf-8')
        
        logger.info(
            f"✅ Subtitle correction applied: {len(subs)} subtitles adjusted",
            extra={
                "input": srt_path_obj.name,
                "output": output_path_obj.name,
                "subtitle_count": len(subs)
            }
        )
        
        return str(output_path_obj)
