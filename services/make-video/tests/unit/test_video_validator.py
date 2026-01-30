"""
Testes para app.video_validator
"""

import pytest
import json
from unittest.mock import Mock, patch
from app.video_validator import (
    validate_video_integrity,
    VideoIntegrityError,
    get_video_info,
    _validate_metadata,
    _validate_frame_decode
)


@pytest.fixture
def valid_metadata():
    """Metadata válido de ffprobe"""
    return {
        'streams': [
            {
                'codec_type': 'video',
                'codec_name': 'h264',
                'width': 1920,
                'height': 1080,
                'r_frame_rate': '30/1'
            }
        ],
        'format': {
            'duration': '60.5',
            'size': '1234567'
        }
    }


def test_validate_video_integrity_success(valid_metadata):
    """Testa validação de vídeo válido"""
    with patch('subprocess.run') as mock_run:
        # Mock ffprobe (metadata check)
        mock_run.return_value = Mock(
            stdout=json.dumps(valid_metadata),
            returncode=0
        )
        
        result = validate_video_integrity('/fake/video.mp4', timeout=10)
        
        assert result is True
        assert mock_run.call_count == 2  # ffprobe + ffmpeg


def test_validate_video_integrity_no_video_stream():
    """Testa vídeo sem stream de vídeo"""
    invalid_metadata = {
        'streams': [
            {'codec_type': 'audio'}  # Apenas áudio
        ],
        'format': {'duration': '60'}
    }
    
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            stdout=json.dumps(invalid_metadata),
            returncode=0
        )
        
        with pytest.raises(VideoIntegrityError, match="No video stream found"):
            validate_video_integrity('/fake/video.mp4')


def test_validate_video_integrity_no_duration():
    """Testa vídeo sem duration"""
    invalid_metadata = {
        'streams': [
            {'codec_type': 'video'}
        ],
        'format': {}  # Sem duration
    }
    
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            stdout=json.dumps(invalid_metadata),
            returncode=0
        )
        
        with pytest.raises(VideoIntegrityError, match="No duration found"):
            validate_video_integrity('/fake/video.mp4')


def test_validate_video_integrity_corrupted_frame():
    """Testa vídeo com frame corrompido"""
    import subprocess
    
    valid_metadata = {
        'streams': [{'codec_type': 'video'}],
        'format': {'duration': '60'}
    }
    
    with patch('subprocess.run') as mock_run:
        # Primeira chamada (ffprobe): OK
        # Segunda chamada (ffmpeg frame decode): FAIL
        mock_run.side_effect = [
            Mock(stdout=json.dumps(valid_metadata), returncode=0),
            subprocess.CalledProcessError(1, 'ffmpeg', stderr='Frame decode failed')
        ]
        
        with pytest.raises(VideoIntegrityError):
            validate_video_integrity('/fake/video.mp4')


def test_get_video_info(valid_metadata):
    """Testa extração de informações do vídeo"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            stdout=json.dumps(valid_metadata),
            returncode=0
        )
        
        info = get_video_info('/fake/video.mp4')
        
        assert info['duration'] == 60.5
        assert info['width'] == 1920
        assert info['height'] == 1080
        assert info['codec'] == 'h264'
        assert info['fps'] == 30.0


def test_validate_metadata_invalid_json():
    """Testa metadata com JSON inválido"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            stdout='invalid json{',
            returncode=0
        )
        
        with pytest.raises(VideoIntegrityError, match="Invalid ffprobe output"):
            _validate_metadata('/fake/video.mp4', timeout=5)
