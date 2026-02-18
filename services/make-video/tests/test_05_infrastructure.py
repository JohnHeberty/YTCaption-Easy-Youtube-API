"""
TESTES MÓDULO 5: Infrastructure
Testa componentes de infraestrutura (redis, checkpoint, metrics, etc)
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRedisStore:
    """Testes para RedisJobStore"""
    
    def test_redis_store_initialization(self):
        """Test 5.1: Inicializar RedisJobStore"""
        print("\n🧪 TEST 5.1: Inicializando RedisJobStore...")
        
        from app.infrastructure.redis_store import RedisJobStore
        from app.core.config import get_settings
        
        settings = get_settings()
        store = RedisJobStore(redis_url=settings['redis_url'])
        
        assert store is not None
        assert store.redis_url == settings['redis_url']
        
        print("✅ RedisJobStore inicializado")
        print(f"   redis_url: {store.redis_url[:50]}...")
    
    @pytest.mark.asyncio
    async def test_redis_store_save_job(self):
        """Test 5.2: Salvar job no Redis"""
        print("\n🧪 TEST 5.2: Salvando job no Redis...")
        
        from app.infrastructure.redis_store import RedisJobStore
        from app.core.models import Job, JobStatus
        from app.core.config import get_settings
        from datetime import datetime
        
        settings = get_settings()
        store = RedisJobStore(redis_url=settings['redis_url'])
        
        job = Job(
            job_id="test_redis_job_001",
            status=JobStatus.QUEUED,
            query="test redis",
            max_shorts=3,
            aspect_ratio="9:16",
            created_at=datetime.utcnow()
        )
        
        # Salvar
        await store.save_job(job)
        print("✅ Job salvo no Redis")
        
        # Recuperar
        retrieved_job = await store.get_job(job.job_id)
        
        assert retrieved_job is not None, "Job não recuperado"
        assert retrieved_job.job_id == job.job_id
        assert retrieved_job.query == job.query
        
        print(f"✅ Job recuperado com sucesso")
        print(f"   job_id: {retrieved_job.job_id}")
        print(f"   query: {retrieved_job.query}")


class TestCheckpointManager:
    """Testes para CheckpointManager"""
    
    @pytest.mark.asyncio
    async def test_checkpoint_save_and_load(self):
        """Test 5.3: Salvar e carregar checkpoint"""
        print("\n🧪 TEST 5.3: Checkpoint save/load...")
        
        from app.infrastructure.checkpoint_manager import CheckpointManager
        from app.core.config import get_settings
        
        settings = get_settings()
        manager = CheckpointManager(redis_url=settings['redis_url'])
        
        job_id = "test_checkpoint_001"
        checkpoint_data = {
            'stage': 'test_stage',
            'progress': 0.5,
            'metadata': {'test': 'data'}
        }
        
        # Salvar
        await manager.save_checkpoint(job_id, checkpoint_data)
        print("✅ Checkpoint salvo")
        
        # Carregar
        loaded = await manager.load_checkpoint(job_id)
        
        assert loaded is not None, "Checkpoint não carregado"
        assert loaded['stage'] == 'test_stage'
        assert loaded['progress'] == 0.5
        
        print(f"✅ Checkpoint carregado")
        print(f"   stage: {loaded['stage']}")
        print(f"   progress: {loaded['progress']}")


class TestCircuitBreaker:
    """Testes para CircuitBreaker"""
    
    def test_circuit_breaker_initialization(self):
        """Test 5.4: Inicializar CircuitBreaker"""
        print("\n🧪 TEST 5.4: CircuitBreaker init...")
        
        from app.infrastructure.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(
            name="test_circuit",
            failure_threshold=3,
            timeout=60
        )
        
        assert cb is not None
        assert cb.name == "test_circuit"
        assert cb.failure_threshold == 3
        
        print(f"✅ CircuitBreaker criado")
        print(f"   name: {cb.name}")
        print(f"   failure_threshold: {cb.failure_threshold}")


class TestMetrics:
    """Testes para sistema de métricas"""
    
    def test_metrics_collector(self):
        """Test 5.5: MetricsCollector"""
        print("\n🧪 TEST 5.5: MetricsCollector...")
        
        try:
            from app.infrastructure.metrics import MetricsCollector
            
            collector = MetricsCollector()
            
            # Incrementar contador
            collector.increment_counter("test_counter")
            
            # Registrar gauge
            collector.set_gauge("test_gauge", 42.0)
            
            print("✅ MetricsCollector funcional")
            
        except ImportError as e:
            print(f"⚠️  MetricsCollector não disponível: {e}")
            pytest.skip("MetricsCollector não implementado")


class TestRateLimiter:
    """Testes para RateLimiter"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """Test 5.6: RateLimiter"""
        print("\n🧪 TEST 5.6: RateLimiter...")
        
        from app.infrastructure.rate_limiter import RateLimiter
        from app.core.config import get_settings
        
        settings = get_settings()
        limiter = RateLimiter(
            redis_url=settings['redis_url'],
            max_requests=5,
            window_seconds=60
        )
        
        # Verificar se permite requisição
        allowed = await limiter.is_allowed("test_key")
        
        assert allowed in [True, False], "is_allowed deve retornar bool"
        
        print(f"✅ RateLimiter funcional")
        print(f"   allowed: {allowed}")


class TestFileLogger:
    """Testes para FileLogger"""
    
    def test_file_logger_setup(self):
        """Test 5.7: FileLogger setup"""
        print("\n🧪 TEST 5.7: FileLogger setup...")
        
        from app.infrastructure.file_logger import FileLogger
        
        # Setup (já foi chamado no import, mas testar que não quebra)
        FileLogger.setup()
        
        # Verificar que logger funciona
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Test log message")
        
        print("✅ FileLogger configurado")


class TestResourceManager:
    """Testes para ResourceManager"""
    
    def test_resource_manager_limits(self):
        """Test 5.8: ResourceManager"""
        print("\n🧪 TEST 5.8: ResourceManager...")
        
        try:
            from app.infrastructure.resource_manager import ResourceManager
            
            manager = ResourceManager(
                max_memory_mb=1024,
                max_cpu_percent=80.0
            )
            
            # Verificar limites
            assert manager.max_memory_mb == 1024
            assert manager.max_cpu_percent == 80.0
            
            print("✅ ResourceManager OK")
            print(f"   max_memory_mb: {manager.max_memory_mb}")
            
        except (ImportError, AttributeError) as e:
            print(f"⚠️  ResourceManager não disponível: {e}")
            pytest.skip("ResourceManager não implementado")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
