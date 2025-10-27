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
        # DEBUG: Log dos parâmetros recebidos
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 DEBUG Job.create_new - filename: {filename}")
        logger.info(f"🔍 DEBUG Job.create_new - remove_noise: {remove_noise}")
        logger.info(f"🔍 DEBUG Job.create_new - apply_highpass_filter: {apply_highpass_filter}")
        logger.info(f"🔍 DEBUG Job.create_new - isolate_vocals: {isolate_vocals}")
        
        # Calcula hash ÚNICO do arquivo + operações + timestamp
        # Isso garante que cada job tenha ID único, evitando colisões de cache
        now = datetime.now()
        operations = [
            "n" if remove_noise else "",
            "m" if convert_to_mono else "",
            "h" if apply_highpass_filter else "",
            "s" if set_sample_rate_16k else "",
            "v" if isolate_vocals else ""
        ]
        operation_string = "".join([op for op in operations if op])
        
        # Adiciona timestamp em microsegundos para garantir unicidade
        timestamp_str = now.strftime("%Y%m%d%H%M%S%f")
        content = f"{filename}_{operation_string}_{timestamp_str}"
        job_id = hashlib.md5(content.encode()).hexdigest()[:12]
        
        logger.info(f"🔍 DEBUG Job.create_new - operations: {operations}")
        logger.info(f"🔍 DEBUG Job.create_new - operation_string: '{operation_string}'")
        logger.info(f"🔍 DEBUG Job.create_new - timestamp: {timestamp_str}")
        logger.info(f"🔍 DEBUG Job.create_new - timestamp: {timestamp_str}")
        logger.info(f"🔍 DEBUG Job.create_new - content: '{content}'")
        logger.info(f"🔍 DEBUG Job.create_new - job_id: {job_id}")
        
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