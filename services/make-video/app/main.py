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


@app.post("/jobs/cleanup-failed")
async def cleanup_failed_jobs():
    """
    Limpar jobs com erro do Redis
    
    **Retorno:**
    - removed_count: Número de jobs removidos
    - job_ids: IDs dos jobs removidos
    """
    try:
        # Buscar todos os jobs com status failed
        all_jobs = await redis_store.list_jobs()
        failed_jobs = [job for job in all_jobs if job.status == 'failed']
        
        removed_ids = []
        for job in failed_jobs:
            try:
                await redis_store.delete_job(job.job_id)
                removed_ids.append(job.job_id)
            except Exception as e:
                logger.warning(f"Failed to delete job {job.job_id}: {e}")
        
        logger.info(f"🧹 Cleanup: {len(removed_ids)} failed jobs removed")
        
        return {
            "message": "Failed jobs cleanup completed",
            "removed_count": len(removed_ids),
            "job_ids": removed_ids
        }
        
    except Exception as e:
        logger.error(f"Error cleaning failed jobs: {e}", exc_info=True)
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


@app.post("/admin/cleanup")
async def admin_cleanup(
    deep: bool = Query(False, description="Se true, faz limpeza PROFUNDA (factory reset)"),
    purge_celery_queue: bool = Query(False, description="Se true, limpa fila Celery também")
):
    """
    🧹 LIMPEZA ADMINISTRATIVA DO SISTEMA
    
    **Modos de operação:**
    
    1. **Limpeza Básica** (deep=false):
       - Remove jobs expirados (>24h)
       - Remove arquivos órfãos (sem job associado)
       - Mantém jobs ativos
    
    2. **Limpeza Profunda** (deep=true) - ⚠️ FACTORY RESET:
       - TODO o banco Redis (FLUSHDB no DB atual)
       - TODOS os uploads de áudio
       - TODOS os vídeos de saída
       - TODOS os arquivos temporários
       - TODO o cache de shorts
       - (Opcional) Purga fila Celery
    
    **Parâmetros:**
    - deep (bool): Factory reset se true
    - purge_celery_queue (bool): Limpa fila Celery (apenas com deep=true)
    
    **Retorna:**
    Relatório detalhado da limpeza executada
    
    **⚠️ ATENÇÃO**: Operação SÍNCRONA - cliente aguarda conclusão completa
    """
    cleanup_type = "PROFUNDA (FACTORY RESET)" if deep else "BÁSICA"
    logger.warning(f"🧹 Iniciando limpeza {cleanup_type} (purge_celery={purge_celery_queue})")
    
    try:
        if deep:
            result = await _perform_deep_cleanup(purge_celery_queue)
        else:
            result = await _perform_basic_cleanup()
        
        logger.info(f"✅ Limpeza {cleanup_type} CONCLUÍDA com sucesso")
        return result
        
    except Exception as e:
        logger.error(f"❌ ERRO na limpeza {cleanup_type}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao executar cleanup: {str(e)}")


