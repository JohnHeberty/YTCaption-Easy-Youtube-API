from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from common.datetime_utils import now_brazil
from common.health_utils import ServiceHealthChecker
from common.log_utils import get_logger
from app.core.config import get_core, get_supported_languages, get_whisper_models
from app.api.schemas import DetailedHealthResponse, EnginesResponse, HealthResponse, LanguagesResponse
from app.domain.interfaces import IJobStore
from app.infrastructure.dependencies import job_store, processor
from app.shared.health_checkers import (
    check_disk_space,
    check_ffmpeg,
    check_whisper_model,
)

if TYPE_CHECKING:
    from app.services.processor import TranscriptionProcessor

logger = get_logger(__name__)
settings = get_core()

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check", response_model=HealthResponse)
async def health_check(
    job_store: IJobStore = Depends(job_store),
    processor: "TranscriptionProcessor" = Depends(processor),
):
    """Check service health including Redis, disk space, ffmpeg, and model status."""
    checker = ServiceHealthChecker("audio-transcription", version=settings.app_version)

    checker.add_check("redis", lambda: ServiceHealthChecker.check_redis(job_store.redis))
    checker.add_check(
        "disk_space",
        lambda: check_disk_space(settings["transcription_dir"]),
    )
    checker.add_check("ffmpeg", lambda: check_ffmpeg())
    checker.add_check(
        "celery_workers",
        lambda: {"status": "ok", "message": "Celery workers verification skipped for faster health response"},
    )
    checker.add_check(
        "whisper_model",
        lambda: check_whisper_model(processor, settings),
    )

    result = await checker.check_all()

    status_code = 200 if result["status"] == "healthy" else 503

    return JSONResponse(content=result, status_code=status_code)


@router.get("/health/detailed", summary="Detailed health check", response_model=DetailedHealthResponse, responses={503: {"description": "Service unhealthy"}})
async def health_check_detailed(
    job_store: IJobStore = Depends(job_store),
    processor: "TranscriptionProcessor" = Depends(processor),
):
    """Perform a detailed health check of Redis, Celery, and model components."""
    from app.health_checker import (
        CeleryHealthChecker,
        RedisHealthChecker,
        ModelHealthChecker,
        AggregateHealthChecker
    )
    from app.infrastructure.celery_config import celery_app

    try:
        aggregate = AggregateHealthChecker()

        aggregate.register_checker("redis", RedisHealthChecker(job_store))
        aggregate.register_checker("celery", CeleryHealthChecker(celery_app))
        aggregate.register_checker("model", ModelHealthChecker(processor))

        health_result = aggregate.check_all()

        health_result["service"] = "audio-transcription"
        health_result["version"] = "2.0.0"

        status_code = 200 if health_result["overall_healthy"] else 503

        return JSONResponse(content=health_result, status_code=status_code)

    except Exception as e:
        logger.error(f"❌ Erro no health check detalhado: {e}")
        return JSONResponse(
            content={
                "overall_healthy": False,
                "error": str(e),
                "timestamp": now_brazil().isoformat()
            },
            status_code=503
        )


