"""
Modelos atualizados para Audio Transcriber Service
Versão resiliente com validação e configuração robusta
"""
from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import hashlib
import os


class JobStatus(str, Enum):
    """Estados do job de transcrição"""
    QUEUED = "queued"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Prioridade do job"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TranscriptionRequest(BaseModel):
    """Request para criação de job de transcrição"""
    language: str = Field(default="auto", description="Idioma do áudio")
    output_format: str = Field(default="srt", description="Formato de saída")
    enable_vad: bool = Field(default=True, description="Voice Activity Detection")
    beam_size: int = Field(default=5, ge=1, le=20, description="Beam size")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0, description="Temperature")
    priority: JobPriority = Field(default=JobPriority.NORMAL, description="Prioridade")
    
    @validator('language')
    def validate_language(cls, v):
        valid_languages = [
            "auto", "pt", "en", "es", "fr", "de", "it", "ja", "ko", "zh", 
            "ru", "ar", "hi", "nl", "sv", "pl", "tr", "da", "no", "fi"
        ]
        if v not in valid_languages:
            raise ValueError(f"Language must be one of: {', '.join(valid_languages)}")
        return v
    
    @validator('output_format')
    def validate_output_format(cls, v):
        valid_formats = ["srt", "vtt", "txt", "json"]
        if v not in valid_formats:
            raise ValueError(f"Output format must be one of: {', '.join(valid_formats)}")
        return v


class JobResponse(BaseModel):
    """Response para operações de job"""
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime
    expires_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_file: Optional[str] = None
    transcription_text: Optional[str] = None
    processing_options: Optional[Dict[str, Any]] = None


