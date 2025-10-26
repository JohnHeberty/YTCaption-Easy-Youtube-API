"""
Aplicação principal do Audio Transcriber Service
Versão resiliente com gerenciamento completo do ciclo de vida
"""
import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn

from .config import get_settings
from .models import (
    Job, JobStatus, JobResponse, TranscriptionRequest, 
    ProcessingResult, TranscriptionStats
)
from .processor import TranscriptionProcessor
from .resource_manager import ResourceMonitor, TempFileManager
from .security_validator import FileValidator, ValidationMiddleware, RateLimiter
from .observability import ObservabilityManager
from .logging_config import create_logger, setup_request_logging
from .exceptions import (
    TranscriptionError, AudioProcessingError, ModelLoadError,
    ValidationError, ResourceError
)

# Storage para jobs (em produção, usar Redis)
from .storage import JobStorage

)

logger = create_logger(__name__)


class TranscriptionApp:
    """
    Classe principal da aplicação de transcrição
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.processor = TranscriptionProcessor()
        self.job_storage = JobStorage()
        self.resource_monitor = ResourceMonitor()
        self.temp_manager = TempFileManager()
        self.file_validator = FileValidator()
        self.observability = ObservabilityManager()
        self.rate_limiter = RateLimiter()
        
        # FastAPI app
        self.app = FastAPI(
            title="Audio Transcriber Service",
            description="High-resilience audio transcription service with Whisper",
            version="2.0.0",
            lifespan=self.lifespan
        )
        
        # Security
        self.security = HTTPBearer(auto_error=False)
        
        # Setup da aplicação
        self._setup_middleware()
        self._setup_routes()
        self._setup_exception_handlers()
    
    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """Gerenciamento do ciclo de vida da aplicação"""
        
        # Startup
        logger.info("Starting Audio Transcriber Service")
        
        try:
            # Inicializa componentes
            await self._startup()
            
            # Sinal de que está pronto
            logger.info("Audio Transcriber Service is ready!")
            
            yield
            
        finally:
            # Shutdown
            logger.info("Shutting down Audio Transcriber Service")
            await self._shutdown()
    
    async def _startup(self):
        """Inicialização da aplicação"""
        
        # Verifica recursos do sistema
        if not await self.resource_monitor.system_health_check():
            raise RuntimeError("System health check failed")
        
        # Inicia observabilidade
        await self.observability.start()
        
        # Verifica diretórios necessários
        self._ensure_directories()
        
        # Inicia limpeza automática
        asyncio.create_task(self._periodic_cleanup())
        
        logger.info("Application startup completed")
    
    async def _shutdown(self):
        """Finalização da aplicação"""
        
        # Para observabilidade
        await self.observability.stop()
        
        # Limpa arquivos temporários
        await self.temp_manager.cleanup_all()
        
        logger.info("Application shutdown completed")
    
    def _ensure_directories(self):
        """Garante que diretórios necessários existem"""
        
        dirs_to_create = [
            self.settings.transcription.output_dir,
            self.settings.transcription.upload_dir,
            self.settings.transcription.model_cache_dir
        ]
        
        for dir_path in dirs_to_create:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"Directory ensured: {dir_path}")
    
    async def _periodic_cleanup(self):
        """Limpeza periódica de jobs expirados"""
        
        while True:
            try:
                await asyncio.sleep(3600)  # A cada hora
                
                # Remove jobs expirados
                expired_jobs = await self.job_storage.get_expired_jobs()
                
                for job in expired_jobs:
                    # Limpa arquivos do job
                    await self.processor.cleanup_job_files(job)
                    
                    # Remove do storage
                    await self.job_storage.delete_job(job.id)
                    
                    logger.info(f"Cleaned up expired job: {job.id}")
                
                # Limpa arquivos temporários antigos
                await self.temp_manager.cleanup_old_files(hours=24)
                
                logger.info(f"Periodic cleanup completed, removed {len(expired_jobs)} jobs")
                
            except Exception as e:
                logger.error(f"Periodic cleanup failed: {e}")
    
    def _setup_middleware(self):
        """Configura middlewares"""
        
        # CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.settings.cors.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Rate limiting e validação
        self.app.add_middleware(ValidationMiddleware)
        
        # Request logging
        setup_request_logging(self.app)
    
    def _setup_routes(self):
        """Configura rotas da API"""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            health = await self.observability.health_checker.check_all()
            
            status_code = status.HTTP_200_OK if health["healthy"] else status.HTTP_503_SERVICE_UNAVAILABLE
            
            return JSONResponse(
                status_code=status_code,
                content=health
            )
        
        @self.app.get("/metrics")
        async def metrics():
            """Prometheus metrics endpoint"""
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
            
            metrics_data = generate_latest()
            return Response(
                metrics_data,
                media_type=CONTENT_TYPE_LATEST
            )
        
        @self.app.post("/transcribe", response_model=JobResponse)
        async def create_transcription_job(
            background_tasks: BackgroundTasks,
            file: UploadFile = File(...),
            language: str = "auto",
            output_format: str = "srt",
            enable_vad: bool = True,
            beam_size: int = 5,
            temperature: float = 0.0,
            priority: str = "normal",
            token: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """
            Cria job de transcrição de áudio
            """
            
            # Rate limiting
            client_ip = "unknown"  # Em produção, extrair do request
            if not await self.rate_limiter.check_rate_limit(client_ip):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )
            
            # Valida arquivo
            validation_result = await self.file_validator.validate_audio_file(
                file.filename, 
                await file.read()
            )
            
            if not validation_result.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file: {validation_result.error}"
                )
            
            # Reset file position
            await file.seek(0)
            
            try:
                # Salva arquivo
                upload_dir = Path(self.settings.transcription.upload_dir)
                file_path = await self._save_upload_file(file, upload_dir)
                
                # Cria job
                job = Job.create_new(
                    input_file=str(file_path),
                    language=language,
                    output_format=output_format,
                    enable_vad=enable_vad,
                    beam_size=beam_size,
                    temperature=temperature,
                    priority=priority,
                    file_size_input=validation_result.file_size,
                    audio_duration=validation_result.duration,
                    sample_rate=validation_result.sample_rate,
                    channels=validation_result.channels
                )
                
                # Verifica se já existe resultado em cache
                existing_job = await self.job_storage.get_job(job.id)
                if existing_job and existing_job.is_completed:
                    logger.info(f"Returning cached result for job: {job.id}")
                    return self._job_to_response(existing_job)
                
                # Salva job
                await self.job_storage.save_job(job)
                
                # Inicia processamento em background
                background_tasks.add_task(self._process_job_async, job)
                
                logger.info(f"Created transcription job: {job.id}")
                return self._job_to_response(job)
                
            except Exception as e:
                logger.error(f"Failed to create transcription job: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create transcription job"
                )
        
        @self.app.get("/jobs/{job_id}", response_model=JobResponse)
        async def get_job_status(job_id: str):
            """
            Consulta status de um job
            """
            
            job = await self.job_storage.get_job(job_id)
            
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            return self._job_to_response(job)
        
        @self.app.delete("/jobs/{job_id}")
        async def cancel_job(job_id: str):
            """
            Cancela um job
            """
            
            job = await self.job_storage.get_job(job_id)
            
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            if job.is_completed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Job already completed"
                )
            
            # Marca como cancelado
            job.mark_as_cancelled()
            await self.job_storage.save_job(job)
            
            # Limpa arquivos
            await self.processor.cleanup_job_files(job)
            
            return {"message": "Job cancelled successfully"}
        
        @self.app.get("/jobs/{job_id}/download")
        async def download_result(job_id: str):
            """
            Download do arquivo de resultado
            """
            
            job = await self.job_storage.get_job(job_id)
            
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            if not job.is_completed or not job.output_file:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Job not completed or output file not available"
                )
            
            if not Path(job.output_file).exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Output file not found"
                )
            
            return FileResponse(
                path=job.output_file,
                filename=f"transcription_{job_id}.{job.output_format}",
                media_type="application/octet-stream"
            )
        
        @self.app.get("/jobs", response_model=List[JobResponse])
        async def list_jobs(
            status_filter: Optional[str] = None,
            limit: int = 50,
            offset: int = 0
        ):
            """
            Lista jobs com filtros opcionais
            """
            
            jobs = await self.job_storage.list_jobs(
                status=status_filter,
                limit=limit,
                offset=offset
            )
            
            return [self._job_to_response(job) for job in jobs]
        
        @self.app.get("/stats", response_model=TranscriptionStats)
        async def get_stats():
            """
            Estatísticas do serviço
            """
            
            return await self.job_storage.get_stats()
        
        @self.app.get("/system/info")
        async def get_system_info():
            """
            Informações do sistema
            """
            
            return {
                "service": "audio-transcriber",
                "version": "2.0.0",
                "processing_stats": await self.processor.get_processing_stats(),
                "resource_usage": await self.resource_monitor.get_current_usage(),
                "system_health": await self.observability.health_checker.check_all()
            }
    
    def _setup_exception_handlers(self):
        """Configura tratamento de exceções"""
        
        @self.app.exception_handler(ValidationError)
        async def validation_exception_handler(request, exc):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": str(exc)}
            )
        
        @self.app.exception_handler(TranscriptionError)
        async def transcription_exception_handler(request, exc):
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": f"Transcription error: {str(exc)}"}
            )
        
        @self.app.exception_handler(ResourceError)
        async def resource_exception_handler(request, exc):
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": f"Resource error: {str(exc)}"}
            )
    
    async def _save_upload_file(self, file: UploadFile, upload_dir: Path) -> Path:
        """Salva arquivo de upload"""
        
        # Gera nome único
        import uuid
        unique_name = f"{uuid.uuid4()}_{file.filename}"
        file_path = upload_dir / unique_name
        
        # Escreve arquivo
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        return file_path
    
    def _job_to_response(self, job: Job) -> JobResponse:
        """Converte Job para JobResponse"""
        
        return JobResponse(
            job_id=job.id,
            status=job.status,
            message=self._get_status_message(job),
            created_at=job.created_at,
            expires_at=job.expires_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            output_file=f"/jobs/{job.id}/download" if job.output_file else None,
            transcription_text=job.transcription_text,
            processing_options={
                "language": job.language,
                "output_format": job.output_format,
                "detected_language": job.detected_language,
                "confidence_score": job.confidence_score,
                "audio_duration": job.audio_duration,
                "processing_time": job.processing_time,
                "real_time_factor": job.real_time_factor
            }
        )
    
    def _get_status_message(self, job: Job) -> str:
        """Gera mensagem de status"""
        
        if job.status == JobStatus.QUEUED:
            return "Job is queued for processing"
        elif job.status == JobStatus.PROCESSING:
            return f"Processing... {job.progress:.1f}% complete"
        elif job.status == JobStatus.COMPLETED:
            return "Transcription completed successfully"
        elif job.status == JobStatus.FAILED:
            return f"Job failed: {job.error_message}"
        elif job.status == JobStatus.CANCELLED:
            return "Job was cancelled"
        
        return "Unknown status"
    
    async def _process_job_async(self, job: Job):
        """Processa job em background"""
        
        try:
            logger.info(f"Starting background processing for job: {job.id}")
            
            # Processa transcrição
            result = await self.processor.process_transcription(job)
            
            # Atualiza job com resultado
            await self.job_storage.save_job(job)
            
            if result.success:
                logger.info(f"Job {job.id} completed successfully")
            else:
                logger.error(f"Job {job.id} failed: {result.error}")
                
        except Exception as e:
            logger.error(f"Background processing failed for job {job.id}: {e}")
            
            # Marca job como falhado
            job.mark_as_failed(str(e))
            await self.job_storage.save_job(job)


# Instância global da aplicação
transcription_app = TranscriptionApp()
app = transcription_app.app


def run_server():
    """Executa o servidor"""
    
    settings = get_settings()
    
    # Configuração do servidor
    config = uvicorn.Config(
        app=app,
        host=settings.server.host,
        port=settings.server.port,
        log_config=None,  # Usamos nosso próprio logging
        access_log=False,  # Desativa log de acesso padrão
        reload=settings.debug,
        workers=1 if settings.debug else settings.server.workers
    )
    
    server = uvicorn.Server(config)
    
    # Setup de signal handlers para shutdown graceful
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        server.should_exit = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Executa servidor
    try:
        logger.info(f"Starting server on {settings.server.host}:{settings.server.port}")
        server.run()
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_server()