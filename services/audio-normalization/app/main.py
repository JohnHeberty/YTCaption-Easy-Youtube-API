import asyncio
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import List
import logging

from .models import Job, AudioProcessingRequest, JobStatus
from .processor import AudioProcessor
from .redis_store import RedisJobStore
from .config import get_settings
from .logging_config import setup_logging, get_logger
from .exceptions import AudioProcessingError, ValidationError, SecurityError

# Configuração inicial
settings = get_settings()
setup_logging("audio-normalization", settings['log_level'])
logger = get_logger(__name__)

# Instâncias globais
app = FastAPI(
    title="Audio Normalization Service",
    description="Microserviço para normalização de áudio com cache de 24h",
    version="2.0.0"
)

# Importa e adiciona middleware de segurança
from .security import SecurityMiddleware, validate_audio_file
app.add_middleware(SecurityMiddleware)

# Exception handlers
@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "type": "validation_error"}
    )

@app.exception_handler(SecurityError)
async def security_exception_handler(request, exc):
    logger.error(f"Security error: {exc}")
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc), "type": "security_error"}
    )

@app.exception_handler(AudioProcessingError)
async def processing_exception_handler(request, exc):
    logger.error(f"Processing error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": "processing_error"}
    )

# Usa Redis como store compartilhado
redis_url = settings['redis_url']
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
    """Submete job para processamento em background via Celery"""
    try:
        from .celery_config import celery_app
        from .celery_tasks import normalize_audio_task
        
        # Envia job para o worker Celery
        task_result = normalize_audio_task.apply_async(
            args=[job.model_dump()], 
            task_id=job.id  # Usa o job ID como task ID
        )
        logger.info(f"📤 Job {job.id} enviado para Celery worker: {task_result.id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar job {job.id} para Celery: {e}")
        logger.error(f"❌ Fallback: processando diretamente job {job.id}")
        # Fallback para processamento direto se Celery falhar
        import asyncio
        asyncio.create_task(processor.process_audio_job(job))


