"""
Video Validator com OCR e TRSD

Valida integridade de vídeo e detecta legendas embutidas usando OCR + TRSD
"""

import subprocess
import json
import logging
import time
import cv2
import pytesseract
import os
import re
from typing import Tuple, Optional, Dict
from pathlib import Path

# TRSD imports (Sprint 04)
from app.subtitle_detector import TextRegionExtractor
from app.temporal_tracker import TemporalTracker
from app.subtitle_classifier_v2 import SubtitleClassifierV2  # Sprint 08 - Reescrito para 90%+ precisão
from app.frame_extractor import FFmpegFrameExtractor  # Sprint 05
from app.telemetry import TRSDTelemetry, DebugArtifactSaver, PerformanceMetrics  # Sprint 07
from app.config import Settings

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
        
        # TRSD Components (Sprint 04)
        self.config = Settings()
        self.trsd_enabled = self.config.trsd_enabled
        
        if self.trsd_enabled:
            self.text_extractor = TextRegionExtractor(self.config)
            self.classifier = SubtitleClassifierV2(self.config, fps=frames_per_second)  # Sprint 08 - V2
            self.frame_extractor = FFmpegFrameExtractor(self.config.trsd_downscale_width)  # Sprint 05
            self.telemetry = TRSDTelemetry(enabled=True)  # Sprint 07
            self.debug_saver = DebugArtifactSaver(  # Sprint 07
                enabled=self.config.trsd_save_debug_artifacts,
                base_dir='storage/debug_artifacts'
            )
            logger.info("TRSD enabled - using intelligent temporal detection")
        else:
            logger.info("TRSD disabled - using legacy OCR detection")
        
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
    
    def _detect_with_trsd(self, video_path: str, timeout: int = 60) -> Tuple[bool, float, str, Dict]:
        """
        Detecção inteligente com TRSD (Sprint 04)
        
        Pipeline:
        1. Extrai frames com OpenCV
        2. Para cada frame:
           - TextRegionExtractor detecta texto por ROI
        3. TemporalTracker rastreia texto entre frames
        4. SubtitleClassifier decide se é legenda ou texto estático
        
        Args:
            video_path: Path do vídeo
            timeout: Timeout em segundos
        
        Returns:
            Tuple (has_subtitles, confidence, reason, debug_info)
        """
        start_time = time.time()
        
        try:
            # Sprint 07: Start timing
            self.telemetry.start_timer('total')
            
            # Obter duração do vídeo
            info = self.get_video_info(video_path)
            duration = info['duration']
            
            # Determinar frames a analisar
            timestamps = self._get_sample_timestamps(duration)
            
            logger.info(f"TRSD: Analyzing {len(timestamps)} frames from {duration:.1f}s video")
            
            # Sprint 05: Extração otimizada de frames
            self.telemetry.start_timer('frame_extraction')
            extraction_result = self.frame_extractor.extract_frames(
                video_path, timestamps, timeout
            )
            frame_extraction_ms = self.telemetry.stop_timer('frame_extraction')
            
            logger.info(
                f"Frame extraction: {extraction_result.method}, "
                f"{extraction_result.extraction_time_ms:.0f}ms, "
                f"{len(extraction_result.frames)} frames"
            )
            
            # Criar tracker temporal
            tracker = TemporalTracker(self.config)
            
            # Sprint 07: Track OCR time
            self.telemetry.start_timer('ocr')
            
            frames_analyzed = 0
            total_lines_detected = 0
            
            for frame_idx, (frame, ts) in enumerate(extraction_result.frames):
                frames_analyzed += 1
                
                # Detectar texto com TextRegionExtractor
                text_lines = self.text_extractor.extract_from_frame(frame, ts, frame_idx)
                total_lines_detected += len(text_lines)
                
                # Atualizar tracker
                tracker.update(text_lines, frame_idx)
                
                # Early exit: se já temos evidência clara de legenda dinâmica
                if frames_analyzed >= 10 and frame_idx % 5 == 0:
                    # Calcular métricas parciais
                    partial_tracks = tracker.active_tracks
                    for track in partial_tracks:
                        track.compute_metrics(frames_analyzed)
                    
                    # Classificar parcialmente
                    self.telemetry.start_timer('classification')
                    result = self.classifier.decide(partial_tracks)
                    classification_ms = self.telemetry.stop_timer('classification')
                    
                    # Se detectou legenda com alta confiança, early exit
                    if result.has_subtitles and result.confidence >= 0.85:
                        ocr_time_ms = self.telemetry.stop_timer('ocr')
                        total_ms = self.telemetry.stop_timer('total')
                        elapsed_ms = (time.time() - start_time) * 1000
                        
                        # Sprint 07: Record telemetry
                        video_id = Path(video_path).stem
                        metrics = PerformanceMetrics(
                            total_time_ms=total_ms,
                            frame_extraction_ms=frame_extraction_ms,
                            ocr_time_ms=ocr_time_ms,
                            tracking_time_ms=0.0,
                            classification_time_ms=classification_ms,
                            frames_analyzed=frames_analyzed,
                            tracks_created=len(partial_tracks),
                            lines_detected=total_lines_detected
                        )
                        
                        self.telemetry.record_decision(
                            video_id=video_id,
                            decision='block',
                            confidence=result.confidence,
                            reason=result.reason,
                            method='TRSD',
                            metrics=metrics,
                            tracks_by_category=result.tracks_by_category,
                            decision_logic=result.decision_logic,
                            early_exit=True,
                            debug_info={'extraction_method': extraction_result.method}
                        )
                        
                        # Save debug artifacts
                        self.debug_saver.save_detection_artifacts(
                            video_id, extraction_result.frames, partial_tracks, result, metrics
                        )
                        
                        logger.warning(
                            f"⚠️ TRSD EARLY EXIT: Detected subtitles @ frame {frame_idx} "
                            f"(conf={result.confidence:.2f}, {elapsed_ms:.0f}ms)"
                        )
                        
                        return (
                            result.has_subtitles,
                            result.confidence,
                            result.reason,
                            {
                                'method': 'TRSD',
                                'early_exit': True,
                                'frames_analyzed': frames_analyzed,
                                'tracks': len(result.subtitle_tracks)
                            }
                        )
            
            # Note: No VideoCapture to release - using frame extractor
            ocr_time_ms = self.telemetry.stop_timer('ocr')
            final_tracks = tracker.finalize()
            
            # Classificar resultado final
            self.telemetry.start_timer('classification')
            result = self.classifier.decide(final_tracks)
            classification_ms = self.telemetry.stop_timer('classification')
            
            total_ms = self.telemetry.stop_timer('total')
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Sprint 07: Record telemetry
            video_id = Path(video_path).stem
            metrics = PerformanceMetrics(
                total_time_ms=total_ms,
                frame_extraction_ms=frame_extraction_ms,
                ocr_time_ms=ocr_time_ms,
                tracking_time_ms=0.0,
                classification_time_ms=classification_ms,
                frames_analyzed=frames_analyzed,
                tracks_created=len(final_tracks),
                lines_detected=total_lines_detected
            )
            
            self.telemetry.record_decision(
                video_id=video_id,
                decision='block' if result.has_subtitles else 'approve',
                confidence=result.confidence,
                reason=result.reason,
                method='TRSD',
                metrics=metrics,
                tracks_by_category=result.tracks_by_category,
                decision_logic=result.decision_logic,
                early_exit=False,
                debug_info={'extraction_method': extraction_result.method}
            )
            
            # Save debug artifacts
            self.debug_saver.save_detection_artifacts(
                video_id, extraction_result.frames, final_tracks, result, metrics
            )
            
            logger.info(
                f"{'⚠️' if result.has_subtitles else '✅'} TRSD: {result.reason} "
                f"(conf={result.confidence:.2f}, {frames_analyzed} frames, {elapsed_ms:.0f}ms)"
            )
            
            return (
                result.has_subtitles,
                result.confidence,
                result.reason,
                {
                    'method': 'TRSD',
                    'early_exit': False,
                    'frames_analyzed': frames_analyzed,
                    'tracks_by_category': result.tracks_by_category
                }
            )
        
        except Exception as e:
            logger.error(f"TRSD detection failed: {e}", exc_info=True)
            # Reraise para fallback
            raise
    
    def has_embedded_subtitles(self, video_path: str, timeout: int = 60) -> Tuple[bool, float, str]:
        """
        Detecta legendas embutidas no vídeo usando TRSD (se habilitado) ou OCR legado
        
        Sprint 04: Integração TRSD com fallback
        - Se TRSD_ENABLED=true: usa detector inteligente
        - Se falhar ou desabil itado: fallback para OCR legado
        
        Estratégia TRSD:
        1. TextRegionExtractor: detecta texto por ROI
        2. TemporalTracker: rastreia texto entre frames
        3. SubtitleClassifier: classifica como legenda ou estático
        4. Early exit em 10-15 frames se detectar legenda clara
        
        Estratégia OCR Legado:
        1. Analisa N frames por segundo (configurável, padrão: 6fps)
        2. Early exit: para na primeira detecção com confiança > threshold
        3. Limite máximo de frames para evitar OOM (padrão: 240 frames)
        4. Full frame OCR (ROI removido)
        5. Transcoding automático para codecs não suportados (AV1)
        
        Args:
            video_path: Path do vídeo
            timeout: Timeout em segundos
        
        Returns:
            Tuple (has_subtitles, confidence, sample_text)
        """
        # Sprint 04: Tentar TRSD primeiro (se habilitado)
        if self.trsd_enabled:
            try:
                logger.info(f"🔍 Attempting TRSD detection: {video_path}")
                has_subs, conf, reason, debug_info = self._detect_with_trsd(video_path, timeout)
                logger.info(f"✅ TRSD detection completed: {reason}")
                return (has_subs, conf, reason)
            
            except Exception as e:
                logger.warning(f"⚠️ TRSD detection failed, falling back to legacy: {e}")
                # Continue para método legado
        
        # Método legado (ou fallback)
        return self._detect_with_legacy_ocr(video_path, timeout)
    
    def _detect_with_legacy_ocr(self, video_path: str, timeout: int = 60) -> Tuple[bool, float, str]:
        """
        Detecção legada com OCR (método original)
        
        Sprint 04: Refatorado para ser fallback do TRSD
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
                    
                    # Armazenar TODAS as detecções (não só as de alta confiança)
                    detections.append((text, confidence, ts))
                    logger.debug(f"OCR @ {ts:.1f}s (conf={confidence:.2f}): {text[:50]}")
            
            # 📊 NOVA ESTRATÉGIA: Densidade de detecção
            # Se detectou texto em muitos frames, provavelmente é legenda
            detection_density = len(detections) / max(frames_analyzed, 1)
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            if not detections:
                logger.info(f"✅ No embedded subtitles detected (analyzed {frames_analyzed} frames, {elapsed_ms:.0f}ms)")
                return False, 0.0, ""
            
            # Calcular confiança média das detecções
            avg_confidence = sum(conf for _, conf, _ in detections) / len(detections)
            
            # 🖥️ DETECTOR DE SCREENCAST/CÓDIGO
            # Detecta vídeos de IDE/terminal/código que têm texto técnico em todos os frames
            if detection_density > 0.80 and len(detections) >= 10:
                # Contar palavras técnicas típicas de código/IDE
                all_text = " ".join(text for text, _, _ in detections)
                tech_patterns = [
                    r'\bexplorer\b', r'\bmanager\b', r'\beditor\b', r'\bstorage\b',
                    r'\bmain\b', r'\bsrc\b', r'\bpath\b', r'\bproject\b',
                    r'\.ts\b', r'\.js\b', r'\.py\b', r'U\s*\|', r'>\s*>', 
                    r'\bselection\b', r'\bview\b', r'\bedit\b'
                ]
                
                tech_matches = sum(len(re.findall(pattern, all_text, re.IGNORECASE)) for pattern in tech_patterns)
                tech_score = tech_matches / len(detections)  # Matches por detection
                
                if tech_score > 0.5:  # Se >50% das detecções têm padrões técnicos
                    best_text, best_conf, best_ts = max(detections, key=lambda x: x[1])
                    logger.warning(
                        f"⚠️ SCREENCAST/CODE detected (density={detection_density:.1%}, "
                        f"{len(detections)} detections, tech_score={tech_score:.2f})\n"
                        f"Sample text: {all_text[:80]}"
                    )
                    return True, 0.50, f"Screencast/Code (tech_score={tech_score:.2f})"
            
            # 🎯 CRITÉRIOS COMBINADOS para detecção por densidade:
            # 1. Densidade > 30% (texto em pelo menos 30% dos frames)
            # 2. Pelo menos 5 detecções (evita ruído pontual)
            # 3. Confiança média >= 0.30 (pelo menos algumas detecções razoáveis)
            should_block_by_density = (
                detection_density > 0.30 and
                len(detections) >= 5 and
                avg_confidence >= 0.30
            )
            
            if should_block_by_density:
                best_text, best_conf, best_ts = max(detections, key=lambda x: x[1])
                logger.warning(
                    f"⚠️ EMBEDDED SUBTITLES detected by DENSITY (density={detection_density:.1%}, "
                    f"{len(detections)} detections, avg_conf={avg_confidence:.2f}, best_conf={best_conf:.2f})\n"
                    f"Sample text: {best_text[:80]}"
                )
                return True, best_conf, best_text
            
            # Retornar melhor detecção mesmo que abaixo do threshold
            best_text, best_conf, best_ts = max(detections, key=lambda x: x[1])
            logger.info(
                f"✅ Low confidence OCR (conf={best_conf:.2f} < {self.min_confidence}, "
                f"density={detection_density:.1%}, analyzed {frames_analyzed} frames, {elapsed_ms:.0f}ms)"
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
        
        IMPROVED: Filtra ruídos visuais detectando apenas legendas legíveis reais
        
        Features:
        - Valid words (3+ alphanum chars)
        - Low special character density
        - No excessive special char sequences
        - Reasonable text length
        - Portuguese/English letters present
        
        Returns:
            Confidence score 0-1
        """
        if not text or len(text) < 3:
            return 0.0
        
        # 🚫 FILTER 1: Excesso de caracteres especiais (>60% = ruído visual)
        special_chars = sum(not c.isalnum() and not c.isspace() for c in text)
        special_ratio = special_chars / len(text)
        if special_ratio > 0.6:
            return 0.0
        
        # 🚫 FILTER 2: Sequências longas de caracteres especiais (ruído visual típico)
        # Ex: "=—|" "===" "---" são ruídos, não legendas
        import re
        special_sequences = re.findall(r'[^a-zA-Z0-9\s]{3,}', text)
        if len(special_sequences) > 2:
            return 0.0
        
        # 🚫 FILTER 3: Verificar se há pelo menos 2 palavras legíveis (4+ letras consecutivas)
        # Ex: "este texto" = válido, "oi la" = inválido
        words = text.split()
        valid_words = [w for w in words if re.search(r'[a-zA-Z]{4,}', w)]
        if len(valid_words) < 2:
            return 0.0
        
        # ✅ SCORING: Texto passou pelos filtros, calcular confiança
        confidence = 0.0
        
        # Feature 1: Palavras válidas (max 0.40)
        valid_word_ratio = len(valid_words) / max(len(words), 1)
        confidence += valid_word_ratio * 0.40
        
        # Feature 2: Baixa densidade de caracteres especiais (max 0.30)
        # Inverso: menos especiais = mais confiança
        clean_ratio = 1.0 - special_ratio
        confidence += clean_ratio * 0.30
        
        # Feature 3: Comprimento razoável (max 0.30)
        # Legendas típicas: 10-100 caracteres
        len_score = 0.0
        if 10 <= len(text) <= 100:
            len_score = 1.0
        elif len(text) < 10:
            len_score = len(text) / 10.0
        else:  # > 100
            len_score = max(0.3, 1.0 - (len(text) - 100) / 200.0)
        confidence += len_score * 0.30
        
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

