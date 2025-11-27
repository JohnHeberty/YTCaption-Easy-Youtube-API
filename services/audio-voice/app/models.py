from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from dataclasses import dataclass
import hashlib


# Perfis de voz genéricos (dropdown)
class VoicePreset(str, Enum):
    female_generic = "female_generic"
    male_generic = "male_generic"
    female_young = "female_young"
    male_deep = "male_deep"
    female_warm = "female_warm"
    male_warm = "male_warm"
    female_soft = "female_soft"
    male_soft = "male_soft"


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


class QualityProfile(str, Enum):
    """
    Perfis de qualidade para geração XTTS.
    
    - BALANCED: Equilíbrio entre emoção e estabilidade (RECOMENDADO)
    - EXPRESSIVE: Máxima emoção e naturalidade (pode ter artefatos)
    - STABLE: Conservador, produção segura
    """
    BALANCED = "balanced"
    EXPRESSIVE = "expressive"
    STABLE = "stable"


@dataclass
class XTTSParameters:
    """Parâmetros de inferência XTTS."""
    temperature: float = 0.65
    repetition_penalty: float = 2.0
    top_p: float = 0.8
    top_k: int = 50
    length_penalty: float = 1.0
    speed: float = 1.0
    enable_text_splitting: bool = True
    
    @classmethod
    def from_profile(cls, profile: QualityProfile) -> 'XTTSParameters':
        """Factory method para criar parâmetros de um perfil."""
        profiles = {
            QualityProfile.BALANCED: cls(
                temperature=0.75,
                repetition_penalty=1.5,
                top_p=0.9,
                top_k=60,
                length_penalty=1.2,
                speed=1.0,
                enable_text_splitting=False
            ),
            QualityProfile.EXPRESSIVE: cls(
                temperature=0.85,
                repetition_penalty=1.3,
                top_p=0.95,
                top_k=70,
                length_penalty=1.3,
                speed=0.98,
                enable_text_splitting=False
            ),
            QualityProfile.STABLE: cls(
                temperature=0.70,
                repetition_penalty=1.7,
                top_p=0.85,
                top_k=55,
                length_penalty=1.1,
                speed=1.0,
                enable_text_splitting=True
            )
        }
        return profiles[profile]


class VoiceProfile(BaseModel):
    """Perfil de voz clonada (XTTS)"""
    id: str
    name: str
    description: Optional[str] = None
    language: str  # Idioma base da voz (pt-BR, en-US, etc.)
    
    # Arquivos e dados (XTTS usa WAV como referência)
    source_audio_path: str  # Caminho da amostra original de áudio (.wav)
    profile_path: str       # Caminho do perfil serializado (.wav para XTTS)
    
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
    
    class Config:
        arbitrary_types_allowed = True
    
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
    voice_preset: Optional[str] = None     # Voz genérica (string do enum)
    voice_id: Optional[str] = None         # ID de voz clonada (se mode=dubbing_with_clone)
    
    # Qualidade
    quality_profile: Optional[QualityProfile] = Field(
        default=QualityProfile.BALANCED,
        description="Perfil de qualidade para geração de áudio"
    )
    
    # === SPRINT 4: Parâmetros RVC ===
    enable_rvc: Optional[bool] = Field(
        default=False,
        description="Se True, aplica conversão RVC após XTTS"
    )
    rvc_model_id: Optional[str] = Field(
        default=None,
        description="ID do modelo RVC a usar (obrigatório se enable_rvc=True)"
    )
    rvc_pitch: Optional[int] = Field(
        default=0,
        ge=-12,
        le=12,
        description="Pitch shift em semitons (±12)"
    )
    rvc_index_rate: Optional[float] = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Taxa de influência do index (0-1)"
    )
    rvc_protect: Optional[float] = Field(
        default=0.33,
        ge=0.0,
        le=0.5,
        description="Proteção de consoantes sem voz (0-0.5)"
    )
    rvc_rms_mix_rate: Optional[float] = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Taxa de mix de envelope RMS (0-1)"
    )
    rvc_filter_radius: Optional[int] = Field(
        default=3,
        ge=0,
        le=7,
        description="Raio do filtro mediano de pitch (0-7)"
    )
    rvc_f0_method: Optional[str] = Field(
        default='rmvpe',
        description="Método de extração de pitch (rmvpe/fcpe/pm/harvest/dio/crepe)"
    )
    rvc_hop_length: Optional[int] = Field(
        default=128,
        ge=1,
        le=512,
        description="Hop length para extração de pitch (1-512)"
    )
    
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
    
    # Qualidade
    quality_profile: Optional[QualityProfile] = Field(
        default=QualityProfile.BALANCED,
        description="Perfil de qualidade: balanced, expressive, stable"
    )


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


