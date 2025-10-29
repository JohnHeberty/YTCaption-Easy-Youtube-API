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
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import time

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
    """Cliente para comunicação com microserviços"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.config = get_microservice_config(service_name)
        self.base_url = self.config["url"].rstrip("/")
        self.timeout = self.config["timeout"]
        self.endpoints = self.config["endpoints"]
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 2)  # segundos

    async def _retry_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """Executa função com retry exponential backoff"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code
                # Não faz retry em erros de cliente (4xx), apenas servidor (5xx) e network
                if 400 <= status < 500:
                    logger.error(f"[{self.service_name}] Client error {status}, not retrying: {e}")
                    raise
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"[{self.service_name}] Attempt {attempt + 1}/{self.max_retries} failed with {status}, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[{self.service_name}] All {self.max_retries} attempts failed")
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"[{self.service_name}] Network error on attempt {attempt + 1}/{self.max_retries}, retrying in {delay}s: {type(e).__name__}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[{self.service_name}] All {self.max_retries} attempts failed with network errors")
        
        # Se chegou aqui, todas as tentativas falharam
        raise RuntimeError(f"[{self.service_name}] Failed after {self.max_retries} retries: {last_error}")

    def _url(self, endpoint_key: str, **fmt):
        path = self.endpoints.get(endpoint_key)
        if not path:
            raise RuntimeError(f"[{self.service_name}] endpoint '{endpoint_key}' não configurado.")
        return f"{self.base_url}{path.format(**fmt)}"

    async def submit_json(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST application/json com retry"""
        async def _do_request():
            url = self._url("submit")
            logger.info(f"Submitting JSON to {self.service_name}: {url}")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                return r.json()
        
        try:
            return await self._retry_with_backoff(_do_request)
        except Exception as e:
            logger.error(f"[{self.service_name}] submit_json failed: {e}")
            raise RuntimeError(f"[{self.service_name}] Failed to submit JSON: {str(e)}") from e

    async def submit_multipart(self, files: Dict[str, Any], data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """POST multipart/form-data com retry (para normalization e transcriber)"""
        async def _do_request():
            url = self._url("submit")
            logger.info(f"Submitting multipart to {self.service_name}: {url}")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(url, files=files, data=data or {})
                r.raise_for_status()
                return r.json()
        
        try:
            return await self._retry_with_backoff(_do_request)
        except Exception as e:
            logger.error(f"[{self.service_name}] submit_multipart failed: {e}")
            raise RuntimeError(f"[{self.service_name}] Failed to submit multipart: {str(e)}") from e

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        url = self._url("status", job_id=job_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()

    async def download_file(self, job_id: str) -> tuple[bytes, str]:
        """
        GET /jobs/{id}/download -> retorna (conteudo, filename)
        """
        url = self._url("download", job_id=job_id)
        
        async def _download():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(url)
                r.raise_for_status()
                filename = _filename_from_cd(r.headers.get("Content-Disposition")) or f"{self.service_name}-{job_id}"
                return r.content, filename
        
        return await self._retry_with_backoff(_download)

    async def check_health(self) -> bool:
        endpoint = self.endpoints.get("health", "/health")
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url)
                return r.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {self.service_name}: {e}")
            return False

# --- utilidades locais (adicione abaixo dos imports, antes do PipelineOrchestrator) ---
def _filename_from_cd(cd: Optional[str]) -> Optional[str]:
    if not cd:
        return None
    # Content-Disposition: attachment; filename="abc.webm"
    import re
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    return m.group(1) if m else None

def _bool_to_str(v: bool) -> str:
    return "true" if v else "false"

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
        """Executa pipeline completo com fluxo: download -> normalize -> transcribe"""
        try:
            logger.info(f"Starting pipeline for job {job.id}")

            # 0) (Opcional) pré-checagem de saúde
            health = await self.check_services_health()
            for svc, st in health.items():
                if st != "healthy":
                    logger.warning(f"Service {svc} is {st}. Proceeding anyway due to resilience focus.")

            # 1) DOWNLOAD (retorna bytes e nome do arquivo de áudio)
            job.status = PipelineStatus.DOWNLOADING
            dl = await self._execute_download(job)
            if not dl:
                job.mark_as_failed("Download failed")
                return job
            audio_bytes, audio_name = dl  # <<< AQUI desempacota

            # 2) NORMALIZAÇÃO (envia multipart; retorna bytes e nome do arquivo normalizado)
            job.status = PipelineStatus.NORMALIZING
            norm = await self._execute_normalization(job, audio_bytes, audio_name)
            if not norm:
                job.mark_as_failed("Audio normalization failed")
                return job
            norm_bytes, norm_name = norm  # <<< AQUI desempacota
            job.audio_file = norm_name     # opcional: mantemos compat com seu modelo

            # 3) TRANSCRIÇÃO (envia multipart; retorna dict com texto/arquivo/segments)
            job.status = PipelineStatus.TRANSCRIBING
            tr = await self._execute_transcription(job, norm_bytes, norm_name)
            if not tr:
                job.mark_as_failed("Transcription failed")
                return job

            job.transcription_text = tr.get("text")
            job.transcription_segments = tr.get("segments")
            job.transcription_file = tr.get("file_name")

            # 4) FECHAMENTO
            job.mark_as_completed()
            logger.info(f"Pipeline completed for job {job.id}")
            return job

        except Exception as e:
            logger.error(f"Pipeline failed for job {job.id}: {str(e)}")
            job.mark_as_failed(str(e))
            return job

    async def _execute_download(self, job: PipelineJob) -> Optional[tuple[bytes, str]]:
        """Cria job no downloader e baixa o ÁUDIO em memória (bytes, filename)."""
        stage = job.download_stage
        stage.start()
        try:
            payload = {"url": job.youtube_url, "quality": "audio"}
            resp = await self.video_client.submit_json(payload)
            stage.job_id = resp.get("job_id") or resp.get("id")
            if not stage.job_id:
                raise RuntimeError(f"video-downloader não retornou job_id: {resp}")

            logger.info(f"Video job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.video_client, stage.job_id, stage)
            if not status:
                stage.fail("Download job failed/timeout")
                return None

            # baixa o áudio do vídeo
            content, filename = await self.video_client.download_file(stage.job_id)
            stage.complete(filename)
            job.update_progress()
            return content, filename
        except Exception as e:
            logger.error(f"Download stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _execute_normalization(self, job: PipelineJob, audio_bytes: bytes, audio_name: str) -> Optional[tuple[bytes, str]]:
        """Envia o áudio por multipart para normalização e baixa o resultado."""
        stage = job.normalization_stage
        stage.start()
        try:
            cfg = get_microservice_config("audio-normalization")
            defaults = (cfg.get("default_params") or {}).copy()

            files = {
                # content-type genérico funciona; se souber a extensão use 'audio/webm' ou 'audio/mpeg'
                "file": (audio_name, audio_bytes, "application/octet-stream")
            }
            data = {
                # o serviço aceita 'true'/'false' em texto
                "remove_noise": _bool_to_str(job.remove_noise if job.remove_noise is not None else defaults.get("remove_noise", False)),
                "convert_to_mono": _bool_to_str(job.convert_to_mono if job.convert_to_mono is not None else defaults.get("convert_to_mono", False)),
                "apply_highpass_filter": _bool_to_str(job.apply_highpass_filter if job.apply_highpass_filter is not None else defaults.get("apply_highpass_filter", False)),
                "set_sample_rate_16k": _bool_to_str(job.set_sample_rate_16k if job.set_sample_rate_16k is not None else defaults.get("set_sample_rate_16k", False)),
                "isolate_vocals": _bool_to_str(job.isolate_vocals if job.isolate_vocals is not None else defaults.get("isolate_vocals", False)),
            }

            resp = await self.audio_client.submit_multipart(files=files, data=data)
            stage.job_id = resp.get("job_id") or resp.get("id")
            if not stage.job_id:
                raise RuntimeError(f"audio-normalization não retornou job_id: {resp}")

            logger.info(f"Audio normalization job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.audio_client, stage.job_id, stage)
            if not status:
                stage.fail("Normalization job failed/timeout")
                return None

            out_bytes, out_name = await self.audio_client.download_file(stage.job_id)
            stage.complete(out_name)
            job.update_progress()
            return out_bytes, out_name
        except Exception as e:
            logger.error(f"Normalization stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _execute_transcription(self, job: PipelineJob, audio_bytes: bytes, audio_name: str) -> Optional[Dict[str, Any]]:
        """Envia o áudio por multipart para transcrição e retorna dict com texto/arquivo."""
        stage = job.transcription_stage
        stage.start()
        try:
            cfg = get_microservice_config("audio-transcriber")
            defaults = (cfg.get("default_params") or {}).copy()

            lang_in = job.language or defaults.get("language_in", "auto")
            lang_out = job.language_out  # Pode ser None

            files = {
                "file": (audio_name, audio_bytes, "application/octet-stream")
            }
            data = {
                "language_in": lang_in
            }
            # Adiciona language_out apenas se especificado (tradução)
            if lang_out:
                data["language_out"] = lang_out

            resp = await self.transcription_client.submit_multipart(files=files, data=data)
            stage.job_id = resp.get("job_id") or resp.get("id")
            if not stage.job_id:
                raise RuntimeError(f"audio-transcriber não retornou job_id: {resp}")

            logger.info(f"Transcription job submitted: {stage.job_id}")

            status = await self._wait_until_done(self.transcription_client, stage.job_id, stage)
            if not status:
                stage.fail("Transcription job failed/timeout")
                return None

            # Busca o texto da transcrição (endpoint retorna JSON: {"text": "..."})
            text = None
            segments = None
            
            try:
                text_url = self.transcription_client._url("text", job_id=stage.job_id)
                async with httpx.AsyncClient(timeout=self.transcription_client.timeout) as client:
                    tr = await client.get(text_url)
                    if tr.status_code == 200:
                        # Parse JSON response para extrair apenas o texto
                        text_data = tr.json()
                        text = text_data.get("text", "")
                        logger.info(f"Transcription text retrieved: {len(text) if text else 0} chars")
            except Exception as e:
                logger.warning(f"Failed to get transcription text: {e}")

            # Busca os segments com timestamps (endpoint /transcription)
            try:
                transcription_url = self.transcription_client._url("transcription", job_id=stage.job_id)
                async with httpx.AsyncClient(timeout=self.transcription_client.timeout) as client:
                    tr = await client.get(transcription_url)
                    if tr.status_code == 200:
                        # Parse JSON completo com segments
                        transcription_data = tr.json()
                        segments = transcription_data.get("segments", [])
                        # Se não pegou o texto antes, pega agora do full_text
                        if not text:
                            text = transcription_data.get("full_text", "")
                        logger.info(f"Transcription segments retrieved: {len(segments)} segments")
            except Exception as e:
                logger.warning(f"Failed to get transcription segments: {e}")

            # baixa o arquivo de transcrição (SRT/VTT/TXT conforme o serviço gerar)
            out_bytes, out_name = await self.transcription_client.download_file(stage.job_id)

            result = {
                "text": text,
                "segments": segments,
                "file_name": out_name,
                "file_bytes_len": len(out_bytes)
            }

            stage.complete(out_name)
            job.update_progress()
            return result
        except Exception as e:
            logger.error(f"Transcription stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _wait_until_done(self, client: MicroserviceClient, job_id: str, stage: PipelineStage) -> Optional[Dict[str, Any]]:
        """Polling GET /jobs/{id} até completed/failed, com progresso 0..1 ou 0..100."""
        attempts = 0
        while attempts < self.max_attempts:
            try:
                status = await client.get_job_status(job_id)
                # progresso
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