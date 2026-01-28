"""
Make-Video Service - FastAPI Application

Serviço para criar vídeos automaticamente a partir de:
- Áudio (entrada do usuário)
- Shorts do YouTube (buscados via youtube-search)
- Legendas (transcrição via audio-transcriber)
"""

import logging
import shortuuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models import Job, JobStatus, CreateVideoRequest
from .redis_store import RedisJobStore
from .shorts_manager import ShortsCache
from .celery_tasks import process_make_video
from .logging_config import setup_logging
from .exceptions import MakeVideoException

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Settings
settings = get_settings()

# FastAPI app
app = FastAPI(
    title="Make-Video Service",
    description="Orquestra criação de vídeos a partir de áudio + shorts + legendas",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
redis_store = RedisJobStore(redis_url=settings['redis_url'])
shorts_cache = ShortsCache(cache_dir=settings['shorts_cache_dir'])


@app.on_event("startup")
async def startup_event():
    """Inicialização do serviço"""
    logger.info("🚀 Make-Video Service starting...")
    
    # Criar diretórios necessários
    for dir_path in [
        settings['audio_upload_dir'],
        settings['shorts_cache_dir'],
        settings['temp_dir'],
        settings['output_dir'],
        settings['logs_dir']
    ]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Iniciar cleanup task automático
    await redis_store.start_cleanup_task()
    logger.info("🧹 Cleanup task started")
    
    logger.info("✅ Make-Video Service ready!")
    logger.info(f"   ├─ Redis: {settings['redis_url']}")
    logger.info(f"   ├─ YouTube Search: {settings['youtube_search_url']}")
    logger.info(f"   ├─ Video Downloader: {settings['video_downloader_url']}")
    logger.info(f"   └─ Audio Transcriber: {settings['audio_transcriber_url']}")


@app.post("/make-video", status_code=202)
async def create_video(
    audio_file: UploadFile = File(..., description="Audio file (max 100MB)"),
    query: str = Form(..., min_length=3, max_length=200),
    max_shorts: int = Form(10, ge=10, le=500),  # Aligned with planning: 10-500
    subtitle_language: str = Form("pt"),
    subtitle_style: str = Form("static"),
    aspect_ratio: str = Form("9:16"),
    crop_position: str = Form("center")
):
    """
    Criar novo vídeo
    
    **Entrada:**
    - audio_file: Arquivo de áudio (mp3, wav, m4a, ogg) - Máx 100MB
    - query: Query de busca para shorts (3-200 caracteres)
    - max_shorts: Máximo de shorts para buscar (10-500)
    - subtitle_language: Idioma das legendas (pt, en, es)
    - subtitle_style: Estilo das legendas (static, dynamic, minimal)
    - aspect_ratio: Proporção do vídeo (9:16, 16:9, 1:1, 4:5)
    - crop_position: Posição do crop (center, top, bottom)
    
    **Retorno:**
    - job_id: ID do job criado
    - status: Status inicial (QUEUED)
    """
    try:
        # Validações
        MAX_AUDIO_SIZE = 100 * 1024 * 1024  # 100MB
        
        # Ler conteúdo do áudio (com limite)
        content = await audio_file.read()
        
        if len(content) > MAX_AUDIO_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"Audio file too large. Max size: 100MB, received: {len(content) / (1024*1024):.1f}MB"
            )
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        
        if max_shorts < 10 or max_shorts > 500:
            raise HTTPException(status_code=400, detail="max_shorts deve estar entre 10 e 500")
        
        if aspect_ratio not in ["9:16", "16:9", "1:1", "4:5"]:
            raise HTTPException(status_code=400, detail="aspect_ratio inválido")
        
        if crop_position not in ["center", "top", "bottom"]:
            raise HTTPException(status_code=400, detail="crop_position inválido")
        
        if subtitle_style not in ["static", "dynamic", "minimal"]:
            raise HTTPException(status_code=400, detail="subtitle_style inválido")
        
        # Verificar extensão do arquivo
        allowed_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.aac']
        file_ext = Path(audio_file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Formato de áudio não suportado. Use: {', '.join(allowed_extensions)}"
            )
        
        # Criar job ID
        job_id = shortuuid.uuid()
        
        # Salvar áudio
        audio_dir = Path(settings['audio_upload_dir']) / job_id
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / f"audio{file_ext}"
        
        # Salvar áudio (content já foi lido acima)
        with open(audio_path, "wb") as f:
            f.write(content)
        
        logger.info(f"💾 Audio saved: {audio_path} ({len(content)} bytes)")
        
        # Criar job
        job = Job(
            job_id=job_id,
            status=JobStatus.QUEUED,
            query=query,
            max_shorts=max_shorts,
            subtitle_language=subtitle_language,
            subtitle_style=subtitle_style,
            aspect_ratio=aspect_ratio,
            crop_position=crop_position,
            created_at=datetime.utcnow()
        )
        
        # Salvar no Redis
        await redis_store.save_job(job)
        
        # Disparar task assíncrona
        process_make_video.delay(job_id)
        
        logger.info(f"🎬 Job {job_id} created and queued")
        
        return {
            "job_id": job_id,
            "status": JobStatus.QUEUED.value,
            "message": "Video creation job queued successfully",
            "query": query,
            "max_shorts": max_shorts,
            "aspect_ratio": aspect_ratio
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating video job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create video job: {str(e)}")


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Verificar status de um job
    
    **Retorno:**
    - job_id: ID do job
    - status: Status atual (QUEUED, ANALYZING_AUDIO, ..., COMPLETED, FAILED)
    - progress: Progresso (0-100%)
    - result: Informações do vídeo (se completo)
    - error: Detalhes do erro (se falhou)
    """
    try:
        job = await redis_store.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return job.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{job_id}")
async def download_video(job_id: str):
    """
    Fazer download do vídeo final
    
    **Retorno:**
    - Arquivo MP4 do vídeo criado
    """
    try:
        job = await redis_store.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=400, 
                detail=f"Video is not ready yet. Current status: {job.status.value}"
            )
        
        if not job.result:
            raise HTTPException(status_code=500, detail="Job completed but no result available")
        
        # Caminho do vídeo
        video_path = Path(settings['output_dir']) / job.result.video_file
        
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found")
        
        logger.info(f"📥 Downloading video: {job_id}")
        
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=f"video_{job_id}.mp4"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filtrar por status"),
    limit: int = Query(50, ge=1, le=500, description="Número máximo de jobs")
):
    """
    Listar todos os jobs
    
    **Parâmetros:**
    - status: Filtrar por status (QUEUED, PROCESSING, COMPLETED, FAILED)
    - limit: Limite de resultados (1-500)
    
    **Retorno:**
    - Lista de jobs
    """
    try:
        jobs = await redis_store.list_jobs(limit=limit)
        
        # Filtrar por status se especificado
        if status:
            try:
                status_enum = JobStatus(status.upper())
                jobs = [job for job in jobs if job.status == status_enum]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        return {
            "total": len(jobs),
            "jobs": [job.dict() for job in jobs]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Deletar um job e seus arquivos associados
    
    **Retorno:**
    - Mensagem de confirmação
    """
    try:
        job = await redis_store.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Deletar arquivos
        import shutil
        
        # Áudio
        audio_dir = Path(settings['audio_upload_dir']) / job_id
        if audio_dir.exists():
            shutil.rmtree(audio_dir)
        
        # Temp
        temp_dir = Path(settings['temp_dir']) / job_id
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        # Vídeo final
        if job.result:
            video_path = Path(settings['output_dir']) / job.result.video_file
            if video_path.exists():
                video_path.unlink()
        
        # Deletar do Redis
        await redis_store.delete_job(job_id)
        
        logger.info(f"🗑️ Job {job_id} deleted")
        
        return {
            "message": "Job deleted successfully",
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats")
async def get_cache_stats():
    """
    Estatísticas do cache de shorts
    
    **Retorno:**
    - total_shorts: Total de shorts em cache
    - total_size_mb: Tamanho total em MB
    - most_used: Shorts mais usados
    """
    try:
        stats = shorts_cache.get_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cache/cleanup")
async def cleanup_cache(days: int = Query(30, ge=1, le=365)):
    """
    Limpar cache de shorts antigos
    
    **Parâmetros:**
    - days: Remover shorts não usados há X dias
    
    **Retorno:**
    - removed_count: Número de shorts removidos
    """
    try:
        removed_count = shorts_cache.cleanup_old(days=days)
        
        logger.info(f"🧹 Cache cleanup: {removed_count} shorts removed")
        
        return {
            "message": "Cache cleanup completed",
            "removed_count": removed_count,
            "days_threshold": days
        }
        
    except Exception as e:
        logger.error(f"Error cleaning cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    
    **Retorno:**
    - status: healthy/unhealthy
    - redis: Estado da conexão Redis
    - services: Estado dos microserviços
    """
    try:
        # Verificar Redis
        redis_ok = await redis_store.health_check()
        
        # Verificar conectividade com microserviços
        import httpx
        services_health = {}
        
        for service, url in [
            ("youtube-search", settings['youtube_search_url']),
            ("video-downloader", settings['video_downloader_url']),
            ("audio-transcriber", settings['audio_transcriber_url'])
        ]:
            try:
                async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
                    response = await client.get(f"{url}/health")
                    services_health[service] = "ok" if response.status_code == 200 else "error"
            except Exception as e:
                logger.warning(f"Service {service} health check failed: {e}")
                services_health[service] = "unreachable"
        
        all_healthy = redis_ok and all(status == "ok" for status in services_health.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "service": "make-video",
            "version": "1.0.0",
            "redis": "connected" if redis_ok else "disconnected",
            "services": services_health,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/")
async def root():
    """Informações do serviço"""
    return {
        "service": "make-video",
        "version": "1.0.0",
        "description": "Orquestra criação de vídeos a partir de áudio + shorts + legendas",
        "endpoints": {
            "POST /make-video": "Criar novo vídeo",
            "GET /jobs/{job_id}": "Status do job",
            "GET /download/{job_id}": "Download do vídeo",
            "GET /jobs": "Listar jobs",
            "DELETE /jobs/{job_id}": "Deletar job",
            "GET /cache/stats": "Estatísticas do cache",
            "POST /cache/cleanup": "Limpar cache",
            "GET /health": "Health check"
        },
        "architecture": {
            "pattern": "Orchestrator",
            "microservices": [
                "youtube-search:8003",
                "video-downloader:8002",
                "audio-transcriber:8005"
            ]
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info"
    )
