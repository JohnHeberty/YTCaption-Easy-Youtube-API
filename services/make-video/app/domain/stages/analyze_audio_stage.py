"""
AnalyzeAudioStage - Analyze audio file and calculate video duration

🎯 Responsibilities:
    - Locate audio file
    - Get audio duration
    - Calculate target video duration (audio + padding)
    - Validate audio length constraints
"""

from pathlib import Path
from typing import Dict, Any
import logging

from ..job_stage import JobStage, StageContext
from ...core.constants import ProcessingLimits
from ...shared.exceptions import AudioProcessingException, ErrorCode


logger = logging.getLogger(__name__)


class AnalyzeAudioStage(JobStage):
    """Stage 1: Analyze uploaded audio file"""
    
    def __init__(self, video_builder):
        """
        Initialize stage
        
        Args:
            video_builder: VideoBuilder instance for audio operations
        """
        super().__init__(
            name="analyze_audio",
            progress_start=5.0,
            progress_end=15.0
        )
        self.video_builder = video_builder
    
    def validate(self, context: StageContext):
        """Validate audio file exists"""
        # Audio path will be found in execute()
        pass
    
    async def execute(self, context: StageContext) -> Dict[str, Any]:
        """
        Analyze audio file
        
        Returns:
            Dict with audio_duration, target_video_duration, audio_path
        """
        logger.info(f"📊 Analyzing audio for job {context.job_id}")
        
        # Locate audio file
        audio_base_path = Path(context.settings['audio_upload_dir']) / context.job_id / "audio"
        
        audio_path = None
        if audio_base_path.exists():
            audio_path = audio_base_path
        else:
            # Try common extensions
            for ext in ['.mp3', '.wav', '.m4a', '.ogg', '.flac']:
                test_path = audio_base_path.parent / f"audio{ext}"
                if test_path.exists():
                    audio_path = test_path
                    break
        
        if not audio_path or not audio_path.exists():
            raise AudioProcessingException(
                f"Audio file not found at {audio_base_path}",
                error_code=ErrorCode.AUDIO_FILE_NOT_FOUND,
                details={'expected_path': str(audio_base_path)},
                job_id=context.job_id,
            )
        
        # Get audio duration
        audio_duration = await self.video_builder.get_audio_duration(str(audio_path))
        
        logger.info(f"🎵 Audio duration: {audio_duration:.2f}s")
        
        # Validate duration constraints
        if audio_duration < ProcessingLimits.MIN_AUDIO_DURATION:
            raise AudioProcessingException(
                f"Audio too short: {audio_duration:.1f}s (minimum {ProcessingLimits.MIN_AUDIO_DURATION}s)",
                error_code=ErrorCode.AUDIO_TOO_SHORT,
                details={
                    'duration': audio_duration,
                    'minimum': ProcessingLimits.MIN_AUDIO_DURATION
                },
                job_id=context.job_id,
            )
        
        if audio_duration > ProcessingLimits.MAX_AUDIO_DURATION:
            raise AudioProcessingException(
                f"Audio too long: {audio_duration:.1f}s (maximum {ProcessingLimits.MAX_AUDIO_DURATION}s)",
                error_code=ErrorCode.AUDIO_TOO_LONG,
                details={
                    'duration': audio_duration,
                    'maximum': ProcessingLimits.MAX_AUDIO_DURATION
                },
                job_id=context.job_id,
            )
        
        # Calculate target video duration with padding
        padding_ms = int(context.settings.get('video_trim_padding_ms', 1000))
        padding_seconds = padding_ms / 1000.0
        target_duration = audio_duration + padding_seconds
        
        logger.info(
            f"🎯 Target video: {target_duration:.2f}s "
            f"(audio {audio_duration:.2f}s + padding {padding_seconds:.2f}s)"
        )
        
        # Update context
        context.audio_path = audio_path
        context.audio_duration = audio_duration
        context.target_video_duration = target_duration
        
        return {
            'audio_path': str(audio_path),
            'audio_duration': audio_duration,
            'target_video_duration': target_duration,
            'padding_seconds': padding_seconds,
        }
