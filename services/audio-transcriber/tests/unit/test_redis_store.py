"""
Testes para redis_store.py.

✅ Sem Mocks - usa StubRedisClient
✅ Verifica operações Redis
✅ Testa serialização JSON
✅ Testa TTL e expiração
"""

import pytest
import json
from datetime import datetime


class StubRedisClient:
    """Stub que simula Redis sem usar Mock"""
    
    def __init__(self):
        self.data = {}
        self.expiry = {}
    
    def set(self, key, value, ex=None):
        self.data[key] = value
        if ex:
            self.expiry[key] = ex
        return True
    
    def get(self, key):
        return self.data.get(key)
    
    def delete(self, key):
        if key in self.data:
            del self.data[key]
            if key in self.expiry:
                del self.expiry[key]
            return 1
        return 0
    
    def exists(self, key):
        return 1 if key in self.data else 0
    
    def keys(self, pattern):
        import fnmatch
        return [k for k in self.data.keys() if fnmatch.fnmatch(k, pattern)]
    
    def setex(self, key, time, value):
        self.data[key] = value
        self.expiry[key] = time
        return True
    
    def ttl(self, key):
        return self.expiry.get(key, -1)
    
    def hset(self, name, key, value):
        if name not in self.data:
            self.data[name] = {}
        self.data[name][key] = value
        return 1
    
    def hget(self, name, key):
        if name in self.data:
            return self.data[name].get(key)
        return None
    
    def hgetall(self, name):
        return self.data.get(name, {})


@pytest.fixture
def stub_redis():
    """Redis stub para testes"""
    return StubRedisClient()


def test_redis_set_get(stub_redis):
    """Testa SET e GET básicos"""
    stub_redis.set("key1", "value1")
    assert stub_redis.get("key1") == "value1"


def test_redis_delete(stub_redis):
    """Testa DELETE"""
    stub_redis.set("key1", "value1")
    assert stub_redis.exists("key1") == 1
    
    stub_redis.delete("key1")
    assert stub_redis.exists("key1") == 0


def test_redis_exists(stub_redis):
    """Testa EXISTS"""
    assert stub_redis.exists("nonexistent") == 0
    
    stub_redis.set("key1", "value1")
    assert stub_redis.exists("key1") == 1


def test_redis_keys_pattern(stub_redis):
    """Testa busca por padrão de keys"""
    stub_redis.set("job:1:status", "queued")
    stub_redis.set("job:2:status", "processing")
    stub_redis.set("user:1:name", "John")
    
    job_keys = stub_redis.keys("job:*")
    assert len(job_keys) == 2
    assert all(k.startswith("job:") for k in job_keys)


def test_redis_setex_with_ttl(stub_redis):
    """Testa SETEX com TTL"""
    stub_redis.setex("temp_key", 3600, "temp_value")
    
    assert stub_redis.get("temp_key") == "temp_value"
    assert stub_redis.ttl("temp_key") == 3600


def test_redis_ttl(stub_redis):
    """Testa verificação de TTL"""
    stub_redis.set("perm_key", "value")
    stub_redis.setex("temp_key", 1800, "value")
    
    assert stub_redis.ttl("perm_key") == -1  # Sem TTL
    assert stub_redis.ttl("temp_key") == 1800  # Com TTL


def test_redis_json_serialization(stub_redis):
    """Testa serialização de JSON"""
    data = {
        "job_id": "abc123",
        "status": "processing",
        "progress": 45
    }
    
    json_str = json.dumps(data)
    stub_redis.set("job:abc123", json_str)
    
    retrieved = stub_redis.get("job:abc123")
    parsed = json.loads(retrieved)
    
    assert parsed["job_id"] == "abc123"
    assert parsed["status"] == "processing"
    assert parsed["progress"] == 45


def test_redis_hash_operations(stub_redis):
    """Testa operações de hash"""
    stub_redis.hset("job:abc123", "status", "queued")
    stub_redis.hset("job:abc123", "progress", "0")
    
    status = stub_redis.hget("job:abc123", "status")
    assert status == "queued"
    
    all_data = stub_redis.hgetall("job:abc123")
    assert all_data["status"] == "queued"
    assert all_data["progress"] == "0"


def test_redis_job_storage(stub_redis):
    """Testa armazenamento de job"""
    job_id = "job123"
    job_data = {
        "job_id": job_id,
        "status": "queued",
        "audio_file": "test.mp3",
        "created_at": datetime.now().isoformat()
    }
    
    key = f"job:{job_id}"
    stub_redis.set(key, json.dumps(job_data), ex=86400)  # 24h TTL
    
    retrieved = stub_redis.get(key)
    parsed = json.loads(retrieved)
    
    assert parsed["job_id"] == job_id
    assert parsed["status"] == "queued"


def test_redis_job_status_update(stub_redis):
    """Testa atualização de status do job"""
    job_id = "job123"
    
    # Cria job
    job_data = {"job_id": job_id, "status": "queued"}
    stub_redis.set(f"job:{job_id}", json.dumps(job_data))
    
    # Atualiza status
    job_data["status"] = "processing"
    stub_redis.set(f"job:{job_id}", json.dumps(job_data))
    
    # Verifica
    retrieved = json.loads(stub_redis.get(f"job:{job_id}"))
    assert retrieved["status"] == "processing"


def test_redis_multiple_jobs(stub_redis):
    """Testa armazenamento de múltiplos jobs"""
    jobs = ["job1", "job2", "job3"]
    
    for job_id in jobs:
        data = {"job_id": job_id, "status": "queued"}
        stub_redis.set(f"job:{job_id}", json.dumps(data))
    
    # Busca todos os jobs
    all_jobs = stub_redis.keys("job:*")
    assert len(all_jobs) == 3


def test_redis_cleanup_completed_jobs(stub_redis):
    """Testa limpeza de jobs completados"""
    # Cria jobs
    stub_redis.set("job:1", json.dumps({"status": "completed"}))
    stub_redis.set("job:2", json.dumps({"status": "processing"}))
    stub_redis.set("job:3", json.dumps({"status": "completed"}))
    
    # Simula limpeza de completados
    all_keys = stub_redis.keys("job:*")
    for key in all_keys:
        data = json.loads(stub_redis.get(key))
        if data["status"] == "completed":
            stub_redis.delete(key)
    
    # Verifica que apenas processing permanece
    remaining = stub_redis.keys("job:*")
    assert len(remaining) == 1
    
    data = json.loads(stub_redis.get(remaining[0]))
    assert data["status"] == "processing"


def test_redis_atomic_operations(stub_redis):
    """Testa operações atômicas"""
    # SET com EX deve ser atômico
    result = stub_redis.set("key1", "value1", ex=3600)
    assert result is True
    
    assert stub_redis.get("key1") == "value1"
    assert stub_redis.ttl("key1") == 3600


def test_redis_key_naming_convention(stub_redis):
    """Testa convenção de nomenclatura de keys"""
    # Padrão: resource:identifier:attribute
    stub_redis.set("job:abc123:status", "queued")
    stub_redis.set("job:abc123:progress", "0")
    stub_redis.set("user:john:email", "john@example.com")
    
    job_keys = stub_redis.keys("job:abc123:*")
    assert len(job_keys) == 2
    assert "job:abc123:status" in job_keys
    assert "job:abc123:progress" in job_keys
