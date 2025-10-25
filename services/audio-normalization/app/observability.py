"""
Sistema completo de observabilidade com métricas Prometheus e health checks
"""
import time
import asyncio
import psutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path

from prometheus_client import (
    Counter, Histogram, Gauge, Info, 
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry, REGISTRY
)
from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse

from .config import get_settings
from .exceptions import BaseServiceError

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Status de saúde dos componentes"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Saúde de um componente individual"""
    name: str
    status: HealthStatus
    message: str = ""
    response_time_ms: Optional[float] = None
    last_check: datetime = field(default_factory=datetime.now)
    error_details: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "response_time_ms": self.response_time_ms,
            "last_check": self.last_check.isoformat(),
            "error_details": self.error_details
        }


class PrometheusMetrics:
    """Coletor de métricas Prometheus"""
    
    def __init__(self, registry: CollectorRegistry = None):
        self.registry = registry or REGISTRY
        self.settings = get_settings()
        
        # Limpa registry antes de criar métricas (evita duplicatas em restart)
        try:
            for collector in list(self.registry._collector_to_names.keys()):
                if hasattr(collector, '_name') and 'audio_normalization' in collector._name:
                    self.registry.unregister(collector)
        except:
            pass  # Ignora erros de limpeza
        
        # Métricas de aplicação
        self.app_info = Info(
            'audio_normalization_app_info',
            'Application information',
            registry=self.registry
        )
        
        # Métricas de requests
        self.requests_total = Counter(
            'audio_normalization_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.request_duration = Histogram(
            'audio_normalization_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # Métricas de processamento
        self.jobs_total = Counter(
            'audio_normalization_jobs_total',
            'Total processing jobs',
            ['status', 'operation_type'],
            registry=self.registry
        )
        
        self.job_duration = Histogram(
            'audio_normalization_job_duration_seconds',
            'Job processing duration',
            ['operation_type', 'status'],
            registry=self.registry
        )
        
        self.job_file_size = Histogram(
            'audio_normalization_job_file_size_bytes',
            'Job input file size',
            ['operation_type'],
            buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600],  # 1KB to 100MB
            registry=self.registry
        )
        
        # Métricas de sistema
        self.system_cpu_usage = Gauge(
            'audio_normalization_cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_usage = Gauge(
            'audio_normalization_memory_usage_bytes',
            'Memory usage in bytes',
            registry=self.registry
        )
        
        self.system_disk_usage = Gauge(
            'audio_normalization_disk_usage_bytes',
            'Disk usage in bytes',
            ['directory'],
            registry=self.registry
        )
        
        # Métricas de cache/Redis
        self.cache_operations = Counter(
            'audio_normalization_cache_operations_total',
            'Cache operations',
            ['operation', 'result'],
            registry=self.registry
        )
        
        self.cache_hit_rate = Gauge(
            'audio_normalization_cache_hit_rate',
            'Cache hit rate',
            registry=self.registry
        )
        
        self.active_jobs = Gauge(
            'audio_normalization_active_jobs',
            'Number of active jobs',
            registry=self.registry
        )
        
        # Métricas de worker/Celery
        self.celery_workers = Gauge(
            'audio_normalization_celery_workers_active',
            'Active Celery workers',
            registry=self.registry
        )
        
        self.celery_queue_size = Gauge(
            'audio_normalization_celery_queue_size',
            'Celery queue size',
            registry=self.registry
        )
        
        # Métricas de erro
        self.errors_total = Counter(
            'audio_normalization_errors_total',
            'Total errors',
            ['error_type', 'severity', 'component'],
            registry=self.registry
        )
        
        # Info da aplicação
        self.app_info.info({
            'version': self.settings.version,
            'environment': self.settings.environment,
            'name': self.settings.app_name
        })
        
        logger.info("Prometheus metrics initialized")
    
    def record_request(
        self, 
        method: str, 
        endpoint: str, 
        status_code: int, 
        duration_seconds: float
    ):
        """Registra métrica de request"""
        self.requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration_seconds)
    
    def record_job(
        self,
        job_id: str,
        operation_type: str,
        status: str,
        duration_seconds: float,
        file_size_bytes: int = None
    ):
        """Registra métrica de job"""
        self.jobs_total.labels(
            status=status,
            operation_type=operation_type
        ).inc()
        
        self.job_duration.labels(
            operation_type=operation_type,
            status=status
        ).observe(duration_seconds)
        
        if file_size_bytes:
            self.job_file_size.labels(
                operation_type=operation_type
            ).observe(file_size_bytes)
    
    def record_error(self, error: BaseServiceError, component: str = "unknown"):
        """Registra métrica de erro"""
        self.errors_total.labels(
            error_type=error.error_code,
            severity=error.severity.value,
            component=component
        ).inc()
    
    def record_cache_operation(self, operation: str, hit: bool):
        """Registra operação de cache"""
        result = "hit" if hit else "miss"
        self.cache_operations.labels(
            operation=operation,
            result=result
        ).inc()
    
    def update_system_metrics(self):
        """Atualiza métricas de sistema"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=None)
            self.system_cpu_usage.set(cpu_percent)
            
            # Memória
            memory = psutil.virtual_memory()
            self.system_memory_usage.set(memory.used)
            
            # Uso de disco por diretório
            for dir_name in ['uploads', 'processed', 'temp']:
                dir_path = getattr(self.settings, f"{dir_name}_dir", None)
                if dir_path and Path(dir_path).exists():
                    usage = sum(
                        f.stat().st_size 
                        for f in Path(dir_path).rglob('*') 
                        if f.is_file()
                    )
                    self.system_disk_usage.labels(directory=dir_name).set(usage)
                    
        except Exception as e:
            logger.warning(f"Failed to update system metrics: {e}")


class HealthChecker:
    """Verificador de saúde dos componentes"""
    
    def __init__(self, metrics: PrometheusMetrics = None):
        self.settings = get_settings()
        self.metrics = metrics
        self._component_checkers = {}
        
        # Registra checkers padrão
        self._register_default_checkers()
    
    def _register_default_checkers(self):
        """Registra verificadores padrão"""
        self.register_checker("redis", self._check_redis)
        self.register_checker("celery", self._check_celery)
        self.register_checker("disk_space", self._check_disk_space)
        self.register_checker("memory", self._check_memory)
        self.register_checker("cpu", self._check_cpu)
    
    def register_checker(self, name: str, checker_func):
        """Registra um verificador customizado"""
        self._component_checkers[name] = checker_func
    
    async def check_all_components(self) -> Dict[str, ComponentHealth]:
        """Verifica saúde de todos os componentes"""
        results = {}
        
        for name, checker in self._component_checkers.items():
            try:
                start_time = time.time()
                result = await self._run_checker(checker, name)
                result.response_time_ms = (time.time() - start_time) * 1000
                results[name] = result
                
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {str(e)}",
                    error_details=str(e)
                )
        
        return results
    
    async def _run_checker(self, checker, name: str) -> ComponentHealth:
        """Executa um verificador específico"""
        if asyncio.iscoroutinefunction(checker):
            return await checker()
        else:
            return checker()
    
    def _check_redis(self) -> ComponentHealth:
        """Verifica saúde do Redis"""
        try:
            from redis import Redis
            
            redis_client = Redis.from_url(
                self.settings.get_redis_url(),
                socket_connect_timeout=2,
                socket_timeout=2
            )
            
            # Teste de ping
            redis_client.ping()
            
            # Verifica informações
            info = redis_client.info()
            used_memory_mb = info.get('used_memory', 0) / 1024 / 1024
            connected_clients = info.get('connected_clients', 0)
            
            return ComponentHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                message=f"Connected with {connected_clients} clients, {used_memory_mb:.1f}MB used"
            )
            
        except Exception as e:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message="Redis connection failed",
                error_details=str(e)
            )
    
    def _check_celery(self) -> ComponentHealth:
        """Verifica saúde do Celery"""
        try:
            from .celery_config import celery_app
            
            inspect = celery_app.control.inspect()
            
            # Verifica workers ativos
            active_workers = inspect.active()
            
            if active_workers is None:
                return ComponentHealth(
                    name="celery",
                    status=HealthStatus.UNHEALTHY,
                    message="No Celery workers responding"
                )
            
            worker_count = len(active_workers)
            total_tasks = sum(len(tasks) for tasks in active_workers.values())
            
            if self.metrics:
                self.metrics.celery_workers.set(worker_count)
            
            status = HealthStatus.HEALTHY if worker_count > 0 else HealthStatus.DEGRADED
            
            return ComponentHealth(
                name="celery",
                status=status,
                message=f"{worker_count} workers active, {total_tasks} tasks running"
            )
            
        except Exception as e:
            return ComponentHealth(
                name="celery",
                status=HealthStatus.UNHEALTHY,
                message="Celery check failed",
                error_details=str(e)
            )
    
    def _check_disk_space(self) -> ComponentHealth:
        """Verifica espaço em disco"""
        try:
            directories = {
                'uploads': self.settings.upload_dir,
                'processed': self.settings.processed_dir,
                'temp': self.settings.temp_dir
            }
            
            issues = []
            total_usage_mb = 0
            
            for name, dir_path in directories.items():
                if not dir_path.exists():
                    continue
                
                # Calcula uso
                usage_bytes = sum(
                    f.stat().st_size 
                    for f in dir_path.rglob('*') 
                    if f.is_file()
                )
                usage_mb = usage_bytes / 1024 / 1024
                total_usage_mb += usage_mb
                
                # Verifica limites
                if usage_mb > 500:  # 500MB por diretório
                    issues.append(f"{name}: {usage_mb:.1f}MB")
            
            if issues:
                return ComponentHealth(
                    name="disk_space",
                    status=HealthStatus.DEGRADED,
                    message=f"High disk usage: {', '.join(issues)}"
                )
            
            return ComponentHealth(
                name="disk_space",
                status=HealthStatus.HEALTHY,
                message=f"Total usage: {total_usage_mb:.1f}MB"
            )
            
        except Exception as e:
            return ComponentHealth(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message="Disk check failed",
                error_details=str(e)
            )
    
    def _check_memory(self) -> ComponentHealth:
        """Verifica uso de memória"""
        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            
            if self.metrics:
                self.metrics.system_memory_usage.set(memory.used)
            
            if usage_percent > 90:
                status = HealthStatus.UNHEALTHY
                message = f"Critical memory usage: {usage_percent:.1f}%"
            elif usage_percent > 80:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage: {usage_percent:.1f}%"
            
            return ComponentHealth(
                name="memory",
                status=status,
                message=message
            )
            
        except Exception as e:
            return ComponentHealth(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message="Memory check failed",
                error_details=str(e)
            )
    
    def _check_cpu(self) -> ComponentHealth:
        """Verifica uso de CPU"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1.0)
            
            if self.metrics:
                self.metrics.system_cpu_usage.set(cpu_percent)
            
            if cpu_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Critical CPU usage: {cpu_percent:.1f}%"
            elif cpu_percent > 80:
                status = HealthStatus.DEGRADED
                message = f"High CPU usage: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage: {cpu_percent:.1f}%"
            
            return ComponentHealth(
                name="cpu",
                status=status,
                message=message
            )
            
        except Exception as e:
            return ComponentHealth(
                name="cpu",
                status=HealthStatus.UNKNOWN,
                message="CPU check failed",
                error_details=str(e)
            )


