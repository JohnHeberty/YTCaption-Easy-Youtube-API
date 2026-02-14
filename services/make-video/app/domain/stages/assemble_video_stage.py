"""
AssembleVideoStage - Concatenate shorts into single video

🎯 Responsibilities:
    - Extract video file paths
    - Concatenate with aspect ratio handling
    - Remove audio from shorts
    - Create temporary video file
"""

from pathlib import Path
from typing import Dict, Any
import logging

from ..job_stage import JobStage, StageContext
from ...shared.exceptions import VideoProcessingException, ErrorCode


logger = logging.getLogger(__name__)


class AssembleVideoStage(JobStage):
    """Stage 5: Assemble video from shorts"""
    
    def __init__(self, video_builder):
        """
        Initialize stage
        
        Args:
            video_builder: VideoBuilder instance
        """
        super().__init__(
            name="assemble_video",
            progress_start=75.0,
            progress_end=80.0
        )
        self.video_builder = video_builder
    
    def validate(self, context: StageContext):
        """Validate selected shorts exist"""
        if not context.selected_shorts:
            raise VideoProcessingException(
                "No selected shorts available",
                error_code=ErrorCode.NO_VALID_SHORTS,
                job_id=context.job_id,
            )
    
    async def execute(self, context: StageContext) -> Dict[str, Any]:
        """
        Assemble video from selected shorts
        
        Returns:
            Dict with temp_video_path and video_count
        """
        logger.info(f"🎬 Assembling video from {len(context.selected_shorts)} shorts")
        
        # Extract video file paths
        video_files = [short['file_path'] for short in context.selected_shorts]
        
        # Create output path
        temp_video_path = Path(context.settings['temp_dir']) / context.job_id / "video_no_audio.mp4"
        temp_video_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Concatenate videos
        await self.video_builder.concatenate_videos(
            video_files=video_files,
            output_path=str(temp_video_path),
            aspect_ratio=context.aspect_ratio,
            crop_position=context.crop_position,
            remove_audio=True  # Remove audio from shorts
        )
        
        logger.info(f"✅ Video assembled: {temp_video_path}")
        
        # Update context
        context.temp_video_path = temp_video_path
        
        return {
            'temp_video_path': str(temp_video_path),
            'video_count': len(video_files),
            'aspect_ratio': context.aspect_ratio,
        }
    
    async def compensate(self, context: StageContext):
        """Delete temporary video file"""
        if context.temp_video_path and context.temp_video_path.exists():
            logger.info(f"↩️  Deleting temporary video: {context.temp_video_path}")
            context.temp_video_path.unlink()
