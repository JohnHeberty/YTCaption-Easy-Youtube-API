"""
YouTube Download Metrics for Prometheus (v3.0)

Métricas específicas para monitorar o sistema de resiliência de downloads.
"""
from prometheus_client import Counter, Histogram, Gauge, Info
from typing import Optional
from loguru import logger


# ============= DOWNLOAD METRICS =============

# Counter: Total de tentativas de download por estratégia
youtube_downloads_total = Counter(
    'youtube_downloads_total',
    'Total YouTube download attempts',
    ['strategy', 'status']  # strategy: android_client, ios_client, etc. | status: success, error
)

# Counter: Erros de download por tipo
youtube_download_errors = Counter(
    'youtube_download_errors_total',
    'YouTube download errors by type',
    ['error_type', 'strategy']  # error_type: 403, 404, network, timeout, etc.
)

# Histogram: Duração do download
youtube_download_duration = Histogram(
    'youtube_download_duration_seconds',
    'Time spent downloading YouTube videos',
    ['strategy'],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 900)  # 1s até 15min
)

# Histogram: Tamanho do arquivo baixado
youtube_download_size_bytes = Histogram(
    'youtube_download_size_bytes',
    'Size of downloaded YouTube videos',
    buckets=(1e6, 5e6, 10e6, 50e6, 100e6, 500e6, 1e9, 5e9)  # 1MB até 5GB
)


# ============= STRATEGY METRICS =============

# Counter: Sucessos por estratégia
youtube_strategy_success = Counter(
    'youtube_strategy_success_total',
    'Successful downloads per strategy',
    ['strategy']
)

# Counter: Falhas por estratégia
youtube_strategy_failures = Counter(
    'youtube_strategy_failures_total',
    'Failed downloads per strategy',
    ['strategy']
)

# Gauge: Taxa de sucesso atual por estratégia (%)
youtube_strategy_success_rate = Gauge(
    'youtube_strategy_success_rate',
    'Current success rate per strategy (0-100)',
    ['strategy']
)


# ============= RATE LIMITING METRICS =============

# Counter: Total de requests limitados
youtube_rate_limit_hits = Counter(
    'youtube_rate_limit_hits_total',
    'Number of times rate limit was enforced',
    ['window']  # window: minute, hour
)

# Gauge: Requests no último minuto
youtube_requests_per_minute = Gauge(
    'youtube_requests_per_minute',
    'Current requests in the last minute window'
)

# Gauge: Requests na última hora
youtube_requests_per_hour = Gauge(
    'youtube_requests_per_hour',
    'Current requests in the last hour window'
)

# Histogram: Tempo de espera do rate limiter
youtube_rate_limit_wait_seconds = Histogram(
    'youtube_rate_limit_wait_seconds',
    'Time spent waiting for rate limit',
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 120, 300)  # 100ms até 5min
)

# Counter: Cooldowns ativados
youtube_cooldown_activations = Counter(
    'youtube_cooldown_activations_total',
    'Number of times cooldown was activated after errors'
)


# ============= USER-AGENT METRICS =============

# Counter: Rotações de User-Agent
youtube_user_agent_rotations = Counter(
    'youtube_user_agent_rotations_total',
    'Number of User-Agent rotations',
    ['type']  # type: random, mobile, desktop
)


# ============= PROXY METRICS =============

# Counter: Requests por proxy
youtube_proxy_requests = Counter(
    'youtube_proxy_requests_total',
    'Requests made through each proxy',
    ['proxy_type']  # proxy_type: custom, none
)

# Counter: Erros por proxy
youtube_proxy_errors = Counter(
    'youtube_proxy_errors_total',
    'Errors from proxy connections',
    ['proxy_type']
)


# ============= CIRCUIT BREAKER METRICS =============

# Gauge: Estado do circuit breaker (0=closed, 1=half-open, 2=open)
youtube_circuit_breaker_state = Gauge(
    'youtube_circuit_breaker_state',
    'Current circuit breaker state (0=closed, 1=half-open, 2=open)'
)

