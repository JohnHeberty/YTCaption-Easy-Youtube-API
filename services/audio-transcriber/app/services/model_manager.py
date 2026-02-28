"""
Gerenciador de modelos Whisper (Single Responsibility Principle).
Responsável APENAS por carregar/descarregar/usar modelos Whisper.
"""
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
import torch
import whisper

from ..domain.interfaces import IModelManager
from ..domain.exceptions import AudioTranscriptionException
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class WhisperModelManager(IModelManager):
    """
    Gerencia ciclo de vida do modelo Whisper.
    
    Responsabilidades:
    - Carregar modelo (lazy loading)
    - Descarregar modelo (para economizar recursos)
    - Transcrever áudio
    - Gerenciar device (GPU/CPU)
    - Retry automático em falhas
    """
    
    def __init__(self, device_manager, model_dir: Optional[Path] = None):
        """
        Args:
            device_manager: Gerenciador de dispositivos (DIP)
            model_dir: Diretório para armazenar modelos
        """
        self.device_manager = device_manager
        self.settings = get_settings()
        self.model_dir = model_dir or Path(self.settings.get('whisper_download_root', './models'))
        self.model_name = self.settings.get('whisper_model', 'base')
        
        self.model: Optional[Any] = None
        self.device: Optional[str] = None
        self.is_loaded = False
        
        # Configurações de retry
        self.max_retries = int(self.settings.get('model_load_retries', 3))
        self.retry_backoff = float(self.settings.get('model_load_backoff', 2.0))
    
    def load_model(self) -> None:
        """Carrega modelo Whisper com retry automático"""
        if self.is_loaded and self.model is not None:
            logger.info(f"Modelo {self.model_name} já carregado no {self.device}")
            return
        
        logger.info(f"📦 Carregando modelo Whisper: {self.model_name}")
        
        # Detecta melhor dispositivo
        self.device = self.device_manager.detect_device()
        
        # Garante diretório existe
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Tenta carregar com retry
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Tentativa {attempt}/{self.max_retries} - Device: {self.device}")
                
                # Valida device antes de usar
                if not self.device_manager.validate_device(self.device):
                    logger.warning(f"Device {self.device} inválido, tentando CPU")
                    self.device = 'cpu'
                
                # Carrega modelo
                self.model = whisper.load_model(
                    self.model_name,
                    device=self.device,
                    download_root=str(self.model_dir)
                )
                
                self.is_loaded = True
                logger.info(f"✅ Modelo {self.model_name} carregado no {self.device.upper()}")
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
        
        # Se chegou aqui, todas as tentativas falharam
        raise AudioTranscriptionException(
            f"Falha ao carregar modelo {self.model_name} após {self.max_retries} tentativas: {last_error}"
        )
    
    def unload_model(self) -> Dict[str, Any]:
        """Descarrega modelo da memória para liberar recursos"""
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
            logger.info(f"🔥 Descarregando modelo {self.model_name} do {self.device}...")
            
            # Captura VRAM antes (se GPU)
            vram_before = 0.0
            if self.device == 'cuda' and torch.cuda.is_available():
                vram_before = torch.cuda.memory_allocated(0) / 1024**2
            
            # Remove modelo
            del self.model
            self.model = None
            self.is_loaded = False
            
            # Força garbage collection
            import gc
            gc.collect()
            
            # Limpa cache CUDA se necessário
            if self.device == 'cuda' and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                
                vram_after = torch.cuda.memory_allocated(0) / 1024**2
                result["memory_freed"]["vram_mb"] = round(vram_before - vram_after, 2)
            
            # Estima RAM liberada
            model_sizes = {'tiny': 75, 'base': 150, 'small': 500, 'medium': 1500, 'large': 3000}
            result["memory_freed"]["ram_mb"] = model_sizes.get(self.model_name, 150)
            
            result["success"] = True
            result["message"] = f"Modelo {self.model_name} descarregado com sucesso"
            logger.info(f"✅ {result['message']}")
            
            return result
            
        except Exception as e:
            result["message"] = f"Erro ao descarregar modelo: {e}"
            logger.error(f"❌ {result['message']}")
            return result
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual do modelo"""
        status = {
            "loaded": self.is_loaded,
            "model_name": self.model_name,
            "device": self.device,
            "model_dir": str(self.model_dir)
        }
        
        if self.is_loaded and self.device == 'cuda' and torch.cuda.is_available():
            status["vram_mb"] = round(torch.cuda.memory_allocated(0) / 1024**2, 2)
            status["vram_reserved_mb"] = round(torch.cuda.memory_reserved(0) / 1024**2, 2)
        
        return status
    
    def transcribe(self, audio_path: Path, language: str = "auto") -> Dict[str, Any]:
        """
        Transcreve áudio usando Whisper.
        
        Args:
            audio_path: Caminho para arquivo de áudio
            language: Código do idioma ou 'auto' para detecção
        
        Returns:
            Resultado da transcrição com segmentos e texto completo
        """
        # Garante modelo carregado
        if not self.is_loaded:
            self.load_model()
        
        try:
            logger.info(f"🎤 Transcrevendo: {audio_path.name} (language={language})")
            
            # Prepara opções
            transcribe_options = {
                "word_timestamps": True  # ✅ Ativar timestamps palavra-por-palavra
            }
            if language != "auto":
                transcribe_options["language"] = language
            
            # Transcreve
            result = self.model.transcribe(
                str(audio_path),
                **transcribe_options
            )
            
            logger.info(f"✅ Transcrição concluída: {len(result.get('segments', []))} segmentos")
            
            return {
                "success": True,
                "text": result["text"],
                "segments": result.get("segments", []),
                "language": result.get("language", language)
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}")
            raise AudioTranscriptionException(f"Falha na transcrição: {e}")
