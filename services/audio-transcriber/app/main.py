import asyncio
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import List
import logging

from .models import Job, JobRequest, JobStatus, TranscriptionResponse
from .processor import TranscriptionProcessor
from .redis_store import RedisJobStore
from .logging_config import setup_logging
from .exceptions import AudioTranscriptionException, ServiceException, exception_handler
from .security import SecurityMiddleware, validate_audio_file
from .config import get_settings

# Configuração de logging
setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

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
    """Submete job para processamento em background"""
    asyncio.create_task(processor.process_transcription_job(job))


@app.post("/jobs", response_model=Job)
async def create_transcription_job(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
) -> Job:
    """
    Cria um novo job de transcrição de áudio
    
    - **file**: Arquivo de áudio para transcrever
    """
    try:
        # Validação de segurança
        file_content = await file.read()
        await file.seek(0)  # Reset para ler novamente depois
        validate_audio_file(file.filename, file_content)
        logger.info(f"Criando job de transcrição para arquivo: {file.filename}")
        
        # Cria job para extrair ID
        new_job = Job.create_new(file.filename, "transcribe")
        
        # Verifica se já existe job com mesmo ID
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            # Job já existe - verifica status
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} já completado")
                return existing_job
            elif existing_job.status in [JobStatus.QUEUED, JobStatus.PROCESSING]:
                logger.info(f"Job {new_job.id} já em processamento")
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
    
    return TranscriptionResponse(
        transcription_id=job.id,
        filename=job.filename or "unknown",
        language=job.language,
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
    """Remove job e arquivo associado"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    # Remove arquivos se existirem
    if job.input_file:
        input_path = Path(job.input_file)
        if input_path.exists():
            input_path.unlink()
    
    if job.output_file:
        output_path = Path(job.output_file)
        if output_path.exists():
            output_path.unlink()
    
    return {"message": "Job removido com sucesso"}


@app.post("/admin/cleanup")
async def manual_cleanup():
    """Força limpeza manual de arquivos expirados"""
    removed = await job_store.cleanup_expired()
    return {"message": f"Removidos {removed} jobs expirados"}


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