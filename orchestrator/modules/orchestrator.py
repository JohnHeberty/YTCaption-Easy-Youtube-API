#orchestrator.py
"""
Lógica de orquestração do pipeline completo
"""
import asyncio
import httpx
from typing import Optional, Dict, Any
from datetime import datetime
import logging
import random

from .models import (
    PipelineJob,
    PipelineStatus,
    StageStatus,
    PipelineStage
)
from .config import get_orchestrator_settings, get_microservice_config

logger = logging.getLogger(__name__)


def _normalize_progress(value: Any) -> float:
    """
    Normaliza progresso vindo dos serviços:
    - aceita 0-1 (fração) ou 0-100 (percentual)
    - ignora valores inválidos
    """
    try:
        p = float(value)
    except Exception:
        return 0.0
    if p <= 1.0:
        return max(0.0, min(100.0, p * 100.0))
    return max(0.0, min(100.0, p))


def _is_done(status_value: str) -> bool:
    v = (status_value or "").lower()
    return v in {"completed", "success", "done", "finished", "ok"}


def _is_failed(status_value: str) -> bool:
    v = (status_value or "").lower()
    return v in {"failed", "error", "aborted", "cancelled", "canceled"}


class MicroserviceClient:
    """Cliente para comunicação com microserviços com retries e backoff"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.config = get_microservice_config(service_name)
        self.base_url = self.config["url"].rstrip("/")
        self.timeout_seconds = self.config["timeout"]
        self.endpoints = self.config["endpoints"]
        settings = get_orchestrator_settings()
        self.max_retries = max(0, int(settings.get("http_max_retries", 3)))
        self.backoff_base = float(settings.get("retry_backoff_base_seconds", 1.5))

    def _resolve_submit_endpoint(self) -> str:
        # Prioridade para 'submit', depois os aliases conhecidos
        for k in ("submit", "transcribe", "process", "download", "jobs"):
            if k in self.endpoints:
                return self.endpoints[k]
        raise KeyError(f"No submit-like endpoint defined for service '{self.service_name}'")

    async def _request_with_retries(self, method: str, url: str, **kwargs) -> httpx.Response:
        # Timeout do httpx refinado (connect/read/write) com total = timeout_seconds
        timeout = httpx.Timeout(self.timeout_seconds, connect=10.0)
        kwargs.setdefault("timeout", timeout)

        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt <= self.max_retries:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.request(method, url, **kwargs)
                # Considera 5xx como retryable
                if 500 <= resp.status_code < 600:
                    raise httpx.HTTPStatusError("Server error", request=resp.request, response=resp)
                return resp
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_exc = e
                if attempt == self.max_retries:
                    break
                # Backoff exponencial com jitter
                backoff = (self.backoff_base ** attempt) + random.uniform(0, 0.4)
                logger.warning(
                    f"[{self.service_name}] {method} {url} failed (attempt {attempt+1}/{self.max_retries+1}): {e}. "
                    f"Retrying in {backoff:.2f}s"
                )
                await asyncio.sleep(backoff)
                attempt += 1

        # Se chegou aqui, falhou
        assert last_exc is not None
        raise last_exc

    async def submit_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submete job ao microserviço (com retries)"""
        endpoint = self._resolve_submit_endpoint()
        url = f"{self.base_url}{endpoint}"
        logger.info(f"Submitting job to {self.service_name}: {url}")

        resp = await self._request_with_retries("POST", url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Consulta status do job (com retries)"""
        endpoint_tmpl = self.endpoints.get("status", "/jobs/{job_id}")
        url = f"{self.base_url}{endpoint_tmpl}".format(job_id=job_id)

        resp = await self._request_with_retries("GET", url)
        resp.raise_for_status()
        return resp.json()

    async def check_health(self) -> bool:
        """Verifica saúde do microserviço (com retries)"""
        endpoint = self.endpoints.get("health", "/health")
        url = f"{self.base_url}{endpoint}"
        try:
            resp = await self._request_with_retries("GET", url)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {self.service_name}: {str(e)}")
            return False


class PipelineOrchestrator:
    """Orquestrador do pipeline completo"""

    def __init__(self):
        self.settings = get_orchestrator_settings()
        self.video_client = MicroserviceClient("video-downloader")
        self.audio_client = MicroserviceClient("audio-normalization")
        self.transcription_client = MicroserviceClient("audio-transcriber")

        self.poll_interval = self.settings["poll_interval"]
        self.max_attempts = self.settings["max_poll_attempts"]

    async def check_services_health(self) -> Dict[str, str]:
        """Verifica saúde de todos os serviços"""
        results = {}

        for name, client in [
            ("video-downloader", self.video_client),
            ("audio-normalization", self.audio_client),
            ("audio-transcriber", self.transcription_client)
        ]:
            is_healthy = await client.check_health()
            results[name] = "healthy" if is_healthy else "unhealthy"

        return results

    async def execute_pipeline(self, job: PipelineJob) -> PipelineJob:
        """Executa pipeline completo com resiliência"""
        try:
            logger.info(f"Starting pipeline for job {job.id}")

            # (Opcional) Pré-checagem de saúde — segue mesmo se algum estiver "unhealthy", mas loga
            health = await self.check_services_health()
            for svc, st in health.items():
                if st != "healthy":
                    logger.warning(f"Service {svc} is {st}. Proceeding anyway due to resilience focus.")

            # Estágio 1: Download do vídeo
            job.status = PipelineStatus.DOWNLOADING
            video_file = await self._execute_download(job)
            if not video_file:
                job.mark_as_failed("Download failed")
                return job

            # Estágio 2: Normalização de áudio
            job.status = PipelineStatus.NORMALIZING
            audio_file = await self._execute_normalization(job, video_file)
            if not audio_file:
                job.mark_as_failed("Audio normalization failed")
                return job

            job.audio_file = audio_file

            # Estágio 3: Transcrição
            job.status = PipelineStatus.TRANSCRIBING
            transcription = await self._execute_transcription(job, audio_file)
            if not transcription:
                job.mark_as_failed("Transcription failed")
                return job

            job.transcription_text = transcription.get("text") if isinstance(transcription, dict) else None
            job.transcription_file = (
                transcription.get("file")
                if isinstance(transcription, dict)
                else None
            )

            # Pipeline completo
            job.mark_as_completed()
            logger.info(f"Pipeline completed for job {job.id}")

            return job

        except Exception as e:
            logger.error(f"Pipeline failed for job {job.id}: {str(e)}")
            job.mark_as_failed(str(e))
            return job

    async def _execute_download(self, job: PipelineJob) -> Optional[str]:
        """Executa download do vídeo"""
        stage = job.download_stage
        stage.start()

        try:
            # Submete job ao video-downloader
            payload = {"url": job.youtube_url}
            response = await self.video_client.submit_job(payload)

            stage.job_id = response.get("job_id") or response.get("id")
            if not stage.job_id:
                raise RuntimeError(f"Video-downloader did not return a job_id: {response}")

            logger.info(f"Video download job submitted: {stage.job_id}")

            # Polling do status
            video_file = await self._poll_job_status(
                client=self.video_client,
                job_id=stage.job_id,
                stage=stage,
                output_key="output_file",
                job=job,
            )

            if video_file:
                stage.complete(video_file if isinstance(video_file, str) else None)
                job.update_progress()
                return video_file if isinstance(video_file, str) else video_file.get("output_file")
            else:
                stage.fail("Download timeout or failed")
                return None

        except Exception as e:
            logger.error(f"Download stage failed: {str(e)}")
            stage.fail(str(e))
            return None

    async def _execute_normalization(self, job: PipelineJob, video_file: str) -> Optional[str]:
        """Executa normalização de áudio"""
        stage = job.normalization_stage
        stage.start()

        try:
            # Merge com default_params do serviço e mapeamento de chaves
            svc_cfg = get_microservice_config("audio-normalization")
            defaults = (svc_cfg.get("default_params") or {}).copy()

            payload = {
                **defaults,
                "input_file": video_file,
                "remove_noise": job.remove_noise,
                "convert_to_mono": job.convert_to_mono,
                # serviço espera 'set_sample_rate_16k'
                "set_sample_rate_16k": job.sample_rate_16k,
            }

            response = await self.audio_client.submit_job(payload)

            stage.job_id = response.get("job_id") or response.get("id")
            if not stage.job_id:
                raise RuntimeError(f"Audio-normalization did not return a job_id: {response}")

            logger.info(f"Audio normalization job submitted: {stage.job_id}")

            # Polling do status
            audio_file = await self._poll_job_status(
                client=self.audio_client,
                job_id=stage.job_id,
                stage=stage,
                output_key="output_file",
                job=job,
            )

            if audio_file:
                final_file = audio_file if isinstance(audio_file, str) else audio_file.get("output_file")
                stage.complete(final_file)
                job.update_progress()
                return final_file
            else:
                stage.fail("Normalization timeout or failed")
                return None

        except Exception as e:
            logger.error(f"Normalization stage failed: {str(e)}")
            stage.fail(str(e))
            return None

    async def _execute_transcription(self, job: PipelineJob, audio_file: str) -> Optional[Dict[str, Any]]:
        """Executa transcrição de áudio"""
        stage = job.transcription_stage
        stage.start()

        try:
            svc_cfg = get_microservice_config("audio-transcriber")
            defaults = (svc_cfg.get("default_params") or {}).copy()

            payload: Dict[str, Any] = {"audio_file": audio_file, **defaults}
            if job.language and job.language != "auto":
                payload["language"] = job.language  # sobrescreve se definido no job

            response = await self.transcription_client.submit_job(payload)

            stage.job_id = response.get("job_id") or response.get("id")
            if not stage.job_id:
                raise RuntimeError(f"Audio-transcriber did not return a job_id: {response}")

            logger.info(f"Transcription job submitted: {stage.job_id}")

            # Polling do status
            result = await self._poll_job_status(
                client=self.transcription_client,
                job_id=stage.job_id,
                stage=stage,
                output_key="transcription",
                job=job,
            )

            if result:
                # result pode ser string (arquivo), ou dict com 'text'/'file'
                output_file = None
                if isinstance(result, dict):
                    output_file = result.get("file") or result.get("output_file")
                elif isinstance(result, str):
                    output_file = result

                stage.complete(output_file)
                job.update_progress()
                return result
            else:
                stage.fail("Transcription timeout or failed")
                return None

        except Exception as e:
            logger.error(f"Transcription stage failed: {str(e)}")
            stage.fail(str(e))
            return None

    async def _poll_job_status(
        self,
        client: MicroserviceClient,
        job_id: str,
        stage: PipelineStage,
        output_key: str,
        job: Optional[PipelineJob] = None,
    ) -> Optional[Any]:
        """Faz polling do status do job até completar"""
        attempts = 0

        while attempts < self.max_attempts:
            try:
                status = await client.get_job_status(job_id)

                # aceita 'status' ou 'state'
                job_status = (status.get("status") or status.get("state") or "").lower()

                # Atualiza progresso, aceitando 0–1 ou 0–100
                if "progress" in status:
                    stage.progress = _normalize_progress(status["progress"])
                    if job:
                        job.update_progress()

                # Verifica fim
                if _is_done(job_status):
                    logger.info(f"Job {job_id} completed")
                    # retorno flexível: output direto ou payload completo
                    return status.get(output_key) or status

                if _is_failed(job_status):
                    error = status.get("error") or status.get("error_message", "Unknown error")
                    logger.error(f"Job {job_id} failed: {error}")
                    return None

                # Ainda processando
                await asyncio.sleep(self.poll_interval)
                attempts += 1

            except Exception as e:
                logger.error(f"Error polling job {job_id}: {str(e)}")
                await asyncio.sleep(self.poll_interval)
                attempts += 1

        logger.error(f"Job {job_id} timeout after {attempts} attempts")
        return None
