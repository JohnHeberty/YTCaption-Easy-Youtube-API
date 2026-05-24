"""
Implementação do TranscriptionEngine usando Whisper.

Implementa a interface TranscriptionEngine usando o faster-whisper
como backend principal, com suporte para fallback em outras implementações.

Segue o Single Responsibility Principle (SRP) ao encapsular toda a
lógica de transcrição em uma única classe bem definida.
"""
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import gc

import torch
from faster_whisper import WhisperModel

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from ..domain.interfaces import TranscriptionEngine, TranscriptionResult
from ..domain.models import WhisperEngine
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
        device: Optional[str] = None,
        compute_type: str = "float16",
        download_root: Optional[str] = None,
        cpu_threads: int = 0,
        num_workers: int = 1,
    ):
        """
        Inicializa o engine Whisper.
        
        Args:
            model_size: Tamanho do modelo (tiny, base, small, medium, large-v1, large-v2, large-v3)
            device: Dispositivo ('cuda', 'cpu', ou None para auto-detect)
            compute_type: Tipo de computação ('float16', 'int8', 'int8_float16')
            download_root: Diretório para download de modelos
            cpu_threads: Threads para CPU (0 = auto)
            num_workers: Workers para processamento
        """
        self.model_size = model_size
        self.device = device or self._detect_device()
        self.compute_type = compute_type if self.device == "cuda" else "int8"
        self.download_root = download_root or os.getenv("WHISPER_MODEL_DIR", "./models")
        self.cpu_threads = cpu_threads
        self.num_workers = num_workers
        
        self._model: Optional[WhisperModel] = None
        self._loaded_at: Optional[Any] = None
        self._last_used_at: Optional[Any] = None
        self._load_count: int = 0
        
        logger.info(
            f"WhisperEngine criado: model={model_size}, device={self.device}, "
            f"compute_type={self.compute_type}"
        )

    def _detect_device(self) -> str:
        """Detecta automaticamente o melhor dispositivo disponível."""
        if torch.cuda.is_available():
            try:
                # Testa se CUDA realmente funciona
                torch.cuda.init()
                device_name = torch.cuda.get_device_name(0)
                logger.info(f"CUDA detectado: {device_name}")
                return "cuda"
            except Exception as e:
                logger.warning(f"CUDA detectado mas não funcional: {e}, usando CPU")
                return "cpu"
        return "cpu"

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
            
            # Força garbage collection
            gc.collect()
            
            # Limpa cache CUDA se estava na GPU
            if device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.info("Cache CUDA limpo")
            
            self._loaded_at = None
            self._last_used_at = None
            
            logger.info(f"Modelo {model_size} descarregado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao descarregar modelo: {e}")
            # Não lança exceção em unload - apenas loga

    def is_loaded(self) -> bool:
        """Retorna True se o modelo está carregado."""
        return self._model is not None

    def get_status(self) -> Dict[str, Any]:
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
        
        # Informações de GPU
        if self.device == "cuda" and torch.cuda.is_available():
            status["gpu"] = {
                "name": torch.cuda.get_device_name(0),
                "memory_allocated_mb": round(torch.cuda.memory_allocated(0) / 1024**2, 2),
                "memory_reserved_mb": round(torch.cuda.memory_reserved(0) / 1024**2, 2),
            }
        
        return status

    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
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

    def __del__(self):
        """Destructor para garantir cleanup."""
        try:
            if self._model is not None:
                self._model = None
                gc.collect()
                if self.device == "cuda" and torch.cuda.is_available():
                    torch.cuda.empty_cache()
        except Exception:
            pass  # Ignora erros no destructor

class ModelManager:
    """
    Gerenciador de ciclo de vida do modelo Whisper.
    
    Implementa o pattern Singleton para garantir que apenas
    uma instância do modelo exista, com gerenciamento automático
    de recursos.
    
    Features:
    - Lazy loading (carrega sob demanda)
    - Auto-unload após timeout de inatividade
    - Cache de engines para múltiplos modelos
    - Thread-safe (para uso com Celery workers)
    
    Example:
        manager = ModelManager()
        engine = manager.get_or_create_engine("base")
        result = await engine.transcribe("audio.mp3")
    """

    _instance: Optional["ModelManager"] = None
    _engines: Dict[str, WhisperEngine] = {}
    _last_accessed: Dict[str, Any] = {}
    
    DEFAULT_IDLE_TIMEOUT_MINUTES: int = 30
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._engines = {}
            cls._instance._last_accessed = {}
        return cls._instance
    
    def get_or_create_engine(
        self,
        model_size: str = "base",
        device: Optional[str] = None,
        **kwargs
    ) -> WhisperEngine:
        """
        Obtém ou cria um engine para o modelo especificado.
        
        Args:
            model_size: Tamanho do modelo
            device: Dispositivo (auto-detect se None)
            **kwargs: Configurações adicionais
            
        Returns:
            WhisperEngine configurado
        """
        cache_key = f"{model_size}_{device or 'auto'}"
        
        if cache_key not in self._engines:
            logger.info(f"Criando novo engine para {cache_key}")
            self._engines[cache_key] = WhisperEngine(
                model_size=model_size,
                device=device,
                **kwargs
            )
        
        self._last_accessed[cache_key] = now_brazil()
        return self._engines[cache_key]
    
    async def unload_idle_engines(self, timeout_minutes: int = None) -> int:
        """
        Descarrega engines inativos.
        
        Args:
            timeout_minutes: Minutos de inatividade (padrão: 30)
            
        Returns:
            int: Número de engines descarregados
        """
        timeout = timeout_minutes or self.DEFAULT_IDLE_TIMEOUT_MINUTES
        cutoff = now_brazil() - __import__("datetime").timedelta(minutes=timeout)
        
        unloaded = 0
        for key, last_access in list(self._last_accessed.items()):
            if last_access < cutoff:
                engine = self._engines.get(key)
                if engine and engine.is_loaded():
                    await engine.unload_model()
                    unloaded += 1
                    logger.info(f"Engine {key} descarregado por inatividade")
        
        return unloaded
    
    def get_loaded_engines(self) -> List[str]:
        """Retorna lista de engines carregados."""
        return [
            key for key, engine in self._engines.items()
            if engine.is_loaded()
        ]
    
    async def unload_all(self) -> None:
        """Descarrega todos os engines."""
        for engine in self._engines.values():
            if engine.is_loaded():
                await engine.unload_model()
        self._engines.clear()
        self._last_accessed.clear()
        logger.info("Todos os engines descarregados")

def get_whisper_engine(
    model_size: str = "base",
    engine_type: WhisperEngine = WhisperEngine.FASTER_WHISPER
) -> TranscriptionEngine:
    """
    Factory function para criar engines de transcrição.
    
    Args:
        model_size: Tamanho do modelo
        engine_type: Tipo de engine
        
    Returns:
        TranscriptionEngine configurado
    """
    if engine_type == WhisperEngine.FASTER_WHISPER:
        return WhisperEngine(model_size=model_size)
    elif engine_type == WhisperEngine.OPENAI_WHISPER:
        # Fallback para WhisperEngine (faster-whisper é mais eficiente)
        logger.warning(
            f"Engine {engine_type} não implementado separadamente, "
            "usando faster-whisper"
        )
        return WhisperEngine(model_size=model_size)
    else:
        raise AudioTranscriptionException(f"Engine não suportado: {engine_type}")

__all__ = [
    "WhisperEngine",
    "ModelManager",
    "get_whisper_engine",
]