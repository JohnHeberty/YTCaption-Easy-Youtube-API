"""
API Client para integração com microserviços existentes

⚠️ IMPORTANTE: Este cliente NÃO reimplementa funcionalidades.
Ele apenas ORQUESTRA chamadas HTTP para os microserviços existentes:
- youtube-search (Port 8003): Busca de shorts
- video-downloader (Port 8002): Download de vídeos
- audio-transcriber (Port 8005): Transcrição de áudio
"""
from __future__ import annotations

import httpx
import asyncio
from typing import Any
from pathlib import Path

from common.log_utils import get_logger
from ..shared.exceptions_v2 import (
    YouTubeSearchUnavailableException,
    VideoDownloaderUnavailableException,
    AudioTranscriberUnavailableException as TranscriberUnavailableException,
    TranscriptionTimeoutException,
    VideoDownloadException,
    VideoCorruptedException,
    ValidationException,
    APIRateLimitException
)

logger = get_logger(__name__)

class MicroservicesClient:
    """Cliente HTTP para integração com microserviços existentes.
    
    NÃO reimplementa funcionalidades - apenas chama APIs.
    """
    
    def __init__(self, 
                 youtube_search_url: str = "http://localhost:8003",
                 video_downloader_url: str = "http://localhost:8002",
                 audio_transcriber_url: str = "http://localhost:8005",
                 timeout: float = 30.0,
                 max_retries: int = 3,
                 api_key: str | None = None,
                 youtube_search_api_key: str | None = None,
                 video_downloader_api_key: str | None = None,
                 audio_transcriber_api_key: str | None = None) -> None:
        
        self.youtube_search_url = youtube_search_url.rstrip('/')
        self.video_downloader_url = video_downloader_url.rstrip('/')
        self.audio_transcriber_url = audio_transcriber_url.rstrip('/')
        self.max_retries = max_retries

        # Per-service API keys for authenticating WITH those services
        self._search_headers = {"X-API-Key": youtube_search_api_key} if youtube_search_api_key else {}
        self._downloader_headers = {"X-API-Key": video_downloader_api_key} if video_downloader_api_key else {}
        self._transcriber_headers = {"X-API-Key": audio_transcriber_api_key} if audio_transcriber_api_key else {}
        
        # Cliente HTTP com retry automático e SSL desabilitado
        transport = httpx.AsyncHTTPTransport(retries=max_retries)
        self.client = httpx.AsyncClient(
            timeout=timeout, 
            transport=transport,
            verify=False,
        )
        
        logger.info(f"🌐 Microservices Client initialized:")
        logger.info(f"   ├─ YouTube Search: {self.youtube_search_url}")
        logger.info(f"   ├─ Video Downloader: {self.video_downloader_url}")
        logger.info(f"   ├─ Audio Transcriber: {self.audio_transcriber_url}")
        logger.info(f"   └─ Max retries: {max_retries}")
    
    async def close(self) -> None:
        """Fecha cliente HTTP"""
        await self.client.aclose()
    
    async def search_shorts(self, query: str, max_results: int = 100) -> list[dict[str, Any]]:
        """✅ Busca shorts usando youtube-search API.
        
        Args:
            query: Query de busca
            max_results: Máximo de shorts para buscar
        
        Returns:
            Lista de shorts encontrados
        
        Raises:
            MicroserviceException: Se falhar a comunicação com youtube-search
        """
        
        logger.info(f"📡 Chamando youtube-search API: query={query}, max_results={max_results}")
        
        try:
            # Iniciar busca
            response = await self.client.post(
                f"{self.youtube_search_url}/search/shorts",
                params={"query": query, "max_results": max_results},
                headers=self._search_headers,
            )
            response.raise_for_status()
            search_job = response.json()
            job_id = search_job["id"]
            
            logger.info(f"🔍 Job de busca criado: {job_id}")
            
            # Aguardar resultado (polling)
            poll_interval = 2  # segundos
            max_polls = 150  # 5 minutos total
            
            for attempt in range(max_polls):
                response = await self.client.get(
                    f"{self.youtube_search_url}/jobs/{job_id}",
                    headers=self._search_headers,
                )
                response.raise_for_status()
                job = response.json()
                
                if job["status"] == "completed":
                    results = job["result"]["results"]
                    logger.info(f"✅ Busca completa: {len(results)} shorts encontrados")
                    return results
                
                elif job["status"] == "failed":
                    error_msg = job.get("error", "Unknown error")
                    logger.error(f"❌ Busca falhou: {error_msg}")
                    raise YouTubeSearchUnavailableException(
                        message=f"Search job failed: {error_msg}",
                        details={"job_id": job_id, "error": error_msg}
                    )
                
                # Aguardar próximo poll
                await asyncio.sleep(poll_interval)
            
            # Timeout
            raise YouTubeSearchUnavailableException(
                message="Search timeout - job took too long",
                details={"job_id": job_id, "max_wait_seconds": max_polls * poll_interval, "timeout": True}
            )
        
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error calling youtube-search: {e}")
            raise YouTubeSearchUnavailableException(
                message=f"HTTP error: {str(e)}",
                details={"error_type": type(e).__name__},
                cause=e
            )
    
    async def _initiate_download(self, video_id: str) -> str:
        """Start a download job and return the job_id."""
        url = f"https://youtube.com/watch?v={video_id}"
        logger.debug(f"   POST /jobs: url={url}, quality=best")
        response = await self.client.post(
            f"{self.video_downloader_url}/jobs",
            json={"url": url, "quality": "best"},
            headers=self._downloader_headers,
        )
        logger.debug(f"   Response status: {response.status_code}")
        response.raise_for_status()
        download_job = response.json()
        job_id = download_job["id"]
        logger.info(f"⬇️ Job de download criado: {job_id}")
        return job_id

    async def _poll_download_job(self, job_id: str, video_id: str, output_path: str) -> dict[str, Any]:
        """Poll download job until completed/failed/timeout. Returns metadata on success."""
        poll_interval = 3
        max_polls = 40

        for attempt in range(max_polls):
            logger.debug(f"   Polling attempt {attempt+1}/{max_polls} for job {job_id}")
            response = await self.client.get(
                f"{self.video_downloader_url}/jobs/{job_id}",
                headers=self._downloader_headers,
            )
            logger.debug(f"   Poll response status: {response.status_code}")
            response.raise_for_status()
            job = response.json()
            logger.debug(f"   Job status: {job.get('status')}, progress: {job.get('progress', 0)}%")

            if job["status"] == "completed":
                await self._download_and_save_file(job_id, video_id, output_path)
                return job.get("metadata", {})

            if job["status"] in ["failed", "error"]:
                error_msg = job.get("error_message", job.get("error", "Unknown error"))
                logger.error(f"❌ Download falhou: {error_msg}")
                raise VideoDownloadException(
                    video_id=video_id,
                    message=error_msg,
                    details={"job_id": job_id}
                )

            if attempt % 7 == 0 and attempt > 0:
                progress = job.get("progress", 0)
                logger.info(f"⏳ Download em progresso... ({attempt * poll_interval}s, {progress}%)")

            await asyncio.sleep(poll_interval)

        logger.warning(f"⚠️ Timeout downloading {video_id} após {max_polls * poll_interval}s - pulando")
        raise VideoDownloaderUnavailableException(
            message=f"Download timeout after {max_polls * poll_interval}s",
            details={"job_id": job_id, "video_id": video_id, "timeout": True}
        )

    async def _download_and_save_file(self, job_id: str, video_id: str, output_path: str) -> None:
        """Download the completed file and validate integrity."""
        logger.info(f"💾 Baixando arquivo: {output_path}")
        video_response = await self.client.get(
            f"{self.video_downloader_url}/jobs/{job_id}/download",
            headers=self._downloader_headers,
        )
        video_response.raise_for_status()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(video_response.content)

        file_size = len(video_response.content)
        logger.info(f"💾 File saved: {output_path} ({file_size} bytes)")
        await self._validate_downloaded_video_integrity(video_id, output_path, file_size)

    async def _validate_downloaded_video_integrity(self, video_id: str, output_path: str, file_size: int) -> None:
        """Validate downloaded video integrity with ffprobe. Raises on failure."""
        logger.info(f"🔍 Validating video integrity with ffprobe...")

        from ..shared.exceptions_v2 import ValidationException

        try:
            from ..services.video_builder import VideoBuilder
            validator = VideoBuilder(output_dir="/tmp")
            video_info = await validator.get_video_info(output_path)

            duration = video_info.get('duration', 0)
            codec = video_info.get('codec', 'unknown')

            if duration <= 0:
                raise ValidationException(
                    message=f"Invalid video duration: {duration}s",
                    details={"video_id": video_id, "duration": duration}
                )

            if codec == 'unknown':
                raise ValidationException(
                    message="Unknown or unsupported video codec",
                    details={"video_id": video_id}
                )

            logger.info(
                f"✅ Integrity validation passed: {video_id}",
                extra={"duration": duration, "codec": codec, "video_info": video_info}
            )

        except Exception as integrity_error:
            logger.error(
                f"❌ Downloaded video failed integrity check: {video_id}",
                extra={"error": str(integrity_error), "file_path": output_path, "file_size": file_size},
                exc_info=True
            )

            try:
                import os
                os.unlink(output_path)
                logger.info(f"🗑️  Removed corrupted file: {output_path}")
            except Exception as rm_error:
                logger.warning(f"Failed to remove corrupted file: {rm_error}")

            raise VideoCorruptedException(
                video_path=output_path,
                message=f"Downloaded video failed integrity validation: {str(integrity_error)}",
                details={"video_id": video_id, "file_size": file_size, "validation_error": str(integrity_error)},
                cause=integrity_error
            )

    async def download_video(self, video_id: str, output_path: str) -> dict[str, Any]:
        """✅ Baixa vídeo usando video-downloader API.

        Args:
            video_id: ID do vídeo do YouTube
            output_path: Caminho onde salvar o vídeo

        Returns:
            Metadados do vídeo baixado

        Raises:
            MicroserviceException: Se falhar a comunicação com video-downloader
        """
        logger.info(f"📡 Chamando video-downloader API: video_id={video_id}")
        logger.debug(f"   Downloader URL: {self.video_downloader_url}")

        try:
            job_id = await self._initiate_download(video_id)
            metadata = await self._poll_download_job(job_id, video_id, output_path)
            logger.info(f"✅ Download completo: {video_id}")
            return metadata

        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error calling video-downloader: {e}")
            logger.debug(f"   Exception type: {type(e).__name__}, details: {str(e)}")
            raise VideoDownloaderUnavailableException(
                message=f"HTTP error: {str(e)}",
                details={"error_type": type(e).__name__, "video_id": video_id},
                cause=e
            )
    
    async def _create_transcription_job(self, audio_path: str, language: str) -> str:
        """Create a transcription job with retry/backoff. Returns job_id."""
        max_create_attempts = 4
        base_backoff_seconds = 2

        for attempt in range(1, max_create_attempts + 1):
            try:
                with open(audio_path, "rb") as f:
                    response = await self.client.post(
                        f"{self.audio_transcriber_url}/jobs",
                        files={"file": ("audio.ogg", f, "audio/ogg")},
                        data={"language_in": language},
                        headers=self._transcriber_headers,
                    )
                response.raise_for_status()
                job = response.json()
                job_id = job.get("id")
                logger.info(f"🎤 Job de transcrição criado: {job_id}")
                return job_id
            except httpx.HTTPError as e:
                status_code = None
                if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
                    status_code = e.response.status_code

                is_retryable = status_code in [429, 502, 503, 504] or isinstance(
                    e,
                    (
                        httpx.ConnectError,
                        httpx.ConnectTimeout,
                        httpx.ReadTimeout,
                        httpx.WriteTimeout,
                        httpx.RemoteProtocolError,
                    ),
                )

                if attempt >= max_create_attempts or not is_retryable:
                    raise

                backoff_seconds = min(base_backoff_seconds * (2 ** (attempt - 1)), 20)
                logger.warning(
                    f"⚠️ audio-transcriber indisponível ao criar job "
                    f"(tentativa {attempt}/{max_create_attempts}, status={status_code}) - "
                    f"retry em {backoff_seconds}s"
                )
                await asyncio.sleep(backoff_seconds)

        raise TranscriberUnavailableException(
            message="Failed to create transcription job - empty job_id"
        )

    async def _poll_transcription_status(self, job_id: str) -> list[dict[str, Any]]:
        """Poll transcription job status until completed/failed/timeout. Returns segments."""
        poll_interval = 3
        max_polls = 10

        attempt = 0
        while attempt < max_polls:
            attempt += 1

            try:
                response = await self.client.get(
                    f"{self.audio_transcriber_url}/jobs/{job_id}",
                    headers=self._transcriber_headers,
                )
                response.raise_for_status()
                job = response.json()

                status = job.get("status")
                progress = job.get("progress", 0.0)

                logger.info(
                    f"📊 Poll #{attempt}/{max_polls}: status={status}, progress={progress:.1%}"
                )

                if status == "completed":
                    return await self._fetch_transcription_result(job_id)

                if status == "failed":
                    error_msg = job.get("error_message", "Unknown error")
                    logger.error(f"❌ Transcrição falhou: {error_msg}")
                    raise TranscriberUnavailableException(
                        message=f"Transcription job failed: {error_msg}"
                    )

            except httpx.HTTPError as e:
                logger.warning(
                    f"⚠️ Polling error (attempt {attempt}/{max_polls}): {e}"
                )
                if attempt >= max_polls:
                    raise

            if attempt < max_polls:
                await asyncio.sleep(poll_interval)

        logger.error(
            f"❌ Transcription timeout after {max_polls} polling attempts "
            f"({max_polls * poll_interval}s total)"
        )
        raise TranscriptionTimeoutException(job_id=job_id, max_polls=max_polls)

    async def _fetch_transcription_result(self, job_id: str) -> list[dict[str, Any]]:
        """Fetch the completed transcription result from the API."""
        response = await self.client.get(
            f"{self.audio_transcriber_url}/jobs/{job_id}/transcription",
            headers=self._transcriber_headers,
        )
        response.raise_for_status()
        transcription = response.json()

        segments = transcription.get("segments", [])
        lang_detected = transcription.get('language_detected') or 'N/A'
        duration = transcription.get('duration') or 0
        proc_time = transcription.get('processing_time') or 0

        logger.info(f"✅ Transcrição completa: {len(segments)} segmentos")
        logger.info(f"   ├─ Idioma detectado: {lang_detected}")
        logger.info(f"   ├─ Duração: {duration:.1f}s")
        logger.info(f"   └─ Tempo processamento: {proc_time:.1f}s")

        return segments

    async def transcribe_audio(self, audio_path: str, language: str = "pt") -> list[dict[str, Any]]:
        """✅ Transcreve áudio usando audio-transcriber API.

        Args:
            audio_path: Caminho do arquivo de áudio
            language: Código do idioma (pt, en, es, etc) ou 'auto' para detectar

        Returns:
            Lista de segmentos de transcrição com start, end, text

        Raises:
            MicroserviceException: Se falhar a comunicação com audio-transcriber
        """
        logger.info(f"📡 Chamando audio-transcriber API: language_in={language}")

        try:
            job_id = await self._create_transcription_job(audio_path, language)
            if not job_id:
                raise TranscriberUnavailableException(
                    message="Failed to create transcription job - empty job_id"
                )
            return await self._poll_transcription_status(job_id)

        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error calling audio-transcriber: {e}")
            status_code = None
            if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
                status_code = e.response.status_code
            raise TranscriberUnavailableException(
                message=f"HTTP error: {str(e)}",
                cause=e
            )
