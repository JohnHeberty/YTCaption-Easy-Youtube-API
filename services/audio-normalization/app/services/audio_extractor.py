"""
Audio Extractor - Responsável por extrair áudio de vídeos
Princípio: Single Responsibility
"""
import asyncio
import logging
from pathlib import Path

from ..exceptions import AudioNormalizationException

logger = logging.getLogger(__name__)


class AudioExtractor:
    """Extrai áudio de arquivos de vídeo"""
    
    def __init__(self, config: dict):
        self.config = config
        self.extraction_timeout = config.get('extraction_timeout_sec', 300)
    
    async def extract_audio_from_video(self, video_path: str, output_dir: Path) -> str:
        """Extrai áudio de arquivo de vídeo"""
        try:
            video_size_mb = Path(video_path).stat().st_size / (1024 * 1024)
            logger.info(f"🎬 Starting audio extraction")
            logger.info(f"   └─ Video: {Path(video_path).name} ({video_size_mb:.2f}MB)")
            
            # Create output file path
            audio_path = output_dir / f"extracted_audio_{Path(video_path).stem}.wav"
            
            # FFmpeg command to extract audio
            cmd = [
                "ffmpeg", "-i", video_path,
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # Compatible codec
                "-ar", "44100",  # Sample rate
                "-ac", "2",  # Stereo
                "-y",  # Overwrite
                str(audio_path)
            ]
            
            logger.info(f"🔄 Executing ffmpeg for extraction...")
            start_time = asyncio.get_event_loop().time()
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.extraction_timeout
            )
            
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if process.returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"❌ ffmpeg failed after {elapsed:.1f}s:")
                logger.error(f"   └─ {error_msg[:500]}")
                raise AudioNormalizationException(
                    f"Failed to extract audio: {error_msg[:200]}"
                )
            
            if not audio_path.exists():
                raise AudioNormalizationException(
                    "Audio file not created after extraction"
                )
            
            audio_size_mb = audio_path.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Audio extracted in {elapsed:.1f}s")
            logger.info(f"   └─ File: {audio_path.name} ({audio_size_mb:.2f}MB)")
            
            return str(audio_path)
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Extraction timeout after {self.extraction_timeout}s")
            raise AudioNormalizationException(
                f"Audio extraction timeout after {self.extraction_timeout}s"
            )
        except AudioNormalizationException:
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during extraction: {e}")
            raise AudioNormalizationException(f"Audio extraction failed: {str(e)}")
