from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import hashlib


class JobStatus(str, Enum):
    """Status do job de dublagem/clonagem"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobMode(str, Enum):
    """Modo de operação do job"""
    DUBBING = "dubbing"                      # Dublagem com voz genérica
    DUBBING_WITH_CLONE = "dubbing_with_clone"  # Dublagem com voz clonada
    CLONE_VOICE = "clone_voice"              # Clonagem de voz


class VoiceProfile(BaseModel):
    """Perfil de voz clonada"""
    id: str
    name: str
    description: Optional[str] = None
    language: str  # Idioma base da voz (pt-BR, en-US, etc.)
    
    # Arquivos e dados
    source_audio_path: str  # Caminho da amostra original
    profile_path: str       # Caminho do perfil serializado (.pkl)
    
    # Metadata
    duration: Optional[float] = None  # Duração da amostra em segundos
    sample_rate: Optional[int] = None
    quality_score: Optional[float] = None  # Score de qualidade (0-1)
    
    # Timestamps
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: datetime
    
    # Uso
    usage_count: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Verifica se o perfil expirou"""
        return datetime.now() > self.expires_at
    
    @classmethod
    def create_new(
        cls,
        name: str,
        language: str,
        source_audio_path: str,
        profile_path: str,
        description: Optional[str] = None,
        duration: Optional[float] = None,
        sample_rate: Optional[int] = None,
        ttl_days: int = 30
    ) -> "VoiceProfile":
        """Cria novo perfil de voz"""
        now = datetime.now()
        
        # Gera ID único baseado em nome + timestamp
        timestamp_str = now.strftime("%Y%m%d%H%M%S%f")
        voice_id = f"voice_{hashlib.md5(f'{name}_{timestamp_str}'.encode('utf-8')).hexdigest()[:12]}"
        
        return cls(
            id=voice_id,
            name=name,
            description=description,
            language=language,
            source_audio_path=source_audio_path,
            profile_path=profile_path,
            duration=duration,
            sample_rate=sample_rate,
            created_at=now,
            expires_at=now + timedelta(days=ttl_days)
        )
    
    def increment_usage(self):
        """Incrementa contador de uso"""
        self.usage_count += 1
        self.last_used_at = datetime.now()


class Job(BaseModel):
    """Job de dublagem ou clonagem de voz"""
    id: str
    mode: JobMode
    status: JobStatus
    
    # Arquivos
    input_file: Optional[str] = None      # Para clonagem: amostra de áudio
    output_file: Optional[str] = None     # Áudio dublado gerado
    
    # Dublagem
    text: Optional[str] = None            # Texto para dublar
    source_language: Optional[str] = None  # Idioma de origem
    target_language: Optional[str] = None  # Idioma de destino
    voice_preset: Optional[str] = None     # Voz genérica (female_generic, male_deep, etc.)
    voice_id: Optional[str] = None         # ID de voz clonada (se mode=dubbing_with_clone)
    
    # Clonagem de voz
    voice_name: Optional[str] = None       # Nome do perfil a criar
    voice_description: Optional[str] = None
    
    # Resultados
    audio_url: Optional[str] = None        # URL para download
    duration: Optional[float] = None       # Duração do áudio gerado em segundos
    file_size_input: Optional[int] = None
    file_size_output: Optional[int] = None
    
    # Metadata
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    expires_at: datetime
    progress: float = 0.0  # Progresso de 0.0 a 100.0
    
    # OpenVoice specific
    openvoice_model: Optional[str] = None  # Modelo usado
    openvoice_params: Optional[Dict[str, Any]] = None  # Parâmetros OpenVoice
    
    @property
    def is_expired(self) -> bool:
        """Verifica se o job expirou"""
        return datetime.now() > self.expires_at
    
    @classmethod
    def create_new(
        cls,
        mode: JobMode,
        text: Optional[str] = None,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
        voice_preset: Optional[str] = None,
        voice_id: Optional[str] = None,
        voice_name: Optional[str] = None,
        voice_description: Optional[str] = None,
        cache_ttl_hours: int = 24
    ) -> "Job":
        """Cria novo job"""
        now = datetime.now()
        
        # Gera ID único baseado em parâmetros + timestamp
        timestamp_str = now.strftime("%Y%m%d%H%M%S%f")
        
        # Hash baseado no modo e parâmetros
        if mode == JobMode.DUBBING or mode == JobMode.DUBBING_WITH_CLONE:
            hash_input = f"{text}_{source_language}_{target_language}_{voice_preset or voice_id}"
        else:  # CLONE_VOICE
            hash_input = f"{voice_name}_{timestamp_str}"
        
        job_id = f"job_{hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:12]}"
        
        return cls(
            id=job_id,
            mode=mode,
            status=JobStatus.QUEUED,
            text=text,
            source_language=source_language,
            target_language=target_language,
            voice_preset=voice_preset,
            voice_id=voice_id,
            voice_name=voice_name,
            voice_description=voice_description,
            created_at=now,
            expires_at=now + timedelta(hours=cache_ttl_hours)
        )


class DubbingRequest(BaseModel):
    """Request para dublagem de texto"""
    mode: JobMode = JobMode.DUBBING
    text: str = Field(..., min_length=1, max_length=10000, description="Texto para dublar")
    source_language: str = Field(..., description="Idioma de origem (ex: pt-BR, en-US)")
    target_language: Optional[str] = Field(None, description="Idioma de destino (opcional)")
    
    # Para voz genérica
    voice_preset: Optional[str] = Field(None, description="Voz genérica pré-configurada")
    
    # Para voz clonada
    voice_id: Optional[str] = Field(None, description="ID de voz clonada")
    
    # Parâmetros opcionais
    speed: Optional[float] = Field(1.0, ge=0.5, le=2.0, description="Velocidade da fala (0.5-2.0)")
    pitch: Optional[float] = Field(1.0, ge=0.5, le=2.0, description="Tom de voz (0.5-2.0)")


class VoiceCloneRequest(BaseModel):
    """Request para clonagem de voz (usado em multipart/form-data)"""
    name: str = Field(..., min_length=1, max_length=100, description="Nome do perfil de voz")
    description: Optional[str] = Field(None, max_length=500, description="Descrição do perfil")
    language: str = Field(..., description="Idioma base da voz (ex: pt-BR)")


class VoiceListResponse(BaseModel):
    """Response para listagem de vozes"""
    total: int
    voices: List[VoiceProfile]


class JobListResponse(BaseModel):
    """Response para listagem de jobs"""
    total: int
    jobs: List[Job]
