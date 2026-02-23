"""
Video Validator com OCR e TRSD

Valida integridade de vídeo e detecta legendas embutidas usando OCR + TRSD
ATUALIZADO: Multi-Engine OCR (PaddleOCR + Tesseract) + Visual Features
"""

import subprocess
import json
import logging
import time
import cv2
import os
import re
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional, Dict, Any, List
from pathlib import Path

# TRSD imports (Sprint 04)
from app.subtitle_processing.subtitle_detector import TextRegionExtractor
from app.subtitle_processing.temporal_tracker import TemporalTracker
from app.subtitle_processing.subtitle_classifier_v2 import SubtitleClassifierV2  # Sprint 08 - Reescrito para 90%+ precisão
from .frame_extractor import FFmpegFrameExtractor  # Sprint 05
from app.infrastructure.telemetry import TRSDTelemetry, DebugArtifactSaver, PerformanceMetrics  # Sprint 07
from app.core.config import Settings

# PaddleOCR + Visual Features
from .ocr_detector_advanced import get_ocr_detector, PaddleOCRDetector
from .visual_features import VisualFeaturesAnalyzer

logger = logging.getLogger(__name__)


def _get_ocr_gpu_setting() -> bool:
    """
    Retorna configuração de GPU para OCR a partir do ambiente.
    
    Returns:
        True se OCR_USE_GPU=true (case-insensitive), False caso contrário
    """
    gpu_env = os.getenv('OCR_USE_GPU', 'false').lower().strip()
    use_gpu = gpu_env in ('true', '1', 'yes', 'on')
    
    if use_gpu:
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            if not cuda_available:
                logger.warning("⚠️ OCR_USE_GPU=true mas CUDA não disponível. Usando CPU.")
                return False
            return True
        except ImportError:
            logger.warning("⚠️ PyTorch não instalado. Usando CPU.")
            return False
    
    return False


class VideoIntegrityError(Exception):
    """Exceção para vídeos corrompidos ou inválidos"""
    pass


