"""
Value Object: YouTubeURL
Representa uma URL do YouTube validada.
Segue o princípio de Value Object do DDD.
"""
from dataclasses import dataclass
from typing import Optional
import re


@dataclass(frozen=True)
class YouTubeURL:
    """Value Object que representa uma URL válida do YouTube."""
    
    url: str
    video_id: str
    
    _YOUTUBE_REGEX = re.compile(
        r'^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))'
        r'(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$'
    )
    
    def __post_init__(self) -> None:
        """Valida a URL após inicialização."""
        if not self._is_valid_youtube_url(self.url):
            raise ValueError(f"Invalid YouTube URL: {self.url}")
    
    @classmethod
    def create(cls, url: str) -> "YouTubeURL":
        """Factory method para criar YouTubeURL."""
        video_id = cls._extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")
        return cls(url=url, video_id=video_id)
    
    @classmethod
    def _is_valid_youtube_url(cls, url: str) -> bool:
        """Verifica se a URL é válida."""
        return bool(cls._YOUTUBE_REGEX.match(url))
    
    @classmethod
    def _extract_video_id(cls, url: str) -> Optional[str]:
        """Extrai o ID do vídeo da URL."""
        match = cls._YOUTUBE_REGEX.match(url)
        if match:
            return match.group(5)
        return None
    
    def __str__(self) -> str:
        """Representação em string."""
        return self.url
