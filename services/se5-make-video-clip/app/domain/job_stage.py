"""
JobStage - Template Method pattern for processing stages

🎯 Design Pattern: Template Method
    - Define skeleton of algorithm in base class
    - Subclasses override specific steps
    - Hook methods for customization

🔄 Lifecycle:
    1. validate() - Pre-execution validation
    2. execute() - Main processing logic
    3. compensate() - Rollback on failure (Saga pattern)
    4. get_checkpoint_name() - For recovery

📊 StageContext: Rich domain context shared between stages
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from common.datetime_utils import now_brazil

from enum import Enum
from pathlib import Path
from typing import Any

from ..shared.events import Event, EventType, EventPublisher
from ..shared.exceptions import EnhancedMakeVideoException, ErrorCode


class StageStatus(str, Enum):
    """Stage execution status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass
class StageResult:
    """Result of stage execution"""
    status: StageStatus
    data: dict[str, Any] = field(default_factory=dict)
    error: EnhancedMakeVideoException | None = None
    duration_seconds: float = 0.0
    checkpoint_name: str | None = None
    
    @property
    def success(self) -> bool:
        """Check if stage succeeded"""
        return self.status == StageStatus.COMPLETED
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'status': self.status.value,
            'data': self.data,
            'error': self.error.to_dict() if self.error else None,
            'duration_seconds': self.duration_seconds,
            'checkpoint_name': self.checkpoint_name,
        }


@dataclass
class StageContext:
    """
    Rich domain context shared between stages
    
    Contains all state needed for job processing
    """
    # Job identifiers
    job_id: str
    query: str
    
    # Processing parameters
    max_shorts: int
    aspect_ratio: str
    crop_position: str
    subtitle_language: str
    subtitle_style: dict[str, Any]
    
    # Settings
    settings: dict[str, Any]
    
    # Event publisher
    event_publisher: EventPublisher | None = None
    
    # Stage results (accumulated)
    results: dict[str, StageResult] = field(default_factory=dict)
    
    # Audio processing
    audio_path: Path | None = None
    audio_duration: float | None = None
    target_video_duration: float | None = None
    
    # Shorts fetching
    shorts_list: list[dict[str, Any]] = field(default_factory=list)
    downloaded_shorts: list[dict[str, Any]] = field(default_factory=list)
    selected_shorts: list[dict[str, Any]] = field(default_factory=list)
    
    # Video assembly
    temp_video_path: Path | None = None
    video_with_audio_path: Path | None = None
    final_video_path: Path | None = None
    
    # Subtitles
    subtitle_path: Path | None = None
    raw_cues: list[dict[str, Any]] = field(default_factory=list)
    gated_cues: list[dict[str, Any]] = field(default_factory=list)
    burn_subtitles: bool = True  # FIX-ERROS Fase 2: flag para queimar legendas no conteúdo

    # Title card
    hook_text: str | None = None  # FIX-ERROS Fase 1: texto do title card
    
    # Video info
    video_info: dict[str, Any] | None = None
    file_size: int | None = None
    
    # Timestamps
    started_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_result(self, stage_name: str, result: StageResult) -> None:
        """Add stage result to context"""
        self.results[stage_name] = result
    
    def get_result(self, stage_name: str) -> StageResult | None:
        """Get stage result from context"""
        return self.results.get(stage_name)
    
    async def publish_event(self, event_type: EventType, data: dict[str, Any]) -> None:
        """Publish event if publisher available"""
        if self.event_publisher:
            import uuid
            from datetime import datetime, timezone
            event = Event(
                id=str(uuid.uuid4()),
                type=event_type,
                source="make-video-service",
                timestamp=datetime.now(timezone.utc),
                data={
                    'job_id': self.job_id,
                    **data
                },
                subject=self.job_id,
            )
            await self.event_publisher.publish(event)


