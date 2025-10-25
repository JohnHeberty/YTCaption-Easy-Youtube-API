"""
Módulo de resiliência para os serviços
Implementa circuit breakers, retry policies e recovery mechanisms
"""
import asyncio
import logging
import time
from functools import wraps
from typing import Callable, Any, Optional, Dict, List
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3
    timeout: int = 30


class CircuitBreaker:
    """Circuit breaker pattern implementation"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        
    def can_execute(self) -> bool:
        """Check if operation can be executed"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                return True
            return False
            
        # HALF_OPEN state
        return True
    
    def record_success(self):
        """Record successful operation"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
        else:
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN


def circuit_breaker(config: CircuitBreakerConfig):
    """Decorator for circuit breaker pattern"""
    breaker = CircuitBreaker(config)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not breaker.can_execute():
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not breaker.can_execute():
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
            
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def retry_with_backoff(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """Retry decorator with exponential backoff"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}"
                    )
                    
                    await asyncio.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}"
                    )
                    
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
            
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


class HealthMonitor:
    """Health monitoring for services"""
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.status_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 30  # seconds
    
    def register_check(self, name: str, check_func: Callable):
        """Register a health check"""
        self.checks[name] = check_func
    
    async def run_check(self, name: str) -> Dict[str, Any]:
        """Run a specific health check"""
        if name not in self.checks:
            return {"status": "unknown", "message": f"Check '{name}' not found"}
        
        # Check cache
        if name in self.status_cache:
            cached = self.status_cache[name]
            if time.time() - cached["timestamp"] < self.cache_ttl:
                return cached
        
        try:
            if asyncio.iscoroutinefunction(self.checks[name]):
                result = await self.checks[name]()
            else:
                result = self.checks[name]()
            
            status = {
                "status": "healthy",
                "timestamp": time.time(),
                "result": result
            }
        except Exception as e:
            status = {
                "status": "unhealthy",
                "timestamp": time.time(),
                "error": str(e)
            }
        
        self.status_cache[name] = status
        return status
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {}
        overall_healthy = True
        
        for name in self.checks:
            result = await self.run_check(name)
            results[name] = result
            if result["status"] != "healthy":
                overall_healthy = False
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": time.time(),
            "checks": results
        }


class ResourceManager:
    """Resource management and limits"""
    
    def __init__(self, max_memory_mb: int = 1024, max_cpu_percent: float = 80.0):
        self.max_memory_mb = max_memory_mb
        self.max_cpu_percent = max_cpu_percent
        self.active_jobs = set()
        self.resource_semaphore = asyncio.Semaphore(10)  # Max concurrent operations
    
    async def acquire_resources(self, job_id: str) -> bool:
        """Acquire resources for a job"""
        await self.resource_semaphore.acquire()
        
        try:
            # Check system resources
            import psutil
            
            memory_usage = psutil.virtual_memory().percent
            cpu_usage = psutil.cpu_percent(interval=1)
            
            if memory_usage > 90 or cpu_usage > self.max_cpu_percent:
                logger.warning(
                    f"Resource limits exceeded: Memory {memory_usage}%, CPU {cpu_usage}%"
                )
                return False
            
            self.active_jobs.add(job_id)
            return True
            
        except Exception as e:
            logger.error(f"Error checking resources: {e}")
            return False
    
    def release_resources(self, job_id: str):
        """Release resources for a job"""
        self.active_jobs.discard(job_id)
        self.resource_semaphore.release()
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """Get current resource statistics"""
        try:
            import psutil
            
            return {
                "memory_percent": psutil.virtual_memory().percent,
                "cpu_percent": psutil.cpu_percent(),
                "active_jobs": len(self.active_jobs),
                "available_slots": self.resource_semaphore._value
            }
        except Exception as e:
            return {"error": str(e)}


# Global instances
default_circuit_breaker_config = CircuitBreakerConfig()
health_monitor = HealthMonitor()
resource_manager = ResourceManager()


def resilient_redis_operation(func: Callable) -> Callable:
    """Decorator for resilient Redis operations"""
    return circuit_breaker(default_circuit_breaker_config)(
        retry_with_backoff(
            max_retries=3,
            exceptions=(ConnectionError, TimeoutError)
        )(func)
    )


def resilient_celery_operation(func: Callable) -> Callable:
    """Decorator for resilient Celery operations"""
    return circuit_breaker(default_circuit_breaker_config)(
        retry_with_backoff(
            max_retries=2,
            exceptions=(ConnectionError, TimeoutError)
        )(func)
    )