"""
PaddleOCR Detector - Single Engine System

Engine: PaddleOCR ONLY (high precision, supports PT/EN)
Features: Thread-safe, GPU support, Singleton pattern

⚠️ IMPORTANTE: Este módulo usa APENAS PaddleOCR.
   Tesseract e EasyOCR NÃO são permitidos no projeto.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
import threading
import logging
import os

logger = logging.getLogger(__name__)

# Importar PaddleOCR (ÚNICO engine permitido)
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except ImportError:
    logger.error("❌ PaddleOCR not installed. Install with: pip install paddleocr")
    PADDLE_AVAILABLE = False


@dataclass
class OCRResult:
    """Resultado de detecção OCR"""
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    engine: str = 'paddleocr'


class PaddleOCRDetector:
    """
    PaddleOCR Detector - Single Engine
    
    Features:
    - PaddleOCR como único engine (alta precisão)
    - Thread-safe com locks
    - Singleton pattern
    - GPU support
    """
    
    def __init__(self, use_gpu: bool = False):
        """
        Inicializa detector com PaddleOCR
        
        Args:
            use_gpu: Usar GPU para PaddleOCR (requer CUDA)
        """
        if not PADDLE_AVAILABLE:
            raise RuntimeError("PaddleOCR not available. Cannot initialize detector.")
        
        self.use_gpu = use_gpu
        self._lock = threading.Lock()
        
        # Inicializar PaddleOCR
        logger.info(f"Initializing PaddleOCR ({'GPU' if use_gpu else 'CPU'})...")
        
        # PaddleOCR 2.7.3 usa 'use_gpu' (versões antigas usam esta flag)
        # Nota: Resolvido MKL error com downgrade para 2.7.3 + NumPy 1.26.4
        
        try:
            self.paddle_ocr = PaddleOCR(
                use_angle_cls=True,
                lang='en',  # Suporta inglês e português
                use_gpu=use_gpu,
                det_db_thresh=0.3,
                det_db_box_thresh=0.5,
                rec_batch_num=6,
                show_log=False
            )
            logger.info("✅ PaddleOCR 2.7.3 initialized (MKL error resolved)")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise
    
    def detect_text(self, frame: np.ndarray) -> List[OCRResult]:
        """
        Detecta texto em frame usando PaddleOCR
        
        Args:
            frame: Frame BGR do OpenCV
            
        Returns:
            Lista de OCRResult com textos detectados
        """
        with self._lock:
            # PaddleOCR detection
            results = self._run_paddleocr(frame)
            return results
    
    def detect_subtitle_in_frame(
        self,
        frame: np.ndarray,
        min_confidence: float = 60.0
    ):
        """
        Detecta legenda em frame (compatibilidade com calibrador)
        
        Args:
            frame: Frame BGR do cv2
            min_confidence: Confiança mínima (0-100)
        
        Returns:
            Objeto com atributos: has_subtitle, confidence, readable_words
        """
        results = self.detect_text(frame)
        
        # Filtrar por confiança
        filtered = [r for r in results if r.confidence * 100 >= min_confidence]
        
        # Extrair texto limpo
        texts = [r.text.strip() for r in filtered if r.text.strip()]
        
        # Criar resultado compatível
        class DetectionResult:
            def __init__(self, has_subtitle, confidence, readable_words):
                self.has_subtitle = has_subtitle
                self.confidence = confidence
                self.readable_words = readable_words
        
        has_sub = len(texts) > 0
        conf = max([r.confidence * 100 for r in filtered], default=0.0)
        
        return DetectionResult(has_sub, conf, texts)
    
    def _run_paddleocr(self, frame: np.ndarray) -> List[OCRResult]:
        """
        Executa PaddleOCR no frame
        
        Args:
            frame: Frame BGR preprocessado
            
        Returns:
            Lista de OCRResult do PaddleOCR
        """
        try:
            # Preprocessar frame
            processed = self._preprocess_frame(frame)
            
            # Executar PaddleOCR
            results = self.paddle_ocr.ocr(processed, cls=True)
            
            if not results or not results[0]:
                return []
            
            ocr_results = []
            
            for line in results[0]:
                # line format: [bbox, (text, confidence)]
                bbox_points = line[0]
                text = line[1][0]
                conf = line[1][1]
                
                # Converter bbox points para (x, y, w, h)
                x_coords = [p[0] for p in bbox_points]
                y_coords = [p[1] for p in bbox_points]
                
                x = int(min(x_coords))
                y = int(min(y_coords))
                w = int(max(x_coords) - x)
                h = int(max(y_coords) - y)
                
                ocr_results.append(OCRResult(
                    text=text,
                    confidence=conf,
                    bbox=(x, y, w, h),
                    engine='paddleocr'
                ))
            
            return ocr_results
            
        except Exception as e:
            logger.warning(f"⚠️ PaddleOCR failed: {e}")
            return []
    
    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Pré-processamento otimizado para OCR
        
        Args:
            frame: Frame BGR original (3 channels)
            
        Returns:
            Frame preprocessado BGR (3 channels) - PaddleOCR requer BGR/RGB
        """
        # PaddleOCR requer 3 channels (BGR ou RGB)
        # Então NÃO convertemos para grayscale
        
        # Opção 1: Aplicar CLAHE em cada canal BGR separadamente
        # Opção 2: Retornar frame original (OCR models já fazem preprocessing interno)
        
        # Por enquanto: retornar frame original
        # PaddleOCR já faz preprocessing interno otimizado
        return frame


