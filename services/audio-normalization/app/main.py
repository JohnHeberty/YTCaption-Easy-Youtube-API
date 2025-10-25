import asyncio
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import List

from .models import Job, JobRequest, JobStatus
from .processor import AudioProcessor
from .redis_store import RedisJobStore

# Instâncias globais
app = FastAPI(
    title="Audio Normalization Service",
    description="Microserviço para normalização de áudio com cache de 24h",
    version="2.0.0"
)

# Usa Redis como store compartilhado
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
job_store = RedisJobStore(redis_url=redis_url)
processor = AudioProcessor()

# Injeta referência do job_store no processor para updates de progresso
processor.job_store = job_store


@app.on_event("startup")
async def startup_event():
    """Inicializa sistema"""
    await job_store.start_cleanup_task()
    print("✅ Serviço de normalização iniciado")


@app.on_event("shutdown") 
async def shutdown_event():
    """Para sistema"""
    await job_store.stop_cleanup_task()
    print("🛑 Serviço parado graciosamente")


def submit_processing_task(job: Job):
    """Submete job para processamento em background"""
    # Por agora, processamento direto (pode ser melhorado com Celery depois)
    asyncio.create_task(processor.process_audio_job(job))


@app.post("/jobs", response_model=Job)
async def create_audio_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
) -> Job:
    """
    Cria um novo job de normalização de áudio
    
    - **file**: Arquivo de áudio para processar
    """
    # Cria job para extrair ID
    new_job = Job.create_new(file.filename, "normalize")
    
    # Verifica se já existe job com mesmo ID
    existing_job = job_store.get_job(new_job.id)
    
    if existing_job:
        # Job já existe - verifica status
        if existing_job.status == JobStatus.COMPLETED:
            return existing_job
        elif existing_job.status in [JobStatus.QUEUED, JobStatus.PROCESSING]:
            return existing_job
        elif existing_job.status == JobStatus.FAILED:
            # Falhou antes - tenta novamente
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
    
    return new_job


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
    """Faz download do arquivo processado"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")
        
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425, 
            detail=f"Processamento não pronto. Status: {job.status}"
        )
    
    file_path = Path(job.output_file) if job.output_file else None
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        path=file_path,
        filename=f"normalized_{job_id}.wav",
        media_type='application/octet-stream'
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
    processed_path = Path("./processed")
    
    total_files = 0
    total_size = 0
    
    for path in [upload_path, processed_path]:
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
        "service": "audio-normalization", 
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }