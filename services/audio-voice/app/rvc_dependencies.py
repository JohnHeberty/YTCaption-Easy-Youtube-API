"""
Helper module for lazy loading RVC dependencies
Sprint 2: Dependencies validation
"""
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RvcDependencies:
    """
    Lazy loader for RVC dependencies
    Carrega módulos apenas quando necessário para economizar memória
    """
    
    def __init__(self):
        self._tts_with_rvc = None
        self._vc_class = None
        self._pipeline_class = None
        self._rmvpe_class = None
        self._fairseq = None
        self._faiss = None
        self._librosa = None
        self._parselmouth = None
        self._torchcrepe = None
    
    @property
    def tts_with_rvc(self):
        """Lazy load tts-with-rvc module"""
        if self._tts_with_rvc is None:
            try:
                import tts_with_rvc
                self._tts_with_rvc = tts_with_rvc
                logger.info(f"Loaded tts-with-rvc v{tts_with_rvc.__version__}")
            except ImportError as e:
                logger.error(f"Failed to import tts-with-rvc: {e}")
                raise ImportError(
                    "tts-with-rvc not installed. "
                    "Install with: pip install tts-with-rvc==0.1.9"
                ) from e
        return self._tts_with_rvc
    
    @property
    def VC(self):
        """Lazy load VC class"""
        if self._vc_class is None:
            try:
                from tts_with_rvc.infer.vc.modules import VC
                self._vc_class = VC
                logger.debug("Loaded VC class from tts-with-rvc")
            except ImportError as e:
                logger.error(f"Failed to import VC: {e}")
                raise ImportError("VC class not available") from e
        return self._vc_class
    
    @property
    def Pipeline(self):
        """Lazy load Pipeline class"""
        if self._pipeline_class is None:
            try:
                from tts_with_rvc.infer.vc.pipeline import Pipeline
                self._pipeline_class = Pipeline
                logger.debug("Loaded Pipeline class from tts-with-rvc")
            except ImportError as e:
                logger.error(f"Failed to import Pipeline: {e}")
                raise ImportError("Pipeline class not available") from e
        return self._pipeline_class
    
    @property
    def RMVPE(self):
        """Lazy load RMVPE class"""
        if self._rmvpe_class is None:
            try:
                from tts_with_rvc.infer.lib.rmvpe import RMVPE
                self._rmvpe_class = RMVPE
                logger.debug("Loaded RMVPE class from tts-with-rvc")
            except ImportError as e:
                logger.error(f"Failed to import RMVPE: {e}")
                raise ImportError("RMVPE class not available") from e
        return self._rmvpe_class
    
    @property
    def fairseq(self):
        """Lazy load fairseq"""
        if self._fairseq is None:
            try:
                import fairseq
                self._fairseq = fairseq
                logger.debug(f"Loaded fairseq v{fairseq.__version__}")
            except ImportError as e:
                logger.error(f"Failed to import fairseq: {e}")
                raise ImportError(
                    "fairseq not installed. "
                    "Install with: pip install fairseq"
                ) from e
        return self._fairseq
    
    @property
    def faiss(self):
        """Lazy load faiss"""
        if self._faiss is None:
            try:
                import faiss
                self._faiss = faiss
                logger.debug("Loaded faiss")
            except ImportError as e:
                logger.error(f"Failed to import faiss: {e}")
                raise ImportError(
                    "faiss not installed. "
                    "Install with: pip install faiss-gpu (CUDA) or faiss-cpu"
                ) from e
        return self._faiss
    
    @property
    def librosa(self):
        """Lazy load librosa"""
        if self._librosa is None:
            try:
                import librosa
                self._librosa = librosa
                logger.debug(f"Loaded librosa v{librosa.__version__}")
            except ImportError as e:
                logger.error(f"Failed to import librosa: {e}")
                raise ImportError(
                    "librosa not installed. "
                    "Install with: pip install librosa==0.10.1"
                ) from e
        return self._librosa
    
    @property
    def parselmouth(self):
        """Lazy load parselmouth"""
        if self._parselmouth is None:
            try:
                import parselmouth
                self._parselmouth = parselmouth
                logger.debug("Loaded parselmouth")
            except ImportError as e:
                logger.error(f"Failed to import parselmouth: {e}")
                raise ImportError(
                    "parselmouth not installed. "
                    "Install with: pip install praat-parselmouth==0.4.3"
                ) from e
        return self._parselmouth
    
    @property
    def torchcrepe(self):
        """Lazy load torchcrepe"""
        if self._torchcrepe is None:
            try:
                import torchcrepe
                self._torchcrepe = torchcrepe
                logger.debug("Loaded torchcrepe")
            except ImportError as e:
                logger.error(f"Failed to import torchcrepe: {e}")
                raise ImportError(
                    "torchcrepe not installed. "
                    "Install with: pip install torchcrepe==0.0.23"
                ) from e
        return self._torchcrepe
    
    def check_all(self) -> Dict[str, Any]:
        """
        Verifica todas as dependências RVC
        
        Returns:
            Dict com status de cada dependência
        """
        results = {}
        
        dependencies = [
            ('tts_with_rvc', 'tts_with_rvc'),
            ('VC', 'VC'),
            ('Pipeline', 'Pipeline'),
            ('RMVPE', 'RMVPE'),
            ('fairseq', 'fairseq'),
            ('faiss', 'faiss'),
            ('librosa', 'librosa'),
            ('parselmouth', 'parselmouth'),
            ('torchcrepe', 'torchcrepe')
        ]
        
        for name, attr in dependencies:
            try:
                module = getattr(self, attr)
                results[name] = {
                    'available': True,
                    'version': getattr(module, '__version__', 'unknown')
                }
            except ImportError as e:
                results[name] = {
                    'available': False,
                    'error': str(e)
                }
        
        return results
    
    def is_ready(self) -> bool:
        """
        Verifica se todas as dependências RVC estão disponíveis
        
        Returns:
            True se todas deps estão OK, False caso contrário
        """
        results = self.check_all()
        return all(dep['available'] for dep in results.values())


# Singleton instance
rvc_deps = RvcDependencies()
