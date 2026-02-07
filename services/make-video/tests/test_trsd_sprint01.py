"""
Testes unitários para Sprint 01: Arquitetura base e ROI
"""

import pytest
import numpy as np
import cv2
from app.subtitle_detector import TextRegionExtractor
from app.models.text_region import ROIType, TextLine
from app.config import Settings


@pytest.fixture
def extractor():
    """Fixture para TextRegionExtractor"""
    config = Settings()
    return TextRegionExtractor(config)


@pytest.fixture
def sample_frame():
    """Cria frame sintético com texto"""
    # Frame 640x360 (downscale padrão)
    frame = np.ones((360, 640, 3), dtype=np.uint8) * 255  # Branco
    
    # Adicionar texto no terço inferior (subtitle region)
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = "This is a subtitle"
    cv2.putText(frame, text, (50, 320), font, 1, (0, 0, 0), 2)
    
    return frame


class TestTextRegionExtractor:
    """Testes para TextRegionExtractor"""
    
    def test_initialization(self, extractor):
        """Testa inicialização do extractor"""
        assert extractor.target_width == 640
        assert extractor.min_text_length == 2
        assert extractor.min_confidence == 0.50
        assert extractor.min_alpha_ratio == 0.60
    
    def test_downscale_frame(self, extractor):
        """Testa downscaling de frames"""
        # Frame grande (1920x1080)
        large_frame = np.ones((1080, 1920, 3), dtype=np.uint8)
        
        scaled, scale_factor = extractor._downscale_frame(large_frame)
        
        # Verifica largura
        assert scaled.shape[1] == 640
        
        # Verifica scale factor
        expected_scale = 640 / 1920
        assert abs(scale_factor - expected_scale) < 0.01
    
    def test_downscale_skip_small_frame(self, extractor):
        """Testa que frames pequenos não são redimensionados"""
        small_frame = np.ones((360, 480, 3), dtype=np.uint8)
        
        scaled, scale_factor = extractor._downscale_frame(small_frame)
        
        # Deve retornar frame original
        assert scale_factor == 1.0
        assert scaled.shape == small_frame.shape
    
    def test_extract_rois(self, extractor):
        """Testa extração de ROIs"""
        frame = np.ones((360, 640, 3), dtype=np.uint8)
        
        rois = extractor._extract_rois(frame)
        
        # Verifica que 3 ROIs foram extraídas
        assert len(rois) == 3
        assert ROIType.BOTTOM in rois
        assert ROIType.TOP in rois
        assert ROIType.MIDDLE in rois
        
        # Verifica dimensões aproximadas (terços)
        h_bottom = rois[ROIType.BOTTOM].shape[0]
        h_total = frame.shape[0]
        
        assert h_bottom < h_total / 2  # Menor que metade
    
    def test_extract_single_roi(self, extractor):
        """Testa extração de ROI específica"""
        frame = np.ones((360, 640, 3), dtype=np.uint8)
        
        roi_bottom = extractor._extract_single_roi(frame, ROIType.BOTTOM)
        
        # Verifica que é apenas uma parte do frame
        assert roi_bottom.shape[0] < frame.shape[0]
        assert roi_bottom.shape[1] == frame.shape[1]
    
    def test_preprocess_roi(self, extractor):
        """Testa preprocessamento de ROI"""
        roi = np.ones((100, 200, 3), dtype=np.uint8) * 128  # Gray
        
        preprocessed = extractor._preprocess_roi(roi)
        
        # Verifica que é grayscale (2D)
        assert len(preprocessed.shape) == 2
        
        # Verifica que aplicou threshold (valores 0 ou 255)
        unique_values = np.unique(preprocessed)
        assert len(unique_values) <= 2  # Aproximadamente binário
    
    def test_filter_words_by_confidence(self, extractor):
        """Testa filtro de palavras por confiança"""
        words = [
            {'text': 'High', 'conf': 0.90, 'bbox': (0, 0, 50, 20)},
            {'text': 'Low', 'conf': 0.30, 'bbox': (60, 0, 40, 20)},  # Será filtrada
            {'text': 'Medium', 'conf': 0.55, 'bbox': (110, 0, 60, 20)},
        ]
        
        filtered = extractor._filter_words(words)
        
        # Verifica que palavra com baixa confiança foi removida
        assert len(filtered) == 2
        assert filtered[0]['text'] == 'High'
        assert filtered[1]['text'] == 'Medium'
    
    def test_filter_words_by_alpha_ratio(self, extractor):
        """Testa filtro de palavras por razão alfabética"""
        words = [
            {'text': 'Hello', 'conf': 0.80, 'bbox': (0, 0, 50, 20)},
            {'text': '12345', 'conf': 0.80, 'bbox': (60, 0, 50, 20)},  # Será filtrada (sem letras)
            {'text': 'A1B2C', 'conf': 0.80, 'bbox': (120, 0, 50, 20)},  # 60% letras (ok)
        ]
        
        filtered = extractor._filter_words(words)
        
        # Verifica que apenas texto com letras suficientes passou
        texts = [w['text'] for w in filtered]
        assert 'Hello' in texts
        assert '12345' not in texts
    
    def test_group_words_into_lines_single_line(self, extractor):
        """Testa agrupamento de palavras na mesma linha"""
        words = [
            {'text': 'This', 'conf': 0.80, 'bbox': (10, 100, 40, 20)},
            {'text': 'is', 'conf': 0.80, 'bbox': (60, 100, 20, 20)},
            {'text': 'one', 'conf': 0.80, 'bbox': (90, 100, 30, 20)},
            {'text': 'line', 'conf': 0.80, 'bbox': (130, 100, 40, 20)},
        ]
        
        lines = extractor._group_words_into_lines(words, scale_factor=1.0)
        
        # Verifica que todas as palavras foram agrupadas em uma linha
        assert len(lines) == 1
        
        line_bbox, line_words = lines[0]
        assert len(line_words) == 4
    
    def test_group_words_into_lines_multiple_lines(self, extractor):
        """Testa agrupamento de palavras em múltiplas linhas"""
        words = [
            {'text': 'First', 'conf': 0.80, 'bbox': (10, 100, 40, 20)},
            {'text': 'line', 'conf': 0.80, 'bbox': (60, 100, 40, 20)},
            {'text': 'Second', 'conf': 0.80, 'bbox': (10, 150, 50, 20)},  # Y diferente
            {'text': 'line', 'conf': 0.80, 'bbox': (70, 150, 40, 20)},
        ]
        
        lines = extractor._group_words_into_lines(words, scale_factor=1.0)
        
        # Verifica que foram criadas 2 linhas
        assert len(lines) == 2
    
    def test_create_text_line(self, extractor):
        """Testa criação de TextLine"""
        words = [
            {'text': 'Hello', 'conf': 0.85},
            {'text': 'World', 'conf': 0.75},
        ]
        
        text_line = extractor._create_text_line(
            timestamp=5.0,
            roi_type=ROIType.BOTTOM,
            bbox=(10, 100, 100, 20),
            words=words
        )
        
        assert text_line is not None
        assert text_line.text == 'Hello World'
        assert text_line.frame_ts == 5.0
        assert text_line.roi_type == ROIType.BOTTOM
        assert text_line.confidence == 0.80  # Média de 0.85 e 0.75
    
    def test_create_text_line_empty_words(self, extractor):
        """Testa que TextLine não é criada com palavras vazias"""
        text_line = extractor._create_text_line(
            timestamp=5.0,
            roi_type=ROIType.BOTTOM,
            bbox=(10, 100, 100, 20),
            words=[]
        )
        
        assert text_line is None


class TestTextLine:
    """Testes para modelo TextLine"""
    
    def test_text_line_creation(self):
        """Testa criação de TextLine"""
        text_line = TextLine(
            frame_ts=10.5,
            roi_type=ROIType.BOTTOM,
            text="Sample subtitle text",
            bbox=(100, 200, 300, 40),
            confidence=0.85,
            words=[]
        )
        
        assert text_line.frame_ts == 10.5
        assert text_line.roi_type == ROIType.BOTTOM
        assert text_line.text == "Sample subtitle text"
        assert text_line.confidence == 0.85
    
    def test_text_line_repr(self):
        """Testa representação de TextLine"""
        text_line = TextLine(
            frame_ts=5.0,
            roi_type=ROIType.TOP,
            text="A very long subtitle text that should be truncated in repr",
            bbox=(0, 0, 100, 20),
            confidence=0.90,
            words=[]
        )
        
        repr_str = repr(text_line)
        
        assert 'ts=5.00s' in repr_str
        assert 'roi=top' in repr_str
        assert 'conf=0.90' in repr_str


class TestROIType:
    """Testes para enum ROIType"""
    
    def test_roi_types_exist(self):
        """Testa que todos os tipos de ROI existem"""
        assert ROIType.BOTTOM.value == 'bottom'
        assert ROIType.TOP.value == 'top'
        assert ROIType.MIDDLE.value == 'middle'
