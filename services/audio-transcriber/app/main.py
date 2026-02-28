import asyncio
import os
import time
from datetime import datetime
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Request, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import List, Optional
import logging

# Common library imports
from common.log_utils import setup_structured_logging, get_logger
from common.exception_handlers import setup_exception_handlers

from .domain.models import Job, JobRequest, JobStatus, TranscriptionResponse, WhisperEngine
from .services.processor import TranscriptionProcessor
from .infrastructure.redis_store import RedisJobStore
from .domain.exceptions import AudioTranscriptionException, ServiceException, exception_handler
from .core.config import get_settings, get_supported_languages, is_language_supported, get_whisper_models

# Configuração de logging
settings = get_settings()
setup_structured_logging(
    service_name="audio-transcriber",
    log_level=settings['log_level'],
    log_dir=settings.get('log_dir', './logs'),
    json_format=(settings.get('log_format', 'json') == 'json')
)
logger = get_logger(__name__)

# Instâncias globais
app = FastAPI(
    title="Audio Transcription Service",
    description="Microserviço para transcrição de áudio com cache de 24h",
    version="2.0.0"
)

# Setup exception handlers
setup_exception_handlers(app, debug=settings.get('debug', False))

# Exception handlers - mantidos para compatibilidade
app.add_exception_handler(AudioTranscriptionException, exception_handler)
app.add_exception_handler(ServiceException, exception_handler)

# Usa Redis como store compartilhado
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
job_store = RedisJobStore(redis_url=redis_url)
processor = TranscriptionProcessor()

# Injeta referência do job_store no processor para updates de progresso
processor.job_store = job_store


@app.on_event("startup")
async def startup_event():
    """Inicializa sistema"""
    try:
        await job_store.start_cleanup_task()
        logger.info("Audio Transcription Service iniciado com sucesso")
        
        # Carrega modelo no startup se configurado (padrão: True)
        preload_model = os.getenv('WHISPER_PRELOAD_MODEL', 'true').lower() == 'true'
        
        if preload_model:
            logger.info("🚀 Pré-carregando modelo Whisper no startup...")
            try:
                result = processor.load_model_explicit()
                if result["success"]:
                    logger.info(f"✅ {result['message']}")
                else:
                    logger.warning(f"⚠️ Falha no pré-carregamento: {result['message']}")
            except Exception as e:
                logger.error(f"❌ Erro ao pré-carregar modelo: {e}")
                logger.warning("⚠️ Serviço continuará funcionando. Modelo será carregado sob demanda.")
        else:
            logger.info("ℹ️ Pré-carregamento de modelo DESABILITADO (WHISPER_PRELOAD_MODEL=false)")
            logger.info("   Modelo será carregado apenas quando necessário (primeira task)")
            
    except Exception as e:
        logger.error(f"Erro durante inicialização: {e}")
        raise


@app.on_event("shutdown") 
async def shutdown_event():
    """Para sistema"""
    try:
        await job_store.stop_cleanup_task()
        logger.info("Audio Transcription Service parado graciosamente")
    except Exception as e:
        logger.error(f"Erro durante shutdown: {e}")


@app.get("/")
async def root():
    """
    Endpoint raiz - Informações do serviço
    """
    return {
        "service": "Audio Transcription Service",
        "version": "2.0.0",
        "status": "running",
        "description": "Microserviço para transcrição de áudio com cache de 24h",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "jobs": {
                "create": "POST /jobs",
                "get": "GET /jobs/{job_id}",
                "list": "GET /jobs",
                "download": "GET /jobs/{job_id}/download",
                "delete": "DELETE /jobs/{job_id}",
                "orphaned": "GET /jobs/orphaned",
                "orphaned_cleanup": "POST /jobs/orphaned/cleanup"
            },
            "admin": {
                "stats": "GET /admin/stats",
                "queue": "GET /admin/queue",
                "cleanup": "POST /admin/cleanup"
            },
            "model": {
                "status": "GET /model/status",
                "load": "POST /model/load",
                "unload": "POST /model/unload"
            }
        }
    }


def submit_processing_task(job: Job):
    """Submete job para processamento em background via Celery"""
    try:
        from .celery_config import celery_app
        from .celery_tasks import transcribe_audio_task
        
        # Envia job para o worker Celery
        task_result = transcribe_audio_task.apply_async(
            args=[job.model_dump()], 
            task_id=job.id  # Usa o job ID como task ID
        )
        logger.info(f"📤 Job {job.id} enviado para Celery worker: {task_result.id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar job {job.id} para Celery: {e}")
        logger.error(f"❌ Fallback: processando diretamente job {job.id}")
        # Fallback para processamento direto se Celery falhar
        asyncio.create_task(processor.process_transcription_job(job))


