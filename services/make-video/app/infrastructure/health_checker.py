"""
Comprehensive Health Checks - Sprint-07

Sistema de health checks para todas as dependências.
"""

import asyncio
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class HealthCheckResult:
    """Resultado de um health check"""
    
    def __init__(self, healthy: bool, details: str, latency_ms: Optional[float] = None):
        self.healthy = healthy
        self.details = details
        self.latency_ms = latency_ms
    
    def to_dict(self) -> Dict:
        result = {
            "healthy": self.healthy,
            "details": self.details
        }
        if self.latency_ms is not None:
            result["latency_ms"] = round(self.latency_ms, 2)
        return result


class HealthChecker:
    """
    Sistema de health checks para dependências.
    
    Verifica:
    - Redis (conexão e latência)
    - Microserviços externos (youtube-search, video-downloader, audio-transcriber)
    - Espaço em disco
    - Celery workers (opcional)
    """
    
    def __init__(self):
        self.redis_store = None
        self.api_client = None
        self.settings = None
        logger.info("✅ HealthChecker initialized")
    
    def set_dependencies(self, redis_store, api_client, settings):
        """Configura dependências (chamado após inicialização)"""
        self.redis_store = redis_store
        self.api_client = api_client
        self.settings = settings
    
    async def check_redis(self) -> HealthCheckResult:
        """
        Verifica saúde do Redis.
        
        Testa:
        - Conexão
        - Latência de ping
        - Operações básicas (set/get)
        """
        if self.redis_store is None:
            return HealthCheckResult(False, "Not initialized")
        
        start = datetime.now()
        
        try:
            # Ping básico
            await asyncio.wait_for(
                self.redis_store.redis.ping(),
                timeout=2.0
            )
            
            # Teste de set/get
            test_key = "health:check:test"
            test_value = str(datetime.now().timestamp())
            
            await asyncio.wait_for(
                self.redis_store.redis.set(test_key, test_value, ex=5),
                timeout=1.0
            )
            
            retrieved = await asyncio.wait_for(
                self.redis_store.redis.get(test_key),
                timeout=1.0
            )
            
            if retrieved != test_value:
                return HealthCheckResult(False, "Set/Get mismatch")
            
            # Calcular latência
            latency_ms = (datetime.now() - start).total_seconds() * 1000
            
            return HealthCheckResult(True, "OK", latency_ms)
        
        except asyncio.TimeoutError:
            latency_ms = (datetime.now() - start).total_seconds() * 1000
            return HealthCheckResult(False, f"Timeout (>{latency_ms:.0f}ms)")
        
        except Exception as e:
            return HealthCheckResult(False, f"Error: {str(e)[:100]}")
    
    async def check_service(self, service_name: str, base_url: str) -> HealthCheckResult:
        """
        Verifica saúde de um microserviço.
        
        Args:
            service_name: Nome do serviço (para logs)
            base_url: URL base do serviço
        
        Testa:
        - Endpoint /health (se existir)
        - Conectividade básica
        - Latência
        """
        start = datetime.now()
        
        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=3.0)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Tentar endpoint /health primeiro
                try:
                    async with session.get(f"{base_url}/health") as resp:
                        latency_ms = (datetime.now() - start).total_seconds() * 1000
                        
                        if resp.status == 200:
                            return HealthCheckResult(True, "OK", latency_ms)
                        else:
                            return HealthCheckResult(
                                False,
                                f"HTTP {resp.status}",
                                latency_ms
                            )
                
                except aiohttp.ClientConnectorError:
                    # Endpoint /health não existe, tentar conectividade básica
                    async with session.get(base_url) as resp:
                        latency_ms = (datetime.now() - start).total_seconds() * 1000
                        
                        # Qualquer resposta (mesmo 404) indica serviço ativo
                        if resp.status < 500:
                            return HealthCheckResult(
                                True,
                                f"Reachable (HTTP {resp.status})",
                                latency_ms
                            )
                        else:
                            return HealthCheckResult(
                                False,
                                f"HTTP {resp.status}",
                                latency_ms
                            )
        
        except asyncio.TimeoutError:
            latency_ms = (datetime.now() - start).total_seconds() * 1000
            return HealthCheckResult(False, f"Timeout (>{latency_ms:.0f}ms)")
        
        except Exception as e:
            return HealthCheckResult(False, f"Error: {str(e)[:100]}")
    
    async def check_disk_space(self, path: Optional[str] = None) -> HealthCheckResult:
        """
        Verifica espaço em disco.
        
        Args:
            path: Caminho para verificar (usa temp_dir se None)
        
        Alertas:
        - < 1GB: Unhealthy (crítico)
        - < 5GB: Warning (incluído em details)
        - >= 5GB: Healthy
        """
        try:
            check_path = path or (self.settings and self.settings.get('temp_dir')) or '/tmp'
            
            stat = shutil.disk_usage(check_path)
            
            free_gb = stat.free / (1024**3)
            total_gb = stat.total / (1024**3)
            used_gb = stat.used / (1024**3)
            used_percent = (stat.used / stat.total) * 100
            
            details = (
                f"{free_gb:.1f}GB free / {total_gb:.1f}GB total "
                f"({used_percent:.1f}% used)"
            )
            
            # Crítico: menos de 1GB
            if free_gb < 1.0:
                return HealthCheckResult(False, f"⚠️ LOW SPACE: {details}")
            
            # Warning: menos de 5GB
            if free_gb < 5.0:
                return HealthCheckResult(True, f"⚠️ Warning: {details}")
            
            # OK
            return HealthCheckResult(True, details)
        
        except Exception as e:
            return HealthCheckResult(False, f"Error: {str(e)[:100]}")
    
    async def check_celery_workers(self) -> HealthCheckResult:
        """
        Verifica workers Celery ativos.
        
        Nota: Requer acesso ao app Celery
        """
        try:
            # Importar celery app
            from .celery_config import celery_app
            
            # Pegar workers ativos
            inspect = celery_app.control.inspect()
            
            # Timeout de 2s
            active_workers = await asyncio.wait_for(
                asyncio.to_thread(inspect.active),
                timeout=2.0
            )
            
            if active_workers is None:
                return HealthCheckResult(False, "No workers responding")
            
            worker_count = len(active_workers)
            
            if worker_count == 0:
                return HealthCheckResult(False, "No active workers")
            
            # Contar tasks ativas
            total_tasks = sum(len(tasks) for tasks in active_workers.values())
            
            details = f"{worker_count} worker(s), {total_tasks} active task(s)"
            
            return HealthCheckResult(True, details)
        
        except asyncio.TimeoutError:
            return HealthCheckResult(False, "Timeout (>2s)")
        
        except Exception as e:
            return HealthCheckResult(False, f"Error: {str(e)[:100]}")
    
    async def check_all(
        self,
        include_celery: bool = False
    ) -> Dict[str, HealthCheckResult]:
        """
        Executa todos os health checks em paralelo.
        
        Args:
            include_celery: Se deve verificar Celery workers
        
        Returns:
            Dicionário com resultados {component_name: HealthCheckResult}
        """
        checks = {
            "redis": self.check_redis(),
            "disk_space": self.check_disk_space()
        }
        
        # Adicionar checks de microserviços se configurados
        if self.settings:
            if self.settings.get('youtube_search_url'):
                checks["youtube_search"] = self.check_service(
                    "youtube-search",
                    self.settings['youtube_search_url']
                )
            
            if self.settings.get('video_downloader_url'):
                checks["video_downloader"] = self.check_service(
                    "video-downloader",
                    self.settings['video_downloader_url']
                )
            
            if self.settings.get('audio_transcriber_url'):
                checks["audio_transcriber"] = self.check_service(
                    "audio-transcriber",
                    self.settings['audio_transcriber_url']
                )
        
        # Adicionar check de Celery se solicitado
        if include_celery:
            checks["celery_workers"] = self.check_celery_workers()
        
        # Executar em paralelo
        results = await asyncio.gather(
            *checks.values(),
            return_exceptions=True
        )
        
        # Mapear resultados
        health_results = {}
        for (name, _), result in zip(checks.items(), results):
            if isinstance(result, Exception):
                health_results[name] = HealthCheckResult(
                    False,
                    f"Exception: {str(result)[:100]}"
                )
            else:
                health_results[name] = result
        
        return health_results
    
    def is_healthy(self, results: Dict[str, HealthCheckResult]) -> bool:
        """
        Determina se sistema está saudável baseado nos resultados.
        
        Args:
            results: Resultados de check_all()
        
        Returns:
            True se todos os componentes críticos estão saudáveis
        """
        # Componentes críticos (devem estar healthy)
        critical_components = ["redis", "disk_space"]
        
        for component in critical_components:
            if component in results and not results[component].healthy:
                return False
        
        return True


# Singleton global
_health_checker = None


def get_health_checker() -> HealthChecker:
    """Retorna instância singleton do HealthChecker"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
