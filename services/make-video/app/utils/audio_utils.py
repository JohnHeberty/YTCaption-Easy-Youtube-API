"""
Audio utilities

Helpers para extração e manipulação de áudio
"""

import subprocess
import tempfile
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def extract_audio(video_path: str, output_path: Optional[str] = None, 
                  sample_rate: int = 16000, timeout: int = 30) -> str:
    """
    Extrai áudio de vídeo usando FFmpeg
    
    Args:
        video_path: Path do vídeo
        output_path: Path de saída (ou None para criar temporário)
        sample_rate: Taxa de amostragem (Hz)
        timeout: Timeout em segundos
    
    Returns:
        Path do arquivo de áudio extraído
    
    Raises:
        subprocess.CalledProcessError: Se FFmpeg falha
        subprocess.TimeoutExpired: Se exceder timeout
    """
    # Criar arquivo temporário se necessário
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
    
    try:
        cmd = [
            'ffmpeg',
            '-hide_banner',
            '-nostdin',
            '-i', video_path,
            '-vn',  # Sem vídeo
            '-ar', str(sample_rate),  # Sample rate
            '-ac', '1',  # Mono
            '-y',  # Overwrite
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True
        )
        
        logger.info(f"✅ Audio extracted: {video_path} → {output_path}")
        return output_path
    
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ FFmpeg extraction failed: {e.stderr}")
        if os.path.exists(output_path):
            os.unlink(output_path)
        raise
    
    except Exception as e:
        logger.error(f"❌ Audio extraction error: {e}")
        if os.path.exists(output_path):
            os.unlink(output_path)
        raise


def get_audio_duration(audio_path: str, timeout: int = 10) -> float:
    """
    Obtém duração do áudio usando ffprobe
    
    Args:
        audio_path: Path do áudio
        timeout: Timeout em segundos
    
    Returns:
        Duração em segundos
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True
    )
    
    return float(result.stdout.strip())
