"""
Base settings with validation using Pydantic
"""
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional
from pathlib import Path


class RedisSettings(BaseSettings):
    """Configurações Redis padronizadas"""
    
    redis_url: str = Field(..., env='REDIS_URL')
    redis_max_connections: int = Field(default=50, env='REDIS_MAX_CONNECTIONS')
    redis_socket_timeout: int = Field(default=10, env='REDIS_SOCKET_TIMEOUT')
    redis_socket_connect_timeout: int = Field(default=5, env='REDIS_SOCKET_CONNECT_TIMEOUT')
    redis_retry_on_timeout: bool = Field(default=True, env='REDIS_RETRY_ON_TIMEOUT')
    redis_health_check_interval: int = Field(default=30, env='REDIS_HEALTH_CHECK_INTERVAL')
    
    # Circuit breaker
    redis_circuit_breaker_enabled: bool = Field(default=True, env='REDIS_CIRCUIT_BREAKER_ENABLED')
    redis_circuit_breaker_max_failures: int = Field(default=5, env='REDIS_CIRCUIT_BREAKER_MAX_FAILURES')
    redis_circuit_breaker_timeout: int = Field(default=60, env='REDIS_CIRCUIT_BREAKER_TIMEOUT')
    
    class Config:
        env_file = '.env'
        case_sensitive = False


class CelerySettings(BaseSettings):
    """Configurações Celery padronizadas"""
    
    celery_broker_url: Optional[str] = Field(default=None, env='CELERY_BROKER_URL')
    celery_result_backend: Optional[str] = Field(default=None, env='CELERY_RESULT_BACKEND')
    celery_task_serializer: str = Field(default='json', env='CELERY_TASK_SERIALIZER')
    celery_result_serializer: str = Field(default='json', env='CELERY_RESULT_SERIALIZER')
    celery_accept_content: str = Field(default='json', env='CELERY_ACCEPT_CONTENT')
    celery_timezone: str = Field(default='UTC', env='CELERY_TIMEZONE')
    celery_enable_utc: bool = Field(default=True, env='CELERY_ENABLE_UTC')
    celery_task_track_started: bool = Field(default=True, env='CELERY_TASK_TRACK_STARTED')
    celery_task_time_limit: int = Field(default=1800, env='CELERY_TASK_TIME_LIMIT')
    celery_task_soft_time_limit: int = Field(default=1500, env='CELERY_TASK_SOFT_TIME_LIMIT')
    celery_worker_prefetch_multiplier: int = Field(default=1, env='CELERY_WORKER_PREFETCH_MULTIPLIER')
    celery_worker_max_tasks_per_child: int = Field(default=100, env='CELERY_WORKER_MAX_TASKS_PER_CHILD')
    
    @validator('celery_broker_url', always=True)
    def set_broker_from_redis(cls, v, values):
        """Se broker não definido, usa Redis URL"""
        if v is None and 'redis_url' in values:
            return values.get('redis_url')
        return v
    
    @validator('celery_result_backend', always=True)
    def set_backend_from_redis(cls, v, values):
        """Se backend não definido, usa Redis URL"""
        if v is None and 'redis_url' in values:
            return values.get('redis_url')
        return v
    
    class Config:
        env_file = '.env'
        case_sensitive = False


class LoggingSettings(BaseSettings):
    """Configurações de logging padronizadas"""
    
    log_level: str = Field(default='INFO', env='LOG_LEVEL')
    log_dir: str = Field(default='./logs', env='LOG_DIR')
    log_format: str = Field(default='json', env='LOG_FORMAT')  # 'json' ou 'text'
    log_to_console: bool = Field(default=True, env='LOG_TO_CONSOLE')
    log_to_file: bool = Field(default=True, env='LOG_TO_FILE')
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Valida log level"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v_upper
    
    @validator('log_format')
    def validate_log_format(cls, v):
        """Valida log format"""
        valid_formats = ['json', 'text']
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f'log_format must be one of {valid_formats}')
        return v_lower
    
    class Config:
        env_file = '.env'
        case_sensitive = False


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
    
    # Aplicação
    app_name: str = Field(..., env='APP_NAME')
    app_version: str = Field(default='1.0.0', env='APP_VERSION')
    environment: str = Field(default='production', env='ENVIRONMENT')
    debug: bool = Field(default=False, env='DEBUG')
    
    # Servidor
    host: str = Field(default='0.0.0.0', env='HOST')
    port: int = Field(default=8000, env='PORT')
    workers: int = Field(default=1, env='WORKERS')
    
    # Redis (herdado)
    redis_url: str = Field(..., env='REDIS_URL')
    redis_max_connections: int = Field(default=50, env='REDIS_MAX_CONNECTIONS')
    
    # Cache
    cache_ttl_hours: int = Field(default=24, env='CACHE_TTL_HOURS')
    cache_cleanup_interval_minutes: int = Field(default=30, env='CACHE_CLEANUP_INTERVAL_MINUTES')
    
    # Limits
    max_file_size_mb: int = Field(default=500, env='MAX_FILE_SIZE_MB')
    max_concurrent_jobs: int = Field(default=3, env='MAX_CONCURRENT_JOBS')
    job_timeout_minutes: int = Field(default=60, env='JOB_TIMEOUT_MINUTES')
    
    # Diretórios
    upload_dir: str = Field(default='./uploads', env='UPLOAD_DIR')
    processed_dir: str = Field(default='./processed', env='PROCESSED_DIR')
    temp_dir: str = Field(default='./temp', env='TEMP_DIR')
    log_dir: str = Field(default='./logs', env='LOG_DIR')
    
    # Logging
    log_level: str = Field(default='INFO', env='LOG_LEVEL')
    log_format: str = Field(default='json', env='LOG_FORMAT')
    
    @validator('environment')
    def validate_environment(cls, v):
        """Valida environment"""
        valid_envs = ['development', 'staging', 'production']
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f'environment must be one of {valid_envs}')
        return v_lower
    
    @validator('port')
    def validate_port(cls, v):
        """Valida port"""
        if not (1 <= v <= 65535):
            raise ValueError('port must be between 1 and 65535')
        return v
    
    @validator('workers')
    def validate_workers(cls, v):
        """Valida workers"""
        if v < 1:
            raise ValueError('workers must be at least 1')
        return v
    
    @validator('cache_ttl_hours')
    def validate_cache_ttl(cls, v):
        """Valida cache TTL"""
        if v < 1:
            raise ValueError('cache_ttl_hours must be at least 1')
        return v
    
    @validator('max_file_size_mb')
    def validate_max_file_size(cls, v):
        """Valida max file size"""
        if v < 1:
            raise ValueError('max_file_size_mb must be at least 1')
        return v
    
    def create_directories(self):
        """Cria diretórios necessários"""
        for dir_path in [
            self.upload_dir,
            self.processed_dir,
            self.temp_dir,
            self.log_dir
        ]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    class Config:
        env_file = '.env'
        case_sensitive = False
        extra = 'allow'  # Permite campos extras para extensões
    
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