class VideoValidator:
    """
    Valida vídeos e detecta legendas embutidas usando PaddleOCR + Visual Features
    
    ATUALIZADO: Migrado de EasyOCR para PaddleOCR (single engine)
    NOVA FEATURE: Análise de features visuais para reduzir falsos positivos
    
    - Validates video integrity (ffprobe + frame decode)
    - Detects embedded subtitles using PaddleOCR
    - Analyzes visual features (position, contrast, size, aspect ratio)
    - Samples multiple frames (start, middle, end)
    - Confidence scoring combining OCR + Visual features
    """
    
    def __init__(self, min_confidence: float = 0.15, frames_per_second: int = None, max_frames: int = None, redis_store: Optional[Any] = None):
        """
        🚨 FORÇA BRUTA 100% FRAMES - ZERO TOLERÂNCIA
        
        Args:
            min_confidence: Confiança mínima para detectar texto (padrão: 0.15 = ultra sensível)
            frames_per_second: IGNORADO - processa 100% dos frames
            max_frames: IGNORADO - processa 100% dos frames
            redis_store: Optional RedisJobStore for cache
        """
        self.min_confidence = min_confidence
        self.frames_per_second = None  # FORÇA BRUTA: processar TODOS
        self.max_frames = None  # FORÇA BRUTA: processar TODOS
        self.redis_store = redis_store
        
        # P2 Optimization: Lock para thread-safe operations
        self._ocr_lock = threading.Lock()
        
        # Determinar se usar GPU (via variável de ambiente)
        use_gpu = _get_ocr_gpu_setting()
        mode = "GPU" if use_gpu else "CPU"
        
        # PaddleOCR Detector (singleton)
        logger.info(f"Initializing PaddleOCR system ({mode})...")
        self.ocr_detector = get_ocr_detector()  # Singleton PaddleOCR
        self.use_gpu = use_gpu
        
        # Visual Features Analyzer
        self.visual_analyzer = VisualFeaturesAnalyzer()
        logger.info("✅ Visual Features Analyzer initialized")
        
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
                base_dir='data/logs/debug/artifacts'
            )
            logger.info("TRSD enabled - using intelligent temporal detection")
        else:
            logger.info("TRSD disabled - using legacy OCR detection")
        
        logger.info(
            f"VideoValidator initialized - 🚨 FORÇA BRUTA 100% FRAMES "
            f"(min_confidence={min_confidence}, ZERO sampling, ZERO limits)"
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
    
    def has_embedded_subtitles(self, video_path: str, timeout: int = 300, force_revalidation: bool = False) -> Tuple[bool, float, str, int]:
        """
        Detecta legendas embutidas no vídeo usando TRSD (se habilitado) ou OCR legado
        
        🚨 FORÇA BRUTA 100% FRAMES quando force_revalidation=True
        
        Args:
            video_path: Path do vídeo
            timeout: Timeout em segundos (aumentado para 300s para processar 100% frames)
            force_revalidation: Se True, IGNORA cache e força validação 100% frames
        
        Returns:
            Tuple (has_subtitles, confidence, sample_text, frames_processed)
        """
        # 🚨 REVALIDAÇÃO: Ignorar cache completamente
        if not force_revalidation:
            # ===== Cache apenas quando NÃO for revalidação =====
            cached_result = self._check_cache(video_path)
            if cached_result is not None:
                logger.info(f"✅ Cache hit: {video_path}")
                # Cache pode ter 3 ou 4 valores, compatibilidade
                if len(cached_result) == 3:
                    return cached_result + (-1,)  # -1 indica cache (frames desconhecidos)
                return cached_result
        else:
            logger.info(f"🚨 REVALIDAÇÃO FORÇADA: Ignorando cache, processando 100% frames")
        
        # Sprint 04: Tentar TRSD primeiro (se habilitado)
        if self.trsd_enabled:
            try:
                logger.info(f"🔍 Attempting TRSD detection: {video_path}")
                has_subs, conf, reason, debug_info = self._detect_with_trsd(video_path, timeout)
                logger.info(f"✅ TRSD detection completed: {reason}")
                
                result = (has_subs, conf, reason, -1)  # -1 = frames não aplicável para TRSD
                
                # Salvar em cache apenas se NÃO for revalidação
                if not force_revalidation:
                    self._save_cache(video_path, result)
                
                return result
            
            except Exception as e:
                logger.warning(f"⚠️ TRSD detection failed, falling back to legacy: {e}")
                # Continue para método legado
        
        # Método legado (ou fallback)
        result = self._detect_with_legacy_ocr(video_path, timeout)
        
        # Salvar em cache apenas se NÃO for revalidação
        if not force_revalidation:
            self._save_cache(video_path, result)
        
        return result
    
    def _process_single_frame(self, working_path: str, ts: float) -> Optional[Tuple[str, float, float]]:
        """
        Processa um frame individual e retorna resultado OCR + Visual Features
        
        ATUALIZADO: PaddleOCR + Visual Analysis
        P2 Optimization: Thread-safe para processamento paralelo
        
        Args:
            working_path: Caminho do vídeo
            ts: Timestamp do frame
        
        Returns:
            Tuple (text, combined_confidence, timestamp) se encontrou texto, None caso contrário
            combined_confidence: Score combinado de OCR (0-1) + Visual Features (0-100)
        """
        frame = self._extract_frame(working_path, ts)
        if frame is None:
            return None
        
        # PaddleOCR detection (thread-safe com lock interno)
        with self._ocr_lock:
            ocr_results = self.ocr_detector.detect_text(frame)
        
        # Unificar textos detectados
        all_texts = []
        max_ocr_conf = 0.0
        
        for result in ocr_results:
            if result.text.strip():
                all_texts.append(result.text)
                max_ocr_conf = max(max_ocr_conf, result.confidence)
        
        text = ' '.join(all_texts).strip()
        
        if not text:
            return None
        
        # Analisar features visuais para validar se é realmente legenda
        visual_score = 0.0
        try:
            visual_analysis = self.visual_analyzer.analyze_frame_with_text(frame, text)
            visual_score = visual_analysis.get('subtitle_score', 0.0) / 100.0  # Normalizar 0-100 → 0-1
        except Exception as e:
            logger.warning(f"⚠️ Visual analysis failed for frame @ {ts:.1f}s: {e}")
        
        # Combinar confiança: OCR (peso 0.6) + Visual Features (peso 0.4)
        combined_confidence = (max_ocr_conf * 0.6) + (visual_score * 0.4)
        
        return (text, combined_confidence, ts)
    
    def _detect_with_legacy_ocr(self, video_path: str, timeout: int = 300) -> Tuple[bool, float, str]:
        """
        🚨 FORÇA BRUTA 100% FRAMES - ZERO TOLERÂNCIA
        
        Processa TODOS os frames do vídeo sequencialmente.
        UMA LETRA DETECTADA = BAN IMEDIATO
        
        Args:
            video_path: Caminho do vídeo
            timeout: Timeout em segundos (aumentado para 300s para processar 100% frames)
        
        Returns:
            Tuple (has_subtitles, confidence, text)
        """
        start_time = time.time()
        working_path = video_path
        cleanup_path = None
        
        try:
            # Converter para codec suportado se necessário (ex.: AV1 → H.264)
            working_path, cleanup_path = self._ensure_supported_codec(video_path)
            
            # Abrir vídeo com OpenCV
            cap = cv2.VideoCapture(working_path)
            if not cap.isOpened():
                raise VideoIntegrityError(f"Cannot open video: {working_path}")
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            
            logger.info(
                f"🚨 FORÇA BRUTA: Processando 100% dos frames: {total_frames} frames "
                f"({fps:.2f} fps, {duration:.1f}s) - ZERO tolerância"
            )
            
            frames_analyzed = 0
            all_detections = []
            first_text_detected = None
            
            # 🚨 PROCESSAR TODOS OS FRAMES SEQUENCIALMENTE
            while True:
                ret, frame = cap.read()
                if not ret:
                    break  # Fim do vídeo
                
                frames_analyzed += 1
                
                # Log progresso a cada 100 frames
                if frames_analyzed % 100 == 0:
                    logger.debug(f"   Processando frame {frames_analyzed}/{total_frames}...")
                
                # OCR no frame completo
                try:
                    with self._ocr_lock:
                        ocr_results = self.ocr_detector.detect_text(frame)
                    
                    # Verificar se encontrou texto
                    if ocr_results:
                        all_texts = []
                        max_conf = 0.0
                        
                        for result in ocr_results:
                            if result.text.strip():
                                all_texts.append(result.text)
                                max_conf = max(max_conf, result.confidence)
                        
                        if all_texts:
                            text = ' '.join(all_texts).strip()
                            timestamp = frames_analyzed / fps if fps > 0 else frames_analyzed
                            
                            all_detections.append((text, max_conf, timestamp))
                            
                            # 🚨 PRIMEIRA DETECÇÃO = GUARDAR PARA RETORNO
                            if first_text_detected is None and max_conf >= self.min_confidence:
                                first_text_detected = (text, max_conf, timestamp)
                                logger.warning(
                                    f"🚨 TEXTO DETECTADO no frame {frames_analyzed}/{total_frames} "
                                    f"(ts={timestamp:.1f}s, conf={max_conf:.2f}): {text[:80]}"
                                )
                
                except Exception as e:
                    # Ignorar erros de frame individual
                    logger.debug(f"Erro no frame {frames_analyzed}: {e}")
                    continue
            
            cap.release()
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # 🚨 ZERO TOLERÂNCIA: SE DETECTOU QUALQUER TEXTO ACIMA DO THRESHOLD = BAN
            if first_text_detected:
                text, conf, ts = first_text_detected
                logger.error(
                    f"🚨 EMBEDDED SUBTITLES DETECTED - BAN IMEDIATO!\n"
                    f"   Frames analisados: {frames_analyzed}/{total_frames} (100%)\n"
                    f"   Total detecções: {len(all_detections)}\n"
                    f"   Primeira detecção: frame @ {ts:.1f}s (conf={conf:.2f})\n"
                    f"   Texto: {text[:100]}\n"
                    f"   Tempo: {elapsed_ms:.0f}ms"
                )
                return True, conf, text, frames_analyzed
            
            # Se não encontrou texto acima do threshold
            logger.info(
                f"✅ Vídeo APROVADO - Nenhum texto detectado\n"
                f"   Frames analisados: {frames_analyzed}/{total_frames} (100%)\n"
                f"   Detecções baixa confiança: {len(all_detections)}\n"
                f"   Tempo: {elapsed_ms:.0f}ms"
            )
            return False, 0.0, "", frames_analyzed
            
        except Exception as e:
            logger.error(f"❌ OCR detection error: {e}", exc_info=True)
            return False, 0.0, f"Error: {e}", 0
        
        finally:
            # Limpar arquivo transcodado temporário, se criado
            if cleanup_path:
                try:
                    Path(cleanup_path).unlink(missing_ok=True)
                except Exception:
                    logger.debug(f"Could not remove temp transcoded file: {cleanup_path}")
    
    def _get_all_frame_indices(self, video_path: str) -> list:
        """
        🚨 FORÇA BRUTA: Retorna TODOS os índices de frames do vídeo
        
        ZERO SAMPLING, ZERO LIMITS - processa 100% dos frames
        
        Args:
            video_path: Caminho do vídeo
        
        Returns:
            Lista com TODOS os índices de frames [0, 1, 2, ..., total_frames-1]
        """
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        
        # Retornar TODOS os frames, sem limite
        all_indices = list(range(total_frames))
        
        duration = total_frames / fps if fps > 0 else 0
        
        logger.info(
            f"🚨 FORÇA BRUTA: Processando 100% dos frames: {total_frames} frames "
            f"({fps:.2f} fps, {duration:.1f}s video) - ZERO sampling"
        )
        
        return all_indices
    
    def _extract_frame(self, video_path: str, timestamp: float, timeout: int = 3) -> Optional[any]:
        """
        Extrai um frame do vídeo em determinado timestamp
        
        🔧 FIX: Thread-safe extraction (removed signal.alarm - not compatible with ThreadPoolExecutor)
        - Fallback para FFmpeg se OpenCV falhar
        - Early failure detection
        
        Returns:
            numpy array (BGR) ou None se falhar
        """
        import tempfile
        
        # Try OpenCV first (without signal timeout - not thread-safe)
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                logger.warning(f"OpenCV failed to open video: {video_path}")
                # Try FFmpeg fallback
                return self._extract_frame_ffmpeg(video_path, timestamp)
            
            # Seek to timestamp
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                logger.debug(f"Failed to extract frame at {timestamp}s - trying FFmpeg")
                return self._extract_frame_ffmpeg(video_path, timestamp)
            
            return frame
        
        except Exception as e:
            logger.error(f"Frame extraction error at {timestamp}s: {e}")
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
    
    # ===== P2 Optimization: Cache Methods =====
    
    def _check_cache(self, video_path: str) -> Optional[Tuple[bool, float, str]]:
        """
        Verifica cache de validação de legendas no Redis
        
        P2 Optimization: Evita reprocessamento do mesmo vídeo
        - Hash do video_path como chave
        - TTL de 7 dias
        
        Args:
            video_path: Caminho do vídeo
        
        Returns:
            Tuple (has_subtitles, confidence, reason) se encontrado, None caso contrário
        """
        if not self.redis_store:
            return None
        
        try:
            # Gerar hash do video_path
            cache_key = f"subtitle_detection:{hashlib.sha256(video_path.encode()).hexdigest()}"
            
            # Verificar no Redis
            cached_data = self.redis_store.redis.get(cache_key)
            if cached_data:
                result = json.loads(cached_data)
                logger.debug(f"✅ Cache hit: {video_path} -> {result}")
                return (result['has_subtitles'], result['confidence'], result['reason'])
            
            return None
        
        except Exception as e:
            logger.warning(f"⚠️ Cache check failed: {e}")
            return None
    
    def _save_cache(self, video_path: str, result: Tuple[bool, float, str]) -> None:
        """
        Salva resultado de detecção no cache Redis
        
        P2 Optimization: Cache com TTL de 7 dias
        
        Args:
            video_path: Caminho do vídeo
            result: Tuple (has_subtitles, confidence, reason)
        """
        if not self.redis_store:
            return
        
        try:
            # Gerar hash do video_path
            cache_key = f"subtitle_detection:{hashlib.sha256(video_path.encode()).hexdigest()}"
            
            # Preparar dados
            has_subtitles, confidence, reason = result
            cache_data = {
                'has_subtitles': has_subtitles,
                'confidence': confidence,
                'reason': reason,
                'video_path': video_path,  # Para debugging
                'cached_at': time.time()
            }
            
            # Salvar com TTL de 7 dias
            ttl_seconds = 7 * 24 * 60 * 60
            self.redis_store.redis.setex(
                cache_key,
                ttl_seconds,
                json.dumps(cache_data)
            )
            
            logger.debug(f"💾 Cache saved: {video_path} -> {result}")
        
        except Exception as e:
            logger.warning(f"⚠️ Cache save failed: {e}")

    def _ensure_supported_codec(self, video_path: str) -> Tuple[str, Optional[str]]:
        """
        Garante que o vídeo está em codec suportado para OCR (H.264).
        
        P1 Optimization: Converte AV1/VP9 → H.264 para evitar lentidão extrema
        - AV1: ~40min/vídeo → ~2min após conversão
        - VP9: ~15min/vídeo → ~2min após conversão
        - H.264: já otimizado, não converte
        
        - Se codec já suportado, retorna (video_path, None)
        - Se codec não suportado (ex.: AV1, VP9), transcodifica para H.264 temporário
        
        Returns:
            (working_path, cleanup_path)
        """
        info = self.get_video_info(video_path)
        codec = info.get('codec', '').lower()
        unsupported_codecs = {"av1", "av01", "vp9", "vp09"}  # P1: Include VP9 and variants
        
        if codec not in unsupported_codecs:
            return video_path, None
        
        # Transcodificar para H.264 para evitar travamentos do OpenCV com AV1/VP9
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        logger.warning(
            f"🔄 [P1 Optimization] Transcoding unsupported codec ({codec}) to H.264 for OCR: {video_path} -> {temp_path}"
        )
        
        cmd = [
            'ffmpeg',
            '-y',
            '-i', video_path,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',  # P1: ultrafast instead of veryfast for faster conversion
            '-crf', '28',  # P1: Lower quality (higher CRF) for faster conversion
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