@app.get("/admin/stats")
async def admin_stats():
    """
    📊 ESTATÍSTICAS ADMINISTRATIVAS COMPLETAS
    
    **Retorna:**
    - jobs: Contagem de jobs por status
    - storage: Uso de armazenamento (uploads, outputs, temp)
    - shorts_cache: Estatísticas do cache de shorts
    - celery: Status dos workers Celery (se disponível)
    - system: Informações do sistema
    
    **Exemplo de resposta:**
    ```json
    {
        "jobs": {
            "queued": 5,
            "processing": 2,
            "completed": 150,
            "failed": 10,
            "total": 167
        },
        "storage": {
            "audio_uploads": {"count": 50, "size_mb": 250.5},
            "output_videos": {"count": 145, "size_mb": 1200.8},
            "temp": {"count": 10, "size_mb": 50.2},
            "total_size_mb": 1501.5
        },
        "shorts_cache": {
            "cached_searches": 20,
            "blacklist_size": 15,
            "total_shorts": 300
        },
        "celery": {
            "active_workers": 2,
            "active_tasks": 3
        }
    }
    ```
    """
    try:
        # 1. Job statistics
        job_stats = redis_store.get_stats()
        
        # 2. Storage statistics
        audio_dir = Path(settings['audio_upload_dir'])
        output_dir = Path(settings['output_dir'])
        temp_dir = Path(settings['temp_dir'])
        
        def get_dir_stats(dir_path: Path) -> dict:
            """Get file count and total size for directory"""
            if not dir_path.exists():
                return {"count": 0, "size_mb": 0.0}
            
            files = [f for f in dir_path.iterdir() if f.is_file()]
            total_size = sum(f.stat().st_size for f in files)
            
            return {
                "count": len(files),
                "size_mb": round(total_size / (1024 * 1024), 2)
            }
        
        audio_stats = get_dir_stats(audio_dir)
        output_stats = get_dir_stats(output_dir)
        temp_stats = get_dir_stats(temp_dir)
        
        total_size_mb = (
            audio_stats["size_mb"] +
            output_stats["size_mb"] +
            temp_stats["size_mb"]
        )
        
        storage_stats = {
            "audio_uploads": audio_stats,
            "output_videos": output_stats,
            "temp": temp_stats,
            "total_size_mb": round(total_size_mb, 2)
        }
        
        # 3. Shorts cache statistics
        cache_stats = shorts_cache.get_stats()
        
        # 4. Celery statistics (best effort)
        celery_stats = {}
        try:
            from .celery_config import celery_app
            inspect = celery_app.control.inspect(timeout=3.0)
            active_workers = inspect.active()
            
            if active_workers:
                celery_stats = {
                    "active_workers": len(active_workers),
                    "active_tasks": sum(len(tasks) for tasks in active_workers.values()),
                    "status": "ok"
                }
            else:
                celery_stats = {
                    "active_workers": 0,
                    "active_tasks": 0,
                    "status": "no_workers"
                }
        except Exception as e:
            celery_stats = {
                "status": "unavailable",
                "error": str(e)
            }
        
        # 5. System info
        import shutil
        disk = shutil.disk_usage(output_dir)
        
        system_stats = {
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent_used": round((disk.used / disk.total) * 100, 1)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {
            "jobs": job_stats,
            "storage": storage_stats,
            "shorts_cache": cache_stats,
            "celery": celery_stats,
            "system": system_stats
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter estatísticas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao obter estatísticas: {str(e)}")


@app.post("/admin/cleanup-orphans")
async def cleanup_orphans(
    max_age_minutes: int = Query(30, ge=5, le=120, description="Idade máxima para considerar job órfão")
):
    """
    🔧 LIMPEZA DE JOBS E ARQUIVOS ÓRFÃOS
    
    **Detecta e corrige:**
    - Jobs travados em PROCESSING por > X minutos
    - Arquivos sem job associado
    - Jobs sem arquivo associado
    
    **Parâmetros:**
    - max_age_minutes: Tempo máximo em PROCESSING antes de considerar órfão (5-120 min)
    
    **Ações executadas:**
    1. Busca jobs em PROCESSING há muito tempo
    2. Marca jobs órfãos como FAILED
    3. Remove arquivos sem job associado
    4. Limpa jobs sem arquivo de áudio
    
    **Retorna:**
    ```json
    {
        "orphaned_jobs_found": 3,
        "orphaned_jobs_fixed": 3,
        "orphaned_files_found": 5,
        "orphaned_files_removed": 5,
        "space_freed_mb": 125.5,
        "details": [...]
    }
    ```
    """
    try:
        logger.info(f"🔍 Buscando jobs e arquivos órfãos (max_age={max_age_minutes}min)")
        
        report = {
            "orphaned_jobs_found": 0,
            "orphaned_jobs_fixed": 0,
            "orphaned_files_found": 0,
            "orphaned_files_removed": 0,
            "space_freed_mb": 0.0,
            "details": []
        }
        
        # 1. Find and fix orphaned jobs
        orphaned_jobs = await redis_store.find_orphaned_jobs(max_age_minutes)
        report["orphaned_jobs_found"] = len(orphaned_jobs)
        
        for job in orphaned_jobs:
            try:
                # Mark as failed
                job.status = "failed"
                job.error = f"Job órfão detectado após {max_age_minutes}min em PROCESSING"
                job.updated_at = datetime.utcnow()
                
                await redis_store.save_job(job)
                report["orphaned_jobs_fixed"] += 1
                
                report["details"].append({
                    "type": "orphaned_job",
                    "job_id": job.job_id,
                    "action": "marked_as_failed",
                    "reason": f"Processing for > {max_age_minutes}min"
                })
                
                logger.info(f"✅ Job órfão marcado como FAILED: {job.job_id}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao marcar job órfão {job.job_id}: {e}")
                report["details"].append({
                    "type": "error",
                    "job_id": job.job_id,
                    "error": str(e)
                })
        
        # 2. Find and remove orphaned files
        audio_dir = Path(settings['audio_upload_dir'])
        output_dir = Path(settings['output_dir'])
        temp_dir = Path(settings['temp_dir'])
        
        for directory in [audio_dir, output_dir, temp_dir]:
            if not directory.exists():
                continue
            
            for file_path in directory.iterdir():
                if not file_path.is_file():
                    continue
                
                try:
                    # Try to extract job_id from filename
                    # Patterns: {job_id}.mp3, {job_id}_output.mp4, etc
                    filename = file_path.stem.split('_')[0]
                    
                    # Check if job exists
                    job = await redis_store.get_job(filename)
                    
                    if job is None:
                        # Orphaned file!
                        file_size_mb = file_path.stat().st_size / (1024 * 1024)
                        
                        file_path.unlink()
                        
                        report["orphaned_files_found"] += 1
                        report["orphaned_files_removed"] += 1
                        report["space_freed_mb"] += file_size_mb
                        
                        report["details"].append({
                            "type": "orphaned_file",
                            "file": file_path.name,
                            "directory": directory.name,
                            "size_mb": round(file_size_mb, 2),
                            "action": "removed"
                        })
                        
                        logger.info(f"🗑️ Arquivo órfão removido: {file_path.name} ({file_size_mb:.2f}MB)")
                        
                except Exception as e:
                    logger.debug(f"Erro ao processar arquivo {file_path.name}: {e}")
        
        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        
        logger.info(
            f"✅ Limpeza de órfãos concluída: "
            f"{report['orphaned_jobs_fixed']} jobs + "
            f"{report['orphaned_files_removed']} arquivos "
            f"({report['space_freed_mb']}MB liberados)"
        )
        
        return report
        
    except Exception as e:
        logger.error(f"❌ Erro na limpeza de órfãos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro na limpeza de órfãos: {str(e)}")


async def _perform_basic_cleanup() -> dict:
    """
    Executa limpeza BÁSICA: Remove apenas jobs expirados e arquivos órfãos
    
    Returns:
        Relatório da limpeza
    """
    try:
        report = {
            "mode": "basic",
            "jobs_removed": 0,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "errors": []
        }
        
        logger.info("🧹 Iniciando limpeza básica...")
        
        # 1. Remove expired jobs
        try:
            expired_count = await redis_store.cleanup_expired()
            report["jobs_removed"] = expired_count
            logger.info(f"🗑️ Redis: {expired_count} jobs expirados removidos")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar jobs expirados: {e}")
            report["errors"].append(f"Redis cleanup: {str(e)}")
        
        # 2. Remove orphaned files (>24h old without job)
        audio_dir = Path(settings['audio_upload_dir'])
        output_dir = Path(settings['output_dir'])
        temp_dir = Path(settings['temp_dir'])
        
        now = datetime.utcnow()
        max_age = timedelta(hours=24)
        
        for directory in [audio_dir, output_dir, temp_dir]:
            if not directory.exists():
                continue
            
            for file_path in directory.iterdir():
                if not file_path.is_file():
                    continue
                
                try:
                    # Check file age
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    file_age = now - file_mtime
                    
                    if file_age > max_age:
                        # Old file - check if has associated job
                        filename_base = file_path.stem.split('_')[0]
                        job = await redis_store.get_job(filename_base)
                        
                        if job is None:
                            # Orphaned file
                            file_size_mb = file_path.stat().st_size / (1024 * 1024)
                            file_path.unlink()
                            
                            report["files_deleted"] += 1
                            report["space_freed_mb"] += file_size_mb
                            
                            logger.debug(f"🗑️ Arquivo órfão removido: {file_path.name}")
                            
                except Exception as e:
                    logger.debug(f"Erro ao processar {file_path.name}: {e}")
                    report["errors"].append(f"{directory.name}/{file_path.name}: {str(e)}")
        
        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        
        logger.info(
            f"✅ Limpeza básica concluída: "
            f"{report['jobs_removed']} jobs + "
            f"{report['files_deleted']} arquivos órfãos "
            f"({report['space_freed_mb']}MB liberados)"
        )
        
        return report
        
    except Exception as e:
        logger.error(f"❌ Erro na limpeza básica: {e}")
        return {"error": str(e), "jobs_removed": 0, "files_deleted": 0}


async def _perform_deep_cleanup(purge_celery: bool) -> dict:
    """
    Executa limpeza PROFUNDA: ZERA TODO O SISTEMA (factory reset)
    
    Args:
        purge_celery: Se true, limpa fila Celery também
    
    Returns:
        Relatório detalhado da limpeza
    """
    try:
        report = {
            "mode": "deep",
            "jobs_removed": 0,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "redis_flushed": False,
            "celery_purged": False,
            "errors": []
        }
        
        logger.warning("🔥 INICIANDO LIMPEZA PROFUNDA - FACTORY RESET!")
        
        # 1. Count jobs before flushing
        job_stats = redis_store.get_stats()
        report["jobs_removed"] = job_stats["total"]
        
        # 2. FLUSHDB no Redis (limpa APENAS o DB atual, não todos)
        try:
            # Flush apenas o DB atual (respeita REDIS_DIVISOR)
            redis_store.redis.flushdb()
            report["redis_flushed"] = True
            logger.warning(f"🔥 Redis FLUSHDB executado: {report['jobs_removed']} jobs + metadata removidos")
        except Exception as e:
            logger.error(f"❌ Erro ao executar FLUSHDB: {e}")
            report["errors"].append(f"Redis FLUSHDB: {str(e)}")
        
        # 3. Remove TODOS os arquivos
        audio_dir = Path(settings['audio_upload_dir'])
        output_dir = Path(settings['output_dir'])
        temp_dir = Path(settings['temp_dir'])
        shorts_dir = Path(settings['shorts_cache_dir'])
        
        for directory in [audio_dir, output_dir, temp_dir, shorts_dir]:
            if not directory.exists():
                continue
            
            logger.info(f"🗑️ Limpando diretório: {directory.name}")
            
            for item in directory.iterdir():
                try:
                    if item.is_file():
                        file_size_mb = item.stat().st_size / (1024 * 1024)
                        item.unlink()
                        report["files_deleted"] += 1
                        report["space_freed_mb"] += file_size_mb
                    elif item.is_dir():
                        # Remove subdirectories recursively
                        import shutil
                        shutil.rmtree(item)
                        logger.debug(f"📁 Removido subdiretório: {item.name}")
                except Exception as e:
                    logger.error(f"❌ Erro ao remover {item.name}: {e}")
                    report["errors"].append(f"{directory.name}/{item.name}: {str(e)}")
            
            logger.info(f"✓ Diretório {directory.name} limpo")
        
        # 4. Purga fila Celery (opcional)
        if purge_celery:
            try:
                from .celery_config import celery_app
                
                logger.warning("🔥 Purgando fila Celery...")
                
                # Purge all queues
                purged = celery_app.control.purge()
                report["celery_purged"] = True
                report["celery_tasks_purged"] = purged or 0
                
                logger.warning(f"🔥 Fila Celery purgada: {purged or 0} tasks removidas")
                
            except Exception as e:
                logger.error(f"❌ Erro ao purgar fila Celery: {e}")
                report["errors"].append(f"Celery purge: {str(e)}")
        else:
            logger.info("⏭️ Fila Celery NÃO foi limpa (purge_celery=false)")
        
        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        
        logger.warning(
            f"🔥 LIMPEZA PROFUNDA CONCLUÍDA: "
            f"{report['jobs_removed']} jobs + "
            f"{report['files_deleted']} arquivos removidos "
            f"({report['space_freed_mb']}MB liberados)"
        )
        
        return report
        
    except Exception as e:
        logger.error(f"❌ Erro na limpeza profunda: {e}")
        return {"error": str(e), "jobs_removed": 0, "files_deleted": 0}


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
            "jobs": {
                "POST /make-video": "Criar novo vídeo",
                "GET /jobs/{job_id}": "Status do job",
                "GET /download/{job_id}": "Download do vídeo",
                "GET /jobs": "Listar jobs",
                "DELETE /jobs/{job_id}": "Deletar job",
                "POST /jobs/cleanup-failed": "Limpar jobs falhados",
                "GET /jobs/orphaned": "Listar jobs órfãos",
                "POST /jobs/orphaned/cleanup": "Limpar jobs órfãos"
            },
            "admin": {
                "POST /admin/cleanup": "Limpeza do sistema (básica ou profunda)",
                "GET /admin/stats": "Estatísticas completas do sistema",
                "POST /admin/cleanup-orphans": "Limpar jobs e arquivos órfãos",
                "GET /admin/queue": "Informações da fila de jobs"
            },
            "cache": {
                "GET /cache/stats": "Estatísticas do cache de shorts",
                "POST /cache/cleanup": "Limpar cache de shorts antigos"
            },
            "health": {
                "GET /health": "Health check",
                "POST /test-speech-gating": "Testar Speech-Gated Subtitles"
            }
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



@app.post("/test-speech-gating")
async def test_speech_gating(
    audio_file: UploadFile = File(...),
    subtitles: str = Form(...)
):
    """
    Endpoint de teste para Speech-Gated Subtitles
    
    - **audio_file**: Arquivo de áudio (WAV, MP3, OGG)
    - **subtitles**: JSON array de legendas [{start, end, text}]
    """
    import json
    import tempfile
    from pathlib import Path
    from app.subtitle_postprocessor import process_subtitles_with_vad
    
    try:
        # Parse subtitles
        cues = json.loads(subtitles)
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(audio_file.filename).suffix) as tmp:
            content = await audio_file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            # Process with speech gating
            gated_cues, vad_ok = process_subtitles_with_vad(
                audio_path=tmp_path,
                raw_cues=cues
            )
            
            return {
                "status": "success",
                "input": {
                    "audio_file": audio_file.filename,
                    "cues_count": len(cues)
                },
                "output": {
                    "gated_cues": gated_cues,
                    "cues_count": len(gated_cues),
                    "dropped_count": len(cues) - len(gated_cues),
                    "vad_status": "primary" if vad_ok else "fallback"
                }
            }
        finally:
            # Cleanup
            Path(tmp_path).unlink(missing_ok=True)
            
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in subtitles: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")


