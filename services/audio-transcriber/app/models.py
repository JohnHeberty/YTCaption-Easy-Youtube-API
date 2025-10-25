from enum import Enum
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioNormalizationRequest(BaseModel):
    """Request para normalização de áudio"""
    audio_file_path: str  # Caminho do arquivo de áudio de entrada
    isolate_vocals: bool = False  # Isola voz (remove instrumental)
    remove_noise: bool = True  # Remove ruído de fundo
    normalize_volume: bool = True  # Normaliza volume
    convert_to_mono: bool = True  # Converte para mono


class Job(BaseModel):
    id: str
    input_file: str
    output_file: Optional[str] = None
    status: JobStatus
    language: str = "auto"
    output_format: str = "srt"
    transcription_text: Optional[str] = None
    detected_language: Optional[str] = None
    segments_count: Optional[int] = None
    audio_duration: Optional[float] = None
    file_size_input: Optional[int] = None
    file_size_output: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    expires_at: datetime
    progress: float = 0.0

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    @classmethod
    def create_new(
        cls,
        input_file: str,
        language: str = "auto",
        output_format: str = "srt"
    ) -> "Job":
        """
        Cria novo job de transcrição com ID baseado em hash do arquivo + idioma + formato
        Job ID = hash_language_format
        """
        import os
        file_hash = cls._calculate_file_hash(input_file)
        job_id = f"{file_hash}_{language}_{output_format}"
        cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        now = datetime.now()
        return cls(
            id=job_id,
            input_file=input_file,
            status=JobStatus.QUEUED,
            language=language,
            output_format=output_format,
            created_at=now,
            expires_at=now + timedelta(hours=cache_ttl_hours)
        )
    
    @staticmethod
    def _calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
        """
        Calcula hash do arquivo para cache
        
        Args:
            file_path: Caminho do arquivo
            algorithm: Algoritmo de hash (sha256, md5)
            
        Returns:
            Hash hexadecimal (primeiros 12 caracteres)
        """
        import hashlib
        
        hash_obj = hashlib.new(algorithm)
        
        # Lê arquivo em chunks para não sobrecarregar memória
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_obj.update(chunk)
        
        # Retorna primeiros 12 caracteres do hash (suficiente para unicidade)
        return hash_obj.hexdigest()[:12]