@app.post("/jobs", response_model=Job)
async def create_transcription_job(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language_in: str = Form("auto"),
    language_out: Optional[str] = Form(None),
    engine: WhisperEngine = Form(WhisperEngine.FASTER_WHISPER)
) -> Job:
    """
    Cria um novo job de transcrição/tradução de áudio
    
    - **file**: Arquivo de áudio para transcrever
    - **language_in**: Código do idioma de entrada (ISO 639-1) ou 'auto' para detecção automática.
                       Exemplos: 'pt' (português), 'en' (inglês), 'es' (espanhol), 'auto' (detectar)
    - **language_out**: (Opcional) Código do idioma de saída para tradução (ISO 639-1).
                        Se omitido, usa o mesmo idioma detectado/especificado em language_in.
                        Exemplos: 'pt', 'en', 'es', 'fr', etc.
    - **engine**: (Opcional) Engine de transcrição Whisper: 
                  - 'faster-whisper' (padrão): 4x mais rápido, word timestamps nativos
                  - 'openai-whisper': Original da OpenAI, compatibilidade máxima
                  - 'whisperx': Word-level timestamps com forced alignment (mais preciso)
    
    **Exemplos de uso**:
    - Transcrever em português: language_in='pt', language_out=None
    - Detectar idioma e transcrever: language_in='auto', language_out=None
    - Traduzir inglês para português: language_in='en', language_out='pt'
    - Detectar e traduzir para inglês: language_in='auto', language_out='en'
    - Usar whisperX para timestamps precisos: engine='whisperx'
    
    Use GET /languages para ver todos os idiomas suportados.
    """
    try:
        # Engine já vem como Enum do Form, não precisa converter
        engine_enum = engine
        
        # Validação de linguagem de entrada
        if not is_language_supported(language_in):
            supported = get_supported_languages()
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Linguagem de entrada não suportada",
                    "language_provided": language_in,
                    "supported_languages": supported[:10],
                    "total_supported": len(supported),
                    "note": "Use GET /languages para ver todas as linguagens suportadas"
                }
            )
        
        # Validação de linguagem de saída (se fornecida)
        if language_out is not None:
            if not is_language_supported(language_out):
                supported = get_supported_languages()
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Linguagem de saída não suportada",
                        "language_provided": language_out,
                        "supported_languages": supported[:10],
                        "total_supported": len(supported),
                        "note": "Use GET /languages para ver todas as linguagens suportadas"
                    }
                )
            
            # Aviso: language_out igual a language_in não faz sentido (exceto se in='auto')
            if language_out == language_in and language_in != "auto":
                logger.warning(f"language_out='{language_out}' igual a language_in='{language_in}', tradução não será aplicada")
        
        logger.info(f"Criando job: arquivo={file.filename}, language_in={language_in}, language_out={language_out or 'same'}, engine={engine}")
        
        # Cria job para extrair ID
        new_job = Job.create_new(file.filename, "transcribe", language_in, language_out, engine_enum)
        
        # Verifica se já existe job com mesmo ID
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            # Job já existe - verifica status
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} já completado")
                return existing_job
            elif existing_job.status in [JobStatus.QUEUED, JobStatus.PROCESSING]:
                # 🔧 CRÍTICO: Detecta jobs órfãos (processando por muito tempo)
                from datetime import datetime, timedelta
                
                # Se job está processando há mais de 30 minutos, considera órfão
                processing_timeout = timedelta(minutes=30)
                job_age = now_brazil() - existing_job.created_at
                
                if job_age > processing_timeout:
                    logger.warning(f"⚠️ Job {new_job.id} órfão detectado (processando há {job_age}), reprocessando...")
                    existing_job.status = JobStatus.QUEUED
                    existing_job.error_message = f"Job órfão detectado após {job_age}, reiniciando processamento"
                    existing_job.progress = 0.0
                    job_store.update_job(existing_job)
                    
                    # Submete para processamento novamente
                    submit_processing_task(existing_job)
                    return existing_job
                else:
                    logger.info(f"Job {new_job.id} já em processamento (idade: {job_age})")
                    return existing_job
            elif existing_job.status == JobStatus.FAILED:
                # Falhou antes - tenta novamente salvando o arquivo novamente
                logger.info(f"Reprocessando job falhado: {new_job.id} - salvando arquivo novamente")
                
                # Salva arquivo novamente com PATH ABSOLUTO
                upload_dir = Path("/app/uploads")
                upload_dir.mkdir(parents=True, exist_ok=True)
                original_extension = Path(file.filename).suffix if file.filename else ""
                file_path = upload_dir / f"{existing_job.id}{original_extension}"
                
                # Lê conteúdo do arquivo
                content = await file.read()
                if not content:
                    logger.error(f"❌ ERRO: Arquivo enviado está vazio")
                    raise HTTPException(status_code=400, detail="Arquivo enviado está vazio")
                
                # Salva arquivo com retry
                max_retries = 3
                saved_successfully = False
                for retry in range(max_retries):
                    try:
                        with open(file_path, "wb") as f:
                            f.write(content)
                            f.flush()
                            os.fsync(f.fileno())  # Força escrita no disco
                        
                        # VALIDA que arquivo foi salvo corretamente
                        if file_path.exists() and file_path.stat().st_size > 0:
                            saved_successfully = True
                            break
                        else:
                            logger.warning(f"⚠️ Tentativa {retry+1}/{max_retries}: Arquivo não foi salvo corretamente")
                    except Exception as e:
                        logger.error(f"❌ Tentativa {retry+1}/{max_retries} falhou ao salvar: {e}")
                        if retry == max_retries - 1:
                            raise
                        time.sleep(0.5 * (retry + 1))
                
                if not saved_successfully:
                    logger.error(f"❌ ERRO: Falha ao salvar arquivo após {max_retries} tentativas")
                    raise HTTPException(status_code=500, detail="Erro ao salvar arquivo no servidor")
                
                file_size = file_path.stat().st_size
                logger.info(f"✅ Arquivo salvo com sucesso: {file_path} ({file_size / (1024*1024):.2f} MB)")
                
                existing_job.input_file = str(file_path.absolute())
                existing_job.file_size_input = file_size
                existing_job.status = JobStatus.QUEUED
                existing_job.error_message = None
                existing_job.progress = 0.0
                job_store.update_job(existing_job)
                
                # Submete para processamento
                submit_processing_task(existing_job)
                logger.info(f"🚀 Job {existing_job.id} submetido para reprocessamento")
                return existing_job
        
        # Job novo - salva arquivo com PATH ABSOLUTO
        upload_dir = Path("/app/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Usar apenas job_id para evitar problemas com caracteres especiais
        original_extension = Path(file.filename).suffix if file.filename else ""
        file_path = upload_dir / f"{new_job.id}{original_extension}"
        
        # Lê conteúdo do arquivo
        content = await file.read()
        if not content:
            logger.error(f"❌ ERRO: Arquivo enviado está vazio")
            raise HTTPException(status_code=400, detail="Arquivo enviado está vazio")
        
        # Salva arquivo com retry
        max_retries = 3
        saved_successfully = False
        for retry in range(max_retries):
            try:
                with open(file_path, "wb") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())  # Força escrita no disco
                
                # VALIDA que arquivo foi salvo corretamente
                if file_path.exists() and file_path.stat().st_size > 0:
                    saved_successfully = True
                    break
                else:
                    logger.warning(f"⚠️ Tentativa {retry+1}/{max_retries}: Arquivo não foi salvo corretamente")
            except Exception as e:
                logger.error(f"❌ Tentativa {retry+1}/{max_retries} falhou ao salvar: {e}")
                if retry == max_retries - 1:
                    raise
                time.sleep(0.5 * (retry + 1))
        
        if not saved_successfully:
            logger.error(f"❌ ERRO: Falha ao salvar arquivo após {max_retries} tentativas")
            raise HTTPException(status_code=500, detail="Erro ao salvar arquivo no servidor")
        
        file_size = file_path.stat().st_size
        logger.info(f"✅ Arquivo salvo com sucesso: {file_path} ({file_size / (1024*1024):.2f} MB)")
        
        new_job.input_file = str(file_path.absolute())
        new_job.file_size_input = file_size
        
        # Salva job e submete para processamento
        job_store.save_job(new_job)
        submit_processing_task(new_job)
        
        logger.info(f"Job de transcrição criado: {new_job.id}")
        return new_job
        
    except HTTPException:
        # HTTPException já tem mensagem apropriada, re-raise sem modificar
        raise
    except Exception as e:
        logger.error(f"Erro ao criar job de transcrição: {e}")
        if isinstance(e, (AudioTranscriptionException, ServiceException)):
            raise
        raise ServiceException(f"Erro interno ao processar arquivo: {str(e)}")


