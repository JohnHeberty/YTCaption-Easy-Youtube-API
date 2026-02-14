"""
TRSD - Temporal Tracking (Sprint 02)

Sistema de tracking de texto através de frames para análise de dinâmica temporal.
Rastreia regiões de texto entre frames para determinar se é legenda dinâmica ou texto estático.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from collections import defaultdict
import numpy as np
from Levenshtein import distance as levenshtein_distance

from app.trsd_models.text_region import TextLine, ROIType
from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """
    Representa um track de texto através do tempo
    
    Agrupa múltiplas detecções (TextLines) do mesmo texto que aparece
    em posições similares ao longo de vários frames.
    """
    track_id: int
    roi_type: ROIType
    detections: List[TextLine] = field(default_factory=list)
    
    # Métricas calculadas
    presence_ratio: float = 0.0      # % de frames onde aparece
    text_change_rate: float = 0.0    # Taxa de mudança de texto (0=estático, 1=sempre-muda)
    y_mean: float = 0.0              # Posição Y média
    y_std: float = 0.0               # Desvio padrão Y (estabilidade vertical)
    avg_confidence: float = 0.0      # Confiança média OCR
    
    def add_detection(self, text_line: TextLine):
        """Adiciona detecção ao track"""
        self.detections.append(text_line)
    
    def compute_metrics(self, total_frames: int):
        """
        Calcula métricas temporais do track
        
        Args:
            total_frames: Total de frames analisados
        """
        if not self.detections:
            return
        
        # Presence ratio: % de frames onde o track aparece
        self.presence_ratio = len(self.detections) / total_frames
        
        # Text change rate: quantas vezes o texto muda
        if len(self.detections) > 1:
            changes = 0
            for i in range(1, len(self.detections)):
                prev_text = self.detections[i-1].text
                curr_text = self.detections[i].text
                
                # Calcular similaridade com Levenshtein
                max_len = max(len(prev_text), len(curr_text))
                if max_len > 0:
                    dist = levenshtein_distance(prev_text, curr_text)
                    similarity = 1.0 - (dist / max_len)
                    
                    # Se similaridade < 0.7, considerar mudança
                    if similarity < 0.70:
                        changes += 1
            
            # CORREÇÃO: Proteção contra divisão por zero
            num_comparisons = len(self.detections) - 1
            self.text_change_rate = changes / num_comparisons if num_comparisons > 0 else 0.0
        else:
            self.text_change_rate = 0.0
        
        # Posição Y (estabilidade vertical)
        y_positions = [d.bbox[1] for d in self.detections]
        self.y_mean = np.mean(y_positions)
        self.y_std = np.std(y_positions)
        
        # Confiança média
        self.avg_confidence = np.mean([d.confidence for d in self.detections])
        
        logger.debug(
            f"Track {self.track_id}: presence={self.presence_ratio:.2f}, "
            f"change_rate={self.text_change_rate:.2f}, y_std={self.y_std:.1f}"
        )
    
    def __repr__(self):
        return (
            f"Track(id={self.track_id}, roi={self.roi_type.value}, "
            f"presence={self.presence_ratio:.2f}, change_rate={self.text_change_rate:.2f})"
        )


class TemporalTracker:
    """
    Rastreador temporal de texto
    
    Associa detecções de texto (TextLines) entre frames consecutivos
    para criar tracks temporais.
    """
    
    def __init__(self, config: Optional[Settings] = None):
        self.config = config or Settings()
        
        # Parâmetros de associação
        self.iou_threshold = self.config.trsd_track_iou_threshold
        self.max_distance_px = self.config.trsd_track_max_distance
        
        # Estado interno
        self.next_track_id = 1
        self.active_tracks: List[Track] = []
        self.total_frames = 0
        
        logger.info(
            f"TemporalTracker initialized: iou_threshold={self.iou_threshold}, "
            f"max_distance={self.max_distance_px}px"
        )
    
    def update(self, text_lines: List[TextLine], frame_idx: int):
        """
        Atualiza tracker com novas detecções
        
        Args:
            text_lines: Detecções do frame atual
            frame_idx: Índice do frame
        """
        self.total_frames += 1
        
        if frame_idx == 0 or not self.active_tracks:
            # Primeiro frame: criar novos tracks
            self._initialize_tracks(text_lines)
            return
        
        # Associar detecções aos tracks existentes
        self._associate_detections(text_lines)
    
    def finalize(self) -> List[Track]:
        """
        Finaliza tracking e retorna tracks completos com métricas
        
        Returns:
            Lista de tracks com métricas calculadas
        """
        # Calcular métricas de todos os tracks
        for track in self.active_tracks:
            track.compute_metrics(self.total_frames)
        
        logger.info(f"Finalized {len(self.active_tracks)} tracks from {self.total_frames} frames")
        
        return self.active_tracks
    
    def _initialize_tracks(self, text_lines: List[TextLine]):
        """Cria tracks iniciais a partir do primeiro frame"""
        for text_line in text_lines:
            track = Track(
                track_id=self.next_track_id,
                roi_type=text_line.roi_type
            )
            track.add_detection(text_line)
            self.active_tracks.append(track)
            self.next_track_id += 1
        
        logger.debug(f"Initialized {len(self.active_tracks)} tracks")
    
    def _associate_detections(self, text_lines: List[TextLine]):
        """
        Associa detecções atuais aos tracks existentes
        
        Usa IoU + distância para matching
        """
        # Agrupar tracks por ROI
        tracks_by_roi = defaultdict(list)
        for track in self.active_tracks:
            tracks_by_roi[track.roi_type].append(track)
        
        # Agrupar detecções por ROI
        detections_by_roi = defaultdict(list)
        for text_line in text_lines:
            detections_by_roi[text_line.roi_type].append(text_line)
        
        # Associar dentro de cada ROI
        for roi_type in ROIType:
            tracks = tracks_by_roi.get(roi_type, [])
            detections = detections_by_roi.get(roi_type, [])
            
            if not tracks or not detections:
                continue
            
            # Calcular matriz de custos (baseada em IoU + distância)
            cost_matrix = self._compute_cost_matrix(tracks, detections)
            
            # Matching guloso (greedy)
            matches, unmatched_detections = self._greedy_matching(
                cost_matrix, tracks, detections
            )
            
            # Atualizar tracks matched
            for track_idx, detection_idx in matches:
                tracks[track_idx].add_detection(detections[detection_idx])
            
            # Criar novos tracks para detecções não matched
            for detection_idx in unmatched_detections:
                track = Track(
                    track_id=self.next_track_id,
                    roi_type=roi_type
                )
                track.add_detection(detections[detection_idx])
                self.active_tracks.append(track)
                self.next_track_id += 1
    
    def _compute_cost_matrix(
        self,
        tracks: List[Track],
        detections: List[TextLine]
    ) -> np.ndarray:
        """
        Calcula matriz de custos para associação
        
        Custo = 1.0 - (IoU * 0.7 + distance_similarity * 0.3)
        
        Returns:
            Matriz NxM onde N=tracks, M=detections
        """
        n_tracks = len(tracks)
        n_detections = len(detections)
        
        cost_matrix = np.ones((n_tracks, n_detections)) * 999.0  # Custo alto padrão
        
        for i, track in enumerate(tracks):
            # Última detecção do track
            last_detection = track.detections[-1]
            last_bbox = last_detection.bbox
            
            for j, detection in enumerate(detections):
                curr_bbox = detection.bbox
                
                # Calcular IoU
                iou = self._calculate_iou(last_bbox, curr_bbox)
                
                # Calcular distância entre centros
                dist = self._calculate_distance(last_bbox, curr_bbox)
                dist_similarity = max(0.0, 1.0 - (dist / self.max_distance_px))
                
                # Custo combinado
                similarity = iou * 0.7 + dist_similarity * 0.3
                cost = 1.0 - similarity
                
                # Se custo muito alto (baixa similaridade), descartar
                if iou < self.iou_threshold and dist > self.max_distance_px:
                    cost = 999.0
                
                cost_matrix[i, j] = cost
        
        return cost_matrix
    
    def _greedy_matching(
        self,
        cost_matrix: np.ndarray,
        tracks: List[Track],
        detections: List[TextLine]
    ) -> Tuple[List[Tuple[int, int]], List[int]]:
        """
        Matching guloso baseado em custo mínimo
        
        Returns:
            (matches, unmatched_detection_indices)
        """
        matches = []
        matched_tracks = set()
        matched_detections = set()
        
        # Ordenar por custo crescente
        n_tracks, n_detections = cost_matrix.shape
        costs_flat = []
        
        for i in range(n_tracks):
            for j in range(n_detections):
                if cost_matrix[i, j] < 999.0:
                    costs_flat.append((cost_matrix[i, j], i, j))
        
        costs_flat.sort()
        
        # Atribuir matches
        for cost, track_idx, detection_idx in costs_flat:
            if track_idx in matched_tracks or detection_idx in matched_detections:
                continue
            
            matches.append((track_idx, detection_idx))
            matched_tracks.add(track_idx)
            matched_detections.add(detection_idx)
        
        # Detecções não matched
        unmatched_detections = [
            j for j in range(n_detections)
            if j not in matched_detections
        ]
        
        return matches, unmatched_detections
    
    def _calculate_iou(
        self,
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int]
    ) -> float:
        """
        Calcula IoU (Intersection over Union) entre duas bboxes
        
        Args:
            bbox1, bbox2: (x, y, w, h)
        
        Returns:
            IoU [0.0, 1.0]
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Coordenadas dos retângulos
        x1_min, y1_min = x1, y1
        x1_max, y1_max = x1 + w1, y1 + h1
        
        x2_min, y2_min = x2, y2
        x2_max, y2_max = x2 + w2, y2 + h2
        
        # Interseção
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        inter_w = max(0, inter_x_max - inter_x_min)
        inter_h = max(0, inter_y_max - inter_y_min)
        inter_area = inter_w * inter_h
        
        # União
        area1 = w1 * h1
        area2 = w2 * h2
        union_area = area1 + area2 - inter_area
        
        if union_area == 0:
            return 0.0
        
        iou = inter_area / union_area
        return iou
    
    def _calculate_distance(
        self,
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int]
    ) -> float:
        """
        Calcula distância Euclidiana entre centros de duas bboxes
        
        Args:
            bbox1, bbox2: (x, y, w, h)
        
        Returns:
            Distância em pixels
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        center1_x = x1 + w1 / 2
        center1_y = y1 + h1 / 2
        
        center2_x = x2 + w2 / 2
        center2_y = y2 + h2 / 2
        
        dist = np.sqrt((center2_x - center1_x)**2 + (center2_y - center1_y)**2)
        return dist