# Counter: Total de aberturas do circuit breaker
youtube_circuit_breaker_opens = Counter(
    'youtube_circuit_breaker_opens_total',
    'Number of times circuit breaker opened'
)


# ============= VIDEO INFO METRICS =============

# Counter: Requisições de info
youtube_info_requests = Counter(
    'youtube_info_requests_total',
    'YouTube video info requests',
    ['status']  # status: success, error
)

# Histogram: Duração da requisição de info
youtube_info_duration = Histogram(
    'youtube_info_duration_seconds',
    'Time spent fetching YouTube video info',
    buckets=(0.5, 1, 2, 5, 10, 30, 60)  # 500ms até 1min
)


# ============= CONFIGURATION INFO =============

# Info: Configuração atual do sistema v3.0
youtube_resilience_info = Info(
    'youtube_resilience_config',
    'Current YouTube Resilience v3.0 configuration'
)


# ============= HELPER FUNCTIONS =============

def record_download_attempt(strategy: str, success: bool, duration: float, size_bytes: Optional[int] = None):
    """
    Registra uma tentativa de download.
    
    Args:
        strategy: Nome da estratégia usada
        success: Se o download foi bem-sucedido
        duration: Duração em segundos
        size_bytes: Tamanho do arquivo (se sucesso)
    """
    status = 'success' if success else 'error'
    youtube_downloads_total.labels(strategy=strategy, status=status).inc()
    youtube_download_duration.labels(strategy=strategy).observe(duration)
    
    if success:
        youtube_strategy_success.labels(strategy=strategy).inc()
        if size_bytes:
            youtube_download_size_bytes.observe(size_bytes)
    else:
        youtube_strategy_failures.labels(strategy=strategy).inc()


def record_download_error(error_type: str, strategy: str):
    """
    Registra um erro de download.
    
    Args:
        error_type: Tipo do erro (403, 404, network, timeout, etc.)
        strategy: Nome da estratégia
    """
    youtube_download_errors.labels(error_type=error_type, strategy=strategy).inc()


def record_rate_limit_wait(window: str, wait_seconds: float):
    """
    Registra espera do rate limiter.
    
    Args:
        window: Janela que causou a espera (minute, hour)
        wait_seconds: Tempo de espera
    """
    youtube_rate_limit_hits.labels(window=window).inc()
    youtube_rate_limit_wait_seconds.observe(wait_seconds)


def update_rate_limit_gauges(per_minute: int, per_hour: int):
    """
    Atualiza gauges de rate limiting.
    
    Args:
        per_minute: Requests no último minuto
        per_hour: Requests na última hora
    """
    youtube_requests_per_minute.set(per_minute)
    youtube_requests_per_hour.set(per_hour)


def record_user_agent_rotation(rotation_type: str = 'random'):
    """
    Registra rotação de User-Agent.
    
    Args:
        rotation_type: Tipo de rotação (random, mobile, desktop)
    """
    youtube_user_agent_rotations.labels(type=rotation_type).inc()


def record_proxy_request(proxy_type: str, success: bool):
    """
    Registra uso de proxy.
    
    Args:
        proxy_type: Tipo do proxy (tor, custom, none)
        success: Se a requisição foi bem-sucedida
    """
    youtube_proxy_requests.labels(proxy_type=proxy_type).inc()
    if not success:
        youtube_proxy_errors.labels(proxy_type=proxy_type).inc()


def record_info_request(success: bool, duration: float):
    """
    Registra requisição de info do vídeo.
    
    Args:
        success: Se foi bem-sucedida
        duration: Duração em segundos
    """
    status = 'success' if success else 'error'
    youtube_info_requests.labels(status=status).inc()
    youtube_info_duration.observe(duration)


def set_resilience_config(config: dict):
    """
    Define informações de configuração.
    
    Args:
        config: Dicionário com configurações
    """
    youtube_resilience_info.info(config)
    logger.info("📊 Prometheus metrics configured for YouTube Resilience v3.0")


# Initialize on import
logger.info("✅ YouTube Resilience v3.0 metrics initialized")