# ============================================================================
# ADDITIONAL ADMIN ENDPOINTS
# ============================================================================

@app.get("/admin/queue")
async def get_queue_info():
    """
    Get detailed information about the job queue
    
    Returns queue statistics including:
    - Total jobs count
    - Jobs by status (queued, processing, completed, failed)
    - Oldest and newest job information
    
    **Use Cases**:
    - Monitor queue health and growth
    - Identify bottlenecks in processing
    - Track job throughput over time
    """
    try:
        queue_info = await redis_store.get_queue_info()
        
        return {
            "status": "success",
            "queue": queue_info
        }
    
    except Exception as e:
        logger.error(f"Error getting queue info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get queue info: {str(e)}")


@app.get("/jobs/orphaned")
async def get_orphaned_jobs(max_age_minutes: int = Query(30, ge=1, description="Maximum age in minutes for processing jobs")):
    """
    Get list of orphaned jobs (stuck in processing state)
    
    Orphaned jobs are jobs that:
    - Are in 'processing' status
    - Haven't been updated for more than max_age_minutes
    - Likely indicate worker crashes or timeout issues
    
    **Parameters**:
    - max_age_minutes: Threshold for considering a job orphaned (default: 30)
    
    **Returns**:
    - List of orphaned jobs with details (job_id, status, age, etc.)
    
    **Use Cases**:
    - Detect stuck jobs before cleanup
    - Monitor for worker health issues
    - Identify patterns in job failures
    """
    try:
        orphaned = await redis_store.find_orphaned_jobs(max_age_minutes=max_age_minutes)
        
        # Format response with detailed info
        orphaned_info = []
        for job in orphaned:
            age_minutes = (datetime.utcnow() - job.updated_at).total_seconds() / 60
            orphaned_info.append({
                "job_id": job.job_id,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
                "age_minutes": round(age_minutes, 2),
                "request": job.request.dict() if job.request else None
            })
        
        return {
            "status": "success",
            "count": len(orphaned),
            "max_age_minutes": max_age_minutes,
            "orphaned_jobs": orphaned_info
        }
    
    except Exception as e:
        logger.error(f"Error getting orphaned jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get orphaned jobs: {str(e)}")


