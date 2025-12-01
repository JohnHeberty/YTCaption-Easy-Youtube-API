"""
Audio Voice Service - FastAPI Main Application
Microserviço de Dublagem e Clonagem de Voz com XTTS (Coqui TTS)
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import tempfile
import subprocess

from .models import (
    Job, JobStatus, JobMode, TTSJobMode, VoiceProfile, QualityProfile, VoicePreset,
    DubbingRequest, VoiceCloneRequest,
    VoiceListResponse, JobListResponse, RvcModelResponse, RvcModelListResponse,
    RvcF0Method  # TTSEngine já vem de quality_profiles
)
from .quality_profiles import (
    TTSEngine,  # Import principal
    XTTSQualityProfile,
    F5TTSQualityProfile,
    QualityProfileCreate,
    QualityProfileUpdate,
    QualityProfileList
)
from .quality_profile_manager import quality_profile_manager
from .processor import VoiceProcessor
from .redis_store import RedisJobStore
from .config import get_settings, is_language_supported, get_voice_presets, is_voice_preset_valid, get_supported_languages
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

# Mount WebUI static files
webui_path = Path(__file__).parent / "webui"
if webui_path.exists():
    app.mount("/webui", StaticFiles(directory=str(webui_path)), name="webui")
    logger.info(f"✅ WebUI mounted at /webui from {webui_path}")
else:
    logger.warning(f"⚠️ WebUI directory not found: {webui_path}")

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

# API NÃO carrega modelo XTTS (lazy_load=True)
# Apenas o Celery Worker precisa carregar o modelo (lazy_load=False)
# Isso economiza ~2GB de VRAM e evita CUDA OOM
processor = VoiceProcessor(lazy_load=True)
processor.job_store = job_store

# Inicializa RvcModelManager (Sprint 6)
from .rvc_model_manager import RvcModelManager
rvc_storage_dir = Path(settings.get('rvc_models_dir', '/app/models/rvc'))
processor.rvc_model_manager = RvcModelManager(storage_dir=rvc_storage_dir)


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
async def create_job(
    text: str = Form(..., min_length=1, max_length=10000, description="Texto para dublar (1-10.000 caracteres)"),
    source_language: str = Form(..., description="Idioma do texto (pt, pt-BR, en, es, fr, etc.)"),
    mode: TTSJobMode = Form(..., description="Modo: dubbing (voz genérica) ou dubbing_with_clone (voz clonada)"),
    voice_preset: Optional[VoicePreset] = Form(VoicePreset.female_generic, description="Preset de voz genérica (dropdown, apenas para mode=dubbing)"),
    voice_id: Optional[str] = Form(None, description="ID de voz clonada (apenas para mode=dubbing_with_clone)"),
    target_language: Optional[str] = Form(None, description="Idioma de destino (padrão: mesmo que source_language)"),
    # TTS Engine Selection (Sprint 4)
    tts_engine: TTSEngine = Form(TTSEngine.XTTS, description="TTS engine: 'xtts' (default/stable) or 'f5tts' (experimental/high-quality)"),
    ref_text: Optional[str] = Form(None, description="Reference transcription for F5-TTS voice cloning (auto-transcribed if None)"),
    # Quality Profile (NEW - usa sistema de profiles por engine)
    quality_profile_id: Optional[str] = Form(None, description="Quality profile ID (ex: 'xtts_balanced', 'f5tts_ultra_quality'). Se None, usa padrão do engine."),
    # RVC Parameters (Sprint 7)
    enable_rvc: bool = Form(False, description="Enable RVC voice conversion (default: False)"),
    rvc_model_id: Optional[str] = Form(None, description="RVC model ID (required if enable_rvc=True)"),
    rvc_pitch: int = Form(0, description="Pitch shift in semitones (-12 to +12)"),
    rvc_index_rate: float = Form(0.75, description="Index rate for retrieval (0.0 to 1.0)"),
    rvc_filter_radius: int = Form(3, description="Median filter radius (0 to 7)"),
    rvc_rms_mix_rate: float = Form(0.25, description="RMS mix rate (0.0 to 1.0)"),
    rvc_protect: float = Form(0.33, description="Protect voiceless consonants (0.0 to 0.5)"),
    rvc_f0_method: RvcF0Method = Form(RvcF0Method.RMVPE, description="Pitch extraction method (dropdown)")
) -> Job:
    """
    Cria job de dublagem com validação rigorosa (similar a admin/cleanup)
    
    **Parâmetros validados via Form (evita erros de tipos/valores inválidos):**
    - **text**: Texto para dublar (1-10.000 caracteres)
    - **source_language**: Idioma do texto (validado contra lista de suportados)
    - **mode**: dubbing ou dubbing_with_clone
    - **voice_preset**: Preset de voz genérica (obrigatório se mode=dubbing)
    - **voice_id**: ID de voz clonada (obrigatório se mode=dubbing_with_clone)
    - **target_language**: Idioma de destino (opcional, padrão=source_language)
    
    **TTS Engine Selection (Sprint 4):**
    - **tts_engine**: 'xtts' (default/stable) or 'f5tts' (experimental/high-quality) - DROPDOWN
    - **ref_text**: Reference transcription for F5-TTS (auto-transcribed if None)
    
    **Quality Profile (NEW):**
    - **quality_profile_id**: ID do perfil de qualidade (ex: 'xtts_balanced', 'f5tts_ultra_quality')
    - Se None, usa perfil padrão do engine selecionado
    - Use GET /quality-profiles para listar perfis disponíveis
    
    **RVC Parameters (Sprint 7):**
    - **enable_rvc**: Enable RVC voice conversion (default: False)
    - **rvc_model_id**: RVC model ID (required if enable_rvc=True)
    - **rvc_pitch**: Pitch shift in semitones (-12 to +12, default: 0)
    - **rvc_index_rate**: Index rate for retrieval (0.0-1.0, default: 0.75)
    - **rvc_filter_radius**: Median filter radius (0-7, default: 3)
    - **rvc_rms_mix_rate**: RMS mix rate (0.0-1.0, default: 0.25)
    - **rvc_protect**: Protect voiceless consonants (0.0-0.5, default: 0.33)
    - **rvc_f0_method**: Pitch extraction method - DROPDOWN (rmvpe/fcpe/pm/harvest/dio/crepe)
    """
    try:
        # Validações adicionais
        if not is_language_supported(source_language):
            raise InvalidLanguageException(source_language)
        
        # Define target_language se não fornecido
        if not target_language:
            target_language = source_language
        
        # Validações específicas por modo (comparar com string value para compatibilidade)
        if mode.value == "dubbing":
            if not voice_preset:
                voice_preset = VoicePreset.female_generic
            if not is_voice_preset_valid(voice_preset.value if isinstance(voice_preset, VoicePreset) else voice_preset):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid voice preset: {voice_preset}. Valid presets: {get_voice_presets()}"
                )
        
        if mode.value == "dubbing_with_clone":
            if not voice_id:
                raise HTTPException(
                    status_code=400,
                    detail="voice_id is required when mode=dubbing_with_clone"
                )
            # Verifica se voz existe
            voice_profile = job_store.get_voice_profile(voice_id)
            if not voice_profile:
                raise VoiceProfileNotFoundException(voice_id)
        
        # Validações RVC (Sprint 7)
        if enable_rvc:
            if not rvc_model_id:
                raise HTTPException(
                    status_code=400,
                    detail="rvc_model_id is required when enable_rvc=True"
                )
            
            # Verifica se modelo RVC existe
            rvc_model = processor.rvc_model_manager.get_model(rvc_model_id)
            if not rvc_model:
                raise HTTPException(
                    status_code=404,
                    detail=f"RVC model not found: {rvc_model_id}"
                )
            
            # Validar ranges de parâmetros RVC
            if not -12 <= rvc_pitch <= 12:
                raise HTTPException(status_code=400, detail="rvc_pitch must be between -12 and +12")
            if not 0.0 <= rvc_index_rate <= 1.0:
                raise HTTPException(status_code=400, detail="rvc_index_rate must be between 0.0 and 1.0")
            if not 0 <= rvc_filter_radius <= 7:
                raise HTTPException(status_code=400, detail="rvc_filter_radius must be between 0 and 7")
            if not 0.0 <= rvc_rms_mix_rate <= 1.0:
                raise HTTPException(status_code=400, detail="rvc_rms_mix_rate must be between 0.0 and 1.0")
            if not 0.0 <= rvc_protect <= 0.5:
                raise HTTPException(status_code=400, detail="rvc_protect must be between 0.0 and 0.5")
        
        # Converte TTSJobMode para JobMode (são compatíveis por valor)
        job_mode = JobMode(mode.value) if isinstance(mode, TTSJobMode) else mode
        
        # Cria job
        new_job = Job.create_new(
            mode=job_mode,
            text=text,
            source_language=source_language,
            target_language=target_language,
            voice_preset=voice_preset.value if isinstance(voice_preset, VoicePreset) else (voice_preset if voice_preset else None),
            voice_id=voice_id,
            tts_engine=tts_engine.value if isinstance(tts_engine, TTSEngine) else tts_engine,  # Converte enum para string se necessário
            ref_text=ref_text
        )
        
        # Adiciona quality_profile_id (novo sistema)
        if quality_profile_id:
            # Validar se profile existe
            engine_name = tts_engine.value if isinstance(tts_engine, TTSEngine) else tts_engine
            engine_enum = TTSEngine(engine_name) if isinstance(engine_name, str) else engine_name
            profile = quality_profile_manager.get_profile(engine_enum, quality_profile_id)
            if not profile:
                raise HTTPException(
                    status_code=404,
                    detail=f"Quality profile not found: {quality_profile_id}"
                )
            new_job.quality_profile = quality_profile_id
        else:
            # Usa perfil padrão do engine
            engine_name = tts_engine.value if isinstance(tts_engine, TTSEngine) else tts_engine
            default_profile_id = f"{engine_name}_balanced"
            new_job.quality_profile = default_profile_id
        
        # Adiciona parâmetros RVC (Sprint 7)
        if enable_rvc:
            new_job.enable_rvc = True
            new_job.rvc_model_id = rvc_model_id
            new_job.rvc_pitch = rvc_pitch
            new_job.rvc_index_rate = rvc_index_rate
            new_job.rvc_filter_radius = rvc_filter_radius
            new_job.rvc_rms_mix_rate = rvc_rms_mix_rate
            new_job.rvc_protect = rvc_protect
            new_job.rvc_f0_method = rvc_f0_method.value if isinstance(rvc_f0_method, RvcF0Method) else rvc_f0_method  # Converte enum para string se necessário
        
        # Verifica cache
        existing_job = job_store.get_job(new_job.id)
        if existing_job and existing_job.status == JobStatus.COMPLETED:
            logger.info(f"Job {new_job.id} found in cache")
            return existing_job
        
        # Salva e processa
        job_store.save_job(new_job)
        submit_processing_task(new_job)
        
        logger.info(f"Job created: {new_job.id} (RVC: {enable_rvc})")
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
    description: Optional[str] = Form(None),
    tts_engine: TTSEngine = Form(TTSEngine.XTTS, description="TTS engine: 'xtts' or 'f5tts'"),
    ref_text: Optional[str] = Form(None, description="Reference transcription for F5-TTS (auto-transcribed if None)")
):
    """
    Clona voz a partir de amostra de áudio (ASYNC)
    
    Retorna imediatamente com job_id. Use polling para verificar status.
    
    - **file**: Arquivo de áudio (WAV, MP3, etc.)
    - **name**: Nome do perfil
    - **language**: Idioma base da voz
    - **description**: Descrição opcional
    - **tts_engine**: 'xtts' (default) or 'f5tts' (experimental)
    - **ref_text**: Reference transcription for F5-TTS (auto-transcribed if None)
    
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
            source_language=language,
            tts_engine=tts_engine.value if isinstance(tts_engine, TTSEngine) else tts_engine,  # Converte enum para string se necessário
            ref_text=ref_text
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


