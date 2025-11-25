"""
Audio Voice Service - FastAPI Main Application
Microserviço de Dublagem e Clonagem de Voz com OpenVoice
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse

from .models import (
    Job, JobStatus, JobMode, VoiceProfile,
    DubbingRequest, VoiceCloneRequest,
    VoiceListResponse, JobListResponse
)
from .processor import VoiceProcessor
from .redis_store import RedisJobStore
from .config import get_settings, is_language_supported, get_voice_presets, is_voice_preset_valid
from .logging_config import setup_logging, get_logger
from .exceptions import (
    VoiceServiceException, InvalidLanguageException, TextTooLongException,
    FileTooLargeException, VoiceProfileNotFoundException, exception_handler
)

# Configuração
settings = get_settings()
setup_logging("audio-voice", settings['log_level'])
logger = get_logger(__name__)

# App FastAPI
app = FastAPI(
    title="Audio Voice Service",
    description="Microserviço para dublagem de texto em áudio e clonagem de vozes",
    version="1.0.0"
)

# Exception handlers
app.add_exception_handler(VoiceServiceException, exception_handler)

# Stores e processors
redis_url = settings['redis_url']
job_store = RedisJobStore(redis_url=redis_url)
processor = VoiceProcessor()
processor.job_store = job_store


@app.get("/")
async def root():
    """Endpoint raiz básico para healthcheck"""
    return {"service": "audio-voice", "status": "running", "version": "1.0.0"}


@app.on_event("startup")
async def startup_event():
    """Inicializa sistema"""
    await job_store.start_cleanup_task()
    logger.info("✅ Audio Voice Service started")


@app.on_event("shutdown")
async def shutdown_event():
    """Para sistema"""
    await job_store.stop_cleanup_task()
    logger.info("🛑 Audio Voice Service stopped")


def submit_processing_task(job: Job):
    """Submete job para Celery"""
    try:
        from .celery_config import celery_app
        from .celery_tasks import dubbing_task, clone_voice_task
        
        if job.mode == JobMode.CLONE_VOICE:
            task = clone_voice_task.apply_async(args=[job.model_dump()], task_id=job.id)
        else:
            task = dubbing_task.apply_async(args=[job.model_dump()], task_id=job.id)
        
        logger.info(f"📤 Job {job.id} sent to Celery: {task.id}")
    except Exception as e:
        logger.error(f"❌ Failed to submit job {job.id} to Celery: {e}")
        asyncio.create_task(processor.process_dubbing_job(job))


# ===== ENDPOINTS DE DUBLAGEM =====

@app.post("/jobs", response_model=Job)
async def create_job(request: DubbingRequest) -> Job:
    """
    Cria job de dublagem
    
    - **mode**: dubbing (genérico) ou dubbing_with_clone (voz clonada)
    - **text**: Texto para dublar (max 10.000 chars)
    - **source_language**: Idioma de origem
    - **voice_preset**: Voz genérica (female_generic, male_deep, etc.)
    - **voice_id**: ID de voz clonada (se mode=dubbing_with_clone)
    """
    try:
        # Validações
        if len(request.text) > settings['max_text_length']:
            raise TextTooLongException(len(request.text), settings['max_text_length'])
        
        if not is_language_supported(request.source_language):
            raise InvalidLanguageException(request.source_language)
        
        if request.mode == JobMode.DUBBING:
            if not request.voice_preset:
                request.voice_preset = 'female_generic'
            if not is_voice_preset_valid(request.voice_preset):
                raise HTTPException(status_code=400, detail=f"Invalid voice preset: {request.voice_preset}")
        
        if request.mode == JobMode.DUBBING_WITH_CLONE:
            if not request.voice_id:
                raise HTTPException(status_code=400, detail="voice_id required for dubbing_with_clone mode")
            # Verifica se voz existe
            voice_profile = job_store.get_voice_profile(request.voice_id)
            if not voice_profile:
                raise VoiceProfileNotFoundException(request.voice_id)
        
        # Cria job
        new_job = Job.create_new(
            mode=request.mode,
            text=request.text,
            source_language=request.source_language,
            target_language=request.target_language,
            voice_preset=request.voice_preset,
            voice_id=request.voice_id
        )
        
        # Verifica cache
        existing_job = job_store.get_job(new_job.id)
        if existing_job and existing_job.status == JobStatus.COMPLETED:
            logger.info(f"Job {new_job.id} found in cache")
            return existing_job
        
        # Salva e processa
        job_store.save_job(new_job)
        submit_processing_task(new_job)
        
        logger.info(f"Job created: {new_job.id}")
        return new_job
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job_status(job_id: str) -> Job:
    """Consulta status de job"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expired")
    return job


