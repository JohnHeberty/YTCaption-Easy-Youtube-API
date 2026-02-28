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

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[EnhancedMakeVideoException] = None
    duration_seconds: float = 0.0
    checkpoint_name: Optional[str] = None
    
    @property
    def success(self) -> bool:
        """Check if stage succeeded"""
        return self.status == StageStatus.COMPLETED
    
    def to_dict(self) -> Dict[str, Any]:
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
    subtitle_style: Dict[str, Any]
    
    # Settings
    settings: Dict[str, Any]
    
    # Event publisher
    event_publisher: Optional[EventPublisher] = None
    
    # Stage results (accumulated)
    results: Dict[str, StageResult] = field(default_factory=dict)
    
    # Audio processing
    audio_path: Optional[Path] = None
    audio_duration: Optional[float] = None
    target_video_duration: Optional[float] = None
    
    # Shorts fetching
    shorts_list: List[Dict[str, Any]] = field(default_factory=list)
    downloaded_shorts: List[Dict[str, Any]] = field(default_factory=list)
    selected_shorts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Video assembly
    temp_video_path: Optional[Path] = None
    video_with_audio_path: Optional[Path] = None
    final_video_path: Optional[Path] = None
    
    # Subtitles
    subtitle_path: Optional[Path] = None
    raw_cues: List[Dict[str, Any]] = field(default_factory=list)
    gated_cues: List[Dict[str, Any]] = field(default_factory=list)
    
    # Video info
    video_info: Optional[Dict[str, Any]] = None
    file_size: Optional[int] = None
    
    # Timestamps
    started_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_result(self, stage_name: str, result: StageResult):
        """Add stage result to context"""
        self.results[stage_name] = result
    
    def get_result(self, stage_name: str) -> Optional[StageResult]:
        """Get stage result from context"""
        return self.results.get(stage_name)
    
    async def publish_event(self, event_type: EventType, data: Dict[str, Any]):
        """Publish event if publisher available"""
        if self.event_publisher:
            event = Event(
                event_type=event_type,
                source="make-video-service",
                data={
                    'job_id': self.job_id,
                    **data
                }
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
    
    def __init__(self, name: str, progress_start: float, progress_end: float):
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
    def validate(self, context: StageContext):
        """
        Validate pre-conditions (Hook Method)
        
        Raises:
            EnhancedMakeVideoException: If validation fails
        """
        pass
    
    @abstractmethod
    async def execute(self, context: StageContext) -> Dict[str, Any]:
        """
        Execute main processing logic (Hook Method)
        
        Returns:
            Dict with stage-specific result data
            
        Raises:
            EnhancedMakeVideoException: If execution fails
        """
        pass
    
    async def compensate(self, context: StageContext):
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
