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

from .celery_config import celery_app
from .config import get_settings
from .models import Job, JobStatus, ShortInfo, JobResult
from .redis_store import RedisJobStore
from .api_client import MicroservicesClient
from .video_builder import VideoBuilder
from .shorts_manager import ShortsCache
from .subtitle_generator import SubtitleGenerator
from .subtitle_postprocessor import process_subtitles_with_vad
from .video_validator import VideoValidator
from .shorts_blacklist import ShortsBlacklist
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
video_validator = None
blacklist = None


def get_instances():
    """Inicializa instâncias globais se necessário"""
    global redis_store, api_client, video_builder, shorts_cache, subtitle_gen, video_validator, blacklist
    
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
        
        # Inicializar validador e blacklist
        video_validator = VideoValidator(min_confidence=0.40)
        blacklist_path = Path(settings['shorts_cache_dir']) / 'blacklist.json'
        blacklist = ShortsBlacklist(str(blacklist_path), ttl_days=90)
        
        logger.info("✅ Video validator and blacklist initialized")
    
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


@celery_app.task(bind=True, name='app.celery_tasks.process_make_video')
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
        # Criar ou obter event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Executar em event loop assíncrono
        loop.run_until_complete(_process_make_video_async(job_id))
        
    except Exception as e:
        logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)
        
        # Atualizar job com erro
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        loop.run_until_complete(update_job_status(
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
        
        # Validar duração do áudio
        if audio_duration < 5.0:
            raise AudioProcessingException(
                f"Audio too short: {audio_duration:.1f}s (minimum 5 seconds)",
                {"duration": audio_duration, "minimum": 5.0}
            )
        if audio_duration > 3600.0:
            raise AudioProcessingException(
                f"Audio too long: {audio_duration:.1f}s (maximum 1 hour)",
                {"duration": audio_duration, "maximum": 3600.0}
            )
        
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
        
        # Etapa 3: Verificar cache e baixar shorts necessários
        logger.info(f"⬇️ [3/7] Checking cache and downloading shorts...")
        await update_job_status(job_id, JobStatus.DOWNLOADING_SHORTS, progress=25.0)
        
        downloaded_shorts = []
        cache_hits = 0
        to_download = []
        failed_downloads = []
        
        # Primeiro: verificar quais já estão em cache
        logger.info(f"🔍 Verificando cache para {len(shorts_list)} vídeos...")
        for short in shorts_list:
            video_id = short['video_id']
            
            # 🚫 CHECK: Blacklist PRIMEIRO (antes de cache)
            if blacklist.is_blacklisted(video_id):
                logger.warning(f"🚫 BLACKLIST (pré-cache): {video_id} - pulando")
                failed_downloads.append(video_id)
                continue
            
            cached = shorts_cache.get(video_id)
            if cached:
                # 🔍 VALIDAÇÃO: Videos em cache também precisam validação OCR!
                video_path = cached.get('file_path')
                if video_path and Path(video_path).exists():
                    # Validar OCR em vídeos do cache
                    try:
                        has_subs, confidence, reason = video_validator.has_embedded_subtitles(video_path)
                        
                        if has_subs:
                            # 🚫 LEGENDAS DETECTADAS NO CACHE - BLOQUEAR
                            logger.error(f"🚫 CACHE: Embedded subtitles in {video_id} (conf: {confidence:.2f}) - blacklisting")
                            blacklist.add(video_id, reason, confidence, metadata={
                                'title': short.get('title', ''),
                                'duration': short.get('duration_seconds', 0),
                                'source': 'cache_validation'
                            })
                            
                            # Remover do cache
                            shorts_cache.remove(video_id)
                            if Path(video_path).exists():
                                Path(video_path).unlink()
                            
                            failed_downloads.append(video_id)
                            continue
                        
                        # ✅ CACHE VÁLIDO - usar
                        downloaded_shorts.append(cached)
                        cache_hits += 1
                        logger.info(f"✅ Cache HIT (validado): {video_id}")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Erro validando cache {video_id}: {e} - removendo")
                        shorts_cache.remove(video_id)
                        to_download.append(short)
                else:
                    logger.warning(f"⚠️ Cache inválido (arquivo não existe): {video_id}")
                    shorts_cache.remove(video_id)
                    to_download.append(short)
            else:
                to_download.append(short)
        
        logger.info(f"💾 Cache: {cache_hits} validados, {len(to_download)} precisam download, {len(failed_downloads)} bloqueados")
        
        # Se já temos shorts suficientes no cache, pular download
        if len(downloaded_shorts) >= min(10, job.max_shorts):
            logger.info(f"⚡ Cache suficiente! Pulando downloads ({len(downloaded_shorts)} vídeos disponíveis)")
        else:
            # Baixar os que faltam (com retry, skip em erro e validação OCR)
            logger.info(f"⬇️ Baixando {len(to_download)} vídeos com validação OCR...")
            
            async def download_with_retry(short_info, index):
                video_id = short_info['video_id']
                output_path = Path(settings['shorts_cache_dir']) / f"{video_id}.mp4"
                
                # 🚫 CHECK 1: Verificar blacklist ANTES de baixar
                if blacklist.is_blacklisted(video_id):
                    logger.warning(f"🚫 BLACKLIST: {video_id} - pulando download")
                    failed_downloads.append(video_id)
                    return None
                
                for attempt in range(3):  # 3 tentativas
                    try:
                        # Download do vídeo
                        metadata = await api_client.download_video(video_id, str(output_path))
                        
                        # ✅ CHECK 2: Validar integridade do vídeo (síncrono)
                        try:
                            video_validator.validate_video_integrity(str(output_path), timeout=5)
                        except Exception as e:
                            logger.error(f"❌ INTEGRITY FAILED: {video_id} - {e}")
                            if output_path.exists():
                                output_path.unlink()
                            failed_downloads.append(video_id)
                            return None
                        
                        # 🔍 CHECK 3: Detectar legendas embutidas (OCR - síncrono)
                        has_subs, confidence, reason = video_validator.has_embedded_subtitles(str(output_path))
                        
                        if has_subs:
                            # 🚫 LEGENDAS EMBUTIDAS DETECTADAS - BLOQUEAR
                            logger.error(f"🚫 EMBEDDED SUBTITLES: {video_id} (conf: {confidence:.2f}) - adicionando à blacklist")
                            blacklist.add(video_id, reason, confidence, metadata={
                                'title': short_info.get('title', ''),
                                'duration': short_info.get('duration_seconds', 0)
                            })
                            
                            # Remover arquivo
                            if output_path.exists():
                                output_path.unlink()
                            
                            failed_downloads.append(video_id)
                            return None
                        
                        # ✅ VÍDEO VÁLIDO - adicionar ao cache
                        result = {
                            'video_id': video_id,
                            'duration_seconds': short_info.get('duration_seconds', 30),
                            'file_path': str(output_path),
                            'resolution': metadata.get('resolution', '1080x1920'),
                            'title': short_info.get('title', ''),
                        }
                        
                        shorts_cache.add(video_id, str(output_path), result)
                        logger.info(f"✅ Downloaded & Validated: {video_id} ({index+1}/{len(to_download)}) - limpo, sem legendas embutidas")
                        return result
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Erro no download {video_id} (tentativa {attempt+1}/3): {e}")
                        if attempt == 2:  # Última tentativa
                            logger.error(f"❌ SKIP: {video_id} - falhou após 3 tentativas")
                            failed_downloads.append(video_id)
                            return None
                        await asyncio.sleep(2 ** attempt)  # Backoff exponencial
                
                return None
            
            # Download em paralelo (máximo 5 simultâneos)
            batch_size = 5
            for i in range(0, len(to_download), batch_size):
                batch = to_download[i:i+batch_size]
                tasks = [download_with_retry(short, i+j) for j, short in enumerate(batch)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if result and not isinstance(result, Exception):
                        downloaded_shorts.append(result)
                
                # Atualizar progresso (protegido contra divisão por zero)
                if len(to_download) > 0:
                    progress = 25.0 + (45.0 * min(i + batch_size, len(to_download)) / len(to_download))
                else:
                    progress = 70.0  # Pular para fim do download se não há nada para baixar
                await update_job_status(job_id, JobStatus.DOWNLOADING_SHORTS, progress=progress)
        
        logger.info(f"📦 Total: {len(downloaded_shorts)} vídeos disponíveis ({cache_hits} cache, {len(downloaded_shorts)-cache_hits} novos)")
        if failed_downloads:
            logger.warning(f"⚠️ Falhas: {len(failed_downloads)} vídeos não baixados: {failed_downloads[:5]}...")
        
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
        
        # Converter segmentos para formato dict (cues)
        raw_cues = []
        for segment in segments:
            # Tentar usar word_timestamps se disponível
            words = segment.get('words', [])
            
            if words:
                # Word-level timestamps disponíveis
                for word_data in words:
                    raw_cues.append({
                        'start': word_data['start'],
                        'end': word_data['end'],
                        'text': word_data['word']
                    })
            else:
                # Fallback: dividir texto do segment em palavras
                text = segment.get('text', '').strip()
                if text:
                    import re
                    words_list = re.findall(r'\S+', text)
                    seg_start = segment.get('start', 0.0)
                    seg_end = segment.get('end', seg_start + 1.0)
                    seg_duration = seg_end - seg_start
                    
                    if words_list:
                        time_per_word = seg_duration / len(words_list)
                        
                        for i, word in enumerate(words_list):
                            word_start = seg_start + (i * time_per_word)
                            word_end = word_start + time_per_word
                            
                            raw_cues.append({
                                'start': word_start,
                                'end': word_end,
                                'text': word
                            })
        
        logger.info(f"📊 Transcription: {len(segments)} segments, {len(raw_cues)} words")
        
        # DEBUG: Log first segment
        if segments:
            logger.info(f"DEBUG first segment: {segments[0]}")
        else:
            logger.error("❌ NO SEGMENTS from transcriber!")
        
        if not raw_cues:
            logger.error(f"❌ NO WORDS extracted from {len(segments)} segments!")
        
        # Aplicar Speech-Gated Subtitles (VAD)
        logger.info(f"🎙️ [6.5/7] Applying speech gating (VAD)...")
        await update_job_status(job_id, JobStatus.GENERATING_SUBTITLES, progress=82.0)
        
        try:
            gated_cues, vad_ok = process_subtitles_with_vad(str(audio_path), raw_cues)
            
            if vad_ok:
                logger.info(f"✅ Speech gating OK: {len(gated_cues)}/{len(raw_cues)} cues (silero-vad)")
            else:
                logger.warning(f"⚠️ Speech gating fallback: {len(gated_cues)}/{len(raw_cues)} cues (webrtcvad/RMS)")
            
            # Usar cues com gating
            final_cues = gated_cues
            
        except Exception as e:
            logger.error(f"⚠️ Speech gating failed: {e}, usando cues originais")
            # Fallback: usar cues originais sem gating
            final_cues = raw_cues
            vad_ok = False
        
        # Gerar SRT com cues finais
        subtitle_path = Path(settings['temp_dir']) / job_id / "subtitles.srt"
        words_per_caption = int(settings.get('words_per_caption', 2))
        
        # DEBUG
        logger.info(f"DEBUG: final_cues count = {len(final_cues)}")
        if not final_cues:
            logger.error("❌ CRITICAL: final_cues is EMPTY! Cannot generate SRT!")
        
        # Gerar SRT usando os cues filtrados por VAD
        from .subtitle_generator import SubtitleGenerator
        subtitle_gen = SubtitleGenerator()
        
        # Agrupar final_cues em segments (cada X palavras = 1 segment)
        # O generate_word_by_word_srt irá re-dividir em palavras e agrupar por words_per_caption
        segment_size = 10  # Agrupar 10 palavras por segment
        segments_for_srt = []
        
        for i in range(0, len(final_cues), segment_size):
            chunk = final_cues[i:i+segment_size]
            if chunk:
                segments_for_srt.append({
                    'start': chunk[0]['start'],
                    'end': chunk[-1]['end'],
                    'text': ' '.join(c['text'] for c in chunk)
                })
        
        subtitle_gen.generate_word_by_word_srt(segments_for_srt, str(subtitle_path), words_per_caption=words_per_caption)
        
        # DEBUG: Verificar se arquivo foi criado
        if subtitle_path.exists():
            srt_size = subtitle_path.stat().st_size
            logger.info(f"DEBUG: SRT file created, size = {srt_size} bytes")
            if srt_size == 0:
                logger.error("❌ CRITICAL: SRT file is EMPTY (0 bytes)!")
        else:
            logger.error(f"❌ CRITICAL: SRT file NOT created at {subtitle_path}!")
        
        num_captions_expected = len(final_cues) // words_per_caption
        logger.info(f"✅ Speech-gated subtitles: {len(final_cues)} words → {len(segments_for_srt)} segments → ~{num_captions_expected} captions, {words_per_caption} words/caption, vad_ok={vad_ok}")
        
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


@celery_app.task(name='app.celery_tasks.cleanup_temp_files')
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
            # Verificar se job ainda está ativo (não deletar arquivos de jobs em execução)
            try:
                job_id = job_dir.name
                store, _, _, _, _ = get_instances()
                job = asyncio.run(store.get_job(job_id))
                
                if job and job.status not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    logger.info(f"⏭️ Skipping active job: {job_id}")
                    continue
            except Exception as e:
                logger.debug(f"Could not check job status for {job_id}: {e}")
                pass  # Se não encontrar job, continuar com limpeza baseada em timestamp
            
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


@celery_app.task(name='app.celery_tasks.cleanup_old_shorts')
def cleanup_old_shorts():
    """Limpa shorts não usados há muito tempo"""
    logger.info("🧹 Running shorts cache cleanup...")
    
    settings = get_settings()
    _, _, _, shorts_cache, _ = get_instances()
    
    days = settings['cleanup_shorts_cache_after_days']
    removed_count = shorts_cache.cleanup_old(days=days)
    
    logger.info(f"✅ Cleanup complete: {removed_count} old shorts removed")
