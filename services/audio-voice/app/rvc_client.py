"""
RVC Client - Voice Conversion usando RVC
Sprint 3: RVC Client Implementation
"""
import os
import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import soundfile as sf
import torch

from app.models import RvcModel, RvcParameters
from app.exceptions import RvcConversionException, RvcModelException, RvcDeviceException

logger = logging.getLogger(__name__)


class RvcClient:
    """
    Cliente para conversão de voz usando RVC (Retrieval-based Voice Conversion)
    
    Features:
    - Lazy loading de módulos RVC (economiza VRAM)
    - Model caching (evita reload desnecessário)
    - Suporte GPU/CPU com fallback automático
    - Cleanup automático de arquivos temporários
    """
    
    def __init__(
        self,
        device: Optional[str] = None,
        fallback_to_cpu: bool = True,
        models_dir: str = "./models/rvc"
    ):
        """
        Inicializa RVC client
        
        Args:
            device: 'cuda', 'cpu' ou None (auto-detect)
            fallback_to_cpu: Se True, usa CPU caso CUDA não disponível
            models_dir: Diretório para armazenar modelos RVC
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Device detection
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        elif device == 'cuda':
            if not torch.cuda.is_available():
                if fallback_to_cpu:
                    logger.warning("CUDA requested but not available, falling back to CPU")
                    self.device = 'cpu'
                else:
                    raise RvcDeviceException(
                        "CUDA requested but not available. "
                        "Set fallback_to_cpu=True or use device='cpu'"
                    )
            else:
                self.device = 'cuda'
        else:
            self.device = device
        
        logger.info(f"RvcClient initialized with device={self.device}")
        
        # Lazy loading
        self._vc = None
        self._current_model_id = None
    
    def _load_vc(self):
        """
        Lazy load do módulo VC do tts-with-rvc
        Carrega apenas quando convert_audio() é chamado pela primeira vez
        """
        if self._vc is not None:
            return
        
        try:
            from tts_with_rvc.infer.vc.modules import VC
            from tts_with_rvc.configs.config import Config
            
            # Configura VC com device correto
            config = Config()
            config.device = self.device
            config.is_half = False  # FP32 por enquanto (Sprint 9 otimizará para FP16)
            config.n_cpu = 0
            config.gpu_name = None
            config.gpu_mem = None
            config.x_pad = 3
            config.x_query = 10
            config.x_center = 60
            config.x_max = 65
            
            self._vc = VC(config)
            logger.info("VC module loaded successfully")
            
        except ImportError as e:
            logger.error(f"Failed to import VC module: {e}")
            raise RvcConversionException(
                "RVC dependencies not available. "
                "Ensure tts-with-rvc is installed (Sprint 2)"
            ) from e
    
    async def convert_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        rvc_model: RvcModel,
        params: RvcParameters
    ) -> Tuple[np.ndarray, float]:
        """
        Converte áudio usando RVC
        
        Args:
            audio_data: Audio numpy array (mono, float32)
            sample_rate: Sample rate do áudio (ex: 24000)
            rvc_model: Modelo RVC a usar
            params: Parâmetros de conversão
        
        Returns:
            Tuple[converted_audio, duration_seconds]
        
        Raises:
            RvcConversionException: Erro durante conversão
            RvcModelException: Erro com modelo RVC
        """
        # Validações
        if audio_data.size == 0:
            raise RvcConversionException("Audio data is empty")
        
        if not Path(rvc_model.pth_path).exists():
            raise RvcModelException(f"Model file not found: {rvc_model.pth_path}")
        
        # Lazy load VC se necessário
        if self._vc is None:
            self._load_vc()
        
        temp_input_path = None
        
        try:
            # Cria arquivo temporário para RVC
            with tempfile.NamedTemporaryFile(
                mode='wb',
                suffix='.wav',
                prefix='rvc_input_',
                delete=False
            ) as temp_file:
                temp_input_path = temp_file.name
            
            # Salva áudio de entrada
            sf.write(temp_input_path, audio_data, sample_rate)
            
            # Carrega modelo se não estiver cacheado
            if self._current_model_id != rvc_model.model_id:
                logger.info(f"Loading RVC model: {rvc_model.name} ({rvc_model.model_id})")
                
                self._vc.get_vc(
                    rvc_model.pth_path,
                    protect0=params.protect,
                    protect1=params.protect
                )
                
                self._current_model_id = rvc_model.model_id
                logger.info(f"Model {rvc_model.name} loaded and cached")
            else:
                logger.debug(f"Using cached model: {rvc_model.name}")
            
            # Conversão RVC
            logger.info(f"Converting audio with RVC (pitch={params.pitch}, method={params.f0_method})")
            
            info, (tgt_sr, audio_opt) = self._vc.vc_single(
                sid=0,  # Speaker ID (sempre 0 para RVC)
                input_audio_path=temp_input_path,
                f0_up_key=params.pitch,  # Pitch shift
                f0_file=None,
                f0_method=params.f0_method,
                file_index=rvc_model.index_path or "",
                file_index2="",
                index_rate=params.index_rate,
                filter_radius=params.filter_radius,
                resample_sr=0,  # 0 = keep original
                rms_mix_rate=params.rms_mix_rate,
                protect=params.protect
            )
            
            # Calcula duração
            duration = len(audio_opt) / tgt_sr
            
            logger.info(f"RVC conversion successful: {duration:.2f}s @ {tgt_sr}Hz")
            
            return audio_opt, duration
            
        except Exception as e:
            logger.error(f"RVC conversion failed: {e}")
            raise RvcConversionException(f"Conversion failed: {str(e)}") from e
        
        finally:
            # Cleanup: remove arquivo temporário
            if temp_input_path and os.path.exists(temp_input_path):
                try:
                    os.remove(temp_input_path)
                    logger.debug(f"Temp file cleaned: {temp_input_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_input_path}: {e}")
    
    def clear_cache(self):
        """
        Limpa cache de modelo
        Útil se quiser forçar reload ou liberar VRAM
        """
        self._current_model_id = None
        logger.info("Model cache cleared")
    
    def unload(self):
        """
        Descarrega módulo VC completamente
        Libera VRAM máxima
        """
        self._vc = None
        self._current_model_id = None
        
        # Force garbage collection
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info("RVC client unloaded, VRAM freed")