# Singleton instance
_ocr_detector_instance = None
_ocr_detector_lock = threading.Lock()


def get_ocr_detector():
    """
    Retorna instância singleton do OCR Detector (PaddleOCR ONLY)
    
    Thread-safe double-check locking
    
    ⚠️ IMPORTANTE: Apenas PaddleOCR é permitido. 
       Se houver erro MKL, deve ser resolvido, NÃO usar fallback.
    
    Returns:
        PaddleOCRDetector instance
        
    Raises:
        RuntimeError: Se PaddleOCR não estiver disponível ou falhar
    """
    global _ocr_detector_instance
    
    if _ocr_detector_instance is None:
        with _ocr_detector_lock:
            if _ocr_detector_instance is None:
                if not PADDLE_AVAILABLE:
                    raise RuntimeError(
                        "PaddleOCR not available. Install with: pip install paddleocr\n"
                        "⚠️ Tesseract/EasyOCR fallbacks are NOT permitted in this project."
                    )
                
                try:
                    use_gpu = _detect_gpu()
                    logger.info("Initializing PaddleOCR (ONLY engine)...")
                    _ocr_detector_instance = PaddleOCRDetector(use_gpu=use_gpu)
                    logger.info("✅ PaddleOCR initialized successfully")
                except Exception as e:
                    logger.error(f"❌ PaddleOCR initialization failed: {e}")
                    logger.error("⚠️ BLOCKER: PaddleOCR must be fixed. See sprints/PROGRESS_SPRINT_00.md")
                    raise RuntimeError(
                        f"PaddleOCR initialization failed: {e}\n"
                        f"Please resolve PaddleOCR MKL error (see PROGRESS_SPRINT_00.md)\n"
                        f"⚠️ Tesseract/EasyOCR fallbacks are NOT permitted."
                    )
    
    return _ocr_detector_instance


def _detect_gpu() -> bool:
    """
    Detecta se GPU está disponível
    
    Returns:
        True se GPU disponível e configurado
    """
    # Verificar variável de ambiente
    gpu_env = os.getenv('OCR_USE_GPU', 'false').lower().strip()
    use_gpu_env = gpu_env in ('true', '1', 'yes', 'on')
    
    if not use_gpu_env:
        return False
    
    # Verificar CUDA
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("✅ GPU detected and enabled for PaddleOCR")
            return True
        else:
            logger.warning("⚠️ OCR_USE_GPU=true but CUDA not available. Using CPU.")
            return False
    except ImportError:
        logger.warning("⚠️ PyTorch not installed. Using CPU.")
        return False
