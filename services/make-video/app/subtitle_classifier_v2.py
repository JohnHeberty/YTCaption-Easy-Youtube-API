"""
TRSD v2 - Advanced Subtitle Classifier (Sprint 08 Rewrite)

Sistema de classificação avançado com 6 métricas temporais sofisticadas
para alcançar 90%+ de precisão na detecção de legendas hardcoded.

Autor: Reescrito do zero para eliminar falsos positivos
Data: 2026-02-07
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import numpy as np
from collections import Counter

from app.temporal_tracker import Track
from app.trsd_models.text_region import ROIType
from app.config import Settings

logger = logging.getLogger(__name__)


class TrackCategory(Enum):
    """Categorias de classificação"""
    SUBTITLE = 'subtitle'              # Legenda hardcoded (BLOQUEAR)
    STATIC_TEXT = 'static_text'        # Texto estático (logo, watermark)
    ANIMATED_LOGO = 'animated_logo'    # Logo com animação/mudança
    SCREENCAST = 'screencast'          # Uso de aplicativo
    NOISE = 'noise'                    # Ruído/artefato OCR


@dataclass
class AdvancedMetrics:
    """Métricas avançadas de um track"""
    
    # 1. Temporal Rhythm (ciclos de aparição)
    avg_gap_duration: float            # Duração média entre aparições (segundos)
    gap_regularity: float              # Regularidade dos gaps (0-1, 1=regular)
    num_gaps: int                      # Número de gaps detectados
    
    # 2. Life Span (duração de cada texto)
    avg_text_lifespan: float           # Duração média de cada texto único (segundos)
    max_text_lifespan: float           # Maior duração de um texto
    
    # 3. Position Stability
    y_position_variance: float         # Variância da posição Y
    position_stability_score: float    # Score de estabilidade (0-1, 1=estável)
    
    # 4. Text Uniqueness
    unique_text_ratio: float           # % de textos únicos vs total
    num_unique_texts: int              # Número de textos diferentes
    
    # 5. Vertical Bias
    bottom_roi_ratio: float            # % de detecções no ROI bottom
    
    # 6. Temporal Density
    detections_per_second: float       # Detecções por segundo
    text_changes_per_second: float     # Mudanças de texto por segundo


@dataclass
class ClassificationResult:
    """Resultado da classificação"""
    has_subtitles: bool
    confidence: float
    reason: str
    decision_logic: str
    
    # Detalhamento
    tracks_by_category: Dict[str, int]
    subtitle_tracks: List[Track]
    metrics_summary: Dict[str, any]


class SubtitleClassifierV2:
    """
    Classificador avançado com 6 métricas temporais
    
    Projetado para 90%+ de precisão eliminando falsos positivos
    através de análise profunda de padrões temporais.
    """
    
    def __init__(self, config: Optional[Settings] = None, fps: float = 3.0):
        self.config = config or Settings()
        self.fps = fps
        
        # === THRESHOLDS OTIMIZADOS (baseados em análise) ===
        
        # 1. Temporal Rhythm (legendas têm gaps regulares de 0.5-2s)
        self.subtitle_gap_min = 0.3       # Min gap entre legendas (segundos)
        self.subtitle_gap_max = 3.0       # Max gap entre legendas
        self.gap_regularity_min = 0.4     # Min regularidade (0-1)
        
        # 2. Life Span (cada legenda dura 2-5s)
        self.subtitle_lifespan_min = 0.5  # Min duração de uma legenda
        self.subtitle_lifespan_max = 8.0  # Max duração de uma legenda
        
        # 3. Position Stability (legendas ficam na mesma altura)
        self.position_stability_min = 0.85  # Min estabilidade para legendas
        
        # 4. Text Uniqueness (legendas têm muitos textos diferentes)
        self.subtitle_uniqueness_min = 0.6  # Min % de textos únicos
        
        # 5. Vertical Bias (legendas no bottom)
        self.subtitle_bottom_ratio_min = 0.7  # Min % no bottom
        
        # 6. Temporal Density (legendas têm alta densidade)
        self.subtitle_density_min = 0.15    # Min mudanças/segundo
        
        # Filtros gerais
        self.min_detections = 3            # Min detecções para considerar
        self.noise_confidence_threshold = 0.5  # Max confidence para noise
        
        logger.info("SubtitleClassifierV2 initialized with advanced metrics")
    
    def decide(self, tracks: List[Track]) -> ClassificationResult:
        """
        Classifica tracks e decide bloqueio
        
        Args:
            tracks: Lista de tracks do TemporalTracker
            
        Returns:
            ClassificationResult com decisão final
        """
        # Filtrar tracks com poucas detecções (ruído)
        valid_tracks = [t for t in tracks if len(t.detections) >= self.min_detections]
        
        if not valid_tracks:
            return self._no_text_result()
        
        # Calcular métricas avançadas para cada track
        subtitle_tracks = []
        other_tracks = []
        
        for track in valid_tracks:
            metrics = self._compute_advanced_metrics(track)
            category = self._classify_track_v2(track, metrics)
            
            if category == TrackCategory.SUBTITLE:
                subtitle_tracks.append((track, metrics))
            else:
                other_tracks.append((track, metrics, category))
        
        # Decisão final
        return self._make_final_decision(subtitle_tracks, other_tracks, valid_tracks)
    
    def _compute_advanced_metrics(self, track: Track) -> AdvancedMetrics:
        """
        Calcula as 6 métricas avançadas de um track
        
        Args:
            track: Track do TemporalTracker
            
        Returns:
            AdvancedMetrics com todas as métricas calculadas
        """
        detections = track.detections
        num_detections = len(detections)
        
        # === 1. TEMPORAL RHYTHM ===
        frame_indices = [d.frame_idx for d in detections]
        gaps = self._calculate_gaps(frame_indices)
        
        if gaps:
            gap_durations_sec = [g / self.fps for g in gaps]
            avg_gap_duration = np.mean(gap_durations_sec)
            gap_regularity = self._calculate_regularity(gap_durations_sec)
        else:
            avg_gap_duration = 0.0
            gap_regularity = 0.0
        
        # === 2. LIFE SPAN ===
        lifespans = self._calculate_text_lifespans(detections)
        if lifespans:
            avg_text_lifespan = np.mean(lifespans)
            max_text_lifespan = np.max(lifespans)
        else:
            avg_text_lifespan = 0.0
            max_text_lifespan = 0.0
        
        # === 3. POSITION STABILITY ===
        y_positions = [d.bbox[1] for d in detections]
        y_variance = np.var(y_positions)
        
        # Normalizar variância pela altura média (0-1 scale)
        # Variância baixa = estável = score alto
        max_variance = 100.0  # pixels²
        position_stability_score = max(0.0, 1.0 - (y_variance / max_variance))
        
        # === 4. TEXT UNIQUENESS ===
        texts = [d.text.strip() for d in detections]
        unique_texts = set(texts)
        num_unique = len(unique_texts)
        unique_ratio = num_unique / num_detections
        
        # === 5. VERTICAL BIAS ===
        bottom_count = sum(1 for d in detections if d.roi_type == ROIType.BOTTOM)
        bottom_ratio = bottom_count / num_detections
        
        # === 6. TEMPORAL DENSITY ===
        if frame_indices:
            duration_frames = frame_indices[-1] - frame_indices[0] + 1
            duration_sec = duration_frames / self.fps
            
            detections_per_sec = num_detections / duration_sec if duration_sec > 0 else 0
            
            # Contar mudanças de texto
            text_changes = sum(
                1 for i in range(1, len(texts)) 
                if texts[i] != texts[i-1]
            )
            text_changes_per_sec = text_changes / duration_sec if duration_sec > 0 else 0
        else:
            detections_per_sec = 0.0
            text_changes_per_sec = 0.0
        
        return AdvancedMetrics(
            avg_gap_duration=avg_gap_duration,
            gap_regularity=gap_regularity,
            num_gaps=len(gaps),
            avg_text_lifespan=avg_text_lifespan,
            max_text_lifespan=max_text_lifespan,
            y_position_variance=y_variance,
            position_stability_score=position_stability_score,
            unique_text_ratio=unique_ratio,
            num_unique_texts=num_unique,
            bottom_roi_ratio=bottom_ratio,
            detections_per_second=detections_per_sec,
            text_changes_per_second=text_changes_per_sec
        )
    
    def _calculate_gaps(self, frame_indices: List[int]) -> List[int]:
        """
        Calcula gaps (intervalos) entre detecções consecutivas
        
        Gap = diferença entre frames consecutivos - 1
        Ex: [0, 1, 2, 5, 6, 10] → gaps = [0, 0, 2, 0, 3]
        """
        if len(frame_indices) < 2:
            return []
        
        gaps = []
        for i in range(1, len(frame_indices)):
            gap = frame_indices[i] - frame_indices[i-1] - 1
            if gap > 0:  # Apenas gaps reais (não consecutivos)
                gaps.append(gap)
        
        return gaps
    
    def _calculate_regularity(self, values: List[float]) -> float:
        """
        Calcula regularidade de uma série (0-1)
        
        Regularidade alta = valores similares (baixo desvio padrão)
        Usa coeficiente de variação invertido
        """
        if not values or len(values) < 2:
            return 0.0
        
        mean_val = np.mean(values)
        if mean_val == 0:
            return 0.0
        
        std_val = np.std(values)
        cv = std_val / mean_val  # Coeficiente de variação
        
        # Inverter: CV baixo → regularidade alta
        # Normalizar para 0-1
        regularity = 1.0 / (1.0 + cv)
        
        return regularity
    
    def _calculate_text_lifespans(self, detections: List) -> List[float]:
        """
        Calcula duração de cada texto único
        
        Agrupa detecções consecutivas com mesmo texto e calcula duração
        """
        if not detections:
            return []
        
        lifespans = []
        current_text = detections[0].text.strip()
        start_frame = detections[0].frame_idx
        prev_frame = start_frame
        
        for detection in detections[1:]:
            text = detection.text.strip()
            frame = detection.frame_idx
            
            if text != current_text:
                # Mudou de texto, salvar lifespan anterior
                duration_frames = prev_frame - start_frame + 1
                duration_sec = duration_frames / self.fps
                lifespans.append(duration_sec)
                
                # Iniciar novo texto
                current_text = text
                start_frame = frame
            
            prev_frame = frame
        
        # Último texto
        duration_frames = prev_frame - start_frame + 1
        duration_sec = duration_frames / self.fps
        lifespans.append(duration_sec)
        
        return lifespans
    
    def _classify_track_v2(self, track: Track, metrics: AdvancedMetrics) -> TrackCategory:
        """
        Classifica track usando as 6 métricas avançadas
        
        Algoritmo de pontuação:
        - Cada métrica contribui com um score (0-1)
        - Score final > threshold → SUBTITLE
        """
        scores = {}
        
        # Score 1: Temporal Rhythm (legendas têm gaps regulares)
        if metrics.num_gaps >= 2:
            gap_in_range = (
                self.subtitle_gap_min <= metrics.avg_gap_duration <= self.subtitle_gap_max
            )
            regularity_ok = metrics.gap_regularity >= self.gap_regularity_min
            
            if gap_in_range and regularity_ok:
                scores['rhythm'] = 1.0
            elif gap_in_range or regularity_ok:
                scores['rhythm'] = 0.5
            else:
                scores['rhythm'] = 0.0
        else:
            # Sem gaps suficientes para avaliar
            scores['rhythm'] = 0.0
        
        # Score 2: Life Span (legendas duram poucos segundos)
        if (self.subtitle_lifespan_min <= metrics.avg_text_lifespan <= self.subtitle_lifespan_max):
            scores['lifespan'] = 1.0
        elif metrics.avg_text_lifespan < self.subtitle_lifespan_min:
            # Muito curto, pode ser ruído
            scores['lifespan'] = 0.3
        else:
            # Muito longo, provavelmente estático
            scores['lifespan'] = 0.0
        
        # Score 3: Position Stability (legendas ficam na mesma altura)
        if metrics.position_stability_score >= self.position_stability_min:
            scores['stability'] = 1.0
        else:
            scores['stability'] = metrics.position_stability_score
        
        # Score 4: Text Uniqueness (legendas têm muitos textos diferentes)
        if metrics.unique_text_ratio >= self.subtitle_uniqueness_min:
            scores['uniqueness'] = 1.0
        elif metrics.unique_text_ratio >= 0.3:
            scores['uniqueness'] = 0.5
        else:
            # Poucos textos únicos, provavelmente logo repetitivo
            scores['uniqueness'] = 0.0
        
        # Score 5: Vertical Bias (legendas no bottom)
        if metrics.bottom_roi_ratio >= self.subtitle_bottom_ratio_min:
            scores['vertical'] = 1.0
        elif metrics.bottom_roi_ratio >= 0.4:
            scores['vertical'] = 0.5
        else:
            # No top/middle, menos provável ser legenda
            scores['vertical'] = 0.0
        
        # Score 6: Temporal Density (legendas têm alta densidade)
        if metrics.text_changes_per_second >= self.subtitle_density_min:
            scores['density'] = 1.0
        elif metrics.text_changes_per_second >= 0.05:
            scores['density'] = 0.5
        else:
            scores['density'] = 0.0
        
        # === DECISÃO POR PONTUAÇÃO PONDERADA ===
        
        # Pesos (total = 1.0)
        weights = {
            'rhythm': 0.20,       # Temporal rhythm é forte indicador
            'lifespan': 0.20,     # Life span também
            'stability': 0.15,    # Position stability importante
            'uniqueness': 0.20,   # Text uniqueness crucial
            'vertical': 0.15,     # Vertical bias relevante
            'density': 0.10       # Temporal density complementar
        }
        
        final_score = sum(scores[k] * weights[k] for k in scores)
        
        logger.debug(
            f"Track {track.track_id} scores: {scores} → final={final_score:.2f}"
        )
        
        # === CLASSIFICAÇÃO FINAL ===
        
        # SUBTITLE: score alto (>= 0.75) - ajustado após calibração
        if final_score >= 0.75:
            logger.info(
                f"Track {track.track_id} classified as SUBTITLE (score={final_score:.2f})"
            )
            return TrackCategory.SUBTITLE
        
        # ANIMATED_LOGO: tem mudanças mas não é subtitle
        elif final_score >= 0.40 and metrics.unique_text_ratio < 0.5:
            logger.debug(
                f"Track {track.track_id} classified as ANIMATED_LOGO (score={final_score:.2f})"
            )
            return TrackCategory.ANIMATED_LOGO
        
        # STATIC_TEXT: baixa mudança, alta estabilidade
        elif metrics.unique_text_ratio < 0.2 and metrics.position_stability_score > 0.8:
            logger.debug(
                f"Track {track.track_id} classified as STATIC_TEXT"
            )
            return TrackCategory.STATIC_TEXT
        
        # SCREENCAST: no top/middle com mudanças
        elif metrics.bottom_roi_ratio < 0.3 and metrics.text_changes_per_second > 0.1:
            logger.debug(
                f"Track {track.track_id} classified as SCREENCAST"
            )
            return TrackCategory.SCREENCAST
        
        # NOISE: baixa confiança ou muito curto
        elif (len(track.detections) < 5 or 
              track.avg_confidence < self.noise_confidence_threshold):
            logger.debug(
                f"Track {track.track_id} classified as NOISE"
            )
            return TrackCategory.NOISE
        
        # Default: NOISE (não se encaixa em nenhuma categoria clara)
        else:
            logger.debug(
                f"Track {track.track_id} classified as NOISE (default, score={final_score:.2f})"
            )
            return TrackCategory.NOISE
    
    def _make_final_decision(
        self,
        subtitle_tracks: List[Tuple[Track, AdvancedMetrics]],
        other_tracks: List[Tuple[Track, AdvancedMetrics, TrackCategory]],
        all_tracks: List[Track]
    ) -> ClassificationResult:
        """
        Toma decisão final baseada em todos os tracks classificados
        """
        # Contar por categoria
        categories_count = {
            'subtitle': len(subtitle_tracks),
            'static_text': sum(1 for _, _, c in other_tracks if c == TrackCategory.STATIC_TEXT),
            'animated_logo': sum(1 for _, _, c in other_tracks if c == TrackCategory.ANIMATED_LOGO),
            'screencast': sum(1 for _, _, c in other_tracks if c == TrackCategory.SCREENCAST),
            'noise': sum(1 for _, _, c in other_tracks if c == TrackCategory.NOISE)
        }
        
        # DECISÃO: Se tem pelo menos 1 track SUBTITLE → BLOQUEAR
        if len(subtitle_tracks) > 0:
            # Confiança proporcional ao número de tracks
            confidence = min(0.95, 0.75 + (len(subtitle_tracks) * 0.05))
            
            # Detalhes do primeiro track para reason
            first_track, first_metrics = subtitle_tracks[0]
            reason = (
                f"Detected {len(subtitle_tracks)} subtitle track(s): "
                f"avg_lifespan={first_metrics.avg_text_lifespan:.1f}s, "
                f"uniqueness={first_metrics.unique_text_ratio:.0%}, "
                f"bottom_ratio={first_metrics.bottom_roi_ratio:.0%}"
            )
            
            return ClassificationResult(
                has_subtitles=True,
                confidence=confidence,
                reason=reason,
                decision_logic='subtitle_detected_v2',
                tracks_by_category=categories_count,
                subtitle_tracks=[t for t, _ in subtitle_tracks],
                metrics_summary={
                    'num_subtitle_tracks': len(subtitle_tracks),
                    'first_track_metrics': {
                        'lifespan': first_metrics.avg_text_lifespan,
                        'uniqueness': first_metrics.unique_text_ratio,
                        'bottom_ratio': first_metrics.bottom_roi_ratio,
                        'density': first_metrics.text_changes_per_second
                    }
                }
            )
        
        # SEM LEGENDAS → APROVAR
        return ClassificationResult(
            has_subtitles=False,
            confidence=0.90,
            reason=f"No subtitles detected ({len(all_tracks)} tracks analyzed)",
            decision_logic='no_subtitle_v2',
            tracks_by_category=categories_count,
            subtitle_tracks=[],
            metrics_summary={
                'total_tracks': len(all_tracks),
                'categories': categories_count
            }
        )
    
    def _no_text_result(self) -> ClassificationResult:
        """Resultado quando não há texto detectado"""
        return ClassificationResult(
            has_subtitles=False,
            confidence=0.95,
            reason="No text detected",
            decision_logic='no_text',
            tracks_by_category={},
            subtitle_tracks=[],
            metrics_summary={}
        )
