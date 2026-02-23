"""
Visual Features Analyzer

Analisa características visuais de texto para distinguir legendas de outros elementos
"""

import cv2
import numpy as np
from typing import Dict, Tuple, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class VisualFeatures:
    """Features visuais extraídas do frame"""
    
    # Posição
    text_vertical_position: str  # 'top', 'middle', 'bottom', 'none'
    distance_from_bottom_pct: float  # % distância do fundo
    
    # Contraste
    avg_contrast: float  # 0-255
    has_outline: bool
    
    # Tamanho
    avg_text_height_pct: float  # % da altura do frame
    avg_text_width_pct: float   # % da largura do frame
    
    # Forma
    aspect_ratio: float  # largura / altura
    
    # Cor
    dominant_text_color: Tuple[int, int, int]  # BGR
    dominant_bg_color: Tuple[int, int, int]
    
    # Score de "legenda-likeness"
subtitle_score: float  # 0-100


class VisualFeaturesAnalyzer:
    """
    Analisa features visuais para distinguir legendas de outros textos
    
    Pattern: Feature Engineering para ML
    
    Legendas típicas têm:
    - Posição: bottom 5-20% da tela
    - Alto contraste com fundo
    - Outline/sombra (legibilidade)
    - Fonte 5-10% da altura
    - Aspect ratio > 3 (horizontal)
    """
    
    def __init__(self):
        self.frame_height = None
        self.frame_width = None
    
    def analyze_frame_with_text(
        self,
        frame: np.ndarray,
        text_bboxes: List[List]
    ) -> VisualFeatures:
        """
        Analisa features visuais em frame com texto detectado
        
        Args:
            frame: Frame BGR
            text_bboxes: Lista de bounding boxes do OCR
                         Formato: [[x1,y1, x2,y2, x3,y3, x4,y4], ...]
        
        Returns:
            VisualFeatures extraídas
        """
        self.frame_height, self.frame_width = frame.shape[:2]
        
        if not text_bboxes:
            return self._empty_features()
        
        # Feature 1: Posição Vertical
        vertical_pos, dist_from_bottom = self._analyze_vertical_position(text_bboxes)
        
        # Feature 2: Contraste
        avg_contrast, has_outline = self._analyze_contrast(frame, text_bboxes)
        
        # Feature 3: Tamanho
        avg_height_pct, avg_width_pct = self._analyze_size(text_bboxes)
        
        # Feature 4: Aspect Ratio
        aspect_ratio = self._calculate_aspect_ratio(text_bboxes)
        
        # Feature 5: Cores
        text_color, bg_color = self._analyze_colors(frame, text_bboxes)
        
        # Calcular score de legenda
        subtitle_score = self._calculate_subtitle_score(
            vertical_pos, dist_from_bottom, avg_contrast, has_outline,
            avg_height_pct, aspect_ratio
        )
        
        return VisualFeatures(
            text_vertical_position=vertical_pos,
            distance_from_bottom_pct=dist_from_bottom,
            avg_contrast=avg_contrast,
            has_outline=has_outline,
            avg_text_height_pct=avg_height_pct,
            avg_text_width_pct=avg_width_pct,
            aspect_ratio=aspect_ratio,
            dominant_text_color=text_color,
            dominant_bg_color=bg_color,
            subtitle_score=subtitle_score
        )
    
    def _analyze_vertical_position(
        self,
        text_bboxes: List[List]
    ) -> Tuple[str, float]:
        """Analisa posição vertical do texto"""
        
        # Calcular centro Y de cada bbox
        y_centers = []
        for bbox in text_bboxes:
            # bbox pode ser [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] ou [x1,y1,x2,y2,x3,y3,x4,y4]
            if isinstance(bbox[0], (list, tuple)):
                y_coords = [p[1] for p in bbox]
            else:
                # Flatten: [x1,y1,x2,y2 ,x3,y3,x4,y4]
                y_coords = [bbox[i] for i in range(1, len(bbox), 2)]
            
            y_center = np.mean(y_coords)
            y_centers.append(y_center)
        
        avg_y = np.mean(y_centers)
        y_pct = avg_y / self.frame_height
        
        # Classificar posição
        if y_pct < 0.33:
            position = 'top'
        elif y_pct > 0.67:
            position = 'bottom'
        else:
            position = 'middle'
        
        # Distância do fundo (legendas geralmente em 80-95% da altura)
        dist_from_bottom_pct = (1.0 - y_pct) * 100
        
        return position, dist_from_bottom_pct
    
    def _analyze_contrast(
        self,
        frame: np.ndarray,
        text_bboxes: List[List]
    ) -> Tuple[float, bool]:
        """Analisa contraste do texto"""
        
        contrasts = []
        has_outline_count = 0
        
        for bbox in text_bboxes:
            # Extrair coordenadas
            if isinstance(bbox[0], (list, tuple)):
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
            else:
                x_coords = [bbox[i] for i in range(0, len(bbox), 2)]
                y_coords = [bbox[i] for i in range(1, len(bbox), 2)]
            
            x_min, x_max = int(min(x_coords)), int(max(x_coords))
            y_min, y_max = int(min(y_coords)), int(max(y_coords))
            
            # Garantir dentro dos bounds
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(self.frame_width, x_max)
            y_max = min(self.frame_height, y_max)
            
            if x_max <= x_min or y_max <= y_min:
                continue
            
            roi = frame[y_min:y_max, x_min:x_max]
            
            if roi.size == 0:
                continue
            
            # Calcular contraste (desvio padrão de intensidade)
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            contrast = np.std(gray_roi)
            contrasts.append(contrast)
            
            # Detectar outline (bordas pretas ou brancas)
            edges = cv2.Canny(gray_roi, 50, 150)
            edge_ratio = np.sum(edges > 0) / edges.size if edges.size > 0 else 0
            
            if edge_ratio > 0.1:  # >10% de bordas
                has_outline_count += 1
        
        avg_contrast = np.mean(contrasts) if contrasts else 0.0
        has_outline = has_outline_count >= len(text_bboxes) * 0.5 if text_bboxes else False
        
        return avg_contrast, has_outline
    
    def _analyze_size(self, text_bboxes: List[List]) -> Tuple[float, float]:
        """Analisa tamanho do texto"""
        
        heights = []
        widths = []
        
        for bbox in text_bboxes:
            if isinstance(bbox[0], (list, tuple)):
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
            else:
                x_coords = [bbox[i] for i in range(0, len(bbox), 2)]
                y_coords = [bbox[i] for i in range(1, len(bbox), 2)]
            
            width = max(x_coords) - min(x_coords)
            height = max(y_coords) - min(y_coords)
            
            heights.append(height)
            widths.append(width)
        
        avg_height = np.mean(heights) if heights else 0
        avg_width = np.mean(widths) if widths else 0
        
        # Normalizar pela resolução do frame
        avg_height_pct = (avg_height / self.frame_height) * 100 if self.frame_height > 0 else 0
        avg_width_pct = (avg_width / self.frame_width) * 100 if self.frame_width > 0 else 0
        
        return avg_height_pct, avg_width_pct
    
    def _calculate_aspect_ratio(self, text_bboxes: List[List]) -> float:
        """Calcula aspect ratio médio do texto"""
        
        aspect_ratios = []
        
        for bbox in text_bboxes:
            if isinstance(bbox[0], (list, tuple)):
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
            else:
                x_coords = [bbox[i] for i in range(0, len(bbox), 2)]
                y_coords = [bbox[i] for i in range(1, len(bbox), 2)]
            
            width = max(x_coords) - min(x_coords)
            height = max(y_coords) - min(y_coords)
            
            if height > 0:
                ar = width / height
                aspect_ratios.append(ar)
        
        return np.mean(aspect_ratios) if aspect_ratios else 0.0
    
    def _analyze_colors(
        self,
        frame: np.ndarray,
        text_bboxes: List[List]
    ) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """Analisa cores dominantes (texto e fundo)"""
        
        text_colors = []
        
        for bbox in text_bboxes:
            if isinstance(bbox[0], (list, tuple)):
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
            else:
                x_coords = [bbox[i] for i in range(0, len(bbox), 2)]
                y_coords = [bbox[i] for i in range(1, len(bbox), 2)]
            
            x_min, x_max = int(min(x_coords)), int(max(x_coords))
            y_min, y_max = int(min(y_coords)), int(max(y_coords))
            
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(self.frame_width, x_max)
            y_max = min(self.frame_height, y_max)
            
            if x_max <= x_min or y_max <= y_min:
                continue
            
            roi = frame[y_min:y_max, x_min:x_max]
            
            if roi.size > 0:
                avg_color = np.mean(roi, axis=(0, 1))
                text_colors.append(tuple(avg_color.astype(int)))
        
        if text_colors:
            text_color = tuple(np.mean(text_colors, axis=0).astype(int))
        else:
            text_color = (255, 255, 255)
        
        # Background: média do frame inteiro
        bg_color = tuple(np.mean(frame, axis=(0, 1)).astype(int))
        
        return text_color, bg_color
    
    def _calculate_subtitle_score(
        self,
        vertical_pos: str,
        dist_from_bottom_pct: float,
        avg_contrast: float,
        has_outline: bool,
        avg_height_pct: float,
        aspect_ratio: float
    ) -> float:
        """
        Calcula score de probabilidade de ser legenda (0-100)
        
        Heurísticas baseadas em padrões conhecidos de legendas
        """
        score = 0.0
        
        # 1. Posição (peso: 30 pontos)
        if vertical_pos == 'bottom':
            score += 30
            # Bonus se estiver em posição típica de legenda (5-20% do fundo)
            if 5 <= dist_from_bottom_pct <= 20:
                score += 10
        elif vertical_pos == 'top':
            score += 15  # Menos comum, mas possível
        else:
            score += 0  # Legendas raramente no centro
        
        # 2. Contraste (peso: 20 pontos)
        if avg_contrast > 60:
            score += 20
        elif avg_contrast > 40:
            score += 10
        
        # 3. Outline (peso: 15 pontos)
        if has_outline:
            score += 15
        
        # 4. Tamanho da fonte (peso: 15 pontos)
        # Legendas típicas: 5-10% da altura do frame
        if 4 <= avg_height_pct <= 12:
            score += 15
        elif 2 <= avg_height_pct <= 15:
            score += 7
        
        # 5. Aspect Ratio (peso: 20 pontos)
        # Legendas são horizontais (largura >> altura)
        if aspect_ratio > 5:
            score += 20
        elif aspect_ratio > 3:
            score += 10
        
        return min(score, 100)  # Cap em 100
    
    def _empty_features(self) -> VisualFeatures:
        """Retorna features vazias"""
        return VisualFeatures(
            text_vertical_position='none',
            distance_from_bottom_pct=0.0,
            avg_contrast=0.0,
            has_outline=False,
            avg_text_height_pct=0.0,
            avg_text_width_pct=0.0,
            aspect_ratio=0.0,
            dominant_text_color=(0, 0, 0),
            dominant_bg_color=(0, 0, 0),
            subtitle_score=0.0
        )
