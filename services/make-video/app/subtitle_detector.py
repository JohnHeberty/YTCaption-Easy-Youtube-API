"""
TRSD - Temporal Region Subtitle Detector (Sprint 01: Base Architecture)

Detector inteligente de legendas embutidas baseado em:
- Análise por ROI (região de interesse)
- Detecção temporal de texto
- Classificação de texto dinâmico vs estático

Sprint 01: Arquitetura base e extração de regiões
"""

import cv2
import pytesseract
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
import logging
from dataclasses import dataclass

from app.trsd_models.text_region import TextLine, ROIType
from app.config import Settings

logger = logging.getLogger(__name__)


class TextRegionExtractor:
    """
    Extrator de regiões de texto por ROI
    
    Sprint 01: Implementa detecção OCR focada em regiões específicas do frame
    para otimizar performance e reduzir ruído.
    """
    
    def __init__(self, config: Optional[Settings] = None):
        self.config = config or Settings()
        
        # Configurações de downscaling
        self.target_width = self.config.trsd_downscale_width
        
        # Thresholds de filtro de conteúdo
        self.min_text_length = self.config.trsd_min_text_length
        self.min_confidence = self.config.trsd_min_confidence
        self.min_alpha_ratio = self.config.trsd_min_alpha_ratio
        
        # Parâmetros de agrupamento de palavras em linhas
        self.line_y_tolerance = self.config.trsd_line_y_tolerance
        self.line_x_gap = self.config.trsd_line_x_gap
        
        logger.info(f"TextRegionExtractor initialized: downscale={self.target_width}px")
    
    def extract_from_frame(
        self,
        frame: np.ndarray,
        timestamp: float,
        frame_idx: int = 0,
        roi_type: Optional[ROIType] = None
    ) -> List[TextLine]:
        """
        Extrai linhas de texto de um frame
        
        Args:
            frame: Frame BGR do vídeo
            timestamp: Timestamp do frame em segundos
            frame_idx: Índice do frame (para tracking temporal)
            roi_type: Tipo de ROI para focar (None = detectar todas)
        
        Returns:
            Lista de TextLines detectadas
        """
        # 1. Downscale frame
        frame_scaled, scale_factor = self._downscale_frame(frame)
        
        # 2. Extrair ROIs
        rois = self._extract_rois(frame_scaled) if roi_type is None else {roi_type: self._extract_single_roi(frame_scaled, roi_type)}
        
        # 3. OCR em cada ROI
        text_lines = []
        for roi_t, roi_img in rois.items():
            # Preprocessar ROI
            roi_prep = self._preprocess_roi(roi_img)
            
            # Detectar palavras com Tesseract
            words = self._detect_words(roi_prep)
            
            # Filtrar palavras
            words_filtered = self._filter_words(words)
            
            if not words_filtered:
                continue
            
            # Agrupar palavras em linhas
            lines = self._group_words_into_lines(words_filtered, scale_factor)
            
            # Criar TextLines
            for line_bbox, line_words in lines:
                text_line = self._create_text_line(
                    timestamp=timestamp,
                    frame_idx=frame_idx,
                    roi_type=roi_t,
                    bbox=line_bbox,
                    words=line_words
                )
                if text_line:
                    text_lines.append(text_line)
        
        logger.debug(f"Frame @ {timestamp:.2f}s: detected {len(text_lines)} lines")
        return text_lines
    
    def _downscale_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Downscale frame para otimizar OCR
        
        Returns:
            (frame_scaled, scale_factor)
        """
        h, w = frame.shape[:2]
        
        if w <= self.target_width:
            return frame, 1.0
        
        scale_factor = self.target_width / w
        new_h = int(h * scale_factor)
        
        frame_scaled = cv2.resize(frame, (self.target_width, new_h), interpolation=cv2.INTER_AREA)
        
        return frame_scaled, scale_factor
    
    def _extract_rois(self, frame: np.ndarray) -> dict:
        """
        Extrai ROIs (bottom, top, middle) do frame
        
        Returns:
            Dict {ROIType: roi_image}
        """
        h, w = frame.shape[:2]
        
        # Dividir frame em terços verticais
        third = h // 3
        
        rois = {
            ROIType.BOTTOM: frame[2*third:h, :],  # Terço inferior
            ROIType.TOP: frame[0:third, :],        # Terço superior
            ROIType.MIDDLE: frame[third:2*third, :]  # Centro
        }
        
        return rois
    
    def _extract_single_roi(self, frame: np.ndarray, roi_type: ROIType) -> np.ndarray:
        """Extrai uma ROI específica"""
        h, w = frame.shape[:2]
        third = h // 3
        
        if roi_type == ROIType.BOTTOM:
            return frame[2*third:h, :]
        elif roi_type == ROIType.TOP:
            return frame[0:third, :]
        else:  # MIDDLE
            return frame[third:2*third, :]
    
    def _preprocess_roi(self, roi: np.ndarray) -> np.ndarray:
        """
        Preprocessa ROI para melhorar OCR
        
        - Converte para grayscale
        - Aplica threshold adaptativo
        """
        # Grayscale
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        
        # Threshold adaptativo (melhora contraste)
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        return thresh
    
    def _detect_words(self, roi_prep: np.ndarray) -> List[dict]:
        """
        Detecta palavras com Tesseract
        
        Returns:
            Lista de dicts com {text, bbox, conf}
        """
        try:
            # Tesseract data
            data = pytesseract.image_to_data(
                roi_prep,
                output_type=pytesseract.Output.DICT,
                config='--psm 6'  # Assume uniform block of text
            )
            
            # Converter para lista de palavras
            words = []
            n_boxes = len(data['text'])
            
            for i in range(n_boxes):
                text = data['text'][i].strip()
                conf = float(data['conf'][i])
                
                if not text or conf < 0:
                    continue
                
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                
                words.append({
                    'text': text,
                    'bbox': (x, y, w, h),
                    'conf': conf / 100.0  # Normalizar [0-1]
                })
            
            return words
        
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return []
    
    def _filter_words(self, words: List[dict]) -> List[dict]:
        """
        Filtra palavras por confiança e conteúdo
        """
        filtered = []
        
        for word in words:
            text = word['text']
            conf = word['conf']
            
            # Filtro de confiança
            if conf < self.min_confidence:
                continue
            
            # Filtro de comprimento
            if len(text) < self.min_text_length:
                continue
            
            # Filtro de caracteres alfabéticos
            alpha_count = sum(c.isalpha() for c in text)
            alpha_ratio = alpha_count / len(text) if len(text) > 0 else 0
            
            if alpha_ratio < self.min_alpha_ratio:
                continue
            
            filtered.append(word)
        
        return filtered
    
    def _group_words_into_lines(
        self,
        words: List[dict],
        scale_factor: float
    ) -> List[Tuple[Tuple[int, int, int, int], List[dict]]]:
        """
        Agrupa palavras em linhas baseado em posição vertical
        
        Returns:
            Lista de (line_bbox, line_words)
        """
        if not words:
            return []
        
        # Ordenar palavras por posição Y, depois X
        words_sorted = sorted(words, key=lambda w: (w['bbox'][1], w['bbox'][0]))
        
        lines = []
        current_line = [words_sorted[0]]
        
        for word in words_sorted[1:]:
            prev_word = current_line[-1]
            
            # Checar se palavra está na mesma linha
            y_prev = prev_word['bbox'][1]
            y_curr = word['bbox'][1]
            x_prev_end = prev_word['bbox'][0] + prev_word['bbox'][2]
            x_curr = word['bbox'][0]
            
            y_diff = abs(y_curr - y_prev)
            x_gap = x_curr - x_prev_end
            
            # Mesma linha se Y próximo e X não muito distante
            if y_diff <= self.line_y_tolerance and x_gap <= self.line_x_gap:
                current_line.append(word)
            else:
                # Nova linha
                lines.append(current_line)
                current_line = [word]
        
        # Adicionar última linha
        if current_line:
            lines.append(current_line)
        
        # Calcular bboxes das linhas (escala original)
        line_data = []
        for line_words in lines:
            # Bbox que engloba todas as palavras
            xs = [w['bbox'][0] for w in line_words]
            ys = [w['bbox'][1] for w in line_words]
            x_ends = [w['bbox'][0] + w['bbox'][2] for w in line_words]
            y_ends = [w['bbox'][1] + w['bbox'][3] for w in line_words]
            
            x_min = min(xs)
            y_min = min(ys)
            x_max = max(x_ends)
            y_max = max(y_ends)
            
            # Escalar de volta para tamanho original
            line_bbox = (
                int(x_min / scale_factor),
                int(y_min / scale_factor),
                int((x_max - x_min) / scale_factor),
                int((y_max - y_min) / scale_factor)
            )
            
            line_data.append((line_bbox, line_words))
        
        return line_data
    
    def _create_text_line(
        self,
        timestamp: float,
        frame_idx: int,
        roi_type: ROIType,
        bbox: Tuple[int, int, int, int],
        words: List[dict]
    ) -> Optional[TextLine]:
        """
        Cria TextLine a partir de palavras agrupadas
        """
        if not words:
            return None
        
        # Texto completo
        text = ' '.join(w['text'] for w in words)
        
        # Confiança média
        avg_conf = sum(w['conf'] for w in words) / len(words)
        
        return TextLine(
            frame_ts=timestamp,
            frame_idx=frame_idx,
            roi_type=roi_type,
            text=text,
            bbox=bbox,
            confidence=avg_conf,
            words=words
        )
