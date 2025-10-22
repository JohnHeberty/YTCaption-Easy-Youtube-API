"""
Testes unitários para TranscriptionCache.

Testa:
- Criação de cache
- get() e put() com file_hash
- Expiração de cache (TTL)
- LRU eviction
- Cleanup de entries expiradas
- Estatísticas do cache
"""
import time
import tempfile
from pathlib import Path
import pytest

from src.infrastructure.cache.transcription_cache import (
    TranscriptionCache,
    CachedTranscription,
    get_transcription_cache
)


class TestCachedTranscription:
    """Testa dataclass CachedTranscription."""
    
    def test_cached_transcription_creation(self):
        """Testa criação de CachedTranscription."""
        entry = CachedTranscription(
            file_hash="abc123",
            transcription_data={"text": "test"},
            model_name="base",
            language="en",
            cached_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
            file_size_bytes=1024
        )
        
        assert entry.file_hash == "abc123"
        assert entry.model_name == "base"
        assert entry.language == "en"
        assert entry.access_count == 1
    
    def test_is_expired(self):
        """Testa verificação de expiração."""
        # Entry recente - não expirado
        entry = CachedTranscription(
            file_hash="abc123",
            transcription_data={"text": "test"},
            model_name="base",
            language="en",
            cached_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
            file_size_bytes=1024
        )
        
        assert not entry.is_expired(ttl_seconds=3600)
        
        # Entry antigo - expirado
        old_entry = CachedTranscription(
            file_hash="old123",
            transcription_data={"text": "old"},
            model_name="base",
            language="en",
            cached_at=time.time() - 7200,  # 2 horas atrás
            last_accessed=time.time() - 7200,
            access_count=1,
            file_size_bytes=1024
        )
        
        assert old_entry.is_expired(ttl_seconds=3600)  # TTL de 1 hora
    
    def test_mark_accessed(self):
        """Testa marcação de acesso."""
        entry = CachedTranscription(
            file_hash="abc123",
            transcription_data={"text": "test"},
            model_name="base",
            language="en",
            cached_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
            file_size_bytes=1024
        )
        
        initial_count = entry.access_count
        initial_time = entry.last_accessed
        
        time.sleep(0.01)  # Pequeno delay
        entry.mark_accessed()
        
        assert entry.access_count == initial_count + 1
        assert entry.last_accessed > initial_time
    
    def test_age_minutes(self):
        """Testa cálculo de idade em minutos."""
        entry = CachedTranscription(
            file_hash="abc123",
            transcription_data={"text": "test"},
            model_name="base",
            language="en",
            cached_at=time.time() - 120,  # 2 minutos atrás
            last_accessed=time.time(),
            access_count=1,
            file_size_bytes=1024
        )
        
        age = entry.age_minutes()
        assert 1.9 < age < 2.1  # ~2 minutos


