"""
Testes para app.video_processor
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock

# Só mock se não foi mockado ainda
if 'cv2' not in sys.modules:
    cv2_mock = MagicMock()
    cv2_mock.CAP_PROP_POS_MSEC = 0
    cv2_mock.COLOR_BGR2GRAY = 6
    cv2_mock.ADAPTIVE_THRESH_GAUSSIAN_C = 1
    cv2_mock.THRESH_BINARY = 0
    sys.modules['cv2'] = cv2_mock

if 'pytesseract' not in sys.modules:
    pytesseract_mock = MagicMock()
    pytesseract_mock.Output = MagicMock()
    pytesseract_mock.Output.DICT = 'dict'
    sys.modules['pytesseract'] = pytesseract_mock

from app.video_processor import (
    VideoProcessor,
    ProcessingDecision,
    ProcessingResult
)
from app.ocr_detector import OCRResult


@pytest.fixture
def mock_blacklist():
    """Mock do BlacklistManager"""
    mock = Mock()
    mock.is_blacklisted.return_value = False
    mock.add_to_blacklist.return_value = True
    mock.get_blacklist_info.return_value = None
    return mock


@pytest.fixture
def mock_ocr_detector():
    """Mock do OCRDetector"""
    mock = Mock()
    mock.extract_frame_at_timestamp.return_value = MagicMock()  # Fake frame
    mock.detect_subtitle_in_frame.return_value = OCRResult(
        text="Sample subtitle",
        confidence=85.0,
        word_count=2,
        has_subtitle=True
    )
    return mock


@pytest.fixture
def processor(mock_blacklist, mock_ocr_detector):
    """VideoProcessor com mocks"""
    return VideoProcessor(
        blacklist_manager=mock_blacklist,
        ocr_detector=mock_ocr_detector,
        audio_timeout=30,
        validation_timeout=5,
        storage_path="/tmp"
    )


@pytest.fixture
def video_info():
    """Video info sample"""
    return {
        'duration': 60.0,
        'width': 1920,
        'height': 1080,
        'codec': 'h264',
        'fps': 30.0
    }


def test_processor_initialization(mock_blacklist):
    """Testa inicialização do processor"""
    processor = VideoProcessor(
        blacklist_manager=mock_blacklist,
        audio_timeout=45,
        validation_timeout=10,
        min_ocr_confidence=70.0
    )
    
    assert processor.audio_timeout == 45
    assert processor.validation_timeout == 10
    assert processor.min_ocr_confidence == 70.0


def test_process_video_blacklisted(processor, mock_blacklist):
    """Testa vídeo já na blacklist"""
    mock_blacklist.is_blacklisted.return_value = True
    mock_blacklist.get_blacklist_info.return_value = {
        'video_id': 'test123',
        'reason': 'no_audio'
    }
    
    result = processor.process_video('test123', '/fake/video.mp4')
    
    assert result.decision == ProcessingDecision.SKIP_BLACKLISTED
    assert result.blacklist_reason == 'no_audio'
    assert result.video_id == 'test123'


@patch('app.video_processor.validate_video_integrity')
@patch('app.video_processor.get_video_info')
def test_process_video_corrupted(
    mock_get_info,
    mock_validate,
    processor,
    mock_blacklist
):
    """Testa vídeo corrompido"""
    from app.video_validator import VideoIntegrityError
    
    mock_validate.side_effect = VideoIntegrityError("Video corrupted")
    
    result = processor.process_video('test456', '/fake/video.mp4')
    
    assert result.decision == ProcessingDecision.SKIP_CORRUPTED
    assert result.blacklist_reason == 'corrupted'
    mock_blacklist.add_to_blacklist.assert_called_once()


@patch('app.video_processor.validate_video_integrity')
@patch('app.video_processor.get_video_info')
@patch('app.video_processor.extract_audio')
@patch('app.video_processor.get_audio_duration')
def test_process_video_no_audio(
    mock_duration,
    mock_extract,
    mock_get_info,
    mock_validate,
    processor,
    mock_blacklist,
    video_info
):
    """Testa vídeo sem áudio"""
    mock_get_info.return_value = video_info
    mock_extract.side_effect = Exception("No audio stream")
    
    result = processor.process_video('test789', '/fake/video.mp4')
    
    assert result.decision == ProcessingDecision.SKIP_NO_AUDIO
    assert result.blacklist_reason == 'no_audio'
    mock_blacklist.add_to_blacklist.assert_called_once()


@patch('app.video_processor.validate_video_integrity')
@patch('app.video_processor.get_video_info')
@patch('app.video_processor.extract_audio')
@patch('app.video_processor.get_audio_duration')
@patch('os.path.exists')
@patch('os.remove')
def test_process_video_no_subtitles(
    mock_remove,
    mock_exists,
    mock_duration,
    mock_extract,
    mock_get_info,
    mock_validate,
    processor,
    mock_blacklist,
    mock_ocr_detector,
    video_info
):
    """Testa vídeo sem legendas detectadas"""
    mock_get_info.return_value = video_info
    mock_duration.return_value = 60.0
    mock_exists.return_value = True
    
    # OCR não detecta legendas
    mock_ocr_detector.detect_subtitle_in_frame.return_value = OCRResult(
        text="",
        confidence=30.0,
        word_count=0,
        has_subtitle=False
    )
    
    result = processor.process_video('test_no_subs', '/fake/video.mp4', check_ocr=True)
    
    assert result.decision == ProcessingDecision.SKIP_NO_SUBTITLES
    assert result.blacklist_reason == 'no_subtitles'
    assert result.ocr_result is not None
    assert result.ocr_result.has_subtitle is False
    mock_blacklist.add_to_blacklist.assert_called_once()
    
    # Audio cleanup deve ser chamado (pode ser 1x ou 2x devido à limpeza prévia)
    assert mock_remove.call_count >= 1


@patch('app.video_processor.validate_video_integrity')
@patch('app.video_processor.get_video_info')
@patch('app.video_processor.extract_audio')
@patch('app.video_processor.get_audio_duration')
def test_process_video_success(
    mock_duration,
    mock_extract,
    mock_get_info,
    mock_validate,
    processor,
    mock_blacklist,
    mock_ocr_detector,
    video_info
):
    """Testa processamento bem-sucedido"""
    mock_get_info.return_value = video_info
    mock_duration.return_value = 60.0
    
    # OCR detecta legendas
    mock_ocr_detector.detect_subtitle_in_frame.return_value = OCRResult(
        text="Hello world",
        confidence=85.0,
        word_count=2,
        has_subtitle=True
    )
    
    result = processor.process_video('test_success', '/fake/video.mp4', check_ocr=True)
    
    assert result.decision == ProcessingDecision.PROCESS
    assert result.audio_path is not None
    assert result.audio_duration == 60.0
    assert result.video_info == video_info
    assert result.ocr_result.has_subtitle is True
    assert mock_blacklist.add_to_blacklist.call_count == 0  # Não blacklistado


@patch('app.video_processor.validate_video_integrity')
@patch('app.video_processor.get_video_info')
@patch('app.video_processor.extract_audio')
@patch('app.video_processor.get_audio_duration')
def test_process_video_without_ocr_check(
    mock_duration,
    mock_extract,
    mock_get_info,
    mock_validate,
    processor,
    mock_ocr_detector,
    video_info
):
    """Testa processamento sem verificação OCR"""
    mock_get_info.return_value = video_info
    mock_duration.return_value = 60.0
    
    result = processor.process_video('test_no_ocr', '/fake/video.mp4', check_ocr=False)
    
    assert result.decision == ProcessingDecision.PROCESS
    assert result.ocr_result is None  # OCR não executado
    mock_ocr_detector.detect_subtitle_in_frame.assert_not_called()


@patch('os.path.exists')
@patch('os.remove')
def test_cleanup_audio_success(mock_remove, mock_exists, processor):
    """Testa limpeza de áudio bem-sucedida"""
    mock_exists.return_value = True
    
    processor.cleanup_audio('/tmp/test_audio.wav')
    
    mock_remove.assert_called_once_with('/tmp/test_audio.wav')


@patch('os.path.exists')
@patch('os.remove')
def test_cleanup_audio_not_exists(mock_remove, mock_exists, processor):
    """Testa limpeza quando arquivo não existe"""
    mock_exists.return_value = False
    
    processor.cleanup_audio('/tmp/nonexistent.wav')
    
    mock_remove.assert_not_called()


@patch('os.path.exists')
@patch('os.remove')
def test_cleanup_audio_error(mock_remove, mock_exists, processor):
    """Testa erro na limpeza de áudio"""
    mock_exists.return_value = True
    mock_remove.side_effect = OSError("Permission denied")
    
    # Não deve lançar exceção
    processor.cleanup_audio('/tmp/test_audio.wav')


def test_check_subtitles_presence_no_frame(processor, mock_ocr_detector, video_info):
    """Testa quando extração de frame falha"""
    mock_ocr_detector.extract_frame_at_timestamp.return_value = None
    
    result = processor._check_subtitles_presence('/fake/video.mp4', video_info)
    
    assert result.has_subtitle is False
    assert result.confidence == 0.0
    assert result.word_count == 0