@app.get("/languages")
async def get_supported_languages_endpoint():
    """
    Retorna lista de linguagens suportadas pelo Whisper para transcrição e tradução.
    
    **Transcrição (language_in):**
    - **auto**: Detecção automática de idioma
    - Códigos ISO 639-1 para idiomas específicos (en, pt, es, fr, de, it, ja, ko, zh, etc.)
    - Suporta 99+ idiomas para transcrição no idioma original
    
    **Tradução (language_out):**
    - **en** (English): Único idioma suportado para tradução pelo Whisper
    - Whisper pode traduzir de qualquer idioma detectado para inglês
    - Tradução para outros idiomas não é suportada nativamente
    
    **Exemplos de uso:**
    - Transcrever em português: `language_in='pt'`, `language_out=None`
    - Detectar e transcrever: `language_in='auto'`, `language_out=None`
    - Traduzir para inglês: `language_in='auto'`, `language_out='en'`
    - Traduzir PT→EN: `language_in='pt'`, `language_out='en'`
    """
    languages = get_supported_languages()
    models = get_whisper_models()
    
    return {
        "transcription": {
            "supported_languages": languages,
            "total_languages": len(languages),
            "default_language": settings.get("whisper_default_language", "auto"),
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


@app.get("/engines")
async def get_available_engines():
    """
    Retorna lista de engines de transcrição disponíveis.
    
    **Engines suportados:**
    - **faster-whisper**: Padrão. 4x mais rápido, menos VRAM, word timestamps nativos
    - **openai-whisper**: Original da OpenAI, compatibilidade máxima, mais lento
    - **whisperx**: Word-level timestamps com forced alignment (mais preciso para lip-sync)
    
    **Word-level timestamps:**
    - **faster-whisper**: Sim (nativos, mas menos precisos)
    - **openai-whisper**: Não (apenas segments)
    - **whisperx**: Sim (forced alignment, máxima precisão)
    
    **Performance:**
    - **faster-whisper**: ⚡⚡⚡⚡ (4x mais rápido)
    - **openai-whisper**: ⚡ (baseline, mais lento)
    - **whisperx**: ⚡⚡⚡ (20% mais lento que faster-whisper, mas timestamps perfeitos)
    """
    from .models import WhisperEngine
    
    # Verifica disponibilidade de WhisperX
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


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job_status(job_id: str) -> Job:
    """Consulta status de um job"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")
    
    return job


@app.get("/jobs/{job_id}/download")
async def download_file(job_id: str):
    """Faz download do arquivo de transcrição"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")
        
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425, 
            detail=f"Transcrição não pronta. Status: {job.status}"
        )
    
    file_path = Path(job.output_file) if job.output_file else None
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        path=file_path,
        filename=f"transcription_{job_id}.srt",
        media_type='text/plain'
    )


@app.get("/jobs/{job_id}/text")
async def get_transcription_text(job_id: str):
    """Retorna apenas o texto da transcrição"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
        
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425, 
            detail=f"Transcrição não pronta. Status: {job.status}"
        )
    
    return {"text": job.transcription_text or ""}


@app.get("/jobs/{job_id}/transcription", response_model=TranscriptionResponse)
async def get_full_transcription(job_id: str) -> TranscriptionResponse:
    """
    Retorna transcrição completa com segments (start, end, duration).
    Formato compatível com projeto v1.
    """
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")
        
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425, 
            detail=f"Transcrição não pronta. Status: {job.status}"
        )
    
    if not job.transcription_segments:
        raise HTTPException(
            status_code=500, 
            detail="Segments não disponíveis para este job"
        )
    
    # Calcula duração total
    duration = job.transcription_segments[-1].end if job.transcription_segments else 0.0
    
    # Calcula tempo de processamento
    processing_time = None
    if job.completed_at and job.created_at:
        processing_time = (job.completed_at - job.created_at).total_seconds()
    
    # Determina se houve tradução
    was_translated = job.language_out is not None and job.language_out != job.language_in
    
    return TranscriptionResponse(
        transcription_id=job.id,
        filename=job.filename or "unknown",
        language=job.language_detected or job.language_in,  # Prioriza idioma detectado
        language_detected=job.language_detected,
        language_out=job.language_out,
        was_translated=was_translated,
        full_text=job.transcription_text or "",
        segments=job.transcription_segments,
        total_segments=len(job.transcription_segments),
        duration=duration,
        processing_time=processing_time
    )


@app.get("/jobs", response_model=List[Job])
async def list_jobs(limit: int = 20) -> List[Job]:
    """Lista jobs recentes"""
    return job_store.list_jobs(limit)


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Remove job e arquivos associados
    
    IMPORTANTE: Remove completamente o job do sistema:
    - Job do Redis
    - Arquivo de entrada (upload)
    - Arquivo de saída (transcrição)
    - Arquivos temporários
    """
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    try:
        # Remove arquivos se existirem
        files_deleted = 0
        
        if job.input_file:
            input_path = Path(job.input_file)
            if input_path.exists():
                input_path.unlink()
                files_deleted += 1
                logger.info(f"🗑️ Arquivo de entrada removido: {input_path.name}")
        
        if job.output_file:
            output_path = Path(job.output_file)
            if output_path.exists():
                output_path.unlink()
                files_deleted += 1
                logger.info(f"🗑️ Arquivo de saída removido: {output_path.name}")
        
        # Remove job do Redis (CRÍTICO - estava faltando!)
        job_store.redis.delete(f"transcription_job:{job_id}")
        logger.info(f"🗑️ Job {job_id} removido do Redis")
        
        return {
            "message": "Job removido com sucesso",
            "job_id": job_id,
            "files_deleted": files_deleted
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao remover job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao remover job: {str(e)}"
        )


