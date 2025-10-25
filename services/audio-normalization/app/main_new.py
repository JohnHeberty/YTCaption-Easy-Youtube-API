"""
Audio Normalization Service - Aplicação principal
Versão 2.0 com alta resiliência, observabilidade e boas práticas
"""
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings, AppSettings
from app.logging_config import setup_logging, get_logger
from app.models import Job, JobStatus, JobResponse, ProcessingOptionsRequest
from app.processor_new import AudioProcessor
from app.redis_store_new import RedisJobStore
from app.security_validator import ValidationMiddleware, RateLimiter
from app.observability import PrometheusMetrics, HealthChecker, ObservabilityManager
from app.instrumentation import get_tracing, trace_function
from app.exceptions import ValidationError, ResourceError, ProcessingError, SecurityError
from app.resource_manager import ResourceMonitor, TempFileManager

# Configuração inicial
settings = get_settings()
setup_logging(settings.log_level.upper())
logger = get_logger(__name__)

# Instâncias globais
job_store: Optional[RedisJobStore] = None
audio_processor: Optional[AudioProcessor] = None
validation_middleware: Optional[ValidationMiddleware] = None
observability_manager: Optional[ObservabilityManager] = None
resource_monitor: Optional[ResourceMonitor] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciamento do ciclo de vida da aplicação"""
    logger.info(f"🚀 Iniciando {settings.app_name} v{settings.version}")
    
    # Inicialização
    await initialize_services()
    
    # Configura instrumentação distribuída
    if settings.monitoring.enable_tracing:
        tracing = get_tracing()
        tracing.instrument_fastapi_app(app)
        logger.info("📡 Instrumentação distribuída configurada")
    
    logger.info("✅ Serviços inicializados com sucesso")
    
    yield
    
    # Shutdown
    await cleanup_services()
    logger.info("👋 Serviços finalizados")


async def initialize_services():
    """Inicializa todos os serviços da aplicação"""
    global job_store, audio_processor, validation_middleware, observability_manager, resource_monitor
    
    try:
        # Monitor de recursos
        resource_monitor = ResourceMonitor()
        
        # Job store
        job_store = RedisJobStore(settings)
        await job_store.initialize()
        
        # Processador de áudio
        audio_processor = AudioProcessor()
        
        # Middleware de validação
        validation_middleware = ValidationMiddleware()
        
        # Observabilidade
        observability_manager = ObservabilityManager(settings)
        await observability_manager.initialize()
        
        # Verifica saúde inicial do sistema
        health = await resource_monitor.check_system_health()
        if not health.healthy:
            logger.warning(f"⚠️ Sistema com recursos limitados: {health.warnings}")
        
    except Exception as e:
        logger.error(f"❌ Falha na inicialização dos serviços: {e}")
        raise


async def cleanup_services():
    """Limpa recursos dos serviços"""
    global job_store, observability_manager
    
    try:
        if job_store:
            await job_store.cleanup_expired()
            
        if observability_manager:
            await observability_manager.shutdown()
            
    except Exception as e:
        logger.warning(f"⚠️ Erro durante cleanup: {e}")


# Criação da aplicação FastAPI
app = FastAPI(
    title=settings.app_name,
    description="Microserviço resiliente para normalização de áudio com observabilidade completa",
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

# Middlewares de segurança
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", settings.host]
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["http://localhost", "https://localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"]
)


# Dependências
def get_job_store() -> RedisJobStore:
    """Dependência para obter job store"""
    if job_store is None:
        raise HTTPException(status_code=503, detail="Job store not available")
    return job_store


def get_audio_processor() -> AudioProcessor:
    """Dependência para obter processador de áudio"""
    if audio_processor is None:
        raise HTTPException(status_code=503, detail="Audio processor not available")
    return audio_processor


def get_validation_middleware() -> ValidationMiddleware:
    """Dependência para obter middleware de validação"""
    if validation_middleware is None:
        raise HTTPException(status_code=503, detail="Validation middleware not available")
    return validation_middleware


def get_resource_monitor() -> ResourceMonitor:
    """Dependência para obter monitor de recursos"""
    if resource_monitor is None:
        raise HTTPException(status_code=503, detail="Resource monitor not available")
    return resource_monitor


# Endpoints de saúde e métricas
@app.get("/health", tags=["Health"])
async def health_check():
    """Verifica saúde do serviço"""
    try:
        monitor = get_resource_monitor()
        health = await monitor.check_system_health()
        
        return {
            "status": "healthy" if health.healthy else "degraded",
            "timestamp": health.timestamp,
            "checks": health.checks,
            "warnings": health.warnings if not health.healthy else []
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """Expõe métricas Prometheus"""
    if observability_manager:
        return await observability_manager.get_metrics()
    return {"message": "Metrics not available"}


@app.get("/readiness", tags=["Health"])
async def readiness_check(store: RedisJobStore = Depends(get_job_store)):
    """Verifica se o serviço está pronto para receber requests"""
    try:
        # Testa conectividade com Redis
        is_ready = await store.health_check()
        
        if is_ready:
            return {"status": "ready", "message": "Service is ready to accept requests"}
        else:
            raise HTTPException(status_code=503, detail="Service not ready - Redis unavailable")
            
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


# Endpoints principais de processamento
@app.post("/upload", response_model=JobResponse, tags=["Processing"])
@trace_function("upload_audio_file")
async def upload_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    remove_noise: bool = False,
    normalize_volume: bool = True,
    convert_to_mono: bool = False,
    apply_highpass_filter: bool = False,
    set_sample_rate_16k: bool = False,
    isolate_vocals: bool = False,
    store: RedisJobStore = Depends(get_job_store),
    validator: ValidationMiddleware = Depends(get_validation_middleware),
    processor: AudioProcessor = Depends(get_audio_processor)
):
    """
    Faz upload e processa arquivo de áudio
    
    - **file**: Arquivo de áudio (MP3, WAV, FLAC)
    - **remove_noise**: Remove ruído de fundo
    - **normalize_volume**: Normaliza volume
    - **convert_to_mono**: Converte para mono
    - **apply_highpass_filter**: Aplica filtro passa-alta
    - **set_sample_rate_16k**: Define sample rate para 16kHz
    - **isolate_vocals**: Isola vocais (experimental)
    """
    try:
        # Obter IP do cliente para rate limiting
        client_ip = request.client.host
        
        # Validação de arquivo e segurança
        file_result, security_result = await validator.validate_upload(file, client_ip)
        
        if not file_result.valid:
            raise ValidationError(f"Invalid file: {file_result.error}")
        
        if not security_result.safe:
            raise SecurityError(f"Security check failed: {security_result.reason}")
        
        # Salva arquivo temporariamente
        temp_manager = TempFileManager()
        with temp_manager.temp_file(suffix=f".{file_result.format}") as temp_path:
            # Lê e salva conteúdo do arquivo
            content = await file.read()
            temp_path.write_bytes(content)
            
            # Cria job
            job = Job.create_new(
                input_file=str(temp_path),
                remove_noise=remove_noise,
                normalize_volume=normalize_volume,
                convert_to_mono=convert_to_mono,
                apply_highpass_filter=apply_highpass_filter,
                set_sample_rate_16k=set_sample_rate_16k,
                isolate_vocals=isolate_vocals
            )
            
            # Salva job
            store.save_job(job)
            
            # Agenda processamento em background
            background_tasks.add_task(process_audio_background, job.id, str(temp_path))
            
            logger.info(f"📄 Job {job.id} criado para arquivo: {file.filename}")
            
            return JobResponse(
                job_id=job.id,
                status=job.status,
                message="Job created successfully",
                created_at=job.created_at,
                expires_at=job.expires_at
            )
            
    except (ValidationError, SecurityError) as e:
        logger.warning(f"⚠️ Upload rejected: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except ResourceError as e:
        logger.error(f"💾 Resource error during upload: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    
    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/process", response_model=JobResponse, tags=["Processing"])
@trace_function("process_audio_job")
async def process_audio_with_options(
    request: ProcessingOptionsRequest,
    background_tasks: BackgroundTasks,
    store: RedisJobStore = Depends(get_job_store)
):
    """
    Cria job de processamento com opções customizadas
    
    Aceita configurações detalhadas de processamento via JSON
    """
    try:
        # Cria job com opções customizadas
        job = Job.create_new(
            input_file=request.input_file,
            **request.model_dump(exclude={"input_file"})
        )
        
        # Salva job
        store.save_job(job)
        
        # Agenda processamento
        background_tasks.add_task(process_audio_background, job.id, request.input_file)
        
        logger.info(f"🔧 Job customizado {job.id} criado")
        
        return JobResponse(
            job_id=job.id,
            status=job.status,
            message="Custom processing job created",
            created_at=job.created_at,
            expires_at=job.expires_at
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to create processing job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/jobs/{job_id}", response_model=JobResponse, tags=["Jobs"])
@trace_function("get_job_status")
async def get_job_status(
    job_id: str,
    store: RedisJobStore = Depends(get_job_store)
):
    """Consulta status de um job"""
    try:
        job = store.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobResponse(
            job_id=job.id,
            status=job.status,
            message=job.error_message if job.status == JobStatus.FAILED else "Job found",
            output_file=job.output_file,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            expires_at=job.expires_at,
            processing_options={
                "remove_noise": job.remove_noise,
                "normalize_volume": job.normalize_volume,
                "convert_to_mono": job.convert_to_mono,
                "apply_highpass_filter": job.apply_highpass_filter,
                "set_sample_rate_16k": job.set_sample_rate_16k,
                "isolate_vocals": job.isolate_vocals
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/jobs", tags=["Jobs"])
@trace_function("list_jobs")
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 10,
    store: RedisJobStore = Depends(get_job_store)
):
    """Lista jobs com filtros opcionais"""
    try:
        jobs = store.list_jobs(status=status, limit=limit)
        
        return {
            "jobs": [
                {
                    "job_id": job.id,
                    "status": job.status,
                    "created_at": job.created_at,
                    "input_file": job.input_file
                }
                for job in jobs
            ],
            "total": len(jobs)
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/download/{job_id}", tags=["Files"])
@trace_function("download_processed_file")
async def download_processed_file(
    job_id: str,
    store: RedisJobStore = Depends(get_job_store)
):
    """Download do arquivo processado"""
    try:
        job = store.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Job not completed")
        
        if not job.output_file or not Path(job.output_file).exists():
            raise HTTPException(status_code=404, detail="Output file not found")
        
        filename = f"processed_{job_id}.mp3"
        
        return FileResponse(
            job.output_file,
            media_type="audio/mpeg",
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/jobs/{job_id}", tags=["Jobs"])
@trace_function("delete_job")
async def delete_job(
    job_id: str,
    store: RedisJobStore = Depends(get_job_store)
):
    """Remove um job e seus arquivos"""
    try:
        job = store.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Remove arquivos se existirem
        if job.output_file and Path(job.output_file).exists():
            Path(job.output_file).unlink()
        
        # Remove job do store
        store.delete_job(job_id)
        
        logger.info(f"🗑️ Job {job_id} removido")
        
        return {"message": "Job deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Função de background para processamento
@trace_function("background_audio_processing")
async def process_audio_background(job_id: str, input_file: str):
    """Processa áudio em background"""
    try:
        # Obtém job
        job = job_store.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found for background processing")
            return
        
        # Inicia processamento
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now()
        job_store.save_job(job)
        
        # Processa áudio
        result = await audio_processor.process_audio(job)
        
        # Atualiza job com resultado
        if result.success:
            job.status = JobStatus.COMPLETED
            job.output_file = result.output_file
            job.completed_at = datetime.now()
            logger.info(f"✅ Job {job_id} completed successfully")
        else:
            job.status = JobStatus.FAILED
            job.error_message = result.error
            logger.error(f"❌ Job {job_id} failed: {result.error}")
        
        job_store.save_job(job)
        
    except Exception as e:
        # Marca job como falhado
        try:
            job = job_store.get_job(job_id)
            if job:
                job.status = JobStatus.FAILED
                job.error_message = f"Background processing failed: {str(e)}"
                job_store.save_job(job)
        except:
            pass  # Evita erro duplo
        
        logger.error(f"❌ Background processing failed for job {job_id}: {e}")


# Handler global de exceções
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handler para erros de validação"""
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "error_code": exc.error_code}
    )


@app.exception_handler(SecurityError)
async def security_exception_handler(request: Request, exc: SecurityError):
    """Handler para erros de segurança"""
    logger.warning(f"Security error: {exc}")
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc), "error_code": exc.error_code}
    )


@app.exception_handler(ResourceError)
async def resource_exception_handler(request: Request, exc: ResourceError):
    """Handler para erros de recurso"""
    logger.error(f"Resource error: {exc}")
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable", "error_code": exc.error_code}
    )


@app.exception_handler(ProcessingError)
async def processing_exception_handler(request: Request, exc: ProcessingError):
    """Handler para erros de processamento"""
    logger.error(f"Processing error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "error_code": exc.error_code}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)