@app.get("/jobs/{job_id}/download")
async def download_audio(job_id: str):
    """Download do áudio dublado"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=425, detail=f"Job not ready: {job.status}")
    
    file_path = Path(job.output_file) if job.output_file else None
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=f"dubbed_{job_id}.wav",
        media_type='audio/wav'
    )


@app.get("/jobs", response_model=JobListResponse)
async def list_jobs(limit: int = 20) -> JobListResponse:
    """Lista jobs recentes"""
    jobs = job_store.list_jobs(limit)
    return JobListResponse(total=len(jobs), jobs=jobs)


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Remove job e arquivos"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Remove arquivos
    files_deleted = 0
    if job.input_file:
        try:
            Path(job.input_file).unlink(missing_ok=True)
            files_deleted += 1
        except:
            pass
    
    if job.output_file:
        try:
            Path(job.output_file).unlink(missing_ok=True)
            files_deleted += 1
        except:
            pass
    
    # Remove do Redis
    job_store.delete_job(job_id)
    
    return {"message": "Job deleted", "job_id": job_id, "files_deleted": files_deleted}


# ===== ENDPOINTS DE CLONAGEM DE VOZ =====

@app.post("/voices/clone", response_model=VoiceProfile)
async def clone_voice(
    file: UploadFile = File(...),
    name: str = Form(...),
    language: str = Form(...),
    description: Optional[str] = Form(None)
) -> VoiceProfile:
    """
    Clona voz a partir de amostra de áudio
    
    - **file**: Arquivo de áudio (WAV, MP3, etc.)
    - **name**: Nome do perfil
    - **language**: Idioma base da voz
    - **description**: Descrição opcional
    """
    try:
        # Validações
        if not is_language_supported(language):
            raise InvalidLanguageException(language)
        
        # Lê arquivo
        content = await file.read()
        if len(content) > settings['max_file_size_mb'] * 1024 * 1024:
            raise FileTooLargeException(
                len(content) / (1024 * 1024),
                settings['max_file_size_mb']
            )
        
        # Salva arquivo
        upload_dir = Path(settings['upload_dir'])
        upload_dir.mkdir(exist_ok=True, parents=True)
        
        file_extension = Path(file.filename).suffix if file.filename else '.wav'
        temp_id = f"clone_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        file_path = upload_dir / f"{temp_id}{file_extension}"
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Cria job de clonagem
        clone_job = Job.create_new(
            mode=JobMode.CLONE_VOICE,
            voice_name=name,
            voice_description=description,
            source_language=language
        )
        clone_job.input_file = str(file_path)
        
        job_store.save_job(clone_job)
        submit_processing_task(clone_job)
        
        logger.info(f"Voice clone job created: {clone_job.id}")
        
        # Aguarda processamento (simplificado - em produção usar polling)
        # Para resposta síncrona, processa diretamente
        voice_profile = await processor.process_clone_job(clone_job)
        
        return voice_profile
        
    except Exception as e:
        logger.error(f"Error cloning voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voices", response_model=VoiceListResponse)
async def list_voices(limit: int = 100) -> VoiceListResponse:
    """Lista vozes clonadas"""
    profiles = job_store.list_voice_profiles(limit)
    return VoiceListResponse(total=len(profiles), voices=profiles)


@app.get("/voices/{voice_id}", response_model=VoiceProfile)
async def get_voice(voice_id: str) -> VoiceProfile:
    """Detalhes de voz clonada"""
    profile = job_store.get_voice_profile(voice_id)
    if not profile:
        raise VoiceProfileNotFoundException(voice_id)
    return profile


@app.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    """Remove voz clonada"""
    profile = job_store.get_voice_profile(voice_id)
    if not profile:
        raise VoiceProfileNotFoundException(voice_id)
    
    # Remove arquivos
    try:
        Path(profile.source_audio_path).unlink(missing_ok=True)
        Path(profile.profile_path).unlink(missing_ok=True)
    except:
        pass
    
    # Remove do Redis
    job_store.delete_voice_profile(voice_id)
    
    return {"message": "Voice profile deleted", "voice_id": voice_id}


# ===== ENDPOINTS INFORMATIVOS =====

@app.get("/presets")
async def get_presets():
    """Lista vozes genéricas disponíveis"""
    presets = get_voice_presets()
    return {"presets": presets}


@app.get("/languages")
async def get_languages():
    """Lista idiomas suportados"""
    from .config import get_supported_languages
    languages = get_supported_languages()
    return {"languages": languages, "total": len(languages)}


# ===== ADMIN ENDPOINTS =====

@app.post("/admin/cleanup")
async def cleanup(deep: bool = False):
    """Limpeza de sistema (similar aos outros serviços)"""
    # Implementação simplificada - expandir conforme necessário
    try:
        if deep:
            # FLUSHDB
            job_store.redis.flushdb()
            
            # Remove arquivos
            for dir_path in [Path(settings['upload_dir']), Path(settings['processed_dir']), 
                            Path(settings['temp_dir']), Path(settings['voice_profiles_dir'])]:
                if dir_path.exists():
                    for file in dir_path.iterdir():
                        if file.is_file():
                            file.unlink()
            
            return {"message": "Deep cleanup completed", "redis_flushed": True}
        else:
            await job_store._cleanup_expired()
            return {"message": "Basic cleanup completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/stats")
async def get_stats():
    """Estatísticas do sistema"""
    stats = job_store.get_stats()
    
    # Adiciona info de cache
    processed_path = Path(settings['processed_dir'])
    if processed_path.exists():
        files = list(processed_path.iterdir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        stats["cache"] = {
            "files_count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    
    return stats


@app.get("/health")
async def health_check():
    """Health check profundo"""
    import shutil
    
    health_status = {
        "status": "healthy",
        "service": "audio-voice",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    is_healthy = True
    
    # Redis
    try:
        job_store.redis.ping()
        health_status["checks"]["redis"] = {"status": "ok"}
    except Exception as e:
        health_status["checks"]["redis"] = {"status": "error", "message": str(e)}
        is_healthy = False
    
    # Disco
    try:
        stat = shutil.disk_usage(settings['processed_dir'])
        free_gb = stat.free / (1024**3)
        percent_free = (stat.free / stat.total) * 100
        
        health_status["checks"]["disk_space"] = {
            "status": "ok" if percent_free > 10 else "warning",
            "free_gb": round(free_gb, 2),
            "percent_free": round(percent_free, 2)
        }
        if percent_free <= 5:
            is_healthy = False
    except Exception as e:
        health_status["checks"]["disk_space"] = {"status": "error", "message": str(e)}
        is_healthy = False
    
    # OpenVoice
    try:
        health_status["checks"]["openvoice"] = {
            "status": "ok",
            "device": processor.openvoice_client.device,
            "models_loaded": processor.openvoice_client._models_loaded
        }
    except Exception as e:
        health_status["checks"]["openvoice"] = {"status": "error", "message": str(e)}
    
    health_status["status"] = "healthy" if is_healthy else "unhealthy"
    status_code = 200 if is_healthy else 503
    
    return JSONResponse(content=health_status, status_code=status_code)