@app.post("/jobs/orphaned/cleanup")
async def cleanup_orphaned_jobs_endpoint(
    max_age_minutes: int = Query(30, ge=1, description="Maximum age in minutes for processing jobs"),
    mark_as_failed: bool = Query(True, description="Mark orphaned jobs as failed instead of deleting")
):
    """
    Cleanup orphaned jobs by marking them as failed or deleting them
    
    This is an alternative to POST /admin/cleanup-orphans with more granular control.
    
    **Parameters**:
    - max_age_minutes: Threshold for considering a job orphaned (default: 30)
    - mark_as_failed: If True, marks as failed; if False, deletes completely (default: True)
    
    **Actions**:
    1. Find all orphaned jobs (processing > max_age_minutes)
    2. Either mark as failed with detailed reason, or delete completely
    3. Remove associated files (audio, video, temp)
    4. Calculate space freed
    
    **Returns**:
    - Count of jobs processed
    - List of actions taken per job
    - Total space freed in MB
    
    **Use Cases**:
    - Automated recovery from worker crashes
    - Periodic cleanup of stuck jobs
    - Free up disk space from abandoned tasks
    """
    try:
        orphaned = await redis_store.find_orphaned_jobs(max_age_minutes=max_age_minutes)
        
        if not orphaned:
            return {
                "status": "success",
                "message": "No orphaned jobs found",
                "count": 0,
                "actions": []
            }
        
        actions = []
        space_freed = 0
        
        for job in orphaned:
            age_minutes = (datetime.utcnow() - job.updated_at).total_seconds() / 60
            
            # Remove associated files
            files_deleted = []
            
            # Audio file
            if job.request and job.request.audio_path:
                audio_path = Path(job.request.audio_path)
                if audio_path.exists():
                    size_mb = audio_path.stat().st_size / (1024 * 1024)
                    audio_path.unlink()
                    files_deleted.append({"file": str(audio_path), "size_mb": round(size_mb, 2)})
                    space_freed += size_mb
            
            # Video file
            if job.video_url:
                video_path = Path(job.video_url.replace("/download/", "output_videos/"))
                if video_path.exists():
                    size_mb = video_path.stat().st_size / (1024 * 1024)
                    video_path.unlink()
                    files_deleted.append({"file": str(video_path), "size_mb": round(size_mb, 2)})
                    space_freed += size_mb
            
            # Temp files
            temp_pattern = f"temp/*{job.job_id}*"
            for temp_file in Path("temp").glob(f"*{job.job_id}*"):
                if temp_file.is_file():
                    size_mb = temp_file.stat().st_size / (1024 * 1024)
                    temp_file.unlink()
                    files_deleted.append({"file": str(temp_file), "size_mb": round(size_mb, 2)})
                    space_freed += size_mb
            
            if mark_as_failed:
                # Mark as failed
                job.status = JobStatus.FAILED
                job.error = f"Job orphaned: stuck in processing for {age_minutes:.1f} minutes (auto-recovery)"
                job.updated_at = datetime.utcnow()
                await redis_store.save_job(job)
                
                actions.append({
                    "job_id": job.job_id,
                    "action": "marked_as_failed",
                    "age_minutes": round(age_minutes, 2),
                    "files_deleted": files_deleted,
                    "reason": job.error
                })
            else:
                # Delete completely
                await redis_store.delete_job(job.job_id)
                
                actions.append({
                    "job_id": job.job_id,
                    "action": "deleted",
                    "age_minutes": round(age_minutes, 2),
                    "files_deleted": files_deleted
                })
            
            logger.info(
                f"🧹 Orphaned job {'marked as failed' if mark_as_failed else 'deleted'}: "
                f"{job.job_id} (age: {age_minutes:.1f}min, files: {len(files_deleted)}, "
                f"space freed: {sum(f['size_mb'] for f in files_deleted):.2f}MB)"
            )
        
        return {
            "status": "success",
            "message": f"Cleaned up {len(orphaned)} orphaned job(s)",
            "count": len(orphaned),
            "mode": "mark_as_failed" if mark_as_failed else "delete",
            "max_age_minutes": max_age_minutes,
            "space_freed_mb": round(space_freed, 2),
            "actions": actions
        }
    
    except Exception as e:
        logger.error(f"Error cleaning up orphaned jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cleanup orphaned jobs: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info"
    )
