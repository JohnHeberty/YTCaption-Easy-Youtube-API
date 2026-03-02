#!/usr/bin/env python3
"""
Configuração do Celery para processamento de jobs
"""

from celery import Celery
import os

# URL do Redis (pode ser configurado via variável de ambiente)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# TTL do cache em segundos (converte de horas)
CACHE_TTL_HOURS = int(os.getenv('CACHE_TTL_HOURS', '24'))
RESULT_EXPIRES_SECONDS = CACHE_TTL_HOURS * 3600

# Cria instância do Celery
celery_app = Celery(
    'video_download_service',
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Configurações do Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,
    
    # Configurações de retry
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Tempo de expiração de resultados (configurável via CACHE_TTL_HOURS)
    result_expires=RESULT_EXPIRES_SECONDS,
    
    # Configurações de workers
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    
    # Timeout de tasks (30 minutos para downloads grandes)
    task_time_limit=1800,
    task_soft_time_limit=1700,
    
    # Reconnect to broker
    broker_connection_retry_on_startup=True,
    
    # 🔧 FILA DEDICADA para video-downloader
    task_default_queue='video_downloader_queue',
    task_routes={
        'download_video_task': {'queue': 'video_downloader_queue'},
        'cleanup_expired_jobs': {'queue': 'video_downloader_queue'},
    },
)