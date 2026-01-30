"""
Video Processor Pipeline

Orquestra o processamento completo de vídeo:
1. Validação de integridade
2. Extração de áudio
3. Detecção OCR
4. Decisão de blacklist
"""

import logging
import os
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from app.video_validator import validate_video_integrity, get_video_info, VideoIntegrityError
from app.audio_utils import extract_audio, get_audio_duration
from app.ocr_detector import OCRDetector, OCRResult
from app.blacklist_manager import BlacklistManager
from app.metrics import downloads_skipped_total

logger = logging.getLogger(__name__)


class ProcessingDecision(Enum):
    """Decisão de processamento"""
    PROCESS = "process"  # Processar normalmente
    SKIP_BLACKLISTED = "skip_blacklisted"  # Pular - está na blacklist
    SKIP_NO_AUDIO = "skip_no_audio"  # Pular - sem áudio
    SKIP_CORRUPTED = "skip_corrupted"  # Pular - vídeo corrompido
    SKIP_NO_SUBTITLES = "skip_no_subtitles"  # Pular - sem legendas detectadas


@dataclass
class ProcessingResult:
    """Resultado do processamento"""
    decision: ProcessingDecision
    video_id: str
    video_path: str
    audio_path: Optional[str] = None
    audio_duration: Optional[float] = None
    video_info: Optional[dict] = None
    ocr_result: Optional[OCRResult] = None
    error: Optional[str] = None
    blacklist_reason: Optional[str] = None


