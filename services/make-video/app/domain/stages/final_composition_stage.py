"""
FinalCompositionStage - Add audio and burn subtitles

🎯 Responsibilities:
    - Add audio track to video
    - Burn subtitles with styling
    - Create final video file
"""

from pathlib import Path
from typing import Dict, Any
import logging

from ..job_stage import JobStage, StageContext
from ...shared.exceptions import VideoProcessingException, ErrorCode


logger = logging.getLogger(__name__)


class FinalCompositionStage(JobStage):
    """Stage 7: Final composition (audio + subtitles)"""
    
    def __init__(self, video_builder):
        """
        Initialize stage
        
        Args:
            video_builder: VideoBuilder instance
        """
        super().__init__(
            name="final_composition",
            progress_start=85.0,
            progress_end=92.0
        )
        self.video_builder = video_builder
    
    def validate(self, context: StageContext):
        """Validate all required files exist"""
        if not context.temp_video_path or not context.temp_video_path.exists():
            raise VideoProcessingException(
                "Temporary video file not found",
                error_code=ErrorCode.VIDEO_FILE_NOT_FOUND,
                job_id=context.job_id,
            )
        
        if not context.audio_path or not context.audio_path.exists():
            raise VideoProcessingException(
                "Audio file not found",
                error_code=ErrorCode.AUDIO_FILE_NOT_FOUND,
                job_id=context.job_id,
            )
        
        if not context.subtitle_path or not context.subtitle_path.exists():
            raise VideoProcessingException(
                "Subtitle file not found",
                error_code=ErrorCode.SUBTITLE_FILE_NOT_FOUND,
                job_id=context.job_id,
            )
    
    async def execute(self, context: StageContext) -> Dict[str, Any]:
        """
        Compose final video with audio and subtitles
        
        Returns:
            Dict with video_with_audio_path and final_video_path
        """
        logger.info(f"🎨 Final composition: audio + subtitles")
        
        # 1. Add audio to video
        video_with_audio_path = Path(context.settings['temp_dir']) / context.job_id / "video_with_audio.mp4"
        
        logger.info(f"  🎵 Adding audio...")
        await self.video_builder.add_audio(
            video_path=str(context.temp_video_path),
            audio_path=str(context.audio_path),
            output_path=str(video_with_audio_path)
        )
        
        logger.info(f"  ✅ Audio added")
        
        # 2. Burn subtitles
        final_video_path = Path(context.settings['output_dir']) / f"{context.job_id}_final.mp4"
        
        logger.info(f"  📝 Burning subtitles...")
        await self.video_builder.burn_subtitles(
            video_path=str(video_with_audio_path),
            subtitle_path=str(context.subtitle_path),
            output_path=str(final_video_path),
            style=context.subtitle_style
        )
        
        logger.info(f"  ✅ Subtitles burned")
        logger.info(f"✅ Final video created: {final_video_path}")
        
        # Update context
        context.video_with_audio_path = video_with_audio_path
        context.final_video_path = final_video_path
        
        return {
            'video_with_audio_path': str(video_with_audio_path),
            'final_video_path': str(final_video_path),
        }
    
    async def compensate(self, context: StageContext):
        """Delete intermediate and final video files"""
        if context.video_with_audio_path and context.video_with_audio_path.exists():
            logger.info(f"↩️  Deleting video with audio: {context.video_with_audio_path}")
            context.video_with_audio_path.unlink()
        
        if context.final_video_path and context.final_video_path.exists():
            logger.info(f"↩️  Deleting final video: {context.final_video_path}")
            context.final_video_path.unlink()