async def _perform_basic_cleanup():
    """Executa limpeza BÁSICA: Remove apenas jobs expirados e arquivos órfãos"""
    try:
        from datetime import timedelta
        report = {"jobs_removed": 0, "files_deleted": 0, "space_freed_mb": 0.0, "errors": []}
        logger.info("🧹 Iniciando limpeza básica (jobs expirados)...")
        
        # Limpar jobs expirados
        try:
            keys = job_store.redis.keys("transcription_job:*")
            now = now_brazil()
            expired_count = 0
            for key in keys:
                job_data = job_store.redis.get(key)
                if job_data:
                    import json
                    try:
                        job = json.loads(job_data)
                        created_at = datetime.fromisoformat(job.get("created_at", ""))
                        if (now - created_at) > timedelta(hours=24):
                            job_store.redis.delete(key)
                            expired_count += 1
                    except (ValueError, TypeError, AttributeError, KeyError) as err:
                        logger.debug(f"Invalid job data in {key}: {err}")
                        pass
            report["jobs_removed"] = expired_count
            logger.info(f"🗑️  Redis: {expired_count} jobs expirados removidos")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"Redis: {str(e)}")
        
        # Limpar arquivos órfãos (>24h)
        for dir_name, dir_key in [("uploads", "upload_dir"), ("transcriptions", "transcription_dir"), ("temp", "temp_dir")]:
            dir_path = Path(settings.get(dir_key, f'./{dir_name}'))
            if dir_path.exists():
                deleted_count = 0
                for file_path in dir_path.iterdir():
                    if not file_path.is_file():
                        continue
                    try:
                        age = now_brazil() - datetime.fromtimestamp(file_path.stat().st_mtime)
                        if age > timedelta(hours=24):
                            size_mb = file_path.stat().st_size / (1024 * 1024)
                            await asyncio.to_thread(file_path.unlink)
                            deleted_count += 1
                            report["space_freed_mb"] += size_mb
                    except Exception as e:
                        logger.error(f"❌ Erro ao remover {file_path.name}: {e}")
                        report["errors"].append(f"{dir_name}/{file_path.name}: {str(e)}")
                report["files_deleted"] += deleted_count
                if deleted_count > 0:
                    logger.info(f"🗑️  {dir_name.capitalize()}: {deleted_count} arquivos órfãos removidos")
        
        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        logger.info(f"✓ Limpeza básica: {report['jobs_removed']} jobs + {report['files_deleted']} arquivos ({report['space_freed_mb']}MB)")
        return report
    except Exception as e:
        logger.error(f"❌ ERRO na limpeza básica: {e}")
        return {"error": str(e)}


