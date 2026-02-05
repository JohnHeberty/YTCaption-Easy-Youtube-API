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
    - Full frame OCR detection
    - Confidence scoring for text detection
    """
    
    def __init__(self, min_confidence: float = 0.40, frames_per_second: int = 6, max_frames: int = 240):
        """
        Args:
            min_confidence: Confiança mínima para detectar texto (0-1)
            frames_per_second: Frames analisados por segundo (padrão: 6)
            max_frames: Limite máximo de frames para evitar OOM (padrão: 240)
        """
        self.min_confidence = min_confidence
        self.frames_per_second = frames_per_second
        self.max_frames = max_frames
        self.tesseract_config = r'--oem 3 --psm 6 -l por+eng'
        
        logger.info(
            f"VideoValidator initialized "
            f"(min_confidence={min_confidence}, fps={frames_per_second}, max_frames={max_frames})"
        )
    
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
        Detecta legendas embutidas no vídeo usando OCR com early exit
        
        Estratégia otimizada:
        1. Analisa N frames por segundo (configurável, padrão: 6fps)
        2. Early exit: para na primeira detecção com confiança > threshold
        3. Limite máximo de frames para evitar OOM (padrão: 240 frames)
        4. Full frame OCR (ROI removido)
        5. 🚧 Transcoding automático para codecs não suportados (AV1)
        
        Args:
            video_path: Path do vídeo
        
        Returns:
            Tuple (has_subtitles, confidence, sample_text)
        """
        start_time = time.time()
        working_path = video_path
        cleanup_path = None
        
        try:
            # Converter para codec suportado se necessário (ex.: AV1 → H.264)
            working_path, cleanup_path = self._ensure_supported_codec(video_path)
            
            # Get video info já no arquivo convertido (se houver)
            info = self.get_video_info(working_path)
            duration = info['duration']
            
            # Sample frames at different timestamps
            timestamps = self._get_sample_timestamps(duration)
            
            logger.debug(f"OCR: Sampling up to {len(timestamps)} frames from {duration:.1f}s video")
            
            frames_analyzed = 0
            detections = []
            consecutive_failures = 0
            max_consecutive_failures = 3
            
            for ts in timestamps:
                frames_analyzed += 1
                
                frame = self._extract_frame(working_path, ts)
                if frame is None:
                    consecutive_failures += 1
                    
                    # 🚨 EARLY ABORT: Se 3 frames consecutivos falharem, pular vídeo
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(
                            f"❌ SKIP OCR: {consecutive_failures} consecutive frame extraction failures "
                            f"(likely codec issue) - marking as NO subtitles"
                        )
                        return False, 0.0, "Frame extraction failed (codec issue)"
                    
                    continue
                
                # Reset counter on success
                consecutive_failures = 0
                
                # Run OCR on full frame
                text = pytesseract.image_to_string(frame, config=self.tesseract_config)
                text = text.strip()
                
                if text:
                    confidence = self._calculate_ocr_confidence(text)
                    
                    # 🚀 EARLY EXIT: Se detectou com confiança suficiente, para!
                    if confidence >= self.min_confidence:
                        elapsed_ms = (time.time() - start_time) * 1000
                        logger.warning(
                            f"⚠️ EMBEDDED SUBTITLES detected (conf={confidence:.2f}, "
                            f"ts={ts:.1f}s, analyzed {frames_analyzed}/{len(timestamps)} frames, {elapsed_ms:.0f}ms): {text[:80]}"
                        )
                        return True, confidence, text
                    
                    # Armazenar para fallback
                    detections.append((text, confidence, ts))
                    logger.debug(f"OCR @ {ts:.1f}s (conf={confidence:.2f}): {text[:50]}")
            
            # Nenhuma detecção passou o threshold
            elapsed_ms = (time.time() - start_time) * 1000
            
            if not detections:
                logger.info(f"✅ No embedded subtitles detected (analyzed {frames_analyzed} frames, {elapsed_ms:.0f}ms)")
                return False, 0.0, ""
            
            # Retornar melhor detecção mesmo que abaixo do threshold
            best_text, best_conf, best_ts = max(detections, key=lambda x: x[1])
            logger.info(
                f"✅ Low confidence OCR (conf={best_conf:.2f} < {self.min_confidence}, "
                f"analyzed {frames_analyzed} frames, {elapsed_ms:.0f}ms)"
            )
            return False, best_conf, best_text
            
            return has_subs, best_conf, best_text
        
        except Exception as e:
            logger.error(f"❌ OCR detection error: {e}", exc_info=True)
            return False, 0.0, f"Error: {e}"
        
        finally:
            # Limpar arquivo transcodado temporário, se criado
            if cleanup_path:
                try:
                    Path(cleanup_path).unlink(missing_ok=True)
                except Exception:
                    logger.debug(f"Could not remove temp transcoded file: {cleanup_path}")
    
    def _get_sample_timestamps(self, duration: float) -> list:
        """
        Gera timestamps para sampling POR SEGUNDO
        
        Estratégia:
        1. Calcular total de frames: duration × frames_per_second
        2. Se total > max_frames → ajustar FPS proporcionalmente
        3. Gerar timestamps uniformemente ao longo do vídeo
        4. Se frames calculados > frames disponíveis → usar todos
        
        Args:
            duration: Duração do vídeo em segundos
        
        Returns:
            Lista de timestamps (em segundos)
        """
        # Calcular total de frames baseado em FPS
        total_frames = int(duration * self.frames_per_second)
        
        # Aplicar limite máximo de segurança
        if total_frames > self.max_frames:
            logger.warning(
                f"⚠️ Total frames ({total_frames}) exceeds max ({self.max_frames}). "
                f"Limiting to {self.max_frames} frames"
            )
            total_frames = self.max_frames
        
        # Calcular FPS efetivo após aplicar limite
        effective_fps = total_frames / duration if duration > 0 else self.frames_per_second
        
        # Gerar timestamps
        timestamps = []
        for i in range(total_frames):
            timestamp = i / effective_fps
            # Garantir que não excede duração do vídeo
            if timestamp < duration:
                timestamps.append(timestamp)
        
        logger.info(
            f"📊 OCR Sampling: {len(timestamps)} frames "
            f"({effective_fps:.2f} fps) for {duration:.1f}s video"
        )
        
        return timestamps
    
    def _extract_frame(self, video_path: str, timestamp: float, timeout: int = 3) -> Optional[any]:
        """
        Extrai um frame do vídeo em determinado timestamp com timeout
        
        🔧 FIX: Previne loop infinito em vídeos AV1 sem suporte de hardware
        - Timeout de 3 segundos por frame
        - Fallback para FFmpeg se OpenCV falhar
        - Early failure detection
        
        Returns:
            numpy array (BGR) ou None se falhar
        """
        import signal
        import tempfile
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Frame extraction timeout")
        
        # Try OpenCV first with timeout
        try:
            # Set timeout alarm (Unix only)
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout)
            
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                logger.warning(f"OpenCV failed to open video: {video_path}")
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)  # Cancel alarm
                # Try FFmpeg fallback
                return self._extract_frame_ffmpeg(video_path, timestamp)
            
            # Seek to timestamp
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            
            ret, frame = cap.read()
            cap.release()
            
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)  # Cancel alarm
            
            if not ret:
                logger.warning(f"Failed to extract frame at {timestamp}s - trying FFmpeg")
                return self._extract_frame_ffmpeg(video_path, timestamp)
            
            return frame
        
        except TimeoutError:
            logger.error(f"⏱️ TIMEOUT extracting frame at {timestamp}s with OpenCV - using FFmpeg")
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
            return self._extract_frame_ffmpeg(video_path, timestamp)
        
        except Exception as e:
            logger.error(f"Frame extraction error at {timestamp}s: {e}")
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
            return None
    
    def _extract_frame_ffmpeg(self, video_path: str, timestamp: float) -> Optional[any]:
        """
        Fallback: Extrai frame usando FFmpeg diretamente
        
        Mais lento mas funciona com qualquer codec (incluindo AV1)
        """
        import tempfile
        import numpy as np
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name
            
            cmd = [
                'ffmpeg',
                '-ss', str(timestamp),
                '-i', video_path,
                '-frames:v', '1',
                '-f', 'image2',
                '-y',
                tmp_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5,
                check=False
            )
            
            if result.returncode == 0 and Path(tmp_path).exists():
                frame = cv2.imread(tmp_path)
                Path(tmp_path).unlink(missing_ok=True)
                
                if frame is not None:
                    logger.debug(f"✅ FFmpeg extracted frame at {timestamp}s")
                    return frame
            
            Path(tmp_path).unlink(missing_ok=True)
            return None
        
        except Exception as e:
            logger.error(f"FFmpeg frame extraction failed: {e}")
            return None

    def _ensure_supported_codec(self, video_path: str) -> Tuple[str, Optional[str]]:
        """
        Garante que o vídeo está em codec suportado para OCR (H.264).
        
        - Se codec já suportado, retorna (video_path, None)
        - Se codec não suportado (ex.: AV1), transcodifica para H.264 temporário
        
        Returns:
            (working_path, cleanup_path)
        """
        info = self.get_video_info(video_path)
        codec = info.get('codec', '').lower()
        unsupported_codecs = {"av1"}
        
        if codec not in unsupported_codecs:
            return video_path, None
        
        # Transcodificar para H.264 para evitar travamentos do OpenCV com AV1
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        logger.warning(
            f"🔄 Transcoding unsupported codec ({codec}) to H.264 for OCR: {video_path} -> {temp_path}"
        )
        
        cmd = [
            'ffmpeg',
            '-y',
            '-i', video_path,
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-crf', '23',
            '-c:a', 'copy',
            temp_path
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=True
            )
            logger.info("✅ Transcoding completed for OCR path")
            return temp_path, temp_path
        except subprocess.TimeoutExpired:
            logger.error("❌ Transcoding timeout for OCR (AV1 → H.264)")
            Path(temp_path).unlink(missing_ok=True)
            raise VideoIntegrityError("Transcoding timeout")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Transcoding failed: {e.stderr}")
            Path(temp_path).unlink(missing_ok=True)
            raise VideoIntegrityError(f"Transcoding failed: {e.stderr}")
        except Exception as e:
            logger.error(f"❌ Unexpected transcoding error: {e}")
            Path(temp_path).unlink(missing_ok=True)
            raise VideoIntegrityError(f"Transcoding error: {e}")
    
    def _calculate_ocr_confidence(self, text: str) -> float:
        """
        Calcula confiança baseado em características do texto detectado
        
        Features:
        - Text length (longer = more confident)
        - Alphanumeric ratio (more alphanum = more confident)
        - Space presence (sentences have spaces)
        
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
        
        # Feature 3: Space presence (max 0.40)
        # Increased weight since we removed position bonus
        has_spaces = ' ' in text
        word_count = len(text.split())
        space_score = min(word_count / 5.0, 1.0) * 0.40 if has_spaces else 0
        confidence += space_score
        
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

