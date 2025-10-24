#!/usr/bin/env python3
"""
Script para iniciar Celery worker
"""
import os
import sys

# Adiciona diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.celery_tasks import celery_app

if __name__ == '__main__':
    # Inicia worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=2',
        '--pool=solo'  # Para Windows
    ])
