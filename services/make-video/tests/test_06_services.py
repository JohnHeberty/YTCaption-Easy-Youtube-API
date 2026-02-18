"""
TESTES MÓDULO 6: Services
Testa serviços principais (shorts, video, subtitles, etc)
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestShortsManager:
    """Testes para ShortsCache/ShortsManager"""
    
    def test_shorts_cache_initialization(self):
        """Test 6.1: Inicializar ShortsCache"""
        print("\n🧪 TEST 6.1: Inicializando ShortsCache...")
        
        from app.services.shorts_manager import ShortsCache
        from app.core.config import get_settings
        
        settings = get_settings()
        cache_dir = Path(settings['temp_dir']) / 'shorts_cache_test'
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        cache = ShortsCache(cache_dir=str(cache_dir))
        
        assert cache is not None
        assert cache.cache_dir == str(cache_dir)
        
        print("✅ ShortsCache inicializado")
        print(f"   cache_dir: {cache.cache_dir}")
    
    def test_shorts_cache_key_generation(self):
        """Test 6.2: Gerar cache key para short"""
        print("\n🧪 TEST 6.2: Cache key generation...")
        
        from app.services.shorts_manager import ShortsCache
        
        cache = ShortsCache(cache_dir="/tmp/test_cache")
        
        video_id = "test_video_123"
        cache_key = cache._get_cache_key(video_id)
        
        assert cache_key is not None
        assert video_id in cache_key
        
        print(f"✅ Cache key gerado: {cache_key}")


class TestVideoBuilder:
    """Testes para VideoBuilder"""
    
    def test_video_builder_initialization(self):
        """Test 6.3: Inicializar VideoBuilder"""
        print("\n🧪 TEST 6.3: Inicializando VideoBuilder...")
        
        from app.services.video_builder import VideoBuilder
        from app.core.config import get_settings
        
        settings = get_settings()
        
        builder = VideoBuilder(
            temp_dir=settings['temp_dir'],
            output_dir=settings['output_dir'],
            video_codec='libx264',
            audio_codec='aac',
            preset='medium',
            crf=23
        )
        
        assert builder is not None
        assert builder.temp_dir == settings['temp_dir']
        
        print("✅ VideoBuilder inicializado")
        print(f"   video_codec: {builder.video_codec}")
        print(f"   preset: {builder.preset}")


class TestSubtitleGenerator:
    """Testes para SubtitleGenerator"""
    
    def test_subtitle_generator_initialization(self):
        """Test 6.4: Inicializar SubtitleGenerator"""
        print("\n🧪 TEST 6.4: SubtitleGenerator init...")
        
        from app.services.subtitle_generator import SubtitleGenerator
        
        generator = SubtitleGenerator()
        
        assert generator is not None
        
        print("✅ SubtitleGenerator inicializado")
    
    def test_subtitle_generate_from_transcript(self):
        """Test 6.5: Gerar legendas de transcrição"""
        print("\n🧪 TEST 6.5: Gerar legendas...")
        
        from app.services.subtitle_generator import SubtitleGenerator
        
        generator = SubtitleGenerator()
        
        # Transcrição simples
        transcript = [
            {"text": "Hello", "start": 0.0, "end": 1.0},
            {"text": "World", "start": 1.0, "end": 2.0},
        ]
        
        subtitles = generator.generate_from_transcript(transcript)
        
        assert subtitles is not None
        assert len(subtitles) > 0
        
        print(f"✅ Legendas geradas: {len(subtitles)} segmentos")


class TestBlacklistManager:
    """Testes para Blacklist"""
    
    def test_blacklist_factory(self):
        """Test 6.6: BlacklistFactory"""
        print("\n🧪 TEST 6.6: BlacklistFactory...")
        
        from app.services.blacklist_factory import get_blacklist
        
        blacklist = get_blacklist()
        
        assert blacklist is not None
        
        print("✅ Blacklist criado via factory")
        print(f"   Tipo: {type(blacklist).__name__}")
    
    def test_blacklist_operations(self):
        """Test 6.7: Operações de blacklist"""
        print("\n🧪 TEST 6.7: Blacklist add/check...")
        
        from app.services.blacklist_factory import get_blacklist
        
        blacklist = get_blacklist()
        
        video_id = "test_blacklist_video_001"
        
        # Adicionar
        blacklist.add(video_id, reason="test")
        print(f"   Adicionado: {video_id}")
        
        # Verificar
        is_blacklisted = blacklist.is_blacklisted(video_id)
        
        assert is_blacklisted is True, f"Video deveria estar blacklisted"
        
        print(f"✅ Blacklist funcionando")


class TestFileOperations:
    """Testes para FileOperations"""
    
    def test_file_operations_import(self):
        """Test 6.8: Importar FileOperations"""
        print("\n🧪 TEST 6.8: FileOperations import...")
        
        try:
            from app.services.file_operations import ensure_dir, safe_delete
            
            print("✅ FileOperations importado")
            print(f"   Funções: ensure_dir, safe_delete")
            
        except ImportError as e:
            print(f"⚠️  FileOperations não disponível: {e}")
            pytest.skip("FileOperations não implementado")


class TestCleanupService:
    """Testes para CleanupService"""
    
    @pytest.mark.asyncio
    async def test_cleanup_service(self):
        """Test 6.9: CleanupService"""
        print("\n🧪 TEST 6.9: CleanupService...")
        
        try:
            from app.services.cleanup_service import CleanupService
            from app.core.config import get_settings
            
            settings = get_settings()
            service = CleanupService(
                temp_dir=settings['temp_dir'],
                max_age_hours=24
            )
            
            assert service is not None
            
            print("✅ CleanupService inicializado")
            print(f"   temp_dir: {service.temp_dir}")
            
        except (ImportError, AttributeError) as e:
            print(f"⚠️  CleanupService não disponível: {e}")
            pytest.skip("CleanupService não implementado")


class TestVideoStatusStore:
    """Testes para VideoStatusStore"""
    
    def test_video_status_factory(self):
        """Test 6.10: VideoStatusFactory"""
        print("\n🧪 TEST 6.10: VideoStatusFactory...")
        
        from app.services.video_status_factory import get_video_status_store
        from app.core.config import get_settings
        
        settings = get_settings()
        store = get_video_status_store(redis_url=settings['redis_url'])
        
        assert store is not None
        
        print("✅ VideoStatusStore criado")
        print(f"   Tipo: {type(store).__name__}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
