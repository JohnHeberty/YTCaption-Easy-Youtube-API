"""
Implementação do TranscriptionEngine usando Whisper.

Implementa a interface TranscriptionEngine usando o faster-whisper
como backend principal, com suporte para fallback em outras implementações.

Segue o Single Responsibility Principle (SRP) ao encapsular toda a
lógica de transcrição em uma única classe bem definida.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from typing import Callable, Type

from ..domain.interfaces import (
    IDeviceManager,
    TranscriptionEngine,
    TranscriptionResult,
)
from ..domain.models import WhisperEngine as _WhisperEngineEnum
from ..shared.device_manager import TorchDeviceManager
from ..shared.exceptions import AudioTranscriptionException

logger = get_logger(__name__)


class WhisperEngine(TranscriptionEngine):
    """
    Engine de transcrição usando Whisper via faster-whisper.

    Esta implementação:
    - Usa faster-whisper (4x mais rápido que whisper original)
    - Suporta word-level timestamps nativamente
    - Gerencia automaticamente dispositivo (CUDA > CPU)
    - Implementa lazy loading do modelo

    Example:
        engine = WhisperEngine(model_size="base")
        await engine.transcribe("/path/to/audio.mp3", language="pt")
    """

    def __init__(
        self,
        model_size: str = "base",
        device_manager: IDeviceManager | None = None,
        compute_type: str = "float16",
        download_root: str | None = None,
        cpu_threads: int = 0,
        num_workers: int = 1,
    ) -> None:
        """
        Inicializa o engine Whisper.
        
        Args:
            model_size: Tamanho do modelo (tiny, base, small, medium, large-v1, large-v2, large-v3)
            device_manager: IDeviceManager (opcional, fallback interno se não injetado)
            compute_type: Tipo de computação ('float16', 'int8', 'int8_float16')
            download_root: Diretório para download de modelos
            cpu_threads: Threads para CPU (0 = auto)
            num_workers: Workers para processamento
        """
        self.model_size = model_size
        self.device_manager = device_manager or TorchDeviceManager()
        self.compute_type_raw = compute_type
        self.download_root = download_root or os.getenv("WHISPER_MODEL_DIR", "./models")
        self.cpu_threads = cpu_threads
        self.num_workers = num_workers

        self._device: str = self.device_manager.detect_device()
        self.compute_type = (
            self.compute_type_raw if self._device == "cuda" else "int8"
        )
        self._model: WhisperModel | None = None
        self._loaded_at: Any | None = None
        self._last_used_at: Any | None = None
        self._load_count: int = 0

        logger.info(
            f"WhisperEngine criado: model={model_size}, device={self._device}, "
            f"compute_type={self.compute_type}"
        )

    @property
    def device(self) -> str:
        """Retorna dispositivo atual ('cpu' ou 'cuda')."""
        return self._device

    def load_model(self) -> None:
        """
        Carrega o modelo Whisper na memória.
        
        É seguro chamar múltiplas vezes (idempotente).
        """
        if self._model is not None:
            logger.debug(f"Modelo {self.model_size} já está carregado")
            return
        
        try:
            logger.info(f"Carregando modelo Whisper {self.model_size}...")
            start_time = time.time()
            
            # Configurações de computação
            device = self.device
            compute_type = self.compute_type
            
            # Ajusta compute_type para CPU
            if device == "cpu":
                compute_type = "int8"  # Mais eficiente em CPU
            
            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
                download_root=self.download_root,
                cpu_threads=self.cpu_threads,
                num_workers=self.num_workers,
            )
            
            self._loaded_at = now_brazil()
            self._last_used_at = self._loaded_at
            self._load_count += 1
            
            load_time = time.time() - start_time
            logger.info(
                f"Modelo {self.model_size} carregado em {load_time:.2f}s "
                f"(device={device}, compute={compute_type})"
            )
            
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            raise AudioTranscriptionException(f"Falha ao carregar modelo: {str(e)}")

    async def unload_model(self) -> None:
        """
        Descarrega o modelo da memória para liberar recursos.
        
        Libera:
        - Memória RAM ocupada pelo modelo
        - Memória GPU/VRAM (se CUDA)
        - Referências internas
        """
        if self._model is None:
            logger.debug("Modelo já está descarregado")
            return
        
        try:
            model_size = self.model_size
            device = self.device
            
            logger.info(f"Descarregando modelo {model_size} do {device}...")
            
            # Remove referência ao modelo
            del self._model
            self._model = None

            # CUDA cleanup via shared utility
            from common.gpu_utils import cleanup_cuda
            cleanup_cuda()
            
            self._loaded_at = None
            self._last_used_at = None
            
            logger.info(f"Modelo {model_size} descarregado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao descarregar modelo: {e}")
            # Não lança exceção em unload - apenas loga

    def is_loaded(self) -> bool:
        """Retorna True se o modelo está carregado."""
        return self._model is not None

    def get_status(self) -> dict[str, Any]:
        """Retorna status detalhado do engine."""
        status = {
            "loaded": self.is_loaded(),
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "load_count": self._load_count,
        }
        
        if self._loaded_at:
            status["loaded_at"] = self._loaded_at.isoformat()
        
        if self._last_used_at:
            status["last_used_at"] = self._last_used_at.isoformat()
        
        # Informações de GPU via device_manager (DIP compliance)
        if self.device == "cuda":
            info = self.device_manager.get_device_info()
            gpu_data = info.get("gpu", {})
            devices = gpu_data.get("devices", [])
            if devices:
                status["gpu"] = {
                    "name": devices[0].get("name"),
                    "memory_allocated_mb": devices[0].get("memory_allocated_mb"),
                    "memory_reserved_mb": devices[0].get("memory_reserved_mb"),
                }
        
        return status

    async def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        task: str = "transcribe"
    ) -> TranscriptionResult:
        """
        Transcreve um arquivo de áudio.
        
        Args:
            audio_path: Caminho para o arquivo de áudio
            language: Código do idioma (ex: 'pt', 'en') ou None para auto
            task: 'transcribe' ou 'translate'
            
        Returns:
            TranscriptionResult com texto e segmentos
            
        Raises:
            AudioTranscriptionException: Se transcrição falhar
        """
        # Garante que modelo está carregado
        if not self.is_loaded():
            self.load_model()
        
        self._last_used_at = now_brazil()
        
        # Valida arquivo
        path = Path(audio_path)
        if not path.exists():
            raise AudioTranscriptionException(f"Arquivo não encontrado: {audio_path}")
        
        if path.stat().st_size == 0:
            raise AudioTranscriptionException(f"Arquivo vazio: {audio_path}")
        
        try:
            logger.info(f"Iniciando transcrição: {path.name}")
            start_time = time.time()
            
            # Configurações de transcrição
            beam_size = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
            
            # Executa transcrição
            segments_iter, info = self._model.transcribe(
                str(path),
                language=language if language != "auto" else None,
                task=task,
                beam_size=beam_size,
                word_timestamps=True,
                condition_on_previous_text=True,
            )
            
            # Coleta segmentos
            segments = []
            full_text_parts = []
            
            for segment in segments_iter:
                seg_dict = {
                    "text": segment.text,
                    "start": segment.start,
                    "end": segment.end,
                    "words": [],
                }
                
                # Processa word-level timestamps se disponível
                if segment.words:
                    for word in segment.words:
                        seg_dict["words"].append({
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "probability": getattr(word, "probability", 1.0),
                        })
                
                segments.append(seg_dict)
                full_text_parts.append(segment.text)
            
            processing_time = time.time() - start_time
            full_text = " ".join(full_text_parts).strip()
            
            logger.info(
                f"Transcrição concluída: {len(segments)} segmentos em "
                f"{processing_time:.2f}s"
            )
            
            return TranscriptionResult(
                text=full_text,
                segments=segments,
                language=info.language if hasattr(info, "language") else language,
                processing_time=processing_time,
                word_timestamps=any(len(s.get("words", [])) > 0 for s in segments),
            )
            
        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")
            raise AudioTranscriptionException(f"Falha na transcrição: {str(e)}")

    def __del__(self) -> None:
        """Destructor para garantir cleanup."""
        try:
            if self._model is not None:
                self._model = None
                from common.gpu_utils import cleanup_cuda
                cleanup_cuda()
        except Exception:
            pass  # Ignora erros no destructor

import datetime


class ModelManager:
    """Gerenciador de ciclo de vida do modelo Whisper.

    Classe regular — cada chamada a ModelManager() retorna uma nova instância,
    permitindo injeção de dependência e testes isolados.

    Features:
    - Lazy loading (carrega sob demanda)
    - Auto-unload após timeout de inatividade
    - Cache de engines para múltiplos modelos
    """

    DEFAULT_IDLE_TIMEOUT_MINUTES = 30

    def __init__(self, device_manager: IDeviceManager | None = None) -> None:
        self._device_manager = device_manager or TorchDeviceManager()
        self._engines: dict[str, WhisperEngine] = {}
        self._last_accessed: dict[str, Any] = {}

    @property
    def device_manager(self) -> IDeviceManager:
        return self._device_manager

    def get_or_create_engine(
        self,
        model_size: str = "base",
        **kwargs: Any
    ) -> WhisperEngine:
        """Obtém ou cria um engine para o modelo especificado."""
        cache_key = f"{model_size}"
        if cache_key not in self._engines:
            logger.info(f"Criando novo engine para {cache_key}")
            self._engines[cache_key] = WhisperEngine(
                model_size=model_size,
                device_manager=self.device_manager,
                **kwargs
            )

        self._last_accessed[cache_key] = now_brazil()
        return self._engines[cache_key]

    async def unload_idle_engines(self, timeout_minutes: int | None = None) -> int:
        """Descarrega engines inativos."""
        timeout = timeout_minutes or self.DEFAULT_IDLE_TIMEOUT_MINUTES
        cutoff = now_brazil() - datetime.timedelta(minutes=timeout)

        unloaded = 0
        for key, last_access in list(self._last_accessed.items()):
            if last_access < cutoff:
                engine = self._engines.get(key)
                if engine and engine.is_loaded():
                    await engine.unload_model()
                    unloaded += 1
                    logger.info(f"Engine {key} descarregado por inatividade")

        return unloaded

    def get_loaded_engines(self) -> list[str]:
        """Retorna lista de engines carregados."""
        return [k for k, e in self._engines.items() if e.is_loaded()]

    async def unload_all(self) -> None:
        """Descarrega todos os engines."""
        for engine in self._engines.values():
            if engine.is_loaded():
                await engine.unload_model()
        self._engines.clear()
        self._last_accessed.clear()
        logger.info("Todos os engines descarregados")


class EngineRegistry:
    """Registro de factories para criação de engines (Open-Closed Principle).

    Permite registrar novos tipos de engine sem modificar código existente.

    Example:
        registry = EngineRegistry()
        registry.register(WhisperEngineEnum.FASTER_WHISPER, lambda **kw: WhisperEngine(**kw))
        engine = registry.create(WhisperEngineEnum.FASTER_WHISPER, model_size="base")
    """

    def __init__(self) -> None:
        self._factories: dict[_WhisperEngineEnum, Callable[..., TranscriptionEngine]] = {}

    def register(self, engine_type: _WhisperEngineEnum, factory: Callable[..., TranscriptionEngine]) -> None:
        """Registra uma factory para um tipo de engine."""
        if engine_type in self._factories:
            logger.warning(f"Factory já registrada para {engine_type}, sobrescrevendo")
        self._factories[engine_type] = factory

    def create(
        self,
        engine_type: _WhisperEngineEnum,
        **kwargs: Any
    ) -> TranscriptionEngine:
        """Cria um engine do tipo registrado."""
        if engine_type not in self._factories:
            raise AudioTranscriptionException(f"Engine não suportado ou sem factory registrada: {engine_type}")

        logger.info(f"Criando engine via registry: type={engine_type}, kwargs={kwargs}")
        return self._factories[engine_type](**kwargs)


def get_whisper_engine(
    model_size: str = "base",
    engine_type: _WhisperEngineEnum = _WhisperEngineEnum.FASTER_WHISPER,
) -> TranscriptionEngine:
    """Factory function compatível com código legado.

    Usa EngineRegistry internamente para criar engines de forma extensível (OCP).
    Novos tipos devem ser registrados via registry.register() em vez de adicionar branches aqui.
    """
    if engine_type == _WhisperEngineEnum.FASTER_WHISPER:
        return WhisperEngine(model_size=model_size)
    elif engine_type == _WhisperEngineEnum.OPENAI_WHISPER:
        logger.warning(
            f"Engine {engine_type} não implementado separadamente, "
            "usando faster-whisper como fallback"
        )
        return WhisperEngine(model_size=model_size)
    else:
        raise AudioTranscriptionException(f"Engine não suportado: {engine_type}")


__all__ = [
    "WhisperEngine",
    "ModelManager",
    "get_whisper_engine",
    "EngineRegistry",
]