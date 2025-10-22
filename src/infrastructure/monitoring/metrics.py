"""
Prometheus Metrics Collector.

v2.2: Custom metrics para observabilidade completa da API.

Métricas disponíveis:
- transcription_requests_total: Counter de requisições por status
- transcription_duration_seconds: Histogram de duração de transcrições
- cache_hit_rate: Gauge de taxa de cache hits (0-1)
- worker_pool_queue_size: Gauge de tamanho da fila de workers
- circuit_breaker_state: Gauge de estado do circuit breaker (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
- model_loading_duration_seconds: Histogram de tempo de carregamento de modelos
"""
from typing import Optional, Dict
from prometheus_client import Counter, Histogram, Gauge, Info
from loguru import logger
from enum import Enum


class CircuitBreakerState(Enum):
    """Estados do Circuit Breaker para métricas."""
    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2


# ===========================
# MÉTRICAS DE TRANSCRIÇÃO
# ===========================

transcription_requests_counter = Counter(
    name='transcription_requests_total',
    documentation='Total de requisições de transcrição',
    labelnames=['status', 'model', 'language']
)

transcription_duration_histogram = Histogram(
    name='transcription_duration_seconds',
    documentation='Duração das transcrições em segundos',
    labelnames=['model', 'language', 'status'],
    buckets=[10, 30, 60, 120, 300, 600, 1200, 1800, 3600]  # 10s até 1h
)

video_duration_histogram = Histogram(
    name='video_duration_seconds',
    documentation='Duração dos vídeos processados',
    labelnames=['status'],
    buckets=[30, 60, 180, 300, 600, 1800, 3600, 7200, 10800]  # 30s até 3h
)


# ===========================
# MÉTRICAS DE CACHE
# ===========================

cache_hit_rate_gauge = Gauge(
    name='cache_hit_rate',
    documentation='Taxa de cache hits (0.0 - 1.0)',
    labelnames=['cache_type']  # 'model', 'transcription'
)

cache_size_gauge = Gauge(
    name='cache_size_bytes',
    documentation='Tamanho do cache em bytes',
    labelnames=['cache_type']
)

cache_entries_gauge = Gauge(
    name='cache_entries_total',
    documentation='Número de entradas no cache',
    labelnames=['cache_type']
)


# ===========================
# MÉTRICAS DE WORKER POOL
# ===========================

worker_pool_queue_gauge = Gauge(
    name='worker_pool_queue_size',
    documentation='Tamanho da fila de workers paralelos',
    labelnames=['pool_name']
)

worker_pool_active_gauge = Gauge(
    name='worker_pool_active_workers',
    documentation='Número de workers ativos',
    labelnames=['pool_name']
)

worker_pool_utilization_gauge = Gauge(
    name='worker_pool_utilization',
    documentation='Utilização do worker pool (0.0 - 1.0)',
    labelnames=['pool_name']
)


# ===========================
# MÉTRICAS DE CIRCUIT BREAKER
# ===========================

circuit_breaker_state_gauge = Gauge(
    name='circuit_breaker_state',
    documentation='Estado do circuit breaker (0=CLOSED, 1=HALF_OPEN, 2=OPEN)',
    labelnames=['circuit_name']
)

circuit_breaker_failures_counter = Counter(
    name='circuit_breaker_failures_total',
    documentation='Total de falhas registradas pelo circuit breaker',
    labelnames=['circuit_name']
)

circuit_breaker_transitions_counter = Counter(
    name='circuit_breaker_state_transitions_total',
    documentation='Total de transições de estado do circuit breaker',
    labelnames=['circuit_name', 'from_state', 'to_state']
)


# ===========================
# MÉTRICAS DE MODELO WHISPER
# ===========================

model_loading_duration_histogram = Histogram(
    name='model_loading_duration_seconds',
    documentation='Tempo de carregamento do modelo Whisper',
    labelnames=['model_name', 'device'],
    buckets=[1, 5, 10, 30, 60, 120, 300]  # 1s até 5min
)

model_info = Info(
    name='whisper_model_info',
    documentation='Informações do modelo Whisper carregado'
)


# ===========================
# MÉTRICAS DE DOWNLOAD
# ===========================

download_duration_histogram = Histogram(
    name='youtube_download_duration_seconds',
    documentation='Duração do download de vídeos do YouTube',
    labelnames=['status'],
    buckets=[5, 10, 30, 60, 120, 300, 600, 900]  # 5s até 15min
)

download_size_histogram = Histogram(
    name='youtube_download_size_bytes',
    documentation='Tamanho dos vídeos baixados',
    labelnames=['status'],
    buckets=[1e6, 10e6, 50e6, 100e6, 500e6, 1e9, 2e9, 5e9]  # 1MB até 5GB
)


# ===========================
# MÉTRICAS DE API
# ===========================

api_requests_in_progress_gauge = Gauge(
    name='api_requests_in_progress',
    documentation='Número de requisições em andamento',
    labelnames=['endpoint']
)

api_errors_counter = Counter(
    name='api_errors_total',
    documentation='Total de erros da API',
    labelnames=['endpoint', 'error_type', 'status_code']
)


