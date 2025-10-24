"""
Entity: Transcription
Representa uma transcrição completa de vídeo.
Segue o princípio de Entity do DDD.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import uuid
from src.domain.value_objects import TranscriptionSegment, YouTubeURL


@dataclass
class Transcription:
    """Entidade que representa uma transcrição completa."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    youtube_url: Optional[YouTubeURL] = None
    segments: List[TranscriptionSegment] = field(default_factory=list)
    language: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    processing_time: Optional[float] = None
    
    def add_segment(self, segment: TranscriptionSegment) -> None:
        """Adiciona um segmento de transcrição."""
        self.segments.append(segment)
    
    def get_full_text(self) -> str:
        """Retorna o texto completo da transcrição."""
        return " ".join(segment.text for segment in self.segments)
    
    def to_srt(self) -> str:
        """Converte transcrição para formato SRT."""
        srt_content = []
        for index, segment in enumerate(self.segments, start=1):
            srt_content.append(segment.to_srt_format(index))
        return "\n".join(srt_content)
    
    def to_vtt(self) -> str:
        """Converte transcrição para formato WebVTT."""
        vtt_content = ["WEBVTT\n"]
        for segment in self.segments:
            vtt_content.append(segment.to_vtt_format())
        return "\n".join(vtt_content)
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "youtube_url": str(self.youtube_url) if self.youtube_url else None,
            "video_id": self.youtube_url.video_id if self.youtube_url else None,
            "language": self.language,
            "full_text": self.get_full_text(),
            "segments": [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "duration": seg.duration
                }
                for seg in self.segments
            ],
            "created_at": self.created_at.isoformat(),
            "processing_time": self.processing_time,
            "total_segments": len(self.segments)
        }
    
    @property
    def duration(self) -> float:
        """Retorna a duração total da transcrição."""
        if not self.segments:
            return 0.0
        return max(segment.end for segment in self.segments)
    
    @property
    def is_complete(self) -> bool:
        """Verifica se a transcrição está completa."""
        return len(self.segments) > 0 and self.language is not None
