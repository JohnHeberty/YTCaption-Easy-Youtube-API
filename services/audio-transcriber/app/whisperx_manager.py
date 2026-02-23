"""
Gerenciador de modelos usando WhisperX.
WhisperX oferece timestamps word-level com forced alignment para precisão máxima.
"""
import logging
import time
import torch
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import whisperx
    WHISPERX_AVAILABLE = True
except ImportError:
    WHISPERX_AVAILABLE = False
    logging.warning("⚠️ whisperx não instalado. Instale com: pip install whisperx")

from .interfaces import IModelManager
from .exceptions import AudioTranscriptionException
from .config import get_settings

logger = logging.getLogger(__name__)


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
    
    def __init__(self, model_dir: Optional[Path] = None):
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
        
        self.model: Optional[Any] = None
        self.align_model: Optional[Any] = None
        self.align_metadata: Optional[Dict] = None
        self.device: Optional[str] = None
        self.compute_type: Optional[str] = None
        self.is_loaded = False
        
        # Configurações
        self.max_retries = int(self.settings.get('model_load_retries', 3))
        self.retry_backoff = float(self.settings.get('model_load_backoff', 2.0))
    
    def _detect_device(self) -> str:
        """Detecta melhor device disponível"""
        requested_device = self.settings.get('whisper_device', 'cpu').lower()
        
        if requested_device == 'cuda':
            if torch.cuda.is_available():
                logger.info("✅ CUDA disponível")
                return 'cuda'
            else:
                logger.warning("⚠️ CUDA solicitado mas não disponível, usando CPU")
                return 'cpu'
        else:
            logger.info("ℹ️ Usando CPU")
            return 'cpu'
    
    def load_model(self):
        """Carrega modelo WhisperX"""
        if self.is_loaded:
            logger.info(f"ℹ️ Modelo WhisperX '{self.model_name}' já está carregado")
            return
        
        logger.info(f"📦 Carregando WhisperX: {self.model_name}")
        
        # Detecta device
        self.device = self._detect_device()
        
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
    
    def _load_align_model(self, language_code: str):
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
    
    def unload_model(self) -> dict:
        """Descarrega modelo da memória"""
        if not self.is_loaded or self.model is None:
            return {
                "success": True,
                "message": "Modelo já estava descarregado",
                "memory_freed": {"ram_mb": 0, "vram_mb": 0}
            }
        
        logger.warning(f"🔥 Descarregando WhisperX '{self.model_name}' do {self.device}")
        
        # Estimativa de memória
        model_sizes = {
            'tiny': 100,
            'base': 200,
            'small': 600,
            'medium': 1800,
            'large': 3500
        }
        
        # Limpa modelos
        del self.model
        self.model = None
        
        if self.align_model is not None:
            del self.align_model
            self.align_model = None
            self.align_metadata = None
        
        self.is_loaded = False
        
        # Força garbage collection
        import gc
        gc.collect()
        
        # Limpa cache CUDA
        if self.device == 'cuda' and torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        ram_freed = model_sizes.get(self.model_name, 200)
        
        logger.info(f"✅ WhisperX descarregado - RAM liberada: ~{ram_freed}MB")
        
        return {
            "success": True,
            "message": f"Modelo '{self.model_name}' descarregado com sucesso",
            "memory_freed": {"ram_mb": ram_freed, "vram_mb": 0}
        }
    
    def get_status(self) -> dict:
        """Retorna status atual do modelo"""
        return {
            "loaded": self.is_loaded,
            "model_name": self.model_name if self.is_loaded else None,
            "device": self.device if self.is_loaded else None,
            "engine": "whisperx",
            "align_model_loaded": self.align_model is not None
        }
    
    def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        task: str = "transcribe"
    ) -> dict:
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
            # Carrega áudio
            audio = whisperx.load_audio(str(audio_path))
            
            # Transcrição inicial
            start_time = time.time()
            
            # Prepara parâmetros
            transcribe_params = {
                "audio": audio,
                "batch_size": 16
            }
            
            # Define idioma se não for auto
            if language != "auto":
                transcribe_params["language"] = language
            
            # Transcreve
            result = self.model.transcribe(**transcribe_params)
            
            # Detecta idioma
            detected_language = result.get("language", language if language != "auto" else "en")
            
            # Aplica forced alignment se possível
            if detected_language != "auto":
                try:
                    # Carrega modelo de alinhamento se necessário
                    if self.align_model is None or self.align_metadata is None:
                        self._load_align_model(detected_language)
                    
                    # Aplica alinhamento
                    if self.align_model is not None:
                        logger.info("🔧 Aplicando forced alignment...")
                        result = whisperx.align(
                            result["segments"],
                            self.align_model,
                            self.align_metadata,
                            audio,
                            self.device,
                            return_char_alignments=False
                        )
                        logger.info("✅ Forced alignment aplicado")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erro no alignment, usando timestamps sem alinhamento: {e}")
            
            transcription_time = time.time() - start_time
            
            # Processa resultado
            segments = []
            full_text = ""
            
            for segment in result.get("segments", []):
                # Extrai words
                words = []
                if "words" in segment:
                    for word in segment["words"]:
                        words.append({
                            "word": word.get("word", ""),
                            "start": float(word.get("start", 0.0)),
                            "end": float(word.get("end", 0.0)),
                            "probability": float(word.get("score", 1.0))  # WhisperX usa 'score'
                        })
                
                segment_text = segment.get("text", "").strip()
                full_text += segment_text + " "
                
                segments.append({
                    "id": segment.get("id", len(segments)),
                    "start": float(segment.get("start", 0.0)),
                    "end": float(segment.get("end", 0.0)),
                    "text": segment_text,
                    "words": words
                })
            
            # Calcula duração
            duration = segments[-1]["end"] if segments else 0.0
            
            total_words = sum(len(s["words"]) for s in segments)
            
            logger.info(
                f"✅ WhisperX transcription: {len(segments)} segments, "
                f"{total_words} words, {duration:.1f}s (aligned timestamps)"
            )
            
            return {
                "success": True,
                "text": full_text.strip(),
                "language": detected_language,
                "segments": segments,
                "duration": duration,
                "transcription_time": transcription_time
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na transcrição WhisperX: {e}")
            raise AudioTranscriptionException(f"Erro ao transcrever com WhisperX: {e}")
