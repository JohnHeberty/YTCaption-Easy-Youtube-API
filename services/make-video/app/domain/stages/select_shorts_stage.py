"""
SelectShortsStage - Randomly select shorts up to target duration

🎯 Responsibilities:
    - Shuffle downloaded shorts
    - Select videos until target duration reached
    - Validate selection
"""

from typing import Dict, Any
import logging
import random

from ..job_stage import JobStage, StageContext
from ...shared.exceptions import VideoProcessingException, ErrorCode


logger = logging.getLogger(__name__)


class SelectShortsStage(JobStage):
    """Stage 4: Select shorts randomly"""
    
    def __init__(self):
        super().__init__(
            name="select_shorts",
            progress_start=70.0,
            progress_end=75.0
        )
    
    def validate(self, context: StageContext):
        """Validate downloaded shorts exist"""
        if not context.downloaded_shorts:
            raise VideoProcessingException(
                "No downloaded shorts available",
                error_code=ErrorCode.NO_VALID_SHORTS,
                job_id=context.job_id,
            )
    
    async def execute(self, context: StageContext) -> Dict[str, Any]:
        """
        Select shorts randomly up to target duration
        
        Returns:
            Dict with selected_count and total_duration
        """
        logger.info(f"🎲 Selecting shorts (target: {context.target_video_duration:.1f}s)")
        
        # Shuffle for randomness
        downloaded_shorts = context.downloaded_shorts.copy()
        random.shuffle(downloaded_shorts)
        
        selected_shorts = []
        total_duration = 0.0
        
        for short in downloaded_shorts:
            if total_duration >= context.target_video_duration:
                logger.info(
                    f"🎯 Target reached: {total_duration:.1f}s >= {context.target_video_duration:.1f}s"
                )
                break
            
            selected_shorts.append(short)
            short_duration = short.get('duration_seconds', 0)
            total_duration += short_duration
            
            logger.info(
                f"  ✓ Added {short['video_id']}: {short_duration:.1f}s "
                f"(cumulative: {total_duration:.1f}s)"
            )
        
        if not selected_shorts:
            raise VideoProcessingException(
                "No shorts available for video creation",
                error_code=ErrorCode.NO_VALID_SHORTS,
                job_id=context.job_id,
            )
        
        logger.info(
            f"🎯 Selected {len(selected_shorts)} shorts "
            f"({total_duration:.1f}s / target {context.target_video_duration:.1f}s)"
        )
        
        # Update context
        context.selected_shorts = selected_shorts
        
        return {
            'selected_count': len(selected_shorts),
            'total_duration': total_duration,
            'target_duration': context.target_video_duration,
        }
