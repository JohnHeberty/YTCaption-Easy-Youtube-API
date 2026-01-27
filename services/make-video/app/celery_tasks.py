"""
Celery Tasks for Make-Video Service

Tasks de processamento assíncrono para criação de vídeos.
"""

import os
import asyncio
import logging
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

from celery import shared_task

from .celery_config import celery_app
from .config import get_settings
from .models import Job, JobStatus, ShortInfo, JobResult
from .redis_store import RedisJobStore
from .api_client import MicroservicesClient
from .video_builder import VideoBuilder
from .shorts_manager import ShortsCache
from .subtitle_generator import SubtitleGenerator
from .exceptions import (
    MakeVideoException,
    AudioProcessingException,
    VideoProcessingException,
    MicroserviceException
)

logger = logging.getLogger(__name__)

# Global instances (will be initialized per worker)
redis_store = None
api_client = None
video_builder = None
shorts_cache = None
subtitle_gen = None


def get_instances():
    """Inicializa instâncias globais se necessário"""
    global redis_store, api_client, video_builder, shorts_cache, subtitle_gen
    
    if redis_store is None:
        settings = get_settings()
        redis_store = RedisJobStore(redis_url=settings['redis_url'])
        
        api_client = MicroservicesClient(
            youtube_search_url=settings['youtube_search_url'],
            video_downloader_url=settings['video_downloader_url'],
            audio_transcriber_url=settings['audio_transcriber_url']
        )
        
        video_builder = VideoBuilder(
            temp_dir=settings['temp_dir'],
            output_dir=settings['output_dir']
        )
        
        shorts_cache = ShortsCache(
            cache_dir=settings['shorts_cache_dir']
        )
        
        subtitle_gen = SubtitleGenerator()
    
    return redis_store, api_client, video_builder, shorts_cache, subtitle_gen


async def update_job_status(job_id: str, status: JobStatus, 
                           progress: float = None, 
                           stage_updates: Dict = None,
                           error: Dict = None):
    """Atualiza status do job no Redis"""
    store, _, _, _, _ = get_instances()
    
    job = await store.get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return
    
    job.status = status
    job.updated_at = datetime.utcnow()
    
    if progress is not None:
        job.progress = progress
    
    if stage_updates:
        for stage_name, stage_info in stage_updates.items():
            if stage_name not in job.stages:
                job.stages[stage_name] = stage_info
            else:
                job.stages[stage_name].update(stage_info)
    
    if error:
        job.error = error
    
    if status == JobStatus.COMPLETED:
        job.completed_at = datetime.utcnow()
        job.expires_at = job.completed_at + timedelta(hours=24)
    
    await store.save_job(job)


@shared_task(bind=True, name='app.celery_tasks.process_make_video')
def process_make_video(self, job_id: str):
    """
    Task principal: Processa criação de vídeo completa
    
    Etapas:
    1. Analisar áudio
    2. Buscar shorts
    3. Baixar shorts
    4. Selecionar aleatoriamente
    5. Montar vídeo
    6. Gerar legendas
    7. Composição final
    """
    logger.info(f"🎬 Starting make-video job: {job_id}")
    
    try:
        # Executar em event loop assíncrono
        asyncio.run(_process_make_video_async(job_id))
        
    except Exception as e:
        logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)
        
        # Atualizar job com erro
        asyncio.run(update_job_status(
            job_id,
            JobStatus.FAILED,
            progress=0.0,
            error={
                "message": str(e),
                "type": type(e).__name__,
                "stage": "unknown"
            }
        ))