# ===== RVC MODEL MANAGEMENT ENDPOINTS (SPRINT 7) =====

@app.post("/rvc-models", response_model=RvcModelResponse, status_code=201)
async def upload_rvc_model(
    name: str = Form(..., min_length=1, max_length=100, description="Model name"),
    description: Optional[str] = Form(None, max_length=500, description="Model description"),
    pth_file: UploadFile = File(..., description=".pth file (PyTorch checkpoint)"),
    index_file: Optional[UploadFile] = File(None, description=".index file (FAISS index, optional)")
):
    """
    Upload RVC model for voice conversion
    
    **Required:**
    - **name**: Model name (unique identifier)
    - **pth_file**: PyTorch checkpoint file (.pth)
    
    **Optional:**
    - **description**: Model description
    - **index_file**: FAISS index file (.index) for better quality
    
    **Returns:** Model metadata with ID for use in /jobs endpoint
    """
    try:
        # Salvar arquivo .pth temporariamente
        temp_dir = Path(settings['temp_dir'])
        temp_dir.mkdir(exist_ok=True, parents=True)
        
        # Salvar .pth
        pth_temp_path = temp_dir / f"upload_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.pth"
        pth_content = await pth_file.read()
        with open(pth_temp_path, 'wb') as f:
            f.write(pth_content)
        
        # Salvar .index se fornecido
        index_temp_path = None
        if index_file:
            index_temp_path = temp_dir / f"upload_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.index"
            index_content = await index_file.read()
            with open(index_temp_path, 'wb') as f:
                f.write(index_content)
        
        # Upload via RvcModelManager
        model_metadata = await processor.rvc_model_manager.upload_model(
            name=name,
            pth_file=pth_temp_path,
            index_file=index_temp_path,
            description=description
        )
        
        # Limpar arquivos temporários
        pth_temp_path.unlink(missing_ok=True)
        if index_temp_path:
            index_temp_path.unlink(missing_ok=True)
        
        logger.info(f"RVC model uploaded: {model_metadata['id']} ({name})")
        
        return RvcModelResponse(**model_metadata)
        
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")
    except Exception as e:
        logger.error(f"Error uploading RVC model: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/rvc-models", response_model=RvcModelListResponse)
