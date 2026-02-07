"""
Modelos de regiões de texto para detecção de legendas
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, List


class ROIType(Enum):
    """Tipo de ROI onde texto foi detectado"""
    BOTTOM = 'bottom'  # Terço inferior (legendas)
    TOP = 'top'        # Terço superior
    MIDDLE = 'middle'  # Centro


@dataclass
class TextLine:
    """
    Representa uma linha de texto detectada em um frame
    
    Agrupa múltiplas palavras (bboxes) detectadas pelo OCR em uma linha lógica
    baseada em proximidade vertical e horizontal.
    """
    frame_ts: float           # Timestamp do frame (segundos)
    frame_idx: int            # Índice do frame (para tracking temporal)
    roi_type: ROIType         # Região onde foi detectado
    text: str                 # Texto completo da linha
    bbox: Tuple[int, int, int, int]  # Bounding box da linha (x, y, w, h)
    confidence: float         # Confiança média do OCR
    words: List[dict]         # Palavras individuais (para debug)
    
    def __repr__(self):
        return f"TextLine(ts={self.frame_ts:.2f}s, roi={self.roi_type.value}, text='{self.text[:30]}...', conf={self.confidence:.2f})"
