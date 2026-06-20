"""
Domain interfaces for Make-Video Service.

Segue princípios SOLID:
- Interface Segregation: Interfaces pequenas e focadas
- Dependency Inversion: Camadas superiores dependem de abstrações
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoConfig:
    """Configuração para construção de vídeo."""
    output_dir: str
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    preset: str = "fast"
    crf: int = 23


@dataclass
class JobInfo:
    """Informações de um job."""
    job_id: str
    status: str
    progress: float
    created_at: Any  # datetime
    updated_at: Any  # datetime
    metadata: dict[str, Any] | None = None


class VideoBuilderInterface(ABC):
    """Interface para construção de vídeos."""

    @abstractmethod
    async def concatenate_videos(
        self,
        video_files: list[str],
        output_path: str,
        aspect_ratio: str,
        crop_position: str,
        remove_audio: bool = True
    ) -> str:
        """Concatena múltiplos vídeos em um só."""
        pass

    @abstractmethod
    async def add_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Adiciona áudio a um vídeo."""
        pass

    @abstractmethod
    async def burn_subtitles(self, video_path: str, subtitle_path: str,
                            output_path: str, style: str) -> str:
        """Adiciona legendas queimadas ao vídeo."""
        pass

    @abstractmethod
    async def trim_video(self, video_path: str, output_path: str,
                        max_duration: float) -> str:
        """Corta vídeo para duração máxima."""
        pass

    @abstractmethod
    async def get_video_info(self, video_path: str) -> dict[str, Any]:
        """Obtém informações do vídeo."""
        pass

    @abstractmethod
    async def get_audio_duration(self, audio_path: str) -> float:
        """Obtém duração do áudio em segundos."""
        pass

    @abstractmethod
    async def convert_to_h264(self, input_path: str, output_path: str) -> str:
        """Converte vídeo para formato H264."""
        pass

    @abstractmethod
    async def crop_video_for_validation(
        self, video_path: str, output_path: str,
        aspect_ratio: str, crop_position: str
    ) -> str:
        """Corta vídeo para proporção específica."""
        pass


class JobManagerInterface(ABC):
    """Interface para gerenciamento de jobs."""

    @abstractmethod
    async def create_job(self, job_data: dict[str, Any]) -> JobInfo:
        """Cria um novo job."""
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> JobInfo | None:
        """Obtém informações de um job."""
        pass

    @abstractmethod
    async def update_job(self, job_id: str, status: str,
                        progress: float, metadata: dict[str, Any] | None = None) -> bool:
        """Atualiza status e progresso de um job."""
        pass

    @abstractmethod
    async def complete_job(self, job_id: str, result: dict[str, Any]) -> bool:
        """Marca job como completo com resultado."""
        pass

    @abstractmethod
    async def fail_job(self, job_id: str, error: dict[str, Any]) -> bool:
        """Marca job como falho com erro."""
        pass

    @abstractmethod
    async def list_jobs(self, limit: int = 100) -> list[JobInfo]:
        """Lista todos os jobs."""
        pass


class CacheManagerInterface(ABC):
    """Interface para gerenciamento de cache de shorts."""

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Retorna estatísticas do cache."""
        pass

    @abstractmethod
    def cleanup_old(self, days: int) -> int:
        """Remove shorts não usados há X dias."""
        pass

    @abstractmethod
    def get_approved_videos(self) -> list[Path]:
        """Retorna lista de vídeos aprovados."""
        pass


class RedisClientInterface(ABC):
    """Interface para cliente Redis."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Obtém valor do Redis."""
        pass

    @abstractmethod
    async def setex(self, key: str, seconds: int, value: str) -> bool:
        """Define valor com TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Deleta chave."""
        pass

    @abstractmethod
    def scan_iter(self, match: str) -> Any:
        """Itera sobre chaves."""
        pass


class RateLimiterInterface(ABC):
    """Interface para rate limiting."""

    @abstractmethod
    def is_allowed(self, client_id: str = "global") -> bool:
        """Verifica se requisição é permitida."""
        pass


class LockManagerInterface(ABC):
    """Interface para gerenciamento de locks distribuídos."""

    @abstractmethod
    async def acquire(self, lock_name: str, timeout_seconds: int) -> str | None:
        """Adquire lock. Retorna token ou None se falhar."""
        pass

    @abstractmethod
    async def release(self, lock_name: str, token: str) -> bool:
        """Libera lock."""
        pass


class HealthCheckerInterface(ABC):
    """Interface para health checking."""

    @abstractmethod
    async def check_redis(self) -> bool:
        """Verifica conexão Redis."""
        pass

    @abstractmethod
    async def check_disk_space(self) -> bool:
        """Verifica espaço em disco."""
        pass

    @abstractmethod
    async def check_all(self) -> dict[str, bool]:
        """Executa todos os checks."""
        pass
