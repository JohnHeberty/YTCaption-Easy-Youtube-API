"""
OCR Detection Module

Detecta presença de legendas em frames usando Tesseract OCR
"""

import cv2
import numpy as np
import pytesseract
import logging
from typing import Tuple, Optional, List
from dataclasses import dataclass
from app.metrics import ocr_confidence_distribution

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Resultado de OCR em um frame"""
    text: str
    confidence: float
    word_count: int
    has_subtitle: bool


class OCRDetector:
    """
    Detector de legendas usando OCR
    
    Detecta presença de legendas na região inferior do vídeo
    """
    
    def __init__(self, subtitle_region_height: float = 0.15):
        """
        Args:
            subtitle_region_height: Porcentagem da altura do frame para ROI (0.0-1.0)
        """
        self.subtitle_region_height = subtitle_region_height
        logger.info(f"OCRDetector initialized (ROI height: {subtitle_region_height:.0%})")
    
    def detect_subtitle_in_frame(
        self,
        frame: np.ndarray,
        min_confidence: float = 60.0
    ) -> OCRResult:
        """
        Detecta legenda em um frame
        
        Args:
            frame: Frame BGR do cv2
            min_confidence: Confiança mínima para considerar legenda
        
        Returns:
            OCRResult com texto e confiança
        """
        # Extrair ROI (região inferior)
        roi = self._extract_roi(frame)
        
        # Pré-processar para melhorar OCR
        processed = self._preprocess_for_ocr(roi)
        
        # Executar OCR
        ocr_data = pytesseract.image_to_data(
            processed,
            lang='eng+por',
            output_type=pytesseract.Output.DICT
        )
        
        # Analisar resultado
        text, confidence, word_count = self._parse_ocr_result(ocr_data)
        
        # Decidir se tem legenda
        has_subtitle = confidence >= min_confidence and word_count >= 2
        
        # Registrar métrica
        ocr_confidence_distribution.observe(confidence)
        
        logger.debug(
            f"OCR result: confidence={confidence:.1f}, "
            f"words={word_count}, has_subtitle={has_subtitle}"
        )
        
        return OCRResult(
            text=text,
            confidence=confidence,
            word_count=word_count,
            has_subtitle=has_subtitle
        )
    
    def _extract_roi(self, frame: np.ndarray) -> np.ndarray:
        """
        Extrai região de interesse (ROI) - parte inferior do frame
        
        Args:
            frame: Frame completo
        
        Returns:
            ROI com legendas (parte inferior)
        """
        height, width = frame.shape[:2]
        roi_height = int(height * self.subtitle_region_height)
        
        # ROI = parte inferior do frame
        roi = frame[height - roi_height:, :]
        
        return roi
    
    def _preprocess_for_ocr(self, roi: np.ndarray) -> np.ndarray:
        """
        Pré-processa ROI para melhorar OCR
        
        - Converte para grayscale
        - Aplica threshold adaptativo
        - Inverte cores (texto branco → preto)
        
        Args:
            roi: ROI em BGR
        
        Returns:
            Imagem processada para OCR
        """
        # Converter para grayscale
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Threshold adaptativo (binarização)
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )
        
        # Inverter cores se necessário (texto branco em fundo preto → preto em branco)
        # Tesseract funciona melhor com texto escuro em fundo claro
        mean_val = np.mean(binary)
        if mean_val < 127:  # Imagem predominantemente escura
            binary = cv2.bitwise_not(binary)
        
        return binary
    
    def _parse_ocr_result(self, ocr_data: dict) -> Tuple[str, float, int]:
        """
        Parseia resultado do Tesseract
        
        Args:
            ocr_data: Dict retornado por image_to_data
        
        Returns:
            (texto, confiança_média, contagem_palavras)
        """
        # Filtrar palavras com confiança válida (> -1)
        valid_words = [
            (text, conf)
            for text, conf in zip(ocr_data['text'], ocr_data['conf'])
            if conf > 0 and text.strip()
        ]
        
        if not valid_words:
            return "", 0.0, 0
        
        # Extrair texto e confiança
        texts, confidences = zip(*valid_words)
        
        # Texto completo
        full_text = " ".join(texts)
        
        # Confiança média
        avg_confidence = sum(confidences) / len(confidences)
        
        # Contagem de palavras
        word_count = len(valid_words)
        
        return full_text, avg_confidence, word_count
    
    def extract_frame_at_timestamp(
        self,
        video_path: str,
        timestamp: float
    ) -> Optional[np.ndarray]:
        """
        Extrai frame em um timestamp específico
        
        Args:
            video_path: Path do vídeo
            timestamp: Timestamp em segundos
        
        Returns:
            Frame BGR ou None se falhar
        """
        cap = cv2.VideoCapture(video_path)
        
        try:
            # Setar posição do vídeo
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            
            # Ler frame
            ret, frame = cap.read()
            
            if not ret:
                logger.warning(f"Failed to extract frame at {timestamp}s")
                return None
            
            return frame
        
        finally:
            cap.release()
