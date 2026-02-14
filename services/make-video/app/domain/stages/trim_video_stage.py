"""
TrimVideoStage - Trim video to target duration with validation

🎯 Responsibilities:
    - Verify video duration matches target
    - Trim video if needed
    - Validate final output
    - Get video metadata
"""

from pathlib import Path
from typing import Dict, Any
import logging
import shutil

from ..job_stage import JobStage, StageContext
from ...shared.exceptions import VideoProcessingException, ErrorCode


logger = logging.getLogger(__name__)


class TrimVideoStage(JobStage):
    """Stage 8: Trim video to exact duration"""
    
    def __init__(self, video_builder):
        """
        Initialize stage
        
        Args:
            video_builder: VideoBuilder instance
        """
        super().__init__(
            name="trim_video",
            progress_start=92.0,
            progress_end=100.0
        )
        self.video_builder = video_builder
    
    def validate(self, context: StageContext):
        """Validate final video exists"""
        if not context.final_video_path or not context.final_video_path.exists():
            raise VideoProcessingException(
                "Final video file not found",
                error_code=ErrorCode.VIDEO_FILE_NOT_FOUND,
                job_id=context.job_id,
            )
    
    async def execute(self, context: StageContext) -> Dict[str, Any]:
        """
        Trim video to target duration
        
        Returns:
            Dict with video_info, file_size, trimmed status
        """
        logger.info(f"✂️  Trimming video to target duration")
        
        # Get current video info
        pre_trim_info = await self.video_builder.get_video_info(str(context.final_video_path))
        current_duration = pre_trim_info['duration']
        
        # Calculate final duration
        padding_ms = int(context.settings.get('video_trim_padding_ms', 1000))
        padding_seconds = padding_ms / 1000.0
        final_duration = context.audio_duration + padding_seconds
        
        logger.info(f"📊 Trim analysis:")
        logger.info(f"   ├─ Audio duration: {context.audio_duration:.2f}s")
        logger.info(f"   ├─ Padding: {padding_ms}ms ({padding_seconds:.2f}s)")
        logger.info(f"   ├─ Target final: {final_duration:.2f}s")
        logger.info(f"   └─ Current video: {current_duration:.2f}s")
        
        # CRITICAL VALIDATION: Video must be >= audio duration
        if current_duration < context.audio_duration - 0.5:  # -0.5s tolerance for keyframes
            raise VideoProcessingException(
                f"CRITICAL: Video ({current_duration:.2f}s) is shorter than audio ({context.audio_duration:.2f}s)!",
                error_code=ErrorCode.VIDEO_TOO_SHORT,
                details={
                    'video_duration': current_duration,
                    'audio_duration': context.audio_duration,
                    'target_duration': final_duration,
                },
                job_id=context.job_id,
            )
        
        # Validate trim configuration
        if final_duration <= context.audio_duration:
            raise VideoProcessingException(
                "Invalid trim configuration: video would be shorter than or equal to audio",
                error_code=ErrorCode.INVALID_TRIM_CONFIG,
                details={
                    'audio_duration': context.audio_duration,
                    'padding_ms': padding_ms,
                    'final_duration': final_duration,
                    'suggestion': 'Increase VIDEO_TRIM_PADDING_MS to at least 100ms'
                },
                job_id=context.job_id,
            )
        
        # Trim if needed
        trimmed = False
        if abs(current_duration - final_duration) > 0.5:  # Only if significant difference
            logger.info(f"✂️  Trimming: {current_duration:.2f}s → {final_duration:.2f}s")
            
            # Create temporary trimmed path
            trimmed_video_path = Path(context.settings['temp_dir']) / context.job_id / f"{context.job_id}_trimmed.mp4"
            
            # Execute trim
            await self.video_builder.trim_video(
                video_path=str(context.final_video_path),
                output_path=str(trimmed_video_path),
                max_duration=final_duration
            )
            
            # Replace final video with trimmed version
            shutil.move(str(trimmed_video_path), str(context.final_video_path))
            
            logger.info(f"✅ Video trimmed and replaced")
            trimmed = True
        else:
            logger.info(
                f"⏭️  Trim skipped: video duration ({current_duration:.2f}s) "
                f"already matches target ({final_duration:.2f}s ± 0.5s)"
            )
        
        # Get final video info
        video_info = await self.video_builder.get_video_info(str(context.final_video_path))
        file_size = context.final_video_path.stat().st_size
        
        logger.info(f"📊 Final video info:")
        logger.info(f"   ├─ Duration: {video_info['duration']:.2f}s")
        logger.info(f"   ├─ Resolution: {video_info.get('width', 0)}x{video_info.get('height', 0)}")
        logger.info(f"   ├─ FPS: {video_info.get('fps', 0)}")
        logger.info(f"   └─ Size: {file_size / (1024*1024):.2f} MB")
        
        # Update context
        context.video_info = video_info
        context.file_size = file_size
        
        return {
            'video_info': video_info,
            'file_size': file_size,
            'final_duration': video_info['duration'],
            'trimmed': trimmed,
            'target_duration': final_duration,
        }
