"""
Configuração robusta para Audio Transcriber Service
Implementação com validação Pydantic e configurações hierárquicas
"""
import os
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class DatabaseConfig(BaseModel):
    """Configurações de banco de dados"""
    
    redis_url: str = Field(
        default="redis://localhost:6379/1",
        description="URL de conexão com Redis para audio-transcriber"
    )
    
    redis_max_connections: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Número máximo de conexões Redis"
    )
    
    redis_retry_on_timeout: bool = Field(
        default=True,
        description="Retry automático em timeout Redis"
    )
    
    redis_socket_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Timeout de socket Redis em segundos"
    )


class CacheConfig(BaseModel):
    """Configurações de cache"""
    
    ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,  # 7 dias
        description="TTL padrão do cache em horas"
    )
    
    cleanup_interval_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,  # 24 horas
        description="Intervalo de limpeza automática em minutos"
    )
    
    max_cache_size_gb: float = Field(
        default=5.0,
        ge=0.1,
        le=100.0,
        description="Tamanho máximo do cache em GB"
    )


class TranscriptionConfig(BaseModel):
    """Configurações de transcrição"""
    
    # Whisper settings
    whisper_model: str = Field(
        default="base",
        description="Modelo Whisper (tiny, base, small, medium, large)"
    )
    
    whisper_device: str = Field(
        default="auto",
        description="Device para processamento (auto, cpu, cuda)"
    )
    
    # Processing limits
    max_audio_duration_minutes: int = Field(
        default=180,  # 3 horas
        ge=1,
        le=480,  # 8 horas
        description="Duração máxima de áudio em minutos"
    )
    
    max_file_size_mb: int = Field(
        default=500,
        ge=1,
        le=2048,  # 2GB
        description="Tamanho máximo de arquivo em MB"
    )
    
    supported_formats: List[str] = Field(
        default=["mp3", "wav", "flac", "ogg", "m4a", "aac", "wma"],
        description="Formatos de áudio suportados"
    )
    
    output_formats: List[str] = Field(
        default=["srt", "vtt", "txt", "json"],
        description="Formatos de saída suportados"
    )
    
    # Quality settings
    enable_vad: bool = Field(
        default=True,
        description="Habilita Voice Activity Detection"
    )
    
    beam_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Beam size para decoding (qualidade vs velocidade)"
    )
    
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Temperature para sampling (0 = determinístico)"
    )


class SecurityConfig(BaseModel):
    """Configurações de segurança"""
    
    # Rate limiting
    rate_limit_requests: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Requests por minuto por IP"
    )
    
    rate_limit_window: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Janela de rate limiting em segundos"
    )
    
    # File validation
    check_file_magic_bytes: bool = Field(
        default=True,
        description="Verifica magic bytes de arquivos"
    )
    
    check_file_entropy: bool = Field(
        default=True,
        description="Detecta arquivos suspeitos por entropia"
    )
    
    allowed_mime_types: List[str] = Field(
        default=[
            "audio/mpeg", "audio/wav", "audio/flac", 
            "audio/ogg", "audio/mp4", "audio/aac"
        ],
        description="MIME types permitidos"
    )


class MonitoringConfig(BaseModel):
    """Configuração de monitoramento e observabilidade"""
    
    # Métricas Prometheus
    enable_prometheus: bool = Field(
        default=True,
        description="Habilita métricas Prometheus"
    )
    
    metrics_port: int = Field(
        default=9091,  # Diferente do audio-normalization
        ge=1024,
        le=65535,
        description="Porta para métricas"
    )
    
    # Rastreamento distribuído
    enable_tracing: bool = Field(
        default=True,
        description="Habilita rastreamento distribuído"
    )
    
    jaeger_endpoint: Optional[str] = Field(
        default=None,
        description="Endpoint Jaeger"
    )
    
    trace_sampling_ratio: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Taxa de amostragem"
    )
    
    # Logging estruturado
    log_correlation_id: bool = Field(
        default=True,
        description="Habilita correlation ID"
    )
    
    structured_logging: bool = Field(
        default=True,
        description="Habilita logging JSON"
    )
    
    enable_performance_logging: bool = Field(
        default=True,
        description="Logging de performance"
    )
    
    # Health checks
    health_check_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Intervalo de health check"
    )


class AppSettings(BaseSettings):
    """Configurações principais da aplicação Audio Transcriber"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__"
    )
    
    # Aplicação
    app_name: str = Field(default="Audio Transcriber Service")
    version: str = Field(default="2.0.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    
    # Servidor
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8002, ge=1024, le=65535)  # Porta específica
    workers: int = Field(default=1, ge=1, le=8)
    
    # Diretórios
    upload_dir: Path = Field(default=Path("./uploads"))
    transcriptions_dir: Path = Field(default=Path("./transcriptions"))
    models_dir: Path = Field(default=Path("./models"))
    temp_dir: Path = Field(default=Path("./temp"))
    log_dir: Path = Field(default=Path("./logs"))
    
    # Logging
    log_level: str = Field(default="INFO")
    
    # Configurações aninhadas
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    def model_post_init(self, __context) -> None:
        """Pós-inicialização: cria diretórios necessários"""
        for dir_path in [
            self.upload_dir,
            self.transcriptions_dir,
            self.models_dir,
            self.temp_dir,
            self.log_dir
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> AppSettings:
    """
    Obtém configurações da aplicação (cached)
    
    Returns:
        AppSettings: Instância das configurações
    """
    return AppSettings()