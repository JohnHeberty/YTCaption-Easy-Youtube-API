# orchestrator/modules/orchestrator.py
"""
Lógica de orquestração do pipeline completo (corrigida para fluxo /jobs)
"""
import asyncio
import httpx
from typing import Optional, Dict, Any
from pathlib import Path
import logging
import os
import math
from datetime import datetime

from .models import (
    PipelineJob,
    PipelineStatus,
    StageStatus,
    PipelineStage,
)
from .config import get_orchestrator_settings, get_microservice_config

logger = logging.getLogger(__name__)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


class MicroserviceClient:
    """Cliente para comunicação com microserviços no padrão:
       - POST   /jobs                      (cria)
       - GET    /jobs/{id}                 (status)
       - GET    /jobs/{id}/download        (artefato)  [fallback: /jobs/{id}/result]
       - GET    /health
    """

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.config = get_microservice_config(service_name)
        self.base_url: str = self.config["url"].rstrip("/")
        self.timeout: int = int(self.config.get("timeout", 300))
        self.endpoints: Dict[str, str] = self.config["endpoints"]

        # Normaliza/garante chaves padrão
        self.submit_ep = self.endpoints.get("submit") or self.endpoints.get("process") or self.endpoints.get("download") or "/jobs"
        self.status_ep = self.endpoints.get("status", "/jobs/{job_id}")
        self.download_ep = self.endpoints.get("download", "/jobs/{job_id}/download")
        self.result_ep = self.endpoints.get("result", "/jobs/{job_id}/result")
        self.health_ep = self.endpoints.get("health", "/health")

    def _url(self, ep: str, **fmt) -> str:
        return f"{self.base_url}{ep.format(**fmt)}"

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        # retries simples com backoff (1s, 2s, 4s)
        retries = kwargs.pop("_retries", 2)
        delay = 1.0
        last_exc = None
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.request(method, url, **kwargs)
                    resp.raise_for_status()
                    return resp
            except Exception as e:
                last_exc = e
                if attempt < retries:
                    await asyncio.sleep(delay)
                    delay = min(8.0, delay * 2.0)
                else:
                    break
        raise last_exc  # propaga

    async def submit_job(
        self,
        json_payload: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Submete job ao microserviço. Usa POST submit_ep (padrão: /jobs)."""
        url = self._url(self.submit_ep)
        logger.info(f"Submitting job to {self.service_name}: {url}")

        kwargs: Dict[str, Any] = {"headers": headers or {}}
        if files:
            kwargs["files"] = files
            if data:
                kwargs["data"] = data
        else:
            kwargs["json"] = json_payload or {}

        resp = await self._request("POST", url, **kwargs)
        return resp.json()

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Consulta status do job em GET /jobs/{id}"""
        url = self._url(self.status_ep, job_id=job_id)
        resp = await self._request("GET", url)
        return resp.json()

    async def download_artifact(self, job_id: str, dest_dir: Path, filename: Optional[str] = None) -> Path:
        """Baixa artefato final.
           Tenta /jobs/{id}/download; se 404, tenta /jobs/{id}/result.
        """
        _ensure_dir(dest_dir)
        # 1ª tentativa: download
        for ep in (self.download_ep, self.result_ep):
            url = self._url(ep, job_id=job_id)
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    async with client.stream("GET", url) as resp:
                        if resp.status_code == 404:
                            raise httpx.HTTPStatusError("Not Found", request=resp.request, response=resp)
                        resp.raise_for_status()

                        # tenta extrair nome de arquivo do header
                        suggested = None
                        cd = resp.headers.get("content-disposition", "")
                        if "filename=" in cd:
                            suggested = cd.split("filename=")[-1].strip('"; ')

                        final_name = filename or suggested or f"{self.service_name}-{job_id}"
                        # se não houver extensão, tenta inferir por content-type
                        if "." not in final_name:
                            ctype = (resp.headers.get("content-type") or "").lower()
                            if "json" in ctype:
                                final_name += ".json"
                            elif "srt" in ctype:
                                final_name += ".srt"
                            elif "vtt" in ctype:
                                final_name += ".vtt"
                            elif "wav" in ctype:
                                final_name += ".wav"
                            elif "mp3" in ctype:
                                final_name += ".mp3"
                            elif "mp4" in ctype:
                                final_name += ".mp4"
                            else:
                                final_name += ".bin"

                        out_path = dest_dir / final_name
                        with out_path.open("wb") as f:
                            async for chunk in resp.aiter_bytes():
                                f.write(chunk)
                        logger.info(f"Downloaded artifact from {self.service_name} to: {out_path}")
                        return out_path
            except httpx.HTTPStatusError as e:
                if e.response is not None and e.response.status_code == 404:
                    logger.debug(f"{self.service_name}: {ep} not found, trying fallback...")
                    continue
                raise
        raise RuntimeError(f"{self.service_name}: no artifact endpoint found for job {job_id}")

    async def check_health(self) -> bool:
        """Verifica saúde do microserviço"""
        url = self._url(self.health_ep)
        try:
            resp = await self._request("GET", url, _retries=0)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {self.service_name}: {e}")
            return False


class PipelineOrchestrator:
    """Orquestrador do pipeline completo baseado no padrão /jobs"""

    def __init__(self):
        self.settings = get_orchestrator_settings()
        self.video_client = MicroserviceClient("video-downloader")
        self.audio_client = MicroserviceClient("audio-normalization")
        self.transcription_client = MicroserviceClient("audio-transcriber")

        self.poll_interval = int(self.settings["poll_interval"])
        self.max_attempts = int(self.settings["max_poll_attempts"])

        # diretórios para artefatos
        base_artifacts = Path(os.getenv("ARTIFACTS_DIR", "/app/artifacts"))
        self.dir_downloads = base_artifacts / "downloads"
        self.dir_normalized = base_artifacts / "normalized"
        self.dir_transcripts = base_artifacts / "transcripts"
        for d in (self.dir_downloads, self.dir_normalized, self.dir_transcripts):
            _ensure_dir(d)

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

            # Estágio 1: Download do vídeo (gera arquivo local)
            job.status = PipelineStatus.DOWNLOADING
            video_or_audio_file = await self._execute_download(job)
            if not video_or_audio_file:
                job.mark_as_failed("Download failed")
                return job

            # Estágio 2: Normalização de áudio (envia arquivo via multipart e baixa o normalizado)
            job.status = PipelineStatus.NORMALIZING
            normalized_audio = await self._execute_normalization(job, video_or_audio_file)
            if not normalized_audio:
                job.mark_as_failed("Audio normalization failed")
                return job
            job.audio_file = str(normalized_audio)

            # Estágio 3: Transcrição (envia o áudio via multipart e baixa/retorna transcript)
            job.status = PipelineStatus.TRANSCRIBING
            transcript = await self._execute_transcription(job, normalized_audio)
            if not transcript:
                job.mark_as_failed("Transcription failed")
                return job

            # transcript pode ser arquivo (.srt/.vtt/.txt) — guardamos o caminho;
            # e opcionalmente extraímos o texto se for .txt ou .json
            job.transcription_file = str(transcript)
            if transcript.suffix.lower() in {".txt", ".json"}:
                try:
                    text = transcript.read_text(encoding="utf-8", errors="ignore")
                    job.transcription_text = text[:100000]  # evita inflar Redis
                except Exception:
                    pass

            job.mark_as_completed()
            logger.info(f"Pipeline completed for job {job.id}")
            return job

        except Exception as e:
            logger.error(f"Pipeline failed for job {job.id}: {e}")
            job.mark_as_failed(str(e))
            return job

    async def _execute_download(self, job: PipelineJob) -> Optional[Path]:
        """1) POST /jobs (json {url}); 2) poll GET /jobs/{id}; 3) GET /jobs/{id}/download"""
        stage = job.download_stage
        stage.start()

        try:
            payload = {"url": job.youtube_url}
            resp = await self.video_client.submit_job(json_payload=payload)
            stage.job_id = resp.get("job_id") or resp.get("id")
            if not stage.job_id:
                raise RuntimeError(f"video-downloader did not return job_id: {resp}")

            logger.info(f"Video job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.video_client, stage.job_id, stage)
            if not status:
                stage.fail("Download timeout or failed")
                return None

            # baixa o artefato (pode ser vídeo ou áudio extraído)
            out = await self.video_client.download_artifact(stage.job_id, self.dir_downloads, filename=f"{job.id}-download")
            stage.complete(str(out))
            job.update_progress()
            return out

        except Exception as e:
            logger.error(f"Download stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _execute_normalization(self, job: PipelineJob, input_path: Path) -> Optional[Path]:
        """1) POST /jobs (multipart file + params); 2) poll GET /jobs/{id}; 3) GET /jobs/{id}/download"""
        stage = job.normalization_stage
        stage.start()

        try:
            svc_cfg = get_microservice_config("audio-normalization")
            defaults = (svc_cfg.get("default_params") or {}).copy()

            data = {
                # mapeia para o que o serviço espera; mantive o nome usado no config: set_sample_rate_16k
                "remove_noise": str(job.remove_noise).lower(),
                "convert_to_mono": str(job.convert_to_mono).lower(),
                "set_sample_rate_16k": str(job.sample_rate_16k).lower(),
                **{k: (str(v).lower() if isinstance(v, bool) else v) for k, v in defaults.items()},
            }
            files = {"file": (os.path.basename(input_path), input_path.open("rb"))}

            resp = await self.audio_client.submit_job(files=files, data=data)
            stage.job_id = resp.get("job_id") or resp.get("id")
            if not stage.job_id:
                raise RuntimeError(f"audio-normalization did not return job_id: {resp}")

            logger.info(f"Audio normalization job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.audio_client, stage.job_id, stage)
            if not status:
                stage.fail("Normalization timeout or failed")
                return None

            out = await self.audio_client.download_artifact(stage.job_id, self.dir_normalized, filename=f"{job.id}-normalized")
            stage.complete(str(out))
            job.update_progress()
            return out

        except Exception as e:
            logger.error(f"Normalization stage failed: {e}")
            stage.fail(str(e))
            return None
        finally:
            # garante fechar o file descriptor se ainda aberto
            try:
                f = files["file"][1]  # type: ignore
                if not f.closed:
                    f.close()
            except Exception:
                pass

    async def _execute_transcription(self, job: PipelineJob, audio_path: Path) -> Optional[Path]:
        """1) POST /jobs (multipart file + language); 2) poll GET /jobs/{id}; 3) GET /jobs/{id}/download"""
        stage = job.transcription_stage
        stage.start()

        try:
            svc_cfg = get_microservice_config("audio-transcriber")
            defaults = (svc_cfg.get("default_params") or {}).copy()

            data: Dict[str, Any] = {**defaults}
            if job.language and job.language != "auto":
                data["language"] = job.language

            files = {"file": (os.path.basename(audio_path), audio_path.open("rb"))}

            resp = await self.transcription_client.submit_job(files=files, data=data)
            stage.job_id = resp.get("job_id") or resp.get("id")
            if not stage.job_id:
                raise RuntimeError(f"audio-transcriber did not return job_id: {resp}")

            logger.info(f"Transcription job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.transcription_client, stage.job_id, stage)
            if not status:
                stage.fail("Transcription timeout or failed")
                return None

            out = await self.transcription_client.download_artifact(stage.job_id, self.dir_transcripts, filename=f"{job.id}-transcript")
            stage.complete(str(out))
            job.update_progress()
            return out

        except Exception as e:
            logger.error(f"Transcription stage failed: {e}")
            stage.fail(str(e))
            return None
        finally:
            try:
                f = files["file"][1]  # type: ignore
                if not f.closed:
                    f.close()
            except Exception:
                pass

    async def _wait_until_done(
        self,
        client: MicroserviceClient,
        job_id: str,
        stage: PipelineStage,
    ) -> Optional[Dict[str, Any]]:
        """Polling GET /jobs/{id} até completed/success."""
        attempts = 0
        while attempts < self.max_attempts:
            try:
                status = await client.get_job_status(job_id)

                # progresso (aceita 0–1 ou 0–100)
                p = status.get("progress")
                if p is not None:
                    try:
                        val = float(p)
                        stage.progress = val * 100.0 if val <= 1.0 else val
                        stage.progress = max(0.0, min(100.0, stage.progress))
                    except Exception:
                        pass

                state = (status.get("status") or status.get("state") or "").lower()
                if state in {"completed", "success", "done", "finished"}:
                    logger.info(f"Job {job_id} completed")
                    return status
                if state in {"failed", "error", "cancelled", "canceled", "aborted"}:
                    err = status.get("error") or status.get("error_message") or "Unknown error"
                    logger.error(f"Job {job_id} failed: {err}")
                    stage.fail(err)
                    return None

            except Exception as e:
                logger.error(f"Error polling job {job_id}: {e}")

            await asyncio.sleep(self.poll_interval)
            attempts += 1

        logger.error(f"Job {job_id} timeout after {attempts} attempts")
        return None
