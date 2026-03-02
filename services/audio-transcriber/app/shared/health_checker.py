"""
Sistema de Health Check para componentes do serviço.
Implementa verificação profunda de saúde e disponibilidade.
"""
import logging
from typing import Dict, Any
from datetime import datetime
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

import asyncio

from ..domain.interfaces import IHealthChecker, IJobStore
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class CeleryHealthChecker(IHealthChecker):
    """
    Verifica saúde do Celery worker.
    """
    
    def __init__(self, celery_app):
        """
        Args:
            celery_app: Instância do Celery app
        """
        self.celery_app = celery_app
        self.last_check_time = None
        self.last_check_result = None
    
    def check_health(self) -> Dict[str, Any]:
        """
        Verifica saúde do Celery.
        
        Returns:
            Dict com status de saúde
        """
        result = {
            "component": "celery_worker",
            "healthy": False,
            "timestamp": datetime.now().isoformat(),
            "details": {}
        }
        
        try:
            # Inspeciona workers ativos
            inspect = self.celery_app.control.inspect()
            
            # Verifica workers registrados
            stats = inspect.stats()
            active = inspect.active()
            registered = inspect.registered()
            
            if not stats:
                result["details"]["error"] = "Nenhum worker respondendo"
                result["details"]["workers_count"] = 0
                return result
            
            # Analisa resposta
            workers_count = len(stats.keys())
            active_tasks = sum(len(tasks) for tasks in (active or {}).values())
            registered_tasks = list((registered or {}).values())[0] if registered else []
            
            result["healthy"] = workers_count > 0
            result["details"] = {
                "workers_count": workers_count,
                "active_tasks": active_tasks,
                "registered_tasks_count": len(registered_tasks),
                "workers": list(stats.keys())
            }
            
            self.last_check_time = now_brazil()
            self.last_check_result = result
            
            if result["healthy"]:
                logger.debug(f"✅ Celery healthy: {workers_count} workers, {active_tasks} tasks ativas")
            else:
                logger.warning(f"⚠️ Celery unhealthy: {result['details']}")
            
        except Exception as e:
            result["details"]["error"] = str(e)
            logger.error(f"❌ Erro ao verificar saúde do Celery: {e}")
        
        return result
    
    def is_healthy(self) -> bool:
        """Retorna se Celery está saudável"""
        health = self.check_health()
        return health.get("healthy", False)


class RedisHealthChecker(IHealthChecker):
    """
    Verifica saúde da conexão Redis.
    """
    
    def __init__(self, job_store: IJobStore):
        """
        Args:
            job_store: Store de jobs (usa Redis)
        """
        self.job_store = job_store
    
    def check_health(self) -> Dict[str, Any]:
        """
        Verifica saúde do Redis.
        
        Returns:
            Dict com status de saúde
        """
        result = {
            "component": "redis",
            "healthy": False,
            "timestamp": datetime.now().isoformat(),
            "details": {}
        }
        
        try:
            # Tenta fazer PING no Redis
            redis_client = self.job_store.redis
            
            # PING
            pong = redis_client.ping()
            
            # INFO (estatísticas)
            info = redis_client.info()
            
            result["healthy"] = pong
            result["details"] = {
                "ping": "pong" if pong else "failed",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
            
            logger.debug(f"✅ Redis healthy: {result['details']['connected_clients']} clients")
            
        except Exception as e:
            result["details"]["error"] = str(e)
            logger.error(f"❌ Erro ao verificar saúde do Redis: {e}")
        
        return result
    
    def is_healthy(self) -> bool:
        """Retorna se Redis está saudável"""
        health = self.check_health()
        return health.get("healthy", False)


class ModelHealthChecker(IHealthChecker):
    """
    Verifica saúde do modelo Whisper.
    """
    
    def __init__(self, model_manager):
        """
        Args:
            model_manager: Gerenciador de modelos
        """
        self.model_manager = model_manager
    
    def check_health(self) -> Dict[str, Any]:
        """
        Verifica saúde do modelo.
        
        Returns:
            Dict com status de saúde
        """
        result = {
            "component": "whisper_model",
            "healthy": False,
            "timestamp": datetime.now().isoformat(),
            "details": {}
        }
        
        try:
            status = self.model_manager.get_status()
            
            # Considera saudável se:
            # - Modelo está carregado OU
            # - Modelo não está carregado mas PODE ser carregado (lazy loading)
            result["healthy"] = True  # Lazy loading é válido
            result["details"] = {
                "loaded": status.get("loaded", False),
                "model_name": status.get("model_name", "unknown"),
                "device": status.get("device", "not_loaded"),
                "ready_for_transcription": status.get("loaded", False)
            }
            
            if status.get("loaded"):
                if "vram_mb" in status:
                    result["details"]["vram_mb"] = status["vram_mb"]
            
            logger.debug(f"✅ Modelo healthy: {result['details']}")
            
        except Exception as e:
            result["details"]["error"] = str(e)
            result["healthy"] = False
            logger.error(f"❌ Erro ao verificar saúde do modelo: {e}")
        
        return result
    
    def is_healthy(self) -> bool:
        """Retorna se modelo está saudável"""
        health = self.check_health()
        return health.get("healthy", False)


class AggregateHealthChecker:
    """
    Agrega health checks de múltiplos componentes.
    """
    
    def __init__(self):
        self.checkers: Dict[str, IHealthChecker] = {}
    
    def register_checker(self, name: str, checker: IHealthChecker):
        """Registra um health checker"""
        self.checkers[name] = checker
        logger.info(f"✅ Health checker registrado: {name}")
    
    def check_all(self) -> Dict[str, Any]:
        """
        Verifica saúde de todos os componentes.
        
        Returns:
            Dict com status agregado
        """
        results = {
            "overall_healthy": True,
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        for name, checker in self.checkers.items():
            try:
                component_health = checker.check_health()
                results["components"][name] = component_health
                
                # Se qualquer componente crítico estiver unhealthy, overall é unhealthy
                if not component_health.get("healthy", False):
                    # Componentes críticos: celery, redis
                    if name in ["celery", "redis"]:
                        results["overall_healthy"] = False
                    
            except Exception as e:
                logger.error(f"❌ Erro ao verificar {name}: {e}")
                results["components"][name] = {
                    "healthy": False,
                    "error": str(e)
                }
                if name in ["celery", "redis"]:
                    results["overall_healthy"] = False
        
        return results
    
    def is_healthy(self) -> bool:
        """Retorna se sistema geral está saudável"""
        result = self.check_all()
        return result.get("overall_healthy", False)


# Alias para compatibilidade com imports antigos
HealthChecker = AggregateHealthChecker
