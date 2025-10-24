"""
Entity: VideoFile
Representa um arquivo de vídeo baixado.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime
import uuid


@dataclass
class VideoFile:
    """Entidade que representa um arquivo de vídeo."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: Path = field(default=Path())
    original_url: Optional[str] = None
    file_size_bytes: int = 0
    format: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self) -> None:
        """Validação pós-inicialização."""
        if isinstance(self.file_path, str):
            object.__setattr__(self, 'file_path', Path(self.file_path))
    
    @property
    def exists(self) -> bool:
        """Verifica se o arquivo existe."""
        return self.file_path.exists()
    
    @property
    def file_size_mb(self) -> float:
        """Retorna o tamanho do arquivo em MB."""
        return self.file_size_bytes / (1024 * 1024)
    
    @property
    def extension(self) -> str:
        """Retorna a extensão do arquivo."""
        return self.file_path.suffix
    
    def delete(self) -> bool:
        """Remove o arquivo do disco."""
        try:
            if self.exists:
                self.file_path.unlink()
                return True
            return False
        except Exception:
            return False
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "file_path": str(self.file_path),
            "original_url": self.original_url,
            "file_size_mb": round(self.file_size_mb, 2),
            "format": self.format,
            "exists": self.exists,
            "created_at": self.created_at.isoformat()
        }
