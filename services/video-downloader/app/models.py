from enum import Enum
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel


class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


class JobRequest(BaseModel):
    url: str
    quality: Optional[str] = "best"  # best, worst, 720p, 480p, etc.


class Job(BaseModel):
    id: str
    url: str
    status: JobStatus
    quality: str
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    received_at: datetime  # Quando foi recebido
    created_at: datetime   # Alias para received_at (compatibilidade)
    started_at: Optional[datetime] = None     # Quando começou a baixar
    completed_at: Optional[datetime] = None   # Quando finalizou
    error_message: Optional[str] = None
    expires_at: datetime
    current_user_agent: Optional[str] = None  # UA usado no download
    progress: float = 0.0  # Progresso de 0.0 a 100.0
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    @classmethod
    def create_new(cls, url: str, quality: str = "best") -> "Job":
        import uuid
        
        # Extrai ID do vídeo do YouTube
        video_id = cls._extract_video_id(url)
        
        # Se não conseguiu extrair, assume que url já é o video_id
        if not video_id:
            # Verifica se é um ID válido (11 caracteres alfanuméricos)
            if len(url) == 11 and url.replace('-', '').replace('_', '').isalnum():
                video_id = url
                # Reconstrói URL completa
                url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Cria ID único: video_id + quality (para diferentes qualidades do mesmo vídeo)
        job_id = f"{video_id}_{quality}" if video_id else str(uuid.uuid4())
        
        now = datetime.now()
        return cls(
            id=job_id,
            url=url,
            status=JobStatus.QUEUED,
            quality=quality,
            received_at=now,
            created_at=now,
            expires_at=now + timedelta(hours=24)
        )
    
    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        """
        Extrai ID do vídeo de URLs do YouTube
        
        Suporta formatos:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://m.youtube.com/watch?v=VIDEO_ID
        """
        import re
        
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None