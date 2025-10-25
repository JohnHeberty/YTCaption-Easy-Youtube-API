import asyncio
from fastapi import APIRouter, Request, HTTPException

from projeto_v3.application.use_cases.save_from_cache import SaveFromCacheUseCase
from projeto_v3.application.use_cases.fetch_captions import FetchCaptionsUseCase
from projeto_v3.adapters.outbound.file_storage import FileStorage
from projeto_v3.adapters.outbound.youtube_transcript import YouTubeTranscriptProvider
from projeto_v3.adapters.outbound.whisper_provider import WhisperProvider
from projeto_v3.adapters.outbound.youtube_stub import YouTubeStubProvider
from projeto_v3.adapters.outbound.cached_provider import CachedProvider
from projeto_v3.adapters.outbound.fallback_provider import FallbackProvider
from projeto_v3.infrastructure.cache import FileCaptionCache

router = APIRouter()

# Semáforo de processo para controlar concorrência
_semaphore: asyncio.Semaphore | None = None


def _ensure_wiring(app):
    global _semaphore
    settings = app.state.settings
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.concurrency_limit)

    storage = getattr(app.state, "storage", None)
    cache = getattr(app.state, "cache", None)
    provider = getattr(app.state, "provider", None)

    if storage is None:
        storage = FileStorage(settings.data_dir)
        app.state.storage = storage

    if cache is None:
        cache = FileCaptionCache(settings.data_dir, ttl_seconds=settings.cache_ttl_seconds)
        app.state.cache = cache

    if provider is None:
        if settings.cached_only:
            return SaveFromCacheUseCase(cache=cache, storage=storage)
        else:
            # Cascata de providers: YouTube transcript → Whisper (download + transcreve) → Stub
            yt_transcript = YouTubeTranscriptProvider(timeout_s=settings.timeout_seconds, max_retries=settings.max_retries)  # pylint: disable=line-too-long
            whisper = WhisperProvider(timeout_s=60.0, max_retries=1, model_name="base")  # timeout maior para whisper
            stub = YouTubeStubProvider(timeout_s=settings.timeout_seconds, max_retries=settings.max_retries)
            
            fallback_chain = FallbackProvider([yt_transcript, whisper, stub])
            provider = CachedProvider(primary=fallback_chain, cache=cache, fallback=None)
            app.state.provider = provider
            return FetchCaptionsUseCase(provider=provider, storage=storage)
    
    return SaveFromCacheUseCase(cache=cache, storage=storage)


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/version")
async def version(request: Request):
    s = request.app.state.settings
    return {"name": s.app_name, "version": s.app_version}


@router.post("/captions/{video_id}")
async def fetch_captions(video_id: str, request: Request):
    use_case = _ensure_wiring(request.app)
    assert _semaphore is not None
    async with _semaphore:
        result = await use_case.execute(video_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Not found in cache")
        return result


@router.get("/captions/{video_id}/cached")
async def get_cached_captions(video_id: str, request: Request):
    _ensure_wiring(request.app)
    cache: FileCaptionCache = request.app.state.cache
    vc = cache.get(video_id)
    if vc is None:
        raise HTTPException(status_code=404, detail="Not found in cache")
    return {"video_id": vc.video_id, "lines": len(vc.lines)}
