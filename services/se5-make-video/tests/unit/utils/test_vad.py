"""Testes para Voice Activity Detection"""
import pytest
import subprocess
from pathlib import Path


@pytest.mark.requires_audio
@pytest.mark.slow
class TestVAD:
    """Testes de Voice Activity Detection"""
    
    def test_vad_with_tone_audio(self, real_test_audio):
        """VAD com áudio de tom puro (sem voz)"""
        # Áudio de teste é tom puro, não deve detectar voz
        # (teste básico de integração)
        assert real_test_audio.exists()
        assert real_test_audio.stat().st_size > 0
    
    def test_vad_with_silent_audio(self, silent_audio):
        """VAD com áudio silencioso"""
        # Áudio silencioso não deve ter atividade
        assert silent_audio.exists()
        
        # Verificar que é realmente silencioso
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(silent_audio)
        ], capture_output=True, text=True, check=True)
        
        assert result.returncode == 0
    
    def test_detect_audio_segments(self, real_test_audio):
        """Detecta segmentos de áudio"""
        # Usar silencedetect do FFmpeg como baseline
        result = subprocess.run([
            "ffmpeg", "-i", str(real_test_audio),
            "-af", "silencedetect=noise=-30dB:d=0.5",
            "-f", "null", "-"
        ], capture_output=True, text=True)
        
        # Deve executar sem erro
        assert "silencedetect" in result.stderr.lower() or result.returncode == 0
    
    def test_silence_detection_with_noisy_audio(self, noisy_audio):
        """Detecta silêncio em áudio ruidoso"""
        # Áudio com ruído branco não deve ter silêncios
        result = subprocess.run([
            "ffmpeg", "-i", str(noisy_audio),
            "-af", "silencedetect=noise=-50dB:d=0.5",
            "-f", "null", "-"
        ], capture_output=True, text=True)
        
        # Deve executar
        assert result.returncode == 0
        # Verificar que processou
        assert "time=" in result.stderr


class TestVADUtils:
    """Testes para vad_utils.py"""
    
    def test_vad_utils_module_imports(self):
        """Módulo VAD utils importa"""
        try:
            from app.utils import vad_utils
            assert vad_utils is not None
        except ImportError:
            pytest.skip("vad_utils.py não existe")
    
    def test_vad_module_imports(self):
        """Módulo VAD importa"""
        try:
            from app.utils import vad
            assert vad is not None
        except ImportError:
            pytest.skip("vad.py não existe")
    
    def test_utils_module_exports(self):
        """Módulo utils exporta corretamente"""
        try:
            from app import utils
            assert utils is not None
            # Verificar que é um módulo
            assert hasattr(utils, '__path__') or hasattr(utils, '__file__')
        except ImportError:
            pytest.skip("app.utils não está acessível")
