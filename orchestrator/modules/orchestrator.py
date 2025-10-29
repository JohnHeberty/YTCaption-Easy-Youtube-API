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
import os

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
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.config = get_microservice_config(service_name)
        self.base_url = self.config["url"]
        self.timeout = self.config["timeout"]
        self.endpoints = self.config["endpoints"]

    async def _request_with_retries(self, method: str, url: str, *, max_attempts=3, **kwargs) -> httpx.Response:
        delay = 1.0
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except httpx.HTTPError as e:
                last_exc = e
                logger.warning(f"{self.service_name} {method} {url} failed (attempt {attempt}/{max_attempts}): {e}")
                if attempt == max_attempts:
                    break
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)
        raise last_exc

    async def submit_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = self.endpoints.get("submit")
        url = f"{self.base_url}{endpoint}"
        # Se vier _files, manda multipart. Caso contrário, JSON.
        files = payload.pop("_files", None)
        if files:
            resp = await self._request_with_retries("POST", url, files=files, data=payload)
        else:
            resp = await self._request_with_retries("POST", url, json=payload)
        return resp.json()

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}{self.endpoints['status']}".format(job_id=job_id)
        resp = await self._request_with_retries("GET", url)
        return resp.json()

    async def download_artifact(self, job_id: str, dest_path: str) -> str:
        url = f"{self.base_url}{self.endpoints.get('artifact', f'/jobs/{job_id}/download')}".format(job_id=job_id)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in r.aiter_bytes():
                        f.write(chunk)
        return dest_path

    async def check_health(self) -> bool:
        url = f"{self.base_url}{self.endpoints.get('health', '/health')}"
        try:
            resp = await self._request_with_retries("GET", url)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {self.service_name}: {e}")
            return False

    async def download_artifact(self, job_id: str, dest_path: str) -> str:
        """Baixa o arquivo pronto em /jobs/{job_id}/download"""
        endpoint = self.endpoints.get("artifact", "/jobs/{job_id}/download")
        url = f"{self.base_url}{endpoint}".format(job_id=job_id)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in r.aiter_bytes():
                        f.write(chunk)
        return dest_path

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
            ("audio-transcriber", self.transcription_client),
        ]:
            is_healthy = await client.check_health()
            results[name] = "healthy" if is_healthy else "unhealthy"
        return results

    async def execute_pipeline(self, job: PipelineJob) -> PipelineJob:
        """Executa pipeline completo com resiliência"""
        try:
            logger.info(f"Starting pipeline for job {job.id}")

            # (Opcional) Pré-checagem de saúde
            health = await self.check_services_health()
            for svc, st in health.items():
                if st != "healthy":
                    logger.warning(f"Service {svc} is {st}. Proceeding anyway.")

            # 1) Download do vídeo
            job.status = PipelineStatus.DOWNLOADING
            video_file = await self._execute_download(job)
            if not video_file:
                job.mark_as_failed("Download failed")
                return job

            # 2) Normalização de áudio
            job.status = PipelineStatus.NORMALIZING
            audio_file = await self._execute_normalization(job, video_file)
            if not audio_file:
                job.mark_as_failed("Audio normalization failed")
                return job
            job.audio_file = audio_file

            # 3) Transcrição
            job.status = PipelineStatus.TRANSCRIBING
            transcription_result = await self._execute_transcription(job, audio_file)
            if not transcription_result:
                job.mark_as_failed("Transcription failed")
                return job

            job.transcription_text = transcription_result.get("text")
            job.transcription_file = transcription_result.get("file")

            # Final
            job.mark_as_completed()
            logger.info(f"Pipeline completed for job {job.id}")
            return job

        except Exception as e:
            logger.error(f"Pipeline failed for job {job.id}: {str(e)}")
            job.mark_as_failed(str(e))
            return job

    async def _execute_download(self, job: PipelineJob) -> Optional[str]:
        """Executa download do vídeo: submit -> poll -> baixa artefato"""
        stage = job.download_stage
        stage.start()

        try:
            payload = {"url": job.youtube_url}
            response = await self.video_client.submit_job(payload)
            stage.job_id = response.get("job_id") or response.get("id")
            if not stage.job_id:
                raise RuntimeError(f"Video-downloader did not return a job_id: {response}")

            logger.info(f"Video download job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.video_client, stage.job_id, stage)
            if not status:
                stage.fail("Download timeout or failed")
                return None

            # Baixa o arquivo pronto em /jobs/{id}/download
            dest_path = f"./artifacts/videos/{job.id}.mp4"
            import os
            os.makedirs("./artifacts/videos", exist_ok=True)

            await self.video_client.download_artifact(stage.job_id, dest_path)

            stage.complete(dest_path)
            job.update_progress()
            return dest_path

        except Exception as e:
            logger.error(f"Download stage failed: {str(e)}")
            stage.fail(str(e))
            return None

    async def _execute_normalization(self, job: PipelineJob, video_file: str) -> Optional[str]:
        """Executa normalização de áudio: submit (multipart) -> poll -> baixa artefato"""
        stage = job.normalization_stage
        stage.start()

        try:
            # Envia arquivo como multipart (_files) + flags no corpo (data)
            svc_cfg = get_microservice_config("audio-normalization")
            defaults = (svc_cfg.get("default_params") or {}).copy()

            import os
            os.makedirs("./artifacts/audio", exist_ok=True)

            with open(video_file, "rb") as f:
                payload = {
                    **defaults,
                    "remove_noise": job.remove_noise,
                    "convert_to_mono": job.convert_to_mono,
                    "set_sample_rate_16k": job.sample_rate_16k,
                    "_files": {"file": ("input.mp4", f, "application/octet-stream")},
                }
                response = await self.audio_client.submit_job(payload)

            stage.job_id = response.get("job_id") or response.get("id")
            if not stage.job_id:
                raise RuntimeError(f"Audio-normalization did not return a job_id: {response}")

            logger.info(f"Audio normalization job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.audio_client, stage.job_id, stage)
            if not status:
                stage.fail("Normalization timeout or failed")
                return None

            dest_path = f"./artifacts/audio/{job.id}.wav"
            await self.audio_client.download_artifact(stage.job_id, dest_path)

            stage.complete(dest_path)
            job.update_progress()
            return dest_path

        except Exception as e:
            logger.error(f"Normalization stage failed: {str(e)}")
            stage.fail(str(e))
            return None

    async def _execute_transcription(self, job: PipelineJob, audio_file: str) -> Optional[Dict[str, Any]]:
        """Executa transcrição: submit (multipart) -> poll -> baixa artefato"""
        stage = job.transcription_stage
        stage.start()

        try:
            svc_cfg = get_microservice_config("audio-transcriber")
            defaults = (svc_cfg.get("default_params") or {}).copy()

            import os
            os.makedirs("./artifacts/transcriptions", exist_ok=True)

            with open(audio_file, "rb") as f:
                payload: Dict[str, Any] = {
                    **defaults,
                    "_files": {"file": ("audio.wav", f, "application/octet-stream")},
                }
                if job.language and job.language != "auto":
                    payload["language"] = job.language

                response = await self.transcription_client.submit_job(payload)

            stage.job_id = response.get("job_id") or response.get("id")
            if not stage.job_id:
                raise RuntimeError(f"Audio-transcriber did not return a job_id: {response}")

            logger.info(f"Transcription job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.transcription_client, stage.job_id, stage)
            if not status:
                stage.fail("Transcription timeout or failed")
                return None

            # Baixa legenda/arquivo final (ajuste extensão conforme o microserviço)
            dest_path = f"./artifacts/transcriptions/{job.id}.srt"
            await self.transcription_client.download_artifact(stage.job_id, dest_path)

            stage.complete(dest_path)
            job.update_progress()
            return {"file": dest_path}

        except Exception as e:
            logger.error(f"Transcription stage failed: {str(e)}")
            stage.fail(str(e))
            return None

    async def _wait_until_done(
        self,
        client: "MicroserviceClient",
        job_id: str,
        stage: PipelineStage,
    ) -> Optional[Dict[str, Any]]:
        """Espera até o job terminar, consultando GET /jobs/{id}"""
        attempts = 0
        while attempts < self.max_attempts:
            try:
                status = await client.get_job_status(job_id)

                # progresso (0–1 ou 0–100)
                if "progress" in status:
                    try:
                        p = float(status["progress"])
                        stage.progress = p * 100.0 if p <= 1.0 else p
                    except Exception:
                        pass

                state = (status.get("status") or status.get("state") or "").lower()
                if state in {"completed", "success", "done", "finished"}:
                    return status
                if state in {"failed", "error", "cancelled", "canceled", "aborted"}:
                    stage.fail(status.get("error") or status.get("error_message", "Unknown error"))
                    return None

            except Exception as e:
                logger.error(f"Error polling job {job_id}: {e}")

            await asyncio.sleep(self.poll_interval)
            attempts += 1

        logger.error(f"Job {job_id} timeout after {attempts} attempts")
        return None

