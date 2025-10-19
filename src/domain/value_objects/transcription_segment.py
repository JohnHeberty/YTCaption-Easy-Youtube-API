"""
Value Object: TranscriptionSegment
Representa um segmento de transcrição com timestamp.
"""
from dataclasses import dataclass
# from typing import Optional  # noqa: F401


@dataclass(frozen=True)
class TranscriptionSegment:
    """Segmento de transcrição com informações de tempo."""
    
    text: str
    start: float
    end: float
    
    def __post_init__(self) -> None:
        """Valida o segmento após inicialização."""
        if self.start < 0:
            raise ValueError("Start time must be non-negative")
        if self.end < self.start:
            raise ValueError("End time must be greater than or equal to start time")
        if not self.text.strip():
            raise ValueError("Text cannot be empty")
    
    @property
    def duration(self) -> float:
        """Retorna a duração do segmento em segundos."""
        return self.end - self.start
    
    def to_srt_format(self, index: int) -> str:
        """Converte para formato SRT."""
        start_time = self._format_timestamp(self.start)
        end_time = self._format_timestamp(self.end)
        return f"{index}\n{start_time} --> {end_time}\n{self.text}\n"
    
    def to_vtt_format(self) -> str:
        """Converte para formato WebVTT."""
        start_time = self._format_timestamp(self.start, use_comma=False)
        end_time = self._format_timestamp(self.end, use_comma=False)
        return f"{start_time} --> {end_time}\n{self.text}\n"
    
    @staticmethod
    def _format_timestamp(seconds: float, use_comma: bool = True) -> str:
        """Formata timestamp para formato de legenda."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        separator = "," if use_comma else "."
        return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"
