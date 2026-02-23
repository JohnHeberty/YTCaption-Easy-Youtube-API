"""
JobProcessor - Chain of Responsibility pattern for job execution

🎯 Design Pattern: Chain of Responsibility
    - Execute stages in sequence
    - Each stage processes and passes context to next
    - Automatic compensation on failure (Saga pattern)

🔄 Saga Pattern:
    - Track completed stages
    - Compensate in reverse order on failure
    - Maintain consistency

📊 Features:
    - Event-driven progress tracking
    - Checkpoint-based recovery
    - Rich error context
"""

from typing import List, Optional
import logging

from .job_stage import JobStage, StageContext, StageResult, StageStatus
from ..shared.events import EventType
from ..shared.exceptions import EnhancedMakeVideoException, ErrorCode


logger = logging.getLogger(__name__)


class JobProcessor:
    """
    Job processor using Chain of Responsibility pattern
    
    Executes stages in sequence with automatic compensation on failure
    """
    
    def __init__(self, stages: List[JobStage]):
        """
        Initialize processor with stages
        
        Args:
            stages: List of stages to execute in order
        """
        self.stages = stages
        self.completed_stages: List[JobStage] = []
    
    async def process(self, context: StageContext) -> StageContext:
        """
        Process job through all stages
        
        Implements Chain of Responsibility:
        1. Execute each stage in sequence
        2. Pass enriched context to next stage
        3. On failure, compensate completed stages in reverse
        
        Args:
            context: Initial job context
            
        Returns:
            Enriched context after all stages
            
        Raises:
            EnhancedMakeVideoException: If any stage fails
        """
        logger.info(f"🚀 Starting job processing: {context.job_id} ({len(self.stages)} stages)")
        
        # Publish job started event
        await context.publish_event(
            EventType.JOB_STARTED,
            {
                'query': context.query,
                'max_shorts': context.max_shorts,
                'stages': [stage.name for stage in self.stages],
            }
        )
        
        try:
            # Execute each stage in sequence
            for i, stage in enumerate(self.stages, 1):
                logger.info(f"📍 [{i}/{len(self.stages)}] Executing stage: {stage.name}")
                
                # Execute stage
                result = await stage.run(context)
                
                # Track completed stage for potential compensation
                if result.success:
                    self.completed_stages.append(stage)
                    logger.info(
                        f"✅ Stage {stage.name} completed in {result.duration_seconds:.2f}s"
                    )
                else:
                    # Stage failed, trigger compensation
                    raise result.error or EnhancedMakeVideoException(
                        f"Stage {stage.name} failed",
                        error_code=ErrorCode.PROCESSING_STAGE_FAILED,
                        details={'stage': stage.name},
                        job_id=context.job_id,
                    )
            
            # All stages completed successfully
            logger.info(f"🎉 Job {context.job_id} completed successfully")
            
            # Publish job completed event
            await context.publish_event(
                EventType.JOB_COMPLETED,
                {
                    'final_video_path': str(context.final_video_path) if context.final_video_path else None,
                    'video_info': context.video_info,
                    'file_size': context.file_size,
                    'stages_completed': len(self.completed_stages),
                }
            )
            
            return context
            
        except Exception as e:
            # Compensate completed stages in reverse order
            logger.error(f"❌ Job {context.job_id} failed: {e}")
            await self._compensate_stages(context)
            
            # Publish job failed event
            error = e if isinstance(e, EnhancedMakeVideoException) else EnhancedMakeVideoException(
                f"Job processing failed: {str(e)}",
                error_code=ErrorCode.PROCESSING_FAILED,
                cause=e,
                job_id=context.job_id,
            )
            
            await context.publish_event(
                EventType.JOB_FAILED,
                {
                    'error': error.to_dict(),
                    'completed_stages': [s.name for s in self.completed_stages],
                }
            )
            
            raise error
    
    async def _compensate_stages(self, context: StageContext):
        """
        Compensate completed stages in reverse order (Saga pattern)
        
        Args:
            context: Job context
        """
        if not self.completed_stages:
            logger.info("No stages to compensate")
            return
        
        logger.info(f"🔄 Compensating {len(self.completed_stages)} completed stages...")
        
        # Compensate in reverse order
        for stage in reversed(self.completed_stages):
            try:
                logger.info(f"↩️  Compensating stage: {stage.name}")
                await stage.compensate(context)
                
                # Update result status
                result = context.get_result(stage.name)
                if result:
                    result.status = StageStatus.COMPENSATED
                
                logger.info(f"✅ Stage {stage.name} compensated")
                
            except Exception as e:
                # Log compensation failure but continue with other stages
                logger.error(
                    f"⚠️ Failed to compensate stage {stage.name}: {e}",
                    exc_info=True
                )
        
        logger.info("✅ Compensation completed")
    
    def get_stage(self, name: str) -> Optional[JobStage]:
        """
        Get stage by name
        
        Args:
            name: Stage name
            
        Returns:
            Stage instance or None
        """
        for stage in self.stages:
            if stage.name == name:
                return stage
        return None
    
    def get_completed_stages(self) -> List[str]:
        """
        Get list of completed stage names
        
        Returns:
            List of stage names
        """
        return [stage.name for stage in self.completed_stages]
