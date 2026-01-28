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
        
        url = f"https://youtube.com/watch?v={video_id}"
        
        try:
            # Iniciar download
            response = await self.client.post(
                f"{self.video_downloader_url}/jobs",
                json={"url": url, "quality": "best"}
            )
            response.raise_for_status()
            download_job = response.json()
            job_id = download_job["id"]
            
            logger.info(f"⬇️ Job de download criado: {job_id}")
            
            # Aguardar download (polling) - timeout reduzido
            poll_interval = 3  # segundos
            max_polls = 40  # 2 minutos total (reduzido de 10min)
            
            for attempt in range(max_polls):
                response = await self.client.get(
                    f"{self.video_downloader_url}/jobs/{job_id}"
                )
                response.raise_for_status()
                job = response.json()
                
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
            
            # Timeout
            raise MicroserviceException(
                "video-downloader",
                "Download timeout - job took too long",
                {"job_id": job_id, "video_id": video_id, "max_wait": max_polls * poll_interval}
            )
        
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error calling video-downloader: {e}")
            raise MicroserviceException(
                "video-downloader",
                f"HTTP error: {str(e)}",
                {"error_type": type(e).__name__, "video_id": video_id}
            )
    
    async def transcribe_audio(self, audio_path: str, language: str = "pt") -> List[Dict]:
        """✅ Transcreve áudio usando audio-transcriber API.
        
        Args:
            audio_path: Caminho do arquivo de áudio
            language: Código do idioma (pt, en, es, etc)
        
        Returns:
            Lista de segmentos de transcrição
        
        Raises:
            MicroserviceException: Se falhar a comunicação com audio-transcriber
        """
        
        logger.info(f"📡 Chamando audio-transcriber API: language={language}")
        
        try:
            # Upload e transcrição usando /jobs
            with open(audio_path, "rb") as f:
                response = await self.client.post(
                    f"{self.audio_transcriber_url}/jobs",
                    files={"file": ("audio.ogg", f, "audio/ogg")},
                    data={"language": language, "operation": "transcribe"}
                )
            response.raise_for_status()
            result = response.json()
            
            # API retorna job
            job_id = result.get("id")
            logger.info(f"🎤 Job de transcrição criado: {job_id}")
            
            # Aguardar transcrição (polling)
            poll_interval = 5  # segundos
            max_polls = 240  # 20 minutos total
            
            for attempt in range(max_polls):
                response = await self.client.get(
                    f"{self.audio_transcriber_url}/jobs/{job_id}"
                )
                response.raise_for_status()
                job = response.json()
                
                # Log detalhado do status
                logger.info(f"📊 Poll #{attempt+1}: status={job.get('status')}, progress={job.get('progress', 'N/A')}")
                
                if job["status"] == "completed":
                    # Extrair segmentos da transcrição
                    segments_data = job.get("transcription_segments", [])
                    
                    # Formatar segmentos
                    segments = []
                    for seg in segments_data:
                        segments.append({
                            "start": seg.get("start", 0.0),
                            "end": seg.get("end", 0.0),
                            "text": seg.get("text", "")
                        })
                    
                    logger.info(f"✅ Transcrição completa: {len(segments)} segmentos")
                    return segments
                
                elif job["status"] == "failed":
                    error_msg = job.get("error", "Unknown error")
                    logger.error(f"❌ Transcrição falhou: {error_msg}")
                    raise MicroserviceException(
                        "audio-transcriber",
                        f"Transcription failed: {error_msg}",
                        {"job_id": job_id, "error": error_msg}
                    )
                
                # Log de progresso
                if attempt % 6 == 0 and attempt > 0:
                    logger.info(f"⏳ Transcrição em progresso... ({attempt * poll_interval}s)")
                
                # Aguardar próximo poll
                await asyncio.sleep(poll_interval)
            
            # Timeout
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
