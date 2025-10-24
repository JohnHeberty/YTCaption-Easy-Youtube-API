"""
Value Object para vídeo enviado via upload.
Imutável e com validações.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class UploadedVideoFile:
    """
    Representa um arquivo de vídeo enviado via upload.
    
    Attributes:
        file_path: Caminho do arquivo no storage temporário
        original_filename: Nome original do arquivo
        mime_type: MIME type do arquivo
        size_bytes: Tamanho em bytes
        duration_seconds: Duração em segundos (após validação)
    """
    
    file_path: Path
    original_filename: str
    mime_type: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    
    def __post_init__(self):
        """Validações após inicialização."""
        if not self.file_path.exists():
            raise ValueError(f"File not found: {self.file_path}")
        
        if self.size_bytes <= 0:
            raise ValueError("File size must be positive")
        
        if not self.original_filename:
            raise ValueError("Original filename is required")
    
    def get_extension(self) -> str:
        """Retorna extensão do arquivo."""
        return self.file_path.suffix.lower()
    
    def is_video(self) -> bool:
        """Verifica se é vídeo."""
        return self.mime_type.startswith('video/')
    
    def is_audio(self) -> bool:
        """Verifica se é áudio."""
        return self.mime_type.startswith('audio/')
    
    def get_size_mb(self) -> float:
        """Retorna tamanho em MB."""
        return self.size_bytes / (1024 * 1024)
