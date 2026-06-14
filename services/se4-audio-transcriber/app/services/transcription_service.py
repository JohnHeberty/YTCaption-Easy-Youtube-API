"""
Serviço de transcrição - orquestração de jobs.

Implementa o Open/Closed Principle (OCP) do SOLID:
- Open for extension: novos engines podem ser adicionados
- Closed for modification: código principal não muda

E o Single Responsibility Principle (SRP):
- TranscriptionService: orquestra jobs
- WhisperEngine: executa transcrição
- ModelManager: gerencia ciclo de vida
"""
import os
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import timedelta

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from ..domain.models import Job, JobStatus, WhisperEngine as WhisperEngineEnum, TranscriptionSegment, TranscriptionWord
from ..shared.caption_formatter import CaptionFormatter, convert_to_srt as _convert_to_srt_compat
from ..shared.job_state_updater import JobStateUpdater
from ..shared.error_handling import safe_cleanup
from ..shared.exceptions import AudioTranscriptionException
from ..infrastructure.whisper_engine import WhisperEngine, ModelManager
from ..infrastructure.storage_manager import LocalFileStorage
from ..domain.interfaces import IStorageManager, ITranscriptionService
from ..core.validators import JobIdValidator, LanguageValidator

logger = get_logger(__name__)

class TranscriptionService(ITranscriptionService):
    """
    Serviço de alto nível para orquestração de transcrições.

    Implementa ITranscriptionService (DIP).

    Responsabilidades:
    - Validação de parâmetros
    - Gestão de jobs
    - Seleção de engine
    - Coordenação do fluxo de trabalho

    Não lida com:
    - Carregamento de modelos (delega ao WhisperEngine)
    - Persistência de jobs (delega ao job_store)
    - Processamento de áudio bruto (delega ao WhisperEngine)

    Example:
        service = TranscriptionService()
        job = await service.create_job("audio.mp3", "pt")
        result = await service.process_job(job)
    """

    def __init__(
        self,
        job_store: Optional[Any] = None,
        model_manager: Optional[ModelManager] = None,
        storage_manager: Optional[IStorageManager] = None,
        output_dir: str = "./transcriptions",
        upload_dir: str = "./uploads"
    ):
        """
        Inicializa o serviço.

        Args:
            job_store: Store para persistência de jobs
            model_manager: Gerenciador de modelos (singleton)
            storage_manager: Abstração de armazenamento de arquivos (opcional, backward compat)
            output_dir: Diretório para saída
            upload_dir: Diretório para uploads
        """
        self.job_store = job_store
        self.state = JobStateUpdater(self.job_store)
        self._current_job_id: Optional[str] = None
        self.model_manager = model_manager or ModelManager()
        self.output_dir = Path(output_dir)
        self.upload_dir = Path(upload_dir)

        # Default storage manager para backward compatibility.
        if storage_manager is not None:
            self.storage_manager = storage_manager  # type: ignore[assignment]
        else:
            from ..infrastructure.storage_manager import LocalFileStorage as _LFS

            base = self.upload_dir.parent or Path.cwd()
            self.storage_manager = _LFS(base)  # type: ignore[assignment]

        # Cria diretórios se necessário
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"TranscriptionService iniciado: output={output_dir}, "
            f"upload={upload_dir}"
        )

    async def create_job(
        self,
        filename: str,
        language_in: str = "auto",
        language_out: Optional[str] = None,
        engine: WhisperEngineEnum = WhisperEngineEnum.FASTER_WHISPER,
        file_content: Optional[bytes] = None
    ) -> Job:
        """
        Cria um novo job de transcrição.
        
        Args:
            filename: Nome do arquivo original
            language_in: Idioma de entrada ou 'auto'
            language_out: Idioma de saída (None = mesmo que entrada)
            engine: Engine a usar
            file_content: Conteúdo do arquivo (opcional)
            
        Returns:
            Job criado
        """
        # Validações
        language_in = LanguageValidator.validate(language_in, "language_in")
        
        if language_out is not None:
            language_out = LanguageValidator.validate(language_out, "language_out")
        
        # Cria job
        job = Job.create_new(
            filename=filename,
            operation="transcribe",
            language_in=language_in,
            language_out=language_out,
            engine=engine
        )
        
        # Salva arquivo se fornecido
        if file_content:
            file_path = await self._save_uploaded_file(job.id, filename, file_content)
            job.input_file = str(file_path)
            job.file_size_input = len(file_content)
        
        # Salva job
        if self.job_store:
            self.job_store.save_job(job)
        
        logger.info(f"Job criado: {job.id} ({filename})")
        return job

    async def process_job(self, job: Job) -> Job:
        """
        Processa um job de transcrição.
        
        Fluxo:
        1. Valida arquivo
        2. Obtém engine
        3. Transcreve
        4. Salva resultado
        
        Args:
            job: Job a processar
            
        Returns:
            Job atualizado
        """
        job_id = job.id
        self._current_job_id = job_id
        
        try:
            logger.info(f"Iniciando processamento do job: {job_id}")
            
            # 1. Valida arquivo de entrada
            input_path = await self._validate_and_resolve_file(job)
            if not input_path:
                raise AudioTranscriptionException(f"Arquivo de entrada não encontrado: {job.input_file}")
            
            # Atualiza job
            self.state.mark_processing(job, started_at=now_brazil())
            self.state.set_progress(10.0, job.id)
            
            # 2. Obtém engine
            model_size = os.getenv("WHISPER_MODEL", "base")
            engine = self._get_engine_for_job(job, model_size)
            
            # Carrega modelo se necessário
            if not engine.is_loaded():
                engine.load_model()
            
            self.state.set_progress(25.0, job.id)

            
            # 3. Transcreve
            result = await engine.transcribe(
                str(input_path),
                language=job.language_in if job.language_in != "auto" else None,
                task="translate" if job.needs_translation else "transcribe"
            )

            
            self.state.set_progress(75.0, job.id)
            
            # 4. Converte segmentos
            transcription_segments = self._convert_segments(result.segments)
            
            # 5. Salva arquivo de saída
            output_path = await self._save_transcription(job, result.text, result.segments)
            
            # 6. Finaliza job
            self.state.mark_completed(
                job,
                output_file=str(output_path),
                text=result.text,
                segments=transcription_segments,
                file_size_output=output_path.stat().st_size,
                language_detected=result.language,
            )
            
            logger.info(f"Job {job_id} concluído: {len(transcription_segments)} segmentos")
            return job
            
        except AudioTranscriptionException as e:
            logger.error("Job %s falhou: %s", job_id, e)
            self.state.mark_failed(job, str(e))
            raise

        except Exception as e:
            logger.error("Job %s falhou (erro inesperado): %s", job_id, e)
            self.state.mark_failed(job, str(e))
            raise AudioTranscriptionException(f"Erro no processamento do job: {str(e)}") from e

    def _get_engine_for_job(
        self,
        job: Job,
        model_size: str
    ) -> WhisperEngine:
        """Obtém ou cria engine para o job."""
        # Por enquanto, sempre usa faster-whisper (mais eficiente)
        # Futuramente pode selecionar baseado em job.engine
        return self.model_manager.get_or_create_engine(model_size)

    async def _validate_and_resolve_file(self, job: Job) -> Optional[Path]:
        """
        Valida e resolve o caminho do arquivo de entrada.
        
        Tenta múltiplos caminhos possíveis para encontrar o arquivo.
        """
        if not job.input_file:
            return None
        
        possible_paths = [
            Path(job.input_file),
            self.upload_dir / Path(job.input_file).name,
        ]
        
        # Adiciona caminhos baseados no job_id
        if job.filename:
            ext = Path(job.filename).suffix
            possible_paths.extend([
                self.upload_dir / f"{job.id}{ext}",
            ])
        
        for path in possible_paths:
            if path.exists() and path.is_file():
                if path.stat().st_size > 0:
                    job.input_file = str(path.absolute())
                    return path
                else:
                    logger.warning(f"Arquivo vazio: {path}")
        
        logger.error(f"Arquivo não encontrado em nenhum caminho: {possible_paths}")
        return None

    async def _save_uploaded_file(
        self,
        job_id: str,
        filename: str,
        content: bytes
    ) -> Path:
        """Salva arquivo de upload via storage manager (com retry)."""
        ext = Path(filename).suffix
        target_name = f"{job_id}{ext}"

        # Salva com retry — apenas para erros transitórios de I/O.
        last_error = None
        for attempt in range(3):
            try:
                saved_path = self.storage_manager.save_file(content, target_name)  # type: ignore[attr-defined]

                if saved_path.exists() and saved_path.stat().st_size > 0:
                    logger.info("Arquivo salvo: %s (%d bytes)", saved_path, len(content))
                    return saved_path

            except (OSError, IOError) as e:
                last_error = e
                logger.warning("Tentativa %d de salvar arquivo falhou: %s", attempt + 1, e)
                await asyncio.sleep(0.5 * (attempt + 1))

        raise AudioTranscriptionException(f"Falha ao salvar arquivo após 3 tentativas") from last_error

    async def _save_transcription(
        self,
        job: Job,
        text: str,
        segments: List[Dict[str, Any]]
    ) -> Path:
        """Salva arquivo de transcrição em formato SRT via storage manager."""
        output_filename = f"{job.id}_transcription.srt"

        # Converte para SRT
        srt_content = CaptionFormatter.to_srt(segments)

        saved_path = self.storage_manager.save_file(  # type: ignore[attr-defined]
            srt_content.encode("utf-8"), output_filename
        )

        return Path(saved_path) if not isinstance(saved_path, Path) else saved_path

    def _convert_segments(self, segments: List[Dict[str, Any]]) -> List[TranscriptionSegment]:
        """Converte segmentos para o formato do domínio."""
        result = []
        
        for seg in segments:
            # Processa word-level timestamps
            words = None
            if "words" in seg and seg["words"]:
                words = [
                    TranscriptionWord(
                        word=w["word"],
                        start=w["start"],
                        end=w["end"],
                        probability=w.get("probability", 1.0)
                    )
                    for w in seg["words"]
                ]
            
            result.append(TranscriptionSegment(
                text=seg["text"].strip(),
                start=seg["start"],
                end=seg["end"],
                duration=seg["end"] - seg["start"],
                words=words
            ))
        
        return result

    
    async def get_job_status(self, job_id: str) -> Optional[Job]:
        """Obtém status de um job."""
        JobIdValidator.validate(job_id)
        
        if self.job_store:
            return self.job_store.get_job(job_id)
        return None

    async def list_jobs(self, limit: int = 20) -> List[Job]:
        """Lista jobs recentes."""
        if self.job_store:
            return self.job_store.list_jobs(limit)
        return []

    async def delete_job(self, job_id: str) -> bool:
        """Remove um job e seus arquivos via storage manager."""
        JobIdValidator.validate(job_id)

        job = await self.get_job_status(job_id)
        if not job:
            return False

        # Remove arquivos de entrada/saída via abstração de armazenamento.
        for file_path in (job.input_file, job.output_file):
            if file_path:
                try:
                    self.storage_manager.delete_file(Path(file_path))  # type: ignore[attr-defined]
                except Exception as e:
                    logger.warning("Erro ao remover arquivo (%s): %s", "input" if file_path == job.input_file else "output", e)
        
        # Remove do store
        if self.job_store:
            self.job_store.delete_job(job_id)
        
        return True