class JobStage(ABC):
    """
    Base class for job processing stages (Template Method pattern)
    
    🎯 Template Method Pattern:
        - run() defines the algorithm skeleton
        - Subclasses implement specific steps
        
    🔄 Saga Pattern:
        - compensate() for rollback on failure
        
    📊 Observability:
        - Event publishing at each stage
        - Checkpoint saving for recovery
    """
    
    def __init__(self, name: str, progress_start: float, progress_end: float) -> None:
        """
        Initialize stage
        
        Args:
            name: Stage name (e.g., "analyze_audio")
            progress_start: Starting progress percentage (0-100)
            progress_end: Ending progress percentage (0-100)
        """
        self.name = name
        self.progress_start = progress_start
        self.progress_end = progress_end
    
    async def run(self, context: StageContext) -> StageResult:
        """
        Execute stage (Template Method)
        
        Orchestrates the execution lifecycle:
        1. Validate pre-conditions
        2. Execute main logic
        3. Save checkpoint
        4. Publish events
        
        Args:
            context: Rich domain context
            
        Returns:
            StageResult with execution outcome
        """
        start_time = now_brazil()
        
        try:
            # Publish stage start event
            await context.publish_event(
                EventType.JOB_STAGE_STARTED,
                {
                    'stage': self.name,
                    'progress': self.progress_start,
                }
            )
            
            # 1. Validate pre-conditions
            self.validate(context)
            
            # 2. Execute main logic
            result_data = await self.execute(context)
            
            # 3. Calculate duration
            end_time = now_brazil()
            duration = (end_time - start_time).total_seconds()
            
            # 4. Create success result
            result = StageResult(
                status=StageStatus.COMPLETED,
                data=result_data,
                duration_seconds=duration,
                checkpoint_name=self.get_checkpoint_name(),
            )
            
            # 5. Add to context
            context.add_result(self.name, result)
            
            # 6. Publish stage completion event
            await context.publish_event(
                EventType.JOB_STAGE_COMPLETED,
                {
                    'stage': self.name,
                    'progress': self.progress_end,
                    'duration': duration,
                    'data': result_data,
                }
            )
            
            return result
            
        except Exception as e:
            # Calculate duration even on failure
            end_time = now_brazil()
            duration = (end_time - start_time).total_seconds()
            
            # Wrap in EnhancedMakeVideoException if needed
            if isinstance(e, EnhancedMakeVideoException):
                error = e
            else:
                error = EnhancedMakeVideoException(
                    f"Stage {self.name} failed: {str(e)}",
                    error_code=ErrorCode.PROCESSING_STAGE_FAILED,
                    details={'stage': self.name},
                    cause=e,
                    job_id=context.job_id,
                )
            
            # Create failure result
            result = StageResult(
                status=StageStatus.FAILED,
                error=error,
                duration_seconds=duration,
            )
            
            # Add to context
            context.add_result(self.name, result)
            
            # Publish stage failure event
            await context.publish_event(
                EventType.JOB_STAGE_FAILED,
                {
                    'stage': self.name,
                    'error': error.to_dict(),
                    'duration': duration,
                }
            )
            
            raise error
    
    @abstractmethod
    def validate(self, context: StageContext) -> None:
        """
        Validate pre-conditions (Hook Method)
        
        Raises:
            EnhancedMakeVideoException: If validation fails
        """
        pass
    
    @abstractmethod
    async def execute(self, context: StageContext) -> dict[str, Any]:
        """
        Execute main processing logic (Hook Method)
        
        Returns:
            Dict with stage-specific result data
            
        Raises:
            EnhancedMakeVideoException: If execution fails
        """
        pass
    
    async def compensate(self, context: StageContext) -> None:
        """
        Compensate/rollback stage (Saga Pattern)
        
        Called when later stage fails and we need to undo this stage's work.
        Default: no-op (override if needed)
        """
        pass
    
    def get_checkpoint_name(self) -> str:
        """
        Get checkpoint name for recovery
        
        Returns:
            Checkpoint name (e.g., "analyzing_audio_completed")
        """
        return f"{self.name}_completed"
    
    def calculate_progress(self, completion_ratio: float) -> float:
        """
        Calculate current progress within stage
        
        Args:
            completion_ratio: 0.0 to 1.0
            
        Returns:
            Progress percentage (0-100)
        """
        return self.progress_start + (self.progress_end - self.progress_start) * completion_ratio