class Job(BaseModel):
    """Modelo principal do job de transcrição"""
    
    # Identificação
    id: str = Field(..., description="ID único do job")
    
    # Arquivos
    input_file: str = Field(..., description="Caminho do arquivo de entrada")
    output_file: Optional[str] = Field(None, description="Caminho do arquivo de saída")
    
    # Status e controle
    status: JobStatus = Field(default=JobStatus.QUEUED, description="Status atual")
    priority: JobPriority = Field(default=JobPriority.NORMAL, description="Prioridade")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Progresso %")
    
    # Configurações de transcrição
    language: str = Field(default="auto", description="Idioma do áudio")
    output_format: str = Field(default="srt", description="Formato de saída")
    enable_vad: bool = Field(default=True, description="Voice Activity Detection")
    beam_size: int = Field(default=5, description="Beam size")
    temperature: float = Field(default=0.0, description="Temperature")
    
    # Resultados
    transcription_text: Optional[str] = Field(None, description="Texto transcrito")
    detected_language: Optional[str] = Field(None, description="Idioma detectado")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confiança")
    
    # Metadados do áudio
    audio_duration: Optional[float] = Field(None, description="Duração em segundos")
    sample_rate: Optional[int] = Field(None, description="Sample rate")
    channels: Optional[int] = Field(None, description="Número de canais")
    
    # Informações de arquivo
    file_size_input: Optional[int] = Field(None, description="Tamanho entrada bytes")
    file_size_output: Optional[int] = Field(None, description="Tamanho saída bytes")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now, description="Criado em")
    started_at: Optional[datetime] = Field(None, description="Iniciado em")
    completed_at: Optional[datetime] = Field(None, description="Completado em")
    expires_at: datetime = Field(..., description="Expira em")
    
    # Error handling
    error_message: Optional[str] = Field(None, description="Mensagem de erro")
    retry_count: int = Field(default=0, description="Tentativas de retry")
    max_retries: int = Field(default=3, description="Máximo de retries")
    
    # Processamento
    processing_time: Optional[float] = Field(None, description="Tempo de processamento")
    whisper_model: Optional[str] = Field(None, description="Modelo Whisper usado")
    device_used: Optional[str] = Field(None, description="Device usado (cpu/cuda)")
    
    # Segmentação
    segments_count: Optional[int] = Field(None, description="Número de segmentos")
    segments_data: Optional[List[Dict[str, Any]]] = Field(None, description="Dados dos segmentos")
    
    @property
    def is_expired(self) -> bool:
        """Verifica se o job expirou"""
        return datetime.now() > self.expires_at
    
    @property
    def is_processing(self) -> bool:
        """Verifica se o job está sendo processado"""
        return self.status == JobStatus.PROCESSING
    
    @property
    def is_completed(self) -> bool:
        """Verifica se o job foi completado"""
        return self.status == JobStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Verifica se o job falhou"""
        return self.status == JobStatus.FAILED
    
    @property
    def can_retry(self) -> bool:
        """Verifica se pode fazer retry"""
        return self.retry_count < self.max_retries and self.is_failed
    
    @property
    def processing_duration(self) -> Optional[float]:
        """Duração do processamento em segundos"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def real_time_factor(self) -> Optional[float]:
        """Fator de tempo real (audio_duration / processing_time)"""
        if self.audio_duration and self.processing_time and self.processing_time > 0:
            return self.audio_duration / self.processing_time
        return None
    
    def update_progress(self, progress: float, message: Optional[str] = None):
        """Atualiza progresso do job"""
        self.progress = max(0.0, min(100.0, progress))
        if message:
            # Podemos usar um campo para mensagens de progresso se necessário
            pass
    
    def mark_as_processing(self, model: str, device: str):
        """Marca job como sendo processado"""
        self.status = JobStatus.PROCESSING
        self.started_at = datetime.now()
        self.whisper_model = model
        self.device_used = device
        self.progress = 0.0
    
    def mark_as_completed(self, transcription_text: str, output_file: str, **metadata):
        """Marca job como completado"""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.now()
        self.transcription_text = transcription_text
        self.output_file = output_file
        self.progress = 100.0
        
        # Calcula tempo de processamento
        if self.started_at:
            self.processing_time = (self.completed_at - self.started_at).total_seconds()
        
        # Atualiza metadados adicionais
        for key, value in metadata.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def mark_as_failed(self, error_message: str, increment_retry: bool = True):
        """Marca job como falhado"""
        self.status = JobStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now()
        
        if increment_retry:
            self.retry_count += 1
    
    def mark_as_cancelled(self, reason: str = "Cancelled by user"):
        """Marca job como cancelado"""
        self.status = JobStatus.CANCELLED
        self.error_message = reason
        self.completed_at = datetime.now()
    
    @classmethod
    def create_new(
        cls,
        input_file: str,
        language: str = "auto",
        output_format: str = "srt",
        **options
    ) -> "Job":
        """
        Cria novo job de transcrição com ID baseado em hash do arquivo + configurações
        
        Args:
            input_file: Caminho do arquivo de entrada
            language: Idioma para transcrição  
            output_format: Formato de saída
            **options: Opções adicionais
        """
        # Calcula hash único baseado no arquivo e configurações
        file_hash = cls._calculate_file_hash(input_file)
        config_hash = cls._calculate_config_hash(language, output_format, **options)
        job_id = f"{file_hash}_{config_hash}"
        
        # TTL do cache
        cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        now = datetime.now()
        
        return cls(
            id=job_id,
            input_file=input_file,
            language=language,
            output_format=output_format,
            expires_at=now + timedelta(hours=cache_ttl_hours),
            **options
        )
    
    @staticmethod
    def _calculate_file_hash(file_path: str) -> str:
        """Calcula hash do arquivo"""
        try:
            hash_obj = hashlib.sha256()
            
            # Para arquivos grandes, lê apenas início e fim
            with open(file_path, 'rb') as f:
                # Lê primeiros 8KB
                chunk = f.read(8192)
                hash_obj.update(chunk)
                
                # Se arquivo é maior que 16KB, lê também o final
                f.seek(0, 2)  # Vai para o final
                file_size = f.tell()
                
                if file_size > 16384:
                    f.seek(-8192, 2)  # Últimos 8KB
                    chunk = f.read(8192)
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()[:12]
            
        except Exception:
            # Fallback para hash simples se não conseguir ler arquivo
            return hashlib.sha256(file_path.encode()).hexdigest()[:12]
    
    @staticmethod
    def _calculate_config_hash(language: str, output_format: str, **options) -> str:
        """Calcula hash das configurações"""
        # Combina configurações em string determinística
        config_str = f"{language}_{output_format}"
        
        # Adiciona opções relevantes ordenadas
        relevant_options = ['enable_vad', 'beam_size', 'temperature']
        for key in sorted(relevant_options):
            if key in options:
                config_str += f"_{key}_{options[key]}"
        
        return hashlib.md5(config_str.encode()).hexdigest()[:8]


class ProcessingResult(BaseModel):
    """Resultado do processamento de transcrição"""
    success: bool
    job_id: str
    transcription_text: Optional[str] = None
    output_file: Optional[str] = None
    segments: Optional[List[Dict[str, Any]]] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TranscriptionSegment(BaseModel):
    """Segmento individual da transcrição"""
    id: int
    start: float = Field(..., description="Tempo de início em segundos")
    end: float = Field(..., description="Tempo de fim em segundos") 
    text: str = Field(..., description="Texto transcrito")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    @property
    def duration(self) -> float:
        """Duração do segmento"""
        return self.end - self.start


class TranscriptionStats(BaseModel):
    """Estatísticas de transcrição"""
    total_jobs: int = 0
    jobs_by_status: Dict[JobStatus, int] = {}
    jobs_by_language: Dict[str, int] = {}
    average_processing_time: Optional[float] = None
    total_audio_duration: Optional[float] = None
    success_rate: Optional[float] = None