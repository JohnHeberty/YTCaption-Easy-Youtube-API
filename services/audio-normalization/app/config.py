"""
Configuração robusta e validada para o microserviço
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseModel):
    """Configuração do Redis/Database"""
    url: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    min_memory_bytes: int = Field(default=52428800, description="Mínimo 50MB para inicialização")
    max_connections: int = Field(default=20, description="Max conexões simultâneas")
    connection_timeout: int = Field(default=5, description="Timeout de conexão em segundos")
    retry_attempts: int = Field(default=5, description="Tentativas de reconexão")
    
    @validator('url')
    def validate_redis_url(cls, v):
        """Valida formato da URL do Redis"""
        if not v.startswith(('redis://', 'rediss://')):
            raise ValueError('Redis URL deve começar com redis:// ou rediss://')
        return v


class CacheConfig(BaseModel):
    """Configuração de cache"""
    ttl_hours: int = Field(default=24, ge=1, le=168, description="TTL do cache (1h-7d)")
    cleanup_interval_minutes: int = Field(default=30, ge=5, le=1440, description="Intervalo de limpeza")
    max_cache_size_mb: int = Field(default=1024, description="Tamanho máximo do cache em MB")


class ProcessingConfig(BaseModel):
    """Configuração de processamento de áudio"""
    max_file_size_mb: int = Field(default=100, ge=1, le=500, description="Tamanho máximo de arquivo")
    max_duration_minutes: int = Field(default=30, ge=1, le=120, description="Duração máxima do áudio")
    allowed_formats: list[str] = Field(default=['.wav', '.mp3', '.flac', '.ogg', '.m4a'])
    max_concurrent_jobs: int = Field(default=3, description="Jobs simultâneos por worker")
    job_timeout_minutes: int = Field(default=30, description="Timeout de processamento")
    
    # Configurações de qualidade
    default_sample_rate: int = Field(default=16000, description="Sample rate padrão")
    default_bitrate: str = Field(default="64k", description="Bitrate padrão")
    noise_reduction_strength: float = Field(default=0.8, ge=0.1, le=1.0)
    
    @validator('allowed_formats')
    def validate_formats(cls, v):
        """Valida formatos de arquivo"""
        valid_formats = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wma'}
        invalid = set(v) - valid_formats
        if invalid:
            raise ValueError(f'Formatos inválidos: {invalid}')
        return v


class SecurityConfig(BaseModel):
    """Configuração de segurança"""
    rate_limit_requests: int = Field(default=100, description="Requests por minuto")
    rate_limit_window: int = Field(default=60, description="Janela de rate limiting")
    enable_file_content_validation: bool = Field(default=True)
    enable_virus_scan: bool = Field(default=False, description="Scan de vírus (requer ClamAV)")
    max_upload_attempts: int = Field(default=3, description="Tentativas máximas de upload")
    
    # Validação de conteúdo
    validate_audio_headers: bool = Field(default=True)
    check_file_entropy: bool = Field(default=True, description="Detecta arquivos suspeitos")


class MonitoringConfig(BaseModel):
    """Configuração de monitoramento e observabilidade"""
    
    # Métricas Prometheus
    enable_prometheus: bool = Field(default=True, description="Habilita métricas Prometheus")
    metrics_port: int = Field(default=9090, ge=1024, le=65535, description="Porta para métricas")
    
    # Rastreamento distribuído
    enable_tracing: bool = Field(default=True, description="Habilita rastreamento distribuído")
    jaeger_endpoint: Optional[str] = Field(default=None, description="Endpoint Jaeger")
    trace_sampling_ratio: float = Field(default=1.0, ge=0.0, le=1.0, description="Taxa de amostragem")
    
    # Logging estruturado
    log_correlation_id: bool = Field(default=True, description="Habilita correlation ID")
    structured_logging: bool = Field(default=True, description="Habilita logging JSON")
    enable_performance_logging: bool = Field(default=True, description="Logging de performance")
    
    # Health checks
    health_check_interval: int = Field(default=30, ge=5, le=300, description="Intervalo de health check")
    enable_baggage_propagation: bool = Field(default=True, description="Propagação de baggage")


class AppSettings(BaseSettings):
    """Configurações principais da aplicação"""
    
    # Aplicação
    app_name: str = Field(default="Audio Normalization Service")
    version: str = Field(default="2.0.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    
    # Servidor
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001, ge=1024, le=65535)
    workers: int = Field(default=1, ge=1, le=8)
    
    # Diretórios
    upload_dir: Path = Field(default=Path("./uploads"))
    processed_dir: Path = Field(default=Path("./processed"))
    temp_dir: Path = Field(default=Path("./temp"))
    log_dir: Path = Field(default=Path("./logs"))
    backup_dir: Path = Field(default=Path("./backup"))
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    log_rotation: str = Field(default="1 day")
    log_retention: str = Field(default="30 days")
    
    # Configurações específicas
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        env_nested_delimiter = '__'
        case_sensitive = False
        
    @validator('upload_dir', 'processed_dir', 'temp_dir', 'log_dir', 'backup_dir')
    def create_directories(cls, v):
        """Cria diretórios se não existirem"""
        if isinstance(v, str):
            v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    def get_redis_url(self) -> str:
        """Retorna URL do Redis com fallbacks"""
        # Prioridade: variável de ambiente > configuração > padrão
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            return redis_url
            
        return self.database.url
    
    def validate_config(self) -> Dict[str, Any]:
        """Valida toda a configuração e retorna relatório"""
        errors = []
        warnings = []
        
        # Valida Redis
        try:
            import redis
            client = redis.from_url(self.get_redis_url())
            client.ping()
        except Exception as e:
            errors.append(f"Redis não acessível: {e}")
        
        # Valida diretórios
        for dir_name, dir_path in [
            ('upload', self.upload_dir),
            ('processed', self.processed_dir),
            ('temp', self.temp_dir),
            ('log', self.log_dir)
        ]:
            if not dir_path.exists():
                errors.append(f"Diretório {dir_name} não existe: {dir_path}")
            elif not os.access(dir_path, os.W_OK):
                errors.append(f"Sem permissão de escrita: {dir_path}")
        
        # Valida dependências
        try:
            import pydub, noisereduce, librosa
        except ImportError as e:
            errors.append(f"Dependência faltando: {e}")
        
        # Warnings para configurações de produção
        if self.environment == "production":
            if self.debug:
                warnings.append("Debug habilitado em produção")
            if self.log_level == "DEBUG":
                warnings.append("Log level DEBUG em produção")
            if not self.monitoring.enable_prometheus:
                warnings.append("Métricas desabilitadas em produção")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "config_summary": {
                "redis_url": self.get_redis_url(),
                "cache_ttl_hours": self.cache.ttl_hours,
                "max_file_size_mb": self.processing.max_file_size_mb,
                "rate_limit": self.security.rate_limit_requests,
                "monitoring_enabled": self.monitoring.enable_prometheus
            }
        }


# Instância global de configuração
def get_settings() -> AppSettings:
    """Factory para configuração singleton"""
    return AppSettings()


# Inicialização com validação
def initialize_config() -> AppSettings:
    """Inicializa e valida configuração"""
    settings = get_settings()
    validation_result = settings.validate_config()
    
    if not validation_result["valid"]:
        logger.error("Configuração inválida:")
        for error in validation_result["errors"]:
            logger.error(f"  - {error}")
        raise RuntimeError("Falha na validação de configuração")
    
    # Log de warnings
    for warning in validation_result["warnings"]:
        logger.warning(f"⚠️  {warning}")
    
    logger.info("✅ Configuração validada com sucesso")
    logger.info(f"📊 Cache TTL: {settings.cache.ttl_hours}h")
    logger.info(f"📁 Max file size: {settings.processing.max_file_size_mb}MB")
    logger.info(f"🚦 Rate limit: {settings.security.rate_limit_requests}/min")
    
    return settings