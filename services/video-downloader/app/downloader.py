import os
import asyncio
import logging
import yt_dlp
from pathlib import Path
from typing import Dict, Any, Optional
from .models import Job, JobStatus
from .user_agent_manager import UserAgentManager

logger = logging.getLogger(__name__)


class SimpleDownloader:
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Gerenciador inteligente de User-Agents
        quarantine_hours = int(os.getenv('UA_QUARANTINE_HOURS', '48'))
        max_error_count = int(os.getenv('UA_MAX_ERRORS', '3'))
        
        self.ua_manager = UserAgentManager(
            user_agents_file="user-agents.txt",
            quarantine_hours=quarantine_hours,
            max_error_count=max_error_count
        )
        
        # Referência para o job store será injetada
        self.job_store = None
    
    def _get_ydl_opts(self, job: Job) -> Dict[str, Any]:
        """Opções do yt-dlp otimizadas com User-Agent inteligente"""
        # Usa job.id completo (já inclui video_id_quality)
        # Isso garante que cada qualidade tenha arquivo separado
        filename_template = f"{job.id}_%(title)s.%(ext)s"
        
        # Obtém User-Agent do gerenciador inteligente
        user_agent = self.ua_manager.get_user_agent()
        
        opts = {
            'outtmpl': str(self.cache_dir / filename_template),
            'format': self._get_format_selector(job.quality),
            'noplaylist': True,
            'extractaudio': False,
            'writeinfojson': False,
            'writedescription': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': False,
            'progress_hooks': [lambda d: self._progress_hook(d, job)],
            'http_headers': {
                'User-Agent': user_agent
            }
        }
        
        # Armazena UA usado para report de erro se necessário
        job.current_user_agent = user_agent
        
        return opts
    
    def _get_format_selector(self, quality: str) -> str:
        """Converte qualidade em seletor de formato"""
        quality_map = {
            'best': 'best[ext=mp4]/best',
            'worst': 'worst[ext=mp4]/worst', 
            '720p': 'best[height<=720][ext=mp4]/best[height<=720]',
            '480p': 'best[height<=480][ext=mp4]/best[height<=480]',
            '360p': 'best[height<=360][ext=mp4]/best[height<=360]',
            # Áudio: Prioriza Opus (melhor compressão sem perder qualidade)
            # Opus: ~50-160kbps, M4A: ~128-256kbps, WebM: ~128-192kbps
            'audio': 'bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio'
        }
        return quality_map.get(quality, 'best[ext=mp4]/best')
    
    def _progress_hook(self, d: Dict[str, Any], job: Job) -> None:
        """Hook de progresso do yt-dlp"""
        try:
            if d['status'] == 'downloading':
                # Calcula progresso baseado em bytes baixados
                if 'total_bytes' in d and d['total_bytes']:
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d['total_bytes']
                    progress = (downloaded / total) * 100
                elif 'total_bytes_estimate' in d and d['total_bytes_estimate']:
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d['total_bytes_estimate']
                    progress = (downloaded / total) * 100
                else:
                    # Se não temos tamanho total, use progresso baseado em tempo
                    progress = min(job.progress + 1.0, 95.0)
                
                # Atualiza progresso no job
                job.progress = min(progress, 99.0)  # Máximo 99% até completar
                
                # Atualiza no store se disponível
                if self.job_store:
                    self.job_store.update_job(job)
                    
            elif d['status'] == 'finished':
                # Download concluído
                job.progress = 100.0
                if self.job_store:
                    self.job_store.update_job(job)
                    
        except Exception as e:
            logger.warning(f"Erro no hook de progresso: {e}")
            # Continue mesmo com erro no progresso
    
    async def download_video(self, job: Job) -> Job:
        """Download assíncrono de vídeo"""
        try:
            # Atualiza status
            job.status = JobStatus.DOWNLOADING
            
            # Executa download em thread separada para não bloquear
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._sync_download, 
                job
            )
            
            return result
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            return job
    
    def _sync_download(self, job: Job) -> Job:
        """Download síncrono (executado em thread) com report de erro para UA"""
        current_ua = None
        
        try:
            opts = self._get_ydl_opts(job)
            current_ua = getattr(job, 'current_user_agent', None)
            
            logger.info(f"Iniciando download com UA: {current_ua[:50] if current_ua else 'N/A'}...")
            
            # Progresso inicial
            job.progress = 5.0
            if self.job_store:
                self.job_store.update_job(job)
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Extrai informações primeiro
                info = ydl.extract_info(job.url, download=False)
                
                # Progresso após extrair info
                job.progress = 15.0
                if self.job_store:
                    self.job_store.update_job(job)
                
                # Atualiza job com informações
                title = info.get('title', 'unknown')
                ext = info.get('ext', 'mp4')
                
                # Usa job.id completo (video_id_quality) no nome do arquivo
                # Isso garante arquivos separados para cada qualidade
                filename = f"{job.id}_{title}.{ext}"
                
                # Sanitiza nome do arquivo
                filename = self._sanitize_filename(filename)
                job.filename = filename
                job.file_path = str(self.cache_dir / filename)
                
                # Progresso antes do download real
                job.progress = 20.0
                if self.job_store:
                    self.job_store.update_job(job)
                
                # Faz o download (progresso será atualizado pelo hook)
                ydl.download([job.url])
                
                # Verifica se arquivo foi criado e pega o tamanho
                # Busca por job.id completo (inclui qualidade)
                downloaded_files = list(self.cache_dir.glob(f"{job.id}_*"))
                if downloaded_files:
                    actual_file = downloaded_files[0]
                    job.file_path = str(actual_file)
                    job.filename = actual_file.name
                    job.file_size = actual_file.stat().st_size
                    
                    job.status = JobStatus.COMPLETED
                    job.completed_at = job.created_at.__class__.now()
                    job.progress = 100.0
                    
                    logger.info(f"Download concluído com sucesso: {job.filename}")
                else:
                    raise Exception("Arquivo não encontrado após download")
                    
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            
            logger.error(f"Erro no download: {str(e)}")
            
            # Reporta erro ao UserAgentManager se UA estava sendo usado
            if current_ua:
                error_details = f"Download failed: {str(e)}"
                self.ua_manager.report_error(current_ua, error_details)
                logger.warning(f"Erro reportado para UA: {current_ua[:50]}...")
        
        return job
    
    def _sanitize_filename(self, filename: str) -> str:
        """Remove caracteres inválidos do nome do arquivo"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:200]  # Limita tamanho
    
    def get_file_path(self, job: Job) -> Optional[Path]:
        """Retorna caminho do arquivo se existir"""
        if job.file_path and Path(job.file_path).exists():
            return Path(job.file_path)
        return None
    
    def get_user_agent_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do sistema de User-Agents"""
        return self.ua_manager.get_stats()
    
    def reset_user_agent(self, user_agent: str) -> bool:
        """Reset manual de User-Agent problemático"""
        return self.ua_manager.reset_user_agent(user_agent)