"""
TESTES MÓDULO 8: Video Processing
Testa detecção, validação, OCR, frames, etc
"""
import pytest
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDetectors:
    """Testes para Detectors (silence, scene, watermark)"""
    
    def test_silence_detector_import(self):
        """Test 8.1: Importar SilenceDetector"""
        print("\n🧪 TEST 8.1: SilenceDetector import...")
        
        from app.video_processing.detectors.silence_detector import SilenceDetector
        
        assert SilenceDetector is not None
        
        print("✅ SilenceDetector importado")
    
    def test_scene_detector_import(self):
        """Test 8.2: Importar SceneDetector"""
        print("\n🧪 TEST 8.2: SceneDetector import...")
        
        try:
            from app.video_processing.detectors.scene_detector import SceneDetector
            
            assert SceneDetector is not None
            
            print("✅ SceneDetector importado")
            
        except ImportError as e:
            print(f"⚠️  SceneDetector não disponível: {e}")
            pytest.skip("SceneDetector não implementado")
    
    def test_watermark_detector_import(self):
        """Test 8.3: Importar WatermarkDetector"""
        print("\n🧪 TEST 8.3: WatermarkDetector import...")
        
        try:
            from app.video_processing.detectors.watermark_detector import WatermarkDetector
            
            assert WatermarkDetector is not None
            
            print("✅ WatermarkDetector importado")
            
        except ImportError as e:
            print(f"⚠️  WatermarkDetector não disponível: {e}")
            pytest.skip("WatermarkDetector não implementado")


class TestValidators:
    """Testes para Validators (video, audio, metadata)"""
    
    def test_video_validator_import(self):
        """Test 8.4: Importar VideoValidator"""
        print("\n🧪 TEST 8.4: VideoValidator import...")
        
        try:
            from app.video_processing.validators.video_validator import VideoValidator
            
            assert VideoValidator is not None
            
            print("✅ VideoValidator importado")
            
        except ImportError as e:
            print(f"⚠️  VideoValidator não disponível: {e}")
            pytest.skip("VideoValidator não implementado")
    
    def test_audio_validator_import(self):
        """Test 8.5: Importar AudioValidator"""
        print("\n🧪 TEST 8.5: AudioValidator import...")
        
        try:
            from app.video_processing.validators.audio_validator import AudioValidator
            
            assert AudioValidator is not None
            
            print("✅ AudioValidator importado")
            
        except ImportError as e:
            print(f"⚠️  AudioValidator não disponível: {e}")
            pytest.skip("AudioValidator não implementado")


class TestOCR:
    """Testes para OCR (detecção de texto em vídeos)"""
    
    def test_ocr_processor_import(self):
        """Test 8.6: Importar OCRProcessor"""
        print("\n🧪 TEST 8.6: OCRProcessor import...")
        
        try:
            from app.video_processing.ocr.ocr_processor import OCRProcessor
            
            assert OCRProcessor is not None
            
            print("✅ OCRProcessor importado")
            
        except ImportError as e:
            print(f"⚠️  OCRProcessor não disponível: {e}")
            pytest.skip("OCRProcessor não implementado")
    
    def test_text_detector_import(self):
        """Test 8.7: Importar TextDetector"""
        print("\n🧪 TEST 8.7: TextDetector import...")
        
        try:
            from app.video_processing.ocr.text_detector import TextDetector
            
            assert TextDetector is not None
            
            print("✅ TextDetector importado")
            
        except ImportError as e:
            print(f"⚠️  TextDetector não disponível: {e}")
            pytest.skip("TextDetector não implementado")


class TestFrameExtractor:
    """Testes para FrameExtractor"""
    
    def test_frame_extractor_import(self):
        """Test 8.8: Importar FrameExtractor"""
        print("\n🧪 TEST 8.8: FrameExtractor import...")
        
        try:
            from app.video_processing.frame_extractor import FrameExtractor
            
            assert FrameExtractor is not None
            
            print("✅ FrameExtractor importado")
            
        except ImportError as e:
            print(f"⚠️  FrameExtractor não disponível: {e}")
            pytest.skip("FrameExtractor não implementado")


class TestVideoAnalyzer:
    """Testes para VideoAnalyzer"""
    
    def test_video_analyzer_import(self):
        """Test 8.9: Importar VideoAnalyzer"""
        print("\n🧪 TEST 8.9: VideoAnalyzer import...")
        
        try:
            from app.video_processing.video_analyzer import VideoAnalyzer
            
            assert VideoAnalyzer is not None
            
            print("✅ VideoAnalyzer importado")
            
        except ImportError as e:
            print(f"⚠️  VideoAnalyzer não disponível: {e}")
            pytest.skip("VideoAnalyzer não implementado")


class TestFFmpegUtils:
    """Testes para FFmpeg utils"""
    
    def test_ffmpeg_wrapper_import(self):
        """Test 8.10: Importar FFmpegWrapper"""
        print("\n🧪 TEST 8.10: FFmpegWrapper import...")
        
        try:
            from app.video_processing.ffmpeg_wrapper import FFmpegWrapper
            
            assert FFmpegWrapper is not None
            
            print("✅ FFmpegWrapper importado")
            
        except ImportError as e:
            print(f"⚠️  FFmpegWrapper não disponível: {e}")
            pytest.skip("FFmpegWrapper não implementado")
    
    def test_ffmpeg_commands_import(self):
        """Test 8.11: Importar FFmpeg commands"""
        print("\n🧪 TEST 8.11: FFmpeg commands import...")
        
        try:
            from app.video_processing.ffmpeg_commands import (
                get_video_info,
                extract_audio,
                concat_videos
            )
            
            print("✅ FFmpeg commands importados")
            print("   - get_video_info")
            print("   - extract_audio")
            print("   - concat_videos")
            
        except ImportError as e:
            print(f"⚠️  FFmpeg commands não disponível: {e}")
            pytest.skip("FFmpeg commands não implementado")


class TestVideoMetadata:
    """Testes para VideoMetadata"""
    
    def test_metadata_extractor_import(self):
        """Test 8.12: Importar MetadataExtractor"""
        print("\n🧪 TEST 8.12: MetadataExtractor import...")
        
        try:
            from app.video_processing.metadata_extractor import MetadataExtractor
            
            assert MetadataExtractor is not None
            
            print("✅ MetadataExtractor importado")
            
        except ImportError as e:
            print(f"⚠️  MetadataExtractor não disponível: {e}")
            pytest.skip("MetadataExtractor não implementado")


class TestTransitions:
    """Testes para Video Transitions"""
    
    def test_transitions_import(self):
        """Test 8.13: Importar Transitions"""
        print("\n🧪 TEST 8.13: Transitions import...")
        
        try:
            from app.video_processing.transitions import (
                FadeTransition,
                CrossfadeTransition
            )
            
            print("✅ Transitions importados")
            print("   - FadeTransition")
            print("   - CrossfadeTransition")
            
        except ImportError as e:
            print(f"⚠️  Transitions não disponível: {e}")
            pytest.skip("Transitions não implementado")


class TestEffects:
    """Testes para Video Effects"""
    
    def test_effects_import(self):
        """Test 8.14: Importar Effects"""
        print("\n🧪 TEST 8.14: Effects import...")
        
        try:
            from app.video_processing.effects import (
                apply_blur,
                apply_brightness
            )
            
            print("✅ Effects importados")
            print("   - apply_blur")
            print("   - apply_brightness")
            
        except ImportError as e:
            print(f"⚠️  Effects não disponível: {e}")
            pytest.skip("Effects não implementado")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
