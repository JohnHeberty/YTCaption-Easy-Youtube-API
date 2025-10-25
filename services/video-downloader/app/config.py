"""
Configuração empresarial para Video Downloader Service
Sistema hierárquico com Pydantic e validação robusta
"""
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field, validator, root_validator
from pydantic_settings import BaseSettings


class ServerConfig(BaseModel):
    """Configurações do servidor"""
    host: str = Field(default="0.0.0.0", description="Host do servidor")
    port: int = Field(default=8003, ge=1024, le=65535, description="Porta do servidor")
    workers: int = Field(default=1, ge=1, le=8, description="Número de workers")
    reload: bool = Field(default=False, description="Auto-reload em desenvolvimento")
    
    @validator('workers')
    def validate_workers(cls, v):
        """Limita workers baseado em CPU disponível"""
        import multiprocessing
        max_workers = multiprocessing.cpu_count()
        return min(v, max_workers)


class DatabaseConfig(BaseModel):
    """Configurações do banco de dados/Redis"""
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="URL de conexão do Redis"
    )
    connection_pool_size: int = Field(default=10, ge=1, le=50)
    socket_timeout: float = Field(default=5.0, ge=1.0, le=30.0)
    socket_connect_timeout: float = Field(default=5.0, ge=1.0, le=30.0)
    retry_on_timeout: bool = Field(default=True)
    
    @validator('redis_url')
    def validate_redis_url(cls, v):
        """Valida formato da URL Redis"""
        if not v.startswith(('redis://', 'rediss://')):
            raise ValueError("Redis URL must start with redis:// or rediss://")
        return v


class CacheConfig(BaseModel):
    """Configurações do cache"""
    ttl_hours: int = Field(default=24, ge=1, le=168, description="TTL em horas")
    max_file_size_gb: float = Field(default=5.0, ge=0.1, le=50.0, description="Tamanho máximo por arquivo (GB)")
    max_total_cache_gb: float = Field(default=100.0, ge=1.0, le=1000.0, description="Cache total máximo (GB)")
    cleanup_interval_minutes: int = Field(default=60, ge=5, le=1440, description="Intervalo de limpeza")
    cache_dir: str = Field(default="./cache", description="Diretório de cache")
    
    @validator('cache_dir')
    def validate_cache_dir(cls, v):
        """Garante que diretório de cache existe"""
        Path(v).mkdir(parents=True, exist_ok=True)
        return v


class DownloadConfig(BaseModel):
    """Configurações de download"""
    
    # Limites gerais
    max_concurrent_downloads: int = Field(default=3, ge=1, le=10, description="Downloads simultâneos")
    max_file_size_gb: float = Field(default=5.0, ge=0.1, le=20.0, description="Tamanho máximo de arquivo")
    download_timeout_seconds: int = Field(default=3600, ge=60, le=7200, description="Timeout de download")
    
    # Formatos e qualidades
    supported_qualities: List[str] = Field(
        default=["best", "720p", "480p", "360p", "240p", "audio"],
        description="Qualidades suportadas"
    )
    default_quality: str = Field(default="best", description="Qualidade padrão")
    preferred_formats: List[str] = Field(
        default=["mp4", "webm", "mkv"],
        description="Formatos preferenciais"
    )
    
    # User Agent management
    user_agents_file: str = Field(default="user-agents.txt", description="Arquivo de User-Agents")
    ua_quarantine_hours: int = Field(default=48, ge=1, le=168, description="Horas de quarentena UA")
    ua_max_errors: int = Field(default=3, ge=1, le=10, description="Máximo erros por UA")
    ua_rotation_enabled: bool = Field(default=True, description="Rotação automática de UA")
    
    # Retry e resiliência
    max_retries: int = Field(default=3, ge=1, le=5, description="Tentativas máximas")
    retry_delay_seconds: float = Field(default=2.0, ge=0.5, le=10.0, description="Delay entre tentativas")
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0, description="Multiplicador de backoff")
    
    # Bandwidth e performance
    rate_limit_mbps: Optional[float] = Field(default=None, ge=1.0, le=1000.0, description="Limite de banda (Mbps)")
    chunk_size_kb: int = Field(default=1024, ge=64, le=8192, description="Tamanho do chunk (KB)")
    
    @validator('default_quality')
    def validate_default_quality(cls, v, values):
        """Valida que qualidade padrão está na lista suportada"""
        if 'supported_qualities' in values and v not in values['supported_qualities']:
            raise ValueError(f"Default quality '{v}' not in supported qualities")
        return v
    
    @validator('user_agents_file')
    def validate_user_agents_file(cls, v):
        """Verifica se arquivo de User-Agents existe"""
        if not Path(v).exists():
            raise ValueError(f"User agents file '{v}' not found")
        return v


