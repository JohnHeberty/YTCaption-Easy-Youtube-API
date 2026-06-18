"""
Prometheus metrics

Métricas para monitoramento do serviço
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST


# === Counters ===

downloads_skipped_total = Counter(
    'make_video_downloads_skipped_total',
    'Total de downloads pulados',
    ['reason']  # blacklisted, duplicate, corrupted, etc
)

vad_segments_dropped_total = Counter(
    'make_video_vad_segments_dropped_total',
    'Total de segmentos VAD descartados',
    ['reason']  # too_short, invalid, etc
)

vad_segments_merged_total = Counter(
    'make_video_vad_segments_merged_total',
    'Total de merges de segmentos VAD'
)

vad_method_used_total = Counter(
    'make_video_vad_method_used_total',
    'Total de vezes que cada método VAD foi usado',
    ['method']  # silero, webrtcvad, rms
)

vad_fallback_rate_total = Counter(
    'make_video_vad_fallback_rate_total',
    'Total de fallbacks VAD',
    ['from_method', 'to_method']
)

policy_decisions_total = Counter(
    'make_video_policy_decisions_total',
    'Total de decisões de política',
    ['action']  # blacklisted, proceed_caution, proceed
)

subtitles_burned_total = Counter(
    'make_video_subtitles_burned_total',
    'Total de legendas queimadas',
    ['status']  # success, fail
)

subtitles_dropped_by_vad_total = Counter(
    'make_video_subtitles_dropped_by_vad_total',
    'Total de legendas descartadas por VAD'
)

blacklist_entries_removed_total = Counter(
    'make_video_blacklist_entries_removed_total',
    'Total de entradas removidas da blacklist',
    ['backend']  # redis, json
)

speech_gating_applied_total = Counter(
    'make_video_speech_gating_applied_total',
    'Total de aplicações de speech gating',
    ['vad_ok']  # true, false
)


# === Histograms ===

validation_time_ms = Histogram(
    'make_video_validation_time_ms',
    'Tempo de validação de vídeo em ms',
    buckets=[100, 500, 1000, 2000, 5000, 10000]
)

vad_merge_ratio = Histogram(
    'make_video_vad_merge_ratio',
    'Ratio de merge (merged/original)',
    buckets=[0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
)

ocr_confidence_distribution = Histogram(
    'make_video_ocr_confidence_distribution',
    'Distribuição de confidence OCR',
    buckets=[0.0, 0.2, 0.4, 0.6, 0.75, 0.9, 1.0]
)


# === Gauges ===

blacklist_size = Gauge(
    'make_video_blacklist_size',
    'Tamanho atual da blacklist'
)


def get_metrics():
    """Retorna métricas em formato Prometheus"""
    return generate_latest()
