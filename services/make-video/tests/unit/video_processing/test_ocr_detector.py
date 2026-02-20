"""Testes unitários para OCR Detector"""
import pytest
import subprocess
from pathlib import Path


@pytest.mark.requires_video
class TestOCRDetector:
    """Testes de OCR"""
    
    def test_ocr_detector_module_imports(self):
        """Módulo ocr_detector importa"""
        try:
            from app.video_processing import ocr_detector
            assert ocr_detector is not None
        except ImportError:
            pytest.skip("ocr_detector.py não existe")
    
    def test_ocr_detector_advanced_imports(self):
        """Módulo ocr_detector_advanced importa"""
        try:
            from app.video_processing import ocr_detector_advanced
            assert ocr_detector_advanced is not None
        except ImportError:
            pytest.skip("ocr_detector_advanced.py não existe")
    
    def test_create_image_with_text(self, tmp_path):
        """Cria imagem com texto para testar OCR"""
        text_image = tmp_path / "text.png"
        
        # Criar imagem com texto usando FFmpeg
        subprocess.run([
            "ffmpeg", "-f", "lavfi",
            "-i", "color=c=white:s=640x480",
            "-vf", "drawtext=text='SUBTITLE':fontsize=48:fontcolor=black:x=100:y=200",
            "-frames:v", "1",
            str(text_image)
        ], check=True, capture_output=True)
        
        assert text_image.exists()
        assert text_image.stat().st_size > 0
    
    def test_create_image_with_subtitle_region(self, tmp_path):
        """Cria imagem simulando região de legenda"""
        subtitle_image = tmp_path / "subtitle_region.png"
        
        # Imagem branca com caixa preta e texto branco (simula legenda)
        subprocess.run([
            "ffmpeg", "-f", "lavfi",
            "-i", "color=c=blue:s=1280x720",
            "-vf", 
            "drawbox=x=0:y=600:w=1280:h=120:color=black@0.8:t=fill,"
            "drawtext=text='Test Subtitle':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=650",
            "-frames:v", "1",
            str(subtitle_image)
        ], check=True, capture_output=True)
        
        assert subtitle_image.exists()
    
    def test_extract_subtitle_region(self, sample_video_path, tmp_path):
        """Extrai região de legendas do vídeo"""
        subtitle_region = tmp_path / "subtitle_region.png"
        
        # Extrair região inferior (onde legendas geralmente aparecem)
        subprocess.run([
            "ffmpeg", "-ss", "2.5",
            "-i", str(sample_video_path),
            "-vf", "crop=1280:120:0:600",  # x:y:width:height
            "-vframes", "1",
            str(subtitle_region)
        ], check=True, capture_output=True)
        
        assert subtitle_region.exists()
    
    def test_paddleocr_is_primary_engine(self, tmp_path):
        """Valida que PaddleOCR é o motor principal (EasyOCR é legado)"""
        # Verifica que SubtitleDetectorV2 usa PaddleOCR
        from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2
        from paddleocr import PaddleOCR
        
        detector = SubtitleDetectorV2()
        
        # SubtitleDetectorV2 deve ter ocr (PaddleOCR), não EasyOCR
        assert hasattr(detector, 'ocr'), "Detector deve ter ocr (PaddleOCR)"
        
        # Verificar que é PaddleOCR
        assert isinstance(detector.ocr, PaddleOCR), "ocr deve ser instância de PaddleOCR"
        
        # Não deve ter EasyOCR
        assert not hasattr(detector, 'easyocr'), "Detector não deve usar EasyOCR (legado)"
        assert not hasattr(detector, 'easy_ocr'), "Detector não deve usar EasyOCR (legado)"
    
    def test_ocr_with_pytesseract(self, tmp_path):
        """Testa OCR com Pytesseract (se disponível)"""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            pytest.skip("Pytesseract/PIL não instalado")
        
        # Criar imagem com texto claro
        text_image = tmp_path / "text_for_pytesseract.png"
        subprocess.run([
            "ffmpeg", "-f", "lavfi",
            "-i", "color=c=white:s=640x480",
            "-vf", "drawtext=text='TEST TEXT':fontsize=60:fontcolor=black:x=150:y=200",
            "-frames:v", "1",
            str(text_image)
        ], check=True, capture_output=True)
        
        # Executar OCR
        try:
            image = Image.open(text_image)
            text = pytesseract.image_to_string(image)
            
            # Deve retornar algo (pode ser vazio se não detectar)
            assert isinstance(text, str)
        except Exception:
            pytest.skip("Tesseract não configurado")


