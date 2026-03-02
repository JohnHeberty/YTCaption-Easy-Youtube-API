"""
File Validator - Responsável por validar arquivos de entrada
Princípio: Single Responsibility
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Tuple

from ..shared.exceptions import AudioNormalizationException

logger = logging.getLogger(__name__)


class FileValidator:
    """Valida arquivos de áudio/vídeo e verifica requisitos"""
    
    def __init__(self, config: dict):
        self.config = config
        self.max_file_size = config.get('max_file_size_mb', 500) * 1024 * 1024
        self.max_duration = config.get('max_duration_minutes', 120) * 60
    
    async def validate_file_exists(self, file_path: str) -> bool:
        """Verifica se arquivo existe e é válido"""
        path = Path(file_path)
        if not path.exists():
            raise AudioNormalizationException(f"File not found: {file_path}")
        if not path.is_file():
            raise AudioNormalizationException(f"Path is not a file: {file_path}")
        return True
    
    async def validate_file_size(self, file_path: str) -> bool:
        """Valida tamanho do arquivo"""
        size = Path(file_path).stat().st_size
        size_mb = size / (1024 * 1024)
        
        if size > self.max_file_size:
            raise AudioNormalizationException(
                f"File too large: {size_mb:.2f}MB exceeds limit of {self.max_file_size/(1024*1024)}MB"
            )
        
        logger.info(f"✅ File size validation passed: {size_mb:.2f}MB")
        return True
    
    async def is_video_file(self, file_path: str) -> bool:
        """Detecta se arquivo é vídeo usando ffprobe"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                file_path
            ]
            
            logger.info(f"🔍 Detecting file type: {Path(file_path).name}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60
            )
            
            if process.returncode != 0:
                logger.warning(f"⚠️ ffprobe failed: {stderr.decode()}")
                return False
            
            data = json.loads(stdout.decode())
            streams = data.get('streams', [])
            
            has_video = any(s.get('codec_type') == 'video' for s in streams)
            has_audio = any(s.get('codec_type') == 'audio' for s in streams)
            
            if has_video:
                logger.info(f"🎬 Video detected (video: {has_video}, audio: {has_audio})")
                if not has_audio:
                    raise AudioNormalizationException(
                        "Video file has no audio stream"
                    )
            
            return has_video
            
        except asyncio.TimeoutError:
            logger.error(f"❌ ffprobe timeout for {Path(file_path).name}")
            raise AudioNormalizationException("Timeout analyzing file")
        except Exception as e:
            logger.warning(f"⚠️ Error detecting file type: {e}")
            # Fallback: check extension
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v']
            return any(file_path.lower().endswith(ext) for ext in video_extensions)
    
    async def get_audio_info(self, file_path: str) -> dict:
        """Obtém informações do áudio usando ffprobe"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )
            
            if process.returncode != 0:
                raise AudioNormalizationException(f"Failed to get audio info: {stderr.decode()}")
            
            data = json.loads(stdout.decode())
            
            # Extract relevant information
            format_info = data.get('format', {})
            audio_stream = next(
                (s for s in data.get('streams', []) if s.get('codec_type') == 'audio'),
                {}
            )
            
            return {
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0)),
                'bit_rate': int(format_info.get('bit_rate', 0)),
                'codec': audio_stream.get('codec_name', 'unknown'),
                'sample_rate': int(audio_stream.get('sample_rate', 0)),
                'channels': int(audio_stream.get('channels', 0)),
            }
            
        except asyncio.TimeoutError:
            raise AudioNormalizationException("Timeout getting audio info")
        except Exception as e:
            logger.error(f"Error getting audio info: {e}")
            raise AudioNormalizationException(f"Failed to get audio info: {str(e)}")
