"""
Interfaces e contratos abstratos para o serviço de transcrição.
Implementa Dependency Inversion Principle (DIP) do SOLID.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pathlib import Path
from .models import Job


class IModelManager(ABC):
    """Interface para gerenciamento de modelos de ML (Whisper)"""
    
    @abstractmethod
    def load_model(self) -> None:
        """Carrega modelo na memória/GPU"""
        pass
    
    @abstractmethod
    def unload_model(self) -> Dict[str, Any]:
        """Descarrega modelo da memória/GPU"""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual do modelo"""
        pass
    
    @abstractmethod
    def transcribe(self, audio_path: Path, language: str = "auto") -> Dict[str, Any]:
        """Transcreve áudio usando o modelo"""
        pass


class IAudioProcessor(ABC):
    """Interface para processamento de áudio"""
    
    @abstractmethod
    def validate_audio(self, audio_path: Path) -> bool:
        """Valida se arquivo de áudio é válido"""
        pass
    
    @abstractmethod
    def convert_to_wav(self, input_path: Path, output_path: Path) -> Path:
        """Converte áudio para formato WAV"""
        pass
    
    @abstractmethod
    def chunk_audio(self, audio_path: Path, chunk_size_mb: int) -> list[Path]:
        """Divide áudio em chunks menores"""
        pass
    
    @abstractmethod
    def get_duration(self, audio_path: Path) -> float:
        """Retorna duração do áudio em segundos"""
        pass


class IProgressTracker(ABC):
    """Interface para rastreamento de progresso de jobs"""
    
    @abstractmethod
    def update_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Atualiza progresso de um job"""
        pass
    
    @abstractmethod
    def mark_started(self, job_id: str) -> None:
        """Marca job como iniciado"""
        pass
    
    @abstractmethod
    def mark_completed(self, job_id: str, result: Any) -> None:
        """Marca job como completado"""
        pass
    
    @abstractmethod
    def mark_failed(self, job_id: str, error: str) -> None:
        """Marca job como falho"""
        pass


class IStorageManager(ABC):
    """Interface para gerenciamento de arquivos e armazenamento"""
    
    @abstractmethod
    def save_file(self, content: bytes, filename: str) -> Path:
        """Salva arquivo no sistema"""
        pass
    
    @abstractmethod
    def get_file(self, path: Path) -> bytes:
        """Recupera arquivo do sistema"""
        pass
    
    @abstractmethod
    def delete_file(self, path: Path) -> None:
        """Remove arquivo do sistema"""
        pass
    
    @abstractmethod
    def cleanup_temp_files(self, pattern: str) -> int:
        """Limpa arquivos temporários"""
        pass
    
    @abstractmethod
    def check_disk_space(self, required_mb: float) -> bool:
        """Verifica se há espaço em disco suficiente"""
        pass


class IDeviceManager(ABC):
    """Interface para gerenciamento de dispositivos (GPU/CPU)"""
    
    @abstractmethod
    def detect_device(self) -> str:
        """Detecta melhor dispositivo disponível (cuda/cpu)"""
        pass
    
    @abstractmethod
    def get_device_info(self) -> Dict[str, Any]:
        """Retorna informações sobre dispositivos disponíveis"""
        pass
    
    @abstractmethod
    def validate_device(self, device: str) -> bool:
        """Valida se dispositivo está funcionando"""
        pass


class IJobStore(ABC):
    """Interface para armazenamento de jobs"""
    
    @abstractmethod
    def save_job(self, job: Job) -> None:
        """Salva job no store"""
        pass
    
    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Job]:
        """Recupera job do store"""
        pass
    
    @abstractmethod
    def update_job(self, job: Job) -> None:
        """Atualiza job no store"""
        pass
    
    @abstractmethod
    def delete_job(self, job_id: str) -> None:
        """Remove job do store"""
        pass
    
    @abstractmethod
    def list_jobs(self, status: Optional[str] = None) -> list[Job]:
        """Lista jobs por status"""
        pass


class IHealthChecker(ABC):
    """Interface para health checks de componentes"""
    
    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """Verifica saúde do componente"""
        pass
    
    @abstractmethod
    def is_healthy(self) -> bool:
        """Retorna se componente está saudável"""
        pass
