"""
Interfaces e contratos abstratos para o serviço de transcrição.

Implementa Dependency Inversion Principle (DIP) do SOLID.
Todas as abstrações dependem de contratos, não de implementações concretas.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass

from .models import Job, TranscriptionSegment


@dataclass
class TranscriptionResult:
    """Resultado de uma transcrição de áudio."""
    text: str
    segments: List[Dict[str, Any]]
    language: Optional[str] = None
    processing_time: Optional[float] = None
    word_timestamps: bool = False


class TranscriptionEngine(ABC):
    """
    Interface abstrata para engines de transcrição.
    
    Implementa o Dependency Inversion Principle (DIP) do SOLID,
    permitindo trocar implementações de Whisper (faster-whisper,
    openai-whisper, whisperx) sem alterar o código que usa a interface.
    
    Example:
        engine = WhisperEngine(model_size="base")
        engine.load_model()
        result = await engine.transcribe("/path/to/audio.mp3")
        await engine.unload_model()
    """

    @abstractmethod
    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> TranscriptionResult:
        """
        Transcreve um arquivo de áudio.
        
        Args:
            audio_path: Caminho completo para o arquivo de áudio
            language: Código do idioma (ex: 'pt', 'en'). None para detecção automática.
            task: 'transcribe' para transcrever, 'translate' para traduzir para inglês
            
        Returns:
            TranscriptionResult com texto, segmentos e metadados
            
        Raises:
            AudioTranscriptionException: Se transcrição falhar
        """
        pass

    @abstractmethod
    def load_model(self) -> None:
        """Carrega o modelo na memória/GPU."""
        pass

    @abstractmethod
    async def unload_model(self) -> None:
        """Descarrega o modelo da memória/GPU para liberar recursos."""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """Retorna True se o modelo está carregado."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do modelo (carregado, dispositivo, memória)."""
        pass

    @property
    @abstractmethod
    def device(self) -> str:
        """Retorna dispositivo atual ('cpu' ou 'cuda')."""
        pass


class IModelManager(ABC):
    """
    Interface para gerenciamento de modelos de ML (Whisper).
    @deprecated Use TranscriptionEngine em vez disso.
    """

    @abstractmethod
    def load_model(self) -> None:
        """Carrega modelo na memória/GPU."""
        pass

    @abstractmethod
    def unload_model(self) -> Dict[str, Any]:
        """Descarrega modelo da memória/GPU."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual do modelo."""
        pass

    @abstractmethod
    def transcribe(self, audio_path: Path, language: str = "auto") -> Dict[str, Any]:
        """Transcreve áudio usando o modelo."""
        pass


class IAudioProcessor(ABC):
    """Interface para processamento de áudio."""

    @abstractmethod
    def validate_audio(self, audio_path: Path) -> bool:
        """Valida se arquivo de áudio é válido."""
        pass

    @abstractmethod
    def convert_to_wav(self, input_path: Path, output_path: Path) -> Path:
        """Converte áudio para formato WAV."""
        pass

    @abstractmethod
    def chunk_audio(self, audio_path: Path, chunk_size_mb: int) -> list[Path]:
        """Divide áudio em chunks menores."""
        pass

    @abstractmethod
    def get_duration(self, audio_path: Path) -> float:
        """Retorna duração do áudio em segundos."""
        pass


class IProgressTracker(ABC):
    """Interface para rastreamento de progresso de jobs."""

    @abstractmethod
    def update_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Atualiza progresso de um job."""
        pass

    @abstractmethod
    def mark_started(self, job_id: str) -> None:
        """Marca job como iniciado."""
        pass

    @abstractmethod
    def mark_completed(self, job_id: str, result: Any) -> None:
        """Marca job como completado."""
        pass

    @abstractmethod
    def mark_failed(self, job_id: str, error: str) -> None:
        """Marca job como falho."""
        pass


class IStorageManager(ABC):
    """Interface para gerenciamento de arquivos e armazenamento."""

    @abstractmethod
    def save_file(self, content: bytes, filename: str) -> Path:
        """Salva arquivo no sistema."""
        pass

    @abstractmethod
    def get_file(self, path: Path) -> bytes:
        """Recupera arquivo do sistema."""
        pass

    @abstractmethod
    def delete_file(self, path: Path) -> None:
        """Remove arquivo do sistema."""
        pass

    @abstractmethod
    def cleanup_temp_files(self, pattern: str) -> int:
        """Limpa arquivos temporários."""
        pass

    @abstractmethod
    def check_disk_space(self, required_mb: float) -> bool:
        """Verifica se há espaço em disco suficiente."""
        pass


class IDeviceManager(ABC):
    """Interface para gerenciamento de dispositivos (GPU/CPU)."""

    @abstractmethod
    def detect_device(self) -> str:
        """Detecta melhor dispositivo disponível (cuda/cpu)."""
        pass

    @abstractmethod
    def get_device_info(self) -> Dict[str, Any]:
        """Retorna informações sobre dispositivos disponíveis."""
        pass

    @abstractmethod
    def validate_device(self, device: str) -> bool:
        """Valida se dispositivo está funcionando."""
        pass


class IJobStore(ABC):
    """Interface para armazenamento de jobs."""

    @abstractmethod
    def save_job(self, job: Job) -> None:
        """Salva job no store."""
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Job]:
        """Recupera job do store."""
        pass

    @abstractmethod
    def update_job(self, job: Job) -> None:
        """Atualiza job no store."""
        pass

    @abstractmethod
    def delete_job(self, job_id: str) -> None:
        """Remove job do store."""
        pass

    @abstractmethod
    def list_jobs(self, status: Optional[str] = None) -> list[Job]:
        """Lista jobs por status."""
        pass


class IHealthChecker(ABC):
    """Interface para health checks de componentes."""

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """Verifica saúde do componente."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Retorna se componente está saudável."""
        pass


__all__ = [
    "TranscriptionResult",
    "TranscriptionEngine",
    "IModelManager",
    "IAudioProcessor",
    "IProgressTracker",
    "IStorageManager",
    "IDeviceManager",
    "IJobStore",
    "IHealthChecker",
]