async def list_rvc_models(
    sort_by: str = Query(default="created_at", description="Sort by: name, created_at, file_size_mb")
) -> RvcModelListResponse:
    """
    List all RVC models
    
    **Query Parameters:**
    - **sort_by**: Sorting field (name, created_at, file_size_mb)
    
    **Returns:** List of RVC models with metadata
    """
    try:
        models = processor.rvc_model_manager.list_models(sort_by=sort_by)
        return RvcModelListResponse(
            total=len(models),
            models=[RvcModelResponse(**m) for m in models]
        )
    except Exception as e:
        logger.error(f"Error listing RVC models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@app.get("/rvc-models/stats")
async def get_rvc_models_stats():
    """
    Get RVC models statistics
    
    **Returns:** Statistics about RVC models (count, size, etc.)
    """
    try:
        # Check if RVC model manager is available
        if not hasattr(processor, 'rvc_model_manager') or processor.rvc_model_manager is None:
            return {
                'total_models': 0,
                'models_with_index': 0,
                'total_size_bytes': 0,
                'total_size_mb': 0.0,
                'message': 'RVC model manager not initialized'
            }
        
        stats = processor.rvc_model_manager.get_model_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting RVC stats: {e}", exc_info=True)
        # Return empty stats instead of 500 error
        return {
            'total_models': 0,
            'models_with_index': 0,
            'total_size_bytes': 0,
            'total_size_mb': 0.0,
            'error': str(e)
        }


@app.get("/rvc-models/{model_id}", response_model=RvcModelResponse)
async def get_rvc_model(model_id: str) -> RvcModelResponse:
    """
    Get RVC model details by ID
    
    **Parameters:**
    - **model_id**: Model unique identifier (MD5 hash)
    
    **Returns:** Model metadata
    """
    try:
        model = processor.rvc_model_manager.get_model(model_id)
        if not model:
            raise HTTPException(status_code=404, detail=f"RVC model not found: {model_id}")
        return RvcModelResponse(**model)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting RVC model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/rvc-models/{model_id}")
async def delete_rvc_model(model_id: str):
    """
    Delete RVC model by ID
    
    **Parameters:**
    - **model_id**: Model unique identifier
    
    **Returns:** Success message
    """
    try:
        success = await processor.rvc_model_manager.delete_model(model_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"RVC model not found: {model_id}")
        
        logger.info(f"RVC model deleted: {model_id}")
        return {"message": "RVC model deleted", "model_id": model_id}
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting RVC model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINTS INFORMATIVOS =====

@app.get("/presets")
async def get_presets():
    """Lista vozes genéricas disponíveis"""
    presets = get_voice_presets()
    return {"presets": presets}


@app.get("/languages")
async def get_languages():
    """Lista idiomas suportados"""
    languages = get_supported_languages()
    return {
        "languages": languages,
        "total": len(languages),
        "examples": {
            "Portuguese (Brazil)": "pt-BR",
            "Portuguese (Portugal)": "pt",
            "English": "en",
            "Spanish": "es",
            "French": "fr"
        }
    }


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
    
    # TTS Engine (XTTS)
    try:
        tts_status = {
            "status": "ok",
            "engine": "XTTS",
            "device": processor.engine.device,
            "model": processor.engine.model_name
        }
        health_status["checks"]["tts_engine"] = tts_status
    except Exception as e:
        health_status["checks"]["tts_engine"] = {"status": "error", "message": str(e)}
    
    health_status["status"] = "healthy" if is_healthy else "unhealthy"
    status_code = 200 if is_healthy else 503
    
    return JSONResponse(content=health_status, status_code=status_code)


# =============================================================================
# Feature Flags Endpoints
# =============================================================================

@app.get("/feature-flags", tags=["feature-flags"])
async def get_feature_flags():
    """
    Retorna todas as feature flags e seus status atuais.
    
    Útil para debugging e monitoramento do rollout gradual.
    """
    from .feature_flags import get_feature_flag_manager
    
    manager = get_feature_flag_manager()
    flags = manager.get_all_flags()
    
    return {
        "feature_flags": flags,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/feature-flags/{feature_name}", tags=["feature-flags"])
async def check_feature_flag(
    feature_name: str,
    user_id: Optional[str] = Query(None, description="User ID para verificar acesso")
):
    """
    Verifica se uma feature específica está habilitada.
    
    Args:
        feature_name: Nome da feature (ex: 'f5tts_engine')
        user_id: ID do usuário (opcional)
    
    Returns:
        Status da feature para o usuário específico ou globalmente
    """
    from .feature_flags import get_feature_flag_manager
    
    manager = get_feature_flag_manager()
    flag = manager.get_flag(feature_name)
    
    if not flag:
        raise HTTPException(
            status_code=404,
            detail=f"Feature flag não encontrada: {feature_name}"
        )
    
    is_enabled = manager.is_enabled(feature_name, user_id)
    
    return {
        "feature_name": feature_name,
        "user_id": user_id,
        "enabled": is_enabled,
        "flag_details": {
            "phase": flag.phase.value,
            "percentage": flag.percentage,
            "description": flag.description
        },
        "timestamp": datetime.now().isoformat()
    }


# ===================================================================
# QUALITY PROFILES ENDPOINTS
# ===================================================================

@app.get(
    "/quality-profiles",
    response_model=QualityProfileList,
    summary="Listar perfis de qualidade",
    description="Lista todos os perfis de qualidade agrupados por engine (XTTS e F5-TTS)"
)
async def list_quality_profiles():
    """
    Lista todos os perfis de qualidade disponíveis.
    
    Retorna perfis separados por engine:
    - xtts_profiles: Perfis otimizados para XTTS
    - f5tts_profiles: Perfis otimizados para F5-TTS
    
    Cada perfil contém parâmetros específicos do seu engine.
    """
    try:
        profiles = quality_profile_manager.list_all_profiles()
        
        return QualityProfileList(
            xtts_profiles=profiles["xtts"],
            f5tts_profiles=profiles["f5tts"],
            total_count=len(profiles["xtts"]) + len(profiles["f5tts"])
        )
    except Exception as e:
        logger.error(f"Erro ao listar perfis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/quality-profiles/{engine}",
    summary="Listar perfis por engine",
    description="Lista perfis de qualidade de um engine específico"
)
async def list_profiles_by_engine(
    engine: TTSEngine
):
    """
    Lista perfis de qualidade de um engine específico.
    
    Args:
        engine: xtts ou f5tts
    
    Returns:
        Lista de perfis do engine
    """
    try:
        profiles = quality_profile_manager.list_profiles(engine)
        return {"engine": engine, "profiles": profiles, "count": len(profiles)}
    except Exception as e:
        logger.error(f"Erro ao listar perfis do engine {engine}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/quality-profiles/{engine}/{profile_id}",
    summary="Buscar perfil específico",
    description="Busca perfil de qualidade por ID"
)
async def get_quality_profile(
    engine: TTSEngine,
    profile_id: str
):
    """
    Busca perfil de qualidade por ID.
    
    Args:
        engine: xtts ou f5tts
        profile_id: ID do perfil
    
    Returns:
        Perfil encontrado
    """
    try:
        profile = quality_profile_manager.get_profile(engine, profile_id)
        
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Perfil {profile_id} não encontrado para engine {engine}"
            )
        
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar perfil: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/quality-profiles",
    status_code=201,
    summary="Criar perfil de qualidade",
    description="Cria novo perfil de qualidade customizado"
)
async def create_quality_profile(
    request: QualityProfileCreate
):
    """
    Cria novo perfil de qualidade.
    
    Args:
        request: Dados do perfil
            - name: Nome do perfil
            - description: Descrição (opcional)
            - engine: xtts ou f5tts
            - is_default: Se é perfil padrão
            - parameters: Parâmetros específicos do engine
    
    Returns:
        Perfil criado
    
    Example XTTS:
        {
            "name": "Meu Perfil XTTS",
            "description": "Perfil customizado",
            "engine": "xtts",
            "is_default": false,
            "parameters": {
                "temperature": 0.8,
                "repetition_penalty": 1.5,
                "top_p": 0.9,
                "top_k": 60,
                "length_penalty": 1.2,
                "speed": 1.0,
                "enable_text_splitting": false
            }
        }
    
    Example F5-TTS:
        {
            "name": "Meu Perfil F5-TTS",
            "description": "Alta qualidade sem ruído",
            "engine": "f5tts",
            "is_default": false,
            "parameters": {
                "nfe_step": 48,
                "cfg_scale": 2.5,
                "denoise_audio": true,
                "noise_reduction_strength": 0.9,
                "enhance_prosody": true,
                "apply_deessing": true
            }
        }
    """
    try:
        import hashlib
        from datetime import datetime
        
        # Gerar ID único
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        engine_str = request.engine.value if hasattr(request.engine, 'value') else str(request.engine)
        profile_id = f"{engine_str}_{hashlib.md5(f'{request.name}_{timestamp}'.encode()).hexdigest()[:12]}"
        
        # Criar perfil baseado no engine
        if request.engine == TTSEngine.XTTS:
            profile = XTTSQualityProfile(
                id=profile_id,
                name=request.name,
                description=request.description,
                engine=request.engine,
                is_default=request.is_default,
                **request.parameters
            )
        else:  # F5TTS
            profile = F5TTSQualityProfile(
                id=profile_id,
                name=request.name,
                description=request.description,
                engine=request.engine,
                is_default=request.is_default,
                **request.parameters
            )
        
        # Salvar
        created_profile = quality_profile_manager.create_profile(profile)
        
        logger.info(f"✅ Perfil criado: {created_profile.id} ({created_profile.engine})")
        return created_profile
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao criar perfil: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/quality-profiles/{engine}",
    status_code=201,
    summary="Criar perfil de qualidade (engine no path)",
    description="Cria novo perfil de qualidade - engine extraído do path"
)
async def create_quality_profile_with_engine(
    engine: TTSEngine,
    request: QualityProfileCreate
):
    """
    Wrapper para create_quality_profile que extrai engine do path.
    Compatibilidade com frontend que envia engine na URL.
    """
    # Override engine do request com o do path
    request.engine = engine
    return await create_quality_profile(request)