class ObservabilityManager:
    """Gerenciador central de observabilidade"""
    
    def __init__(self):
        self.settings = get_settings()
        self.metrics = PrometheusMetrics() if self.settings.monitoring.enable_prometheus else None
        self.health_checker = HealthChecker(self.metrics)
        
        # Task para atualização periódica de métricas
        self._metrics_task = None
        self._is_running = False
    
    async def start(self):
        """Inicia sistema de observabilidade"""
        if self._is_running:
            return
        
        self._is_running = True
        
        if self.metrics:
            self._metrics_task = asyncio.create_task(self._metrics_update_loop())
            logger.info("Observability system started with Prometheus metrics")
        else:
            logger.info("Observability system started without metrics")
    
    async def stop(self):
        """Para sistema de observabilidade"""
        self._is_running = False
        
        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Observability system stopped")
    
    async def _metrics_update_loop(self):
        """Loop de atualização de métricas"""
        while self._is_running:
            try:
                if self.metrics:
                    self.metrics.update_system_metrics()
                
                await asyncio.sleep(30)  # Atualiza a cada 30 segundos
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")
                await asyncio.sleep(30)
    
    def setup_fastapi_routes(self, app: FastAPI):
        """Configura rotas de observabilidade no FastAPI"""
        
        @app.get("/metrics", response_class=PlainTextResponse)
        async def get_metrics():
            """Endpoint de métricas Prometheus"""
            if not self.metrics:
                return "Metrics not enabled"
            
            return generate_latest(self.metrics.registry)
        
        @app.get("/health")
        async def health_check():
            """Health check básico"""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        @app.get("/health/detailed")
        async def detailed_health_check():
            """Health check detalhado"""
            components = await self.health_checker.check_all_components()
            
            # Determina status geral
            statuses = [comp.status for comp in components.values()]
            
            if any(status == HealthStatus.UNHEALTHY for status in statuses):
                overall_status = HealthStatus.UNHEALTHY
            elif any(status == HealthStatus.DEGRADED for status in statuses):
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.HEALTHY
            
            return {
                "status": overall_status.value,
                "timestamp": datetime.now().isoformat(),
                "components": {name: comp.to_dict() for name, comp in components.items()},
                "summary": {
                    "total_components": len(components),
                    "healthy": sum(1 for c in components.values() if c.status == HealthStatus.HEALTHY),
                    "degraded": sum(1 for c in components.values() if c.status == HealthStatus.DEGRADED),
                    "unhealthy": sum(1 for c in components.values() if c.status == HealthStatus.UNHEALTHY)
                }
            }
        
        @app.get("/health/ready")
        async def readiness_check():
            """Readiness probe para Kubernetes"""
            # Verifica componentes críticos
            critical_components = await self.health_checker.check_all_components()
            
            critical_services = ["redis"]  # Serviços críticos para funcionamento
            
            for service in critical_services:
                if service in critical_components:
                    if critical_components[service].status == HealthStatus.UNHEALTHY:
                        return Response(
                            content=f"Service {service} is unhealthy",
                            status_code=503
                        )
            
            return {"status": "ready"}
        
        @app.get("/health/live")
        async def liveness_check():
            """Liveness probe para Kubernetes"""
            # Verifica se a aplicação está viva (não travada)
            return {"status": "alive", "timestamp": datetime.now().isoformat()}


# Instância global do gerenciador de observabilidade
observability_manager = ObservabilityManager()