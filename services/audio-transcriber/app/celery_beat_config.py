"""
Configuração do Celery Beat para tarefas periódicas.
Inclui limpeza de jobs órfãos e expirados.
"""
from celery.schedules import crontab

# Configuração de tarefas periódicas
beat_schedule = {
    # Limpeza de jobs órfãos a cada 5 minutos
    'cleanup-orphan-jobs': {
        'task': 'cleanup_orphan_jobs',
        'schedule': 300.0,  # 5 minutos em segundos
        'options': {
            'queue': 'audio_transcriber_queue'
        }
    },
    
    # Limpeza de jobs expirados a cada 30 minutos
    'cleanup-expired-jobs': {
        'task': 'cleanup_expired_jobs',
        'schedule': 1800.0,  # 30 minutos
        'options': {
            'queue': 'audio_transcriber_queue'
        }
    },
}

# Exporta para ser usado pelo celery_config.py
def get_beat_schedule():
    return beat_schedule
