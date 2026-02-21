"""
Gerenciador de modelos Whisper usando Faster-Whisper.
Faster-Whisper é uma reimplementação do Whisper usando CTranslate2, muito mais rápida.
"""
import logging
import time
import torch
from pathlib import Path
from typing import Dict, Any, Optional
from faster_whisper import WhisperModel

from .interfaces import IModelManager
from .exceptions import AudioTranscriptionException
from .config import get_settings

logger = logging.getLogger(__name__)


class FasterWhisperModelManager(IModelManager):
    """
    Gerencia ciclo de vida do modelo Faster-Whisper.
    
    Vantagens vs OpenAI Whisper:
    - 4x mais rápido
    - Menos uso de VRAM
    - word_timestamps nativamente suport

ado
    """
    
    def __init__(self, model_dir: Optional[Path] = None):
        """
        Args:
            model_dir: Diretório para armazenar modelos
        """
        self.settings = get_settings()
        self.model_dir = model_dir or Path(self.settings.get('whisper_download_root', './models'))
        self.model_name = self.settings.get('whisper_model', 'base')
        
        self.model: Optional[WhisperModel] = None
        self.device: Optional[str] = None
        self.is_loaded = False
        
        # Configurações de retry
        self.max_retries = int(self.settings.get('model_load_retries', 3))
        self.retry_backoff = float(self.settings.get('model_load_backoff', 2.0))
    
    def _detect_device(self) -> str:
        """Detecta melhor device disponível"""
        requested_device = self.settings.get('whisper_device', 'cpu').lower()
        
        if requested_device == 'cuda' and torch.cuda.is_available():
            logger.info(f"🎮 CUDA disponível: {torch.cuda.get_device_name(0)}")
            return 'cuda'
        else:
            if requested_device == 'cuda':
                logger.warning("⚠️  CUDA solicitado mas não disponível, usando CPU")
            else:
                logger.info("ℹ️  Usando CPU")
            return 'cpu'
    
    def load_model(self) -> None:
        """Carrega modelo Faster-Whisper"""
        if self.is_loaded and self.model is not None:
            logger.info(f"Modelo {self.model_name} já carregado no {self.device}")
            return
        
        logger.info(f"📦 Carregando Faster-Whisper: {self.model_name}")
        
        # Detecta melhor dispositivo
        self.device = self._detect_device()
        
        # Garante diretório existe
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Tenta carregar com retry
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Tentativa {attempt}/{self.max_retries} - Device: {self.device}")
                
                # Carrega modelo (faster-whisper usa compute_type)
                compute_type = "float16" if self.device == "cuda" else "int8"
                
                self.model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=compute_type,
                    download_root=str(self.model_dir)
                )
                
                self.is_loaded = True
                logger.info(f"✅ Faster-Whisper {self.model_name} carregado no {self.device.upper()} ({compute_type})")
                return
                
            except Exception as e:
                last_error = e
                logger.error(f"❌ Falha na tentativa {attempt}: {e}")
                
                if attempt < self.max_retries:
                    sleep_time = self.retry_backoff ** attempt
                    logger.info(f"⏳ Aguardando {sleep_time}s antes de retentar...")
                    time.sleep(sleep_time)
                    
                    # Se falhou na GPU, tenta CPU
                    if self.device == 'cuda':
                        logger.warning("Fallback para CPU após falha na GPU")
                        self.device = 'cpu'
        
        raise AudioTranscriptionException(
            f"Falha ao carregar Faster-Whisper {self.model_name} após {self.max_retries} tentativas: {last_error}"
        )
    
    def unload_model(self) -> Dict[str, Any]:
        """Descarrega modelo da memória"""
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
            
            del self.model
            self.model = None
            self.is_loaded = False
            
            import gc
            gc.collect()
            
            # Estima RAM liberada (faster-whisper usa menos memória)
            model_sizes = {'tiny': 40, 'base': 75, 'small': 250, 'medium': 770, 'large': 1550}
            result["memory_freed"]["ram_mb"] = model_sizes.get(self.model_name, 75)
            
            result["success"] = True
            result["message"] = f"Faster-Whisper {self.model_name} descarregado"
            logger.info(f"✅ {result['message']}")
            
            return result
            
        except Exception as e:
            result["message"] = f"Erro ao descarregar: {e}"
            logger.error(f"❌ {result['message']}")
            return result
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual do modelo"""
        return {
            "loaded": self.is_loaded,
            "model_name": self.model_name,
            "device": self.device,
            "model_dir": str(self.model_dir),
            "engine": "faster-whisper"
        }
    
    def transcribe(self, audio_path: Path, language: str = "auto", task: str = "transcribe", **kwargs) -> Dict[str, Any]:
        """
        Transcreve áudio usando Faster-Whisper com word timestamps.
        
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
        
        try:
            logger.info(f"🎤 Transcrevendo com Faster-Whisper: {audio_path.name} (lang={language}, task={task})")
            
            # Configurações de transcrição
            transcribe_kwargs = {
                "word_timestamps": True,  # ✅ Timestamps palavra-por-palavra
                "vad_filter": False,  # Desabilitar VAD interno
                "task": task  # transcribe ou translate
            }
            
            if language != "auto" and language:
                transcribe_kwargs["language"] = language
            
            # Merge kwargs extras (fp16, beam_size, etc)
            transcribe_kwargs.update(kwargs)
            
            # Transcreve (faster-whisper retorna generators)
            segments_gen, info = self.model.transcribe(
                str(audio_path),
                **transcribe_kwargs
            )
            
            # Converte generator para lista e extrai words
            segments = []
            full_text = []
            
            for segment in segments_gen:
                # Extrai word-level timestamps
                words_list = []
                if hasattr(segment, 'words') and segment.words:
                    for word in segment.words:
                        words_list.append({
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "probability": word.probability
                        })
                
                segment_dict = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "words": words_list  # ✅ Word-level timestamps!
                }
                
                segments.append(segment_dict)
                full_text.append(segment.text)
            
            result = {
                "success": True,
                "text": " ".join(full_text),
                "segments": segments,
                "language": info.language if hasattr(info, 'language') else language,
                "duration": info.duration if hasattr(info, 'duration') else 0.0
            }
            
            logger.info(
                f"✅ Faster-Whisper transcription: {len(segments)} segments, "
                f"{sum(len(s['words']) for s in segments)} words, "
                f"{result['duration']:.1f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}")
            raise AudioTranscriptionException(f"Falha na transcrição: {e}")