class VideoProcessor:
    """
    Pipeline de processamento de vídeo
    
    Integra validação, extração de áudio, OCR e decisão de blacklist
    """
    
    def __init__(
        self,
        blacklist_manager: BlacklistManager,
        ocr_detector: Optional[OCRDetector] = None,
        audio_timeout: int = 60,
        validation_timeout: int = 10,
        min_ocr_confidence: float = 60.0,
        storage_path: str = "/tmp"
    ):
        """
        Args:
            blacklist_manager: Gerenciador de blacklist
            ocr_detector: Detector OCR (opcional, criado se None)
            audio_timeout: Timeout para extração de áudio
            validation_timeout: Timeout para validação
            min_ocr_confidence: Confiança mínima OCR
            storage_path: Path para armazenar arquivos temporários
        """
        self.blacklist = blacklist_manager
        self.ocr = ocr_detector or OCRDetector()
        self.audio_timeout = audio_timeout
        self.validation_timeout = validation_timeout
        self.min_ocr_confidence = min_ocr_confidence
        self.storage_path = storage_path
        
        logger.info(
            f"VideoProcessor initialized "
            f"(audio_timeout={audio_timeout}s, "
            f"validation_timeout={validation_timeout}s, "
            f"min_ocr_conf={min_ocr_confidence})"
        )
    
    def process_video(
        self,
        video_id: str,
        video_path: str,
        check_ocr: bool = True
    ) -> ProcessingResult:
        """
        Processa vídeo completo através do pipeline
        
        Args:
            video_id: ID do vídeo (YouTube video ID)
            video_path: Path do arquivo de vídeo
            check_ocr: Se True, verifica presença de legendas com OCR
        
        Returns:
            ProcessingResult com decisão e dados
        """
        logger.info(f"🎬 Processing video: {video_id}")
        
        # Step 1: Verificar blacklist
        if self.blacklist.is_blacklisted(video_id):
            info = self.blacklist.get_blacklist_info(video_id)
            reason = info.get('reason', 'unknown') if info else 'unknown'
            
            logger.info(f"⏭️ Skipping blacklisted video: {video_id} (reason: {reason})")
            downloads_skipped_total.labels(reason="blacklisted").inc()
            
            return ProcessingResult(
                decision=ProcessingDecision.SKIP_BLACKLISTED,
                video_id=video_id,
                video_path=video_path,
                blacklist_reason=reason
            )
        
        # Step 2: Validar integridade do vídeo
        try:
            validate_video_integrity(video_path, timeout=self.validation_timeout)
            video_info = get_video_info(video_path)
        except VideoIntegrityError as e:
            logger.error(f"❌ Video integrity check failed: {video_id} - {e}")
            
            # Adicionar à blacklist
            self.blacklist.add_to_blacklist(
                video_id,
                reason="corrupted",
                metadata={"error": str(e)}
            )
            
            downloads_skipped_total.labels(reason="corrupted").inc()
            
            return ProcessingResult(
                decision=ProcessingDecision.SKIP_CORRUPTED,
                video_id=video_id,
                video_path=video_path,
                error=str(e),
                blacklist_reason="corrupted"
            )
        except Exception as e:
            logger.error(f"❌ Unexpected error validating video: {video_id} - {e}")
            return ProcessingResult(
                decision=ProcessingDecision.SKIP_CORRUPTED,
                video_id=video_id,
                video_path=video_path,
                error=str(e)
            )
        
        # Step 3: Extrair áudio
        audio_path = os.path.join(self.storage_path, f"{video_id}_audio.wav")
        
        # Limpar arquivo existente se houver
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.debug(f"Removed existing audio file: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to remove existing audio: {e}")
        
        try:
            extract_audio(video_path, audio_path, timeout=self.audio_timeout)
            audio_duration = get_audio_duration(audio_path)
            
            logger.info(f"✅ Audio extracted: {audio_path} ({audio_duration:.1f}s)")
        
        except Exception as e:
            logger.error(f"❌ Audio extraction failed: {video_id} - {e}")
            
            # Adicionar à blacklist
            self.blacklist.add_to_blacklist(
                video_id,
                reason="no_audio",
                metadata={"error": str(e)}
            )
            
            downloads_skipped_total.labels(reason="no_audio").inc()
            
            return ProcessingResult(
                decision=ProcessingDecision.SKIP_NO_AUDIO,
                video_id=video_id,
                video_path=video_path,
                video_info=video_info,
                error=str(e),
                blacklist_reason="no_audio"
            )
        
        # Step 4: Verificar presença de legendas com OCR (opcional)
        ocr_result = None
        if check_ocr:
            try:
                ocr_result = self._check_subtitles_presence(video_path, video_info)
                
                if not ocr_result.has_subtitle:
                    logger.warning(
                        f"⚠️ No subtitles detected via OCR: {video_id} "
                        f"(confidence={ocr_result.confidence:.1f}, words={ocr_result.word_count})"
                    )
                    
                    # Adicionar à blacklist
                    self.blacklist.add_to_blacklist(
                        video_id,
                        reason="no_subtitles",
                        metadata={
                            "ocr_confidence": f"{ocr_result.confidence:.1f}",
                            "word_count": str(ocr_result.word_count)
                        }
                    )
                    
                    downloads_skipped_total.labels(reason="no_subtitles").inc()
                    
                    # Limpar áudio extraído
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                    
                    return ProcessingResult(
                        decision=ProcessingDecision.SKIP_NO_SUBTITLES,
                        video_id=video_id,
                        video_path=video_path,
                        video_info=video_info,
                        ocr_result=ocr_result,
                        blacklist_reason="no_subtitles"
                    )
                
                logger.info(
                    f"✅ Subtitles detected: {video_id} "
                    f"(confidence={ocr_result.confidence:.1f}, words={ocr_result.word_count})"
                )
            
            except Exception as e:
                logger.error(f"❌ OCR check failed: {video_id} - {e}")
                # Não bloqueia o processamento se OCR falhar
        
        # Step 5: Decisão final - processar vídeo
        logger.info(f"✅ Video ready for processing: {video_id}")
        
        return ProcessingResult(
            decision=ProcessingDecision.PROCESS,
            video_id=video_id,
            video_path=video_path,
            audio_path=audio_path,
            audio_duration=audio_duration,
            video_info=video_info,
            ocr_result=ocr_result
        )
    
    def _check_subtitles_presence(
        self,
        video_path: str,
        video_info: dict
    ) -> OCRResult:
        """
        Verifica presença de legendas via OCR
        
        Extrai frame no meio do vídeo e detecta legendas
        
        Args:
            video_path: Path do vídeo
            video_info: Informações do vídeo (duration)
        
        Returns:
            OCRResult com detecção
        """
        # Extrair frame no meio do vídeo
        duration = video_info.get('duration', 60)
        
        # Validação: duration deve ser > 0
        if duration <= 0:
            logger.warning(f"Invalid duration: {duration}, using default 60s")
            duration = 60
        
        mid_timestamp = duration / 2
        
        frame = self.ocr.extract_frame_at_timestamp(video_path, mid_timestamp)
        
        if frame is None:
            logger.warning(f"Failed to extract frame at {mid_timestamp}s")
            # Retornar resultado vazio
            from app.ocr_detector import OCRResult
            return OCRResult(text="", confidence=0.0, word_count=0, has_subtitle=False)
        
        # Detectar legenda
        result = self.ocr.detect_subtitle_in_frame(
            frame,
            min_confidence=self.min_ocr_confidence
        )
        
        return result
    
    def cleanup_audio(self, audio_path: str):
        """
        Remove arquivo de áudio temporário
        
        Args:
            audio_path: Path do arquivo de áudio
        """
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                logger.debug(f"Cleaned up audio: {audio_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup audio {audio_path}: {e}")
