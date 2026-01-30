"""
Testes de edge cases e validação de bugs
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock

# Mock cv2 e pytesseract
if 'cv2' not in sys.modules:
    cv2_mock = MagicMock()
    cv2_mock.CAP_PROP_POS_MSEC = 0
    sys.modules['cv2'] = cv2_mock

if 'pytesseract' not in sys.modules:
    sys.modules['pytesseract'] = MagicMock()

from app.video_processor import VideoProcessor
from app.blacklist_manager import BlacklistManager


def test_video_processor_zero_duration(mock_redis):
    """Testa processamento com duração zero"""
    blacklist = BlacklistManager(mock_redis)
    processor = VideoProcessor(blacklist)
    
    # Video info com duration = 0
    video_info = {'duration': 0, 'width': 1920, 'height': 1080}
    
    with patch.object(processor.ocr, 'extract_frame_at_timestamp') as mock_extract:
        mock_extract.return_value = Mock()
        
        with patch.object(processor.ocr, 'detect_subtitle_in_frame') as mock_detect:
            from app.ocr_detector import OCRResult
            mock_detect.return_value = OCRResult(
                text="Test", confidence=80.0, word_count=1, has_subtitle=True
            )
            
            result = processor._check_subtitles_presence('/fake/video.mp4', video_info)
            
            # Deve usar default de 60s e extrair frame em 30s
            mock_extract.assert_called_once_with('/fake/video.mp4', 30.0)


def test_video_processor_negative_duration(mock_redis):
    """Testa processamento com duração negativa"""
    blacklist = BlacklistManager(mock_redis)
    processor = VideoProcessor(blacklist)
    
    # Video info com duration negativa
    video_info = {'duration': -10, 'width': 1920, 'height': 1080}
    
    with patch.object(processor.ocr, 'extract_frame_at_timestamp') as mock_extract:
        mock_extract.return_value = Mock()
        
        with patch.object(processor.ocr, 'detect_subtitle_in_frame') as mock_detect:
            from app.ocr_detector import OCRResult
            mock_detect.return_value = OCRResult(
                text="Test", confidence=80.0, word_count=1, has_subtitle=True
            )
            
            result = processor._check_subtitles_presence('/fake/video.mp4', video_info)
            
            # Deve usar default de 60s
            mock_extract.assert_called_once_with('/fake/video.mp4', 30.0)


def test_blacklist_empty_video_id(mock_redis):
    """Testa blacklist com video_id vazio"""
    blacklist = BlacklistManager(mock_redis)
    
    # Não deve dar erro com string vazia
    blacklist.add_to_blacklist("", reason="test")
    assert blacklist.is_blacklisted("") is True


def test_blacklist_unicode_video_id(mock_redis):
    """Testa blacklist com caracteres unicode"""
    blacklist = BlacklistManager(mock_redis)
    
    video_id = "test_中文_🎬"
    blacklist.add_to_blacklist(video_id, reason="test")
    
    assert blacklist.is_blacklisted(video_id) is True
    info = blacklist.get_blacklist_info(video_id)
    assert info['video_id'] == video_id


def test_blacklist_special_characters(mock_redis):
    """Testa blacklist com caracteres especiais"""
    blacklist = BlacklistManager(mock_redis)
    
    video_id = "test:with:colons"
    blacklist.add_to_blacklist(video_id, reason="test")
    
    assert blacklist.is_blacklisted(video_id) is True


def test_blacklist_large_metadata(mock_redis):
    """Testa blacklist com metadata grande"""
    blacklist = BlacklistManager(mock_redis)
    
    large_metadata = {
        f"field_{i}": "x" * 1000 for i in range(10)
    }
    
    blacklist.add_to_blacklist("test_large", reason="test", metadata=large_metadata)
    
    info = blacklist.get_blacklist_info("test_large")
    assert info is not None
    assert info['reason'] == 'test'


def test_ocr_detector_empty_text():
    """Testa OCR com texto vazio"""
    import sys
    from unittest.mock import MagicMock
    
    if 'cv2' not in sys.modules:
        sys.modules['cv2'] = MagicMock()
    if 'pytesseract' not in sys.modules:
        sys.modules['pytesseract'] = MagicMock()
    
    from app.ocr_detector import OCRDetector
    
    detector = OCRDetector()
    
    # OCR data com apenas espaços
    ocr_data = {
        'text': ['   ', '\n', '\t'],
        'conf': [50.0, 40.0, 30.0]
    }
    
    text, confidence, word_count = detector._parse_ocr_result(ocr_data)
    
    # Deve ignorar espaços/whitespace
    assert word_count == 0


def test_ocr_detector_mixed_confidence():
    """Testa OCR com confidências mistas"""
    import sys
    from unittest.mock import MagicMock
    
    if 'cv2' not in sys.modules:
        sys.modules['cv2'] = MagicMock()
    if 'pytesseract' not in sys.modules:
        sys.modules['pytesseract'] = MagicMock()
    
    from app.ocr_detector import OCRDetector
    
    detector = OCRDetector()
    
    # Mix de confidências válidas e inválidas
    ocr_data = {
        'text': ['Good', '', 'Word', '', 'Text'],
        'conf': [85.0, -1, 90.0, -1, 80.0]  # -1 = invalid
    }
    
    text, confidence, word_count = detector._parse_ocr_result(ocr_data)
    
    assert word_count == 3  # Apenas os válidos
    assert "Good" in text
    assert "Word" in text
    assert "Text" in text
    assert confidence == pytest.approx(85.0, abs=3)  # Média dos válidos
