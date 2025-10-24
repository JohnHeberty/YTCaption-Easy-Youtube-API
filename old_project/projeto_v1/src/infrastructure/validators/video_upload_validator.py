"""
Validador de arquivos de vídeo enviados.
Usa FFprobe para análise detalhada.
"""
import subprocess
import json
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from src.domain.interfaces import IVideoUploadValidator
from src.domain.exceptions import (
    ValidationError,
    UnsupportedFormatError,
    FileTooLargeError,
    InvalidVideoFileError
)


class VideoUploadValidator(IVideoUploadValidator):
    """Valida uploads de vídeo usando FFprobe."""
    
    # Formatos suportados
    SUPPORTED_VIDEO_FORMATS = [
        '.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv',
        '.wmv', '.m4v', '.mpg', '.mpeg', '.3gp'
    ]
    
    SUPPORTED_AUDIO_FORMATS = [
        '.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg',
        '.wma', '.opus'
    ]
    
    SUPPORTED_MIME_TYPES = [
        'video/mp4', 'video/x-msvideo', 'video/quicktime',
        'video/x-matroska', 'video/webm', 'video/x-flv',
        'audio/mpeg', 'audio/wav', 'audio/aac', 'audio/mp4',
        'audio/flac', 'audio/ogg', 'audio/x-ms-wma'
    ]
    
    def __init__(self, ffprobe_path: str = "ffprobe"):
        self.ffprobe_path = ffprobe_path
        self._check_ffprobe_available()
    
    def _check_ffprobe_available(self):
        """Verifica se FFprobe está disponível."""
        try:
            subprocess.run(
                [self.ffprobe_path, '-version'],
                capture_output=True,
                check=True,
                timeout=5
            )
            logger.info(f"FFprobe available: {self.ffprobe_path}")
        except Exception as e:
            logger.warning(f"FFprobe not available: {e}")
    
    async def validate_file(
        self,
        file_path: Path,
        max_size_mb: int,
        max_duration_seconds: int
    ) -> Dict[str, Any]:
        """Valida arquivo de vídeo/áudio."""
        logger.info(f"Validating upload: {file_path.name}")
        
        # 1. Validar extensão
        extension = file_path.suffix.lower()
        all_formats = self.SUPPORTED_VIDEO_FORMATS + self.SUPPORTED_AUDIO_FORMATS
        if extension not in all_formats:
            raise UnsupportedFormatError(extension, all_formats)
        
        # 2. Validar tamanho
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            raise FileTooLargeError(size_mb, max_size_mb)
        
        # 3. Analisar com FFprobe
        metadata = await self._analyze_with_ffprobe(file_path)
        
        # 4. Validar duração
        duration = metadata.get('duration', 0)
        if duration > max_duration_seconds:
            raise ValidationError(
                f"Video duration ({duration}s) exceeds maximum ({max_duration_seconds}s)"
            )
        
        logger.info(
            f"✅ File validated: {file_path.name} "
            f"({size_mb:.2f}MB, {duration}s)"
        )
        
        return metadata
    
    async def _analyze_with_ffprobe(self, file_path: Path) -> Dict[str, Any]:
        """Analisa arquivo com FFprobe."""
        try:
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            
            data = json.loads(result.stdout)
            format_info = data.get('format', {})
            streams = data.get('streams', [])
            
            video_stream = next((s for s in streams if s['codec_type'] == 'video'), None)
            audio_stream = next((s for s in streams if s['codec_type'] == 'audio'), None)
            
            metadata = {
                'duration': float(format_info.get('duration', 0)),
                'size_bytes': int(format_info.get('size', 0)),
                'bitrate': int(format_info.get('bit_rate', 0)),
                'format': format_info.get('format_name', 'unknown'),
                'has_video': video_stream is not None,
                'has_audio': audio_stream is not None,
            }
            
            if video_stream:
                metadata['video_codec'] = video_stream.get('codec_name')
                metadata['width'] = video_stream.get('width')
                metadata['height'] = video_stream.get('height')
            
            if audio_stream:
                metadata['audio_codec'] = audio_stream.get('codec_name')
                metadata['sample_rate'] = audio_stream.get('sample_rate')
                metadata['channels'] = audio_stream.get('channels')
            
            metadata['codec'] = metadata.get('video_codec') or metadata.get('audio_codec')
            
            return metadata
            
        except subprocess.TimeoutExpired:
            raise InvalidVideoFileError("FFprobe analysis timed out")
        except subprocess.CalledProcessError as e:
            raise InvalidVideoFileError(f"FFprobe failed: {e.stderr}")
        except json.JSONDecodeError:
            raise InvalidVideoFileError("FFprobe returned invalid JSON")
        except Exception as e:
            raise InvalidVideoFileError(f"Analysis failed: {str(e)}")
    
    def get_supported_formats(self) -> list:
        """Retorna lista de formatos suportados."""
        return self.SUPPORTED_VIDEO_FORMATS + self.SUPPORTED_AUDIO_FORMATS
