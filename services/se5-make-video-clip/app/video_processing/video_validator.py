from __future__ import annotations

"""
Video Validator com OCR e TRSD

Valida integridade de vídeo e detecta legendas embutidas usando OCR + TRSD
"""

import subprocess
import json
import time
import cv2
import os
import re
import hashlib
import threading
from typing import Any
from pathlib import Path

from app.subtitle_processing.subtitle_detector import TextRegionExtractor
from app.subtitle_processing.subtitle_classifier_v2 import SubtitleClassifierV2
from .frame_extractor import FFmpegFrameExtractor, FrameExtractor
from app.infrastructure.telemetry import TRSDTelemetry, DebugArtifactSaver
from app.core.config import Settings
from .ocr_detector_advanced import get_ocr_detector
from .visual_features import VisualFeaturesAnalyzer
from .ocr_detectors import TRSDDetector, LegacyOCRDetector, VideoIntegrityError
from common.log_utils import get_logger

logger = get_logger(__name__)

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
    
    def __init__(self, min_confidence: float = 0.15, frames_per_second: int | None = None, max_frames: int | None = None, redis_store: Any = None) -> None:
        self.min_confidence = min_confidence
        self.frames_per_second = frames_per_second
        self.max_frames = max_frames
        self.redis_store = redis_store
        
        self._ocr_lock = threading.Lock()
        
        use_gpu = _get_ocr_gpu_setting()
        mode = "GPU" if use_gpu else "CPU"
        
        logger.info(f"Initializing PaddleOCR system ({mode})...")
        self.ocr_detector = get_ocr_detector()
        self.use_gpu = use_gpu
        
        self.visual_analyzer = VisualFeaturesAnalyzer()
        logger.info("Visual Features Analyzer initialized")
        
        self._frame_extractor = FrameExtractor()
        
        self.config = Settings()
        self.trsd_enabled = self.config.trsd_enabled
        
        if self.trsd_enabled:
            self.text_extractor = TextRegionExtractor(self.config)
            self.classifier = SubtitleClassifierV2(self.config, fps=frames_per_second or 3.0)
            self.trsd_frame_extractor = FFmpegFrameExtractor(self.config.trsd_downscale_width)
            self.telemetry = TRSDTelemetry(enabled=True)
            self.debug_saver = DebugArtifactSaver(
                enabled=self.config.trsd_save_debug_artifacts,
                base_dir='data/logs/debug/artifacts'
            )
            self._trsd_detector = TRSDDetector(
                config=self.config,
                text_extractor=self.text_extractor,
                classifier=self.classifier,
                frame_extractor=self.trsd_frame_extractor,
                telemetry=self.telemetry,
                debug_saver=self.debug_saver,
                get_video_info=self.get_video_info,
            )
            logger.info("TRSD enabled - using intelligent temporal detection")
        else:
            logger.info("TRSD disabled - using legacy OCR detection")
        
        self._legacy_detector = LegacyOCRDetector(
            ocr_detector=self.ocr_detector,
            visual_analyzer=self.visual_analyzer,
            ocr_lock=self._ocr_lock,
            min_confidence=self.min_confidence,
            frames_per_second=self.frames_per_second,
            max_frames=self.max_frames,
            ensure_supported_codec=self._ensure_supported_codec,
        )
        
        logger.info(
            f"VideoValidator initialized "
            f"(min_confidence={min_confidence})"
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
    
    def has_embedded_subtitles(self, video_path: str, timeout: int = 300, force_revalidation: bool = False) -> tuple[bool, float, str, int]:
        if not force_revalidation:
            cached_result = self._check_cache(video_path)
            if cached_result is not None:
                logger.info(f"Cache hit: {video_path}")
                if len(cached_result) == 3:
                    return cached_result + (-1,)
                return cached_result
        else:
            logger.info(f"REVALIDATION FORCED: Ignoring cache")
        
        if self.trsd_enabled:
            try:
                logger.info(f"Attempting TRSD detection: {video_path}")
                has_subs, conf, reason, debug_info = self._trsd_detector.detect(video_path, timeout)
                logger.info(f"TRSD detection completed: {reason}")
                
                result = (has_subs, conf, reason, -1)
                
                if not force_revalidation:
                    self._save_cache(video_path, result)
                
                return result
            
            except Exception as e:
                logger.warning(f"TRSD detection failed, falling back to legacy: {e}")
        
        result = self._legacy_detector.detect(video_path, timeout)
        
        if not force_revalidation:
            self._save_cache(video_path, result)
        
        return result
    
    def _process_single_frame(self, working_path: str, ts: float) -> tuple[str, float, float] | None:
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
        frame = self._frame_extractor.extract_frame(working_path, ts)
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
    
    # ===== P2 Optimization: Cache Methods =====
    
    def _check_cache(self, video_path: str) -> tuple[bool, float, str] | None:
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
    
    def _save_cache(self, video_path: str, result: tuple[bool, float, str]) -> None:
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

    def _ensure_supported_codec(self, video_path: str) -> tuple[str, str | None]:
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
    
    def _validate_metadata(self, video_path: str, timeout: int) -> dict[str, Any]:
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
    
    def _validate_frame_decode(self, video_path: str, timeout: int) -> None:
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
    
    def get_video_info(self, video_path: str, timeout: int = 5) -> dict[str, Any]:
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
        except (ValueError, ZeroDivisionError):
            fps = 0
        
        return {
            'duration': float(format_info.get('duration', 0)),
            'width': int(stream_info.get('width', 0)),
            'height': int(stream_info.get('height', 0)),
            'codec': stream_info.get('codec_name', 'unknown'),
            'fps': fps,
        }

