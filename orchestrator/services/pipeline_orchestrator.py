"""
Pipeline Orchestrator - Orquestrador de pipeline refatorado.

Responsabilidade única: Orquestrar execução do pipeline.
Delega health checks, circuit breaking e downloads para classes especializadas.
"""
from typing import Any, Dict, Optional, Tuple

from common.log_utils import get_logger

from core.config import get_microservice_config, get_settings
from domain.interfaces import MicroserviceClientInterface
from domain.models import PipelineJob, PipelineStatus, StageStatus
from infrastructure.redis_store import RedisStore
from services.health_checker import HealthChecker

logger = get_logger(__name__)


def _bool_to_str(v: bool) -> str:
    """Converte bool para string 'true'/'false'."""
    return "true" if v else "false"


class PipelineOrchestrator:
    """
    Orquestrador de pipeline refatorado com injeção de dependência.

    Pipeline:
    1. Download vídeo (video-downloader)
    2. Normalização áudio (audio-normalization)
    3. Transcrição (audio-transcriber)

    Args:
        video_client: Cliente do serviço video-downloader
        audio_client: Cliente do serviço audio-normalization
        transcription_client: Cliente do serviço audio-transcriber
        health_checker: Verificador de saúde dos serviços
        redis_store: Store Redis para persistência
    """

    def __init__(
        self,
        video_client: MicroserviceClientInterface,
        audio_client: MicroserviceClientInterface,
        transcription_client: MicroserviceClientInterface,
        health_checker: HealthChecker,
        redis_store: Optional[RedisStore] = None,
    ):
        self._video_client = video_client
        self._audio_client = audio_client
        self._transcription_client = transcription_client
        self._health_checker = health_checker
        self._redis = redis_store

        settings = get_settings()
        self.poll_interval_initial = settings.poll_interval_initial
        self.poll_interval_max = settings.poll_interval_max
        self.max_attempts = settings.max_poll_attempts

    async def execute_pipeline(self, job: PipelineJob) -> PipelineJob:
        """
        Executa pipeline completo de processamento.

        Args:
            job: Job do pipeline a ser processado

        Returns:
            PipelineJob: Job atualizado com status final

        Example:
            >>> job = PipelineJob.create_new(url="https://youtube.com/...")
            >>> result = await orchestrator.execute_pipeline(job)
            >>> print(result.status)
            'completed'
        """
        try:
            logger.info(f"Starting pipeline for job {job.id}")

            if not job.started_at:
                job.started_at = now_brazil()

            # 1) DOWNLOAD
            job.status = PipelineStatus.DOWNLOADING
            await self._save_job(job)
            logger.info(f"[PIPELINE:{job.id}] Starting DOWNLOAD stage")

            dl = await self._execute_download(job)
            if not dl:
                logger.error(f"[PIPELINE:{job.id}] DOWNLOAD stage failed")
                job.mark_as_failed("Download failed")
                await self._save_job(job)
                return job

            audio_bytes, audio_name = dl
            logger.info(
                f"[PIPELINE:{job.id}] DOWNLOAD completed: {audio_name} "
                f"({len(audio_bytes) / (1024 * 1024):.1f}MB)"
            )

            # 2) NORMALIZAÇÃO
            job.status = PipelineStatus.NORMALIZING
            await self._save_job(job)
            logger.info(f"[PIPELINE:{job.id}] Starting NORMALIZATION stage")

            norm = await self._execute_normalization(job, audio_bytes, audio_name)
            if not norm:
                logger.error(f"[PIPELINE:{job.id}] NORMALIZATION stage failed")
                job.mark_as_failed("Audio normalization failed")
                await self._save_job(job)
                return job

            norm_bytes, norm_name = norm
            job.audio_file = norm_name
            logger.info(
                f"[PIPELINE:{job.id}] NORMALIZATION completed: {norm_name} "
                f"({len(norm_bytes) / (1024 * 1024):.1f}MB)"
            )

            # 3) TRANSCRIÇÃO
            job.status = PipelineStatus.TRANSCRIBING
            await self._save_job(job)
            logger.info(f"[PIPELINE:{job.id}] Starting TRANSCRIPTION stage")

            tr = await self._execute_transcription(job, norm_bytes, norm_name)
            if not tr:
                logger.error(f"[PIPELINE:{job.id}] TRANSCRIPTION stage failed")
                job.mark_as_failed("Transcription failed")
                await self._save_job(job)
                return job

            job.transcription_text = tr.get("text")
            job.transcription_segments = tr.get("segments")
            job.transcription_file = tr.get("file_name")
            logger.info(
                f"[PIPELINE:{job.id}] TRANSCRIPTION completed: "
                f"{len(job.transcription_text or '')} chars"
            )

            # 4) FECHAMENTO
            job.mark_as_completed()
            await self._save_job(job)
            logger.info(f"Pipeline completed for job {job.id}")
            return job

        except Exception as e:
            logger.error(f"Pipeline failed for job {job.id}: {e}")
            job.mark_as_failed(str(e))
            await self._save_job(job)
            return job

    async def _save_job(self, job: PipelineJob) -> None:
        """Salva job no Redis se disponível."""
        if self._redis:
            self._redis.save_job(job)

    async def check_services_health(self) -> Dict[str, str]:
        """
        Verifica saúde de todos os serviços.

        Returns:
            Dict com status de cada serviço
        """
        return await self._health_checker.check_all()

    async def _execute_download(
        self, job: PipelineJob
    ) -> Optional[Tuple[bytes, str]]:
        """
        Executa estágio de download.

        Args:
            job: Job em processamento

        Returns:
            Tuple com bytes e nome do arquivo, ou None se falhar
        """
        stage = job.download_stage
        stage.start()

        try:
            payload = {"url": job.youtube_url, "quality": "audio"}
            resp = await self._video_client.submit_job(payload)
            stage.job_id = resp.get("job_id") or resp.get("id")

            if not stage.job_id:
                raise RuntimeError(f"video-downloader não retornou job_id: {resp}")

            logger.info(f"Video job submitted: {stage.job_id}")
            await asyncio.sleep(1)  # Aguarda processamento inicial

            status = await self._wait_until_done(
                self._video_client, stage.job_id, stage, "video-downloader"
            )
            if not status:
                stage.fail("Download job failed/timeout")
                return None

            content, filename = await self._video_client.download_file(stage.job_id)
            stage.complete(filename)
            job.update_progress()
            await self._save_job(job)

            return content, filename

        except Exception as e:
            logger.error(f"Download stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _execute_normalization(
        self, job: PipelineJob, audio_bytes: bytes, audio_name: str
    ) -> Optional[Tuple[bytes, str]]:
        """
        Executa estágio de normalização.

        Args:
            job: Job em processamento
            audio_bytes: Bytes do arquivo de áudio
            audio_name: Nome do arquivo

        Returns:
            Tuple com bytes e nome do arquivo normalizado, ou None
        """
        stage = job.normalization_stage
        stage.start()

        try:
            cfg = get_microservice_config("audio-normalization")
            defaults = (cfg.get("default_params") or {}).copy()

            files = {
                "file": (audio_name, audio_bytes, "application/octet-stream")
            }
            data = {
                "remove_noise": _bool_to_str(
                    job.remove_noise
                    if job.remove_noise is not None
                    else defaults.get("remove_noise", False)
                ),
                "convert_to_mono": _bool_to_str(
                    job.convert_to_mono
                    if job.convert_to_mono is not None
                    else defaults.get("convert_to_mono", False)
                ),
                "apply_highpass_filter": _bool_to_str(
                    job.apply_highpass_filter
                    if job.apply_highpass_filter is not None
                    else defaults.get("apply_highpass_filter", False)
                ),
                "set_sample_rate_16k": _bool_to_str(
                    job.set_sample_rate_16k
                    if job.set_sample_rate_16k is not None
                    else defaults.get("set_sample_rate_16k", False)
                ),
                "isolate_vocals": _bool_to_str(
                    job.isolate_vocals
                    if job.isolate_vocals is not None
                    else defaults.get("isolate_vocals", False)
                ),
            }

            resp = await self._audio_client.submit_multipart(files=files, data=data)
            stage.job_id = resp.get("job_id") or resp.get("id")

            if not stage.job_id:
                raise RuntimeError(f"audio-normalization não retornou job_id: {resp}")

            logger.info(f"Audio normalization job submitted: {stage.job_id}")

            status = await self._wait_until_done(
                self._audio_client, stage.job_id, stage, "audio-normalization"
            )
            if not status:
                stage.fail("Normalization job failed/timeout")
                return None

            out_bytes, out_name = await self._audio_client.download_file(stage.job_id)
            stage.complete(out_name)
            job.update_progress()
            await self._save_job(job)

            return out_bytes, out_name

        except Exception as e:
            logger.error(f"Normalization stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _execute_transcription(
        self, job: PipelineJob, audio_bytes: bytes, audio_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Executa estágio de transcrição.

        Args:
            job: Job em processamento
            audio_bytes: Bytes do arquivo de áudio
            audio_name: Nome do arquivo

        Returns:
            Dict com text, segments e file_name, ou None
        """
        stage = job.transcription_stage
        stage.start()

        try:
            cfg = get_microservice_config("audio-transcriber")
            defaults = (cfg.get("default_params") or {}).copy()

            lang_in = job.language or defaults.get("language_in", "auto")
            lang_out = job.language_out

            files = {"file": (audio_name, audio_bytes, "application/octet-stream")}
            data: Dict[str, str] = {"language_in": lang_in}
            if lang_out:
                data["language_out"] = lang_out

            resp = await self._transcription_client.submit_multipart(files=files, data=data)
            stage.job_id = resp.get("job_id") or resp.get("id")

            if not stage.job_id:
                raise RuntimeError(f"audio-transcriber não retornou job_id: {resp}")

            logger.info(f"Transcription job submitted: {stage.job_id}")

            status = await self._wait_until_done(
                self._transcription_client, stage.job_id, stage, "audio-transcriber"
            )
            if not status:
                stage.fail("Transcription job failed/timeout")
                return None

            # Busca texto da transcrição
            text = None
            segments = None

            try:
                text_url = f"{self._transcription_client.base_url}/jobs/{stage.job_id}/text"
                import httpx
                from core.ssl_config import get_ssl_context
                ssl_verify = get_ssl_context()
                async with httpx.AsyncClient(timeout=self._transcription_client.timeout, verify=ssl_verify) as client:
                    tr = await client.get(text_url)
                    if tr.status_code == 200:
                        text_data = tr.json()
                        text = text_data.get("text", "")
                        logger.info(f"Transcription text retrieved: {len(text) if text else 0} chars")
            except Exception as e:
                logger.warning(f"Failed to get transcription text: {e}")

            # Busca segments
            try:
                seg_url = f"{self._transcription_client.base_url}/jobs/{stage.job_id}/transcription"
                async with httpx.AsyncClient(timeout=self._transcription_client.timeout, verify=ssl_verify) as client:
                    tr = await client.get(seg_url)
                    if tr.status_code == 200:
                        seg_data = tr.json()
                        segments = seg_data.get("segments", [])
                        if not text:
                            text = seg_data.get("full_text", "")
                        logger.info(f"Transcription segments retrieved: {len(segments)} segments")
            except Exception as e:
                logger.warning(f"Failed to get transcription segments: {e}")

            # Download do arquivo
            out_bytes, out_name = await self._transcription_client.download_file(stage.job_id)

            result = {
                "text": text,
                "segments": segments,
                "file_name": out_name,
                "file_bytes_len": len(out_bytes),
            }

            stage.complete(out_name)
            job.update_progress()
            await self._save_job(job)

            return result

        except Exception as e:
            logger.error(f"Transcription stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _wait_until_done(
        self,
        client: MicroserviceClientInterface,
        job_id: str,
        stage: Any,
        service_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Aguarda job completar via polling.

        Args:
            client: Cliente do serviço
            job_id: ID do job
            stage: Estágio atual
            service_name: Nome do serviço

        Returns:
            Status final ou None se falhar
        """
        import asyncio

        settings = get_settings()
        attempts = 0
        consecutive_errors = 0
        max_consecutive_errors = 5

        # Timeout baseado no serviço
        if service_name == "audio-normalization":
            max_wait_time = settings.audio_normalization_job_timeout
        elif service_name == "audio-transcriber":
            max_wait_time = settings.audio_transcriber_job_timeout
        else:
            max_wait_time = settings.video_downloader_job_timeout

        start_time = asyncio.get_event_loop().time()

        while attempts < self.max_attempts:
            elapsed_time = asyncio.get_event_loop().time() - start_time
            if elapsed_time > max_wait_time:
                logger.error(f"Job {job_id} timeout after {elapsed_time:.0f}s")
                stage.fail(f"Timeout after {elapsed_time:.0f}s")
                return None

            try:
                status = await client.get_job_status(job_id)
                consecutive_errors = 0

                # Atualiza progresso
                if status and "progress" in status:
                    try:
                        p = float(status["progress"])
                        stage.progress = p * 100.0 if p <= 1.0 else p
                    except Exception:
                        pass

                state = (status.get("status") or status.get("state") or "").lower()
                if state in {"completed", "success", "done", "finished"}:
                    logger.info(f"Job {job_id} completed after {elapsed_time:.0f}s")
                    return status
                if state in {"failed", "error", "cancelled", "canceled", "aborted"}:
                    error_msg = status.get("error") or status.get(
                        "error_message", f"Job failed with state: {state}"
                    )
                    logger.error(f"Job {job_id} failed: {error_msg}")
                    stage.fail(error_msg)
                    return None

            except Exception as e:
                consecutive_errors += 1
                logger.warning(f"Error polling job {job_id}: {e}")

            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Too many errors polling job {job_id}")
                stage.fail("Too many polling errors")
                return None

            # Polling adaptativo
            if attempts < 10:
                poll_delay = self.poll_interval_initial
            elif attempts < 50:
                poll_delay = min(self.poll_interval_initial * 2, self.poll_interval_max)
            else:
                poll_delay = self.poll_interval_max

            await asyncio.sleep(poll_delay)
            attempts += 1

        logger.error(f"Job {job_id} timeout after {attempts} attempts")
        stage.fail(f"Timeout after {attempts} polling attempts")
        return None


# Import no final para evitar circular imports
import asyncio
from common.datetime_utils import now_brazil