async def _perform_cleanup(purge_celery_queue: bool = False):
    """
    Executa limpeza COMPLETA do sistema SÍNCRONAMENTE (sem background tasks)
    
    ⚠️ CRÍTICO: Executa no handler HTTP para evitar ciclo vicioso onde
    o próprio job de limpeza seria deletado antes de terminar.
    
    ZERA ABSOLUTAMENTE TUDO:
    - TODO o banco Redis (FLUSHDB usando DIVISOR do .env)
    - TODOS os arquivos de uploads/
    - TODOS os arquivos de transcriptions/
    - TODOS os arquivos temporários
    - TODOS os modelos baixados em models/
    - (OPCIONAL) TODOS os jobs da fila Celery
    """
    try:
        from redis import Redis
        from urllib.parse import urlparse
        
        report = {
            "jobs_removed": 0,
            "redis_flushed": False,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "models_deleted": 0,
            "celery_queue_purged": False,
            "celery_tasks_purged": 0,
            "errors": []
        }
        
        logger.warning("🔥 INICIANDO LIMPEZA TOTAL DO SISTEMA - TUDO SERÁ REMOVIDO!")
        
        # 1. FLUSHDB NO REDIS (limpa TODO o banco de dados)
        try:
            # Extrai host, port e db do REDIS_URL (que usa DIVISOR)
            redis_url = job_store.redis.connection_pool.connection_kwargs.get('host') or 'localhost'
            redis_port = job_store.redis.connection_pool.connection_kwargs.get('port') or 6379
            redis_db = job_store.redis.connection_pool.connection_kwargs.get('db') or 0
            
            logger.warning(f"🔥 Executando FLUSHDB no Redis {redis_url}:{redis_port} DB={redis_db}")
            
            # Conta jobs ANTES de limpar
            keys_before = job_store.redis.keys("transcription_job:*")
            report["jobs_removed"] = len(keys_before)
            
            # FLUSHDB - Remove TODO o conteúdo do banco atual
            job_store.redis.flushdb()
            report["redis_flushed"] = True
            
            logger.info(f"✅ Redis FLUSHDB executado: {len(keys_before)} jobs + todas as outras keys removidas")
            
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"Redis FLUSHDB: {str(e)}")
        
        # 2. LIMPAR FILA CELERY (SE SOLICITADO)
        if purge_celery_queue:
            try:
                from redis import Redis
                
                logger.warning("🔥 Limpando fila Celery 'audio_transcriber_queue'...")
                
                # Conecta ao Redis Celery
                redis_celery = job_store.redis  # Usa o mesmo Redis do job_store
                
                # Nome da fila no Redis (Celery usa formato customizado ou default)
                queue_keys = [
                    "audio_transcriber_queue",          # Fila principal (nome customizado)
                    "audio_transcription_queue",        # Possível nome alternativo
                    "celery",                           # Fila default do Celery
                    "_kombu.binding.audio_transcriber_queue",  # Bindings
                    "_kombu.binding.audio_transcription_queue",  # Bindings alternativo
                    "_kombu.binding.celery",            # Bindings default
                    "unacked",                          # Tasks não reconhecidas
                    "unacked_index",                    # Índice de unacked
                ]
                
                tasks_purged = 0
                for queue_key in queue_keys:
                    # LLEN para verificar se existe (funciona apenas para listas)
                    try:
                        queue_len = redis_celery.llen(queue_key)
                        if queue_len > 0:
                            logger.info(f"   Fila '{queue_key}': {queue_len} tasks")
                            tasks_purged += queue_len
                    except (redis.ResponseError, redis.DataError) as err:
                        logger.debug(f"Queue {queue_key} not a list: {err}")
                        pass  # Não é uma lista, pode ser outro tipo de key
                    
                    # DELETE remove a key inteira (funciona para qualquer tipo)
                    deleted = redis_celery.delete(queue_key)
                    if deleted:
                        logger.info(f"   ✓ Fila '{queue_key}' removida")
                
                # Também remove keys de resultados e metadados Celery
                celery_result_keys = redis_celery.keys("celery-task-meta-*")
                if celery_result_keys:
                    redis_celery.delete(*celery_result_keys)
                    logger.info(f"   ✓ {len(celery_result_keys)} resultados Celery removidos")
                
                report["celery_queue_purged"] = True
                report["celery_tasks_purged"] = tasks_purged
                logger.warning(f"🔥 Fila Celery purgada: {tasks_purged} tasks removidas")
                
            except Exception as e:
                logger.error(f"❌ Erro ao limpar fila Celery: {e}")
                report["errors"].append(f"Celery: {str(e)}")
        else:
            logger.info("⏭️  Fila Celery NÃO será limpa (purge_celery_queue=false)")
        
        # 3. LIMPAR TODOS OS ARQUIVOS DE UPLOADS
        upload_dir = Path(settings.get('upload_dir', './uploads'))
        if upload_dir.exists():
            deleted_count = 0
            for file_path in upload_dir.iterdir():
                if not file_path.is_file():
                    continue
                    
                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover upload {file_path.name}: {e}")
                    report["errors"].append(f"Upload/{file_path.name}: {str(e)}")
            
            report["files_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"🗑️  Uploads: {deleted_count} arquivos removidos")
            else:
                logger.info("✓ Uploads: nenhum arquivo encontrado")
        
        # 3. LIMPAR TODOS OS ARQUIVOS DE TRANSCRIPTIONS
        transcription_dir = Path(settings.get('transcription_dir', './transcriptions'))
        if transcription_dir.exists():
            deleted_count = 0
            for file_path in transcription_dir.iterdir():
                if not file_path.is_file():
                    continue
                    
                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover transcrição {file_path.name}: {e}")
                    report["errors"].append(f"Transcription/{file_path.name}: {str(e)}")
            
            report["files_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"🗑️  Transcriptions: {deleted_count} arquivos removidos")
            else:
                logger.info("✓ Transcriptions: nenhum arquivo encontrado")
        
        # 4. LIMPAR TODOS OS ARQUIVOS TEMPORÁRIOS
        temp_dir = Path(settings.get('temp_dir', './temp'))
        if temp_dir.exists():
            deleted_count = 0
            for file_path in temp_dir.iterdir():
                if not file_path.is_file():
                    continue
                    
                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover temp {file_path.name}: {e}")
                    report["errors"].append(f"Temp/{file_path.name}: {str(e)}")
            
            report["files_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"🗑️  Temp: {deleted_count} arquivos removidos")
            else:
                logger.info("✓ Temp: nenhum arquivo encontrado")
        
        # 5. LIMPAR TODOS OS MODELOS WHISPER BAIXADOS
        models_dir = Path(settings.get('model_dir', './models'))
        if models_dir.exists():
            deleted_count = 0
            for file_path in models_dir.rglob("*"):  # rglob para pegar subdiretórios também
                if not file_path.is_file():
                    continue
                    
                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                    report["models_deleted"] += 1
                except Exception as e:
                    logger.error(f"❌ Erro ao remover modelo {file_path.name}: {e}")
                    report["errors"].append(f"Models/{file_path.name}: {str(e)}")
            
            if deleted_count > 0:
                logger.warning(f"🗑️  Models: {deleted_count} arquivos de modelo removidos ({size_mb:.2f}MB)")
            else:
                logger.info("✓ Models: nenhum modelo encontrado")
        
        # Formatar relatório
        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        
        # ✅ CRÍTICO: SEGUNDO FLUSHDB para garantir limpeza total
        # (Remove jobs que foram salvos DURANTE a limpeza por workers Celery)
        try:
            # Verifica se há keys novas (salvos durante a limpeza)
            keys_after = job_store.redis.keys("transcription_job:*")
            if keys_after:
                logger.warning(f"⚠️ {len(keys_after)} jobs foram salvos DURANTE a limpeza! Executando FLUSHDB novamente...")
                job_store.redis.flushdb()
                report["jobs_removed"] += len(keys_after)
                logger.info(f"✅ SEGUNDO FLUSHDB executado: {len(keys_after)} jobs adicionais removidos")
            else:
                logger.info("✓ Nenhum job novo detectado após limpeza")
                
        except Exception as e:
            logger.error(f"❌ Erro no segundo FLUSHDB: {e}")
            report["errors"].append(f"Segundo FLUSHDB: {str(e)}")
        
        report["message"] = (
            f"🔥 LIMPEZA TOTAL CONCLUÍDA: "
            f"{report['jobs_removed']} jobs do Redis + "
            f"{report['files_deleted']} arquivos + "
            f"{report['models_deleted']} modelos removidos "
            f"({report['space_freed_mb']}MB liberados)"
        )
        
        if report["errors"]:
            report["message"] += f" ⚠️ com {len(report['errors'])} erros"
        
        logger.warning(report["message"])
        return report
        
    except Exception as e:
        logger.error(f"❌ Erro na limpeza total: {e}")
        return {"error": str(e), "jobs_removed": 0, "files_deleted": 0, "models_deleted": 0}


@app.post("/admin/cleanup")
async def manual_cleanup(
    deep: bool = False,
    purge_celery_queue: bool = False
):
    """
    🧹 LIMPEZA DO SISTEMA
    
    ⚠️ IMPORTANTE: Execução SÍNCRONA (sem background tasks ou Celery)
    O cliente AGUARDA a conclusão completa antes de receber a resposta.
    
    **Por que síncrono?**
    Se usássemos Celery/background tasks, o job de limpeza seria deletado
    antes de terminar (ciclo vicioso). Por isso executa DIRETAMENTE no handler HTTP.
    
    **Modos de operação:**
    
    1. **Limpeza básica** (deep=false):
       - Remove jobs expirados (>24h)
       - Remove arquivos órfãos
    
    2. **Limpeza profunda** (deep=true) - ⚠️ FACTORY RESET:
       - TODO o banco Redis (FLUSHDB usando DIVISOR do .env)
       - TODOS os arquivos de uploads/
       - TODOS os arquivos de transcriptions/
       - TODOS os arquivos temporários em temp/
       - TODOS os modelos Whisper baixados (~500MB cada)
       - **OPCIONAL:** Purga fila Celery (purge_celery_queue=true)
    
    **Parâmetros:**
    - deep (bool): Se true, faz limpeza COMPLETA (factory reset)
    - purge_celery_queue (bool): Se true, limpa FILA CELERY também
    
    **Retorna apenas APÓS conclusão completa!**
    """
    cleanup_type = "TOTAL" if deep else "básica"
    logger.warning(f"🔥 Iniciando limpeza {cleanup_type} SÍNCRONA (purge_celery={purge_celery_queue})")
    
    try:
        # Executa DIRETAMENTE (sem background tasks ou Celery)
        if deep:
            result = await _perform_cleanup(purge_celery_queue)
        else:
            result = await _perform_basic_cleanup()
        
        logger.info(f"✅ Limpeza {cleanup_type} CONCLUÍDA com sucesso")
        return result
        
    except Exception as e:
        logger.error(f"❌ ERRO na limpeza {cleanup_type}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer cleanup: {str(e)}")


@app.get("/admin/stats")
async def get_stats():
    """Estatísticas do sistema"""
    stats = job_store.get_stats()
    
    # Adiciona info do cache
    upload_path = Path("./uploads")
    transcription_path = Path("./transcriptions")
    
    total_files = 0
    total_size = 0
    
    for path in [upload_path, transcription_path]:
        if path.exists():
            files = list(path.iterdir())
            total_files += len(files)
            total_size += sum(f.stat().st_size for f in files if f.is_file())
    
    stats["cache"] = {
        "files_count": total_files,
        "total_size_mb": round(total_size / (1024 * 1024), 2)
    }
    
    return stats


@app.get("/admin/queue")
async def get_queue_info_endpoint():
    """
    Get queue information
    
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
        queue_info = await job_store.get_queue_info()
        
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
        orphaned = await job_store.find_orphaned_jobs(max_age_minutes=max_age_minutes)
        
        # Format response with detailed info
        orphaned_info = []
        for job in orphaned:
            age_minutes = (now_brazil() - job.updated_at).total_seconds() / 60
            orphaned_info.append({
                "job_id": job.job_id,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
                "age_minutes": round(age_minutes, 2),
                "filename": job.filename if hasattr(job, 'filename') else None
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
    
    **Parameters**:
    - max_age_minutes: Threshold for considering a job orphaned (default: 30)
    - mark_as_failed: If True, marks as failed; if False, deletes completely (default: True)
    
    **Actions**:
    1. Find all orphaned jobs (processing > max_age_minutes)
    2. Either mark as failed with detailed reason, or delete completely
    3. Remove associated files (audio, transcription, temp)
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
        orphaned = await job_store.find_orphaned_jobs(max_age_minutes=max_age_minutes)
        
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
            age_minutes = (now_brazil() - job.updated_at).total_seconds() / 60
            
            # Remove associated files
            files_deleted = []
            errors = []
            
            # Audio file in uploads
            if hasattr(job, 'filename') and job.filename:
                try:
                    audio_path = Path(f"./uploads/{job.job_id}_{job.filename}")
                    if audio_path.exists() and audio_path.is_file():
                        size_mb = audio_path.stat().st_size / (1024 * 1024)
                        audio_path.unlink(missing_ok=True)
                        files_deleted.append({"file": str(audio_path), "size_mb": round(size_mb, 2)})
                        space_freed += size_mb
                except Exception as e:
                    errors.append(f"Failed to delete audio {job.filename}: {str(e)}")
                    logger.warning(f"Failed to delete audio file: {e}")
            
            # Transcription file
            try:
                transcription_path = Path(f"./transcriptions/{job.job_id}.json")
                if transcription_path.exists() and transcription_path.is_file():
                    size_mb = transcription_path.stat().st_size / (1024 * 1024)
                    transcription_path.unlink(missing_ok=True)
                    files_deleted.append({"file": str(transcription_path), "size_mb": round(size_mb, 2)})
                    space_freed += size_mb
            except Exception as e:
                errors.append(f"Failed to delete transcription: {str(e)}")
                logger.warning(f"Failed to delete transcription file: {e}")
            
            # Temp files
            try:
                temp_dir = Path("./temp")
                if temp_dir.exists() and temp_dir.is_dir():
                    for temp_file in temp_dir.glob(f"*{job.job_id}*"):
                        if temp_file.is_file():
                            try:
                                size_mb = temp_file.stat().st_size / (1024 * 1024)
                                temp_file.unlink(missing_ok=True)
                                files_deleted.append({"file": str(temp_file), "size_mb": round(size_mb, 2)})
                                space_freed += size_mb
                            except Exception as e:
                                errors.append(f"Failed to delete temp {temp_file.name}: {str(e)}")
                                logger.warning(f"Failed to delete temp file: {e}")
            except Exception as e:
                errors.append(f"Failed to scan temp directory: {str(e)}")
                logger.warning(f"Failed to scan temp directory: {e}")
            
            if mark_as_failed:
                # Mark as failed
                try:
                    job.status = JobStatus.FAILED
                    job.error = f"Job orphaned: stuck in processing for {age_minutes:.1f} minutes (auto-recovery)"
                    job.updated_at = now_brazil()
                    await job_store.save_job(job)
                    
                    actions.append({
                        "job_id": job.job_id,
                        "action": "marked_as_failed",
                        "age_minutes": round(age_minutes, 2),
                        "files_deleted": files_deleted,
                        "reason": job.error,
                        "errors": errors if errors else None
                    })
                except Exception as e:
                    errors.append(f"Failed to mark job as failed: {str(e)}")
                    logger.error(f"Failed to mark job {job.job_id} as failed: {e}", exc_info=True)
                    actions.append({
                        "job_id": job.job_id,
                        "action": "failed_to_update",
                        "age_minutes": round(age_minutes, 2),
                        "files_deleted": files_deleted,
                        "errors": errors
                    })
            else:
                # Delete completely
                try:
                    await job_store.delete_job(job.job_id)
                    
                    actions.append({
                        "job_id": job.job_id,
                        "action": "deleted",
                        "age_minutes": round(age_minutes, 2),
                        "files_deleted": files_deleted,
                        "errors": errors if errors else None
                    })
                except Exception as e:
                    errors.append(f"Failed to delete job: {str(e)}")
                    logger.error(f"Failed to delete job {job.job_id}: {e}", exc_info=True)
                    actions.append({
                        "job_id": job.job_id,
                        "action": "failed_to_delete",
                        "age_minutes": round(age_minutes, 2),
                        "files_deleted": files_deleted,
                        "errors": errors
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


@app.get("/health")
async def health_check():
    """Health check profundo - valida recursos críticos"""
    import shutil
    import subprocess
    from fastapi.responses import JSONResponse
    
    health_status = {
        "status": "healthy",
        "service": "audio-transcription", 
        "version": "2.0.0",
        "timestamp": now_brazil().isoformat(),
        "checks": {}
    }
    
    is_healthy = True
    
    # 1. Verifica Redis
    try:
        job_store.redis.ping()
        health_status["checks"]["redis"] = {"status": "ok", "message": "Connected"}
    except Exception as e:
        health_status["checks"]["redis"] = {"status": "error", "message": str(e)}
        is_healthy = False
    
    # 2. Verifica espaço em disco
    try:
        output_dir = Path(settings['transcription_dir'])
        output_dir.mkdir(exist_ok=True, parents=True)
        stat = shutil.disk_usage(output_dir)
        free_gb = stat.free / (1024**3)
        total_gb = stat.total / (1024**3)
        percent_free = (stat.free / stat.total) * 100
        
        disk_status = "ok" if percent_free > 10 else "warning" if percent_free > 5 else "critical"
        if percent_free <= 5:
            is_healthy = False
            
        health_status["checks"]["disk_space"] = {
            "status": disk_status,
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "percent_free": round(percent_free, 2)
        }
    except Exception as e:
        health_status["checks"]["disk_space"] = {"status": "error", "message": str(e)}
        is_healthy = False
    
    # 3. Verifica ffmpeg (não bloqueante)
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            health_status["checks"]["ffmpeg"] = {"status": "ok", "version": version}
        else:
            health_status["checks"]["ffmpeg"] = {"status": "warning", "message": "ffmpeg not responding"}
            logger.warning("FFmpeg check failed but not marking service as unhealthy")
    except FileNotFoundError:
        health_status["checks"]["ffmpeg"] = {"status": "warning", "message": "ffmpeg not installed"}
        logger.warning("FFmpeg not found but not marking service as unhealthy")
    except Exception as e:
        health_status["checks"]["ffmpeg"] = {"status": "warning", "message": str(e)}
        logger.warning(f"FFmpeg check error: {e} - not marking service as unhealthy")
    
    # 4. Verifica Celery workers (verificação simplificada)
    try:
        # Verificação básica sem timeout complexo para evitar travamento
        # Não verificar workers ativamente para evitar timeout no health check
        health_status["checks"]["celery_workers"] = {
            "status": "ok",
            "message": "Celery workers verification skipped for faster health response"
        }
    except Exception as e:
        logger.warning(f"Celery workers check error (non-critical): {e}")
        health_status["checks"]["celery_workers"] = {"status": "ok", "message": "Check skipped"}
    
    # 5. Verifica modelo Whisper (verificação básica e rápida)
    try:
        model_name = settings.get('whisper_model', 'base')
        # Verificar se modelo está carregado, mas não forçar carregamento
        is_loaded = processor.model is not None
        health_status["checks"]["whisper_model"] = {
            "status": "ok",
            "model": model_name,
            "loaded": is_loaded,
            "message": "Model loaded" if is_loaded else "Model will be loaded on first use"
        }
    except Exception as e:
        logger.warning(f"Whisper model check error (non-critical): {e}")
        health_status["checks"]["whisper_model"] = {"status": "ok", "message": "Check skipped"}
    
    # Atualiza status geral
    health_status["status"] = "healthy" if is_healthy else "unhealthy"
    
    status_code = 200 if is_healthy else 503
    
    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/health/detailed")
async def health_check_detailed():
    """
    Health check detalhado com verificação profunda de todos os componentes.
    Usa o novo sistema de health checkers SOLID.
    """
    from .health_checker import (
        CeleryHealthChecker,
        RedisHealthChecker,
        ModelHealthChecker,
        AggregateHealthChecker
    )
    from .celery_config import celery_app
    
    try:
        # Cria health checker agregado
        aggregate = AggregateHealthChecker()
        
        # Registra checkers
        aggregate.register_checker("redis", RedisHealthChecker(job_store))
        aggregate.register_checker("celery", CeleryHealthChecker(celery_app))
        aggregate.register_checker("model", ModelHealthChecker(processor))
        
        # Executa verificações
        health_result = aggregate.check_all()
        
        # Adiciona informações extras
        health_result["service"] = "audio-transcription"
        health_result["version"] = "2.0.0"
        
        # Status code baseado em saúde geral
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


@app.post("/admin/cleanup-orphans")
async def cleanup_orphan_jobs_endpoint():
    """
    🧹 Executa limpeza manual de jobs órfãos.
    Endpoint administrativo para forçar limpeza de jobs travados.
    """
    from .orphan_cleaner import OrphanJobCleaner
    
    try:
        cleaner = OrphanJobCleaner(job_store)
        stats = await cleaner.cleanup_orphans()
        
        return JSONResponse(content={
            "success": True,
            "stats": stats,
            "timestamp": now_brazil().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na limpeza de órfãos: {e}")
        return JSONResponse(
            content={
                "success": False,
                "error": str(e)
            },
            status_code=500
        )


@app.post("/model/unload")
async def unload_whisper_model():
    """
    🔋 Descarrega modelo Whisper da memória/GPU para economia de recursos
    
    **Por que usar este endpoint?**
    - **Economia de energia**: Libera GPU/CPU quando não há tasks rodando
    - **Sustentabilidade**: Reduz pegada de carbono do serviço
    - **Recursos**: Libera RAM (~150MB a 3GB) e VRAM conforme modelo usado
    
    **Comportamento:**
    - Remove modelo da memória RAM e GPU/VRAM
    - Limpa cache CUDA se aplicável
    - Modelo será recarregado automaticamente na próxima task
    - Seguro: não afeta tasks em execução
    
    **Quando usar:**
    - Após processar batch de transcrições
    - Durante períodos de inatividade
    - Para reduzir consumo de recursos quando serviço está idle
    
    **Retorna:**
    - Relatório com memória liberada (RAM/VRAM)
    - Status do dispositivo anterior (CPU/CUDA)
    - Sucesso/erro da operação
    """
    try:
        logger.info("📥 Requisição para descarregar modelo Whisper")
        result = processor.unload_model()
        
        if result["success"]:
            logger.info(f"✅ Modelo descarregado: {result['message']}")
            return JSONResponse(
                content=result,
                status_code=200
            )
        else:
            logger.error(f"❌ Falha ao descarregar: {result['message']}")
            return JSONResponse(
                content=result,
                status_code=500
            )
            
    except Exception as e:
        error_msg = f"Erro inesperado ao descarregar modelo: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/model/load")
async def load_whisper_model():
    """
    🚀 Carrega modelo Whisper explicitamente na memória/GPU
    
    **Por que usar este endpoint?**
    - **Performance**: Pré-carrega modelo antes de processar batch de tasks
    - **Latência**: Primeira transcrição será mais rápida (sem delay de carregamento)
    - **Preparação**: Útil após usar /model/unload para reativar o modelo
    
    **Comportamento:**
    - Carrega modelo na RAM e GPU/VRAM (se CUDA disponível)
    - Detecta automaticamente melhor dispositivo (CUDA > CPU)
    - Testa GPU se disponível para garantir funcionamento
    - Idempotente: se modelo já carregado, retorna status atual
    
    **Quando usar:**
    - Antes de processar múltiplas transcrições
    - Após período de inatividade onde modelo foi descarregado
    - Para garantir sistema pronto com latência mínima
    
    **Por padrão:**
    - Serviço JÁ inicia com modelo carregado no startup
    - Este endpoint só é necessário após usar /model/unload
    
    **Retorna:**
    - Relatório com memória usada (RAM/VRAM)
    - Dispositivo onde modelo foi carregado (CPU/CUDA)
    - Sucesso/erro da operação
    """
    try:
        logger.info("📤 Requisição para carregar modelo Whisper")
        result = processor.load_model_explicit()
        
        if result["success"]:
            logger.info(f"✅ Modelo carregado: {result['message']}")
            return JSONResponse(
                content=result,
                status_code=200
            )
        else:
            logger.error(f"❌ Falha ao carregar: {result['message']}")
            return JSONResponse(
                content=result,
                status_code=500
            )
            
    except Exception as e:
        error_msg = f"Erro inesperado ao carregar modelo: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/model/status")
async def get_model_status():
    """
    📊 Consulta status atual do modelo Whisper
    
    **Retorna informações sobre:**
    - Se modelo está carregado ou não
    - Nome do modelo configurado (tiny/base/small/medium/large)
    - Dispositivo atual (CPU/CUDA/None)
    - Uso de memória VRAM (se GPU)
    - Informações da GPU (se disponível)
    
    **Útil para:**
    - Monitoramento de recursos
    - Verificar se modelo precisa ser carregado
    - Debugging de problemas de memória
    - Dashboards de observabilidade
    """
    try:
        status = processor.get_model_status()
        return JSONResponse(content=status, status_code=200)
    except Exception as e:
        error_msg = f"Erro ao consultar status do modelo: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