@app.post("/jobs", response_model=Job)
async def create_audio_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    remove_noise: str = Form("false"),
    convert_to_mono: str = Form("false"),
    apply_highpass_filter: str = Form("false"),
    set_sample_rate_16k: str = Form("false"),
    isolate_vocals: str = Form("false")
) -> Job:
    """
    Cria um novo job de processamento de áudio
    
    **IMPORTANTE**: Aceita QUALQUER formato de áudio como entrada e SEMPRE retorna .webm
    
    - **file**: Arquivo de áudio (qualquer formato: .mp3, .wav, .m4a, .ogg, etc.)
    - **remove_noise**: Remove ruído de fundo (padrão: False)
    - **convert_to_mono**: Converte para mono (padrão: False)  
    - **apply_highpass_filter**: Aplica filtro high-pass (padrão: False)
    - **set_sample_rate_16k**: Define sample rate para 16kHz (padrão: False)
    - **isolate_vocals**: Isola vocais usando OpenUnmix (padrão: False)
    
    Se nenhum parâmetro for True, apenas converte o arquivo para .webm.
    """
    try:
        # Validação 1: Arquivo está presente?
        if not file:
            logger.error("Nenhum arquivo foi enviado")
            raise HTTPException(status_code=400, detail="Nenhum arquivo enviado")
        
        # Validação 2: Arquivo tem nome?
        if not file.filename:
            logger.error("Arquivo sem nome")
            raise HTTPException(status_code=400, detail="Arquivo sem nome")
        
        logger.info(f"Recebido request para processar: {file.filename}")
        
        # Converte strings form-data para boolean
        def str_to_bool(value: str) -> bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        
        remove_noise_bool = str_to_bool(remove_noise)
        convert_to_mono_bool = str_to_bool(convert_to_mono)
        apply_highpass_filter_bool = str_to_bool(apply_highpass_filter)
        set_sample_rate_16k_bool = str_to_bool(set_sample_rate_16k)
        isolate_vocals_bool = str_to_bool(isolate_vocals)
        
        logger.info(f"🔍 DEBUG Parâmetros convertidos:")
        logger.info(f"  remove_noise: '{remove_noise}' -> {remove_noise_bool}")
        logger.info(f"  apply_highpass_filter: '{apply_highpass_filter}' -> {apply_highpass_filter_bool}")
        logger.info(f"  isolate_vocals: '{isolate_vocals}' -> {isolate_vocals_bool}")
        
        # Cria job com parâmetros de processamento
        new_job = Job.create_new(
            filename=file.filename,
            remove_noise=remove_noise_bool,
            convert_to_mono=convert_to_mono_bool,
            apply_highpass_filter=apply_highpass_filter_bool,
            set_sample_rate_16k=set_sample_rate_16k_bool,
            isolate_vocals=isolate_vocals_bool
        )
        
        # Verifica se já existe job com mesmo ID (cache baseado no arquivo + operações)
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            # Job já existe - verifica status
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} já completado - retornando do cache")
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
        
        # Job novo - lê arquivo
        try:
            content = await file.read()
            logger.info(f"Arquivo lido: {len(content)} bytes")
        except Exception as e:
            logger.error(f"Erro ao ler arquivo: {e}")
            raise HTTPException(status_code=400, detail=f"Erro ao ler arquivo: {str(e)}")
        
        # Validação 3: Arquivo não está vazio?
        if not content or len(content) == 0:
            logger.error("Arquivo vazio")
            raise HTTPException(status_code=400, detail="Arquivo está vazio")
        
        # Validação 4: Arquivo não excede limite de tamanho?
        max_size = 100 * 1024 * 1024  # 100MB
        if len(content) > max_size:
            logger.error(f"Arquivo muito grande: {len(content)} bytes")
            raise HTTPException(
                status_code=413,
                detail=f"Arquivo muito grande. Máximo: {max_size//1024//1024}MB"
            )
        
        # Validação básica de segurança (apenas tamanho - sem validar formato)
        try:
            validate_audio_file(file.filename, content)
            logger.info(f"Validação básica concluída: {file.filename}")
        except (ValidationError, SecurityError) as e:
            logger.error(f"Validação básica falhou para {file.filename}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        
        logger.info("IMPORTANTE: Validação real de formato será feita com ffprobe durante processamento")
        
        # Salva arquivo
        upload_dir = Path("./uploads")
        try:
            upload_dir.mkdir(exist_ok=True, parents=True)
        except Exception as e:
            logger.error(f"Erro ao criar diretório: {e}")
            raise HTTPException(status_code=500, detail="Erro ao criar diretório de upload")
        
        file_path = upload_dir / f"{new_job.id}_{file.filename}"
        try:
            with open(file_path, "wb") as f:
                f.write(content)
            logger.info(f"Arquivo salvo em: {file_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo: {e}")
            raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {str(e)}")
        
        new_job.input_file = str(file_path)
        new_job.file_size_input = file_path.stat().st_size
        
        # Salva job e submete para processamento
        try:
            job_store.save_job(new_job)
            submit_processing_task(new_job)
            logger.info(f"Job {new_job.id} criado e submetido para processamento")
        except Exception as e:
            logger.error(f"Erro ao salvar job: {e}")
            # Limpa arquivo se falhou
            if file_path.exists():
                file_path.unlink()
            raise HTTPException(status_code=500, detail=f"Erro ao criar job: {str(e)}")
        
        return new_job
        
    except HTTPException:
        # Re-lança HTTPExceptions
        raise
    except Exception as e:
        # Captura qualquer erro inesperado
        logger.error(f"Erro inesperado ao criar job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    🛡️ ENDPOINT RESILIENTE - Consulta status de um job
    GARANTIA: Este endpoint NUNCA quebra, mesmo com jobs corrompidos
    
    Args:
        job_id: ID do job a consultar
        
    Returns:
        dict: Dados do job com status atual (formato flexível para resiliência)
    """
    # PRIMEIRA LINHA DE DEFESA - Validação de entrada
    if not job_id or len(job_id.strip()) == 0:
        logger.error("❌ Job ID vazio ou inválido")
        raise HTTPException(status_code=400, detail="Job ID inválido")
    
    job_id = job_id.strip()
    logger.info(f"🔍 Consultando status do job: {job_id}")
    
    try:
        # SEGUNDA LINHA DE DEFESA - Busca no Redis/Store
        job = None
        try:
            job = job_store.get_job(job_id)
            logger.info(f"📦 Job encontrado no store: {job_id}")
        except Exception as store_err:
            logger.error(f"⚠️ Erro ao buscar job {job_id} no store: {store_err}")
            # Continua para tentar buscar no Celery
        
        # TERCEIRA LINHA DE DEFESA - Consulta status no Celery se store falhou
        celery_status = None
        celery_meta = None
        
        try:
            from .celery_config import celery_app
            task_result = celery_app.AsyncResult(job_id)
            celery_status = task_result.state
            celery_meta = task_result.info if hasattr(task_result, 'info') else {}
            
            logger.info(f"🔧 Celery status para job {job_id}: {celery_status}")
            
            # Se o Celery tem informações e o store não
            if not job and celery_status in ['SUCCESS', 'FAILURE', 'PENDING', 'RETRY', 'REVOKED']:
                logger.info(f"📋 Reconstruindo job {job_id} a partir do Celery")
                
                # Reconstrói informações básicas do job
                if celery_status == 'FAILURE' and isinstance(celery_meta, dict):
                    return {
                        "id": job_id,
                        "status": "failed",
                        "error_message": celery_meta.get('error', 'Unknown error'),
                        "progress": celery_meta.get('progress', 0.0),
                        "created_at": None,
                        "completed_at": None,
                        "source": "celery_recovery"
                    }
                elif celery_status == 'SUCCESS' and isinstance(celery_meta, dict):
                    return {
                        "id": job_id,
                        "status": "completed",
                        "progress": celery_meta.get('progress', 100.0),
                        "output_file": celery_meta.get('output_file'),
                        "created_at": None,
                        "completed_at": None,
                        "source": "celery_recovery"
                    }
                elif celery_status == 'PENDING':
                    return {
                        "id": job_id,
                        "status": "queued",
                        "progress": 0.0,
                        "created_at": None,
                        "completed_at": None,
                        "source": "celery_recovery"
                    }
                
        except Exception as celery_err:
            logger.error(f"⚠️ Erro ao consultar Celery para job {job_id}: {celery_err}")
            # Continua mesmo se Celery falhar
        
        # QUARTA LINHA DE DEFESA - Validação do job encontrado
        if job:
            try:
                # Verifica se job está expirado
                if hasattr(job, 'is_expired') and job.is_expired:
                    logger.info(f"⏰ Job expirado: {job_id}")
                    return {
                        "id": job_id,
                        "status": "expired",
                        "error_message": "Job expired",
                        "progress": 0.0,
                        "source": "store_expired"
                    }
                
                # Converte job para dict de forma segura
                if hasattr(job, 'model_dump'):
                    job_dict = job.model_dump()
                elif hasattr(job, 'dict'):
                    job_dict = job.dict()
                else:
                    # Fallback manual
                    job_dict = {
                        "id": getattr(job, 'id', job_id),
                        "status": getattr(job, 'status', 'unknown'),
                        "progress": getattr(job, 'progress', 0.0),
                        "error_message": getattr(job, 'error_message', None),
                        "created_at": getattr(job, 'created_at', None),
                        "completed_at": getattr(job, 'completed_at', None),
                        "source": "store_manual"
                    }
                
                # Enriquece com informações do Celery se disponível
                if celery_status and celery_meta:
                    job_dict["celery_status"] = celery_status
                    if celery_status == 'FAILURE' and isinstance(celery_meta, dict):
                        if not job_dict.get("error_message"):
                            job_dict["error_message"] = celery_meta.get('error', 'Processing failed')
                
                logger.info(f"✅ Job {job_id} status: {job_dict.get('status', 'unknown')}")
                return job_dict
                
            except Exception as job_err:
                logger.error(f"💥 Erro ao processar job {job_id}: {job_err}")
                # Fallback para formato mínimo
                return {
                    "id": job_id,
                    "status": "error",
                    "error_message": f"Job processing error: {str(job_err)}",
                    "progress": 0.0,
                    "source": "error_fallback"
                }
        
        # QUINTA LINHA DE DEFESA - Job completamente não encontrado
        logger.warning(f"🚫 Job não encontrado: {job_id}")
        raise HTTPException(status_code=404, detail="Job não encontrado")
        
    except HTTPException:
        # Re-raise HTTP exceptions (são controladas)
        raise
    except Exception as catastrophic_err:
        # SEXTA LINHA DE DEFESA - Falha catastrófica
        error_msg = f"CATASTROPHIC ERROR querying job {job_id}: {str(catastrophic_err)}"
        logger.critical(error_msg, exc_info=True)
        
        # Retorna erro estruturado em vez de quebrar
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Internal server error",
                "job_id": job_id,
                "details": "Unable to retrieve job status due to internal error",
                "support": "Check server logs for details"
            }
        )


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