"""
Sistema completo de observabilidade para Audio Transcriber
Métricas Prometheus, health checks, instrumentação distribuída
"""
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.config import AppSettings
from app.logging_config import get_logger
from app.resource_manager import get_resource_monitor

logger = get_logger(__name__)


@dataclass
class HealthStatus:
    """Status de saúde de um componente"""
    name: str
    healthy: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class PrometheusMetrics:
    """Métricas Prometheus customizadas para Audio Transcriber"""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # Métricas de transcrição
        self.transcription_requests = Counter(
            'transcriber_requests_total',
            'Total transcription requests',
            ['status', 'language', 'format'],
            registry=self.registry
        )
        
        self.transcription_duration = Histogram(
            'transcriber_processing_duration_seconds',
            'Transcription processing time',
            ['language', 'model'],
            registry=self.registry
        )
        
        self.audio_duration_processed = Histogram(
            'transcriber_audio_duration_seconds',
            'Duration of audio processed',
            ['language'],
            registry=self.registry
        )
        
        self.file_size_processed = Histogram(
            'transcriber_file_size_bytes',
            'Size of files processed',
            ['format'],
            registry=self.registry
        )
        
        self.active_transcriptions = Gauge(
            'transcriber_active_jobs',
            'Number of active transcription jobs',
            registry=self.registry
        )
        
        self.whisper_model_loads = Counter(
            'transcriber_model_loads_total',
            'Total Whisper model loads',
            ['model', 'device'],
            registry=self.registry
        )
        
        self.transcription_errors = Counter(
            'transcriber_errors_total',
            'Total transcription errors',
            ['error_type', 'error_code'],
            registry=self.registry
        )
        
        # Métricas de sistema
        self.system_cpu_usage = Gauge(
            'transcriber_cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_usage = Gauge(
            'transcriber_memory_usage_percent',
            'Memory usage percentage',
            registry=self.registry
        )
        
        self.system_gpu_memory_usage = Gauge(
            'transcriber_gpu_memory_usage_percent',
            'GPU memory usage percentage',
            registry=self.registry
        )
    
    def record_transcription_request(self, status: str, language: str, format: str):
        """Registra request de transcrição"""
        self.transcription_requests.labels(
            status=status,
            language=language,
            format=format
        ).inc()
    
    def record_transcription_duration(self, duration: float, language: str, model: str):
        """Registra duração de transcrição"""
        self.transcription_duration.labels(
            language=language,
            model=model
        ).observe(duration)
    
    def record_audio_processed(self, duration: float, language: str):
        """Registra áudio processado"""
        self.audio_duration_processed.labels(language=language).observe(duration)
    
    def record_file_size(self, size_bytes: int, format: str):
        """Registra tamanho de arquivo"""
        self.file_size_processed.labels(format=format).observe(size_bytes)
    
    def set_active_jobs(self, count: int):
        """Define número de jobs ativos"""
        self.active_transcriptions.set(count)
    
    def record_model_load(self, model: str, device: str):
        """Registra carregamento de modelo"""
        self.whisper_model_loads.labels(model=model, device=device).inc()
    
    def record_error(self, error_type: str, error_code: str):
        """Registra erro"""
        self.transcription_errors.labels(
            error_type=error_type,
            error_code=error_code
        ).inc()
    
    def update_system_metrics(self, cpu_percent: float, memory_percent: float, gpu_memory_percent: Optional[float] = None):
        """Atualiza métricas de sistema"""
        self.system_cpu_usage.set(cpu_percent)
        self.system_memory_usage.set(memory_percent)
        if gpu_memory_percent is not None:
            self.system_gpu_memory_usage.set(gpu_memory_percent)
    
    def get_metrics_text(self) -> str:
        """Retorna métricas em formato Prometheus"""
        return generate_latest(self.registry).decode('utf-8')


