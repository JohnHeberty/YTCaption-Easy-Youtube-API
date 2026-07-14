"""
Cliente para comunicação com microserviços.

Implementa retry, circuit breaker e logging estruturado.
"""
from __future__ import annotations

import asyncio
import random
import re
from pathlib import Path
from typing import Any, Callable

import httpx
from common.log_utils import get_logger

from app.core.constants import BYTES_PER_MB, HEALTH_CHECK_TIMEOUT_SECONDS, DOWNLOAD_TIMEOUT_SECONDS, DOWNLOAD_READ_TIMEOUT_SECONDS, DOWNLOAD_WRITE_TIMEOUT_SECONDS, DOWNLOAD_CONNECT_TIMEOUT_SECONDS
from app.core.config import get_microservice_config, get_settings
from app.core.ssl_config import get_ssl_context
from app.domain.interfaces import MicroserviceClientInterface
from app.infrastructure.circuit_breaker import CircuitBreaker
from app.core.exceptions import CircuitBreakerOpenError, PipelineStageError

logger = get_logger(__name__)


def _filename_from_cd(cd: str | None) -> str | None:
    """Extrai filename do header Content-Disposition."""
    if not cd:
        return None

    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    return m.group(1) if m else None


class MicroserviceClient(MicroserviceClientInterface):
    """
    Cliente para comunicação com microserviços.

    Features:
    - Circuit breaker integrado
    - Retry com exponential backoff
    - SSL configurável
    - Logging estruturado
    """

    def __init__(self, service_name: str) -> None:
        """
        Inicializa cliente.

        Args:
            service_name: Nome do serviço (se2-video-downloader, se3-audio-normalization, se4-audio-transcriber)
        """
        self.service_name = service_name
        self.config = get_microservice_config(service_name)
        self.base_url = self.config["url"].rstrip("/")
        self.timeout = self.config["timeout"]
        self.endpoints = self.config["endpoints"]
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 2)

        settings = get_settings()
        self._headers: dict[str, str] = {}
        if settings.api_key:
            self._headers["X-API-Key"] = settings.api_key

        # Circuit breaker integrado
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_max_failures,
            recovery_timeout=settings.circuit_breaker_recovery_timeout,
            half_open_max_calls=settings.circuit_breaker_half_open_max_requests,
            name=service_name,
        )

    async def check_health(self) -> dict[str, Any]:
        """
        Verifica health do microserviço.

        IMPORTANTE: Health checks NÃO afetam o circuit breaker.

        Args:
            Nenhum

        Returns:
            Dict[str, Any]: Status do serviço com chaves 'status' e opcionalmente 'error'

        Example:
            >>> client = MicroserviceClient("se2-video-downloader")
            >>> health = await client.check_health()
            >>> print(health["status"])  # 'healthy' ou 'unhealthy'
        """
        try:
            url = f"{self.base_url}/health"
            ssl_verify = get_ssl_context()
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT_SECONDS, verify=ssl_verify) as client:
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as http_error:
            logger.warning(f"[{self.service_name}] Health check HTTP error: {http_error}")
            return {"status": "unhealthy", "error": f"HTTP {http_error.response.status_code}"}
        except httpx.RequestError as request_error:
            logger.warning(f"[{self.service_name}] Health check request failed: {request_error}")
            return {"status": "unhealthy", "error": str(request_error)}
        except Exception as unexpected_error:
            logger.warning(f"[{self.service_name}] Health check unexpected error: {unexpected_error}")
            return {"status": "unhealthy", "error": str(unexpected_error)}

    async def submit_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Submete job via JSON.

        Args:
            payload: Dados do job em formato dicionário

        Returns:
            Dict[str, Any]: Resposta do serviço com dados do job criado

        Raises:
            PipelineStageError: Se falhar na submissão ou circuit breaker estiver aberto
            CircuitBreakerOpenError: Se circuit breaker estiver aberto para o serviço

        Example:
            >>> client = MicroserviceClient("se2-video-downloader")
            >>> payload = {"youtube_url": "https://...", "options": {}}
            >>> response = await client.submit_job(payload)
            >>> print(response["job_id"])
        """
        async def _do_request() -> dict[str, Any]:
            url = self._url("submit")
            logger.info(f"Submitting JSON to {self.service_name}: {url}")
            ssl_verify = get_ssl_context()
            async with httpx.AsyncClient(timeout=self.timeout, verify=ssl_verify) as client:
                response = await client.post(url, json=payload, headers=self._headers)
                response.raise_for_status()
                return response.json()

        try:
            return await self._circuit_breaker.call(_do_request)
        except CircuitBreakerOpenError as circuit_error:
            raise PipelineStageError(
                "submit", f"Circuit breaker OPEN for {self.service_name}", service_name=self.service_name
            ) from circuit_error
        except httpx.HTTPStatusError as http_error:
            raise PipelineStageError(
                "submit", f"HTTP {http_error.response.status_code}", http_error, self.service_name
            ) from http_error
        except httpx.RequestError as request_error:
            raise PipelineStageError(
                "submit", f"Request failed: {str(request_error)}", request_error, self.service_name
            ) from request_error

    async def submit_multipart(
        self, files: dict[str, Any], data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Submete arquivo via multipart/form-data.

        Args:
            files: Arquivos a enviar como dicionário de arquivos
            data: Dados adicionais opcionais como dicionário

        Returns:
            Dict[str, Any]: Resposta do serviço com dados do processamento

        Raises:
            PipelineStageError: Se falhar no upload ou circuit breaker estiver aberto
            CircuitBreakerOpenError: Se circuit breaker estiver aberto para o serviço

        Example:
            >>> client = MicroserviceClient("se4-audio-transcriber")
            >>> files = {"audio": open("audio.wav", "rb")}
            >>> data = {"language": "pt"}
            >>> response = await client.submit_multipart(files, data)
        """
        async def _do_request() -> dict[str, Any]:
            url = self._url("submit")
            logger.info(f"Submitting multipart to {self.service_name}: {url}")
            ssl_verify = get_ssl_context()
            async with httpx.AsyncClient(timeout=self.timeout, verify=ssl_verify) as client:
                response = await client.post(url, files=files, data=data or {}, headers=self._headers)
                response.raise_for_status()
                return response.json()

        try:
            return await self._circuit_breaker.call(_do_request)
        except CircuitBreakerOpenError as circuit_error:
            raise PipelineStageError(
                "submit", f"Circuit breaker OPEN for {self.service_name}", service_name=self.service_name
            ) from circuit_error
        except httpx.HTTPStatusError as http_error:
            raise PipelineStageError(
                "submit", f"HTTP {http_error.response.status_code}", http_error, self.service_name
            ) from http_error
        except httpx.RequestError as request_error:
            raise PipelineStageError(
                "submit", f"Request failed: {str(request_error)}", request_error, self.service_name
            ) from request_error

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """
        Consulta status de um job.

        Args:
            job_id: ID do job a consultar

        Returns:
            Optional[Dict[str, Any]]: Status do job ou None se não encontrado

        Raises:
            httpx.HTTPStatusError: Se receber erro HTTP inesperado
            httpx.RequestError: Se falhar na comunicação
            CircuitBreakerOpenError: Se circuit breaker estiver aberto

        Example:
            >>> client = MicroserviceClient("se2-video-downloader")
            >>> status = await client.get_job_status("abc123")
            >>> print(status.get("progress", 0))
        """
        url = self._url("status", job_id=job_id)
        ssl_verify = get_ssl_context()

        async def _do_request() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=self.timeout, verify=ssl_verify) as client:
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()
                return response.json()

        try:
            return await self._circuit_breaker.call(_do_request)
        except httpx.HTTPStatusError as http_error:
            logger.error(f"[{self.service_name}] get_job_status HTTP error for job {job_id}: {http_error}")
            raise
        except httpx.RequestError as request_error:
            logger.error(f"[{self.service_name}] get_job_status request error for job {job_id}: {request_error}")
            raise

    async def download_file(self, job_id: str) -> tuple[bytes, str]:
        """
        Baixa resultado do job.

        Args:
            job_id: ID do job cujo resultado será baixado

        Returns:
            Tuple[bytes, str]: Tupla com conteúdo do arquivo em bytes e nome do arquivo

        Raises:
            PipelineStageError: Se falhar no download, arquivo muito grande, ou timeout
            CircuitBreakerOpenError: Se circuit breaker estiver aberto
            RuntimeError: Se arquivo exceder tamanho máximo ou timeout de download

        Example:
            >>> client = MicroserviceClient("se2-video-downloader")
            >>> content, filename = await client.download_file("abc123")
            >>> with open(filename, "wb") as f:
            ...     f.write(content)
        """
        url = self._url("download", job_id=job_id)
        service_settings = get_settings()
        max_size_bytes = service_settings.max_file_size_mb * 1024 * 1024
        download_timeout = httpx.Timeout(DOWNLOAD_TIMEOUT_SECONDS, read=DOWNLOAD_READ_TIMEOUT_SECONDS, write=DOWNLOAD_WRITE_TIMEOUT_SECONDS, connect=DOWNLOAD_CONNECT_TIMEOUT_SECONDS)
        ssl_verify = get_ssl_context()

        async def _download() -> tuple[bytes, str]:
            try:
                async with asyncio.timeout(960):  # 16 minutos total
                    async with httpx.AsyncClient(timeout=download_timeout, verify=ssl_verify) as client:
                        logger.info(f"[{self.service_name}] Starting download for job {job_id}...")
                        response = await client.get(url, headers=self._headers)
                        response.raise_for_status()

                        # Verifica Content-Length
                        content_length_header = response.headers.get("Content-Length")
                        if content_length_header and int(content_length_header) > max_size_bytes:
                            raise RuntimeError(f"File too large: {content_length_header} bytes")

                        extracted_filename = _filename_from_cd(response.headers.get("Content-Disposition")) or f"{self.service_name}-{job_id}"
                        file_content = response.content

                        if len(file_content) > max_size_bytes:
                            raise RuntimeError(f"Downloaded file too large: {len(file_content)} bytes")

                        logger.info(f"[{self.service_name}] Downloaded {extracted_filename}: {len(file_content) / BYTES_PER_MB:.1f}MB")
                        return file_content, extracted_filename

            except asyncio.TimeoutError as timeout_error:
                raise RuntimeError(f"Download timeout after 16 minutes for job {job_id}") from timeout_error

        try:
            return await self._circuit_breaker.call(_download)
        except CircuitBreakerOpenError as circuit_error:
            raise PipelineStageError(
                "download", f"Circuit breaker OPEN for {self.service_name}", service_name=self.service_name
            ) from circuit_error
        except httpx.HTTPStatusError as http_error:
            raise PipelineStageError(
                "download", f"HTTP {http_error.response.status_code}", http_error, self.service_name
            ) from http_error
        except httpx.RequestError as request_error:
            raise PipelineStageError(
                "download", f"Request failed: {str(request_error)}", request_error, self.service_name
            ) from request_error

    def _url(self, endpoint_key: str, **format_args: Any) -> str:
        """
        Gera URL completa para um endpoint.

        Args:
            endpoint_key: Chave do endpoint configurado
            **format_args: Argumentos para formatação do path

        Returns:
            URL completa do endpoint

        Raises:
            RuntimeError: Se endpoint não estiver configurado
        """
        path = self.endpoints.get(endpoint_key)
        if not path:
            raise RuntimeError(f"[{self.service_name}] endpoint '{endpoint_key}' não configurado")
        return f"{self.base_url}{path.format(**format_args)}"

    async def check_health_simple(self) -> bool:
        """
        Health check simples que retorna apenas bool.

        Returns:
            True se saudável

        Example:
            >>> client = MicroserviceClient("se2-video-downloader")
            >>> is_healthy = await client.check_health_simple()
            >>> if not is_healthy:
            ...     print("Service is down")
        """
        if self._circuit_breaker.state.value == "open":
            return False

        try:
            result = await self.check_health()
            return result.get("status") == "healthy"
        except Exception as e:
            logger.debug(f"[{self.service_name}] Health check simple failed: {e}")
            return False