@router.get("/metrics", summary="Prometheus metrics", response_class=Response)
async def prometheus_metrics(job_store: IJobStore = Depends(job_store)):
    """Expose Prometheus-format metrics for the transcription service."""
    svc = "audio_transcriber"
    stats: dict = {}
    try:
        stats = job_store.get_stats()
    except Exception as _e:
        logger.warning("Metrics: failed to get stats: %s", _e)

    by_status = stats.get("by_status", {})
    total = stats.get("total_jobs", 0)

    lines = [
        f"# HELP {svc}_jobs_total Jobs in Redis store by status",
        f"# TYPE {svc}_jobs_total gauge",
    ]
    for _status, _count in by_status.items():
        lines.append(f'{svc}_jobs_total{{status="{_status}"}} {_count}')
    lines += [
        f"# HELP {svc}_jobs_store_total Total jobs in Redis store",
        f"# TYPE {svc}_jobs_store_total gauge",
        f"{svc}_jobs_store_total {total}",
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@router.get("/languages", summary="Supported languages", response_model=LanguagesResponse)
async def get_supported_languages_endpoint():
    """Retrieve supported transcription and translation languages with usage examples."""
    languages = get_supported_languages()
    models = get_whisper_models()

    return {
        "transcription": {
            "supported_languages": languages,
            "total_languages": len(languages),
            "default_language": settings.whisper_language,
            "note": "Use 'auto' para detecção automática ou código ISO 639-1 específico",
            "examples": ["auto", "pt", "en", "es", "fr", "de", "it", "ja", "ko", "zh"]
        },
        "translation": {
            "supported_languages": ["en"],
            "note": "Whisper só suporta tradução para inglês (en)",
            "limitation": "Tradução para outros idiomas requer ferramentas externas",
            "examples": ["en"]
        },
        "models": models,
        "usage_examples": {
            "transcribe_portuguese": {
                "language_in": "pt",
                "language_out": None,
                "description": "Transcreve áudio em português"
            },
            "auto_detect_transcribe": {
                "language_in": "auto",
                "language_out": None,
                "description": "Detecta idioma e transcreve no idioma original"
            },
            "translate_to_english": {
                "language_in": "auto",
                "language_out": "en",
                "description": "Detecta idioma e traduz para inglês"
            },
            "translate_pt_to_en": {
                "language_in": "pt",
                "language_out": "en",
                "description": "Traduz áudio em português para inglês"
            }
        }
    }


@router.get("/engines", summary="Available engines", response_model=EnginesResponse)
async def get_available_engines():
    """List available transcription engines (Faster-Whisper, OpenAI Whisper, WhisperX) with capabilities."""
    from app.domain.models import WhisperEngine

    try:
        import whisperx
        whisperx_available = True
    except ImportError:
        whisperx_available = False

    engines = [
        {
            "id": WhisperEngine.FASTER_WHISPER.value,
            "name": "Faster-Whisper",
            "description": "4x mais rápido que OpenAI Whisper, usa CTranslate2",
            "available": True,
            "default": True,
            "features": {
                "word_timestamps": True,
                "word_timestamps_precision": "good",
                "forced_alignment": False,
                "speaker_diarization": False,
                "speed": "very_fast",
                "vram_usage": "low"
            },
            "use_cases": ["Transcrição rápida", "Produção em larga escala", "Recursos limitados"],
            "recommendation": "Recomendado para a maioria dos casos"
        },
        {
            "id": WhisperEngine.OPENAI_WHISPER.value,
            "name": "OpenAI Whisper",
            "description": "Implementação original da OpenAI",
            "available": True,
            "default": False,
            "features": {
                "word_timestamps": False,
                "word_timestamps_precision": None,
                "forced_alignment": False,
                "speaker_diarization": False,
                "speed": "slow",
                "vram_usage": "high"
            },
            "use_cases": ["Compatibilidade máxima", "Referência de qualidade"],
            "recommendation": "Use apenas se precisar compatibilidade exata com OpenAI"
        },
        {
            "id": WhisperEngine.WHISPERX.value,
            "name": "WhisperX",
            "description": "Word-level timestamps com forced alignment para precisão máxima",
            "available": whisperx_available,
            "default": False,
            "features": {
                "word_timestamps": True,
                "word_timestamps_precision": "excellent",
                "forced_alignment": True,
                "speaker_diarization": True,
                "speed": "fast",
                "vram_usage": "medium"
            },
            "use_cases": ["Lip-sync", "Legendas precisas", "Timing palavra por palavra"],
            "recommendation": "Recomendado para lip-sync e legendas precisas" if whisperx_available else "Instale whisperx: pip install whisperx",
            "note": None if whisperx_available else "⚠️ WhisperX não está instalado neste servidor"
        }
    ]

    return {
        "engines": engines,
        "default_engine": WhisperEngine.FASTER_WHISPER.value,
        "total_available": sum(1 for e in engines if e["available"]),
        "recommendation": {
            "general_use": WhisperEngine.FASTER_WHISPER.value,
            "word_level_precision": WhisperEngine.WHISPERX.value if whisperx_available else WhisperEngine.FASTER_WHISPER.value,
            "compatibility": WhisperEngine.OPENAI_WHISPER.value
        }
    }