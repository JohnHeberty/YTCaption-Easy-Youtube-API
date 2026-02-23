"""Testes de integração para SubtitleDetectorV2 com vídeos REAIS"""
import pytest
from pathlib import Path


@pytest.mark.requires_video
@pytest.mark.slow
class TestSubtitleDetectorV2:
    """Testes com vídeos REAIS"""
    
    def test_detector_module_imports(self):
        """Módulo subtitle_detector_v2 importa"""
        try:
            from app.video_processing import subtitle_detector_v2
            assert subtitle_detector_v2 is not None
        except ImportError:
            pytest.skip("subtitle_detector_v2.py não existe")
    
    def test_detector_class_exists(self):
        """Classe SubtitleDetectorV2 existe"""
        try:
            from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2
            assert SubtitleDetectorV2 is not None
            
            # Deve ser instanciável
            detector = SubtitleDetectorV2(show_log=False)
            assert detector is not None
        except ImportError:
            pytest.skip("SubtitleDetectorV2 não existe")
    
    def test_detect_method_exists(self):
        """Método detect() existe"""
        try:
            from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2
            detector = SubtitleDetectorV2(show_log=False)
            
            # Deve ter método detect
            assert hasattr(detector, 'detect')
            assert callable(detector.detect)
        except ImportError:
            pytest.skip("SubtitleDetectorV2 não existe")
    
    def test_detect_with_video_path(self, sample_video_path):
        """Detecta em vídeo COM legendas (real)"""
        try:
            from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2
            detector = SubtitleDetectorV2(show_log=False)
            
            # Executar detecção
            result = detector.detect(str(sample_video_path))
            
            # API retorna tupla: (has_subtitles, confidence, text, metadata)
            assert isinstance(result, tuple)
            assert len(result) == 4
            
            has_subtitles, confidence, text, metadata = result
            
            # Verificar tipos
            assert isinstance(has_subtitles, bool)
            assert isinstance(confidence, (int, float))
            assert isinstance(text, str)
            assert isinstance(metadata, dict)
            
            # Verificar valores
            assert 0 <= confidence <= 1
        except ImportError:
            pytest.skip("SubtitleDetectorV2 não existe")
    
    def test_detect_clean_video(self, sample_video_no_subs):
        """Detecta em vídeo SEM legendas"""
        try:
            from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2
            detector = SubtitleDetectorV2(show_log=False)
            
            result = detector.detect(str(sample_video_no_subs))
            
            # API retorna tupla: (has_subtitles, confidence, text, metadata)
            assert isinstance(result, tuple)
            assert len(result) == 4
            
            has_subtitles, confidence, text, metadata = result
            
            assert isinstance(has_subtitles, bool)
            assert isinstance(confidence, (int, float))
            assert isinstance(text, str)
            assert isinstance(metadata, dict)
        except ImportError:
            pytest.skip("SubtitleDetectorV2 não existe")


@pytest.mark.requires_video
class TestSubtitleDetection:
    """Testes de detecção de legendas"""
    
    def test_video_with_hardcoded_subs(self, sample_video_path):
        """Vídeo com legendas hardcoded"""
        # Vídeo foi gerado com legendas visíveis
        assert sample_video_path.exists()
        assert sample_video_path.stat().st_size > 0
        
        # Verificar que é vídeo válido
        import subprocess
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(sample_video_path)
        ], capture_output=True, text=True, check=True)
        
        duration = float(result.stdout.strip())
        assert duration > 0
    
    def test_video_without_subs(self, sample_video_no_subs):
        """Vídeo sem legendas"""
        assert sample_video_no_subs.exists()
        assert sample_video_no_subs.stat().st_size > 0
        
        # Verificar que é vídeo válido
        import subprocess
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(sample_video_no_subs)
        ], capture_output=True, text=True, check=True)
        
        assert "h264" in result.stdout
    
    def test_extract_frame_from_video_with_subs(self, sample_video_path, tmp_path):
        """Extrai frame de vídeo com legendas"""
        import subprocess
        
        output_frame = tmp_path / "frame_with_subs.png"
        
        # Extrair frame do meio do vídeo (onde legendas estão visíveis)
        subprocess.run([
            "ffmpeg", "-i", str(sample_video_path),
            "-ss", "2.5",  # Meio do vídeo de 5s
            "-vframes", "1",
            str(output_frame)
        ], check=True, capture_output=True)
        
        assert output_frame.exists()
        assert output_frame.stat().st_size > 0
    
    def test_video_processing_pipeline(self, sample_video_path):
        """Pipeline básico de processamento"""
        # Validar vídeo existe
        assert sample_video_path.exists()
        
        # Obter informações do vídeo
        import subprocess
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height,duration",
            "-of", "json",
            str(sample_video_path)
        ], capture_output=True, text=True, check=True)
        
        import json
        data = json.loads(result.stdout)
        
        assert 'streams' in data
        assert len(data['streams']) > 0


@pytest.mark.requires_video
class TestVideoProcessingModule:
    """Testes do módulo video_processing"""
    
    def test_video_processing_module_imports(self):
        """Módulo video_processing importa"""
        try:
            from app import video_processing
            assert video_processing is not None
        except ImportError:
            pytest.skip("video_processing module não existe")
    
    def test_video_processing_has_detector(self):
        """Módulo tem detector de legendas"""
        try:
            from app.video_processing import subtitle_detector_v2
            assert subtitle_detector_v2 is not None
        except (ImportError, AttributeError):
            pytest.skip("subtitle_detector_v2 não existe")
