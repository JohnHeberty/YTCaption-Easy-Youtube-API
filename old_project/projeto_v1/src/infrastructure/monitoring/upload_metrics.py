"""
Métricas Prometheus para upload de vídeos.
"""
from prometheus_client import Counter, Histogram, Gauge


# Contador de requisições de upload
upload_requests_total = Counter(
    'upload_requests_total',
    'Total de requisições de upload de vídeo',
    labelnames=['status', 'format']
)


# Histograma de duração do upload
upload_duration_seconds = Histogram(
    'upload_duration_seconds',
    'Tempo de duração do upload de vídeo (segundos)',
    labelnames=['format'],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0)
)


# Histograma de tamanho dos arquivos
upload_file_size_bytes = Histogram(
    'upload_file_size_bytes',
    'Tamanho dos arquivos enviados (bytes)',
    labelnames=['format'],
    buckets=(
        1_000_000,      # 1MB
        10_000_000,     # 10MB
        50_000_000,     # 50MB
        100_000_000,    # 100MB
        250_000_000,    # 250MB
        500_000_000,    # 500MB
        1_000_000_000,  # 1GB
        2_500_000_000   # 2.5GB
    )
)


# Gauge de uploads em progresso
uploads_in_progress = Gauge(
    'uploads_in_progress',
    'Número de uploads em progresso no momento'
)


# Contador de erros de validação
upload_validation_errors = Counter(
    'upload_validation_errors',
    'Total de erros de validação em uploads',
    labelnames=['error_type', 'format']
)


# Histograma de duração dos vídeos enviados
upload_video_duration_seconds = Histogram(
    'upload_video_duration_seconds',
    'Duração dos vídeos enviados (segundos)',
    labelnames=['format'],
    buckets=(
        30,      # 30s
        60,      # 1min
        300,     # 5min
        600,     # 10min
        1800,    # 30min
        3600,    # 1h
        7200,    # 2h
        10800    # 3h (máximo)
    )
)


# Contador de formatos de arquivo
upload_formats_total = Counter(
    'upload_formats_total',
    'Total de uploads por formato de arquivo',
    labelnames=['format', 'type']  # type: video ou audio
)