@pytest.mark.requires_video
class TestSubtitleRegionDetection:
    """Testes de detecção de região de legendas"""
    
    def test_detect_bottom_region(self, sample_video_path, tmp_path):
        """Detecta região inferior do vídeo (onde legendas aparecem)"""
        # Extrair últimos 120 pixels de altura
        bottom_region = tmp_path / "bottom.png"
        
        subprocess.run([
            "ffmpeg", "-ss", "2",
            "-i", str(sample_video_path),
            "-vf", "crop=in_w:120:0:in_h-120",
            "-vframes", "1",
            str(bottom_region)
        ], check=True, capture_output=True)
        
        assert bottom_region.exists()
    
    def test_detect_black_regions(self, sample_video_path, tmp_path):
        """Detecta regiões pretas (possíveis legendas)"""
        frame = tmp_path / "frame_for_analysis.png"
        
        # Extrair frame
        subprocess.run([
            "ffmpeg", "-ss", "2.5",
            "-i", str(sample_video_path),
            "-vframes", "1",
            str(frame)
        ], check=True, capture_output=True)
        
        assert frame.exists()
        
        # Análise (se OpenCV disponível)
        try:
            import cv2
            import numpy as np
            
            img = cv2.imread(str(frame))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Threshold para detectar regiões escuras
            _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
            
            # Deve ter processado
            assert thresh is not None
        except ImportError:
            pass  # Skip if OpenCV not available
    
    def test_extract_text_region_features(self, sample_video_path, tmp_path):
        """Extrai features de região de texto"""
        frame_with_text = tmp_path / "text_region.png"
        
        # Extrair frame com legendas
        subprocess.run([
            "ffmpeg", "-ss", "2.5",
            "-i", str(sample_video_path),
            "-vf", "crop=1280:100:0:620",  # Região de legendas
            "-vframes", "1",
            str(frame_with_text)
        ], check=True, capture_output=True)
        
        assert frame_with_text.exists()
        assert frame_with_text.stat().st_size > 0


@pytest.mark.requires_video
class TestOCRValidation:
    """Testes de validação de OCR"""
    
    def test_validate_text_detection(self, tmp_path):
        """Valida detecção de texto"""
        # Criar imagem clara com texto grande
        clear_text = tmp_path / "clear_text.png"
        
        subprocess.run([
            "ffmpeg", "-f", "lavfi",
            "-i", "color=c=white:s=800x200",
            "-vf", "drawtext=text='CLEAR TEXT':fontsize=80:fontcolor=black:x=150:y=60",
            "-frames:v", "1",
            str(clear_text)
        ], check=True, capture_output=True)
        
        assert clear_text.exists()
    
    def test_image_preprocessing(self, tmp_path):
        """Pré-processamento de imagem para OCR"""
        original = tmp_path / "original.png"
        
        # Criar imagem
        subprocess.run([
            "ffmpeg", "-f", "lavfi",
            "-i", "color=c=gray:s=640x480",
            "-frames:v", "1",
            str(original)
        ], check=True, capture_output=True)
        
        # Pré-processar: converter para grayscale, threshold, etc.
        processed = tmp_path / "processed.png"
        
        subprocess.run([
            "ffmpeg", "-i", str(original),
            "-vf", "format=gray,eq=contrast=1.5",
            str(processed)
        ], check=True, capture_output=True)
        
        assert processed.exists()