async def _process_make_video_async(job_id: str):
    """Processamento assíncrono do vídeo"""
    
    store, api_client, video_builder, shorts_cache, subtitle_gen = get_instances()
    settings = get_settings()
    
    # Carregar job
    job = await store.get_job(job_id)
    if not job:
        raise MakeVideoException(f"Job {job_id} not found")
    
    try:
        # Etapa 1: Analisar áudio
        logger.info(f"📊 [1/7] Analyzing audio...")
        await update_job_status(job_id, JobStatus.ANALYZING_AUDIO, progress=5.0)
        
        audio_path = Path(settings['audio_upload_dir']) / job_id / "audio"
        if not audio_path.exists():
            # Procurar por extensões comuns
            for ext in ['.mp3', '.wav', '.m4a', '.ogg']:
                test_path = audio_path.parent / f"audio{ext}"
                if test_path.exists():
                    audio_path = test_path
                    break
        
        if not audio_path.exists():
            raise AudioProcessingException(f"Audio file not found: {audio_path}")
        
        audio_duration = await video_builder.get_audio_duration(str(audio_path))
        target_duration = audio_duration + 5.0  # +5s sobra
        
        # Atualizar job com duração do áudio
        job.audio_duration = audio_duration
        job.target_video_duration = target_duration
        await store.save_job(job)
        
        logger.info(f"🎵 Audio: {audio_duration:.1f}s → Target: {target_duration:.1f}s")
        
        # Etapa 2: Buscar shorts
        logger.info(f"🔍 [2/7] Fetching shorts...")
        await update_job_status(job_id, JobStatus.FETCHING_SHORTS, progress=15.0)
        
        shorts_list = await api_client.search_shorts(job.query, job.max_shorts)
        logger.info(f"✅ Found {len(shorts_list)} shorts")
        
        if not shorts_list:
            raise VideoProcessingException(f"No shorts found for query: {job.query}")
        
        # Etapa 3: Baixar shorts
        logger.info(f"⬇️ [3/7] Downloading shorts...")
        await update_job_status(job_id, JobStatus.DOWNLOADING_SHORTS, progress=25.0)
        
        downloaded_shorts = []
        cache_hits = 0
        
        for i, short in enumerate(shorts_list):
            video_id = short['video_id']
            
            # Verificar cache
            cached = shorts_cache.get(video_id)
            if cached:
                downloaded_shorts.append(cached)
                cache_hits += 1
                logger.info(f"💾 Cache HIT: {video_id} ({i+1}/{len(shorts_list)})")
            else:
                # Baixar via API
                output_path = Path(settings['shorts_cache_dir']) / f"{video_id}.mp4"
                try:
                    metadata = await api_client.download_video(video_id, str(output_path))
                    
                    short_info = {
                        'video_id': video_id,
                        'duration_seconds': short.get('duration_seconds', 30),
                        'file_path': str(output_path),
                        'resolution': metadata.get('resolution', '1080x1920'),
                        'title': short.get('title', ''),
                    }
                    
                    shorts_cache.add(video_id, str(output_path), short_info)
                    downloaded_shorts.append(short_info)
                    
                    logger.info(f"✅ Downloaded: {video_id} ({i+1}/{len(shorts_list)})")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to download {video_id}: {e}")
                    continue
            
            # Atualizar progresso
            progress = 25.0 + (45.0 * (i + 1) / len(shorts_list))
            await update_job_status(job_id, JobStatus.DOWNLOADING_SHORTS, progress=progress)
        
        logger.info(f"📦 Downloads: {len(downloaded_shorts)} total ({cache_hits} from cache)")
        
        if not downloaded_shorts:
            raise VideoProcessingException("No shorts could be downloaded")
        
        # Etapa 4: Selecionar shorts aleatoriamente
        logger.info(f"🎲 [4/7] Selecting shorts randomly...")
        await update_job_status(job_id, JobStatus.SELECTING_SHORTS, progress=70.0)
        
        random.shuffle(downloaded_shorts)
        
        selected_shorts = []
        total_duration = 0.0
        
        for short in downloaded_shorts:
            if total_duration >= target_duration:
                break
            selected_shorts.append(short)
            total_duration += short['duration_seconds']
        
        logger.info(f"🎯 Selected {len(selected_shorts)} shorts ({total_duration:.1f}s)")
        
        if not selected_shorts:
            raise VideoProcessingException("No shorts available for video creation")
        
        # Etapa 5: Montar vídeo (sem áudio)
        logger.info(f"🎬 [5/7] Assembling video...")
        await update_job_status(job_id, JobStatus.ASSEMBLING_VIDEO, progress=75.0)
        
        video_files = [s['file_path'] for s in selected_shorts]
        temp_video_path = Path(settings['temp_dir']) / job_id / "video_no_audio.mp4"
        temp_video_path.parent.mkdir(parents=True, exist_ok=True)
        
        await video_builder.concatenate_videos(
            video_files=video_files,
            output_path=str(temp_video_path),
            aspect_ratio=job.aspect_ratio,
            crop_position=job.crop_position,
            remove_audio=True
        )
        
        logger.info(f"✅ Video assembled: {temp_video_path}")
        
        # Etapa 6: Gerar legendas
        logger.info(f"📝 [6/7] Generating subtitles...")
        await update_job_status(job_id, JobStatus.GENERATING_SUBTITLES, progress=80.0)
        
        segments = await api_client.transcribe_audio(str(audio_path), job.subtitle_language)
        
        subtitle_path = Path(settings['temp_dir']) / job_id / "subtitles.srt"
        subtitle_gen.segments_to_srt(segments, str(subtitle_path))
        
        logger.info(f"✅ Subtitles generated: {len(segments)} segments")
        
        # Etapa 7: Composição final
        logger.info(f"🎨 [7/7] Final composition...")
        await update_job_status(job_id, JobStatus.FINAL_COMPOSITION, progress=85.0)
        
        # Adicionar áudio
        video_with_audio_path = Path(settings['temp_dir']) / job_id / "video_with_audio.mp4"
        await video_builder.add_audio(
            video_path=str(temp_video_path),
            audio_path=str(audio_path),
            output_path=str(video_with_audio_path)
        )
        
        logger.info(f"✅ Audio added")
        
        # Burn-in legendas
        final_video_path = Path(settings['output_dir']) / f"{job_id}_final.mp4"
        await video_builder.burn_subtitles(
            video_path=str(video_with_audio_path),
            subtitle_path=str(subtitle_path),
            output_path=str(final_video_path),
            style=job.subtitle_style
        )
        
        logger.info(f"✅ Subtitles burned")
        
        # Obter informações do vídeo final
        video_info = await video_builder.get_video_info(str(final_video_path))
        file_size = final_video_path.stat().st_size
        
        # Criar resultado
        result = JobResult(
            video_url=f"/download/{job_id}",
            video_file=final_video_path.name,
            file_size=file_size,
            file_size_mb=round(file_size / (1024 * 1024), 2),
            duration=video_info['duration'],
            resolution=video_info['resolution'],
            aspect_ratio=job.aspect_ratio,
            fps=int(video_info['fps']),
            shorts_used=len(selected_shorts),
            shorts_list=[
                ShortInfo(
                    video_id=s['video_id'],
                    duration_seconds=s['duration_seconds'],
                    file_path=s['file_path'],
                    position_in_video=sum(selected_shorts[j]['duration_seconds'] 
                                        for j in range(i))
                )
                for i, s in enumerate(selected_shorts)
            ],
            subtitle_segments=len(segments),
            processing_time=(datetime.utcnow() - job.created_at).total_seconds()
        )
        
        # Atualizar job como completo
        job.result = result
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.completed_at = datetime.utcnow()
        job.expires_at = job.completed_at + timedelta(hours=24)
        await store.save_job(job)
        
        logger.info(f"🎉 Job {job_id} completed successfully!")
        logger.info(f"   ├─ Duration: {result.duration:.1f}s")
        logger.info(f"   ├─ Size: {result.file_size_mb}MB")
        logger.info(f"   ├─ Shorts used: {result.shorts_used}")
        logger.info(f"   └─ Processing time: {result.processing_time:.1f}s")
        
    except MakeVideoException as e:
        logger.error(f"❌ MakeVideo error: {e}", exc_info=True)
        await update_job_status(
            job_id,
            JobStatus.FAILED,
            error={
                "message": e.message,
                "code": e.code,
                "details": e.details
            }
        )
        raise
        
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        await update_job_status(
            job_id,
            JobStatus.FAILED,
            error={
                "message": str(e),
                "type": type(e).__name__
            }
        )
        raise


