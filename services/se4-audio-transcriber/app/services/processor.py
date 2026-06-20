from __future__ import annotations

import gc
import json
import os
import asyncio
from pathlib import Path
from typing import Any
import torch
from pydub import AudioSegment
from common.datetime_utils import now_brazil
from ..domain.models import Job, JobStatus, TranscriptionSegment, WhisperEngine
from ..shared.audio_chunker import AudioChunker
from ..shared.chunk_transcriber import ChunkTranscriber
from ..shared.audio_converter import convert_to_wav, has_audio_stream
from ..shared.caption_formatter import CaptionFormatter
from ..shared.error_handling import retry_on_transient_error, safe_cleanup
from ..shared.exceptions import AudioTranscriptionException
from ..shared.job_state_updater import JobStateUpdater
from ..core.config import get_settings
from .faster_whisper_manager import FasterWhisperModelManager
from .openai_whisper_manager import OpenAIWhisperManager
from .whisperx_manager import WhisperXManager
import time
from common.log_utils import get_logger

logger = get_logger(__name__)

_ENGINE_MAP = {
    WhisperEngine.FASTER_WHISPER: FasterWhisperModelManager,
    WhisperEngine.OPENAI_WHISPER: OpenAIWhisperManager,
    WhisperEngine.WHISPERX: WhisperXManager,
}

WHISPER_MODEL_SIZES = {
    'tiny': 75,
    'base': 150,
    'small': 500,
    'medium': 1500,
    'large': 3000,
}

