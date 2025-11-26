"""
Audio Voice Service - FastAPI Main Application
Microserviço de Dublagem e Clonagem de Voz com OpenVoice
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import tempfile
import subprocess

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

# Formatos de áudio suportados para download
SUPPORTED_AUDIO_FORMATS = {
    'wav': {'mime': 'audio/wav', 'extension': '.wav'},
    'mp3': {'mime': 'audio/mpeg', 'extension': '.mp3'},
    'ogg': {'mime': 'audio/ogg', 'extension': '.ogg'},
    'flac': {'mime': 'audio/flac', 'extension': '.flac'},
    'm4a': {'mime': 'audio/mp4', 'extension': '.m4a'},
    'opus': {'mime': 'audio/opus', 'extension': '.opus'}
}

def convert_audio_format(input_path: Path, output_format: str) -> Path:
    """
    Converte áudio para formato especificado usando ffmpeg.
    Retorna caminho do arquivo temporário (deve ser limpo após uso).
    
    Args:
        input_path: Caminho do arquivo WAV original
        output_format: Formato de saída (mp3, ogg, flac, etc.)
    
    Returns:
        Path do arquivo convertido em diretório temp
    
    Raises:
        HTTPException: Se formato não suportado ou conversão falhar
    """
    if output_format not in SUPPORTED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {output_format}. Suportados: {list(SUPPORTED_AUDIO_FORMATS.keys())}"
        )
    
    # Se já é WAV, retorna o original
    if output_format == 'wav':
        return input_path
    
    # Cria arquivo temporário
    temp_dir = Path(settings['temp_dir'])
    temp_dir.mkdir(exist_ok=True, parents=True)
    
    extension = SUPPORTED_AUDIO_FORMATS[output_format]['extension']
    temp_file = temp_dir / f"convert_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{extension}"
    
    try:
        # Configurações de conversão por formato
        ffmpeg_opts = {
            'mp3': ['-codec:a', 'libmp3lame', '-qscale:a', '2'],  # VBR ~190 kbps
            'ogg': ['-codec:a', 'libvorbis', '-qscale:a', '6'],   # VBR ~192 kbps
            'flac': ['-codec:a', 'flac'],                         # Lossless
            'm4a': ['-codec:a', 'aac', '-b:a', '192k'],           # AAC 192 kbps
            'opus': ['-codec:a', 'libopus', '-b:a', '128k']       # Opus 128 kbps
        }
        
        cmd = [
            'ffmpeg', '-y',
            '-i', str(input_path),
            *ffmpeg_opts.get(output_format, []),
            str(temp_file)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"Falha na conversão de áudio: {result.stderr[:200]}"
            )
        
        if not temp_file.exists():
            raise HTTPException(
                status_code=500,
                detail="Arquivo convertido não foi criado"
            )
        
        logger.info(f"Audio converted: {input_path.name} -> {temp_file.name} ({output_format})")
        return temp_file
        
    except subprocess.TimeoutExpired:
        if temp_file.exists():
            temp_file.unlink()
        raise HTTPException(
            status_code=500,
            detail="Timeout na conversão de áudio (>30s)"
        )
    except Exception as e:
        if temp_file.exists():
            temp_file.unlink()
        logger.error(f"Conversion error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao converter áudio: {str(e)}"
        )

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
        from .logging_config import log_job_serialization, log_dict_serialization
        
        # DEBUG: Log do job antes de serializar
        log_job_serialization(job, "BEFORE_SERIALIZE", logger)
        
        # Serializa com exclude_none=False para incluir todos os campos
        job_dict = job.model_dump(mode='json', exclude_none=False)
        
        # DEBUG: Log do dict serializado
        log_dict_serialization(job_dict, "AFTER_SERIALIZE", logger)
        logger.info(f"🔍 Enviando para Celery: {job_dict.get('id')} input_file={job_dict.get('input_file')}")
        
        if job.mode == JobMode.CLONE_VOICE:
            task = clone_voice_task.apply_async(args=[job_dict], task_id=job.id)
        else:
            task = dubbing_task.apply_async(args=[job_dict], task_id=job.id)
        
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


@app.get("/jobs/{job_id}/formats")
async def get_available_formats(job_id: str):
    """
    Lista formatos de áudio disponíveis para download.
    
    Returns:
        Lista de formatos suportados com informações de qualidade
    """
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=425, detail=f"Job not ready: {job.status}")
    
    formats = [
        {
            "format": "wav",
            "name": "WAV (Original)",
            "mime_type": "audio/wav",
            "quality": "Lossless",
            "description": "Formato original sem compressão"
        },
        {
            "format": "mp3",
            "name": "MP3",
            "mime_type": "audio/mpeg",
            "quality": "VBR ~190 kbps",
            "description": "Compressão com perdas, alta compatibilidade"
        },
        {
            "format": "ogg",
            "name": "OGG Vorbis",
            "mime_type": "audio/ogg",
            "quality": "VBR ~192 kbps",
            "description": "Compressão eficiente, código aberto"
        },
        {
            "format": "flac",
            "name": "FLAC",
            "mime_type": "audio/flac",
            "quality": "Lossless",
            "description": "Compressão sem perdas, tamanho menor que WAV"
        },
        {
            "format": "m4a",
            "name": "M4A (AAC)",
            "mime_type": "audio/mp4",
            "quality": "192 kbps",
            "description": "AAC, ótima qualidade/tamanho"
        },
        {
            "format": "opus",
            "name": "OPUS",
            "mime_type": "audio/opus",
            "quality": "128 kbps",
            "description": "Melhor compressão para voz"
        }
    ]
    
    return {
        "job_id": job_id,
        "formats": formats,
        "download_url_template": f"/jobs/{job_id}/download?format={{format}}"
    }


@app.get("/jobs/{job_id}/download")
async def download_audio(
    job_id: str,
    format: str = Query(default="wav", description="Formato de áudio: wav, mp3, ogg, flac, m4a, opus"),
    background_tasks: BackgroundTasks = None
):
    """
    Download do áudio em formato especificado.
    
    Args:
        job_id: ID do job
        format: Formato de áudio desejado (padrão: wav)
        background_tasks: Background tasks for cleanup
    
    Returns:
        Arquivo de áudio no formato solicitado
    
    Note:
        Arquivos convertidos são criados temporariamente e deletados após envio
    """
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=425, detail=f"Job not ready: {job.status}")
    
    original_file = Path(job.output_file) if job.output_file else None
    if not original_file or not original_file.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Normaliza formato
    format = format.lower().strip()
    
    try:
        # Converte para formato solicitado (ou retorna original se WAV)
        converted_file = convert_audio_format(original_file, format)
        
        # Prepara response
        format_info = SUPPORTED_AUDIO_FORMATS[format]
        extension = format_info['extension']
        filename = f"dubbed_{job_id}{extension}"
        
        # Se arquivo convertido (não é o original WAV), agenda limpeza
        if converted_file != original_file and background_tasks:
            def cleanup_file():
                try:
                    if converted_file.exists():
                        converted_file.unlink()
                        logger.debug(f"Cleaned up temp file: {converted_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file: {e}")
            
            background_tasks.add_task(cleanup_file)
        
        # FileResponse
        return FileResponse(
            path=converted_file,
            filename=filename,
            media_type=format_info['mime']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao preparar download: {str(e)}"
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

@app.post("/voices/clone", status_code=202)
async def clone_voice(
    file: UploadFile = File(...),
    name: str = Form(...),
    language: str = Form(...),
    description: Optional[str] = Form(None)
):
    """
    Clona voz a partir de amostra de áudio (ASYNC)
    
    Retorna imediatamente com job_id. Use polling para verificar status.
    
    - **file**: Arquivo de áudio (WAV, MP3, etc.)
    - **name**: Nome do perfil
    - **language**: Idioma base da voz
    - **description**: Descrição opcional
    
    **Response:** HTTP 202 com job_id
    **Polling:** GET /jobs/{job_id} até status="completed"
    **Result:** GET /voices/{voice_id} quando completo
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
        # IMPORTANTE: Setar input_file ANTES de salvar/enviar
        clone_job.input_file = str(file_path)
        
        # DEBUG: Verificar antes de serializar
        logger.debug(f"🔍 Job antes de salvar: input_file={clone_job.input_file}")
        
        # Salva job no Redis com input_file preenchido
        job_store.save_job(clone_job)
        
        # Envia para Celery (job já tem input_file)
        submit_processing_task(clone_job)
        
        logger.info(f"Voice clone job created: {clone_job.id}")
        
        # Retorna job para polling (padrão assíncrono)
        return JSONResponse(
            status_code=202,  # Accepted
            content={
                "message": "Voice cloning job queued",
                "job_id": clone_job.id,
                "status": clone_job.status,
                "poll_url": f"/jobs/{clone_job.id}"
            }
        )
        
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
    
    # TTS Engine (XTTS / F5-TTS / OpenVoice)
    try:
        # Obtém engine atual via factory pattern
        engine = processor._get_tts_engine()
        
        # Determina qual engine está ativa
        if processor.use_xtts:
            engine_name = "XTTS"
        else:
            engine_name = os.getenv('TTS_ENGINE', 'openvoice')
        
        tts_status = {
            "status": "ok",
            "engine": engine_name,
            "use_xtts": processor.use_xtts
        }
        
        # Detalhes do engine se disponível
        if hasattr(engine, 'device'):
            tts_status["device"] = engine.device
        if hasattr(engine, 'model_name'):
            tts_status["model_name"] = engine.model_name
        if hasattr(engine, '_models_loaded'):
            tts_status["models_loaded"] = engine._models_loaded
        
        health_status["checks"]["tts_engine"] = tts_status
    except Exception as e:
        health_status["checks"]["tts_engine"] = {"status": "error", "message": str(e)}
    
    health_status["status"] = "healthy" if is_healthy else "unhealthy"
    status_code = 200 if is_healthy else 503
    
    return JSONResponse(content=health_status, status_code=status_code)
