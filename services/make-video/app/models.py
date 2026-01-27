from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import shortuuid


class JobStatus(str, Enum):
    """Status do job de criação de vídeo"""
    QUEUED = "queued"
    ANALYZING_AUDIO = "analyzing_audio"
    FETCHING_SHORTS = "fetching_shorts"
    DOWNLOADING_SHORTS = "downloading_shorts"
    SELECTING_SHORTS = "selecting_shorts"
    ASSEMBLING_VIDEO = "assembling_video"
    GENERATING_SUBTITLES = "generating_subtitles"
    FINAL_COMPOSITION = "final_composition"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ShortInfo(BaseModel):
    """Informações de um short usado no vídeo"""
    video_id: str
    duration_seconds: float  # Changed from int to float for precision
    file_path: str
    position_in_video: float  # Changed from int to float - posição em segundos no vídeo final
    resolution: str = "1080x1920"
    fps: int = 30


class SubtitleSegment(BaseModel):
    """Segmento de legenda"""
    id: int
    start: float
    end: float
    text: str


class StageInfo(BaseModel):
    """Informações de uma etapa de processamento"""
    status: str  # "pending", "in_progress", "completed", "failed"
    progress: float = 0.0
    duration: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class JobResult(BaseModel):
    """Resultado final do job"""
    video_url: str
    video_file: str
    file_size: int
    file_size_mb: float
    duration: float
    resolution: str
    aspect_ratio: str
    fps: int
    shorts_used: int
    shorts_list: List[ShortInfo]
    subtitle_segments: int
    processing_time: float


class Job(BaseModel):
    """Job de criação de vídeo"""
    job_id: str = Field(default_factory=lambda: shortuuid.uuid())
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    
    # Input data
    query: str
    audio_duration: Optional[float] = None  # Será preenchido após análise
    target_video_duration: Optional[float] = None  # Será preenchido após análise
    max_shorts: int = 100
    subtitle_language: str = "pt"
    subtitle_style: str = "dynamic"
    aspect_ratio: str = "9:16"
    crop_position: str = "center"
    
    # Processing stages
    stages: Dict[str, StageInfo] = {}
    
    # Result
    result: Optional[JobResult] = None
    error: Optional[Dict[str, Any]] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True


class CreateVideoRequest(BaseModel):
    """Request para criar vídeo"""
    query: str = Field(..., min_length=1, max_length=200, description="Search query for shorts")
    max_shorts: int = Field(default=100, ge=10, le=500, description="Maximum shorts to fetch")
    subtitle_language: str = Field(default="pt", description="Language code for subtitles")
    subtitle_style: str = Field(default="dynamic", description="Subtitle style (static, dynamic, minimal)")
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio (9:16, 16:9, 1:1, 4:5)")
    crop_position: str = Field(default="center", description="Crop position (center, top, bottom)")


class JobResponse(BaseModel):
    """Response ao criar ou consultar job"""
    job_id: str
    status: str
    progress: float = 0.0
    current_stage: Optional[str] = None
    stages: Optional[Dict[str, StageInfo]] = None
    result: Optional[JobResult] = None
    error: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Response do health check"""
    status: str
    service: str = "make-video"
    version: str = "1.0.0"
    dependencies: Dict[str, str]
    storage: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
