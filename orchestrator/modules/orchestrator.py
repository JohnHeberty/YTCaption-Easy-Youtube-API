# orchestrator/modules/orchestrator.py
"""
Lógica de orquestração do pipeline completo (resiliente)
- Submete jobs aos microserviços
- Faz polling em /jobs/{id}
- Faz download de artefatos quando concluído
- Envia arquivo ao próximo serviço via multipart/form-data
"""
import os
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import httpx

from .models import (
    PipelineJob,
    PipelineStatus,
    StageStatus,
    PipelineStage,
)
from .config import get_orchestrator_settings, get_microservice_config

logger = logging.getLogger(__name__)


class MicroserviceClient:
    """Cliente para comunicação com microserviços, com suporte a download/upload."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.config = get_microservice_config(service_name)
        if not self.config:
            raise RuntimeError(f"Config for service '{service_name}' not found")

        self.base_url: str = self.config["url"].rstrip("/")
        self.timeout: int = self.config.get("timeout", 60)
        self.endpoints: Dict[str, str] = self.config.get("endpoints", {})

        # Endpoints padrão/fallbacks
        self.submit_ep = (
            self.endpoints.get("submit")
            or self.endpoints.get("process")
            or self.endpoints.get("download")  # legado downloader
            or "/jobs"
        )
        self.status_tmpl = self.endpoints.get("status", "/jobs/{job_id}")
        # template flexível de download — pode ser "/jobs/{job_id}/download",
        # "/jobs/{job_id}/download/{artifact}" etc.
        self.download_tmpl = self.endpoints.get("download", "/jobs/{job_id}/download")
        self.health_ep = self.endpoints.get("health", "/health")

    def _fmt(self, tmpl: str, **kv) -> str:
        return (self.base_url + tmpl).format(**kv)

    async def submit_job(self, json_payload: Dict[str, Any] | None = None,
                        files: Dict[str, Any] | None = None,
                        data: Dict[str, Any] | None = None,
                        headers: Dict[str, str] | None = None) -> Dict[str, Any]:
        base = self.submit_ep or "/jobs"
        candidates = [base]
        # alternativos comuns para normalizer/transcriber
        if self.service_name == "audio-normalization":
            if base != "/normalize": candidates.append("/normalize")
            if base != "/upload":    candidates.append("/upload")
        if self.service_name == "audio-transcriber":
            if base != "/transcribe": candidates.append("/transcribe")
            if base != "/upload":     candidates.append("/upload")

        data = data or {}
        headers = headers or {}
        # variações de nome de campo do arquivo
        fieldnames = ["file", "audio", "input", "audio_file", "upload"] if files else [None]

        last_err = None
        for ep in candidates:
            url = self._url(ep)
            for field in fieldnames:
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        if files:
                            (name, fobj) = next(iter(files.values()))
                            import os, mimetypes
                            mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
                            send_files = {field: (os.path.basename(name), fobj, mime)}
                            resp = await client.post(url, data=data, files=send_files, headers=headers)
                        else:
                            resp = await client.post(url, json=json_payload or {}, headers=headers)
                        resp.raise_for_status()
                        return resp.json()
                except httpx.HTTPStatusError as e:
                    body = ""
                    try:
                        body = e.response.text[:1000]
                    except Exception:
                        pass
                    logger.warning(f"[{self.service_name}] submit {url} field={field} failed: {e} body={body!r}")
                    last_err = e
                except Exception as e:
                    logger.warning(f"[{self.service_name}] submit {url} field={field} failed: {e}")
                    last_err = e

        raise RuntimeError(f"Submit to {self.service_name} failed: {last_err}")

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Consulta status do job."""
        url = self._fmt(self.status_tmpl, job_id=job_id)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    async def check_health(self) -> bool:
        """Health check simples."""
        url = self._fmt(self.health_ep)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url)
                return r.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {self.service_name}: {e}")
            return False

    async def download_artifact(self, job_id: str, dest_dir: Path, filename: Optional[str] = None) -> Path:
        _ensure_dir(dest_dir)
        primary = self._url(self.download_ep, job_id=job_id)

        # 1ª tentativa: conforme OpenAPI
        try:
            return await self._stream_to_file(primary, dest_dir, filename)
        except httpx.HTTPStatusError as e:
            if e.response is None or e.response.status_code != 404:
                raise
            logger.debug(f"{self.service_name} primary download 404, trying fallbacks...")
        # fallbacks de compatibilidade (se ainda houver versão antiga)
        for url in (f"{primary}?type=audio", f"{primary}?artifact=audio"):
            try:
                return await self._stream_to_file(url, dest_dir, filename)
            except Exception:
                continue
        raise RuntimeError(f"{self.service_name}: no artifact endpoint for job {job_id}")

    async def get_transcription_text(self, job_id: str) -> Optional[str]:
        if not self.text_ep:
            return None
        url = self._url(self.text_ep, job_id=job_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text

    async def get_full_transcription(self, job_id: str) -> Optional[Dict[str, Any]]:
        if not self.full_tx_ep:
            return None
        url = self._url(self.full_tx_ep, job_id=job_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()

class PipelineOrchestrator:
    """Orquestrador do pipeline completo"""

    def __init__(self):
        self.settings = get_orchestrator_settings()
        self.video_client = MicroserviceClient("video-downloader")
        self.audio_client = MicroserviceClient("audio-normalization")
        self.transcription_client = MicroserviceClient("audio-transcriber")

        self.poll_interval = self.settings["poll_interval"]
        self.max_attempts = self.settings["max_poll_attempts"]
        self.artifacts_dir = os.getenv("ARTIFACTS_DIR", "./artifacts")
        os.makedirs(self.artifacts_dir, exist_ok=True)

    async def check_services_health(self) -> Dict[str, str]:
        results = {}
        for name, client in [
            ("video-downloader", self.video_client),
            ("audio-normalization", self.audio_client),
            ("audio-transcriber", self.transcription_client),
        ]:
            ok = await client.check_health()
            results[name] = "healthy" if ok else "unhealthy"
        return results

    async def execute_pipeline(self, job: PipelineJob) -> PipelineJob:
        """Executa pipeline com resiliência completa."""
        try:
            logger.info(f"Starting pipeline for job {job.id}")
            health = await self.check_services_health()
            for svc, st in health.items():
                if st != "healthy":
                    logger.warning(f"Service {svc} is {st}. Proceeding due to resilience policy.")

            # 1) VIDEO → criar job e aguardar
            job.status = PipelineStatus.DOWNLOADING
            audio_from_video = await self._execute_download(job)
            if not audio_from_video:
                job.mark_as_failed("Download failed")
                return job

            # 2) NORMALIZE → enviar arquivo e aguardar
            job.status = PipelineStatus.NORMALIZING
            normalized_audio = await self._execute_normalization(job, audio_from_video)
            if not normalized_audio:
                job.mark_as_failed("Audio normalization failed")
                return job
            job.audio_file = normalized_audio

            # 3) TRANSCRIBE → enviar arquivo e aguardar
            job.status = PipelineStatus.TRANSCRIBING
            transcription = await self._execute_transcription(job, normalized_audio)
            if not transcription:
                job.mark_as_failed("Transcription failed")
                return job

            # preencher resultados
            if isinstance(transcription, dict):
                job.transcription_text = transcription.get("text")
                job.transcription_file = transcription.get("file") or transcription.get("srt_file")

            job.mark_as_completed()
            logger.info(f"Pipeline completed for job {job.id}")
            return job

        except Exception as e:
            logger.error(f"Pipeline failed for job {job.id}: {e}")
            job.mark_as_failed(str(e))
            return job

    async def _execute_download(self, job: PipelineJob) -> Optional[Path]:
        stage = job.download_stage
        stage.start()
        try:
            # peça ÁUDIO já no submit (conforme OpenAPI)
            payload = {"url": job.youtube_url, "quality": "audio"}
            resp = await self.video_client.submit_job(json_payload=payload)

            stage.job_id = resp.get("job_id") or resp.get("id")
            if not stage.job_id:
                raise RuntimeError(f"video-downloader did not return job_id: {resp}")
            logger.info(f"Video job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.video_client, stage)
            if not status:
                stage.fail("Download timeout or failed")
                return None

            # download “puro” → /jobs/{id}/download  (sem /audio e sem ?type=)
            out = await self.video_client.download_artifact(
                job_id=stage.job_id,
                dest_dir=self.dir_downloads,
                filename=f"{job.id}-audio-from-video"    # dica de nome
            )
            if out:
                stage.complete(str(out))
                job.update_progress()
                return out

            # fallback: tentar extrair caminho do status, se o serviço expuser
            out2 = self._extract_output_file(status)
            if out2:
                stage.complete(out2)
                job.update_progress()
                return Path(out2)

            stage.fail("No artifact returned by video-downloader")
            return None

        except Exception as e:
            logger.error(f"Download stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _execute_normalization(self, job: PipelineJob, audio_file: str) -> Optional[str]:
        """2) Envia áudio ao normalizer (multipart), faz polling e baixa áudio normalizado."""
        stage = job.normalization_stage
        stage.start()
        try:
            svc_cfg = get_microservice_config("audio-normalization")
            defaults = (svc_cfg.get("default_params") or {}).copy()

            form_data = {
                "remove_noise": str(job.remove_noise).lower(),
                "convert_to_mono": str(job.convert_to_mono).lower(),
                "set_sample_rate_16k": str(job.sample_rate_16k).lower(),
                **{k: str(v).lower() if isinstance(v, bool) else v for k, v in defaults.items()},
            }

            files = {"file": (os.path.basename(audio_file), open(audio_file, "rb"))}
            try:
                resp = await self.audio_client.submit_job(data=form_data, files=files)
            finally:
                files["file"][1].close()

            stage.job_id = resp.get("job_id") or resp.get("id")
            if not stage.job_id:
                raise RuntimeError(f"audio-normalization did not return job_id: {resp}")
            logger.info(f"Normalization job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.audio_client, stage)
            if not status:
                stage.fail("Timeout or failed")
                return None

            norm_path = await self.audio_client.download_artifact(
                job_id=stage.job_id,
                dest_dir=os.path.join(self.artifacts_dir, "normalized"),
                artifact="audio",
                filename_hint=f"{job.id}-normalized",
            )
            if not norm_path:
                norm_path = self._extract_output_file(status)

            if norm_path:
                stage.complete(norm_path)
                job.update_progress()
                return norm_path

            stage.fail("No artifact returned by audio-normalization")
            return None

        except Exception as e:
            logger.error(f"Normalization stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _execute_transcription(self, job: PipelineJob, audio_file: str) -> Optional[Dict[str, Any]]:
        """3) Envia áudio ao transcriber (multipart), faz polling e baixa a transcrição (SRT/TXT)."""
        stage = job.transcription_stage
        stage.start()
        try:
            svc_cfg = get_microservice_config("audio-transcriber")
            defaults = (svc_cfg.get("default_params") or {}).copy()

            form_data: Dict[str, Any] = {**defaults}
            if job.language and job.language != "auto":
                form_data["language"] = job.language

            files = {"file": (os.path.basename(audio_file), open(audio_file, "rb"))}
            try:
                resp = await self.transcription_client.submit_job(data=form_data, files=files)
            finally:
                files["file"][1].close()

            stage.job_id = resp.get("job_id") or resp.get("id")
            if not stage.job_id:
                raise RuntimeError(f"audio-transcriber did not return job_id: {resp}")
            logger.info(f"Transcription job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.transcription_client, stage)
            if not status:
                stage.fail("Timeout or failed")
                return None

            # tente baixar SRT, VTT ou TXT
            srt_path = (
                await self.transcription_client.download_artifact(
                    job_id=stage.job_id,
                    dest_dir=os.path.join(self.artifacts_dir, "transcriptions"),
                    artifact="srt",
                    filename_hint=f"{job.id}-transcription",
                )
                or await self.transcription_client.download_artifact(
                    job_id=stage.job_id,
                    dest_dir=os.path.join(self.artifacts_dir, "transcriptions"),
                    artifact="vtt",
                    filename_hint=f"{job.id}-transcription",
                )
                or await self.transcription_client.download_artifact(
                    job_id=stage.job_id,
                    dest_dir=os.path.join(self.artifacts_dir, "transcriptions"),
                    artifact="txt",
                    filename_hint=f"{job.id}-transcription",
                )
            )

            result: Dict[str, Any] = {"file": srt_path} if srt_path else {}

            # fallback: se o status já trouxer texto/caminho
            if not srt_path:
                text = status.get("text") or status.get("transcript")
                out_file = self._extract_output_file(status)
                if text:
                    result["text"] = text
                if out_file:
                    result["file"] = out_file

            if result:
                stage.complete(result.get("file"))
                job.update_progress()
                return result

            stage.fail("No artifact returned by audio-transcriber")
            return None

        except Exception as e:
            logger.error(f"Transcription stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _wait_until_done(
        self,
        client: MicroserviceClient,
        stage: PipelineStage,
    ) -> Optional[Dict[str, Any]]:
        """Polling: GET /jobs/{id} até estado final."""
        attempts = 0
        while attempts < self.max_attempts:
            try:
                status = await client.get_job_status(stage.job_id)
                # progresso pode vir 0–1 ou 0–100
                p = status.get("progress")
                if p is not None:
                    try:
                        p = float(p)
                        stage.progress = p * 100.0 if p <= 1.0 else p
                    except Exception:
                        pass

                state = (status.get("status") or status.get("state") or "").lower()
                if state in {"completed", "success", "done", "finished"}:
                    return status
                if state in {"failed", "error", "cancelled", "canceled", "aborted"}:
                    err = status.get("error") or status.get("error_message") or "Unknown error"
                    stage.fail(err)
                    return None

            except Exception as e:
                logger.error(f"Error polling job {stage.job_id}: {e}")

            await asyncio.sleep(self.poll_interval)
            attempts += 1

        logger.error(f"Job {stage.job_id} timeout after {attempts} attempts")
        return None

    def _extract_output_file(self, status: Dict[str, Any]) -> Optional[str]:
        """Tenta extrair caminho/URL do arquivo de um status heterogêneo."""
        # formatos comuns
        for k in ("output_file", "file", "audio_file", "path", "result_file"):
            if isinstance(status.get(k), str):
                return status[k]
        # artefatos estruturados
        artifacts = status.get("artifacts") or status.get("outputs")
        if isinstance(artifacts, dict):
            for cand in ("audio", "normalized_audio", "srt", "vtt", "txt", "file"):
                v = artifacts.get(cand)
                if isinstance(v, str):
                    return v
        return None
