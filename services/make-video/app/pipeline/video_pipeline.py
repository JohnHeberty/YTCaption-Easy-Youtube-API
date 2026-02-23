"""
Pipeline Service - Download, Transform, Validate, Approve

Gerencia o pipeline completo de vídeos:
1. Download → data/raw/
2. Transform → data/transform/ (conversão H264)
3. Validate → data/validate/ (detecção legendas)
4. Approve → data/approved/ (vídeos finais)
5. Cleanup → Remove das pastas anteriores
6. Blacklist → Vídeos reprovados não são reprocessados
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import httpx
from datetime import datetime

from app.core.config import get_settings
from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2
from app.services.video_status_factory import get_video_status_store
from app.services.video_builder import VideoBuilder

logger = logging.getLogger(__name__)
settings = get_settings()


class VideoPipeline:
    """
    Pipeline completo para processar vídeos
    
    Fluxo CORRETO (com crop ANTES da validação):
    1. Download → data/raw/shorts/
    2. Transform → data/transform/videos/ (H264)
    3. CROP PERMANENTE → data/transform/videos/ (9:16 - substitui o H264)
    4. Validate → Detector de legendas no vídeo JÁ cropado (97.73% acurácia)
    5. Approve/Reject:
       - Aprovado: Move vídeo CROPADO para data/approved/videos/
       - Reprovado: Adiciona ao blacklist + deleta TODOS os arquivos
    6. Cleanup: Remove de pastas anteriores a cada step
    
    GARANTIA: Vídeos em approved/ estão SEMPRE cropados para 9:16
    """
    
    def __init__(self):
        self.detector = SubtitleDetectorV2(show_log=True)
        self.status_store = get_video_status_store()  # Approved + Rejected tracking
        self.video_builder = VideoBuilder(
            output_dir="data/approved/output"
        )  # Para crop_video_for_validation
        self.settings = settings
        
        # Criar diretórios
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Garantir que todos os diretórios existem"""
        dirs = [
            'data/raw/shorts',
            'data/raw/audio',
            'data/transform/videos',
            'data/validate/in_progress',
            'data/approved/videos',
            'data/approved/output',
        ]
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def move_to_validation(self, video_id: str, transform_path: str, job_id: str) -> str:
        """
        Move vídeo transformado para pasta de validação com tag de progresso
        
        Flow:
        - Input: data/transform/videos/{video_id}.mp4
        - Output: data/validate/in_progress/{job_id}_{video_id}_PROCESSING_.mp4
        
        Args:
            video_id: ID do vídeo
            transform_path: Path do vídeo transformado
            job_id: ID do job (para rastreamento)
        
        Returns:
            Path do arquivo com tag
        """
        transform_file = Path(transform_path)
        if not transform_file.exists():
            raise FileNotFoundError(f"Transform file not found: {transform_path}")
        
        # Criar path com tag
        validate_dir = Path("data/validate/in_progress")
        validate_dir.mkdir(parents=True, exist_ok=True)
        
        tagged_filename = f"{job_id}_{video_id}_PROCESSING_.mp4"
        tagged_path = validate_dir / tagged_filename
        
        # Move atômico
        logger.info(f"🔄 Moving to validation: {video_id}")
        logger.debug(f"   From: {transform_path}")
        logger.debug(f"   To: {tagged_path}")
        
        transform_file.rename(tagged_path)
        
        logger.info(f"🏷️  Processing tag added: {tagged_filename}")
        return str(tagged_path)
    
    def finalize_validation(self, tagged_path: str, video_id: str, approved: bool, job_id: str = None) -> Optional[str]:
        """
        Finaliza validação: remove tag e move/delete conforme resultado
        
        Args:
            tagged_path: Path com tag _PROCESSING_
            video_id: ID do vídeo
            approved: Se True, move para approved; Se False, deleta de TODAS as pastas
            job_id: ID do job (para limpeza completa)
        
        Returns:
            Path final do vídeo aprovado, ou None se rejeitado
        """
        tagged_file = Path(tagged_path)
        if not tagged_file.exists():
            logger.warning(f"⚠️  Tagged file not found: {tagged_path}")
            return None
        
        try:
            if approved:
                # Remover tag e mover para approved
                approved_dir = Path("data/approved/videos")
                approved_dir.mkdir(parents=True, exist_ok=True)
                final_path = approved_dir / f"{video_id}.mp4"
                
                logger.info(f"✅ Validation complete, moving to approved: {video_id}")
                tagged_file.rename(final_path)
                logger.info(f"   Approved: {final_path}")
                
                # Limpar arquivos intermediários (shorts e transform)
                try:
                    shorts_path = Path(self.settings['shorts_cache_dir']) / f"{video_id}.mp4"
                    if shorts_path.exists():
                        shorts_path.unlink()
                        logger.debug(f"🗑️  Cleaned shorts: {video_id}")
                    
                    transform_dir = Path(self.settings['transform_dir'])
                    for file_path in transform_dir.glob(f"{video_id}*.mp4"):
                        file_path.unlink()
                        logger.debug(f"🗑️  Cleaned transform: {file_path.name}")
                except Exception as e:
                    logger.warning(f"⚠️  Cleanup warning for approved video: {e}")
                
                return str(final_path)
            else:
                # Rejeitar: deletar de TODAS as pastas do pipeline
                logger.info(f"❌ Validation failed, cleaning all files: {video_id}")
                tagged_file.unlink()
                logger.info(f"🗑️  Rejected video deleted: {tagged_path}")
                
                # Limpar de todas as pastas (shorts, transform)
                self.cleanup_rejected_video(video_id, job_id)
                
                return None
                
        except Exception as e:
            logger.error(f"❌ Error finalizing validation: {e}", exc_info=True)
            # Tentar deletar em caso de erro para não deixar lixo
            try:
                if tagged_file.exists():
                    tagged_file.unlink()
                    logger.info(f"🗑️  Cleanup: removed {tagged_path}")
                # Limpar tudo em caso de erro também
                self.cleanup_rejected_video(video_id, job_id)
            except:
                pass
            return None
    
    def cleanup_stale_validations(self, job_id: str, max_age_minutes: int = 30):
        """
        Remove arquivos de validação abandonados (órfãos de jobs crashados)
        
        Args:
            job_id: ID do job atual
            max_age_minutes: Idade máxima permitida (default: 30 min)
        """
        import time
        
        validate_dir = Path("data/validate/in_progress")
        if not validate_dir.exists():
            return
        
        current_time = time.time()
        max_age_seconds = max_age_minutes * 60
        
        cleaned = 0
        for file_path in validate_dir.glob("*_PROCESSING_*.mp4"):
            try:
                # Verificar idade do arquivo
                file_age = current_time - file_path.stat().st_mtime
                
                if file_age > max_age_seconds:
                    logger.warning(f"🧹 Cleaning stale validation file: {file_path.name} (age: {file_age/60:.1f} min)")
                    file_path.unlink()
                    cleaned += 1
            except Exception as e:
                logger.error(f"❌ Error cleaning {file_path}: {e}")
        
        if cleaned > 0:
            logger.info(f"🧹 Cleaned {cleaned} stale validation files")
    
    def cleanup_rejected_video(self, video_id: str, job_id: str = None):
        """
        Limpa vídeo rejeitado de TODAS as pastas do pipeline.
        
        Remove:
        - data/raw/shorts/{video_id}.mp4
        - data/transform/videos/{video_id}*.mp4
        - data/validate/in_progress/{job_id}_{video_id}*.mp4
        
        Args:
            video_id: ID do vídeo a ser removido
            job_id: ID do job (opcional, para validate)
        """
        cleaned = 0
        
        try:
            # 1. Remover de shorts
            shorts_path = Path(self.settings['shorts_cache_dir']) / f"{video_id}.mp4"
            if shorts_path.exists():
                shorts_path.unlink()
                logger.info(f"🗑️  Removed from shorts: {video_id}")
                cleaned += 1
            
            # 2. Remover de transform (pode ter múltiplos arquivos: original, _cropped_temp)
            transform_dir = Path(self.settings['transform_dir'])
            for file_path in transform_dir.glob(f"{video_id}*.mp4"):
                file_path.unlink()
                logger.info(f"🗑️  Removed from transform: {file_path.name}")
                cleaned += 1
            
            # 3. Remover de validate (com ou sem job_id)
            validate_dir = Path(self.settings['validate_dir']) / "in_progress"
            if job_id:
                # Buscar por job_id específico
                for file_path in validate_dir.glob(f"{job_id}_{video_id}*.mp4"):
                    file_path.unlink()
                    logger.info(f"🗑️  Removed from validate: {file_path.name}")
                    cleaned += 1
            else:
                # Buscar qualquer arquivo com esse video_id
                for file_path in validate_dir.glob(f"*_{video_id}*.mp4"):
                    file_path.unlink()
                    logger.info(f"🗑️  Removed from validate: {file_path.name}")
                    cleaned += 1
            
            if cleaned > 0:
                logger.info(f"🧹✅ Cleaned {cleaned} files for rejected video: {video_id}")
        
        except Exception as e:
            logger.error(f"❌ Error cleaning rejected video {video_id}: {e}")
    
    def cleanup_orphaned_files(self, max_age_minutes: int = 30):
        """
        Limpa arquivos órfãos de TODAS as pastas do pipeline.
        
        Remove arquivos com idade > max_age_minutes de:
        - data/raw/shorts/*.mp4 (exceto metadata.json)
        - data/transform/videos/*.mp4
        - data/validate/in_progress/*.mp4
        
        Args:
            max_age_minutes: Idade máxima em minutos (default: 30)
        """
        from datetime import datetime, timedelta
        import time
        
        now = time.time()
        max_age_seconds = max_age_minutes * 60
        cleaned_total = 0
        
        # Pastas a limpar
        folders = {
            'shorts': Path(self.settings['shorts_cache_dir']),
            'transform': Path(self.settings['transform_dir']),
            'validate': Path(self.settings['validate_dir']) / 'in_progress'
        }
        
        for folder_name, folder_path in folders.items():
            if not folder_path.exists():
                continue
            
            cleaned = 0
            try:
                for file_path in folder_path.glob("*.mp4"):
                    # Calcular idade do arquivo
                    file_age = now - file_path.stat().st_mtime
                    
                    if file_age > max_age_seconds:
                        file_age_min = file_age / 60
                        logger.warning(f"🧹 Cleaning orphaned file in {folder_name}: {file_path.name} (age: {file_age_min:.1f} min)")
                        file_path.unlink()
                        cleaned += 1
                        cleaned_total += 1
            except Exception as e:
                logger.error(f"❌ Error cleaning {folder_name}: {e}")
            
            if cleaned > 0:
                logger.info(f"🧹 Cleaned {cleaned} files from {folder_name}/")
        
        if cleaned_total > 0:
            logger.info(f"🧹✅ Total orphaned files cleaned: {cleaned_total} (age > {max_age_minutes} min)")
        else:
            logger.debug(f"✅ No orphaned files found (age > {max_age_minutes} min)")
    
    def cleanup_job_files(self, job_id: str):
        """
        Limpa TODOS os arquivos relacionados a um job específico.
        
        CRITICAL FIX: Este método é chamado no finally do pipeline para garantir
        cleanup mesmo em caso de falha/timeout/cancelamento.
        
        Remove arquivos com job_id em:
        - data/raw/shorts/{job_id}_*.mp4
        - data/transform/videos/{job_id}_*.mp4
        - data/validate/in_progress/{job_id}_*.mp4
        
        Args:
            job_id: ID do job a limpar
        """
        from pathlib import Path
        
        cleaned_total = 0
        
        # Pastas a limpar
        folders = {
            'shorts': Path(self.settings['shorts_cache_dir']),
            'transform': Path(self.settings['transform_dir']),
            'validate': Path(self.settings['validate_dir']) / 'in_progress'
        }
        
        logger.info(f"🧹 Starting cleanup for job {job_id} across all pipeline stages...")
        
        for folder_name, folder_path in folders.items():
            if not folder_path.exists():
                logger.debug(f"⏭️  Skipping {folder_name} (folder doesn't exist)")
                continue
            
            cleaned = 0
            try:
                # Buscar arquivos com job_id no nome
                pattern = f"{job_id}_*.mp4"
                for file_path in folder_path.glob(pattern):
                    logger.debug(f"🗑️  Removing {folder_name}/{file_path.name}")
                    file_path.unlink()
                    cleaned += 1
                    cleaned_total += 1
                    
                if cleaned > 0:
                    logger.info(f"🧹 Cleaned {cleaned} files from {folder_name}/ for job {job_id}")
            except Exception as e:
                logger.error(f"❌ Error cleaning {folder_name} for job {job_id}: {e}")
        
        if cleaned_total > 0:
            logger.info(f"🧹✅ Job {job_id} cleanup complete: {cleaned_total} files removed")
        else:
            logger.debug(f"✅ No files found for job {job_id} (already cleaned or no files created)")
    
    async def download_shorts(self, query: str, max_count: int = 50, progress_callback=None) -> List[Dict]:
        """
        1. DOWNLOAD: Buscar e baixar shorts via youtube-search + video-downloader
        
        SMART REUSE: Verifica vídeos existentes em data/raw/shorts/ antes de baixar.
        - Se >= max_count vídeos existem → Reutiliza todos, pula download
        - Se < max_count vídeos existem → Baixa complemento para atingir max_count
        
        Args:
            query: Query de busca
            max_count: Máximo de shorts para baixar
            progress_callback: Callback opcional p/ atualizar progresso (async)
        
        Returns:
            Lista de shorts baixados/reutilizados com metadados
        """
        logger.info(f"📥 DOWNLOAD: Buscando shorts para '{query}' (max: {max_count})")
        
        # SMART REUSE: Verificar vídeos existentes
        shorts_dir = Path(self.settings['shorts_cache_dir'])
        existing_videos = list(shorts_dir.glob("*.mp4")) if shorts_dir.exists() else []
        existing_count = len(existing_videos)
        
        logger.info(f"📦 Found {existing_count} existing videos in {shorts_dir}")
        
        # Se já temos vídeos suficientes, reutilizar todos
        if existing_count >= max_count:
            logger.info(f"♻️  REUSING {existing_count} existing videos (>= {max_count} requested)")
            logger.info(f"⏭️  SKIPPING download phase (videos already available)")
            
            downloaded = []
            for video_path in existing_videos:
                video_id = video_path.stem  # Filename without extension
                downloaded.append({
                    'video_id': video_id,
                    'title': f'Reused: {video_id}',
                    'raw_path': str(video_path),
                    'downloaded_at': datetime.utcnow().isoformat(),
                    'reused': True
                })
            
            # Callback de progresso (pula para 50% = download completo)
            if progress_callback:
                try:
                    await progress_callback(
                        progress=50.0,
                        metadata={
                            'step': 'download_skipped_reused',
                            'downloaded': existing_count,
                            'total': existing_count,
                            'reused': True
                        }
                    )
                except Exception as e:
                    logger.warning(f"⚠️  Callback error: {e}")
            
            logger.info(f"📥 DOWNLOAD SKIPPED: {existing_count} videos reused")
            return downloaded
        
        # Se temos alguns vídeos, calcular quantos faltam
        videos_needed = max_count - existing_count
        logger.info(f"📥 Need to download {videos_needed} more videos ({existing_count} existing + {videos_needed} new = {max_count} total)")
        
        downloaded = []
        
        # COMPLEMENTO: Adicionar vídeos existentes à lista de downloads
        for video_path in existing_videos:
            video_id = video_path.stem
            downloaded.append({
                'video_id': video_id,
                'title': f'Existing: {video_id}',
                'raw_path': str(video_path),
                'downloaded_at': datetime.utcnow().isoformat(),
                'reused': True
            })
        
        logger.info(f"📦 Starting with {len(downloaded)} reused videos")
        
        try:
            # 1. Buscar shorts via youtube-search (ajustado para videos_needed)
            youtube_search_url = self.settings.get('youtube_search_url')
            async with httpx.AsyncClient(timeout=120.0) as client:
                # 1.1. Criar job de busca
                response = await client.post(
                    f"{youtube_search_url}/search/shorts",
                    params={
                        "query": query,
                        "max_results": videos_needed  # Buscar apenas o que falta
                    }
                )
                response.raise_for_status()
                job_data = response.json()
                job_id = job_data.get('id')
                
                logger.info(f"   📋 Job criado: {job_id} (buscando {videos_needed} novos vídeos)")
                
                # 1.2. Aguardar job completar
                wait_response = await client.get(
                    f"{youtube_search_url}/jobs/{job_id}/wait",
                    timeout=90.0
                )
                wait_response.raise_for_status()
                completed_job = wait_response.json()
                
                # 1.3. Extrair resultados
                shorts = completed_job.get('result', {}).get('results', [])
            
            logger.info(f"   ✅ {len(shorts)} novos shorts encontrados")

            # 1.4. Deduplicar por video_id para evitar contagem inflada e sobrescrita
            unique_shorts = []
            seen_video_ids = set()
            duplicated_count = 0

            for short in shorts:
                video_id = short.get('video_id')
                if not video_id:
                    continue

                if video_id in seen_video_ids:
                    duplicated_count += 1
                    continue

                seen_video_ids.add(video_id)
                unique_shorts.append(short)

            if duplicated_count > 0:
                logger.info(
                    f"   🔁 Duplicados removidos: {duplicated_count} "
                    f"(únicos: {len(unique_shorts)})"
                )
            
            # 2. Baixar cada short via video-downloader (assíncrono)
            video_downloader_url = self.settings.get('video_downloader_url')
            
            for i, short in enumerate(unique_shorts, 1):
                video_id = short.get('video_id')

                # Pular vídeos já aprovados em execuções anteriores
                approved_video_path = Path(f"data/approved/videos/{video_id}.mp4")
                if approved_video_path.exists():
                    logger.info(f"   🟢 [{i}/{len(unique_shorts)}] {video_id}: JÁ APROVADO (skip)")
                    continue
                
                # Verificar status ANTES de baixar (blacklist = rejected)
                if self.status_store.is_rejected(video_id):  # Sync call
                    logger.info(f"   ⚫ [{i}/{len(unique_shorts)}] {video_id}: REJECTED (skip)")
                    continue
                
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        # 2.1. Criar job de download
                        response = await client.post(
                            f"{video_downloader_url}/jobs",
                            json={
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "quality": "best"
                            }
                        )
                        response.raise_for_status()
                        job = response.json()
                        job_id = job.get('id')
                        
                        logger.info(f"   📦 [{i}/{len(unique_shorts)}] {video_id}: Job {job_id} criado")
                        
                        # 2.2. Aguardar job completar (polling)
                        max_retries = 30  # 30 tentativas × 2s = 60s timeout 
                        for retry in range(max_retries):
                            await asyncio.sleep(2)
                            status_response = await client.get(
                                f"{video_downloader_url}/jobs/{job_id}"
                            )
                            status_response.raise_for_status()
                            job_status = status_response.json()
                            
                            if job_status.get('status') == 'completed':
                                file_path = job_status.get('file_path')
                                logger.info(f"   ✅ [{i}/{len(unique_shorts)}] {video_id}: Download concluído ({file_path})")
                                break
                            elif job_status.get('status') == 'failed':
                                error_msg = job_status.get('error_message', 'Unknown error')
                                raise Exception(f"Download failed: {error_msg}")
                        else:
                            raise Exception("Download timeout (60s)")
                        
                        # 2.3. Baixar arquivo via GET /jobs/{job_id}/download
                        download_response = await client.get(
                            f"{video_downloader_url}/jobs/{job_id}/download",
                            timeout=60.0
                        )
                        download_response.raise_for_status()
                    
                    # 2.4. Salvar em data/raw/shorts/ com extensão real
                    file_ext = ".mp4"
                    if file_path:
                        parsed_ext = Path(file_path).suffix
                        if parsed_ext:
                            file_ext = parsed_ext

                    video_path = Path(f"data/raw/shorts/{video_id}{file_ext}")
                    video_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(video_path, 'wb') as f:
                        f.write(download_response.content)
                    
                    logger.info(f"   💾 [{i}/{len(unique_shorts)}] {video_id}: Salvo em {video_path}")
                    
                    downloaded.append({
                        'video_id': video_id,
                        'title': short.get('title'),
                        'raw_path': str(video_path),
                        'downloaded_at': datetime.utcnow().isoformat()
                    })
                    
                    logger.info(f"   ✅ [{i}/{len(unique_shorts)}] {video_id}: Downloaded")
                    
                    # Chamar callback de progresso se fornecido
                    if progress_callback:
                        progress_pct = 10 + (i / len(unique_shorts) * 40)  # 10-50%
                        try:
                            await progress_callback(
                                progress=progress_pct,
                                metadata={
                                    'step': 'downloading_shorts',
                                    'downloaded': len(downloaded),
                                    'total': len(unique_shorts),
                                    'current_video': video_id
                                }
                            )
                        except Exception as e:
                            logger.warning(f"⚠️  Callback error: {e}")
                    
                except Exception as e:
                    logger.error(f"   ❌ [{i}/{len(unique_shorts)}] {video_id}: Download failed - {e}")
                    continue

                logger.info(f"📥 DOWNLOAD COMPLETO: {len(downloaded)}/{len(unique_shorts)} baixados")
            return downloaded
            
        except Exception as e:
            logger.error(f"❌ Erro no download: {e}", exc_info=True)
            return []
    
    def transform_video(self, video_id: str, raw_path: str) -> Optional[str]:
        """
        2. TRANSFORM: Converter vídeo para H264 compatível
        
        Args:
            video_id: ID do vídeo
            raw_path: Caminho do vídeo bruto (data/raw/)
        
        Returns:
            Caminho do vídeo transformado (data/transform/) ou None se falhou
        """
        logger.info(f"🔄 TRANSFORM: Convertendo {video_id} para H264")
        
        try:
            raw_video = Path(raw_path)
            if not raw_video.exists():
                logger.error(f"   ❌ Arquivo não encontrado: {raw_path}")
                return None
            
            # Caminho de saída
            transform_path = Path(f"data/transform/videos/{video_id}.mp4")
            
            # Conversão FFmpeg para H264
            cmd = [
                'ffmpeg',
                '-i', str(raw_video),
                '-c:v', 'libx264',  # Codec H264
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',  # Sobrescrever
                str(transform_path)
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120
            )
            
            if result.returncode == 0 and transform_path.exists():
                logger.info(f"   ✅ Convertido: {transform_path}")
                return str(transform_path)
            else:
                logger.error(f"   ❌ Conversão falhou (code {result.returncode})")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro na conversão: {e}", exc_info=True)
            return None
    
    async def crop_video_permanent(self, video_id: str, transform_path: str, aspect_ratio: str = "9:16", crop_position: str = "center") -> Optional[str]:
        """
        2.5 CROP PERMANENTE: Cropar vídeo para aspect ratio ANTES da validação
        
        CRÍTICO: Este crop é PERMANENTE. O vídeo cropado substituirá o transform
        e será o que vai para approved/ se passar na validação OCR.
        
        Args:
            video_id: ID do vídeo
            transform_path: Path do vídeo H264 transformado
            aspect_ratio: Aspect ratio alvo ("9:16", "16:9", "1:1", "4:5")
            crop_position: Posição do crop ("center", "top", "bottom")
        
        Returns:
            Path do vídeo cropado (substitui o original) ou None se falhou
        """
        logger.info(f"✂️ CROP: Aplicando crop {aspect_ratio} PERMANENTE em {video_id}")
        
        cropped_temp = None  # Inicializar antes do try
        try:
            # Path temporário para o crop
            cropped_temp = Path(f"data/transform/videos/{video_id}_cropped_temp.mp4")
            
            # Aplicar crop usando VideoBuilder
            await self.video_builder.crop_video_for_validation(
                video_path=transform_path,
                output_path=str(cropped_temp),
                aspect_ratio=aspect_ratio,
                crop_position=crop_position
            )
            
            # Verificar se crop foi bem-sucedido
            if not cropped_temp.exists():
                logger.error(f"   ❌ Crop falhou: arquivo não criado")
                return None
            
            # SUBSTITUIR o arquivo original pelo cropado
            transform_file = Path(transform_path)
            if transform_file.exists():
                transform_file.unlink()  # Deletar original
            
            cropped_temp.rename(transform_file)  # Renomear cropado para original
            
            logger.info(f"   ✅ Cropado permanentemente: {transform_path} ({aspect_ratio})")
            return str(transform_file)
            
        except Exception as e:
            logger.error(f"❌ Erro no crop permanente: {e}", exc_info=True)
            # Limpar arquivo temp se existir
            if cropped_temp and cropped_temp.exists():
                cropped_temp.unlink()
            return None
    
    async def validate_video(self, video_id: str, validation_path: str, aspect_ratio: str = "9:16", crop_position: str = "center") -> Tuple[bool, Dict]:
        """
        3. VALIDATE: Detectar texto/legendas nos frames do vídeo (OCR 100%)
        
        ⚠️ IMPORTANTE: 
        - Vídeo deve estar em data/validate/in_progress/ (com tag _PROCESSING_)
        - Vídeo já foi cropado permanentemente para aspect ratio correto
        - Validação é APENAS OCR nos frames (não verifica metadados do container)
        
        Args:
            video_id: ID do vídeo  
            validation_path: Caminho do vídeo em data/validate/in_progress/{job_id}_{video_id}_PROCESSING_.mp4
            aspect_ratio: Aspect ratio do vídeo (informativo)
            crop_position: Posição do crop (informativo)
        
        Returns:
            (aprovado, metadados)
            - aprovado: True se SEM texto nos frames, False se COM texto
            - metadados: Detalhes da detecção OCR
        """
        logger.info(f"🔍 VALIDATE: Detectando texto em {video_id} (OCR 100% frames)")
        
        try:
            # OCR nos frames do vídeo
            has_text, confidence, sample_text, metadata = self.detector.detect(validation_path)
            
            # 🚨 CRÍTICO: Rejeitar se nenhum frame foi processado (vídeo corrupto)
            frames_processed = metadata.get('frames_processed', 0)
            if frames_processed == 0:
                logger.error(f"❌ ZERO FRAMES PROCESSED: {video_id} - vídeo corrupto ou ilegível")
                return False, {
                    'video_id': video_id,
                    'error': 'zero_frames_processed',
                    'frames_processed': 0,
                    'reason': 'Vídeo corrompido ou ilegível - nenhum frame pôde ser processado'
                }
            
            # Aprovado = SEM legendas
            aprovado = not has_text
            
            result_meta = {
                'video_id': video_id,
                'has_text': has_text,
                'confidence': confidence,
                'sample_text': sample_text,
                'frames_processed': metadata.get('frames_processed', 0),
                'frames_with_text': metadata.get('frames_with_text', 0),
                'detection_ratio': metadata.get('detection_ratio', 0.0),
                'aspect_ratio': aspect_ratio,
                'crop_position': crop_position,
                'validated_at': datetime.utcnow().isoformat()
            }
            
            if aprovado:
                logger.info(f"   ✅ APROVADO: {video_id} (SEM legendas, conf: {confidence:.2f})")
            else:
                logger.info(f"   ❌ REPROVADO: {video_id} (COM legendas, conf: {confidence:.2f})")
                logger.info(f"      Texto detectado: '{sample_text[:100]}'")
            
            return aprovado, result_meta
            
        except Exception as e:
            logger.error(f"❌ Erro na validação: {e}", exc_info=True)
            # Em caso de erro, rejeitar por segurança
            return False, {'error': str(e), 'video_id': video_id}
    
    async def approve_video(self, video_id: str, transform_path: str, metadata: Dict):
        """
        4a. APPROVE: Mover vídeo aprovado para data/approved/ e registrar no banco
        
        Args:
            video_id: ID do vídeo
            transform_path: Caminho do vídeo transformado
            metadata: Metadados da validação
            
        Returns:
            Caminho do vídeo aprovado ou None se falhou
        """
        logger.info(f"✅ APPROVE: Movendo {video_id} para approved/")
        
        try:
            transform_video = Path(transform_path)
            approved_path = Path(f"data/approved/videos/{video_id}.mp4")
            
            # Mover (não copiar) para economizar espaço
            if transform_video.exists():
                transform_video.rename(approved_path)
                logger.info(f"   ✅ Movido: {approved_path}")
            
            # Registrar no banco de APROVADOS
            self.status_store.add_approved(
                video_id=video_id,
                title=metadata.get('title'),
                url=f"https://www.youtube.com/watch?v={video_id}",
                file_path=str(approved_path),
                metadata=metadata
            )
            
            # Limpar pastas anteriores
            await self._cleanup_previous_stages(video_id)
            
            return str(approved_path)
            
        except Exception as e:
            logger.error(f"❌ Erro ao aprovar: {e}", exc_info=True)
            return None
    
    async def reject_video(self, video_id: str, metadata: Dict):
        """
        4b. REJECT: Adicionar aos reprovados e limpar
        
        Args:
            video_id: ID do vídeo
            metadata: Metadados da validação (motivo da rejeição)
        """
        logger.info(f"❌ REJECT: Adicionando {video_id} aos reprovados")
        
        try:
            # Adicionar à lista de REPROVADOS
            confidence = metadata.get('confidence', 0.0)
            reason = "embedded_subtitles"
            self.status_store.add_rejected(  # Sync call
                video_id=video_id,
                reason=reason,
                confidence=confidence,
                title=metadata.get('title'),
                url=f"https://www.youtube.com/watch?v={video_id}",
                metadata=metadata
            )
            
            logger.info(f"   ⚫ Rejected: {video_id} ({reason}, conf: {confidence:.2f})")
            
            # Limpar todas as pastas
            await self._cleanup_all_stages(video_id)
            
        except Exception as e:
            logger.error(f"❌ Erro ao rejeitar: {e}", exc_info=True)
    
    async def _cleanup_previous_stages(self, video_id: str):
        """
        5. CLEANUP: Remover vídeo de pastas anteriores (aprovado)
        
        Remove de:
        - data/raw/shorts/
        - data/transform/videos/
        """
        logger.info(f"🧹 CLEANUP: Removendo {video_id} de pastas anteriores")
        
        raw_dir = Path("data/raw/shorts")
        transform_dir = Path("data/transform/videos")

        # Remove todas as variantes de extensão no raw (ex: .mp4, .webm, .mkv)
        for path in raw_dir.glob(f"{video_id}.*"):
            if path.is_file():
                path.unlink()
                logger.info(f"   🗑️  Removido: {path}")

        # Remove transformado (normalmente .mp4)
        for path in transform_dir.glob(f"{video_id}.*"):
            if path.is_file():
                path.unlink()
                logger.info(f"   🗑️  Removido: {path}")
    
    async def _cleanup_all_stages(self, video_id: str):
        """
        5. CLEANUP: Remover vídeo de TODAS as pastas (rejeitado)
        
        Remove de:
        - data/raw/shorts/
        - data/transform/videos/
        - data/validate/in_progress/
        """
        logger.info(f"🧹 CLEANUP COMPLETO: Removendo {video_id} de todas as pastas")
        
        stage_dirs = [
            Path("data/raw/shorts"),
            Path("data/transform/videos"),
            Path("data/validate/in_progress"),
        ]

        for stage_dir in stage_dirs:
            for path in stage_dir.glob(f"{video_id}.*"):
                if path.is_file():
                    path.unlink()
                    logger.info(f"   🗑️  Removido: {path}")
    
    async def process_pipeline(self, query: str, max_shorts: int = 50, progress_callback=None) -> Dict:
        """
        Pipeline completo: Download → Transform → Validate → Approve/Reject
        
        Args:
            query: Query de busca
            max_shorts: Máximo de shorts para processar
            progress_callback: Callback opcional p/ atualizar progresso (async)
        
        Returns:
            Estatísticas do pipeline
        """
        logger.info(f"🚀 PIPELINE INICIADO: '{query}' (max: {max_shorts})")
        
        stats = {
            'query': query,
            'downloaded': 0,
            'transformed': 0,
            'approved': 0,
            'rejected': 0,
            'errors': 0,
            'start_time': datetime.utcnow().isoformat()
        }
        
        # 1. DOWNLOAD (10-50% do progresso)
        shorts = await self.download_shorts(query, max_shorts, progress_callback=progress_callback)
        stats['downloaded'] = len(shorts)
        
        # Callback: download completo
        if progress_callback:
            try:
                await progress_callback(progress=50.0, metadata={'step': 'download_completed', 'downloaded': len(shorts)})
            except Exception as e:
                logger.warning(f"⚠️  Callback error: {e}")
        
        if not shorts:
            logger.warning("⚠️  Nenhum short baixado. Pipeline finalizado.")
            stats['end_time'] = datetime.utcnow().isoformat()
            return stats
        
        # 2. TRANSFORM + 3. VALIDATE + 4. APPROVE/REJECT
        processed_video_ids = set()

        for short in shorts:
            video_id = short['video_id']
            raw_path = short['raw_path']

            if video_id in processed_video_ids:
                logger.info(f"   🔁 DUPLICADO no pipeline final (skip): {video_id}")
                continue

            processed_video_ids.add(video_id)
            
            try:
                # 2. Transform (H264)
                transform_path = self.transform_video(video_id, raw_path)
                if not transform_path:
                    stats['errors'] += 1
                    await self._cleanup_all_stages(video_id)
                    continue
                stats['transformed'] += 1
                
                # 2.5 CROP PERMANENTE (9:16) - CRÍTICO!
                # O vídeo DEVE estar cropado ANTES da validação
                # Este é o vídeo que irá para approved/ se passar no OCR
                cropped_path = await self.crop_video_permanent(
                    video_id=video_id,
                    transform_path=transform_path,
                    aspect_ratio="9:16",
                    crop_position="center"
                )
                if not cropped_path:
                    logger.error(f"   ❌ Crop permanente falhou: {video_id}")
                    stats['errors'] += 1
                    await self._cleanup_all_stages(video_id)
                    continue
                
                # 3. Validate (no vídeo JÁ CROPADO)
                # IMPORTANTE: validate_video ainda cria um crop temporário
                # mas agora é redundante - o vídeo já está cropado
                # Vamos passar cropped_path aqui
                aprovado, metadata = await self.validate_video(video_id, cropped_path)
                
                # 4. Approve ou Reject
                if aprovado:
                    # Move o vídeo JÁ CROPADO para approved/
                    await self.approve_video(video_id, cropped_path, metadata)
                    stats['approved'] += 1
                    
                    # Callback: progresso (50-100%)
                    if progress_callback:
                        processed = stats['approved'] + stats['rejected']
                        progress_pct = 50 + (processed / len(shorts) * 50)
                        try:
                            await progress_callback(
                                progress=progress_pct,
                                metadata={
                                    'step': 'processing_videos',
                                    'processed': processed,
                                    'total': len(shorts),
                                    'approved': stats['approved'],
                                    'rejected': stats['rejected']
                                }
                            )
                        except Exception as e:
                            logger.warning(f"⚠️  Callback error: {e}")
                else:
                    await self.reject_video(video_id, metadata)
                    stats['rejected'] += 1
                    
                    # Callback: progresso (50-100%)
                    if progress_callback:
                        processed = stats['approved'] + stats['rejected']
                        progress_pct = 50 + (processed / len(shorts) * 50)
                        try:
                            await progress_callback(
                                progress=progress_pct,
                                metadata={
                                    'step': 'processing_videos',
                                    'processed': processed,
                                    'total': len(shorts),
                                    'approved': stats['approved'],
                                    'rejected': stats['rejected']
                                }
                            )
                        except Exception as e:
                            logger.warning(f"⚠️  Callback error: {e}")
                
            except Exception as e:
                logger.error(f"❌ Erro processando {video_id}: {e}", exc_info=True)
                stats['errors'] += 1
                await self._cleanup_all_stages(video_id)
                continue
        
        stats['end_time'] = datetime.utcnow().isoformat()
        
        logger.info(f"🎉 PIPELINE COMPLETO:")
        logger.info(f"   📥 Downloaded: {stats['downloaded']}")
        logger.info(f"   🔄 Transformed: {stats['transformed']}")
        logger.info(f"   ✅ Approved: {stats['approved']}")
        logger.info(f"   ❌ Rejected: {stats['rejected']}")
        logger.info(f"   ⚠️  Errors: {stats['errors']}")
        
        return stats