class RvcModelResponse(BaseModel):
    """Response para operações de RVC models (Sprint 7 API)"""
    id: str = Field(..., description="Unique model ID (MD5 hash)")
    name: str = Field(..., description="Model name")
    description: Optional[str] = Field(None, description="Model description")
    pth_file: str = Field(..., description="Path to .pth file")
    index_file: Optional[str] = Field(None, description="Path to .index file (optional)")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    file_size_mb: float = Field(..., description="Total size in MB")


class RvcModelListResponse(BaseModel):
    """Response para listagem de RVC models (Sprint 7 API)"""
    total: int = Field(..., description="Total number of models")
    models: List[RvcModelResponse] = Field(..., description="List of RVC models")


# === RVC MODELS (Sprint 3) ===

class RvcModel(BaseModel):
    """
    Modelo RVC para voice conversion
    """
    model_id: str = Field(..., description="ID único do modelo")
    name: str = Field(..., min_length=1, max_length=100, description="Nome do modelo")
    pth_path: str = Field(..., description="Caminho para arquivo .pth")
    index_path: Optional[str] = Field(None, description="Caminho para arquivo .index (opcional)")
    sample_rate: int = Field(24000, description="Sample rate do modelo (Hz)")
    version: str = Field("v2", description="Versão do RVC (v1/v2)")
    description: Optional[str] = Field(None, max_length=500, description="Descrição do modelo")
    created_at: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def create_new(
        cls,
        name: str,
        model_path: str,
        index_path: Optional[str] = None,
        description: Optional[str] = None
    ) -> 'RvcModel':
        """Factory para criar novo modelo RVC"""
        model_id = hashlib.md5(f"{name}_{model_path}".encode()).hexdigest()[:16]
        return cls(
            model_id=model_id,
            name=name,
            pth_path=model_path,
            index_path=index_path,
            description=description
        )


class RvcParameters(BaseModel):
    """
    Parâmetros para conversão RVC
    """
    pitch: int = Field(
        0,
        ge=-12,
        le=12,
        description="Pitch shift em semitons (-12 a +12)"
    )
    index_rate: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Taxa de influência do index (0.0 a 1.0)"
    )
    protect: float = Field(
        0.33,
        ge=0.0,
        le=0.5,
        description="Proteção de consoantes/respiração (0.0 a 0.5)"
    )
    rms_mix_rate: float = Field(
        0.25,
        ge=0.0,
        le=1.0,
        description="Mix rate do volume envelope (0.0 a 1.0)"
    )
    filter_radius: int = Field(
        3,
        ge=0,
        le=7,
        description="Raio do filtro de mediana para harvest (0-7)"
    )
    f0_method: str = Field(
        "rmvpe",
        description="Método de extração de pitch (rmvpe, fcpe, pm, harvest, dio, crepe)"
    )
    hop_length: int = Field(
        128,
        description="Hop length para processamento de áudio"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "pitch": 0,
                "index_rate": 0.5,
                "protect": 0.33,
                "rms_mix_rate": 0.25,
                "filter_radius": 3,
                "f0_method": "rmvpe",
                "hop_length": 128
            }
        }

