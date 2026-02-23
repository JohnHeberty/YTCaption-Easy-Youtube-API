"""
TRSD Telemetry System (Sprint 07)

Sistema completo de telemetria, métricas e debug artifacts para TRSD.
"""

import logging
import time
import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Métricas de performance por etapa"""
    total_time_ms: float
    frame_extraction_ms: float
    ocr_time_ms: float
    tracking_time_ms: float
    classification_time_ms: float
    frames_analyzed: int
    tracks_created: int
    lines_detected: int
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DetectionEvent:
    """Evento de detecção completo"""
    video_id: str
    timestamp: str
    decision: str  # 'block' or 'approve'
    confidence: float
    reason: str
    method: str  # 'TRSD' or 'Legacy'
    
    # Performance
    metrics: PerformanceMetrics
    
    # Detalhes
    tracks_by_category: Dict[str, int]
    decision_logic: str
    early_exit: bool
    
    # Debug
    debug_info: Dict
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data['metrics'] = self.metrics.to_dict()
        return data


class TRSDTelemetry:
    """
    Sistema de telemetria do TRSD
    
    Coleta métricas de performance, decisões e debugging
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.timers = {}
    
    def start_timer(self, name: str):
        """Inicia timer para uma etapa"""
        if not self.enabled:
            return
        self.timers[name] = time.time()
    
    def stop_timer(self, name: str) -> float:
        """Para timer e retorna tempo em ms"""
        if not self.enabled or name not in self.timers:
            return 0.0
        
        elapsed = (time.time() - self.timers[name]) * 1000
        del self.timers[name]
        return elapsed
    
    def record_decision(
        self,
        video_id: str,
        decision: str,
        confidence: float,
        reason: str,
        method: str,
        metrics: PerformanceMetrics,
        tracks_by_category: Dict[str, int],
        decision_logic: str,
        early_exit: bool = False,
        debug_info: Optional[Dict] = None
    ):
        """
        Registra decisão de detecção
        
        Salva em:
        1. Log estruturado
        2. Arquivo JSON (opcional)
        """
        event = DetectionEvent(
            video_id=video_id,
            timestamp=datetime.now().isoformat(),
            decision=decision,
            confidence=confidence,
            reason=reason,
            method=method,
            metrics=metrics,
            tracks_by_category=tracks_by_category,
            decision_logic=decision_logic,
            early_exit=early_exit,
            debug_info=debug_info or {}
        )
        
        # Log estruturado
        logger.info(
            f"📊 Detection event: {decision}",
            extra={'detection_event': event.to_dict()}
        )
        
        # Salvar em arquivo (opcional)
        if os.getenv('TRSD_SAVE_DETECTION_EVENTS', 'false') == 'true':
            self._save_event(event)
    
    def _save_event(self, event: DetectionEvent):
        """Salva evento em arquivo JSON"""
        events_dir = Path('data/logs/debug/detection_events')
        events_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{event.video_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = events_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(event.to_dict(), f, indent=2)
        
        logger.debug(f"Detection event saved to {filepath}")


class DebugArtifactSaver:
    """
    Salva artifacts de debug para análise
    
    Artifacts:
    - Frames com bboxes desenhadas
    - tracks.json com todos os tracks
    - metrics.json com métricas
    """
    
    def __init__(self, enabled: bool = False, base_dir: str = 'data/logs/debug/artifacts'):
        self.enabled = enabled
        self.base_dir = Path(base_dir)
        if self.enabled:
            self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save_detection_artifacts(
        self,
        video_id: str,
        frames: List[Tuple[np.ndarray, float]],
        tracks: List,
        result,
        metrics: PerformanceMetrics
    ):
        """
        Salva artifacts de uma detecção
        """
        if not self.enabled:
            return
        
        try:
            # Criar diretório para este vídeo
            video_dir = self.base_dir / video_id
            video_dir.mkdir(exist_ok=True)
            
            # Salvar tracks
            self._save_tracks(video_dir, tracks)
            
            # Salvar métricas
            self._save_metrics(video_dir, metrics, result)
            
            # Salvar frames (sample)
            if frames:
                self._save_frames_with_bboxes(video_dir, frames[:10], tracks)
            
            logger.info(f"📁 Debug artifacts saved to {video_dir}")
        
        except Exception as e:
            logger.warning(f"Could not save debug artifacts: {e}")
    
    def _save_tracks(self, video_dir: Path, tracks: List):
        """Salva tracks como JSON (com truncamento para privacidade)"""
        tracks_data = []
        
        for track in tracks:
            track_dict = {
                'track_id': track.track_id,
                'roi_type': track.roi_type.value,
                'presence_ratio': track.presence_ratio,
                'text_change_rate': track.text_change_rate,
                'y_mean': track.y_mean,
                'y_std': track.y_std,
                'avg_confidence': track.avg_confidence,
                'detections': [
                    {
                        'timestamp': d.frame_ts,
                        # CORREÇÃO: Truncar texto para privacidade
                        'text': d.text[:50] + '...' if len(d.text) > 50 else d.text,
                        'text_length': len(d.text),
                        'bbox': list(d.bbox),  # Convert tuple to list for JSON
                        'confidence': d.confidence
                    }
                    for d in track.detections[:5]  # Apenas primeiras 5
                ]
            }
            tracks_data.append(track_dict)
        
        with open(video_dir / 'tracks.json', 'w') as f:
            json.dump(tracks_data, f, indent=2)
    
    def _save_metrics(self, video_dir: Path, metrics: PerformanceMetrics, result):
        """Salva métricas"""
        data = {
            'metrics': metrics.to_dict(),
            'result': {
                'has_subtitles': result.has_subtitles,
                'confidence': result.confidence,
                'reason': result.reason,
                'decision_logic': result.decision_logic
            }
        }
        
        with open(video_dir / 'metrics.json', 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_frames_with_bboxes(
        self,
        video_dir: Path,
        frames: List[Tuple[np.ndarray, float]],
        tracks: List
    ):
        """Salva frames com bboxes desenhadas"""
        frames_dir = video_dir / 'frames'
        frames_dir.mkdir(exist_ok=True)
        
        for i, (frame, timestamp) in enumerate(frames):
            frame_copy = frame.copy()
            
            # Desenhar bboxes de todas as detecções neste timestamp
            for track in tracks:
                for detection in track.detections:
                    if abs(detection.frame_ts - timestamp) < 0.1:
                        x, y, w, h = detection.bbox
                        
                        # Cor por ROI
                        color = (0, 255, 0) if detection.roi_type.value == 'bottom' else (0, 0, 255)
                        
                        # Desenhar bbox
                        cv2.rectangle(frame_copy, (x, y), (x+w, y+h), color, 2)
                        
                        # Texto
                        text_label = f"T{track.track_id}: {detection.text[:20]}"
                        cv2.putText(
                            frame_copy, text_label,
                            (x, y-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
                        )
            
            # Salvar frame
            filename = f"frame_{i:03d}_{timestamp:.2f}s.jpg"
            cv2.imwrite(str(frames_dir / filename), frame_copy)