class HealthChecker:
    """Verificador de saúde do sistema"""
    
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.resource_monitor = get_resource_monitor()
    
    async def check_redis_health(self) -> HealthStatus:
        """Verifica saúde do Redis"""
        try:
            from app.redis_store import get_redis_store
            store = get_redis_store()
            
            # Testa ping
            await asyncio.wait_for(store.health_check(), timeout=5.0)
            
            return HealthStatus(
                name="redis",
                healthy=True,
                message="Redis connection healthy"
            )
            
        except asyncio.TimeoutError:
            return HealthStatus(
                name="redis",
                healthy=False,
                message="Redis connection timeout"
            )
        except Exception as e:
            return HealthStatus(
                name="redis",
                healthy=False,
                message=f"Redis error: {str(e)}"
            )
    
    async def check_whisper_health(self) -> HealthStatus:
        """Verifica saúde do Whisper"""
        try:
            # Tenta importar e verificar Whisper
            import whisper
            
            model_name = self.settings.transcription.whisper_model
            device = self.settings.transcription.whisper_device
            
            # Verifica se modelo pode ser carregado (sem carregá-lo realmente)
            available_models = whisper.available_models()
            
            if model_name not in available_models:
                return HealthStatus(
                    name="whisper",
                    healthy=False,
                    message=f"Model {model_name} not available",
                    details={"available_models": available_models}
                )
            
            return HealthStatus(
                name="whisper",
                healthy=True,
                message=f"Whisper ready with model {model_name}",
                details={
                    "model": model_name,
                    "device": device,
                    "available_models": available_models
                }
            )
            
        except ImportError:
            return HealthStatus(
                name="whisper",
                healthy=False,
                message="Whisper not installed"
            )
        except Exception as e:
            return HealthStatus(
                name="whisper",
                healthy=False,
                message=f"Whisper error: {str(e)}"
            )
    
    async def check_system_health(self) -> HealthStatus:
        """Verifica saúde do sistema"""
        try:
            health = await self.resource_monitor.check_system_health()
            
            return HealthStatus(
                name="system",
                healthy=health.healthy,
                message="System resources OK" if health.healthy else "System resources degraded",
                details={
                    "checks": health.checks,
                    "warnings": health.warnings
                }
            )
            
        except Exception as e:
            return HealthStatus(
                name="system",
                healthy=False,
                message=f"System check error: {str(e)}"
            )
    
    async def check_storage_health(self) -> HealthStatus:
        """Verifica saúde do armazenamento"""
        try:
            from pathlib import Path
            
            # Verifica diretórios necessários
            required_dirs = [
                self.settings.upload_dir,
                self.settings.transcriptions_dir,
                self.settings.models_dir,
                self.settings.temp_dir
            ]
            
            issues = []
            for dir_path in required_dirs:
                if not dir_path.exists():
                    issues.append(f"Directory missing: {dir_path}")
                elif not dir_path.is_dir():
                    issues.append(f"Not a directory: {dir_path}")
                else:
                    # Testa escrita
                    try:
                        test_file = dir_path / f".health_check_{time.time()}"
                        test_file.touch()
                        test_file.unlink()
                    except Exception:
                        issues.append(f"Cannot write to: {dir_path}")
            
            if issues:
                return HealthStatus(
                    name="storage",
                    healthy=False,
                    message="Storage issues detected",
                    details={"issues": issues}
                )
            
            return HealthStatus(
                name="storage",
                healthy=True,
                message="Storage accessible"
            )
            
        except Exception as e:
            return HealthStatus(
                name="storage",
                healthy=False,
                message=f"Storage check error: {str(e)}"
            )
    
    async def get_comprehensive_health(self) -> Dict[str, Any]:
        """Obtém verificação completa de saúde"""
        checks = await asyncio.gather(
            self.check_redis_health(),
            self.check_whisper_health(),
            self.check_system_health(),
            self.check_storage_health(),
            return_exceptions=True
        )
        
        health_results = {}
        overall_healthy = True
        
        for check in checks:
            if isinstance(check, Exception):
                health_results["unknown"] = {
                    "healthy": False,
                    "message": f"Health check failed: {str(check)}"
                }
                overall_healthy = False
            else:
                health_results[check.name] = {
                    "healthy": check.healthy,
                    "message": check.message,
                    "details": check.details
                }
                if not check.healthy:
                    overall_healthy = False
        
        return {
            "status": "healthy" if overall_healthy else "degraded",
            "timestamp": datetime.now().isoformat(),
            "checks": health_results,
            "service": "audio-transcriber",
            "version": self.settings.version
        }


