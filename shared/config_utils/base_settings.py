"""
Base settings with validation using Pydantic v2
"""
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path


class RedisSettings(BaseSettings):
    """Configurações Redis padronizadas"""

    model_config = SettingsConfigDict(env_file='.env', case_sensitive=False)

    redis_url: str = Field(...)
    redis_max_connections: int = Field(default=50)
    redis_socket_timeout: int = Field(default=10)
    redis_socket_connect_timeout: int = Field(default=5)
    redis_retry_on_timeout: bool = Field(default=True)
    redis_health_check_interval: int = Field(default=30)

    # Circuit breaker
    redis_circuit_breaker_enabled: bool = Field(default=True)
    redis_circuit_breaker_max_failures: int = Field(default=5)
    redis_circuit_breaker_timeout: int = Field(default=60)


class CelerySettings(BaseSettings):
    """Configurações Celery padronizadas.

    If broker/backend are not set, they fall back to ``redis_url`` at the
    BaseServiceSettings level (not here, since this sub-model doesn't have it).
    """

    model_config = SettingsConfigDict(env_file='.env', case_sensitive=False)

    celery_broker_url: Optional[str] = Field(default=None)
    celery_result_backend: Optional[str] = Field(default=None)
    celery_task_serializer: str = Field(default='json')
    celery_result_serializer: str = Field(default='json')
    celery_accept_content: str = Field(default='json')
    celery_timezone: str = Field(default='UTC')
    celery_enable_utc: bool = Field(default=True)
    celery_task_track_started: bool = Field(default=True)
    celery_task_time_limit: int = Field(default=1800)
    celery_task_soft_time_limit: int = Field(default=1500)
    celery_worker_prefetch_multiplier: int = Field(default=1)
    celery_worker_max_tasks_per_child: int = Field(default=100)


class LoggingSettings(BaseSettings):
    """Configurações de logging padronizadas"""

    model_config = SettingsConfigDict(env_file='.env', case_sensitive=False)

    log_level: str = Field(default='INFO')
    log_dir: str = Field(default='./data/logs')
    log_format: str = Field(default='json')  # 'json' ou 'text'
    log_to_console: bool = Field(default=True)
    log_to_file: bool = Field(default=True)

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        """Valida log level"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v_upper

    @field_validator('log_format')
    @classmethod
    def validate_log_format(cls, v):
        """Valida log format"""
        valid_formats = ['json', 'text']
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f'log_format must be one of {valid_formats}')
        return v_lower


class BaseServiceSettings(BaseSettings):
    """
    Configuração base para todos os microserviços.

    Inclui configurações comuns como:
    - Informações da aplicação
    - Redis
    - Celery
    - Logging
    - Cache
    - Diretórios

    Cada serviço pode estender esta classe.
    """

    model_config = SettingsConfigDict(
        env_file='.env',
        case_sensitive=False,
        extra='allow',  # Permite campos extras para extensões
    )

    # Aplicação
    app_name: str = Field(...)
    app_version: str = Field(default='1.0.0')
    environment: str = Field(default='production')
    debug: bool = Field(default=False)

    # Servidor
    host: str = Field(default='0.0.0.0')
    port: int = Field(default=8000)
    workers: int = Field(default=1)

    # Redis (herdado)
    redis_url: str = Field(...)
    redis_max_connections: int = Field(default=50)

    # Cache
    cache_ttl_hours: int = Field(default=24)
    cache_cleanup_interval_minutes: int = Field(default=30)

    # Limits
    max_file_size_mb: int = Field(default=500)
    max_concurrent_jobs: int = Field(default=3)
    job_timeout_minutes: int = Field(default=60)

    # Diretórios
    upload_dir: str = Field(default='./data/uploads')
    processed_dir: str = Field(default='./data/processed')
    temp_dir: str = Field(default='./data/temp')
    log_dir: str = Field(default='./data/logs')

    # Logging
    log_level: str = Field(default='INFO')
    log_format: str = Field(default='json')

    # Celery (fallback para redis_url)
    celery_broker_url: Optional[str] = Field(default=None)
    celery_result_backend: Optional[str] = Field(default=None)

    # API Key (autenticacao)
    api_key: Optional[str] = Field(default=None)

    # Timezone
    tz: str = Field(default='America/Sao_Paulo')

    # Output
    output_dir: str = Field(default='./data/outputs')

    # Divisor (porta Redis DB = DIVISOR)
    divisor: Optional[int] = Field(default=None)

    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v):
        """Valida environment"""
        valid_envs = ['development', 'staging', 'production']
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f'environment must be one of {valid_envs}')
        return v_lower

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        """Valida port"""
        if not (1 <= v <= 65535):
            raise ValueError('port must be between 1 and 65535')
        return v

    @field_validator('workers')
    @classmethod
    def validate_workers(cls, v):
        """Valida workers"""
        if v < 1:
            raise ValueError('workers must be at least 1')
        return v

    @model_validator(mode='after')
    def set_celery_defaults_from_redis(self):
        """Fallback: se broker/backend não definido, usa redis_url."""
        if self.celery_broker_url is None:
            self.celery_broker_url = self.redis_url
        if self.celery_result_backend is None:
            self.celery_result_backend = self.redis_url
        return self

    @field_validator('cache_ttl_hours')
    @classmethod
    def validate_cache_ttl(cls, v):
        """Valida cache TTL"""
        if v < 1:
            raise ValueError('cache_ttl_hours must be at least 1')
        return v

    @field_validator('max_file_size_mb')
    @classmethod
    def validate_max_file_size(cls, v):
        """Valida max file size"""
        if v < 1:
            raise ValueError('max_file_size_mb must be at least 1')
        return v

    def create_directories(self):
        """Cria diretórios necessários.

        NOTE: Side-effect removed from settings constructor. Call explicitly
        in lifespan/startup.
        """
        for dir_path in [
            self.upload_dir,
            self.processed_dir,
            self.temp_dir,
            self.log_dir,
            self.output_dir,
        ]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    def get_redis_settings(self) -> RedisSettings:
        """Retorna configurações Redis"""
        return RedisSettings(
            redis_url=self.redis_url,
            redis_max_connections=self.redis_max_connections
        )

    def get_logging_settings(self) -> LoggingSettings:
        """Retorna configurações de logging"""
        return LoggingSettings(
            log_level=self.log_level,
            log_dir=self.log_dir,
            log_format=self.log_format
        )
