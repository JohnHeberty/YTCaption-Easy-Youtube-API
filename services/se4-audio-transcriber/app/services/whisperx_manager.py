"""
Gerenciador de modelos usando WhisperX.
WhisperX oferece timestamps word-level com forced alignment para precisão máxima.
"""
from __future__ import annotations

import gc
import logging
import time
import torch

from ..core.constants import WHISPERX_MODEL_SIZES
from pathlib import Path
from typing import Any

try:
    import whisperx
    WHISPERX_AVAILABLE = True
except ImportError:
    WHISPERX_AVAILABLE = False
    logging.warning("⚠️ whisperx não instalado. Instale com: pip install whisperx")

from ..domain.interfaces import IModelManager
from ..shared.exceptions import AudioTranscriptionException
from ..core.config import get_settings
from .device_manager import TorchDeviceManager
from common.log_utils import get_logger

logger = get_logger(__name__)

class WhisperXManager(IModelManager):
    """
    Gerencia ciclo de vida do modelo WhisperX.
    
    Características:
    - Word-level timestamps com forced alignment (mais preciso)
    - Detecção de speakers (diarization)
    - Timestamps perfeitos para lip-sync
    - ~20% mais lento que faster-whisper
    - Requer modelos de alignment adicionais
    """
    
    def __init__(self, model_dir: Path | None = None) -> None:
        """
        Args:
            model_dir: Diretório para armazenar modelos
        """
        if not WHISPERX_AVAILABLE:
            raise AudioTranscriptionException(
                "WhisperX não está instalado. "
                "Instale com: pip install whisperx"
            )
        
        self.settings = get_settings()
        self.model_dir = model_dir or Path(self.settings.get('whisper_download_root', './models'))
        self.model_name = self.settings.get('whisper_model', 'base')
        
        self.model: Any | None = None
        self.align_model: Any | None = None
        self.align_metadata: dict[str, Any] | None = None
        self.device: str | None = None
        self.compute_type: str | None = None
        self.is_loaded = False
        
        from ..core.constants import DEFAULT_MAX_RETRIES, DEFAULT_RETRY_BACKOFF_BASE

        # Configurações
        self.max_retries = int(self.settings.get('model_load_retries', DEFAULT_MAX_RETRIES))
        self.retry_backoff = float(self.settings.get('model_load_backoff', DEFAULT_RETRY_BACKOFF_BASE))

        # Device detection via IDeviceManager (DIP)
        self.device_mgr = TorchDeviceManager(
            preferred_device=self.settings.get('whisper_device', 'auto')
        )

    def load_model(self) -> None:
        """Carrega modelo WhisperX"""
        if self.is_loaded:
            logger.info(f"ℹ️ Modelo WhisperX '{self.model_name}' já está carregado")
            return
        
        logger.info(f"📦 Carregando WhisperX: {self.model_name}")
        
        # Detecta dispositivo via IDeviceManager (DIP)
        self.device = self.device_mgr.detect_device()
        
        # Define compute_type baseado no device
        if self.device == 'cuda':
            self.compute_type = "float16"
        else:
            self.compute_type = "int8"
        
        logger.info(f"🖥️ Device: {self.device.upper()}, Compute: {self.compute_type}")
        
        # Tenta carregar com retry
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Tentativa {attempt}/{self.max_retries}")
                
                # Carrega modelo de transcrição
                self.model = whisperx.load_model(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=str(self.model_dir)
                )
                
                self.is_loaded = True
                logger.info(f"✅ WhisperX {self.model_name} carregado no {self.device.upper()}")
                return
                
            except Exception as e:
                logger.error(f"❌ Tentativa {attempt} falhou: {e}")
                
                if attempt < self.max_retries:
                    wait_time = self.retry_backoff ** attempt
                    logger.info(f"⏳ Aguardando {wait_time}s antes de tentar novamente...")
                    time.sleep(wait_time)
                else:
                    raise AudioTranscriptionException(
                        f"Falha ao carregar WhisperX após {self.max_retries} tentativas: {e}"
                    )
    
    def _load_align_model(self, language_code: str) -> None:
        """Carrega modelo de alinhamento para um idioma específico"""
        try:
            logger.info(f"📦 Carregando modelo de alinhamento para: {language_code}")
            
            self.align_model, self.align_metadata = whisperx.load_align_model(
                language_code=language_code,
                device=self.device
            )
            
            logger.info(f"✅ Modelo de alinhamento carregado para {language_code}")
            
        except Exception as e:
            logger.warning(f"⚠️ Falha ao carregar modelo de alinhamento: {e}")
            logger.warning("   Continuando sem alinhamento preciso")
            self.align_model = None
            self.align_metadata = None
    
    def unload_model(self) -> dict[str, Any]:
        """Descarrega modelo da memória"""
        if not self.is_loaded or self.model is None:
            return {
                "success": True,
                "message": "Modelo já estava descarregado",
                "memory_freed": {"ram_mb": 0, "vram_mb": 0}
            }
        
        logger.warning(f"🔥 Descarregando WhisperX '{self.model_name}' do {self.device}")
        
        # Estimativa de memória
        ram_freed = WHISPERX_MODEL_SIZES.get(self.model_name, 200)
        
        # Limpa modelos
        del self.model
        self.model = None
        
        if self.align_model is not None:
            del self.align_model
            self.align_model = None
            self.align_metadata = None
        
        self.is_loaded = False
        
        # Força garbage collection
        gc.collect()
        
        # Limpa cache CUDA
        if self.device == 'cuda' and torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        ram_freed = WHISPERX_MODEL_SIZES.get(self.model_name, 200)
        
        logger.info(f"✅ WhisperX descarregado - RAM liberada: ~{ram_freed}MB")
        
        return {
            "success": True,
            "message": f"Modelo '{self.model_name}' descarregado com sucesso",
            "memory_freed": {"ram_mb": ram_freed, "vram_mb": 0}
        }
    
    def get_status(self) -> dict[str, Any]:
        """Retorna status atual do modelo"""
        return {
            "loaded": self.is_loaded,
            "model_name": self.model_name if self.is_loaded else None,
            "device": self.device if self.is_loaded else None,
            "engine": "whisperx",
            "align_model_loaded": self.align_model is not None
        }
    
    def _run_initial_transcription(self, audio: Any, language: str) -> dict[str, Any]:
        """Run WhisperX initial transcription pass."""
        transcribe_params: dict[str, Any] = {"audio": audio, "batch_size": 16}
        if language != "auto":
            transcribe_params["language"] = language
        return self.model.transcribe(**transcribe_params)

    def _apply_forced_alignment(
        self, result: dict[str, Any], audio: Any, detected_language: str,
    ) -> dict[str, Any]:
        """Apply forced alignment to improve timestamp precision."""
        if detected_language == "auto":
            return result
        try:
            if self.align_model is None or self.align_metadata is None:
                self._load_align_model(detected_language)
            if self.align_model is not None:
                logger.info("🔧 Aplicando forced alignment...")
                result = whisperx.align(
                    result["segments"],
                    self.align_model,
                    self.align_metadata,
                    audio,
                    self.device,
                    return_char_alignments=False,
                )
                logger.info("✅ Forced alignment aplicado")
        except Exception as e:
            logger.warning(f"⚠️ Erro no alignment, usando timestamps sem alinhamento: {e}")
        return result

    @staticmethod
    def _process_segments(result: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        """Extract and normalize segments from raw WhisperX output."""
        segments: list[dict[str, Any]] = []
        full_text = ""
        for segment in result.get("segments", []):
            words = []
            if "words" in segment:
                for word in segment["words"]:
                    words.append({
                        "word": word.get("word", ""),
                        "start": float(word.get("start", 0.0)),
                        "end": float(word.get("end", 0.0)),
                        "probability": float(word.get("score", 1.0)),
                    })
            segment_text = segment.get("text", "").strip()
            full_text += segment_text + " "
            segments.append({
                "id": segment.get("id", len(segments)),
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "text": segment_text,
                "words": words,
            })
        return full_text.strip(), segments

    def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        task: str = "transcribe"
    ) -> dict[str, Any]:
        """
        Transcreve áudio usando WhisperX com forced alignment.
        
        Args:
            audio_path: Caminho do arquivo de áudio
            language: Código do idioma (ISO 639-1) ou "auto"
            task: "transcribe" ou "translate"
        
        Returns:
            dict com:
                - success: bool
                - text: str (texto completo)
                - language: str (idioma detectado)
                - segments: list (segmentos com timestamps PRECISOS)
                - duration: float
        """
        if not self.is_loaded:
            logger.info("📦 Modelo não carregado, carregando agora...")
            self.load_model()
        
        logger.info(f"🎤 Transcrevendo com WhisperX: {audio_path.name} (lang={language}, task={task})")
        
        try:
            audio = whisperx.load_audio(str(audio_path))
            start_time = time.time()
            
            result = self._run_initial_transcription(audio, language)
            detected_language = result.get("language", language if language != "auto" else "en")
            result = self._apply_forced_alignment(result, audio, detected_language)
            
            transcription_time = time.time() - start_time
            full_text, segments = self._process_segments(result)
            duration = segments[-1]["end"] if segments else 0.0
            total_words = sum(len(s["words"]) for s in segments)
            
            logger.info(
                f"✅ WhisperX transcription: {len(segments)} segments, "
                f"{total_words} words, {duration:.1f}s (aligned timestamps)"
            )
            
            return {
                "success": True,
                "text": full_text,
                "language": detected_language,
                "segments": segments,
                "duration": duration,
                "transcription_time": transcription_time,
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na transcrição WhisperX: {e}")
            raise AudioTranscriptionException(f"Erro ao transcrever com WhisperX: {e}")
