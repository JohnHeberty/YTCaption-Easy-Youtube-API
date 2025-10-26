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


class AudioProcessingRequest(BaseModel):
    """Request para processamento de áudio com parâmetros booleanos"""
    remove_noise: bool = False
    convert_to_mono: bool = False
    apply_highpass_filter: bool = False
    set_sample_rate_16k: bool = False
    isolate_vocals: bool = False


class Job(BaseModel):
    id: str
    input_file: str
    output_file: Optional[str] = None
    status: JobStatus
    filename: Optional[str] = None
    file_size_input: Optional[int] = None
    file_size_output: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    expires_at: datetime
    progress: float = 0.0  # Progresso de 0.0 a 100.0
    
    # Parâmetros de processamento
    remove_noise: bool = False
    convert_to_mono: bool = False
    apply_highpass_filter: bool = False
    set_sample_rate_16k: bool = False
    isolate_vocals: bool = False
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    @property
    def processing_operations(self) -> str:
        """Gera string identificadora das operações para cache"""
        operations = []
        if self.remove_noise:
            operations.append("n")
        if self.convert_to_mono:
            operations.append("m")
        if self.apply_highpass_filter:
            operations.append("h")
        if self.set_sample_rate_16k:
            operations.append("s")
        if self.isolate_vocals:
            operations.append("v")
        return "".join(operations) if operations else "none"
    
    @classmethod
    def create_new(
        cls, 
        filename: str, 
        remove_noise: bool = False,
        convert_to_mono: bool = False,
        apply_highpass_filter: bool = False,
        set_sample_rate_16k: bool = False,
        isolate_vocals: bool = False
    ) -> "Job":
        # Calcula hash do nome do arquivo + operações para criar ID único
        operations = [
            "n" if remove_noise else "",
            "m" if convert_to_mono else "",
            "h" if apply_highpass_filter else "",
            "s" if set_sample_rate_16k else "",
            "v" if isolate_vocals else ""
        ]
        operation_string = "".join([op for op in operations if op])
        content = f"{filename}_{operation_string}" if operation_string else filename
        job_id = hashlib.md5(content.encode()).hexdigest()[:12]
        
        now = datetime.now()
        cache_ttl_hours = 24
        
        return cls(
            id=job_id,
            input_file="",  # será preenchido depois
            status=JobStatus.QUEUED,
            filename=filename,
            remove_noise=remove_noise,
            convert_to_mono=convert_to_mono,
            apply_highpass_filter=apply_highpass_filter,
            set_sample_rate_16k=set_sample_rate_16k,
            isolate_vocals=isolate_vocals,
            created_at=now,
            expires_at=now + timedelta(hours=cache_ttl_hours)
        )