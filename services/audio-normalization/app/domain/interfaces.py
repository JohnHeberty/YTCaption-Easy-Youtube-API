"""
Interfaces (protocolos) para o serviço de normalização de áudio.

Define contratos para implementações seguindo princípio ISP (Interface Segregation Principle).
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Protocol, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from pydub import AudioSegment

from ..core.models import AudioNormJob


class IJobStore(Protocol):
    """Protocolo para storage de jobs."""

    def save_job(self, job: AudioNormJob) -> None:
        """Salva job no storage."""
        ...

    def get_job(self, job_id: str) -> Optional[AudioNormJob]:
        """Recupera job pelo ID."""
        ...

    def update_job(self, job: AudioNormJob) -> None:
        """Atualiza job existente."""
        ...

    def delete_job(self, job_id: str) -> bool:
        """Remove job do storage."""
        ...

    def list_jobs(self, limit: int = 50) -> List[AudioNormJob]:
        """Lista jobs recentes."""
        ...


class IAudioProcessor(Protocol):
    """Protocolo para processamento de áudio."""

    async def process_audio_job(self, job: AudioNormJob) -> None:
        """Processa um job de áudio completamente."""
        ...

    async def normalize(self, audio_path: str) -> str:
        """Normaliza áudio e retorna caminho do arquivo processado."""
        ...


class IAudioValidator(Protocol):
    """Protocolo para validação de áudio."""

    async def validate(self, file_path: str) -> dict:
        """Valida arquivo de áudio e retorna metadados."""
        ...

    def is_video_file(self, file_path: str) -> bool:
        """Detecta se arquivo é vídeo."""
        ...


class IFileStorage(Protocol):
    """Protocolo para armazenamento de arquivos."""

    def save(self, content: bytes, filename: str) -> Path:
        """Salva conteúdo e retorna caminho."""
        ...

    def delete(self, file_path: Path) -> bool:
        """Remove arquivo."""
        ...

    def exists(self, file_path: Path) -> bool:
        """Verifica se arquivo existe."""
        ...


class AbstractAudioNormalizer(ABC):
    """Classe abstrata para normalizadores de áudio."""

    @abstractmethod
    async def normalize(self, audio: "AudioSegment") -> "AudioSegment":
        """
        Normaliza um segmento de áudio.

        Args:
            audio: Segmento de áudio a ser normalizado

        Returns:
            AudioSegment normalizado
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Retorna nome do normalizador."""
        pass


class AbstractAudioFilter(ABC):
    """Classe abstrata para filtros de áudio."""

    @abstractmethod
    async def apply(self, audio: "AudioSegment") -> "AudioSegment":
        """
        Aplica filtro ao áudio.

        Args:
            audio: Segmento de áudio

        Returns:
            AudioSegment filtrado
        """
        pass

    @abstractmethod
    def get_parameters(self) -> dict:
        """Retorna parâmetros do filtro."""
        pass
