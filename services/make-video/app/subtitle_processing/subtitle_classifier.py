"""
TRSD - Classificador de Tracks (Sprint 03)

Sistema de classificação de tracks baseado em regras usando métricas temporais.
Classifica texto em: SUBTITLE, STATIC_OVERLAY, SCREENCAST, ou AMBIGUOUS.
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict
import numpy as np

from .temporal_tracker import Track
from app.trsd_models.text_region import ROIType
from app.core.config import Settings

logger = logging.getLogger(__name__)


class TrackCategory(Enum):
    """Categorias de classificação de tracks"""
    SUBTITLE = 'subtitle'                # Legenda dinâmica (bloquear)
    STATIC_OVERLAY = 'static_overlay'    # Texto estático (watermark, UI fixa)
    SCREENCAST = 'screencast'            # Uso de aplicativo (texto em app)
    AMBIGUOUS = 'ambiguous'              # Não conseguiu classificar com certeza


@dataclass
class ClassificationResult:
    """Resultado da classificação de um vídeo"""
    has_subtitles: bool                  # Decisão final: bloquear?
    confidence: float                    # Confiança da decisão [0-1]
    reason: str                          # Explicação legível
    decision_logic: str                  # Lógica da decisão (para debug)
    
    # Detalhamento por categoria
    tracks_by_category: Dict[str, int]   # {category: count}
    subtitle_tracks: List[Track]
    static_tracks: List[Track]
    screencast_tracks: List[Track]
    ambiguous_tracks: List[Track]


class SubtitleClassifier:
    """
    Classificador de tracks baseado em regras
    
    Analisa métricas temporais calculadas pelo TemporalTracker e
    classifica cada track em uma categoria.
    """
    
    def __init__(self, config: Optional[Settings] = None):
        self.config = config or Settings()
        
        # Política de classificação
        self.ignore_static_text = self.config.trsd_ignore_static_text
        
        # Thresholds de classificação (Sprint 03)
        self.static_min_presence = self.config.trsd_static_min_presence
        self.static_max_change = self.config.trsd_static_max_change
        self.subtitle_min_change_rate = self.config.trsd_subtitle_min_change_rate
        self.screencast_min_detections = self.config.trsd_screencast_min_detections
        
        logger.info(
            f"SubtitleClassifier initialized: ignore_static={self.ignore_static_text}, "
            f"static_threshold={self.static_min_presence:.2f}"
        )
    
    def decide(self, tracks: List[Track]) -> ClassificationResult:
        """
        Classifica tracks e decide se vídeo deve ser bloqueado
        
        Args:
            tracks: Lista de tracks com métricas calculadas
        
        Returns:
            ClassificationResult com decisão final
        """
        # Classificar cada track
        subtitle_tracks = []
        static_tracks = []
        screencast_tracks = []
        ambiguous_tracks = []
        
        for track in tracks:
            category = self._classify_track(track)
            
            if category == TrackCategory.SUBTITLE:
                subtitle_tracks.append(track)
            elif category == TrackCategory.STATIC_OVERLAY:
                static_tracks.append(track)
            elif category == TrackCategory.SCREENCAST:
                screencast_tracks.append(track)
            else:  # AMBIGUOUS
                ambiguous_tracks.append(track)
        
        # Contagem por categoria
        tracks_by_category = {
            'subtitle': len(subtitle_tracks),
            'static_overlay': len(static_tracks),
            'screencast': len(screencast_tracks),
            'ambiguous': len(ambiguous_tracks)
        }
        
        # Decidir bloqueio
        decision = self._make_decision(
            subtitle_tracks, static_tracks, screencast_tracks, ambiguous_tracks
        )
        
        return ClassificationResult(
            has_subtitles=decision['block'],
            confidence=decision['confidence'],
            reason=decision['reason'],
            decision_logic=decision['logic'],
            tracks_by_category=tracks_by_category,
            subtitle_tracks=subtitle_tracks,
            static_tracks=static_tracks,
            screencast_tracks=screencast_tracks,
            ambiguous_tracks=ambiguous_tracks
        )
    
    def _classify_track(self, track: Track) -> TrackCategory:
        """
        Classifica um track individual
        
        Lógica de classificação:
        1. STATIC_OVERLAY: presence_ratio alto + text_change_rate baixo
        2. SUBTITLE: text_change_rate médio/alto + ROI bottom
        3. SCREENCAST: middle/top ROI + muitas detecções + alguma mudança
        4. AMBIGUOUS: não se encaixa claramente em nenhuma categoria
        """
        presence = track.presence_ratio
        change_rate = track.text_change_rate
        roi = track.roi_type
        num_detections = len(track.detections)
        y_std = track.y_std
        
        # Regra 1: STATIC_OVERLAY
        # Texto que aparece em quase todos os frames e não muda
        if (presence >= self.static_min_presence and
            change_rate <= self.static_max_change):
            
            logger.debug(
                f"Track {track.track_id} classified as STATIC_OVERLAY: "
                f"presence={presence:.2f}, change={change_rate:.2f}"
            )
            return TrackCategory.STATIC_OVERLAY
        
        # Regra 2: SUBTITLE
        # Texto dinâmico no terço inferior (ROI bottom) com mudanças frequentes
        if (roi == ROIType.BOTTOM and
            change_rate >= self.subtitle_min_change_rate):
            
            logger.debug(
                f"Track {track.track_id} classified as SUBTITLE: "
                f"change={change_rate:.2f}, roi=bottom"
            )
            return TrackCategory.SUBTITLE
        
        # Regra 3: SCREENCAST
        # Texto em middle/top com muitas detecções e alguma variação
        # (usuário usando app, digitando, navegando)
        if (roi in [ROIType.MIDDLE, ROIType.TOP] and
            num_detections >= self.screencast_min_detections and
            change_rate > 0.1):  # Alguma mudança
            
            logger.debug(
                f"Track {track.track_id} classified as SCREENCAST: "
                f"roi={roi.value}, detections={num_detections}"
            )
            return TrackCategory.SCREENCAST
        
        # Regra 4: SUBTITLE secundária
        # Pode ser subtitle em posição não-padrão (middle/top)
        # mas com padrão de mudança característico
        if (change_rate >= self.subtitle_min_change_rate and
            presence < 0.50):  # Não aparece o tempo todo
            
            logger.debug(
                f"Track {track.track_id} classified as SUBTITLE (non-standard position): "
                f"change={change_rate:.2f}"
            )
            return TrackCategory.SUBTITLE
        
        # Caso contrário: AMBIGUOUS
        logger.debug(
            f"Track {track.track_id} classified as AMBIGUOUS: "
            f"presence={presence:.2f}, change={change_rate:.2f}, roi={roi.value}"
        )
        return TrackCategory.AMBIGUOUS
    
    def _make_decision(
        self,
        subtitle_tracks: List[Track],
        static_tracks: List[Track],
        screencast_tracks: List[Track],
        ambiguous_tracks: List[Track]
    ) -> Dict:
        """
        Toma decisão final baseada em políticas
        
        Política:
        - Se IGNORE_STATIC_TEXT=true: ignorar static e screencast
        - Se encontrar SUBTITLE: bloquear
        - Se encontrar AMBIGUOUS sem SUBTITLE: considerar suspeito
        
        Returns:
            Dict com: block, confidence, reason, logic
        """
        # Caso 1: Tem legendas claras → BLOQUEAR
        if len(subtitle_tracks) > 0:
            confidence = min(0.95, 0.70 + (len(subtitle_tracks) * 0.10))
            
            return {
                'block': True,
                'confidence': confidence,
                'reason': f"Detected {len(subtitle_tracks)} subtitle track(s)",
                'logic': 'subtitle_detected'
            }
        
        # Caso 2: Apenas texto estático/screencast e política=ignorar
        if self.ignore_static_text:
            if len(static_tracks) > 0 or len(screencast_tracks) > 0:
                return {
                    'block': False,
                    'confidence': 0.85,
                    'reason': f"Only static/screencast text (ignored by policy)",
                    'logic': 'static_ignored'
                }
        
        # Caso 3: Tem ambiguous → suspeito (pode ter perdido legenda)
        if len(ambiguous_tracks) > 0:
            # Se tem muito ambiguous, considerar suspeito
            # CORREÇÃO: Threshold mais conservador para evitar falsos positivos
            if len(ambiguous_tracks) >= 5:  # Aumentado de 3 para 5
                return {
                    'block': True,
                    'confidence': 0.55,  # Baixa confiança
                    'reason': f"Multiple ambiguous tracks ({len(ambiguous_tracks)}) - potential subtitle",
                    'logic': 'ambiguous_suspicious'
                }
            else:
                # Poucos ambiguous, provavelmente ruído
                return {
                    'block': False,
                    'confidence': 0.70,
                    'reason': f"Ambiguous detection but likely noise ({len(ambiguous_tracks)} tracks)",
                    'logic': 'ambiguous_noise'
                }
        
        # Caso 4: Texto estático sem política de ignorar
        if not self.ignore_static_text and len(static_tracks) > 0:
            return {
                'block': True,
                'confidence': 0.75,
                'reason': f"Static text detected ({len(static_tracks)} tracks)",
                'logic': 'static_detected'
            }
        
        # Caso 5: Nenhum texto detectado → APROVAR
        return {
            'block': False,
            'confidence': 0.90,
            'reason': "No text detected",
            'logic': 'no_text'
        }