class SecurityConfig(BaseModel):
    """Configurações de segurança"""
    
    # Rate limiting
    rate_limit_per_minute: int = Field(default=30, ge=1, le=1000, description="Requests por minuto por IP")
    rate_limit_window_seconds: int = Field(default=60, ge=10, le=3600, description="Janela de rate limit")
    
    # URL validation
    allowed_domains: List[str] = Field(
        default=["youtube.com", "youtu.be", "m.youtube.com"],
        description="Domínios permitidos"
    )
    blocked_domains: List[str] = Field(default=[], description="Domínios bloqueados")
    max_url_length: int = Field(default=2048, ge=100, le=8192, description="Tamanho máximo de URL")
    
    # File validation
    scan_downloads: bool = Field(default=True, description="Escanear downloads")
    max_scan_size_mb: int = Field(default=100, ge=1, le=1000, description="Tamanho máximo para scan")
    
    # Headers de segurança
    enable_security_headers: bool = Field(default=True, description="Habilitar headers de segurança")
    cors_origins: List[str] = Field(default=["*"], description="Origins CORS permitidas")
    
    @validator('allowed_domains')
    def validate_domains(cls, v):
        """Valida formato dos domínios"""
        for domain in v:
            if not domain or '://' in domain:
                raise ValueError(f"Invalid domain format: {domain}")
        return v


class MonitoringConfig(BaseModel):
    """Configurações de monitoramento"""
    
    # Métricas
    enable_metrics: bool = Field(default=True, description="Habilitar métricas Prometheus")
    metrics_port: int = Field(default=9090, ge=1024, le=65535, description="Porta das métricas")
    metrics_path: str = Field(default="/metrics", description="Path das métricas")
    
    # Health checks
    health_check_interval_seconds: int = Field(default=30, ge=5, le=300, description="Intervalo health check")
    health_check_timeout_seconds: float = Field(default=5.0, ge=1.0, le=30.0, description="Timeout health check")
    
    # Tracing
    enable_tracing: bool = Field(default=True, description="Habilitar distributed tracing")
    tracing_endpoint: Optional[str] = Field(default=None, description="Endpoint do tracing")
    tracing_service_name: str = Field(default="video-downloader", description="Nome do serviço no tracing")
    
    # Logging
    log_level: str = Field(default="INFO", description="Nível de log")
    log_format: str = Field(default="json", description="Formato do log (json/text)")
    enable_performance_logging: bool = Field(default=True, description="Log de performance")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Valida nível de log"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()


class CeleryConfig(BaseModel):
    """Configurações do Celery"""
    broker_url: str = Field(default="redis://localhost:6379/1", description="URL do broker")
    result_backend: str = Field(default="redis://localhost:6379/1", description="Backend de resultados")
    task_serializer: str = Field(default="json", description="Serializer de tasks")
    result_serializer: str = Field(default="json", description="Serializer de resultados")
    
    # Configurações de worker
    worker_prefetch_multiplier: int = Field(default=1, ge=1, le=10, description="Prefetch multiplier")
    task_acks_late: bool = Field(default=True, description="Acks tardios")
    worker_max_tasks_per_child: int = Field(default=100, ge=10, le=1000, description="Max tasks por child")
    
    # Timeouts
    task_soft_time_limit: int = Field(default=3600, ge=60, le=7200, description="Soft timeout")
    task_time_limit: int = Field(default=3900, ge=120, le=7500, description="Hard timeout")
    
    # Retry
    task_default_max_retries: int = Field(default=3, ge=0, le=10, description="Retries padrão")
    task_default_retry_delay: int = Field(default=60, ge=10, le=600, description="Delay de retry")


