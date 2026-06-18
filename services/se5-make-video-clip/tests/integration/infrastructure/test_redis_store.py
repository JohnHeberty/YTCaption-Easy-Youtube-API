"""Testes de integração para Redis Store com conexão REAL"""
import pytest
import redis
import json
import time


@pytest.mark.requires_redis
class TestRedisStore:
    """Testes com Redis REAL (DB 15)"""
    
    def test_redis_connection(self, test_redis_url):
        """Conecta ao Redis real"""
        r = redis.from_url(test_redis_url, decode_responses=True)
        assert r.ping() is True
        r.close()
    
    def test_set_and_get(self, test_redis_url):
        """Set/Get com Redis real"""
        r = redis.from_url(test_redis_url, decode_responses=True)
        
        key = "test:key:001"
        value = "test_value"
        
        r.set(key, value, ex=60)  # 60s TTL
        result = r.get(key)
        
        assert result == value
        
        # Cleanup
        r.delete(key)
        r.close()
    
    def test_hash_operations(self, test_redis_url):
        """Operações de hash"""
        r = redis.from_url(test_redis_url, decode_responses=True)
        
        hash_key = "test:hash:001"
        data = {"field1": "value1", "field2": "value2"}
        
        r.hset(hash_key, mapping=data)
        result = r.hgetall(hash_key)
        
        assert result == data
        
        # Cleanup
        r.delete(hash_key)
        r.close()
    
    def test_list_operations(self, test_redis_url):
        """Operações de lista"""
        r = redis.from_url(test_redis_url, decode_responses=True)
        
        list_key = "test:list:001"
        
        # Push elementos
        r.rpush(list_key, "item1", "item2", "item3")
        
        # Verificar tamanho
        length = r.llen(list_key)
        assert length == 3
        
        # Recuperar elementos
        items = r.lrange(list_key, 0, -1)
        assert items == ["item1", "item2", "item3"]
        
        # Cleanup
        r.delete(list_key)
        r.close()
    
    def test_expiration(self, test_redis_url):
        """Testa expiração de chaves"""
        r = redis.from_url(test_redis_url, decode_responses=True)
        
        key = "test:expire:001"
        r.set(key, "value", ex=2)  # 2 segundos
        
        # Deve existir inicialmente
        assert r.exists(key) == 1
        
        # Verificar TTL
        ttl = r.ttl(key)
        assert 0 < ttl <= 2
        
        # Aguardar expiração
        time.sleep(3)
        
        # Não deve mais existir
        assert r.exists(key) == 0
        r.close()
    
    def test_json_storage(self, test_redis_url):
        """Armazenar JSON no Redis"""
        r = redis.from_url(test_redis_url, decode_responses=True)
        
        key = "test:json:001"
        data = {"video_id": "abc123", "status": "processing", "progress": 50}
        
        # Serializar e armazenar
        r.set(key, json.dumps(data))
        
        # Recuperar e deserializar
        stored = r.get(key)
        result = json.loads(stored)
        
        assert result == data
        
        # Cleanup
        r.delete(key)
        r.close()
    
    def test_increment_counter(self, test_redis_url):
        """Testa contador atômico"""
        r = redis.from_url(test_redis_url, decode_responses=True)
        
        key = "test:counter:001"
        
        # Incrementar
        r.incr(key)
        r.incr(key)
        r.incr(key)
        
        count = int(r.get(key))
        assert count == 3
        
        # Cleanup
        r.delete(key)
        r.close()
    
    def test_redis_keys_pattern(self, test_redis_url):
        """Busca chaves por padrão"""
        r = redis.from_url(test_redis_url, decode_responses=True)
        
        # Criar várias chaves
        r.set("test:pattern:001", "value1")
        r.set("test:pattern:002", "value2")
        r.set("test:other:003", "value3")
        
        # Buscar padrão
        keys = r.keys("test:pattern:*")
        assert len(keys) == 2
        
        # Cleanup
        r.delete("test:pattern:001", "test:pattern:002", "test:other:003")
        r.close()
    
    def test_set_operations(self, test_redis_url):
        """Operações de conjunto (set)"""
        r = redis.from_url(test_redis_url, decode_responses=True)
        
        set_key = "test:set:001"
        
        # Adicionar membros
        r.sadd(set_key, "member1", "member2", "member3")
        
        # Verificar tamanho
        size = r.scard(set_key)
        assert size == 3
        
        # Verificar membro (retorna 1 para True, 0 para False)
        assert r.sismember(set_key, "member1") == 1
        assert r.sismember(set_key, "member99") == 0
        
        # Recuperar membros
        members = r.smembers(set_key)
        assert members == {"member1", "member2", "member3"}
        
        # Cleanup
        r.delete(set_key)
        r.close()


@pytest.mark.requires_redis
class TestRedisStoreModule:
    """Testa módulo redis_store.py"""
    
    def test_redis_store_module_imports(self):
        """Módulo redis_store importa"""
        try:
            from app.infrastructure import redis_store
            assert redis_store is not None
        except ImportError:
            pytest.skip("redis_store.py não existe")
    
    def test_redis_client_fixture(self, redis_client):
        """Fixture redis_client funciona"""
        assert redis_client is not None
        assert redis_client.ping() is True
        
        # Testar operação simples
        redis_client.set("test:fixture", "value")
        assert redis_client.get("test:fixture") == "value"