class TranscriptionProcessor:
    def __init__(self, output_dir: str | None = None, model_dir: str | None = None) -> None:
        self.job_store = None  # Will be injected
        self.state = JobStateUpdater(self.job_store)
        self.current_job_id: str | None = None
        self.settings = get_settings()
        self.output_dir = output_dir or self.settings.get('transcription_dir', './transcriptions')
        self.model_dir = model_dir or self.settings.get('whisper_download_root', './models')
        
        # Managers para diferentes engines
        self.model_managers = {}
        self.current_engine = WhisperEngine.FASTER_WHISPER
        
        # Backwards compatibility
        self.model_manager = None  # Será definido quando carregar
        self.model = None  # Para compatibilidade
        self.device = None
        self.model_loaded = False

    async def _run_with_timeout(self, awaitable: Any, timeout_seconds: int, operation_name: str) -> Any:
        """Executa awaitable com timeout explícito para evitar jobs pendurados indefinidamente."""
        try:
            return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise AudioTranscriptionException(
                f"Timeout ao executar '{operation_name}' após {timeout_seconds}s"
            ) from exc
    
    def _get_model_manager(self, engine: WhisperEngine) -> Any:
        """
        Retorna o model manager para o engine especificado.
        Cria e cacheia managers sob demanda.
        """
        if engine not in self.model_managers:
            logger.info(f"🔧 Criando manager para engine: {engine.value}")

            manager_cls = _ENGINE_MAP.get(engine)
            if manager_cls is None:
                raise AudioTranscriptionException(f"Engine não suportado: {engine}")
            self.model_managers[engine] = manager_cls(model_dir=Path(self.model_dir))
        
        return self.model_managers[engine]
    
    def _check_disk_space(self, file_path: str, output_dir: str) -> bool:
        """Verifica se há espaço em disco suficiente para transcrição."""
        try:
            import shutil
            
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Estima espaço necessário: 2x o tamanho do arquivo (transcripts são pequenos, mas previne)
            estimated_space_needed = file_size * 2
            
            stat = shutil.disk_usage(output_dir)
            available_space = stat.free
            available_space_mb = available_space / (1024 * 1024)
            
            logger.info(f"💾 Espaço em disco - Disponível: {available_space_mb:.2f}MB, Estimado necessário: {estimated_space_needed/(1024*1024):.2f}MB")
            
            if available_space < estimated_space_needed:
                logger.error(f"❌ Espaço em disco insuficiente! Disponível: {available_space_mb:.2f}MB")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível verificar espaço em disco: {e}")
            return True  # fail-open
    
    def _detect_device(self, engine: WhisperEngine = WhisperEngine.FASTER_WHISPER) -> str:
        """Detecta dispositivo para o engine especificado via IDeviceManager (DIP)"""
        from .device_manager import TorchDeviceManager
        preferred_device = self.settings.get('whisper_device', 'auto').lower()
        if not preferred_device or preferred_device == 'cpu':
            preferred_device = 'cpu'
        elif preferred_device != 'cuda':
            preferred_device = 'auto'
        return TorchDeviceManager(preferred_device=preferred_device).detect_device()
    
    def _load_model(self, engine: WhisperEngine = WhisperEngine.FASTER_WHISPER) -> None:
        """
        Carrega modelo usando o engine especificado.
        
        Args:
            engine: Engine a ser usado (faster-whisper, openai-whisper, whisperx)
        """
        manager = self._get_model_manager(engine)
        
        # Verifica se já está carregado
        if manager.is_loaded:
            logger.info(f"ℹ️ Modelo {engine.value} já está carregado")
            self.model_manager = manager
            self.current_engine = engine
            self.model_loaded = True
            self.device = manager.device
            return
        
        logger.info(f"📦 Carregando modelo {engine.value}...")
        manager.load_model()
        
        # Atualiza referências
        self.model_manager = manager
        self.current_engine = engine
        self.device = manager.device
        self.model_loaded = True
        
        logger.info(f"✅ Modelo {engine.value} carregado no {self.device.upper()}")

    def unload_model(self) -> dict[str, Any]:
        """
        Descarrega modelo Whisper da memória/GPU para economia de recursos.
        
        Libera:
        - Memória RAM (~500MB - 3GB dependendo do modelo)
        - Memória GPU/VRAM (se CUDA disponível)
        - Reduz consumo energético
        - Reduz pegada de carbono
        
        Returns:
            dict: Relatório com memória liberada e status
        """
        try:
            report = {
                "success": False,
                "message": "",
                "memory_freed": {
                    "ram_mb": 0.0,
                    "vram_mb": 0.0
                },
                "device_was": None,
                "model_name": self.settings.get('whisper_model', 'base')
            }
            
            if self.model is None or not self.model_loaded:
                report["message"] = "Modelo já estava descarregado"
                report["success"] = True
                logger.info("ℹ️ Modelo Whisper já estava descarregado")
                return report
            
            # Captura informações antes de descarregar
            report["device_was"] = self.device
            
            # Se está na GPU, captura uso de memória ANTES
            vram_before = 0.0
            if self.device == 'cuda' and torch.cuda.is_available():
                vram_before = torch.cuda.memory_allocated(0) / 1024**2  # MB
                logger.info(f"📊 VRAM antes do unload: {vram_before:.2f} MB")
            
            # Remove modelo
            logger.warning(f"🔥 Descarregando modelo Whisper '{report['model_name']}' do {self.device}...")
            
            del self.model
            self.model = None
            self.model_loaded = False
            self.device = None
            
            # Força garbage collection
            gc.collect()
            
            # Se estava na GPU, limpa cache CUDA
            if report["device_was"] == 'cuda' and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # Aguarda operações GPU finalizarem
                
                # Captura memória APÓS
                vram_after = torch.cuda.memory_allocated(0) / 1024**2  # MB
                report["memory_freed"]["vram_mb"] = round(vram_before - vram_after, 2)
                
                logger.info(f"📊 VRAM depois do unload: {vram_after:.2f} MB")
                logger.info(f"✅ VRAM liberada: {report['memory_freed']['vram_mb']} MB")
            
            report["memory_freed"]["ram_mb"] = WHISPER_MODEL_SIZES.get(report['model_name'], 150)
            
            report["success"] = True
            report["message"] = (
                f"✅ Modelo '{report['model_name']}' descarregado com sucesso do {report['device_was'].upper()}. "
                f"Recursos liberados para economia de energia e redução de pegada de carbono. "
                f"Modelo será recarregado automaticamente quando houver nova task."
            )
            
            logger.warning(f"♻️ Modelo Whisper DESCARREGADO - Economia de recursos ativada")
            logger.info(f"   └─ RAM liberada (estimado): ~{report['memory_freed']['ram_mb']} MB")
            if report["memory_freed"]["vram_mb"] > 0:
                logger.info(f"   └─ VRAM liberada: {report['memory_freed']['vram_mb']} MB")
            logger.info(f"   └─ Dispositivo anterior: {report['device_was'].upper()}")
            
            return report
            
        except Exception as e:
            error_msg = f"Erro ao descarregar modelo: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "memory_freed": {"ram_mb": 0.0, "vram_mb": 0.0}
            }
    
    def load_model_explicit(self) -> dict[str, Any]:
        """
        Carrega modelo Whisper explicitamente na memória/GPU.
        
        Útil para:
        - Pré-carregar modelo antes de processar batch de tasks
        - Reduzir latência da primeira transcrição
        - Preparar sistema após unload manual
        
        Returns:
            dict: Relatório com memória usada e status
        """
        try:
            report = {
                "success": False,
                "message": "",
                "memory_used": {
                    "ram_mb": 0.0,
                    "vram_mb": 0.0
                },
                "device": None,
                "model_name": self.settings.get('whisper_model', 'base')
            }
            
            if self.model is not None and self.model_loaded:
                report["success"] = True
                report["device"] = self.device
                report["message"] = f"Modelo já estava carregado no {self.device.upper()}"
                logger.info(f"ℹ️ Modelo Whisper já carregado no {self.device}")
                return report
            
            logger.info(f"🚀 Carregando modelo Whisper '{report['model_name']}' explicitamente...")
            
            # Captura memória GPU ANTES (se disponível)
            vram_before = 0.0
            if torch.cuda.is_available():
                vram_before = torch.cuda.memory_allocated(0) / 1024**2  # MB
            
            # Carrega modelo (usa _load_model que já tem lógica de retry e device detection)
            self._load_model()
            
            report["success"] = True
            report["device"] = self.device
            
            # Captura memória GPU DEPOIS
            if self.device == 'cuda' and torch.cuda.is_available():
                vram_after = torch.cuda.memory_allocated(0) / 1024**2  # MB
                report["memory_used"]["vram_mb"] = round(vram_after - vram_before, 2)
                logger.info(f"📊 VRAM usada: {report['memory_used']['vram_mb']} MB")
            
            report["memory_used"]["ram_mb"] = WHISPER_MODEL_SIZES.get(report['model_name'], 150)
            
            report["message"] = (
                f"✅ Modelo '{report['model_name']}' carregado com sucesso no {self.device.upper()}. "
                f"Sistema pronto para transcrições de baixa latência."
            )
            
            logger.info(f"✅ Modelo carregado explicitamente")
            logger.info(f"   └─ Dispositivo: {self.device.upper()}")
            logger.info(f"   └─ RAM usada (estimado): ~{report['memory_used']['ram_mb']} MB")
            if report["memory_used"]["vram_mb"] > 0:
                logger.info(f"   └─ VRAM usada: {report['memory_used']['vram_mb']} MB")
            
            return report
            
        except Exception as e:
            error_msg = f"Erro ao carregar modelo: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "memory_used": {"ram_mb": 0.0, "vram_mb": 0.0}
            }
    
    def get_model_status(self) -> dict[str, Any]:
        """
        Retorna status atual do modelo.
        
        Returns:
            dict: Status do modelo (loaded/unloaded, device, memory, etc)
        """
        status = {
            "loaded": self.model_loaded and self.model is not None,
            "model_name": self.settings.get('whisper_model', 'base'),
            "device": self.device if self.model_loaded else None,
            "memory": {
                "vram_mb": 0.0,
                "cuda_available": torch.cuda.is_available()
            }
        }
        
        # Se modelo está carregado na GPU, mostra uso de VRAM
        if status["loaded"] and self.device == 'cuda' and torch.cuda.is_available():
            status["memory"]["vram_mb"] = round(torch.cuda.memory_allocated(0) / 1024**2, 2)
            status["memory"]["vram_reserved_mb"] = round(torch.cuda.memory_reserved(0) / 1024**2, 2)
            
            # Informações da GPU
            status["gpu_info"] = {
                "name": torch.cuda.get_device_name(0),
                "device_count": torch.cuda.device_count(),
                "cuda_version": torch.version.cuda
            }
        
        return status
    
    def transcribe_audio(self, job: Job) -> Job:
        """
        Método síncrono para Celery task processar transcrição
        Converte o processamento assíncrono em síncrono
        """
        timeout_seconds = int(self.settings.get("job_processing_timeout_seconds", 3600))
        coroutine = self._run_with_timeout(
            self.process_transcription_job(job),
            timeout_seconds,
            "process_transcription_job",
        )
        try:
            asyncio.get_running_loop()
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(coroutine)
            finally:
                loop.close()
        except RuntimeError:
            asyncio.run(coroutine)

        return job
    
    async def process_transcription_job(self, job: Job) -> None:
        """Processa um job de transcrição"""
        converted_file = None
        is_temp_file = False

        try:
            logger.info(f"Iniciando processamento do job: {job.id}")

            self.state.mark_processing(job, started_at=job.started_at or now_brazil())
            self.current_job_id = job.id
            
            # ==========================================
            # VALIDAÇÃO CRÍTICA: Verifica se arquivo existe
            # ==========================================
            input_path = Path(job.input_file)
            
            # Tenta encontrar arquivo em múltiplos caminhos possíveis
            upload_dir = Path(self.settings.get('upload_dir', './uploads'))
            possible_paths = [
                input_path,  # Caminho original
                upload_dir / input_path.name,  # Usando upload_dir configurável
                Path("./data/uploads") / input_path.name,  # ./data/uploads/filename
            ]
            
            actual_file_path = None
            for path in possible_paths:
                if path.exists() and path.is_file():
                    actual_file_path = path
                    logger.info(f"✅ Arquivo encontrado em: {path}")
                    break
                else:
                    logger.debug(f"⚠️ Arquivo NÃO encontrado em: {path}")
            
            if actual_file_path is None:
                error_msg = (
                    f"Arquivo de entrada não encontrado! "
                    f"Procurado em: {[str(p) for p in possible_paths]}. "
                    f"Verifique se o arquivo foi enviado corretamente."
                )
                logger.error(f"❌ {error_msg}")
                raise AudioTranscriptionException(error_msg)
            
            # Valida que o arquivo não está vazio
            file_size = actual_file_path.stat().st_size
            if file_size == 0:
                raise AudioTranscriptionException(
                    f"Arquivo de entrada está vazio (0 bytes): {actual_file_path}"
                )
            
            logger.info(f"📁 Arquivo validado: {actual_file_path} ({file_size / (1024*1024):.2f} MB)")
            
            # Atualiza job com caminho correto e absoluto
            job.input_file = str(actual_file_path.absolute())
            job.file_size_input = file_size
            
            # ==========================================
            # CONVERSÃO AUTOMÁTICA PARA WAV
            # Converte OGG, MP3, MP4, M4A, WEBM etc. para WAV 16kHz mono
            # Resolve bug "tuple index out of range" do faster-whisper
            # ==========================================
            try:
                converted_file, is_temp_file = convert_to_wav(actual_file_path, self.settings)
                if is_temp_file:
                    original_ext = actual_file_path.suffix.lower()
                    logger.info(f"Arquivo {original_ext} convertido para WAV: {converted_file.name}")
                    job.input_file = str(converted_file.absolute())
            except AudioTranscriptionException as e:
                error_msg = (
                    f"Falha ao preparar arquivo de áudio para transcrição: {e}. "
                    f"O arquivo '{actual_file_path.name}' não pôde ser processado. "
                    f"Verifique se o arquivo contém um stream de áudio válido."
                )
                logger.error(f"❌ {error_msg}")
                raise AudioTranscriptionException(error_msg)
            
            # Carrega modelo do engine especificado no job
            engine = job.engine if hasattr(job, 'engine') else WhisperEngine.FASTER_WHISPER
            logger.info(f"🔧 Usando engine: {engine.value}")
            load_timeout_seconds = int(self.settings.get("async_timeout_seconds", 1800))
            await self._run_with_timeout(
                asyncio.to_thread(self._load_model, engine),
                load_timeout_seconds,
                "load_model",
            )
            
            # Atualiza progresso (model loaded)
            self.state.set_progress(25.0, job.id)
            
            # Decide se usa chunking baseado nas configurações e duração do áudio
            enable_chunking = self.settings.get('enable_chunking', False)
            
            if enable_chunking:
                # Verifica duração do áudio para decidir se vale a pena usar chunks
                audio = await asyncio.to_thread(AudioSegment.from_file, job.input_file)
                duration_seconds = len(audio) / 1000.0
                
                # Usa chunking apenas para áudios longos (configurável, padrão 5 min = 300s)
                min_duration_for_chunks = int(self.settings.get('whisper_min_duration_for_chunks', 300))
                
                if duration_seconds > min_duration_for_chunks:
                    logger.info(f"Áudio longo detectado ({duration_seconds:.1f}s), usando chunking")
                    transcription_timeout = int(self.settings.get("job_processing_timeout_seconds", 3600))
                    chunk_transcriber = ChunkTranscriber(self.settings, self.state)
                    result = await self._run_with_timeout(
                        chunk_transcriber.transcribe(
                            job.input_file,
                            job.language_in,
                            job.language_out,
                            transcribe_fn=self._transcribe_direct,
                            job_id=self.current_job_id,
                            audio=audio,
                        ),
                        transcription_timeout,
                        "transcribe_with_chunking",
                    )
                else:
                    logger.info(f"Áudio curto ({duration_seconds:.1f}s), transcrição direta")
                    direct_timeout = int(self.settings.get("async_timeout_seconds", 1800))
                    result = await self._run_with_timeout(
                        asyncio.to_thread(
                            self._transcribe_direct,
                            job.input_file,
                            job.language_in,
                            job.language_out,
                        ),
                        direct_timeout,
                        "transcribe_direct",
                    )
            else:
                logger.info("Chunking desabilitado, transcrição direta")
                direct_timeout = int(self.settings.get("async_timeout_seconds", 1800))
                result = await self._run_with_timeout(
                    asyncio.to_thread(
                        self._transcribe_direct,
                        job.input_file,
                        job.language_in,
                        job.language_out,
                    ),
                    direct_timeout,
                    "transcribe_direct",
                )
            
            # Atualiza progresso
            self.state.set_progress(75.0, job.id)
            
            # Converte segments para o formato com start, end, duration E words
            transcription_segments = []
            for seg in result["segments"]:
                # Converte words se presentes
                words_list = None
                if "words" in seg and seg["words"]:
                    from ..domain.models import TranscriptionWord  # 🔧 FIX: Import correto
                    words_list = [
                        TranscriptionWord(
                            word=w["word"],
                            start=w["start"],
                            end=w["end"],
                            probability=w.get("probability", 1.0)
                        )
                        for w in seg["words"]
                    ]
                
                segment = TranscriptionSegment(
                    text=seg["text"].strip(),
                    start=seg["start"],
                    end=seg["end"],
                    duration=seg["end"] - seg["start"],
                    words=words_list  # ✅ Preserva word-level timestamps!
                )
                transcription_segments.append(segment)
            
            # Salva arquivo de transcrição
            transcription_dir = Path(self.output_dir)
            transcription_dir.mkdir(parents=True, exist_ok=True)
            
            output_path = transcription_dir / f"{job.id}_transcription.srt"
            
            # Converte para formato SRT
            srt_content = CaptionFormatter.to_srt(result["segments"])
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            
            # Finaliza job via JobStateUpdater
            language_detected = None
            if "language" in result:
                language_detected = result["language"]
                logger.info(f"Idioma detectado pelo Whisper: {result['language']}")

            self.state.mark_completed(
                job,
                output_file=str(output_path),
                text=result["text"],
                segments=transcription_segments,
                file_size_output=output_path.stat().st_size,
                language_detected=language_detected,
            )
            
            logger.info(f"Job {job.id} transcrito com sucesso")
            logger.info(f"Total de segmentos: {len(transcription_segments)}")
            
        except AudioTranscriptionException as e:
            self.state.mark_failed(job, str(e))
            logger.error("Job %s falhou: %s", job.id, e)
            raise

        except Exception as e:
            self.state.mark_failed(job, str(e))
            logger.error("Job %s falhou (erro inesperado): %s", job.id, e)
            raise AudioTranscriptionException(f"Erro na transcrição: {str(e)}") from e
        
        finally:
            # Limpa arquivo WAV temporário convertido — safe_cleanup para Pattern B consistency.
            if is_temp_file and converted_file is not None:
                temp_path = Path(converted_file) if not isinstance(converted_file, Path) else converted_file

                def _remove_temp():
                    if temp_path.exists():
                        temp_path.unlink()
                        logger.info("Arquivo temporário removido: %s", temp_path.name)

                safe_cleanup(_remove_temp, label="Remover arquivo temporário")

            # Auto-unload do modelo para liberar VRAM quando ocioso.
            def _unload_model():
                unload_result = self.model_manager.unload_model()
                if unload_result.get("success"):
                    logger.info(
                        "🧹 Modelo descarregado pós-job (freed ~%s MB RAM)",
                        unload_result["memory_freed"]["ram_mb"],
                    )

            safe_cleanup(_unload_model, label="Descarregar modelo")

    
    def _transcribe_direct(self, audio_file: str, language_in: str = "auto", language_out: str | None = None) -> dict[str, Any]:
        """
        Transcrição ou tradução direta sem chunking
        
        Args:
            audio_file: Caminho do arquivo de áudio
            language_in: Idioma de entrada ("auto" para detecção automática)
            language_out: Idioma de saída para tradução (None = apenas transcrever)
        
        Returns:
            dict: Resultado com 'text', 'segments' e 'language' detectado
        """
        logger.info(f"🎙️ Transcrevendo diretamente: {audio_file}")
        
        # Valida que arquivo existe ANTES de processar
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise AudioTranscriptionException(
                f"Arquivo de áudio não encontrado para transcrição: {audio_file}"
            )
        
        # Valida que arquivo não está vazio
        if audio_path.stat().st_size == 0:
            raise AudioTranscriptionException(
                f"Arquivo de áudio está vazio: {audio_file}"
            )
        
        # Se language_out for especificado e diferente de language_in, usa translate
        needs_translation = language_out is not None and language_out != language_in and language_in != ''
        
        if needs_translation:
            logger.info(f"Traduzindo de {language_in} para {language_out}")
            # Whisper translate() sempre traduz para inglês
            # Se language_out não for inglês, teremos que fazer em 2 etapas
            if language_out.lower() not in ['en', 'english']:
                logger.warning(f"Whisper só traduz para inglês. Tradução para {language_out} não suportada diretamente.")
                # Fallback: apenas transcreve no idioma original
                needs_translation = False
        
        ##############################################################
        # CONFIGURAÇÃO DE OPÇÕES DO WHISPER
        ##############################################################
        # NOTA: fp16 é configurado na criação do modelo, não no transcribe()
        # Faster-Whisper usa compute_type no modelo, não fp16 no transcribe()
        base_options = {
            "beam_size": self.settings.get('whisper_beam_size', 5),
        }
        
        from ..core.constants import DEFAULT_MAX_RETRIES, DEFAULT_RETRY_BACKOFF_BASE as _retry_base

        # Retry com backoff exponencial — apenas para erros transitórios (I/O, CUDA OOM).
        # Erros de programação como ValueError/TypeError NÃO são retried.
        max_retries = self.settings.get('whisper_max_retries', DEFAULT_MAX_RETRIES)
        retry_delay = float(self.settings.get('whisper_retry_backoff_base', _retry_base))

        @retry_on_transient_error(max_retries=max_retries - 1, base_delay=retry_delay)
        def _do_transcribe():
            if needs_translation:
                logger.info(f"🌐 Usando {self.current_engine.value} task='translate' para traduzir para inglês")
                result = self.model_manager.transcribe(
                    Path(audio_file),
                    language=None if language_in == "auto" else language_in,
                    task="translate",
                    **base_options
                )
                logger.info(f"✅ Tradução concluída. Idioma detectado: {result.get('language', 'unknown')}")
            else:
                logger.info(f"📝 Usando {self.current_engine.value} task='transcribe' para transcrever em {language_in}")
                result = self.model_manager.transcribe(
                    Path(audio_file),
                    language=None if language_in == "auto" else language_in,
                    task="transcribe",
                    **base_options
                )
                logger.info(f"✅ Transcrição concluída. Idioma: {result.get('language', language_in)}")
            return result

        try:
            return _do_transcribe()
        except AudioTranscriptionException as e:
            raise e from None if not e.__cause__ else e
    

