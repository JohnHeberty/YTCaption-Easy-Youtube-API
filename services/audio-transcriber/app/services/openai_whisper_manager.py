"""
Gerenciador de modelos usando OpenAI Whisper original.
OpenAI Whisper é o modelo original, mais lento mas com compatibilidade máxima.
"""
import logging
import time
import torch
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import whisper
    OPENAI_WHISPER_AVAILABLE = True
except ImportError:
    OPENAI_WHISPER_AVAILABLE = False
    logging.warning("⚠️ openai-whisper não instalado. Instale com: pip install openai-whisper")

from ..domain.interfaces import IModelManager
from ..domain.exceptions import AudioTranscriptionException
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class OpenAIWhisperManager(IModelManager):
    """
    Gerencia ciclo de vida do modelo OpenAI Whisper original.
    
    Características:
    - Modelo original da OpenAI
    - Compatibilidade máxima
    - Mais lento que faster-whisper (4x)
    - Maior uso de VRAM
    - Word timestamps requerem configuração extra
    """
    
    def __init__(self, model_dir: Optional[Path] = None):
        """
        Args:
            model_dir: Diretório para armazenar modelos
        """
        if not OPENAI_WHISPER_AVAILABLE:
            raise AudioTranscriptionException(
                "OpenAI Whisper não está instalado. "
                "Instale com: pip install openai-whisper"
            )
        
        self.settings = get_settings()
        self.model_dir = model_dir or Path(self.settings.get('whisper_download_root', './models'))
        self.model_name = self.settings.get('whisper_model', 'base')
        
        self.model: Optional[Any] = None
        self.device: Optional[str] = None
        self.is_loaded = False
        
        # Configurações de retry
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
        """Carrega modelo OpenAI Whisper"""
        if self.is_loaded:
            logger.info(f"ℹ️ Modelo OpenAI Whisper '{self.model_name}' já está carregado")
            return
        
        logger.info(f"📦 Carregando OpenAI Whisper: {self.model_name}")
        
        # Detecta device
        self.device = self._detect_device()
        logger.info(f"🖥️ Device: {self.device.upper()}")
        
        # Tenta carregar com retry
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Tentativa {attempt}/{self.max_retries} - Device: {self.device}")
                
                # Carrega modelo
                self.model = whisper.load_model(
                    self.model_name,
                    device=self.device,
                    download_root=str(self.model_dir)
                )
                
                self.is_loaded = True
                logger.info(f"✅ OpenAI Whisper {self.model_name} carregado no {self.device.upper()}")
                return
                
            except Exception as e:
                logger.error(f"❌ Tentativa {attempt} falhou: {e}")
                
                if attempt < self.max_retries:
                    wait_time = self.retry_backoff ** attempt
                    logger.info(f"⏳ Aguardando {wait_time}s antes de tentar novamente...")
                    time.sleep(wait_time)
                else:
                    raise AudioTranscriptionException(
                        f"Falha ao carregar OpenAI Whisper após {self.max_retries} tentativas: {e}"
                    )
    
    def unload_model(self) -> dict:
        """Descarrega modelo da memória"""
        if not self.is_loaded or self.model is None:
            return {
                "success": True,
                "message": "Modelo já estava descarregado",
                "memory_freed": {"ram_mb": 0, "vram_mb": 0}
            }
        
        logger.warning(f"🔥 Descarregando OpenAI Whisper '{self.model_name}' do {self.device}")
        
        # Estimativa de memória baseada no modelo
        model_sizes = {
            'tiny': 75,
            'base': 150,
            'small': 500,
            'medium': 1500,
            'large': 3000
        }
        
        del self.model
        self.model = None
        self.is_loaded = False
        
        # Força garbage collection
        import gc
        gc.collect()
        
        # Limpa cache CUDA se necessário
        if self.device == 'cuda' and torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        ram_freed = model_sizes.get(self.model_name, 150)
        
        logger.info(f"✅ OpenAI Whisper descarregado - RAM liberada: ~{ram_freed}MB")
        
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
            "engine": "openai-whisper"
        }
    
    def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        task: str = "transcribe"
    ) -> dict:
        """
        Transcreve áudio usando OpenAI Whisper.
        
        Args:
            audio_path: Caminho do arquivo de áudio
            language: Código do idioma (ISO 639-1) ou "auto"
            task: "transcribe" ou "translate"
        
        Returns:
            dict com:
                - success: bool
                - text: str (texto completo)
                - language: str (idioma detectado)
                - segments: list (segmentos com timestamps)
                - duration: float
        """
        if not self.is_loaded:
            logger.info("📦 Modelo não carregado, carregando agora...")
            self.load_model()
        
        logger.info(f"🎤 Transcrevendo com OpenAI Whisper: {audio_path.name} (lang={language}, task={task})")
        
        try:
            # Prepara parâmetros
            whisper_params = {
                "audio": str(audio_path),
                "task": task,
                "verbose": False,
                "word_timestamps": True  # Habilita word timestamps
            }
            
            # Define idioma se não for auto
            if language != "auto":
                whisper_params["language"] = language
            
            # Transcreve
            start_time = time.time()
            result = self.model.transcribe(**whisper_params)
            transcription_time = time.time() - start_time
            
            # Processa resultado
            segments = []
            for segment in result.get("segments", []):
                # Extrai words se disponíveis
                words = []
                if "words" in segment:
                    for word in segment["words"]:
                        words.append({
                            "word": word.get("word", ""),
                            "start": float(word.get("start", 0.0)),
                            "end": float(word.get("end", 0.0)),
                            "probability": float(word.get("probability", 1.0))
                        })
                
                segments.append({
                    "id": segment.get("id", 0),
                    "start": float(segment.get("start", 0.0)),
                    "end": float(segment.get("end", 0.0)),
                    "text": segment.get("text", "").strip(),
                    "words": words
                })
            
            # Calcula duração
            duration = segments[-1]["end"] if segments else 0.0
            
            logger.info(
                f"✅ OpenAI Whisper transcription: {len(segments)} segments, "
                f"{sum(len(s['words']) for s in segments)} words, {duration:.1f}s"
            )
            
            return {
                "success": True,
                "text": result.get("text", "").strip(),
                "language": result.get("language", language),
                "segments": segments,
                "duration": duration,
                "transcription_time": transcription_time
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na transcrição OpenAI Whisper: {e}")
            raise AudioTranscriptionException(f"Erro ao transcrever com OpenAI Whisper: {e}")
