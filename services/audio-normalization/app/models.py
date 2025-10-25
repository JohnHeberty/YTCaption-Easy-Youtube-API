from enum import Enum
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
import hashlib


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobRequest(BaseModel):
    operation: Optional[str] = "normalize"  # normalize, denoise, etc.


class Job(BaseModel):
    id: str
    input_file: str
    output_file: Optional[str] = None
    status: JobStatus
    operation: str
    filename: Optional[str] = None
    file_size_input: Optional[int] = None
    file_size_output: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    expires_at: datetime
    progress: float = 0.0  # Progresso de 0.0 a 100.0
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    @classmethod
    def create_new(cls, filename: str, operation: str = "normalize") -> "Job":
        # Calcula hash do nome do arquivo + operação para criar ID único
        content = f"{filename}_{operation}"
        job_id = hashlib.md5(content.encode()).hexdigest()[:12]
        
        now = datetime.now()
        cache_ttl_hours = 24
        
        return cls(
            id=job_id,
            input_file="",  # será preenchido depois
            status=JobStatus.QUEUED,
            operation=operation,
            filename=filename,
            created_at=now,
            expires_at=now + timedelta(hours=cache_ttl_hours)
        )