class AppSettings(BaseSettings):
    """Configurações principais da aplicação"""
    
    # Informações básicas
    app_name: str = Field(default="Video Downloader Service", description="Nome da aplicação")
    version: str = Field(default="2.0.0", description="Versão da aplicação")
    debug: bool = Field(default=False, description="Modo debug")
    environment: str = Field(default="development", description="Ambiente (development/staging/production)")
    
    # Configurações aninhadas
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    celery: CeleryConfig = Field(default_factory=CeleryConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False
    
    @root_validator
    def validate_settings(cls, values):
        """Validações cruzadas entre configurações"""
        
        # Valida que cache e download limits são consistentes
        cache_config = values.get('cache')
        download_config = values.get('download')
        
        if cache_config and download_config:
            if download_config.max_file_size_gb > cache_config.max_file_size_gb:
                raise ValueError(
                    "Download max file size cannot be larger than cache max file size"
                )
        
        # Valida ambiente vs debug
        environment = values.get('environment', 'development')
        debug = values.get('debug', False)
        
        if environment == 'production' and debug:
            raise ValueError("Debug mode should not be enabled in production")
        
        return values
    
    def get_redis_config(self) -> Dict[str, Any]:
        """Retorna configuração Redis formatada"""
        return {
            "url": self.database.redis_url,
            "connection_pool_kwargs": {
                "max_connections": self.database.connection_pool_size,
                "socket_timeout": self.database.socket_timeout,
                "socket_connect_timeout": self.database.socket_connect_timeout,
                "retry_on_timeout": self.database.retry_on_timeout
            }
        }
    
    def get_ydl_base_opts(self) -> Dict[str, Any]:
        """Retorna opções base para yt-dlp"""
        return {
            'noplaylist': True,
            'extractaudio': False,
            'writeinfojson': False,
            'writedescription': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': False,
            'socket_timeout': self.download.download_timeout_seconds,
            'retries': self.download.max_retries
        }
    
    def get_cors_config(self) -> Dict[str, Any]:
        """Retorna configuração CORS"""
        return {
            "allow_origins": self.security.cors_origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"],
        }
    
    def is_url_allowed(self, url: str) -> bool:
        """Verifica se URL é permitida"""
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. se presente
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Verifica domínios bloqueados
            if domain in self.security.blocked_domains:
                return False
            
            # Verifica domínios permitidos
            return any(
                domain == allowed or domain.endswith(f'.{allowed}')
                for allowed in self.security.allowed_domains
            )
            
        except Exception:
            return False


# Singleton settings
_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """
    Retorna instância singleton das configurações
    
    Returns:
        Configurações da aplicação
    """
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


def reload_settings() -> AppSettings:
    """
    Força recarregamento das configurações
    
    Returns:
        Nova instância das configurações
    """
    global _settings
    _settings = AppSettings()
    return _settings


# Configurações para diferentes ambientes
class DevelopmentSettings(AppSettings):
    """Configurações para desenvolvimento"""
    debug: bool = True
    environment: str = "development"
    
    class Config:
        env_file = ".env.development"


class ProductionSettings(AppSettings):
    """Configurações para produção"""
    debug: bool = False
    environment: str = "production"
    
    # Override para produção
    server: ServerConfig = Field(
        default_factory=lambda: ServerConfig(
            host="0.0.0.0",
            port=8003,
            workers=4,
            reload=False
        )
    )
    
    monitoring: MonitoringConfig = Field(
        default_factory=lambda: MonitoringConfig(
            log_level="INFO",
            enable_metrics=True,
            enable_tracing=True
        )
    )
    
    class Config:
        env_file = ".env.production"


def get_settings_for_environment(env: str) -> AppSettings:
    """
    Retorna configurações específicas para ambiente
    
    Args:
        env: Nome do ambiente (development, production, testing)
        
    Returns:
        Configurações do ambiente
    """
    if env.lower() == "development":
        return DevelopmentSettings()
    elif env.lower() == "production":
        return ProductionSettings()
    else:
        return AppSettings()