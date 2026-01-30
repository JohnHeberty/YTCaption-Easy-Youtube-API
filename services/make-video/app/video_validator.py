"""
Video Validator com OCR

Valida integridade de vídeo e detecta legendas embutidas usando OCR
"""

import subprocess
import json
import logging
import time
import cv2
import pytesseract
import os
import re
from typing import Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class VideoIntegrityError(Exception):
    """Exceção para vídeos corrompidos ou inválidos"""
    pass


class VideoValidator:
    """
    Valida vídeos e detecta legendas embutidas usando OCR
    
    PLAN.md Section 2.3.2: VideoValidator Class
    - Validates video integrity (ffprobe + frame decode)
    - Detects embedded subtitles using OCR
    - Samples multiple frames (start, middle, end)
    - ROI-based detection (bottom 30% of frame)
    - Confidence scoring for text detection
    """
    
    def __init__(self, min_confidence: float = 0.40):
        """
        Args:
            min_confidence: Confiança mínima para detectar texto (0-1)
        """
        self.min_confidence = min_confidence
        self.tesseract_config = r'--oem 3 --psm 6 -l por+eng'
        
        logger.info(f"VideoValidator initialized (min_confidence={min_confidence})")
    
    def validate_video_integrity(self, video_path: str, timeout: int = 10) -> bool:
        """
        Valida integridade do vídeo usando ffprobe + frame decode
        
        Args:
            video_path: Path do vídeo
            timeout: Timeout em segundos
        
        Returns:
            True se vídeo é válido
        
        Raises:
            VideoIntegrityError: Se vídeo está corrompido
        """
        start_time = time.time()
        
        try:
            # Step 1: Validar metadata com ffprobe
            self._validate_metadata(video_path, timeout=timeout // 2)
            
            # Step 2: Tentar decodificar um frame
            self._validate_frame_decode(video_path, timeout=timeout // 2)
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            logger.info(f"✅ Video integrity OK: {video_path} ({elapsed_ms:.0f}ms)")
            return True
        
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            
            logger.error(f"❌ Video integrity check failed: {video_path} - {e}")
            raise VideoIntegrityError(f"Video validation failed: {e}")
    
    def has_embedded_subtitles(self, video_path: str) -> Tuple[bool, float, str]:
        """
        Detecta legendas embutidas no vídeo usando OCR
        
        PLAN.md Section 2.3.3: OCR Detection Logic
        - Sample 6 frames: início (2 frames), meio (2 frames), fim (2 frames)
        - Extract ROI: Bottom 30% of frame (where subtitles usually are)
        - OCR: pytesseract with Portuguese + English
        - Confidence: Weighted score based on text characteristics
        
        Args:
            video_path: Path do vídeo
        
        Returns:
            Tuple (has_subtitles, confidence, sample_text)
        """
        start_time = time.time()
        
        try:
            # Get video info
            info = self.get_video_info(video_path)
            duration = info['duration']
            
            # Sample frames at different timestamps
            timestamps = self._get_sample_timestamps(duration)
            
            logger.debug(f"OCR: Sampling {len(timestamps)} frames from {duration:.1f}s video")
            
            detections = []
            
            for ts in timestamps:
                frame = self._extract_frame(video_path, ts)
                if frame is None:
                    continue
                
                # Extract ROI (bottom 30%)
                roi = self._extract_subtitle_roi(frame)
                
                # Run OCR
                text = pytesseract.image_to_string(roi, config=self.tesseract_config)
                text = text.strip()
                
                if text:
                    confidence = self._calculate_ocr_confidence(text, frame.shape[0], roi.shape[0])
                    detections.append((text, confidence, ts))
                    logger.debug(f"OCR @ {ts:.1f}s (conf={confidence:.2f}): {text[:50]}")
            
            # Aggregate results
            if not detections:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(f"✅ No embedded subtitles detected ({elapsed_ms:.0f}ms)")
                return False, 0.0, ""
            
            # Use highest confidence detection
            best_text, best_conf, best_ts = max(detections, key=lambda x: x[1])
            
            has_subs = best_conf >= self.min_confidence
            elapsed_ms = (time.time() - start_time) * 1000
            
            if has_subs:
                logger.warning(
                    f"⚠️ EMBEDDED SUBTITLES detected (conf={best_conf:.2f}, "
                    f"ts={best_ts:.1f}s, {len(detections)} detections, {elapsed_ms:.0f}ms): {best_text[:80]}"
                )
            else:
                logger.info(f"✅ Low confidence OCR (conf={best_conf:.2f} < {self.min_confidence}, {elapsed_ms:.0f}ms)")
            
            return has_subs, best_conf, best_text
        
        except Exception as e:
            logger.error(f"❌ OCR detection error: {e}", exc_info=True)
            return False, 0.0, f"Error: {e}"
    
    def _get_sample_timestamps(self, duration: float) -> list:
        """
        Gera timestamps para sampling
        
        Returns 6 timestamps: início, meio, fim (2 cada)
        """
        if duration < 10:
            # Video curto: apenas 3 frames
            return [
                duration * 0.2,
                duration * 0.5,
                duration * 0.8,
            ]
        else:
            # Video normal: 6 frames
            return [
                duration * 0.1,   # 10%
                duration * 0.2,   # 20%
                duration * 0.4,   # 40%
                duration * 0.6,   # 60%
                duration * 0.8,   # 80%
                duration * 0.9,   # 90%
            ]
    
    def _extract_frame(self, video_path: str, timestamp: float) -> Optional[any]:
        """
        Extrai um frame do vídeo em determinado timestamp
        
        Returns:
            numpy array (BGR) ou None se falhar
        """
        try:
            cap = cv2.VideoCapture(video_path)
            
            # Seek to timestamp
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                logger.warning(f"Failed to extract frame at {timestamp}s")
                return None
            
            return frame
        
        except Exception as e:
            logger.error(f"Frame extraction error at {timestamp}s: {e}")
            return None
    
    def _extract_subtitle_roi(self, frame: any) -> any:
        """
        Extrai ROI (Region of Interest) onde legendas geralmente aparecem
        
        Returns bottom 30% of frame
        """
        height, width = frame.shape[:2]
        roi_height = int(height * 0.30)
        
        # Bottom 30%
        roi = frame[-roi_height:, :]
        
        return roi
    
    def _calculate_ocr_confidence(self, text: str, frame_height: int, roi_height: int) -> float:
        """
        Calcula confiança baseado em características do texto detectado
        
        Features:
        - Text length (longer = more confident)
        - Alphanumeric ratio (more alphanum = more confident)
        - Space presence (sentences have spaces)
        - Position in frame (bottom = subtitle region)
        
        Returns:
            Confidence score 0-1
        """
        # Base confidence
        confidence = 0.0
        
        # Feature 1: Text length (max 0.30)
        text_len = len(text)
        len_score = min(text_len / 50.0, 1.0) * 0.30
        confidence += len_score
        
        # Feature 2: Alphanumeric ratio (max 0.30)
        alnum_count = sum(c.isalnum() for c in text)
        alnum_ratio = alnum_count / max(len(text), 1)
        confidence += alnum_ratio * 0.30
        
        # Feature 3: Space presence (max 0.20)
        has_spaces = ' ' in text
        word_count = len(text.split())
        space_score = min(word_count / 5.0, 1.0) * 0.20 if has_spaces else 0
        confidence += space_score
        
        # Feature 4: Position bonus (max 0.20)
        # ROI is already bottom region, give bonus
        position_score = 0.20
        confidence += position_score
        
        return min(confidence, 1.0)
    
    def _validate_metadata(self, video_path: str, timeout: int) -> dict:
        """
        Valida metadata do vídeo com ffprobe
        
        Returns:
            Dict com metadata do vídeo
        """
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True
        )
        
        try:
            metadata = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise VideoIntegrityError(f"Invalid ffprobe output: {e}")
        
        # Validar que tem pelo menos um stream de vídeo
        video_streams = [s for s in metadata.get('streams', []) if s.get('codec_type') == 'video']
        
        if not video_streams:
            raise VideoIntegrityError("No video stream found")
        
        # Validar que format tem duration
        format_info = metadata.get('format', {})
        if 'duration' not in format_info:
            raise VideoIntegrityError("No duration found in metadata")
        
        logger.debug(f"Metadata validation OK: {len(video_streams)} video stream(s)")
        
        return metadata
    
    def _validate_frame_decode(self, video_path: str, timeout: int):
        """
        Tenta decodificar um frame do vídeo
        
        Isso catch corrupções que ffprobe não detecta
        """
        cmd = [
            'ffmpeg',
            '-hide_banner',
            '-nostdin',
            '-i', video_path,
            '-frames:v', '1',  # Apenas 1 frame
            '-f', 'null',  # Não salvar output
            '-'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )
            logger.debug("Frame decode validation OK")
        except subprocess.CalledProcessError as e:
            raise VideoIntegrityError(f"Frame decode failed: {e}")
        except Exception as e:
            raise VideoIntegrityError(f"Frame decode error: {e}")
    
    def get_video_info(self, video_path: str, timeout: int = 5) -> dict:
        """
        Obtém informações do vídeo
        
        Returns:
            Dict com: duration, width, height, codec, fps
        """
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-select_streams', 'v:0',  # Primeiro stream de vídeo
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True
        )
        
        metadata = json.loads(result.stdout)
        
        format_info = metadata.get('format', {})
        stream_info = metadata.get('streams', [{}])[0]
        
        fps_str = stream_info.get('r_frame_rate', '0/1')
        try:
            num, den = map(int, fps_str.split('/'))
            fps = num / den if den != 0 else 0
        except:
            fps = 0
        
        return {
            'duration': float(format_info.get('duration', 0)),
            'width': int(stream_info.get('width', 0)),
            'height': int(stream_info.get('height', 0)),
            'codec': stream_info.get('codec_name', 'unknown'),
            'fps': fps,
        }

