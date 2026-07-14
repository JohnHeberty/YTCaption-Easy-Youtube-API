"""
Gerenciador de modelos Whisper usando Faster-Whisper.
Faster-Whisper é uma reimplementação do Whisper usando CTranslate2, muito mais rápida.
"""
from __future__ import annotations

import gc
import time
import torch
from pathlib import Path

from ..core.constants import FASTER_WHISPER_MODEL_SIZES
from typing import Any
from faster_whisper import WhisperModel

from ..domain.interfaces import IModelManager
from ..shared.exceptions import AudioTranscriptionException
from ..core.config import get_settings
try:
    from av.error import FFmpegError as AvFFmpegError, EOFError as AvEOFError  # noqa: F401
except ImportError:
    pass

from ..infrastructure import get_circuit_breaker, CircuitBreakerException
from .device_manager import TorchDeviceManager
from common.log_utils import get_logger

logger = get_logger(__name__)

class FasterWhisperModelManager(IModelManager):
    """
    Gerencia ciclo de vida do modelo Faster-Whisper.
    
    Vantagens vs OpenAI Whisper:
    - 4x mais rápido
    - Menos uso de VRAM
    - word_timestamps nativamente suport

ado
    """
    
    def __init__(self, model_dir: Path | None = None) -> None:
        """
        Args:
            model_dir: Diretório para armazenar modelos
        """
        self.settings = get_settings()
        self.model_dir = model_dir or Path(self.settings.get('whisper_download_root', './models'))
        self.model_name = self.settings.get('whisper_model', 'base')
        
        self.model: WhisperModel | None = None
        self.device: str | None = None
        self.is_loaded = False
        
        # Configurações de retry
        self.max_retries = int(self.settings.get('model_load_retries', 3))
        self.retry_backoff = float(self.settings.get('model_load_backoff', 2.0))
        
        # Device detection via IDeviceManager (DIP)
        self.device_mgr = TorchDeviceManager(
            preferred_device=self.settings.get('whisper_device', 'auto')
        )

    def _is_oom_error(self, e: Exception) -> bool:
        """Detecta se o erro é Out-of-Memory na GPU"""
        error_msg = str(e).lower()
        oom_keywords = ["out of memory", "outofmemory", "cuda error", "cudaerror", "not enough memory"]
        # PyTorch >= 1.13 tem torch.cuda.OutOfMemoryError
        try:
            if isinstance(e, torch.cuda.OutOfMemoryError):
                return True
        except AttributeError:
            pass
        return any(kw in error_msg for kw in oom_keywords)

    def _try_load_on_device(
        self, device: str, compute_type: str, cb: Any, service_name: str,
    ) -> bool:
        """Try loading the model on a device with retries. Returns True on success."""
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Tentativa {attempt}/{self.max_retries} - "
                    f"Device: {device.upper()}, compute_type: {compute_type}, "
                    f"modelo: {self.model_name}"
                )
                self.model = WhisperModel(
                    self.model_name,
                    device=device,
                    compute_type=compute_type,
                    download_root=str(self.model_dir),
                )
                self.is_loaded = True
                cb.record_success(service_name)
                logger.info(
                    f"✅ Faster-Whisper '{self.model_name}' carregado em "
                    f"{device.upper()} ({compute_type})"
                )
                return True
            except (RuntimeError, OSError, IOError, Exception) as e:
                cb.record_failure(service_name)
                if device == "cuda" and self._is_oom_error(e):
                    fallback_enabled = str(self.settings.get('whisper_fallback_cpu', 'true')).lower() == 'true'
                    if fallback_enabled:
                        logger.warning(
                            f"⚠️ OOM na GPU ao carregar '{self.model_name}' "
                            f"({e}) — fallback imediato para CPU com int8"
                        )
                        try:
                            torch.cuda.empty_cache()
                        except Exception:
                            pass
                        return False  # signal caller to try CPU
                    raise AudioTranscriptionException(
                        f"OOM na GPU ao carregar {self.model_name} e fallback CPU desabilitado: {e}"
                    ) from e
                logger.exception(f"❌ Falha na tentativa {attempt}/{self.max_retries}: {e}")
                if attempt < self.max_retries:
                    sleep_time = self.retry_backoff ** attempt
                    logger.info(f"⏳ Aguardando {sleep_time}s antes de retentar...")
                    time.sleep(sleep_time)
        return False

    def load_model(self) -> None:
        """Carrega modelo Faster-Whisper com Circuit Breaker e fallback GPU→CPU imediato em OOM"""
        if self.is_loaded and self.model is not None:
            logger.info(f"Modelo {self.model_name} já carregado no {self.device}")
            return
        
        logger.info(f"📦 Carregando Faster-Whisper: {self.model_name}")
        
        self.device = self.device_mgr.detect_device()
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        cb = get_circuit_breaker()
        service_name = f"faster_whisper_load_{self.model_name}"
        
        if cb.is_open(service_name):
            raise AudioTranscriptionException(
                f"Circuit breaker OPEN for {service_name}. Service temporarily unavailable."
            )
        
        last_error = None
        attempted_devices: list[str] = []
        
        while True:
            if self.device in attempted_devices:
                break
            attempted_devices.append(self.device)
            
            compute_type = "float16" if self.device == "cuda" else "int8"
            
            if self._try_load_on_device(self.device, compute_type, cb, service_name):
                return
            
            if self.device == "cuda":
                logger.warning("Fallback para CPU após falha na GPU")
                self.device = "cpu"
            else:
                break
        
        raise AudioTranscriptionException(
            f"Falha ao carregar Faster-Whisper '{self.model_name}' em todos os dispositivos "
            f"tentados {attempted_devices}: {last_error}"
        )
    
    def unload_model(self) -> dict[str, Any]:
        """Descarrega modelo da memória com cleanup garantido"""
        result = {
            "success": False,
            "model_name": self.model_name,
            "device_was": self.device,
            "memory_freed": {"ram_mb": 0.0, "vram_mb": 0.0}
        }
        
        if not self.is_loaded or self.model is None:
            result["success"] = True
            result["message"] = "Modelo já estava descarregado"
            return result
        
        try:
            logger.info(f"🔥 Descarregando Faster-Whisper {self.model_name}...")
            
            # Cleanup garantido com finally não é necessário aqui pois já estamos no try
            del self.model
            self.model = None
            self.is_loaded = False
            
            gc.collect()
            
            # Libera CUDA cache se estava usando GPU
            if self.device == 'cuda' and torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug("CUDA cache limpo")
            
            # Estima RAM liberada (faster-whisper usa menos memória)
            result["memory_freed"]["ram_mb"] = FASTER_WHISPER_MODEL_SIZES.get(self.model_name, 75)
            
            result["success"] = True
            result["message"] = f"Faster-Whisper {self.model_name} descarregado"
            logger.info(f"✅ {result['message']}")
            
            return result
            
        except Exception as e:
            result["message"] = f"Erro ao descarregar: {e}"
            logger.exception(f"❌ {result['message']}")  # ✅ Usa exception() para stack trace
            return result
        finally:
            # Garante que flags sejam resetadas mesmo em caso de erro
            self.model = None
            self.is_loaded = False
    
    def get_status(self) -> dict[str, Any]:
        """Retorna status atual do modelo"""
        return {
            "loaded": self.is_loaded,
            "model_name": self.model_name,
            "device": self.device,
            "model_dir": str(self.model_dir),
            "engine": "faster-whisper"
        }
    
    def _build_transcribe_kwargs(self, language: str, task: str, **kwargs: Any) -> dict[str, Any]:
        """Build kwargs dict for faster-whisper transcribe call."""
        transcribe_kwargs: dict[str, Any] = {
            "word_timestamps": True,
            "vad_filter": False,
            "task": task,
            "beam_size": int(self.settings.get('whisper_beam_size', 5)),
            "best_of": int(self.settings.get('whisper_best_of', 5)),
        }
        if language != "auto" and language:
            transcribe_kwargs["language"] = language
        transcribe_kwargs.update(kwargs)
        return transcribe_kwargs

    @staticmethod
    def _collect_segments(segments_gen: Any) -> tuple[list[dict[str, Any]], list[str]]:
        """Collect segments from faster-whisper generator into list of dicts."""
        segments: list[dict[str, Any]] = []
        full_text: list[str] = []
        for segment in segments_gen:
            words_list = []
            if hasattr(segment, 'words') and segment.words:
                for word in segment.words:
                    words_list.append({
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "probability": word.probability,
                    })
            segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "words": words_list,
            })
            full_text.append(segment.text)
        return segments, full_text

    def transcribe(self, audio_path: Path, language: str = "auto", task: str = "transcribe", **kwargs: Any) -> dict[str, Any]:
        """
        Transcreve áudio usando Faster-Whisper com word timestamps e circuit breaker.
        
        Args:
            audio_path: Caminho para arquivo de áudio
            language: Código do idioma ou 'auto' para detecção
            task: 'transcribe' ou 'translate' (traduz para inglês)
            **kwargs: Opções adicionais (fp16, beam_size, etc)
        
        Returns:
            Resultado com segments e word-level timestamps
        """
        if not self.is_loaded:
            self.load_model()
        
        cb = get_circuit_breaker()
        service_name = f"faster_whisper_transcribe_{self.model_name}"
        
        if cb.is_open(service_name):
            raise AudioTranscriptionException(
                f"Circuit breaker OPEN for {service_name}. Service temporarily unavailable."
            )
        
        try:
            logger.info(f"🎤 Transcrevendo com Faster-Whisper: {audio_path.name} (lang={language}, task={task})")
            
            transcribe_kwargs = self._build_transcribe_kwargs(language, task, **kwargs)
            
            segments_gen, info = self.model.transcribe(str(audio_path), **transcribe_kwargs)
            
            segments, full_text = self._collect_segments(segments_gen)
            
            result = {
                "success": True,
                "text": " ".join(full_text),
                "segments": segments,
                "language": info.language if hasattr(info, 'language') else language,
                "duration": info.duration if hasattr(info, 'duration') else 0.0,
            }
            
            logger.info(
                f"✅ Faster-Whisper transcription: {len(segments)} segments, "
                f"{sum(len(s['words']) for s in segments)} words, "
                f"{result['duration']:.1f}s"
            )
            
            cb.record_success(service_name)
            return result
            
        except Exception as e:
            logger.exception(f"❌ Erro na transcrição: {e}")
            cb.record_failure(service_name)

            if isinstance(e, IndexError):
                raise AudioTranscriptionException(
                    f"Erro interno do faster-whisper (tuple index out of range): "
                    f"o arquivo de áudio pode estar corrompido, vazio, ou sem stream de áudio válido. "
                    f"Detalhes: {e}"
                ) from e

            raise AudioTranscriptionException(f"Falha na transcrição: {e}") from e
