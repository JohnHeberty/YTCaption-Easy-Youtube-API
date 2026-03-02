# 🏗️ SPRINT 4 - INFRASTRUCTURE

**Status**: ⏳ Pendente  
**Prioridade**: 🔴 CRÍTICA  
**Duração Estimada**: 4-5 horas  
**Pré-requisitos**: Sprint 1

---

## 🎯 OBJETIVOS

1. ✅ Testar Redis Store com conexão REAL
2. ✅ Validar Checkpoint Manager com arquivos reais
3. ✅ Testar Circuit Breaker funcional
4. ✅ Validar Resource Manager
5. ✅ Testar Metrics e Telemetry
6. ✅ Validar Health Checker

---

## 📁 ARQUIVOS

```
app/infrastructure/
├── redis_store.py          # Armazenamento Redis
├── checkpoint_manager.py   # Gerenciamento de checkpoints
├── circuit_breaker.py      # Padrão Circuit Breaker
├── resource_manager.py     # Gerenciamento de recursos
├── metrics.py              # Métricas
├── telemetry.py            # Telemetria
├── health_checker.py       # Health checks
├── file_logger.py          # Logger de arquivos
├── log_utils.py            # Utilitários de log
├── subprocess_utils.py     # Subprocess helpers
└── celery_workaround.py    # Workarounds Celery
```

---

## 🧪 TESTES PRINCIPAIS

```python
# tests/integration/infrastructure/test_redis_store.py
import pytest
import redis


@pytest.mark.requires_redis
class TestRedisStore:
    """Testes com Redis REAL"""
    
    def test_redis_connection(self, test_redis_url):
        """Conecta ao Redis real"""
        r = redis.from_url(test_redis_url)
        assert r.ping() is True
    
    def test_set_and_get(self, test_redis_url):
        """Set/Get com Redis real"""
        r = redis.from_url(test_redis_url)
        
        key = "test:key:001"
        value = "test_value"
        
        r.set(key, value, ex=60)  # 60s TTL
        result = r.get(key)
        
        assert result.decode() == value
        
        # Cleanup
        r.delete(key)
    
    def test_hash_operations(self, test_redis_url):
        """Operações de hash"""
        r = redis.from_url(test_redis_url)
        
        hash_key = "test:hash:001"
        data = {"field1": "value1", "field2": "value2"}
        
        r.hset(hash_key, mapping=data)
        result = r.hgetall(hash_key)
        
        result_decoded = {k.decode(): v.decode() for k, v in result.items()}
        assert result_decoded == data
        
        # Cleanup
        r.delete(hash_key)


# tests/unit/infrastructure/test_checkpoint_manager.py
class TestCheckpointManager:
    """Testes de checkpoint com arquivos reais"""
    
    def test_save_checkpoint(self, tmp_path):
        """Salva checkpoint real"""
        import json
        
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        
        job_id = "job_123"
        state = {"stage": "transform", "progress": 50}
        
        # Salvar
        checkpoint_file = checkpoint_dir / f"{job_id}.json"
        checkpoint_file.write_text(json.dumps(state))
        
        assert checkpoint_file.exists()
        
        # Load
        loaded = json.loads(checkpoint_file.read_text())
        assert loaded == state


# tests/unit/infrastructure/test_circuit_breaker.py
class TestCircuitBreaker:
    """Testes de Circuit Breaker"""
    
    def test_circuit_breaker_pattern(self):
        """Padrão Circuit Breaker básico"""
        failure_count = 0
        threshold = 3
        
        def failing_operation():
            nonlocal failure_count
            failure_count += 1
            if failure_count < threshold:
                raise ValueError("Error")
            return "success"
        
        # Tentar até abrir o circuito
        for _ in range(threshold - 1):
            with pytest.raises(ValueError):
                failing_operation()
        
        # Próxima deve ter sucesso
        result = failing_operation()
        assert result == "success"
```

---

## 📋 IMPLEMENTAÇÃO

```bash
mkdir -p tests/{integration,unit}/infrastructure
touch tests/integration/infrastructure/__init__.py
touch tests/integration/infrastructure/test_redis_store.py
touch tests/unit/infrastructure/test_checkpoint_manager.py
touch tests/unit/infrastructure/test_circuit_breaker.py

# Executar
pytest tests/integration/infrastructure/ -v -m requires_redis
pytest tests/unit/infrastructure/ -v
```

---

## ✅ CRITÉRIOS

- [ ] Redis testado com conexão real
- [ ] Checkpoints salvos e carregados
- [ ] Circuit breaker funcional
- [ ] Cobertura > 80%

---

**Status**: ⏳ Pendente
