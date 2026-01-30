"""
Testes para audio_utils
"""

import pytest
from unittest.mock import patch, Mock
from app.audio_utils import extract_audio, get_audio_duration
import subprocess


def test_extract_audio_success(temp_dir):
    """Testa extração de áudio com sucesso"""
    output_path = f"{temp_dir}/audio.wav"
    
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')
        
        result = extract_audio('video.mp4', output_path, timeout=30)
        
        assert result == output_path
        assert mock_run.called
        
        # Verificar que FFmpeg foi chamado com flags corretas
        cmd = mock_run.call_args[0][0]
        assert 'ffmpeg' in cmd
        assert '-hide_banner' in cmd
        assert '-nostdin' in cmd


def test_extract_audio_timeout():
    """Testa que timeout é respeitado"""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='ffmpeg', timeout=1)
        
        with pytest.raises(subprocess.TimeoutExpired):
            extract_audio('video.mp4', timeout=1)


def test_get_audio_duration():
    """Testa obtenção de duração"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout='45.5\n',
            stderr=''
        )
        
        duration = get_audio_duration('audio.wav')
        
        assert duration == 45.5
        assert mock_run.called