class TestTranscriptionCache:
    """Testa classe TranscriptionCache."""
    
    def test_cache_initialization(self):
        """Testa inicialização do cache."""
        cache = TranscriptionCache(max_size=50, ttl_hours=12)
        
        assert cache.max_size == 50
        assert cache.ttl_seconds == 12 * 3600
        assert len(cache._cache) == 0
    
    def test_compute_file_hash(self, tmp_path):
        """Testa cálculo de hash de arquivo."""
        cache = TranscriptionCache()
        
        # Criar arquivo temporário
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")
        
        # Calcular hash
        file_hash = cache.compute_file_hash(test_file)
        
        assert isinstance(file_hash, str)
        assert len(file_hash) == 32  # MD5 hash tem 32 caracteres
        
        # Hash deve ser consistente
        file_hash2 = cache.compute_file_hash(test_file)
        assert file_hash == file_hash2
    
    def test_put_and_get(self, tmp_path):
        """Testa put() e get() básicos."""
        cache = TranscriptionCache(max_size=10, ttl_hours=1)
        
        # Criar arquivo de teste
        test_file = tmp_path / "audio.mp3"
        test_file.write_bytes(b"fake audio data")
        
        file_hash = cache.compute_file_hash(test_file)
        
        # Dados de transcrição
        transcription_data = {
            "transcription_id": "123",
            "text": "Test transcription",
            "segments": []
        }
        
        # Put no cache
        cache.put(
            file_hash=file_hash,
            transcription_data=transcription_data,
            model_name="base",
            language="en",
            file_size_bytes=1024
        )
        
        # Get do cache
        result = cache.get(
            file_hash=file_hash,
            model_name="base",
            language="en"
        )
        
        assert result is not None
        assert result["text"] == "Test transcription"
        assert result["transcription_id"] == "123"
    
    def test_cache_miss(self):
        """Testa cache miss."""
        cache = TranscriptionCache()
        
        result = cache.get(
            file_hash="nonexistent",
            model_name="base",
            language="en"
        )
        
        assert result is None
    
    def test_cache_key_with_different_models(self, tmp_path):
        """Testa que modelos diferentes geram cache keys diferentes."""
        cache = TranscriptionCache()
        
        test_file = tmp_path / "audio.mp3"
        test_file.write_bytes(b"fake audio")
        
        file_hash = cache.compute_file_hash(test_file)
        
        # Adicionar com modelo "base"
        cache.put(
            file_hash=file_hash,
            transcription_data={"text": "base model"},
            model_name="base",
            language="en",
            file_size_bytes=1024
        )
        
        # Adicionar com modelo "small"
        cache.put(
            file_hash=file_hash,
            transcription_data={"text": "small model"},
            model_name="small",
            language="en",
            file_size_bytes=1024
        )
        
        # Get com "base"
        result_base = cache.get(file_hash, "base", "en")
        assert result_base["text"] == "base model"
        
        # Get com "small"
        result_small = cache.get(file_hash, "small", "en")
        assert result_small["text"] == "small model"
    
    def test_cache_key_with_different_languages(self, tmp_path):
        """Testa que idiomas diferentes geram cache keys diferentes."""
        cache = TranscriptionCache()
        
        test_file = tmp_path / "audio.mp3"
        test_file.write_bytes(b"fake audio")
        
        file_hash = cache.compute_file_hash(test_file)
        
        # Adicionar com idioma "en"
        cache.put(
            file_hash=file_hash,
            transcription_data={"text": "English"},
            model_name="base",
            language="en",
            file_size_bytes=1024
        )
        
        # Adicionar com idioma "pt"
        cache.put(
            file_hash=file_hash,
            transcription_data={"text": "Portuguese"},
            model_name="base",
            language="pt",
            file_size_bytes=1024
        )
        
        # Get com "en"
        result_en = cache.get(file_hash, "base", "en")
        assert result_en["text"] == "English"
        
        # Get com "pt"
        result_pt = cache.get(file_hash, "base", "pt")
        assert result_pt["text"] == "Portuguese"
    
    def test_cache_expiration(self, tmp_path):
        """Testa expiração de cache por TTL."""
        cache = TranscriptionCache(ttl_hours=0.001)  # TTL muito curto (3.6 segundos)
        
        test_file = tmp_path / "audio.mp3"
        test_file.write_bytes(b"fake audio")
        
        file_hash = cache.compute_file_hash(test_file)
        
        # Adicionar ao cache
        cache.put(
            file_hash=file_hash,
            transcription_data={"text": "test"},
            model_name="base",
            language="en",
            file_size_bytes=1024
        )
        
        # Verificar que está no cache
        result = cache.get(file_hash, "base", "en")
        assert result is not None
        
        # Aguardar expiração
        time.sleep(4)
        
        # Verificar que expirou
        result_after = cache.get(file_hash, "base", "en")
        assert result_after is None
    
    def test_lru_eviction(self, tmp_path):
        """Testa eviction LRU quando cache atinge max_size."""
        cache = TranscriptionCache(max_size=3, ttl_hours=24)
        
        # Adicionar 4 entries (max_size=3)
        for i in range(4):
            test_file = tmp_path / f"audio{i}.mp3"
            test_file.write_bytes(f"audio {i}".encode())
            
            file_hash = cache.compute_file_hash(test_file)
            
            cache.put(
                file_hash=file_hash,
                transcription_data={"text": f"transcription {i}"},
                model_name="base",
                language="en",
                file_size_bytes=1024
            )
        
        # Cache deve ter apenas 3 entries
        assert len(cache._cache) == 3
        
        # Primeira entry deve ter sido removida (LRU)
        first_file = tmp_path / "audio0.mp3"
        first_hash = cache.compute_file_hash(first_file)
        
        result = cache.get(first_hash, "base", "en")
        assert result is None  # Foi removida
    
    def test_invalidate(self, tmp_path):
        """Testa invalidação de cache por file_hash."""
        cache = TranscriptionCache()
        
        test_file = tmp_path / "audio.mp3"
        test_file.write_bytes(b"fake audio")
        
        file_hash = cache.compute_file_hash(test_file)
        
        # Adicionar múltiplas entries com mesmo file_hash
        cache.put(file_hash, {"text": "en"}, "base", "en", 1024)
        cache.put(file_hash, {"text": "pt"}, "base", "pt", 1024)
        cache.put(file_hash, {"text": "small"}, "small", "en", 1024)
        
        assert len(cache._cache) == 3
        
        # Invalidar todas as entries do file_hash
        cache.invalidate(file_hash)
        
        # Verificar que foram removidas
        assert cache.get(file_hash, "base", "en") is None
        assert cache.get(file_hash, "base", "pt") is None
        assert cache.get(file_hash, "small", "en") is None
    
    def test_clear(self, tmp_path):
        """Testa limpeza total do cache."""
        cache = TranscriptionCache()
        
        # Adicionar várias entries
        for i in range(5):
            test_file = tmp_path / f"audio{i}.mp3"
            test_file.write_bytes(f"audio {i}".encode())
            
            file_hash = cache.compute_file_hash(test_file)
            cache.put(file_hash, {"text": f"test {i}"}, "base", "en", 1024)
        
        assert len(cache._cache) == 5
        
        # Limpar cache
        cache.clear()
        
        assert len(cache._cache) == 0
    
    def test_cleanup_expired(self, tmp_path):
        """Testa cleanup de entries expiradas."""
        cache = TranscriptionCache(ttl_hours=0.001)  # TTL muito curto
        
        # Adicionar entries
        for i in range(3):
            test_file = tmp_path / f"audio{i}.mp3"
            test_file.write_bytes(f"audio {i}".encode())
            
            file_hash = cache.compute_file_hash(test_file)
            cache.put(file_hash, {"text": f"test {i}"}, "base", "en", 1024)
        
        assert len(cache._cache) == 3
        
        # Aguardar expiração
        time.sleep(4)
        
        # Cleanup
        removed = cache.cleanup_expired()
        
        assert removed == 3
        assert len(cache._cache) == 0
    
    def test_get_stats(self, tmp_path):
        """Testa estatísticas do cache."""
        cache = TranscriptionCache(max_size=10, ttl_hours=24)
        
        # Cache vazio
        stats = cache.get_stats()
        assert stats["cache_size"] == 0
        assert stats["max_size"] == 10
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        
        # Adicionar entry
        test_file = tmp_path / "audio.mp3"
        test_file.write_bytes(b"fake audio")
        file_hash = cache.compute_file_hash(test_file)
        
        cache.put(file_hash, {"text": "test"}, "base", "en", 1024)
        
        # Cache miss
        cache.get("nonexistent", "base", "en")
        
        # Cache hit
        cache.get(file_hash, "base", "en")
        
        stats = cache.get_stats()
        assert stats["cache_size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == 50.0
    
    def test_get_cached_entries(self, tmp_path):
        """Testa listagem de entries cacheadas."""
        cache = TranscriptionCache()
        
        # Adicionar entries
        for i in range(3):
            test_file = tmp_path / f"audio{i}.mp3"
            test_file.write_bytes(f"audio {i}".encode())
            
            file_hash = cache.compute_file_hash(test_file)
            cache.put(file_hash, {"text": f"test {i}"}, "base", "en", 1024)
        
        entries = cache.get_cached_entries()
        
        assert len(entries) == 3
        assert all("file_hash" in entry for entry in entries)
        assert all("model_name" in entry for entry in entries)
        assert all("language" in entry for entry in entries)


class TestTranscriptionCacheSingleton:
    """Testa singleton get_transcription_cache()."""
    
    def test_singleton_returns_same_instance(self):
        """Testa que get_transcription_cache() retorna mesma instância."""
        cache1 = get_transcription_cache()
        cache2 = get_transcription_cache()
        
        assert cache1 is cache2
    
    def test_singleton_is_instance_of_cache(self):
        """Testa que singleton retorna instância de TranscriptionCache."""
        cache = get_transcription_cache()
        
        assert isinstance(cache, TranscriptionCache)
        assert hasattr(cache, "get")
        assert hasattr(cache, "put")
        assert hasattr(cache, "compute_file_hash")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