@shared_task(name='app.celery_tasks.cleanup_temp_files')
def cleanup_temp_files():
    """Limpa arquivos temporários antigos"""
    logger.info("🧹 Running temp files cleanup...")
    
    settings = get_settings()
    temp_dir = Path(settings['temp_dir'])
    cutoff_hours = settings['cleanup_temp_after_hours']
    
    if not temp_dir.exists():
        return
    
    cutoff_time = datetime.utcnow() - timedelta(hours=cutoff_hours)
    removed_count = 0
    
    for job_dir in temp_dir.iterdir():
        if job_dir.is_dir():
            mtime = datetime.fromtimestamp(job_dir.stat().st_mtime)
            if mtime < cutoff_time:
                try:
                    import shutil
                    shutil.rmtree(job_dir)
                    removed_count += 1
                    logger.info(f"🗑️ Removed temp dir: {job_dir.name}")
                except Exception as e:
                    logger.error(f"Error removing {job_dir}: {e}")
    
    logger.info(f"✅ Cleanup complete: {removed_count} temp directories removed")


@shared_task(name='app.celery_tasks.cleanup_old_shorts')
def cleanup_old_shorts():
    """Limpa shorts não usados há muito tempo"""
    logger.info("🧹 Running shorts cache cleanup...")
    
    settings = get_settings()
    _, _, _, shorts_cache, _ = get_instances()
    
    days = settings['cleanup_shorts_cache_after_days']
    removed_count = shorts_cache.cleanup_old(days=days)
    
    logger.info(f"✅ Cleanup complete: {removed_count} old shorts removed")
