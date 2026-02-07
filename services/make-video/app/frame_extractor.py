"""
Frame Extractor Otimizado (Sprint 05)

Extração eficiente de frames usando FFmpeg batch extraction.
Elimina necessidade de transcode completo para codecs pesados (AV1).
"""

import subprocess
import tempfile
import logging
from pathlib import Path
from typing import List, Tuple, Optional
import cv2
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Resultado da extração de frames"""
    frames: List[Tuple[np.ndarray, float]]  # [(frame, timestamp), ...]
    extraction_time_ms: float
    method: str  # 'opencv' or 'ffmpeg'


class FFmpegFrameExtractor:
    """
    Extrator otimizado de frames usando FFmpeg
    
    Sprint 05: Usa FFmpeg para extrair frames específicos sem transcode completo
    """
    
    def __init__(self, downscale_width: int = 640):
        self.downscale_width = downscale_width
        self.ffmpeg_available = self._check_ffmpeg_available()
    
    def _check_ffmpeg_available(self) -> bool:
        """Verifica se ffmpeg e ffprobe estão disponíveis"""
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                check=True,
                timeout=5
            )
            subprocess.run(
                ['ffprobe', '-version'],
                capture_output=True,
                check=True,
                timeout=5
            )
            logger.info("FFmpeg available for frame extraction")
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"FFmpeg not available: {e} - will use OpenCV only")
            return False
    
    def extract_frames(
        self,
        video_path: str,
        timestamps: List[float],
        timeout: int = 60
    ) -> ExtractionResult:
        """
        Extrai frames em timestamps específicos
        
        Estratégia:
        1. Tentar OpenCV primeiro (rápido para H.264/H.265)
        2. Se falhar ou for codec pesado (AV1), usar FFmpeg batch
        
        Args:
            video_path: Caminho do vídeo
            timestamps: Lista de timestamps (segundos)
            timeout: Timeout em segundos
        
        Returns:
            ExtractionResult com frames e métricas
        """
        import time
        start_time = time.time()
        
        # Detectar codec
        codec = self._detect_codec(video_path)
        
        # AV1 ou codecs pesados: usar FFmpeg (se disponível)
        use_ffmpeg = (
            self.ffmpeg_available and
            (codec in ['av1', 'vp9', 'hevc'] or not self._try_opencv_fast(video_path))
        )
        
        if use_ffmpeg:
            logger.info(f"Using FFmpeg extraction for codec: {codec}")
            frames = self._extract_with_ffmpeg(video_path, timestamps, timeout)
            method = 'ffmpeg'
        else:
            logger.info(f"Using OpenCV extraction for codec: {codec}")
            frames = self._extract_with_opencv(video_path, timestamps)
            method = 'opencv'
        
        extraction_time_ms = (time.time() - start_time) * 1000
        
        return ExtractionResult(
            frames=frames,
            extraction_time_ms=extraction_time_ms,
            method=method
        )
    
    def _detect_codec(self, video_path: str) -> str:
        """Detecta codec do vídeo usando ffprobe"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            codec = result.stdout.strip().lower()
            return codec
        
        except Exception as e:
            logger.warning(f"Could not detect codec: {e}")
            return 'unknown'
    
    def _try_opencv_fast(self, video_path: str) -> bool:
        """Testa se OpenCV consegue abrir vídeo rapidamente"""
        try:
            cap = cv2.VideoCapture(video_path)
            can_open = cap.isOpened()
            
            if can_open:
                # Tentar ler um frame
                ret, _ = cap.read()
                cap.release()
                return ret
            
            cap.release()
            return False
        
        except Exception:
            return False
    
    def _extract_with_opencv(
        self,
        video_path: str,
        timestamps: List[float]
    ) -> List[Tuple[np.ndarray, float]]:
        """Extrai frames com OpenCV (método atual)"""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise Exception("Could not open video with OpenCV")
        
        frames = []
        
        for ts in timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ret, frame = cap.read()
            
            if ret:
                # Downscale
                frame_scaled = self._downscale_frame(frame)
                frames.append((frame_scaled, ts))
        
        cap.release()
        
        return frames
    
    def _extract_with_ffmpeg(
        self,
        video_path: str,
        timestamps: List[float],
        timeout: int = 60
    ) -> List[Tuple[np.ndarray, float]]:
        """
        Extrai frames com FFmpeg (otimizado para codecs pesados)
        
        Usa select filter para extrair apenas frames específicos
        """
        frames = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Criar select expression para timestamps
            # Ex: "eq(t,5.2)+eq(t,10.5)+eq(t,15.8)"
            # Aproximação: gte(t,5.0)*lt(t,5.5) para janelas
            
            for i, ts in enumerate(timestamps):
                output_file = tmpdir_path / f"frame_{i:04d}.jpg"
                
                # Extrair frame único em timestamp específico
                cmd = [
                    'ffmpeg',
                    '-ss', str(ts),  # Seek to timestamp
                    '-i', video_path,
                    '-vframes', '1',  # Extract 1 frame
                    '-vf', f'scale={self.downscale_width}:-1',  # Downscale
                    '-f', 'image2',
                    '-y',
                    str(output_file)
                ]
                
                try:
                    # Use minimum 2s timeout per frame for heavy codecs
                    frame_timeout = max(2, timeout // len(timestamps))
                    subprocess.run(
                        cmd,
                        capture_output=True,
                        timeout=frame_timeout,
                        check=False  # Não falhar se um frame falhar
                    )
                    
                    # Ler frame extraído
                    if output_file.exists():
                        frame = cv2.imread(str(output_file))
                        if frame is not None:
                            frames.append((frame, ts))
                
                except subprocess.TimeoutExpired:
                    logger.warning(f"FFmpeg timeout extracting frame @ {ts}s")
                    continue
                except Exception as e:
                    logger.warning(f"FFmpeg error extracting frame @ {ts}s: {e}")
                    continue
        
        return frames
    
    def _downscale_frame(self, frame: np.ndarray) -> np.ndarray:
        """Downscale frame para largura target"""
        h, w = frame.shape[:2]
        
        if w <= self.downscale_width:
            return frame
        
        scale_factor = self.downscale_width / w
        new_h = int(h * scale_factor)
        
        frame_scaled = cv2.resize(
            frame,
            (self.downscale_width, new_h),
            interpolation=cv2.INTER_AREA
        )
        
        return frame_scaled
