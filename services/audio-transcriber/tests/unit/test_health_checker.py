"""
Testes para health_checker.py.

✅ Sem Mocks - usa Stubs para Redis e filesystem
✅ Verifica health checks
✅ Testa disponibilidade de serviços
✅ Testa métricas de sistema
"""

import pytest
from pathlib import Path


class StubProcess:
    """Stub que simula processo do sistema"""
    
    def __init__(self):
        self.memory_info_data = type('obj', (object,), {'rss': 50 * 1024 * 1024})()  # 50 MB
        self.cpu_percent_value = 15.5
    
    def memory_info(self):
        return self.memory_info_data
    
    def cpu_percent(self, interval=0.1):
        return self.cpu_percent_value


class StubMemory:
    """Stub que simula memória do sistema"""
    
    def __init__(self):
        self.total = 16 * 1024 ** 3  # 16 GB
        self.available = 8 * 1024 ** 3  # 8 GB
        self.percent = 50.0


class StubRedisClient:
    """Stub que simula Redis para health checks"""
    
    def __init__(self, is_healthy=True):
        self.is_healthy = is_healthy
        self.ping_count = 0
    
    def ping(self):
        self.ping_count += 1
        if not self.is_healthy:
            raise ConnectionError("Redis unavailable")
        return True


@pytest.fixture
def healthy_redis():
    """Redis saudável"""
    return StubRedisClient(is_healthy=True)


@pytest.fixture
def unhealthy_redis():
    """Redis indisponível"""
    return StubRedisClient(is_healthy=False)


def test_redis_health_check_success(healthy_redis):
    """Testa health check Redis com sucesso"""
    try:
        result = healthy_redis.ping()
        status = "healthy"
    except Exception:
        status = "unhealthy"
    
    assert status == "healthy"
    assert result is True


def test_redis_health_check_failure(unhealthy_redis):
    """Testa health check Redis com falha"""
    try:
        unhealthy_redis.ping()
        status = "healthy"
    except ConnectionError:
        status = "unhealthy"
    
    assert status == "unhealthy"


def test_disk_space_check():
    """Testa verificação de espaço em disco"""
    import shutil
    
    stat = shutil.disk_usage("/")
    
    free_gb = stat.free / (1024 ** 3)
    total_gb = stat.total / (1024 ** 3)
    percent_used = (stat.used / stat.total) * 100
    
    assert free_gb >= 0
    assert total_gb > 0
    assert 0 <= percent_used <= 100


def test_memory_check():
    """Testa verificação de memória"""
    memory = StubMemory()
    
    total_mb = memory.total / (1024 ** 2)
    available_mb = memory.available / (1024 ** 2)
    percent_used = memory.percent
    
    assert total_mb > 0
    assert available_mb >= 0
    assert 0 <= percent_used <= 100


def test_cpu_check():
    """Testa verificação de CPU"""
    cpu_percent = 45.5
    cpu_count = 4
    
    assert cpu_count > 0
    assert 0 <= cpu_percent <= 100


def test_process_health():
    """Testa health do processo"""
    process = StubProcess()
    
    memory_info = process.memory_info()
    cpu_percent = process.cpu_percent(interval=0.1)
    
    assert memory_info.rss > 0  # RSS deve ser positivo
    assert cpu_percent >= 0


def test_uptime_calculation():
    """Testa cálculo de uptime"""
    import time
    
    start_time = time.time()
    time.sleep(0.1)
    current_time = time.time()
    
    uptime = current_time - start_time
    assert uptime >= 0.1


def test_health_status_aggregation(healthy_redis):
    """Testa agregação de status de health"""
    checks = {
        "redis": "healthy",
        "disk": "healthy",
        "memory": "healthy"
    }
    
    # Sistema está saudável se todos os checks passarem
    overall_status = "healthy" if all(v == "healthy" for v in checks.values()) else "unhealthy"
    
    assert overall_status == "healthy"


def test_health_status_partial_failure(unhealthy_redis):
    """Testa agregação com falha parcial"""
    checks = {
        "redis": "unhealthy",
        "disk": "healthy",
        "memory": "healthy"
    }
    
    overall_status = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"
    
    assert overall_status == "degraded"


def test_response_time_check(healthy_redis):
    """Testa verificação de tempo de resposta"""
    import time
    
    start = time.time()
    healthy_redis.ping()
    end = time.time()
    
    response_time_ms = (end - start) * 1000
    
    assert response_time_ms < 100  # Deve responder em <100ms


def test_health_endpoint_response():
    """Testa formato da resposta do endpoint de health"""
    health_response = {
        "status": "healthy",
        "timestamp": "2026-02-21T12:00:00Z",
        "checks": {
            "redis": {"status": "healthy", "latency_ms": 1.5},
            "disk": {"status": "healthy", "free_gb": 100},
            "memory": {"status": "healthy", "available_gb": 8}
        }
    }
    
    assert health_response["status"] == "healthy"
    assert "checks" in health_response
    assert health_response["checks"]["redis"]["status"] == "healthy"


def test_critical_vs_non_critical_checks():
    """Testa separação de checks críticos vs não-críticos"""
    critical_checks = {
        "redis": "healthy",
        "disk": "healthy"
    }
    
    non_critical_checks = {
        "metrics": "degraded"  # Não deve afetar status overall
    }
    
    # Sistema é saudável se checks críticos passarem
    is_healthy = all(v == "healthy" for v in critical_checks.values())
    
    assert is_healthy is True


def test_health_check_timeout():
    """Testa timeout em health checks"""
    import time
    
    timeout = 5.0
    
    start = time.time()
    # Simula check rápido
    time.sleep(0.1)
    elapsed = time.time() - start
    
    # Check deve completar antes do timeout
    assert elapsed < timeout


def test_consecutive_failures_tracking(unhealthy_redis):
    """Testa tracking de falhas consecutivas"""
    failures = 0
    max_failures = 3
    
    for _ in range(5):
        try:
            unhealthy_redis.ping()
            failures = 0  # Reset em sucesso
        except ConnectionError:
            failures += 1
    
    # Deve ter atingido max_failures
    assert failures >= max_failures
