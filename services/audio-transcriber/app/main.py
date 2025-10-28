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
from .security import SecurityMiddleware, validate_audio_file
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

# Middleware de segurança
app.add_middleware(SecurityMiddleware)

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
        
        # Validação de segurança
        file_content = await file.read()
        await file.seek(0)  # Reset para ler novamente depois
        validate_audio_file(file.filename, file_content)
        
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
        
        file_path = upload_dir / f"{new_job.id}_{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        new_job.input_file = str(file_path)
        
        # Salva job e submete para processamento
        job_store.save_job(new_job)
        submit_processing_task(new_job)
        
        logger.info(f"Job de transcrição criado: {new_job.id}")
        return new_job
        
    except Exception as e:
        logger.error(f"Erro ao criar job de transcrição: {e}")
        if isinstance(e, (AudioTranscriptionException, ServiceException)):
            raise
        raise ServiceException(f"Erro interno ao processar arquivo: {str(e)}")


@app.get("/languages")
async def get_supported_languages():
    """
    Retorna lista de linguagens suportadas pelo Whisper.
    
    - **auto**: Detecção automática de idioma
    - Códigos ISO 639-1 para idiomas específicos (en, pt, es, etc.)
    """
    languages = get_supported_languages()
    models = get_whisper_models()
    
    return {
        "supported_languages": languages,
        "total_languages": len(languages),
        "models": models,
        "default_language": settings.get("whisper_default_language", "auto"),
        "note": "Use 'auto' para detecção automática ou código ISO 639-1 específico"
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


async def _perform_cleanup():
    """
    Executa limpeza COMPLETA do sistema em background
    
    ZERA ABSOLUTAMENTE TUDO:
    - TODOS os jobs do Redis (não só expirados)
    - TODOS os arquivos de uploads/
    - TODOS os arquivos de transcriptions/
    - TODOS os arquivos temporários
    - TODOS os modelos baixados em models/
    """
    try:
        report = {
            "jobs_removed": 0,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "models_deleted": 0,
            "errors": []
        }
        
        logger.warning("🔥 INICIANDO LIMPEZA TOTAL DO SISTEMA - TUDO SERÁ REMOVIDO!")
        
        # 1. LIMPAR TODOS OS JOBS DO REDIS (não só expirados)
        try:
            keys = job_store.redis.keys("transcription_job:*")
            if keys:
                for key in keys:
                    job_store.redis.delete(key)
                report["jobs_removed"] = len(keys)
                logger.info(f"🗑️  Redis: {len(keys)} jobs removidos")
            else:
                logger.info("✓ Redis: nenhum job encontrado")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"Redis: {str(e)}")
        
        # 2. LIMPAR TODOS OS ARQUIVOS DE UPLOADS
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
async def manual_cleanup(background_tasks: BackgroundTasks):
    """
    🔥 LIMPEZA TOTAL DO SISTEMA (RESILIENTE)
    
    ⚠️ ATENÇÃO: Este endpoint ZERA ABSOLUTAMENTE TUDO:
    
    1. TODOS os jobs do Redis (não só expirados)
    2. TODOS os arquivos de uploads/
    3. TODOS os arquivos de transcriptions/
    4. TODOS os arquivos temporários em temp/
    5. TODOS os modelos Whisper baixados em models/ (~500MB cada)
    
    Use este endpoint para resetar completamente o sistema.
    A limpeza é executada em background e retorna imediatamente.
    
    Returns:
        - cleanup_id: ID da operação de limpeza
        - status: "processing"
        - message: Mensagem informativa
    """
    # Cria um job para a limpeza
    cleanup_job_id = f"cleanup_total_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Agenda limpeza TOTAL em background
    background_tasks.add_task(_perform_cleanup)
    
    logger.warning(f"🔥 LIMPEZA TOTAL agendada: {cleanup_job_id}")
    
    return {
        "message": "🔥 LIMPEZA TOTAL iniciada em background - TUDO será removido!",
        "cleanup_id": cleanup_job_id,
        "status": "processing",
        "warning": "Esta operação removerá TODOS os jobs, arquivos e modelos do sistema",
        "note": "Verifique os logs para acompanhar o progresso e resultados."
    }


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
    """Health check simples"""
    return {
        "status": "healthy",
        "service": "audio-transcription", 
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }