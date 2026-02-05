"""
Testes para app.ocr_detector
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock

# Mock dos módulos pesados antes de importar
cv2_mock = MagicMock()
cv2_mock.CAP_PROP_POS_MSEC = 0  # Valor real do OpenCV
cv2_mock.COLOR_BGR2GRAY = 6
cv2_mock.ADAPTIVE_THRESH_GAUSSIAN_C = 1
cv2_mock.THRESH_BINARY = 0
sys.modules['cv2'] = cv2_mock

pytesseract_mock = MagicMock()
pytesseract_mock.Output = MagicMock()
pytesseract_mock.Output.DICT = 'dict'
sys.modules['pytesseract'] = pytesseract_mock

import numpy as np
from app.ocr_detector import OCRDetector, OCRResult


@pytest.fixture
def detector():
    """Detector com configuração padrão"""
    return OCRDetector()


@pytest.fixture
def sample_frame():
    """Frame de teste 1920x1080"""
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


@pytest.fixture
def mock_ocr_data_with_text():
    """Mock de OCR com texto detectado"""
    return {
        'text': ['Hello', 'World', 'Test'],
        'conf': [85.5, 90.0, 80.0]
    }


@pytest.fixture
def mock_ocr_data_empty():
    """Mock de OCR sem texto"""
    return {
        'text': ['', '', ''],
        'conf': [-1, -1, -1]
    }


def test_preprocess_for_ocr(detector, sample_frame):
    """Testa pré-processamento para OCR"""
    
    with patch('cv2.cvtColor', return_value=np.zeros((1080, 1920), dtype=np.uint8)), \
         patch('cv2.adaptiveThreshold', return_value=np.full((1080, 1920), 255, dtype=np.uint8)), \
         patch('cv2.bitwise_not', return_value=np.zeros((1080, 1920), dtype=np.uint8)):
        
        processed = detector._preprocess_for_ocr(sample_frame)
        
        # Deve ser grayscale (2D)
        assert len(processed.shape) == 2


def test_parse_ocr_result_with_text(detector, mock_ocr_data_with_text):
    """Testa parsing de resultado OCR com texto"""
    text, confidence, word_count = detector._parse_ocr_result(mock_ocr_data_with_text)
    
    assert text == "Hello World Test"
    assert confidence == pytest.approx(85.17, abs=0.1)  # (85.5 + 90 + 80) / 3
    assert word_count == 3


def test_parse_ocr_result_empty(detector, mock_ocr_data_empty):
    """Testa parsing de resultado OCR vazio"""
    text, confidence, word_count = detector._parse_ocr_result(mock_ocr_data_empty)
    
    assert text == ""
    assert confidence == 0.0
    assert word_count == 0


@patch('pytesseract.image_to_data')
@patch('cv2.cvtColor')
@patch('cv2.adaptiveThreshold')
def test_detect_subtitle_in_frame_with_subtitle(mock_thresh, mock_cvt, mock_ocr, detector, sample_frame, mock_ocr_data_with_text):
    """Testa detecção de legenda presente"""
    mock_cvt.return_value = np.zeros((162, 1920), dtype=np.uint8)
    mock_thresh.return_value = np.full((162, 1920), 255, dtype=np.uint8)
    mock_ocr.return_value = mock_ocr_data_with_text
    
    result = detector.detect_subtitle_in_frame(sample_frame, min_confidence=60.0)
    
    assert isinstance(result, OCRResult)
    assert result.has_subtitle is True
    assert result.confidence > 60.0
    assert result.word_count >= 2
    assert "Hello" in result.text


@patch('pytesseract.image_to_data')
@patch('cv2.cvtColor')
@patch('cv2.adaptiveThreshold')
def test_detect_subtitle_in_frame_no_subtitle(mock_thresh, mock_cvt, mock_ocr, detector, sample_frame, mock_ocr_data_empty):
    """Testa detecção sem legenda"""
    mock_cvt.return_value = np.zeros((162, 1920), dtype=np.uint8)
    mock_thresh.return_value = np.full((162, 1920), 255, dtype=np.uint8)
    mock_ocr.return_value = mock_ocr_data_empty
    
    result = detector.detect_subtitle_in_frame(sample_frame, min_confidence=60.0)
    
    assert isinstance(result, OCRResult)
    assert result.has_subtitle is False
    assert result.confidence == 0.0
    assert result.word_count == 0


@patch('pytesseract.image_to_data')
@patch('cv2.cvtColor')
@patch('cv2.adaptiveThreshold')
def test_detect_subtitle_in_frame_low_confidence(mock_thresh, mock_cvt, mock_ocr, detector, sample_frame):
    """Testa detecção com confiança baixa"""
    mock_cvt.return_value = np.zeros((162, 1920), dtype=np.uint8)
    mock_thresh.return_value = np.full((162, 1920), 255, dtype=np.uint8)
    
    low_conf_data = {
        'text': ['Maybe', 'Text'],
        'conf': [45.0, 40.0]  # Abaixo de 60
    }
    mock_ocr.return_value = low_conf_data
    
    result = detector.detect_subtitle_in_frame(sample_frame, min_confidence=60.0)
    
    assert result.has_subtitle is False  # Confiança < threshold


@patch('cv2.VideoCapture')
def test_extract_frame_at_timestamp_success(mock_cap_class, detector):
    """Testa extração de frame com sucesso"""
    # Mock do VideoCapture
    mock_cap = MagicMock()
    mock_cap.read.return_value = (True, np.zeros((1080, 1920, 3), dtype=np.uint8))
    mock_cap_class.return_value = mock_cap
    
    frame = detector.extract_frame_at_timestamp('/fake/video.mp4', timestamp=5.0)
    
    assert frame is not None
    assert frame.shape == (1080, 1920, 3)
    # Verificar que set foi chamado com timestamp correto
    mock_cap.set.assert_called_once()
    assert mock_cap.set.call_args[0][1] == 5000.0  # Timestamp em ms
    mock_cap.release.assert_called_once()


@patch('cv2.VideoCapture')
def test_extract_frame_at_timestamp_failure(mock_cap_class, detector):
    """Testa falha na extração de frame"""
    mock_cap = MagicMock()
    mock_cap.read.return_value = (False, None)
    mock_cap_class.return_value = mock_cap
    
    frame = detector.extract_frame_at_timestamp('/fake/video.mp4', timestamp=5.0)
    
    assert frame is None
    mock_cap.release.assert_called_once()


def test_detector_initialization():
    """Testa inicialização do detector"""
    detector = OCRDetector()
    
    # Detector deve ser inicializado sem erros
    assert detector is not None
