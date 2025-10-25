from enum import Enum
from datetime import datetime, timedelta
from typing import Optional
import os
import hashlib
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
    apply_highpass_filter: bool = True  # Aplica filtro highpass

class Job(BaseModel):
    id: str
    input_file: str
    output_file: Optional[str] = None
    status: JobStatus
    isolate_vocals: bool
    remove_noise: bool
    normalize_volume: bool
    convert_to_mono: bool
    file_size_input: Optional[int] = None
    file_size_output: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    expires_at: datetime
    progress: float = 0.0  # Progresso de 0.0 a 100.0
    apply_highpass_filter: bool  # Aplica filtro highpass
    set_sample_rate_16k: bool  # Reduz sample rate para 16kHz
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    @classmethod
    def create_new(
        cls,
        input_file: str,
        isolate_vocals: bool = False,
        remove_noise: bool = True,
        normalize_volume: bool = True,
        convert_to_mono: bool = True,
        apply_highpass_filter: bool = True,
        set_sample_rate_16k: bool = True
    ) -> "Job":
        """
        Cria novo job com ID baseado no hash do arquivo + operações
        Sistema de cache:
        - Calcula hash SHA256 do arquivo
        - Combina com operações solicitadas
        - Job ID = hash_operacoes (ex: abc123def_invm)
        - Se mesmo arquivo + mesmas operações = retorna job existente (cache)
        """
    # imports já movidos para o topo
        # Calcula hash SHA256 do arquivo (cache key)
        def _calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
            hash_obj = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()[:12]

        file_hash = _calculate_file_hash(input_file)
        # Gera código de operações (i=isolate, n=noise, v=volume, m=mono, h=highpass, s=sample_rate)
        operations = f"{'i' if isolate_vocals else ''}{'n' if remove_noise else ''}{'v' if normalize_volume else ''}{'m' if convert_to_mono else ''}{'h' if apply_highpass_filter else ''}{'s' if set_sample_rate_16k else ''}"  # pylint: disable=line-too-long
        job_id = f"{file_hash}_{operations}" if operations else file_hash
        cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        now = datetime.now()
        return cls(
            id=job_id,
            input_file=input_file,
            status=JobStatus.QUEUED,
            isolate_vocals=isolate_vocals,
            remove_noise=remove_noise,
            normalize_volume=normalize_volume,
            convert_to_mono=convert_to_mono,
            apply_highpass_filter=apply_highpass_filter,
            set_sample_rate_16k=set_sample_rate_16k,
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
    # imports já movidos para o topo
        
        hash_obj = hashlib.new(algorithm)
        
        # Lê arquivo em chunks para não sobrecarregar memória
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_obj.update(chunk)
        
        # Retorna primeiros 12 caracteres do hash (suficiente para unicidade)
        return hash_obj.hexdigest()[:12]