class MetricsCollector:
    """
    Coletor centralizado de métricas.
    
    v2.2: Fornece métodos convenientes para coletar métricas em diferentes pontos da aplicação.
    """
    
    @staticmethod
    def record_transcription_request(status: str, model: str, language: str):
        """Registra uma requisição de transcrição."""
        transcription_requests_counter.labels(
            status=status,
            model=model,
            language=language
        ).inc()
        logger.debug(f"📊 Metric recorded: transcription_request status={status} model={model} lang={language}")
    
    @staticmethod
    def record_transcription_duration(duration: float, model: str, language: str, status: str):
        """Registra a duração de uma transcrição."""
        transcription_duration_histogram.labels(
            model=model,
            language=language,
            status=status
        ).observe(duration)
        logger.debug(f"📊 Metric recorded: transcription_duration={duration:.2f}s model={model}")
    
    @staticmethod
    def record_video_duration(duration: float, status: str):
        """Registra a duração de um vídeo processado."""
        video_duration_histogram.labels(status=status).observe(duration)
    
    @staticmethod
    def update_cache_metrics(cache_type: str, hit_rate: float, size_bytes: int, entries: int):
        """Atualiza métricas de cache."""
        cache_hit_rate_gauge.labels(cache_type=cache_type).set(hit_rate)
        cache_size_gauge.labels(cache_type=cache_type).set(size_bytes)
        cache_entries_gauge.labels(cache_type=cache_type).set(entries)
        logger.debug(f"📊 Cache metrics updated: {cache_type} hit_rate={hit_rate:.2%} entries={entries}")
    
    @staticmethod
    def update_worker_pool_metrics(pool_name: str, queue_size: int, active_workers: int, max_workers: int):
        """Atualiza métricas do worker pool."""
        worker_pool_queue_gauge.labels(pool_name=pool_name).set(queue_size)
        worker_pool_active_gauge.labels(pool_name=pool_name).set(active_workers)
        utilization = active_workers / max_workers if max_workers > 0 else 0
        worker_pool_utilization_gauge.labels(pool_name=pool_name).set(utilization)
        logger.debug(f"📊 Worker pool metrics: {pool_name} queue={queue_size} active={active_workers}/{max_workers}")
    
    @staticmethod
    def update_circuit_breaker_state(circuit_name: str, state: CircuitBreakerState):
        """Atualiza o estado do circuit breaker."""
        circuit_breaker_state_gauge.labels(circuit_name=circuit_name).set(state.value)
        logger.debug(f"📊 Circuit breaker state: {circuit_name} = {state.name}")
    
    @staticmethod
    def record_circuit_breaker_failure(circuit_name: str):
        """Registra uma falha no circuit breaker."""
        circuit_breaker_failures_counter.labels(circuit_name=circuit_name).inc()
    
    @staticmethod
    def record_circuit_breaker_transition(circuit_name: str, from_state: str, to_state: str):
        """Registra uma transição de estado do circuit breaker."""
        circuit_breaker_transitions_counter.labels(
            circuit_name=circuit_name,
            from_state=from_state,
            to_state=to_state
        ).inc()
        logger.info(f"📊 Circuit breaker transition: {circuit_name} {from_state} -> {to_state}")
    
    @staticmethod
    def record_model_loading(duration: float, model_name: str, device: str):
        """Registra o tempo de carregamento de um modelo."""
        model_loading_duration_histogram.labels(
            model_name=model_name,
            device=device
        ).observe(duration)
        logger.info(f"📊 Model loading: {model_name} on {device} took {duration:.2f}s")
    
    @staticmethod
    def set_model_info(model_name: str, device: str, parameters: Optional[str] = None):
        """Define informações do modelo carregado."""
        info_dict = {
            'model_name': model_name,
            'device': device
        }
        if parameters:
            info_dict['parameters'] = parameters
        model_info.info(info_dict)
    
    @staticmethod
    def record_download_duration(duration: float, status: str):
        """Registra a duração de um download."""
        download_duration_histogram.labels(status=status).observe(duration)
    
    @staticmethod
    def record_download_size(size_bytes: int, status: str):
        """Registra o tamanho de um download."""
        download_size_histogram.labels(status=status).observe(size_bytes)
    
    @staticmethod
    def record_api_error(endpoint: str, error_type: str, status_code: int):
        """Registra um erro da API."""
        api_errors_counter.labels(
            endpoint=endpoint,
            error_type=error_type,
            status_code=str(status_code)
        ).inc()
        logger.debug(f"📊 API error recorded: {endpoint} {error_type} {status_code}")
    
    @staticmethod
    def track_request_in_progress(endpoint: str):
        """
        Context manager para rastrear requisições em andamento.
        
        Usage:
            with MetricsCollector.track_request_in_progress("/api/v1/transcribe"):
                # ... process request
        """
        class RequestTracker:
            def __init__(self, endpoint: str):
                self.endpoint = endpoint
            
            def __enter__(self):
                api_requests_in_progress_gauge.labels(endpoint=self.endpoint).inc()
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                api_requests_in_progress_gauge.labels(endpoint=self.endpoint).dec()
                return False
        
        return RequestTracker(endpoint)
