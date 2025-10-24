"""
Testes unitários para Transcription Cache.
"""
import pytest
from src.infrastructure.cache.transcription_cache import TranscriptionCache
from src.domain.entities.transcription import Transcription


class TestTranscriptionCache:
    """Testes para cache de transcrições."""
    
    @pytest.fixture
    def cache(self):
        """Cria instância do cache."""
        return TranscriptionCache()
    
    def test_set_and_get_transcription(self, cache):
        """Deve armazenar e recuperar transcrição."""
        transcription = Transcription(
            video_id="test123",
            language="en",
            model_name="base"
        )
        
        # Armazenar
        cache.set("test123", transcription)
        
        # Recuperar
        retrieved = cache.get("test123")
        
        assert retrieved is not None
        assert retrieved.video_id == "test123"
        assert retrieved.language == "en"
    
    def test_get_nonexistent_returns_none(self, cache):
        """Deve retornar None para chave inexistente."""
        result = cache.get("non_existent_key")
        
        assert result is None
    
    def test_delete_transcription(self, cache):
        """Deve deletar transcrição do cache."""
        transcription = Transcription(
            video_id="test456",
            language="pt",
            model_name="base"
        )
        
        cache.set("test456", transcription)
        assert cache.get("test456") is not None
        
        # Deletar
        cache.delete("test456")
        
        assert cache.get("test456") is None
    
    def test_exists(self, cache):
        """Deve verificar se chave existe."""
        transcription = Transcription(
            video_id="exists",
            language="en",
            model_name="base"
        )
        
        assert not cache.exists("exists")
        
        cache.set("exists", transcription)
        
        assert cache.exists("exists")
    
    def test_clear_all(self, cache):
        """Deve limpar todo o cache."""
        # Adicionar várias transcrições
        for i in range(5):
            transcription = Transcription(
                video_id=f"test{i}",
                language="en",
                model_name="base"
            )
            cache.set(f"test{i}", transcription)
        
        # Limpar
        cache.clear()
        
        # Verificar que está vazio
        for i in range(5):
            assert cache.get(f"test{i}") is None
    
    def test_cache_expiration(self, cache):
        """Deve expirar entradas antigas (se implementado TTL)."""
        # Se TranscriptionCache implementar TTL
        if hasattr(cache, 'ttl'):
            transcription = Transcription(
                video_id="expire",
                language="en",
                model_name="base"
            )
            
            cache.set("expire", transcription, ttl=1)  # 1 segundo
            
            assert cache.get("expire") is not None
            
            # Aguardar expiração
            import time
            time.sleep(1.5)
            
            assert cache.get("expire") is None