class DistributedTracing:
    """Instrumentação distribuída com OpenTelemetry"""
    
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.tracer: Optional[trace.Tracer] = None
        self.meter: Optional[metrics.Meter] = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """Inicializa instrumentação distribuída"""
        if not self.settings.monitoring.enable_tracing:
            logger.info("Distributed tracing disabled")
            return True
        
        try:
            # Resource para identificar o serviço
            resource = Resource.create({
                "service.name": "audio-transcriber",
                "service.version": self.settings.version,
                "service.environment": self.settings.environment
            })
            
            # Configura tracer
            trace_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(trace_provider)
            self.tracer = trace.get_tracer(__name__)
            
            # Configura meter
            meter_provider = MeterProvider(resource=resource)
            metrics.set_meter_provider(meter_provider)
            self.meter = metrics.get_meter(__name__)
            
            self._initialized = True
            logger.info("Distributed tracing initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize distributed tracing: {e}")
            return False
    
    def instrument_fastapi_app(self, app):
        """Instrumenta aplicação FastAPI"""
        if not self._initialized:
            return
        
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumentation enabled")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}")


class ObservabilityManager:
    """Gerenciador principal de observabilidade"""
    
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.metrics = PrometheusMetrics()
        self.health_checker = HealthChecker(settings)
        self.tracing = DistributedTracing(settings)
        self._metrics_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Inicializa todos os componentes de observabilidade"""
        try:
            # Inicializa instrumentação distribuída
            self.tracing.initialize()
            
            # Inicia tarefas de background
            if self.settings.monitoring.enable_prometheus:
                self._metrics_task = asyncio.create_task(self._update_metrics_periodically())
                logger.info("Metrics collection started")
            
            # Inicia limpeza periódica
            self._cleanup_task = asyncio.create_task(self._cleanup_periodically())
            
            logger.info("Observability manager initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize observability: {e}")
            raise
    
    async def shutdown(self):
        """Para todos os componentes"""
        if self._metrics_task:
            self._metrics_task.cancel()
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        logger.info("Observability manager shut down")
    
    async def _update_metrics_periodically(self):
        """Atualiza métricas de sistema periodicamente"""
        try:
            while True:
                try:
                    # Obtém uso de recursos
                    resource_monitor = get_resource_monitor()
                    usage = resource_monitor.get_resource_usage()
                    
                    # Atualiza métricas Prometheus
                    self.metrics.update_system_metrics(
                        cpu_percent=usage.cpu_percent,
                        memory_percent=usage.memory_percent,
                        gpu_memory_percent=usage.gpu_memory_percent
                    )
                    
                    # Atualiza número de jobs ativos
                    from app.resource_manager import get_processing_limiter
                    limiter = get_processing_limiter()
                    active_jobs = len(limiter.get_active_jobs())
                    self.metrics.set_active_jobs(active_jobs)
                    
                except Exception as e:
                    logger.error(f"Error updating metrics: {e}")
                
                await asyncio.sleep(30)  # Atualiza a cada 30 segundos
                
        except asyncio.CancelledError:
            pass
    
    async def _cleanup_periodically(self):
        """Executa limpeza periódica"""
        try:
            while True:
                try:
                    # Limpa arquivos temporários antigos
                    from app.resource_manager import get_temp_file_manager
                    temp_manager = get_temp_file_manager()
                    temp_manager.cleanup_old_files(max_age_hours=24)
                    
                    # Limpa rate limiter
                    from app.security_validator import get_validation_middleware
                    validator = get_validation_middleware()
                    await validator.rate_limiter.cleanup_old_entries()
                    
                except Exception as e:
                    logger.error(f"Error during periodic cleanup: {e}")
                
                await asyncio.sleep(3600)  # Limpa a cada hora
                
        except asyncio.CancelledError:
            pass
    
    async def get_metrics(self) -> str:
        """Retorna métricas Prometheus"""
        return self.metrics.get_metrics_text()
    
    async def get_health(self) -> Dict[str, Any]:
        """Retorna status de saúde completo"""
        return await self.health_checker.get_comprehensive_health()


# Instâncias globais
_observability_manager: Optional[ObservabilityManager] = None


def get_observability_manager() -> ObservabilityManager:
    """Obtém instância global do observability manager"""
    global _observability_manager
    if _observability_manager is None:
        from app.config import get_settings
        settings = get_settings()
        _observability_manager = ObservabilityManager(settings)
    return _observability_manager


# Decorators para instrumentação
def trace_transcription(operation_name: str):
    """Decorator para rastreamento de operações de transcrição"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            manager = get_observability_manager()
            
            if not manager.tracing._initialized:
                return await func(*args, **kwargs)
            
            with manager.tracing.tracer.start_as_current_span(operation_name) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error", str(e))
                    raise
        return wrapper
    return decorator