import os
import asyncio
import logging
import yt_dlp
from pathlib import Path
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from ..core.models import Job, JobStatus
from ..services.user_agent_manager import UserAgentManager

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential_jitter(initial=2, max=20),
    retry=retry_if_exception_type((IOError, OSError, ConnectionError)),
    reraise=True,
)
def _ytdlp_extract_info(ydl: yt_dlp.YoutubeDL, url: str) -> dict:
    """Extract video metadata with tenacity retry for transient network errors."""
    return ydl.extract_info(url, download=False)


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
    
    def _check_disk_space(self, output_dir: str) -> bool:
        """Verifica se há espaço em disco suficiente para download."""
        try:
            import shutil
            
            stat = shutil.disk_usage(output_dir)
            available_space = stat.free
            available_space_gb = available_space / (1024**3)
            
            # Verifica se há pelo menos 1GB livre
            min_space_gb = 1.0
            
            logger.info(f"💾 Espaço em disco - Disponível: {available_space_gb:.2f}GB")
            
            if available_space_gb < min_space_gb:
                logger.error(f"❌ Espaço em disco insuficiente! Disponível: {available_space_gb:.2f}GB, Mínimo: {min_space_gb}GB")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível verificar espaço em disco: {e}")
            return True  # fail-open


    
    def _get_format_selector(self, quality: str) -> str:
        """Converte qualidade em seletor de formato
        
        Evita formatos HLS fragmentados que causam problemas de 'empty file'.
        Prioriza formatos progressivos (non-HLS) quando possível.
        """
        quality_map = {
            # Evita HLS/DASH fragmentados, prefere progressive
            'best': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b',
            'worst': 'wv*[ext=mp4]+wa[ext=m4a]/w[ext=mp4]/wv*+wa/w',
            '720p': 'bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/bv*[height<=720]+ba/b[height<=720]',
            '480p': 'bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480][ext=mp4]/bv*[height<=480]+ba/b[height<=480]',
            '360p': 'bv*[height<=360][ext=mp4]+ba[ext=m4a]/b[height<=360][ext=mp4]/bv*[height<=360]+ba/b[height<=360]',
            # Áudio: Prioriza Opus (melhor compressão sem perder qualidade)
            # Opus: ~50-160kbps, M4A: ~128-256kbps, WebM: ~128-192kbps
            'audio': 'bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio'
        }
        return quality_map.get(quality, 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b')
    
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
                    
        except Exception as exc:
            logger.warning("Erro no hook de progresso: %s", exc)
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
            
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            return job
    
    def _sync_download(self, job: Job) -> Job:
        """
        Download síncrono RESILIENTE com multiple user agents e backoff exponencial
        
        Estratégia:
        - 3 user agents diferentes
        - 3 tentativas por user agent = 9 tentativas total
        - Backoff exponencial: 2^(2+i) onde i vai de 0 a 8
        - User agent em quarentena após 3 falhas
        """
        import time
        import math
        
        # Verifica espaço em disco antes de começar
        if not self._check_disk_space(str(self.cache_dir)):
            job.status = JobStatus.FAILED
            job.error_message = "Espaço em disco insuficiente para download (mínimo 1GB necessário)"
            if self.job_store:
                self.job_store.update_job(job)
            return job
        
        max_user_agents = 3
        max_attempts_per_ua = 3
        total_attempts = max_user_agents * max_attempts_per_ua
        
        logger.info(f"🚀 Iniciando download RESILIENTE: {max_user_agents} UAs × {max_attempts_per_ua} tentativas = {total_attempts} tentativas máximas")
        
        # Progresso inicial
        job.progress = 5.0
        if self.job_store:
            self.job_store.update_job(job)
        
        last_error = None
        current_ua = None
        attempt_global = 0
        
        # Loop por cada user agent
        for ua_index in range(max_user_agents):
            # Pega um novo user agent para esta rodada
            current_ua = self.ua_manager.get_user_agent()
            ua_display = current_ua[:50] if current_ua else 'N/A'
            
            logger.info(f"📱 User Agent {ua_index + 1}/{max_user_agents}: {ua_display}...")
            
            # Loop de tentativas para este user agent
            for attempt_ua in range(max_attempts_per_ua):
                attempt_global += 1
                
                logger.info(f"🔄 Tentativa {attempt_ua + 1}/{max_attempts_per_ua} com UA {ua_index + 1} (global: {attempt_global}/{total_attempts})")
                
                try:
                    # Calcula delay do backoff ANTES da tentativa (exceto primeira)
                    if attempt_global > 1:
                        # Fórmula: 2^(2 + i) onde i começa em 0
                        # Mas LIMITA a 60 segundos máximo!
                        delay_seconds = min(math.pow(2, 2 + (attempt_global - 2)), 60.0)
                        logger.warning(f"⏳ Aguardando {delay_seconds:.0f}s (backoff exponencial limitado)...")
                        time.sleep(delay_seconds)
                    
                    # Atualiza UA no job
                    job.current_user_agent = current_ua
                    
                    # Progresso baseado na tentativa global (5% a 20%)
                    progress_base = 5 + (15 * attempt_global / total_attempts)
                    job.progress = min(progress_base, 20.0)
                    if self.job_store:
                        self.job_store.update_job(job)
                    
                    # Prepara opções do yt-dlp
                    opts = self._get_ydl_opts_with_ua(job, current_ua)
                    
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        # Extrai informações primeiro
                        logger.info(f"📥 Extraindo informações do vídeo (tentativa {attempt_global})...")
                        info = _ytdlp_extract_info(ydl, job.url)
                        
                        # Progresso após extrair info
                        job.progress = min(progress_base + 5, 25.0)
                        if self.job_store:
                            self.job_store.update_job(job)
                        
                        # Atualiza job com informações
                        title = info.get('title', 'unknown')
                        ext = info.get('ext', 'mp4')
                        
                        # Usa apenas job.id para evitar problemas com caracteres especiais
                        filename = f"{job.id}.{ext}"
                        
                        job.filename = filename
                        job.file_path = str(self.cache_dir / filename)
                        
                        # Progresso antes do download real
                        job.progress = 30.0
                        if self.job_store:
                            self.job_store.update_job(job)
                        
                        logger.info(f"⬇️ Iniciando download do arquivo: {filename}")
                        
                        # Faz o download (progresso será atualizado pelo hook)
                        ydl.download([job.url])
                        
                        # Verifica se arquivo foi criado e pega o tamanho
                        downloaded_files = list(self.cache_dir.glob(f"{job.id}.*"))
                        if downloaded_files:
                            actual_file = downloaded_files[0]
                            job.file_path = str(actual_file)
                            job.filename = actual_file.name
                            job.file_size = actual_file.stat().st_size
                            
                            job.status = JobStatus.COMPLETED
                            job.completed_at = job.created_at.__class__.now()
                            job.progress = 100.0
                            
                            logger.info(f"✅ Download SUCESSO após {attempt_global} tentativas: {job.filename} ({job.file_size} bytes)")
                            logger.info(f"🎯 UA vencedor: {ua_display}...")
                            
                            return job  # ✅ SUCESSO! Retorna imediatamente
                        else:
                            raise FileNotFoundError("Arquivo não encontrado após download")
                            
                except Exception as exc:
                    last_error = exc
                    error_msg = str(exc)
                    
                    logger.error(f"❌ Erro na tentativa {attempt_global}: {error_msg}")
                    
                    # Se não é a última tentativa com este UA, apenas continua
                    if attempt_ua < max_attempts_per_ua - 1:
                        next_delay = min(math.pow(2, 2 + (attempt_global - 1)), 60.0)
                        logger.warning(f"🔁 Tentando novamente com o mesmo UA em {next_delay:.0f}s...")
                        continue
                    else:
                        # Última tentativa com este UA - reporta erro e coloca em quarentena
                        error_details = f"Failed after {max_attempts_per_ua} attempts: {error_msg}"
                        self.ua_manager.report_error(current_ua, error_details)
                        logger.warning(f"🚫 UA colocado em quarentena após {max_attempts_per_ua} falhas: {ua_display}...")
                        break  # Vai para o próximo UA
        
        # Se chegou aqui, todas as tentativas falharam
        logger.error(f"💥 FALHA TOTAL após {total_attempts} tentativas com {max_user_agents} user agents diferentes")
        
        job.status = JobStatus.FAILED
        job.error_message = f"Download failed after {total_attempts} attempts across {max_user_agents} user agents. Last error: {str(last_error)}"
        
        # Reporta erro final se temos UA atual
        if current_ua:
            self.ua_manager.report_error(current_ua, f"Final failure: {str(last_error)}")
        
        return job
    
    def _get_ydl_opts_with_ua(self, job: Job, user_agent: str) -> Dict[str, Any]:
        """Opções do yt-dlp com User-Agent específico"""
        filename_template = f"{job.id}.%(ext)s"
        
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
            },
            # Opções para melhor tratamento de fragmentos HLS
            'fragment_retries': 10,  # Tenta até 10x baixar fragmento faltante
            'skip_unavailable_fragments': False,  # Não pula fragmentos (falha se não conseguir)
            'extractor_retries': 3,  # Retry do extractor
            'file_access_retries': 3,  # Retry de acesso a arquivo
            'concurrent_fragment_downloads': 1,  # 1 fragmento por vez (mais estável)
            # Evita problemas com livestreams/vídeos ao vivo
            'live_from_start': False,  # Não baixa do início se for livestream
            'wait_for_video': 0,  # Não aguarda se vídeo ainda não está disponível
        }
        
        return opts
    
    def _sanitize_filename(self, filename: str) -> str:
        """Remove caracteres inválidos do nome do arquivo"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:200]  # Limita tamanho
    
    def get_file_path(self, job: Job) -> Optional[Path]:
        """Retorna caminho do arquivo se existir"""
        if not job.file_path:
            return None
        # Try stored path directly (absolute or relative from CWD)
        direct = Path(job.file_path)
        if direct.exists():
            return direct
        # Fallback: look in current cache_dir by filename only
        # (handles old jobs that stored relative paths before CACHE_DIR was fixed)
        fallback = self.cache_dir / direct.name
        if fallback.exists():
            return fallback
        return None
    
    def get_user_agent_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do sistema de User-Agents"""
        return self.ua_manager.get_stats()
    
    def reset_user_agent(self, user_agent: str) -> bool:
        """Reset manual de User-Agent problemático"""
        return self.ua_manager.reset_user_agent(user_agent)