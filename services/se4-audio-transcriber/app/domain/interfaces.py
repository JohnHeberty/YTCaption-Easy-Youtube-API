"""
Interfaces e contratos abstratos para o serviço de transcrição.

Implementa Dependency Inversion Principle (DIP) do SOLID.
Todas as abstrações dependem de contratos, não de implementações concretas.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass

from typing import Union

from .models import (
    AudioTranscriptionJob as Job,
    TranscriptionSegment,
    WhisperEngine as WhisperEngineEnum,
)

# Re-export focused job interfaces (ISP split) for backward compatibility.
from .job_interfaces import IJobRepository, IJobQuery, IJobStore  # noqa: F401


@dataclass
class TranscriptionResult:
    """Resultado de uma transcrição de áudio."""
    text: str
    segments: List[Dict[str, Any]]
    language: Optional[str] = None
    processing_time: Optional[float] = None
    word_timestamps: bool = False


class ITranscriber(ABC):
    """
    Interface mínima para qualquer serviço de transcrição.

    Satisfaz ISP (Interface Segregation Principle): clientes que só precisam
    transcrever áudio não são forçados a implementar métodos de lifecycle
    (load_model, unload_model, device) que fazem sentido apenas para engines
    locais com modelos ML carregados em memória.

    Cloud APIs e serviços HTTP implementam apenas esta interface.
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


class ILifecycleManaged(ABC):
    """
    Interface opcional para engines que gerenciam ciclo de vida de modelos ML.

    Aplica-se a implementações locais (faster-whisper, openai-whisper) que
    precisam carregar/descarregar pesos em memória/GPU. Cloud APIs e serviços
    HTTP NÃO devem implementar esta interface.
    """

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


class TranscriptionEngine(ITranscriber, ILifecycleManaged):
    """
    Interface combinada para engines de transcrição com gestão de ciclo de vida.

    Herda de ITranscriber (transcrever áudio) e ILifecycleManaged (carregar/
    descarregar modelo). Mantida por conveniência: implementações que precisam
    dos dois conjuntos de métodos podem herdar desta classe em vez de listar
    ambas as interfaces separadamente.

    Implementa o Dependency Inversion Principle (DIP) do SOLID,
    permitindo trocar implementações de Whisper (faster-whisper,
    openai-whisper, whisperx) sem alterar o código que usa a interface.

    Example:
        engine = WhisperEngine(model_size="base")
        await engine.load_model()
        result = await engine.transcribe("/path/to/audio.mp3")
        await engine.unload_model()
    """
    pass


class IModelManager(ABC):
    """
    DEPRECATED — Remover em próxima versão.

    Esta interface foi marcada como deprecated porque:

      1) Viola ISP ao misturar transcrição com lifecycle management.
      2) Tem assinaturas incompatíveis com TranscriptionEngine:
         - unload_model() retorna Dict[str, Any] aqui vs async -> None em TranscriptionEngine.
         - transcribe() recebe Path + str e retorna dict genérico, enquanto ITranscriber
           usa str para audio_path e retorna TranscriptionResult tipado.

    A funcionalidade de lifecycle management foi absorvida pela classe concreta
    ModelManager (em app/services/model_manager.py), que agora é responsável
    apenas por carregar/descarregar o modelo openai-whisper sem expor uma
    interface genérica duplicada.

    Use TranscriptionEngine (ou ITranscriber + ILifecycleManaged) para novas implementações.
    """

    @abstractmethod
    def load_model(self) -> None:
        pass  # pragma: no cover — deprecated, mantido apenas por compatibilidade

    @abstractmethod
    def unload_model(self) -> Dict[str, Any]:
        pass  # pragma: no cover — deprecated, mantido apenas por compatibilidade

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        pass  # pragma: no cover — deprecated, mantido apenas por compatibilidade

    @abstractmethod
    def transcribe(self, audio_path: Path, language: str = "auto") -> Dict[str, Any]:
        pass  # pragma: no cover — deprecated, mantido apenas por compatibilidade


class ITranscriptionService(ABC):
    """
    Interface abstrata para o serviço de orquestração de transcrições.

    Satisfaz DIP: a camada API depende desta interface, não da classe concreta
    TranscriptionService. Permite trocar implementações (ex: mock em testes) sem
    alterar rotas ou controladores.

    Métodos espelham o público API de TranscriptionService — nenhum método novo
    foi adicionado para manter compatibilidade retroativa.
    """

    @abstractmethod
    async def create_job(
        self,
        filename: str,
        language_in: str = "auto",
        language_out: Optional[str] = None,
        engine: WhisperEngineEnum | None = None,
        file_content: Optional[bytes] = None,
    ) -> Job:
        """Cria um novo job de transcrição."""
        pass

    @abstractmethod
    async def process_job(self, job: Job) -> Job:
        """Processa um job de transcrição (validação → engine → save)."""
        pass

    @abstractmethod
    async def get_job_status(self, job_id: str) -> Optional[Job]:
        """Obtém status de um job pelo ID."""
        pass

    @abstractmethod
    async def list_jobs(self, limit: int = 20) -> List[Job]:
        """Lista jobs recentes."""
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """Remove um job e seus arquivos associados."""
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
    "ITranscriber",
    "ILifecycleManaged",
    "TranscriptionEngine",
    "IModelManager",
    "ITranscriptionService",
    "IAudioProcessor",
    "IProgressTracker",
    "IStorageManager",
    "IDeviceManager",
    "IJobRepository",
    "IJobQuery",
    "IJobStore",
    "IHealthChecker",
]