@app.patch(
    "/quality-profiles/{engine}/{profile_id}",
    summary="Atualizar perfil",
    description="Atualiza perfil de qualidade existente"
)
async def update_quality_profile(
    engine: TTSEngine,
    profile_id: str,
    request: QualityProfileUpdate
):
    """
    Atualiza perfil de qualidade.
    
    Args:
        engine: xtts ou f5tts
        profile_id: ID do perfil
        request: Campos a atualizar
    
    Returns:
        Perfil atualizado
    """
    try:
        # Preparar updates
        updates = {}
        if request.name is not None:
            updates['name'] = request.name
        if request.description is not None:
            updates['description'] = request.description
        if request.is_default is not None:
            updates['is_default'] = request.is_default
        if request.parameters is not None:
            updates.update(request.parameters)
        
        # Atualizar
        updated_profile = quality_profile_manager.update_profile(
            engine, profile_id, updates
        )
        
        if not updated_profile:
            raise HTTPException(
                status_code=404,
                detail=f"Perfil {profile_id} não encontrado"
            )
        
        logger.info(f"✅ Perfil atualizado: {profile_id}")
        return updated_profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar perfil: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete(
    "/quality-profiles/{engine}/{profile_id}",
    status_code=204,
    summary="Deletar perfil",
    description="Deleta perfil de qualidade (não permite deletar perfis padrão)"
)
async def delete_quality_profile(
    engine: TTSEngine,
    profile_id: str
):
    """
    Deleta perfil de qualidade.
    
    Args:
        engine: xtts ou f5tts
        profile_id: ID do perfil
    
    Raises:
        400: Se tentar deletar perfil padrão
        404: Se perfil não encontrado
    """
    try:
        deleted = quality_profile_manager.delete_profile(engine, profile_id)
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Perfil {profile_id} não encontrado"
            )
        
        logger.info(f"✅ Perfil deletado: {profile_id}")
        return
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar perfil: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/quality-profiles/{engine}/{profile_id}/set-default",
    summary="Definir perfil padrão",
    description="Define perfil como padrão do engine (remove padrão de outros)"
)
async def set_default_quality_profile(
    engine: TTSEngine,
    profile_id: str
):
    """
    Define perfil como padrão do engine.
    
    Args:
        engine: xtts ou f5tts
        profile_id: ID do perfil
    
    Returns:
        Perfil atualizado
    """
    try:
        quality_profile_manager.set_default_profile(engine, profile_id)
        profile = quality_profile_manager.get_profile(engine, profile_id)
        
        logger.info(f"✅ Perfil padrão definido: {profile_id} ({engine})")
        return profile
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao definir perfil padrão: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/quality-profiles/{engine}/{profile_id}/duplicate",
    status_code=201,
    summary="Duplicar perfil de qualidade",
    description="Cria cópia de um perfil existente com novo nome"
)
async def duplicate_quality_profile(
    engine: TTSEngine,
    profile_id: str,
    new_name: str = None
):
    """
    Duplica perfil existente.
    
    Args:
        engine: xtts ou f5tts
        profile_id: ID do perfil a duplicar
        new_name: Nome para o novo perfil (opcional, usa "Copy of {original}")
    
    Returns:
        Novo perfil criado
    """
    try:
        import hashlib
        from datetime import datetime
        
        # Buscar perfil original
        original = quality_profile_manager.get_profile(engine, profile_id)
        if not original:
            raise HTTPException(
                status_code=404,
                detail=f"Perfil {profile_id} não encontrado"
            )
        
        # Gerar novo ID e nome
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        engine_str = engine.value if hasattr(engine, 'value') else str(engine)
        new_profile_id = f"{engine_str}_{hashlib.md5(f'{original.name}_copy_{timestamp}'.encode()).hexdigest()[:12]}"
        final_name = new_name or f"Copy of {original.name}"
        
        # Criar novo perfil com mesmos parâmetros
        if engine == TTSEngine.XTTS:
            new_profile = XTTSQualityProfile(
                id=new_profile_id,
                name=final_name,
                description=f"Duplicado de {original.name}",
                engine=engine,
                is_default=False,  # Duplicatas nunca são padrão
                temperature=original.temperature,
                repetition_penalty=original.repetition_penalty,
                top_p=original.top_p,
                top_k=original.top_k,
                length_penalty=original.length_penalty,
                speed=original.speed,
                enable_text_splitting=original.enable_text_splitting
            )
        else:  # F5TTS
            new_profile = F5TTSQualityProfile(
                id=new_profile_id,
                name=final_name,
                description=f"Duplicado de {original.name}",
                engine=engine,
                is_default=False,
                nfe_step=original.nfe_step,
                cfg_scale=original.cfg_scale,
                sway_sampling_coef=original.sway_sampling_coef,
                speed=original.speed,
                denoise_audio=original.denoise_audio,
                noise_reduction_strength=original.noise_reduction_strength,
                apply_normalization=original.apply_normalization,
                target_loudness=original.target_loudness,
                apply_declipping=original.apply_declipping,
                apply_deessing=original.apply_deessing,
                deessing_frequency=original.deessing_frequency,
                add_breathing=original.add_breathing,
                breathing_strength=original.breathing_strength,
                pause_optimization=original.pause_optimization
            )
        
        # Salvar
        created = quality_profile_manager.create_profile(new_profile)
        
        logger.info(f"✅ Perfil duplicado: {profile_id} → {new_profile_id}")
        return created
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao duplicar perfil: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ===== WEB UI =====

from fastapi.responses import HTMLResponse

@app.get("/webui", response_class=HTMLResponse)
async def webui():
    """Full Control Panel - 100% API Coverage"""
    html_path = Path(__file__).parent / "webui" / "index.html"

    # Se arquivo existe, serve ele
    with open(html_path, 'r', encoding='utf-8') as f:
        return HTMLResponse(content=f.read())


# webui já está montada em /webui acima

