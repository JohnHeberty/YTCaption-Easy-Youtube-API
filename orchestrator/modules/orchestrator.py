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
import random
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
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
    """Cliente para comunicação com microserviços com circuit breaker"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.config = get_microservice_config(service_name)
        self.base_url = self.config["url"].rstrip("/")
        self.timeout = self.config["timeout"]
        self.endpoints = self.config["endpoints"]
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 2)  # segundos
        
        # Circuit breaker configurável com half-open state
        settings = get_orchestrator_settings()
        self.failure_count = 0
        self.max_failures = settings["circuit_breaker_max_failures"]
        self.recovery_timeout = settings["circuit_breaker_recovery_timeout"]
        self.half_open_max_requests = settings.get("circuit_breaker_half_open_max_requests", 3)
        self.last_failure_time = None
        self._circuit_state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._half_open_attempts = 0
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Verifica health do microserviço
        IMPORTANTE: Health checks NÃO afetam o circuit breaker
        """
        try:
            url = f"{self.base_url}/health"
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                r = await client.get(url)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.warning(f"[{self.service_name}] Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    def _is_circuit_open(self) -> bool:
        """
        Verifica se o circuit breaker está aberto
        Implementa três estados: CLOSED, HALF_OPEN, OPEN
        """
        if self._circuit_state == "CLOSED":
            return False
        
        if self._circuit_state == "OPEN":
            # Se passou o tempo de recovery, transiciona para HALF_OPEN
            if self.last_failure_time and datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                logger.warning(f"🟡 [{self.service_name}] Circuit breaker OPEN → HALF_OPEN - testing recovery after {self.recovery_timeout}s downtime")
                self._circuit_state = "HALF_OPEN"
                self._half_open_attempts = 0
                return False  # Permite tentativas no estado HALF_OPEN
            return True  # Ainda está OPEN
        
        # Estado HALF_OPEN: permite algumas tentativas de teste
        if self._circuit_state == "HALF_OPEN":
            if self._half_open_attempts >= self.half_open_max_requests:
                logger.warning(f"⚠️ [{self.service_name}] Circuit breaker HALF_OPEN limit reached ({self._half_open_attempts}/{self.half_open_max_requests}), reopening")
                self._circuit_state = "OPEN"
                self.last_failure_time = datetime.now()
                return True
            return False  # Permite tentativa
        
        return False
    
    def _record_success(self):
        """Registra sucesso - fecha circuit breaker completamente"""
        previous_state = self._circuit_state
        if self._circuit_state != "CLOSED":
            logger.info(f"✅ [{self.service_name}] Circuit breaker {previous_state} → CLOSED - service recovered successfully")
        self._circuit_state = "CLOSED"
        self.failure_count = 0
        self._half_open_attempts = 0
        self.last_failure_time = None
    
    def _record_failure(self):
        """Registra falha - pode abrir circuit breaker"""
        self.last_failure_time = datetime.now()
        
        if self._circuit_state == "HALF_OPEN":
            # Se falhar no HALF_OPEN, volta para OPEN
            self._half_open_attempts += 1
            if self._half_open_attempts >= self.half_open_max_requests:
                self._circuit_state = "OPEN"
                logger.error(f"🔴 [{self.service_name}] Circuit breaker HALF_OPEN → OPEN - recovery failed after {self._half_open_attempts} attempts at {self.last_failure_time.strftime('%H:%M:%S')}")
            return
        
        if self._circuit_state == "CLOSED":
            self.failure_count += 1
            logger.warning(f"⚠️ [{self.service_name}] Failure {self.failure_count}/{self.max_failures} recorded")
            if self.failure_count >= self.max_failures:
                self._circuit_state = "OPEN"
                logger.critical(f"🚨 [{self.service_name}] Circuit breaker CLOSED → OPEN after {self.failure_count} consecutive failures - will retry in {self.recovery_timeout}s at {(datetime.now() + timedelta(seconds=self.recovery_timeout)).strftime('%H:%M:%S')}")

    async def _retry_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """Executa função com retry exponential backoff e circuit breaker"""
        # Verifica circuit breaker
        if self._is_circuit_open():
            raise RuntimeError(f"[{self.service_name}] Circuit breaker is {self._circuit_state} - service unavailable")
        
        # Incrementa contador se está em HALF_OPEN
        if self._circuit_state == "HALF_OPEN":
            self._half_open_attempts += 1
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                result = await func(*args, **kwargs)
                self._record_success()  # Registra sucesso
                return result
            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code
                # Não faz retry em erros de cliente (4xx), apenas servidor (5xx) e network
                if 400 <= status < 500:
                    logger.error(f"[{self.service_name}] Client error {status}, not retrying: {e}")
                    raise
                
                if attempt < self.max_retries - 1:
                    base_delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    jitter = random.uniform(0, base_delay * 0.1)  # 10% jitter
                    delay = base_delay + jitter
                    logger.warning(f"[{self.service_name}] Attempt {attempt + 1}/{self.max_retries} failed with {status}, retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[{self.service_name}] All {self.max_retries} attempts failed")
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    base_delay = self.retry_delay * (2 ** attempt)
                    jitter = random.uniform(0, base_delay * 0.1)  # 10% jitter
                    delay = base_delay + jitter
                    logger.warning(f"[{self.service_name}] Network error on attempt {attempt + 1}/{self.max_retries}, retrying in {delay:.1f}s: {type(e).__name__}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[{self.service_name}] All {self.max_retries} attempts failed with network errors")
        
        # Se chegou aqui, todas as tentativas falharam
        self._record_failure()  # Registra falha para circuit breaker
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
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                return r.json()
        
        try:
            return await self._retry_with_backoff(_do_request)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise RuntimeError(f"[{self.service_name}] Bad request - check payload format: {e}")
            elif e.response.status_code == 422:
                raise RuntimeError(f"[{self.service_name}] Validation error - check payload data: {e}")
            else:
                raise RuntimeError(f"[{self.service_name}] HTTP error submitting JSON: {e}")
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise RuntimeError(f"[{self.service_name}] Network error submitting JSON - service may be down: {e}")
        except Exception as e:
            logger.error(f"[{self.service_name}] submit_json failed: {e}")
            raise RuntimeError(f"[{self.service_name}] Failed to submit JSON: {str(e)}") from e

    async def submit_multipart(self, files: Dict[str, Any], data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """POST multipart/form-data com retry (para normalization e transcriber)"""
        async def _do_request():
            url = self._url("submit")
            logger.info(f"Submitting multipart to {self.service_name}: {url}")
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                r = await client.post(url, files=files, data=data or {})
                r.raise_for_status()
                return r.json()
        
        try:
            return await self._retry_with_backoff(_do_request)
        except httpx.HTTPStatusError as e:
            # Captura corpo da resposta para diagnóstico
            error_body = ""
            try:
                error_body = e.response.text[:500]  # Primeiros 500 chars
            except (AttributeError, ValueError, TypeError) as err:
                logger.debug(f"Could not extract error body: {err}")
                pass
            
            if e.response.status_code == 400:
                logger.error(f"[{self.service_name}] Bad request (400): {error_body}")
                raise RuntimeError(f"[{self.service_name}] Bad request - check file format or parameters: {error_body[:200]}")
            elif e.response.status_code == 413:
                raise RuntimeError(f"[{self.service_name}] File too large for service: {e}")
            elif e.response.status_code == 422:
                logger.error(f"[{self.service_name}] Validation error (422): {error_body}")
                raise RuntimeError(f"[{self.service_name}] Validation error - check file and parameters: {error_body[:200]}")
            else:
                logger.error(f"[{self.service_name}] HTTP error ({e.response.status_code}): {error_body}")
                raise RuntimeError(f"[{self.service_name}] HTTP error submitting multipart: {e}")
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise RuntimeError(f"[{self.service_name}] Network error submitting multipart - service may be down: {e}")
        except Exception as e:
            logger.error(f"[{self.service_name}] submit_multipart failed: {e}")
            raise RuntimeError(f"[{self.service_name}] Failed to submit multipart: {str(e)}") from e

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """GET /jobs/{id} com retry para verificar status"""
        async def _do_request():
            url = self._url("status", job_id=job_id)
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                r = await client.get(url)
                r.raise_for_status()
                return r.json()
        
        try:
            return await self._retry_with_backoff(_do_request)
        except Exception as e:
            logger.error(f"[{self.service_name}] get_job_status failed for job {job_id}: {e}")
            raise

    async def download_file(self, job_id: str) -> tuple[bytes, str]:
        """
        GET /jobs/{id}/download -> retorna (conteudo, filename) com verificação de tamanho e timeout
        """
        url = self._url("download", job_id=job_id)
        max_size_bytes = get_orchestrator_settings()["max_file_size_mb"] * 1024 * 1024
        
        # Timeout de 15 minutos para download completo (arquivos grandes)
        download_timeout = httpx.Timeout(300.0, read=900.0, write=300.0, connect=30.0)
        
        async def _download():
            try:
                # Timeout adicional de asyncio como fallback
                async with asyncio.timeout(960):  # 16 minutos total (margem extra)
                    async with httpx.AsyncClient(timeout=download_timeout, verify=False) as client:
                        logger.info(f"[{self.service_name}] Starting download for job {job_id}...")
                        r = await client.get(url)
                        r.raise_for_status()
                        
                        # Verifica Content-Length se disponível
                        content_length = r.headers.get("Content-Length")
                        if content_length:
                            size_mb = int(content_length) / (1024 * 1024)
                            logger.info(f"[{self.service_name}] Download size: {size_mb:.1f}MB")
                            
                            if int(content_length) > max_size_bytes:
                                raise RuntimeError(
                                    f"[{self.service_name}] File too large: {size_mb:.1f}MB > "
                                    f"{max_size_bytes/(1024*1024)}MB limit"
                                )
                        
                        filename = _filename_from_cd(r.headers.get("Content-Disposition")) or f"{self.service_name}-{job_id}"
                        content = r.content
                        
                        # Verifica tamanho real do conteúdo baixado
                        actual_size_mb = len(content) / (1024 * 1024)
                        if len(content) > max_size_bytes:
                            raise RuntimeError(
                                f"[{self.service_name}] Downloaded file too large: {actual_size_mb:.1f}MB > "
                                f"{max_size_bytes/(1024*1024)}MB limit"
                            )
                        
                        logger.info(f"[{self.service_name}] Downloaded {filename}: {actual_size_mb:.1f}MB")
                        return content, filename
                        
            except asyncio.TimeoutError:
                raise RuntimeError(
                    f"[{self.service_name}] Download timeout after 16 minutes for job {job_id}"
                )
        
        return await self._retry_with_backoff(_download)

    async def check_health_simple(self) -> bool:
        """Health check simples que retorna apenas bool (usado internamente)"""
        # Se circuit breaker está aberto, serviço é considerado unhealthy
        if self._is_circuit_open():
            logger.warning(f"Health check for {self.service_name}: CIRCUIT BREAKER OPEN")
            return False
            
        endpoint = self.endpoints.get("health", "/health")
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=10, verify=False) as client:  # Timeout maior para health check
                r = await client.get(url)
                healthy = r.status_code == 200
                if healthy:
                    # Health check bem-sucedido - registra sucesso para ajudar na recuperação
                    # mas apenas se não estivermos em HALF_OPEN (para não interferir no teste)
                    if self._circuit_state != "HALF_OPEN":
                        self._record_success()
                else:
                    logger.warning(f"Health check for {self.service_name} returned status {r.status_code}")
                return healthy
        except Exception as e:
            logger.error(f"Health check failed for {self.service_name}: {e}")
            # ✅ CORREÇÃO: Health check NÃO conta como falha operacional
            # Apenas retorna status sem afetar circuit breaker
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

    def __init__(self, redis_store=None):
        self.settings = get_orchestrator_settings()
        self.video_client = MicroserviceClient("video-downloader")
        self.audio_client = MicroserviceClient("audio-normalization")
        self.transcription_client = MicroserviceClient("audio-transcriber")

        self.poll_interval_initial = self.settings["poll_interval_initial"]
        self.poll_interval_max = self.settings["poll_interval_max"]
        self.max_attempts = self.settings["max_poll_attempts"]
        
        # Redis store para salvar progresso em tempo real
        self.redis_store = redis_store

    async def check_services_health(self) -> Dict[str, str]:
        results = {}
        for name, client in [
            ("video-downloader", self.video_client),
            ("audio-normalization", self.audio_client),
            ("audio-transcriber", self.transcription_client),
        ]:
            ok = await client.check_health_simple()
            results[name] = "healthy" if ok else "unhealthy"
        return results

    async def execute_pipeline(self, job: PipelineJob) -> PipelineJob:
        """Executa pipeline completo com fluxo: download -> normalize -> transcribe"""
        try:
            logger.info(f"Starting pipeline for job {job.id}")
            
            # Marca quando o pipeline começou a processar
            if not job.started_at:
                job.started_at = datetime.now()

            # 0) Pré-checagem de saúde crítica
            health = await self.check_services_health()
            unhealthy_services = [svc for svc, st in health.items() if st != "healthy"]
            
            if unhealthy_services:
                logger.warning(f"Unhealthy services detected: {unhealthy_services}")
                # Não bloqueia, mas registra para monitoramento
                for svc in unhealthy_services:
                    logger.warning(f"Service {svc} is {health[svc]} - pipeline may fail")

            # 1) DOWNLOAD (retorna bytes e nome do arquivo de áudio)
            job.status = PipelineStatus.DOWNLOADING
            if self.redis_store:
                self.redis_store.save_job(job)  # Salva status atualizado
            logger.info(f"[PIPELINE:{job.id}] Starting DOWNLOAD stage for URL: {job.youtube_url}")
            dl = await self._execute_download(job)
            if not dl:
                logger.error(f"[PIPELINE:{job.id}] DOWNLOAD stage failed")
                job.mark_as_failed("Download failed")
                if self.redis_store:
                    self.redis_store.save_job(job)
                return job
            audio_bytes, audio_name = dl  # <<< AQUI desempacota
            logger.info(f"[PIPELINE:{job.id}] DOWNLOAD completed: {audio_name} ({len(audio_bytes)/(1024*1024):.1f}MB)")

            # 2) NORMALIZAÇÃO (envia multipart; retorna bytes e nome do arquivo normalizado)
            job.status = PipelineStatus.NORMALIZING
            if self.redis_store:
                self.redis_store.save_job(job)  # Salva status atualizado
            logger.info(f"[PIPELINE:{job.id}] Starting NORMALIZATION stage")
            norm = await self._execute_normalization(job, audio_bytes, audio_name)
            if not norm:
                logger.error(f"[PIPELINE:{job.id}] NORMALIZATION stage failed")
                job.mark_as_failed("Audio normalization failed")
                if self.redis_store:
                    self.redis_store.save_job(job)
                return job
            norm_bytes, norm_name = norm  # <<< AQUI desempacota
            job.audio_file = norm_name     # opcional: mantemos compat com seu modelo
            logger.info(f"[PIPELINE:{job.id}] NORMALIZATION completed: {norm_name} ({len(norm_bytes)/(1024*1024):.1f}MB)")

            # 3) TRANSCRIÇÃO (envia multipart; retorna dict com texto/arquivo/segments)
            job.status = PipelineStatus.TRANSCRIBING
            if self.redis_store:
                self.redis_store.save_job(job)  # Salva status atualizado
            logger.info(f"[PIPELINE:{job.id}] Starting TRANSCRIPTION stage")
            tr = await self._execute_transcription(job, norm_bytes, norm_name)
            if not tr:
                logger.error(f"[PIPELINE:{job.id}] TRANSCRIPTION stage failed")
                job.mark_as_failed("Transcription failed")
                return job

            job.transcription_text = tr.get("text")
            job.transcription_segments = tr.get("segments")
            job.transcription_file = tr.get("file_name")
            logger.info(f"[PIPELINE:{job.id}] TRANSCRIPTION completed: {len(job.transcription_text or '')} chars, {len(job.transcription_segments or [])} segments")

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
                raise RuntimeError(f"video-downloader não retornou job_id válido: {resp}")

            logger.info(f"Video job submitted: {stage.job_id}")
            
            # Aguarda um momento para o job ser processado antes de verificar status
            await asyncio.sleep(1)

            status = await self._wait_until_done(self.video_client, stage.job_id, stage)
            if not status:
                stage.fail("Download job failed/timeout")
                return None

            # baixa o áudio do vídeo
            content, filename = await self.video_client.download_file(stage.job_id)
            stage.complete(filename)
            job.update_progress()
            
            # Salva progresso no Redis
            if self.redis_store:
                self.redis_store.save_job(job)
                
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
            
            # Salva progresso no Redis
            if self.redis_store:
                self.redis_store.save_job(job)
                
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
                async with httpx.AsyncClient(timeout=self.transcription_client.timeout, verify=False) as client:
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
                async with httpx.AsyncClient(timeout=self.transcription_client.timeout, verify=False) as client:
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
            
            # Salva progresso no Redis
            if self.redis_store:
                self.redis_store.save_job(job)
                
            return result
        except Exception as e:
            logger.error(f"Transcription stage failed: {e}")
            stage.fail(str(e))
            return None

    async def _wait_until_done(self, client: MicroserviceClient, job_id: str, stage: PipelineStage) -> Optional[Dict[str, Any]]:
        """Polling GET /jobs/{id} até completed/failed, com progresso 0..1 ou 0..100."""
        attempts = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        # Define timeout específico baseado no serviço
        service_name = client.service_name
        if service_name == "audio-normalization":
            max_wait_time = self.settings.get("audio_normalization_job_timeout", 3600)
        elif service_name == "audio-transcriber":
            max_wait_time = self.settings.get("audio_transcriber_job_timeout", 2400)
        else:  # video-downloader
            max_wait_time = self.settings.get("video_downloader_job_timeout", 1800)
        
        start_time = asyncio.get_event_loop().time()
        
        while attempts < self.max_attempts:
            # Verifica timeout global
            elapsed_time = asyncio.get_event_loop().time() - start_time
            if elapsed_time > max_wait_time:
                logger.error(f"Job {job_id} timeout after {elapsed_time:.0f}s (max: {max_wait_time}s)")
                stage.fail(f"Timeout after {elapsed_time:.0f}s")
                return None
            
            try:
                status = await client.get_job_status(job_id)
                consecutive_errors = 0  # Reset contador de erros em caso de sucesso
                
                # progresso
                if "progress" in status:
                    try:
                        p = float(status["progress"])
                        stage.progress = p * 100.0 if p <= 1.0 else p
                    except Exception:
                        pass
                
                state = (status.get("status") or status.get("state") or "").lower()
                if state in {"completed", "success", "done", "finished"}:
                    logger.info(f"Job {job_id} completed successfully after {elapsed_time:.0f}s")
                    return status
                if state in {"failed", "error", "cancelled", "canceled", "aborted"}:
                    error_msg = status.get("error") or status.get("error_message", f"Job failed with state: {state}")
                    logger.error(f"Job {job_id} failed: {error_msg}")
                    stage.fail(error_msg)
                    return None
                    
                # Estado em progresso
                logger.debug(f"Job {job_id} status: {state}, progress: {stage.progress}%, elapsed: {elapsed_time:.0f}s")
                
            except httpx.HTTPStatusError as e:
                consecutive_errors += 1
                if e.response.status_code == 404:
                    if attempts < 3:  # Nos primeiros attempts, 404 pode ser normal (job ainda sendo criado)
                        logger.warning(f"Job {job_id} not found yet (attempt {attempts + 1}), retrying...")
                    else:
                        logger.error(f"Job {job_id} not found after {attempts} attempts - may have been deleted or expired")
                        stage.fail(f"Job not found: {e}")
                        return None
                elif e.response.status_code >= 500:
                    logger.warning(f"Server error polling job {job_id} (attempt {attempts + 1}): {e}")
                else:
                    logger.error(f"Client error polling job {job_id}: {e}")
                    stage.fail(f"Polling failed: {e}")
                    return None
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as e:
                consecutive_errors += 1
                logger.warning(f"Network error polling job {job_id} (attempt {attempts + 1}): {type(e).__name__}")
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Unexpected error polling job {job_id} (attempt {attempts + 1}): {e}")
            
                # Se muitos erros consecutivos, aborta
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Too many consecutive errors ({consecutive_errors}) polling job {job_id}, giving up")
                stage.fail(f"Too many polling errors - service may be down")
                return None
            
            # Polling adaptativo: começa rápido, fica mais lento com o tempo
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