"""
Audio Transcription Service Package
"""

# Evita import pesado (torch/whisper) durante import de modulos simples em testes.
try:
	from .main import app
except Exception:  # pragma: no cover - fallback para ambientes sem deps opcionais
	app = None

try:
	from .infrastructure.celery_config import celery_app
except Exception:  # pragma: no cover - fallback para ambientes sem deps opcionais
	celery_app = None

__all__ = ['app', 'celery_app']