class TranscriptionOrchestrator:
    """
    Orquestrador para fluxos complexos de transcrição.
    
    Responsabilidades:
    - Coordenação de múltiplos jobs
    - Batch processing
    - Retry automático
    - Cleanup de recursos
    """

    def __init__(self, service: TranscriptionService):
        self.service = service

    async def process_batch(
        self,
        jobs: List[Job],
        max_concurrent: int = 1
    ) -> List[Job]:
        """
        Processa um batch de jobs.
        
        Args:
            jobs: Lista de jobs a processar
            max_concurrent: Máximo de jobs simultâneos
            
        Returns:
            Lista de jobs processados
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(job: Job) -> Job:
            async with semaphore:
                try:
                    return await self.service.process_job(job)
                except Exception as e:
                    logger.error(f"Job {job.id} falhou no batch: {e}")
                    self.state.mark_failed(job, str(e))
                    return job
        
        tasks = [process_with_semaphore(job) for job in jobs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filtra exceções
        processed = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Exceção em job do batch: {result}")
            else:
                processed.append(result)
        
        return processed

    from ..core.constants import DEFAULT_MAX_RETRIES

    async def retry_failed_jobs(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES
    ) -> List[Job]:
        """
        Reprocessa jobs que falharam.
        
        Args:
            max_retries: Máximo de tentativas por job
            
        Returns:
            Lista de jobs reprocessados
        """
        failed_jobs = await self.service.list_jobs()
        failed_jobs = [j for j in failed_jobs if j.status == JobStatus.FAILED]
        
        to_retry = [j for j in failed_jobs if j.retry_count < max_retries]
        
        for job in to_retry:
            job.retry_count += 1
            job.status = JobStatus.QUEUED
            job.error_message = None
            if self.service.job_store:
                self.service.job_store.update_job(job)
        
        logger.info(f"Reprocessando {len(to_retry)} jobs falhos")
        return await self.process_batch(to_retry)

__all__ = [
    "TranscriptionService",
    "TranscriptionOrchestrator",
]