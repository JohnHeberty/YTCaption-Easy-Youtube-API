"""
API Client para integração com microserviços existentes

⚠️ IMPORTANTE: Este cliente NÃO reimplementa funcionalidades.
Ele apenas ORQUESTRA chamadas HTTP para os microserviços existentes:
- youtube-search (Port 8003): Busca de shorts
- video-downloader (Port 8002): Download de vídeos
- audio-transcriber (Port 8005): Transcrição de áudio
"""

import httpx
import asyncio
import logging
from typing import Dict, List, Optional
from pathlib import Path

from .exceptions import MicroserviceException

logger = logging.getLogger(__name__)


class MicroservicesClient:
    """Cliente HTTP para integração com microserviços existentes.
    
    NÃO reimplementa funcionalidades - apenas chama APIs.
    """
    
    def __init__(self, 
                 youtube_search_url: str = "http://localhost:8003",
                 video_downloader_url: str = "http://localhost:8002",
                 audio_transcriber_url: str = "http://localhost:8005",
                 timeout: float = 30.0,  # Timeout menor para requests individuais
                 max_retries: int = 3):
        
        self.youtube_search_url = youtube_search_url.rstrip('/')
        self.video_downloader_url = video_downloader_url.rstrip('/')
        self.audio_transcriber_url = audio_transcriber_url.rstrip('/')
        self.max_retries = max_retries
        
        # Cliente HTTP com retry automático e SSL desabilitado
        transport = httpx.AsyncHTTPTransport(retries=max_retries)
        self.client = httpx.AsyncClient(
            timeout=timeout, 
            transport=transport,
            verify=False  # Ignorar verificação SSL
        )
        
        logger.info(f"🌐 Microservices Client initialized:")
        logger.info(f"   ├─ YouTube Search: {self.youtube_search_url}")
        logger.info(f"   ├─ Video Downloader: {self.video_downloader_url}")
        logger.info(f"   ├─ Audio Transcriber: {self.audio_transcriber_url}")
        logger.info(f"   └─ Max retries: {max_retries}")
    
    async def close(self):
        """Fecha cliente HTTP"""
        await self.client.aclose()
    
    async def search_shorts(self, query: str, max_results: int = 100) -> List[Dict]:
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
                params={"query": query, "max_results": max_results}
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
                    f"{self.youtube_search_url}/jobs/{job_id}"
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
                    raise MicroserviceException(
                        "youtube-search",
                        f"Search failed: {error_msg}",
                        {"job_id": job_id, "error": error_msg}
                    )
                
                # Aguardar próximo poll
                await asyncio.sleep(poll_interval)
            
            # Timeout
            raise MicroserviceException(
                "youtube-search",
                "Search timeout - job took too long",
                {"job_id": job_id, "max_wait": max_polls * poll_interval}
            )
        
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error calling youtube-search: {e}")
            raise MicroserviceException(
                "youtube-search",
                f"HTTP error: {str(e)}",
                {"error_type": type(e).__name__}
            )
    
    async def download_video(self, video_id: str, output_path: str) -> Dict:
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
        
        url = f"https://youtube.com/watch?v={video_id}"
        
        try:
            # Iniciar download
            logger.debug(f"   POST /jobs: url={url}, quality=best")
            response = await self.client.post(
                f"{self.video_downloader_url}/jobs",
                json={"url": url, "quality": "best"}
            )
            logger.debug(f"   Response status: {response.status_code}")
            response.raise_for_status()
            download_job = response.json()
            job_id = download_job["id"]
            
            logger.info(f"⬇️ Job de download criado: {job_id}")
            
            # Aguardar download (polling) - timeout reduzido
            poll_interval = 3  # segundos
            max_polls = 40  # 2 minutos total (reduzido de 10min)
            
            for attempt in range(max_polls):
                logger.debug(f"   Polling attempt {attempt+1}/{max_polls} for job {job_id}")
                response = await self.client.get(
                    f"{self.video_downloader_url}/jobs/{job_id}"
                )
                logger.debug(f"   Poll response status: {response.status_code}")
                response.raise_for_status()
                job = response.json()
                logger.debug(f"   Job status: {job.get('status')}, progress: {job.get('progress', 0)}%")
                
                if job["status"] == "completed":
                    # Baixar arquivo
                    logger.info(f"💾 Baixando arquivo: {output_path}")
                    video_response = await self.client.get(
                        f"{self.video_downloader_url}/jobs/{job_id}/download"
                    )
                    video_response.raise_for_status()
                    
                    # Salvar arquivo
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(video_response.content)
                    
                    logger.info(f"✅ Download completo: {video_id}")
                    return job.get("metadata", {})
                
                elif job["status"] in ["failed", "error"]:
                    error_msg = job.get("error_message", job.get("error", "Unknown error"))
                    logger.error(f"❌ Download falhou: {error_msg}")
                    raise MicroserviceException(
                        "video-downloader",
                        f"Download failed: {error_msg}",
                        {"job_id": job_id, "video_id": video_id, "error": error_msg}
                    )
                
                # Log de progresso a cada 20s
                if attempt % 7 == 0 and attempt > 0:
                    progress = job.get("progress", 0)
                    logger.info(f"⏳ Download em progresso... ({attempt * poll_interval}s, {progress}%)")
                
                # Aguardar próximo poll
                await asyncio.sleep(poll_interval)
            
            # Timeout - pular este vídeo em vez de falhar tudo
            logger.warning(f"⚠️ Timeout downloading {video_id} após {max_polls * poll_interval}s - pulando")
            raise MicroserviceException(
                "video-downloader",
                f"Download timeout after {max_polls * poll_interval}s",
                {"job_id": job_id, "video_id": video_id, "timeout": True}
            )
        
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error calling video-downloader: {e}")
            logger.debug(f"   Exception type: {type(e).__name__}, details: {str(e)}")
            raise MicroserviceException(
                "video-downloader",
                f"HTTP error: {str(e)}",
                {"error_type": type(e).__name__, "video_id": video_id}
            )
    
    async def transcribe_audio(self, audio_path: str, language: str = "pt") -> List[Dict]:
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
            # 1. Criar job de transcrição (POST /jobs)
            # OpenAPI params: file, language_in (default "auto"), language_out (opcional)
            with open(audio_path, "rb") as f:
                response = await self.client.post(
                    f"{self.audio_transcriber_url}/jobs",
                    files={"file": ("audio.ogg", f, "audio/ogg")},
                    data={"language_in": language}  # ✅ Corrigido: language_in ao invés de language
                    # language_out omitido = sem tradução (transcreve no idioma original)
                )
            response.raise_for_status()
            job = response.json()
            
            job_id = job.get("id")
            logger.info(f"🎤 Job de transcrição criado: {job_id}")
            
            # 2. Polling do status (GET /jobs/{job_id})
            poll_interval = 3  # segundos
            max_polls = 300  # 15 minutos total
            
            for attempt in range(max_polls):
                response = await self.client.get(
                    f"{self.audio_transcriber_url}/jobs/{job_id}"
                )
                response.raise_for_status()
                job = response.json()
                
                status = job.get("status")
                progress = job.get("progress", 0.0)
                
                # Log detalhado a cada 10 polls
                if attempt % 10 == 0 or status != "processing":
                    logger.info(f"📊 Poll #{attempt+1}: status={status}, progress={progress:.1%}")
                
                if status == "completed":
                    # 3. Buscar transcrição completa (GET /jobs/{job_id}/transcription)
                    # ✅ OpenAPI: Retorna TranscriptionResponse com segments[]
                    response = await self.client.get(
                        f"{self.audio_transcriber_url}/jobs/{job_id}/transcription"
                    )
                    response.raise_for_status()
                    transcription = response.json()
                    
                    # Extrair segments (já vem no formato correto)
                    segments = transcription.get("segments", [])
                    
                    # Dados opcionais (podem ser None)
                    lang_detected = transcription.get('language_detected') or 'N/A'
                    duration = transcription.get('duration') or 0
                    proc_time = transcription.get('processing_time') or 0
                    
                    logger.info(f"✅ Transcrição completa: {len(segments)} segmentos")
                    logger.info(f"   ├─ Idioma detectado: {lang_detected}")
                    logger.info(f"   ├─ Duração: {duration:.1f}s")
                    logger.info(f"   └─ Tempo processamento: {proc_time:.1f}s")
                    
                    return segments
                
                elif status == "failed":
                    error_msg = job.get("error_message", "Unknown error")
                    logger.error(f"❌ Transcrição falhou: {error_msg}")
                    raise MicroserviceException(
                        "audio-transcriber",
                        f"Transcription failed: {error_msg}",
                        {"job_id": job_id, "error": error_msg}
                    )
                
                # Aguardar próximo poll
                await asyncio.sleep(poll_interval)
            
            # Timeout após 15 minutos
            raise MicroserviceException(
                "audio-transcriber",
                "Transcription timeout - job took too long",
                {"job_id": job_id, "max_wait": max_polls * poll_interval}
            )
        
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error calling audio-transcriber: {e}")
            raise MicroserviceException(
                "audio-transcriber",
                f"HTTP error: {str(e)}",
                {"error_type": type(e).__name__}
            )
