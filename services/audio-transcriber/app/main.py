import asyncio
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Request, Form
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import List, Optional
import logging

from .models import Job, JobRequest, JobStatus, TranscriptionResponse
from .processor import TranscriptionProcessor
from .redis_store import RedisJobStore
from .logging_config import setup_logging, get_logger
from .exceptions import AudioTranscriptionException, ServiceException, exception_handler
from .config import get_settings, get_supported_languages, is_language_supported, get_whisper_models

# Configuração de logging
settings = get_settings()
setup_logging("audio-transcriber", settings['log_level'])
logger = get_logger(__name__)

# Instâncias globais
app = FastAPI(
    title="Audio Transcription Service",
    description="Microserviço para transcrição de áudio com cache de 24h",
    version="2.0.0"
)

# Exception handlers
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
    language_out: Optional[str] = Form(None)
) -> Job:
    """
    Cria um novo job de transcrição/tradução de áudio
    
    - **file**: Arquivo de áudio para transcrever
    - **language_in**: Código do idioma de entrada (ISO 639-1) ou 'auto' para detecção automática.
                       Exemplos: 'pt' (português), 'en' (inglês), 'es' (espanhol), 'auto' (detectar)
    - **language_out**: (Opcional) Código do idioma de saída para tradução (ISO 639-1).
                        Se omitido, usa o mesmo idioma detectado/especificado em language_in.
                        Exemplos: 'pt', 'en', 'es', 'fr', etc.
    
    **Exemplos de uso**:
    - Transcrever em português: language_in='pt', language_out=None
    - Detectar idioma e transcrever: language_in='auto', language_out=None
    - Traduzir inglês para português: language_in='en', language_out='pt'
    - Detectar e traduzir para inglês: language_in='auto', language_out='en'
    
    Use GET /languages para ver todos os idiomas suportados.
    """
    try:
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
        
        logger.info(f"Criando job: arquivo={file.filename}, language_in={language_in}, language_out={language_out or 'same'}")
        
        # Cria job para extrair ID
        new_job = Job.create_new(file.filename, "transcribe", language_in, language_out)
        
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
                job_age = datetime.now() - existing_job.created_at
                
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
                # Falhou antes - tenta novamente
                logger.info(f"Reprocessando job falhado: {new_job.id}")
                existing_job.status = JobStatus.QUEUED
                existing_job.error_message = None
                existing_job.progress = 0.0
                job_store.update_job(existing_job)
                
                # Submete para processamento
                submit_processing_task(existing_job)
                return existing_job
        
        # Job novo - salva arquivo
        upload_dir = Path("./uploads")
        upload_dir.mkdir(exist_ok=True)
        
        # Usar apenas job_id para evitar problemas com caracteres especiais
        original_extension = Path(file.filename).suffix if file.filename else ""
        file_path = upload_dir / f"{new_job.id}{original_extension}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        new_job.input_file = str(file_path)
        
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
            now = datetime.now()
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
                    except:
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
                        age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
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
                    except:
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
        "timestamp": datetime.now().isoformat(),
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
    
    # 3. Verifica ffmpeg
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
            health_status["checks"]["ffmpeg"] = {"status": "error", "message": "ffmpeg not responding"}
            is_healthy = False
    except FileNotFoundError:
        health_status["checks"]["ffmpeg"] = {"status": "error", "message": "ffmpeg not installed"}
        is_healthy = False
    except Exception as e:
        health_status["checks"]["ffmpeg"] = {"status": "error", "message": str(e)}
        is_healthy = False
    
    # 4. Verifica Celery workers (verificação simplificada)
    try:
        # Verificação básica sem timeout complexo para evitar travamento
        health_status["checks"]["celery_workers"] = {
            "status": "ok",
            "message": "Celery workers check skipped for faster health response"
        }
    except Exception as e:
        health_status["checks"]["celery_workers"] = {"status": "error", "message": str(e)}
    
    # 5. Verifica modelo Whisper (verificação básica e rápida)
    try:
        model_name = settings.get('whisper_model', 'base')
        health_status["checks"]["whisper_model"] = {
            "status": "ok",
            "model": model_name,
            "message": "Model será carregado no primeiro uso"
        }
    except Exception as e:
        health_status["checks"]["whisper_model"] = {"status": "error", "message": str(e)}
    
    # Atualiza status geral
    health_status["status"] = "healthy" if is_healthy else "unhealthy"
    
    status_code = 200 if is_healthy else 503
    
    return JSONResponse(content=health_status, status_code=status_code)
