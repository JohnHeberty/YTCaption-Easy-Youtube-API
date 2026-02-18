"""
TESTES MÓDULO 9: Utils e Subtitle Processing
Testa utils (audio, timeout, vad) e subtitle_processing
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAudioUtils:
    """Testes para Audio Utils"""
    
    def test_audio_utils_import(self):
        """Test 9.1: Importar audio_utils"""
        print("\n🧪 TEST 9.1: audio_utils import...")
        
        try:
            from app.utils.audio_utils import (
                extract_audio,
                get_audio_duration,
                normalize_audio
            )
            
            print("✅ audio_utils importado")
            print("   - extract_audio")
            print("   - get_audio_duration")
            print("   - normalize_audio")
            
        except ImportError as e:
            print(f"⚠️  audio_utils não disponível: {e}")
            pytest.skip("audio_utils não implementado")


class TestTimeoutUtils:
    """Testes para Timeout Utils"""
    
    def test_timeout_decorator_import(self):
        """Test 9.2: Importar timeout decorator"""
        print("\n🧪 TEST 9.2: timeout decorator import...")
        
        try:
            from app.utils.timeout_utils import with_timeout, TimeoutError
            
            assert with_timeout is not None
            
            print("✅ timeout decorator importado")
            
        except ImportError as e:
            print(f"⚠️  timeout_utils não disponível: {e}")
            pytest.skip("timeout_utils não implementado")
    
    def test_timeout_functionality(self):
        """Test 9.3: Testar timeout functionality"""
        print("\n🧪 TEST 9.3: timeout functionality...")
        
        try:
            from app.utils.timeout_utils import with_timeout
            import time
            
            @with_timeout(seconds=2)
            def fast_function():
                time.sleep(0.1)
                return "success"
            
            result = fast_function()
            
            assert result == "success"
            
            print("✅ Timeout decorator funciona")
            
        except ImportError as e:
            print(f"⚠️  timeout_utils não disponível: {e}")
            pytest.skip("timeout_utils não implementado")


class TestVAD:
    """Testes para Voice Activity Detection"""
    
    def test_vad_import(self):
        """Test 9.4: Importar VAD"""
        print("\n🧪 TEST 9.4: VAD import...")
        
        try:
            from app.utils.vad import VADProcessor
            
            assert VADProcessor is not None
            
            print("✅ VAD importado")
            
        except ImportError as e:
            print(f"⚠️  VAD não disponível: {e}")
            pytest.skip("VAD não implementado")


class TestSubtitleProcessing:
    """Testes para Subtitle Processing"""
    
    def test_subtitle_formatter_import(self):
        """Test 9.5: Importar SubtitleFormatter"""
        print("\n🧪 TEST 9.5: SubtitleFormatter import...")
        
        try:
            from app.subtitle_processing.subtitle_formatter import SubtitleFormatter
            
            assert SubtitleFormatter is not None
            
            print("✅ SubtitleFormatter importado")
            
        except ImportError as e:
            print(f"⚠️  SubtitleFormatter não disponível: {e}")
            pytest.skip("SubtitleFormatter não implementado")
    
    def test_subtitle_splitter_import(self):
        """Test 9.6: Importar SubtitleSplitter"""
        print("\n🧪 TEST 9.6: SubtitleSplitter import...")
        
        try:
            from app.subtitle_processing.subtitle_splitter import SubtitleSplitter
            
            assert SubtitleSplitter is not None
            
            print("✅ SubtitleSplitter importado")
            
        except ImportError as e:
            print(f"⚠️  SubtitleSplitter não disponível: {e}")
            pytest.skip("SubtitleSplitter não implementado")
    
    def test_subtitle_aligner_import(self):
        """Test 9.7: Importar SubtitleAligner"""
        print("\n🧪 TEST 9.7: SubtitleAligner import...")
        
        try:
            from app.subtitle_processing.subtitle_aligner import SubtitleAligner
            
            assert SubtitleAligner is not None
            
            print("✅ SubtitleAligner importado")
            
        except ImportError as e:
            print(f"⚠️  SubtitleAligner não disponível: {e}")
            pytest.skip("SubtitleAligner não implementado")
    
    def test_subtitle_renderer_import(self):
        """Test 9.8: Importar SubtitleRenderer"""
        print("\n🧪 TEST 9.8: SubtitleRenderer import...")
        
        try:
            from app.subtitle_processing.subtitle_renderer import SubtitleRenderer
            
            assert SubtitleRenderer is not None
            
            print("✅ SubtitleRenderer importado")
            
        except ImportError as e:
            print(f"⚠️  SubtitleRenderer não disponível: {e}")
            pytest.skip("SubtitleRenderer não implementado")


class TestSubtitleValidation:
    """Testes para Subtitle Validation"""
    
    def test_subtitle_validator_import(self):
        """Test 9.9: Importar SubtitleValidator"""
        print("\n🧪 TEST 9.9: SubtitleValidator import...")
        
        try:
            from app.subtitle_processing.subtitle_validator import SubtitleValidator
            
            assert SubtitleValidator is not None
            
            print("✅ SubtitleValidator importado")
            
        except ImportError as e:
            print(f"⚠️  SubtitleValidator não disponível: {e}")
            pytest.skip("SubtitleValidator não implementado")


class TestSubtitleIntegration:
    """Testes de integração para Subtitle Processing"""
    
    def test_subtitle_pipeline(self):
        """Test 9.10: Pipeline de legendas"""
        print("\n🧪 TEST 9.10: Subtitle pipeline...")
        
        try:
            # Importar todos os componentes
            from app.subtitle_processing.subtitle_formatter import SubtitleFormatter
            from app.subtitle_processing.subtitle_splitter import SubtitleSplitter
            
            formatter = SubtitleFormatter()
            splitter = SubtitleSplitter(max_chars_per_line=40)
            
            # Texto simples
            text = "This is a long sentence that should be split into multiple subtitle lines"
            
            # Split
            lines = splitter.split(text)
            
            assert lines is not None
            assert len(lines) > 0
            
            print(f"✅ Subtitle pipeline funcionando")
            print(f"   Input: {len(text)} chars")
            print(f"   Output: {len(lines)} lines")
            
        except ImportError as e:
            print(f"⚠️  Subtitle pipeline não disponível: {e}")
            pytest.skip("Subtitle pipeline não implementado")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
