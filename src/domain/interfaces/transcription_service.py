"""
Interface: ITranscriptionService
Define o contrato para serviços de transcrição.
Segue o princípio de Dependency Inversion (SOLID).
"""
from abc import ABC, abstractmethod
from pathlib import Path
from src.domain.entities import Transcription, VideoFile


class ITranscriptionService(ABC):
    """Interface para serviços de transcrição de áudio."""
    
    @abstractmethod
    async def transcribe(self, video_file: VideoFile, language: str = "auto") -> Transcription:
        """
        Transcreve um arquivo de vídeo.
        
        Args:
            video_file: Arquivo de vídeo para transcrever
            language: Idioma do vídeo (auto para detecção automática)
            
        Returns:
            Transcription: Entidade com a transcrição completa
            
        Raises:
            TranscriptionError: Se houver erro na transcrição
        """
        pass
    
    @abstractmethod
    async def detect_language(self, video_file: VideoFile) -> str:
        """
        Detecta o idioma do áudio.
        
        Args:
            video_file: Arquivo de vídeo
            
        Returns:
            str: Código do idioma detectado
            
        Raises:
            TranscriptionError: Se houver erro na detecção
        """
        pass
