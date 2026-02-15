"""
Celery Tasks for Make-Video Service

Tasks de processamento assíncrono para criação de vídeos.
"""

import os
import asyncio
import logging
import random
import json
import gc
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from .celery_config import celery_app
from ..core.config import get_settings
from ..core.models import Job, JobStatus, ShortInfo, JobResult
from .redis_store import RedisJobStore
from ..api.api_client import MicroservicesClient
from ..services.video_builder import VideoBuilder
from ..services.shorts_manager import ShortsCache
from ..services.subtitle_generator import SubtitleGenerator
from ..services.subtitle_postprocessor import process_subtitles_with_vad
from ..video_processing.video_validator import VideoValidator
from ..services.blacklist_factory import get_blacklist
from .file_logger import FileLogger
from ..shared.exceptions import (
    MakeVideoException,
    AudioProcessingException,
    VideoProcessingException,
    MicroserviceException
)
from ..core.constants import ProcessingLimits, TimeoutConstants, ValidationThresholds
from ..shared.events import EventPublisher, EventType, Event
from ..shared.domain_integration import process_job_with_domain
import shortuuid

logger = logging.getLogger(__name__)

# Inicializar sistema de logging em arquivo
FileLogger.setup()

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
            output_dir=settings['output_dir'],
            video_codec=settings['ffmpeg_video_codec'],
            audio_codec=settings['ffmpeg_audio_codec'],
            preset=settings['ffmpeg_preset'],
            crf=settings['ffmpeg_crf']
        )
        
        shorts_cache = ShortsCache(
            cache_dir=settings['shorts_cache_dir']
        )
        
        subtitle_gen = SubtitleGenerator()
        
        # Inicializar validador e blacklist (usando factory)
        video_validator = VideoValidator(
            min_confidence=ValidationThresholds.OCR_MIN_CONFIDENCE,
            frames_per_second=ValidationThresholds.OCR_FRAMES_PER_SECOND,
            max_frames=ValidationThresholds.OCR_MAX_FRAMES,
            redis_store=redis_store  # P2 Optimization: Cache de validação
        )
        blacklist = get_blacklist()  # Factory cria instância baseada em config
        
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


@celery_app.task(bind=True, name='app.infrastructure.celery_tasks.process_make_video')
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
    8. Trimming (ajuste de duração)
    
    Nota: Suporta duas implementações:
    - Legada (padrão): Processamento monolítico original
    - Domain-Driven: Nova arquitetura com JobProcessor e Stages
    
    Configuração via variável de ambiente:
    USE_DOMAIN_DRIVEN_ARCHITECTURE=true (para nova implementação)
    """
    logger.info(f"🎬 Starting make-video job: {job_id}")
    
    # Verificar se deve usar Domain-Driven Architecture
    settings = get_settings()
    use_domain = settings.get('use_domain_driven_architecture', False)
    
    if use_domain:
        logger.info(f"🏗️  Using Domain-Driven Architecture")
    
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
        
        # Executar implementação apropriada
        if use_domain:
            loop.run_until_complete(_process_make_video_with_domain(job_id))
        else:
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


async def _process_make_video_with_domain(job_id: str):
    """
    Processamento assíncrono usando Domain-Driven Design
    
    Esta é a nova implementação que usa JobProcessor e Stages
    para processamento modular e testável.
    """
    
    store, api_client, video_builder, shorts_cache, subtitle_gen = get_instances()
    settings = get_settings()
    
    # Obter instâncias adicionais
    if video_validator is None or blacklist is None:
        get_instances()  # Garante que todas as instâncias globais estão inicializadas
    
    # Criar event publisher (opcional)
    event_publisher = EventPublisher(redis_url=settings['redis_url'])
    
    # Processar job usando Domain-Driven Design
    result = await process_job_with_domain(
        job_id=job_id,
        redis_store=store,
        api_client=api_client,
        video_builder=video_builder,
        shorts_cache=shorts_cache,
        subtitle_gen=subtitle_gen,
        video_validator=video_validator,
        blacklist=blacklist,
        settings=settings,
        event_publisher=event_publisher
    )
    
    return result


async def _process_make_video_async(job_id: str):
    """Processamento assíncrono do vídeo (implementação legada)"""
    
    # Criar logger específico para este job
    job_logger = FileLogger.get_job_logger(job_id)
    job_logger.info("="*80)
    job_logger.info(f"🎬 STARTING MAKE-VIDEO JOB: {job_id}")
    job_logger.info("="*80)
    
    store, api_client, video_builder, shorts_cache, subtitle_gen = get_instances()
    settings = get_settings()
    
    job_logger.debug(f"Settings loaded: {list(settings.keys())}")
    
    # Carregar job
    job = await store.get_job(job_id)
    if not job:
        job_logger.error(f"❌ Job {job_id} not found in Redis")
        raise MakeVideoException(f"Job {job_id} not found")
    
    job_logger.info(f"Job loaded: query='{job.query}', max_shorts={job.max_shorts}")
    
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
        
        # Calcular target_duration com padding configurável (Sprint-09)
        padding_ms = int(settings.get('video_trim_padding_ms', 1000))
        padding_seconds = padding_ms / 1000.0
        target_duration = audio_duration + padding_seconds
        
        # Atualizar job com duração do áudio
        job.audio_duration = audio_duration
        job.target_video_duration = target_duration
        await store.save_job(job)
        
        logger.info(f"🎵 Audio: {audio_duration:.1f}s + {padding_seconds:.2f}s padding → Target: {target_duration:.1f}s")
        
        # Salvar checkpoint (Sprint-01)
        await _save_checkpoint(job_id, "analyzing_audio_completed")
        
        # Etapa 2: Buscar shorts
        logger.info(f"🔍 [2/7] Fetching shorts...")
        await update_job_status(job_id, JobStatus.FETCHING_SHORTS, progress=15.0)
        
        shorts_list = await api_client.search_shorts(job.query, job.max_shorts)
        logger.info(f"✅ Found {len(shorts_list)} shorts")
        
        if not shorts_list:
            raise VideoProcessingException(f"No shorts found for query: {job.query}")
        
        # Salvar checkpoint (Sprint-01)
        await _save_checkpoint(job_id, "fetching_shorts_completed")
        
        # Etapa 3: Verificar cache e baixar shorts necessários
        job_logger.info("="*60)
        job_logger.info(f"⬇️ [3/7] CHECKING CACHE AND DOWNLOADING SHORTS")
        job_logger.info("="*60)
        logger.info(f"⬇️ [3/7] Checking cache and downloading shorts...")
        await update_job_status(job_id, JobStatus.DOWNLOADING_SHORTS, progress=25.0)
        
        job_logger.info(f"shorts_cache_dir: {settings['shorts_cache_dir']}")
        job_logger.info(f"max_fetch_rounds: {settings['max_fetch_rounds']}")
        job_logger.info(f"Initial shorts_list length: {len(shorts_list)}")
        
        downloaded_shorts = []
        failed_downloads = []
        processed_ids = set()
        max_rounds = settings['max_fetch_rounds']  # Configurável via MAX_FETCH_ROUNDS
        base_request = max(job.max_shorts, 10)
        
        job_logger.info(f"max_rounds={max_rounds}, base_request={base_request}")

        async def download_with_retry(short_info, index):
            video_id = short_info['video_id']
            output_path = Path(settings['shorts_cache_dir']) / f"{video_id}.mp4"
            
            job_logger.debug(f"📥 [Download] Starting: {video_id} (#{index+1})")
            job_logger.debug(f"   Output path: {output_path}")
            
            # 🚫 CHECK 1: Verificar blacklist ANTES de baixar
            if blacklist.is_blacklisted(video_id):
                job_logger.warning(f"🚫 BLACKLIST: {video_id} - pulando download")
                logger.warning(f"🚫 BLACKLIST: {video_id} - pulando download")
                failed_downloads.append(video_id)
                return None
            
            job_logger.debug(f"   ✅ Not in blacklist")
            
            for attempt in range(3):  # 3 tentativas
                try:
                    job_logger.debug(f"   🔄 Download attempt {attempt+1}/3 for {video_id}")
                    
                    #Download do vídeo com timeout
                    job_logger.debug(f"   📡 Calling video-downloader API: {video_id}")
                    job_logger.debug(f"   ⏱️  Timeout: 180s (3 minutos)")
                    
                    try:
                        metadata = await asyncio.wait_for(
                            api_client.download_video(video_id, str(output_path)),
                            timeout=180.0  # 3 minutos timeout absoluto
                        )
                        job_logger.debug(f"   ✅ Download completed: {video_id}, metadata: {metadata}")
                    except asyncio.TimeoutError:
                        job_logger.error(f"   ⏱️❌ TIMEOUT 180s for {video_id}")
                        raise MicroserviceException(
                            "video-downloader",
                            f"Download timeout after 180s",
                            {"video_id": video_id, "timeout": True}
                        )
                    
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
                    logger.info(f"✅ Downloaded & Validated: {video_id} ({index+1}) - limpo, sem legendas embutidas")
                    return result
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erro no download {video_id} (tentativa {attempt+1}/3): {e}")
                    if attempt == 2:  # Última tentativa
                        logger.error(f"❌ SKIP: {video_id} - falhou após 3 tentativas")
                        failed_downloads.append(video_id)
                        return None
                    await asyncio.sleep(2 ** attempt)  # Backoff exponencial
            
            return None

        for round_idx in range(1, max_rounds + 1):
            request_size = base_request * round_idx
            job_logger.info(f"🔁 ROUND {round_idx}/{max_rounds}: buscando até {request_size} shorts (base={base_request})")
            logger.info(f"🔁 Round {round_idx}/{max_rounds}: buscando até {request_size} shorts (base={base_request})")
            await update_job_status(
                job_id,
                JobStatus.DOWNLOADING_SHORTS,
                progress=25.0 + (round_idx - 1) * 5.0
            )
            
            job_logger.debug(f"Calling api_client.search_shorts(query='{job.query}', max_shorts={request_size})")
            shorts_list = await api_client.search_shorts(job.query, request_size)
            job_logger.info(f"🔍 Received {len(shorts_list)} shorts from search API")
            logger.info(f"🔍 Verificando cache para {len(shorts_list)} vídeos (round {round_idx})...")
            cache_hits = 0
            to_download = []
            
            for short in shorts_list:
                video_id = short['video_id']
                if video_id in processed_ids:
                    job_logger.debug(f"   ⏭️  {video_id}: already processed, skipping")
                    continue
                processed_ids.add(video_id)
                job_logger.debug(f"   🔍 Checking cache for: {video_id}")
                cached = shorts_cache.get(video_id)
                if cached:
                    try:
                        file_path = Path(cached["file_path"])
                        job_logger.debug(f"   ✅ Cache hit: {video_id}, validating integrity...")
                        video_validator.validate_video_integrity(str(file_path), timeout=5)
                        has_subs, confidence, reason = video_validator.has_embedded_subtitles(str(file_path))
                        if has_subs:
                            job_logger.warning(
                                f"   🚫 EMBEDDED SUBTITLES (cache): {video_id} (conf: {confidence:.2f}) - blacklisting"
                            )
                            logger.error(
                                f"🚫 EMBEDDED SUBTITLES (cache): {video_id} (conf: {confidence:.2f}) - blacklisting"
                            )
                            blacklist.add(video_id, reason, confidence, metadata={
                                'title': short.get('title', ''),
                                'duration': short.get('duration_seconds', 0)
                            })
                            shorts_cache.remove(video_id)
                            continue
                        shorts_cache.mark_validated(video_id, False, confidence)
                        downloaded_shorts.append(cached)
                        cache_hits += 1
                        job_logger.info(f"   ✅ Cache HIT validado: {video_id} (conf={confidence:.2f})")
                        logger.info(f"✅ Cache HIT validado: {video_id} (conf={confidence:.2f})")
                    except Exception as e:
                        job_logger.warning(f"   ⚠️ Cache invalid: {video_id} - {e}. Will re-download.")
                        logger.warning(f"⚠️ Cache invalid: {video_id} - {e}. Will re-download.")
                        shorts_cache.remove(video_id)
                        to_download.append(short)
                else:
                    job_logger.debug(f"   ⬇️  Cache miss: {video_id}, adding to download queue")
                    to_download.append(short)
            
            job_logger.info(f"💾 Cache: {cache_hits} hits, {len(to_download)} precisam download (round {round_idx})")
            logger.info(f"💾 Cache: {cache_hits} hits, {len(to_download)} precisam download (round {round_idx})")

            if len(downloaded_shorts) < min(10, base_request):
                job_logger.info(f"⬇️ Baixando {len(to_download)} vídeos com validação OCR...")
                logger.info(f"⬇️ Baixando {len(to_download)} vídeos com validação OCR...")
                batch_size = 5
                for i in range(0, len(to_download), batch_size):
                    batch = to_download[i:i+batch_size]
                    job_logger.debug(f"   Batch {i//batch_size + 1}: processing {len(batch)} videos")
                    job_logger.debug(f"   Video IDs in batch: {[s['video_id'] for s in batch]}")
                    tasks = [download_with_retry(short, i+j) for j, short in enumerate(batch)]
                    job_logger.debug(f"   Awaiting asyncio.gather for {len(tasks)} tasks...")
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    job_logger.debug(f"   Results received: {len([r for r in results if r and not isinstance(r, Exception)])} successful")
                    for result in results:
                        if result and not isinstance(result, Exception):
                            downloaded_shorts.append(result)
                    if len(to_download) > 0:
                        progress = 30.0 + (40.0 * min(i + batch_size, len(to_download)) / len(to_download))
                    else:
                        progress = 70.0
                    await update_job_status(job_id, JobStatus.DOWNLOADING_SHORTS, progress=progress)
            
            total_duration = sum(s.get('duration_seconds', 0) for s in downloaded_shorts)
            logger.info(
                f"📦 Round {round_idx} done: {len(downloaded_shorts)} vídeos válidos, duração acumulada {total_duration:.1f}s "
                f"(target {target_duration:.1f}s)"
            )
            
            if total_duration >= target_duration:
                logger.info("✅ Duração suficiente alcançada, encerrando busca de shorts")
                break
            elif round_idx == max_rounds:
                raise VideoProcessingException(
                    f"Insufficient shorts after {max_rounds} rounds (got {total_duration:.1f}s, target {target_duration:.1f}s)"
                )
            else:
                logger.warning(
                    f"⚠️ Duração insuficiente ({total_duration:.1f}/{target_duration:.1f}s). "
                    f"Nova rodada solicitará {base_request * (round_idx + 1)} vídeos (mult={round_idx+1}x)."
                )
                continue
        
        logger.info(f"📦 Total final: {len(downloaded_shorts)} vídeos válidos")
        if failed_downloads:
            logger.warning(f"⚠️ Falhas: {len(failed_downloads)} vídeos não baixados: {failed_downloads[:5]}...")
        
        if not downloaded_shorts:
            raise VideoProcessingException("No shorts could be downloaded")
        
        # Salvar checkpoint (Sprint-01)
        await _save_checkpoint(job_id, "downloading_shorts_completed")
        
        # Etapa 4: Selecionar shorts aleatoriamente
        logger.info(f"🎲 [4/7] Selecting shorts randomly...")
        await update_job_status(job_id, JobStatus.SELECTING_SHORTS, progress=70.0)
        
        # DEBUG: Log antes do shuffle
        logger.info(f"📊 DEBUG: downloaded_shorts count = {len(downloaded_shorts)}, target_duration = {target_duration:.1f}s")
        for i, s in enumerate(downloaded_shorts[:10]):  # Mostrar primeiros 10
            logger.info(f"  [{i}] {s['video_id']}: {s['duration_seconds']:.1f}s")
        
        random.shuffle(downloaded_shorts)
        
        selected_shorts = []
        total_duration = 0.0
        
        for short in downloaded_shorts:
            if total_duration >= target_duration:
                logger.info(f"🎯 Breaking loop: total_duration={total_duration:.1f}s >= target_duration={target_duration:.1f}s")
                break
            selected_shorts.append(short)
            total_duration += short['duration_seconds']
            logger.info(f"  ✓ Added {short['video_id']}: {short['duration_seconds']:.1f}s (cumulative: {total_duration:.1f}s)")
        
        logger.info(f"🎯 Selected {len(selected_shorts)} shorts ({total_duration:.1f}s / target {target_duration:.1f}s)")
        
        if not selected_shorts:
            raise VideoProcessingException("No shorts available for video creation")
        
        # Salvar checkpoint (Sprint-01)
        await _save_checkpoint(job_id, "selecting_shorts_completed")
        
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
        
        # ============================================================================
        # VALIDAÇÃO PÓS-CONCATENAÇÃO (BUG FIX: detectar duplicação de frames)
        # ============================================================================
        concat_info = await video_builder.get_video_info(str(temp_video_path))
        concat_duration = concat_info['duration']
        expected_duration = sum(s['duration_seconds'] for s in selected_shorts)
        
        logger.info(f"📊 CONCATENATION VALIDATION:")
        logger.info(f"   ├─ Expected: {expected_duration:.2f}s (sum of {len(selected_shorts)} shorts)")
        logger.info(f"   └─ Actual: {concat_duration:.2f}s")
        
        # Tolerância: ±2 segundos
        concat_tolerance = 2.0
        concat_diff = abs(concat_duration - expected_duration)
        
        if concat_diff > concat_tolerance:
            logger.error(
                f"❌ CONCATENATION VALIDATION FAILED! "
                f"Concatenated video ({concat_duration:.2f}s) differs from expected "
                f"({expected_duration:.2f}s) by {concat_diff:.2f}s (tolerance: {concat_tolerance}s)"
            )
            
            raise VideoProcessingException(
                "Concatenation produced incorrect duration",
                {
                    "expected_duration": expected_duration,
                    "actual_duration": concat_duration,
                    "difference": concat_diff,
                    "tolerance": concat_tolerance,
                    "shorts_count": len(selected_shorts),
                    "conclusion": "Frame duplication during concatenation. Check FFmpeg concat filter."
                }
            )
        
        logger.info(f"✅ CONCATENATION VALIDATION PASSED: Duration OK ({concat_duration:.2f}s ≈ {expected_duration:.2f}s)")
        
        # Salvar checkpoint (Sprint-01)
        await _save_checkpoint(job_id, "assembling_video_completed")
        
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
        
        # Salvar checkpoint (Sprint-01)
        await _save_checkpoint(job_id, "generating_subtitles_completed")
        
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
        
        # Etapa 8: Trimming final (Sprint-09)
        logger.info(f"✂️ [8/8] Trimming video to target duration...")
        await update_job_status(job_id, JobStatus.FINAL_COMPOSITION, progress=92.0)
        
        # Calcular duração final desejada
        padding_ms = int(settings.get('video_trim_padding_ms', 1000))
        padding_seconds = padding_ms / 1000.0
        final_duration = audio_duration + padding_seconds
        
        # Validação obrigatória: video deve ser maior que áudio
        if final_duration <= audio_duration:
            raise VideoProcessingException(
                "Invalid trim configuration: video would be shorter than or equal to audio",
                {
                    "audio_duration": audio_duration,
                    "padding_ms": padding_ms,
                    "final_duration": final_duration,
                    "suggestion": "Increase VIDEO_TRIM_PADDING_MS to at least 100ms"
                }
            )
        
        # Verificar duração atual do vídeo
        pre_trim_info = await video_builder.get_video_info(str(final_video_path))
        current_duration = pre_trim_info['duration']
        
        logger.info(f"📊 Trim analysis:")
        logger.info(f"   ├─ Audio duration: {audio_duration:.2f}s")
        logger.info(f"   ├─ Padding: {padding_ms}ms ({padding_seconds:.2f}s)")
        logger.info(f"   ├─ Target final: {final_duration:.2f}s")
        logger.info(f"   └─ Current video: {current_duration:.2f}s")
        
        # VALIDAÇÃO CRÍTICA: Vídeo DEVE ser >= audio_duration
        if current_duration < audio_duration - 0.5:  # -0.5s tolerância para keyframes
            raise VideoProcessingException(
                f"ERRO CRÍTICO: Vídeo ({current_duration:.2f}s) é menor que áudio ({audio_duration:.2f}s)!",
                {
                    "video_duration": current_duration,
                    "audio_duration": audio_duration,
                    "target_duration": final_duration,
                    "problem": "Vídeo não pode ser menor que áudio"
                }
            )
        
        # Trim para a duração exata: audio_duration + padding
        if abs(current_duration - final_duration) > 0.5:  # Apenas se diferença significativa
            logger.info(f"✂️ Trimming needed: {current_duration:.2f}s → {final_duration:.2f}s")
            
            # Criar path temporário para arquivo trimmed
            trimmed_video_path = Path(settings['temp_dir']) / job_id / f"{job_id}_trimmed.mp4"
            
            # Executar trim
            await video_builder.trim_video(
                video_path=str(final_video_path),
                output_path=str(trimmed_video_path),
                max_duration=final_duration
            )
            
            # Substituir vídeo final pelo trimmed
            import shutil
            shutil.move(str(trimmed_video_path), str(final_video_path))
            
            logger.info(f"✅ Video trimmed and replaced")
        else:
            logger.info(f"⏭️ Trim skipped: video duration ({current_duration:.2f}s) already matches target ({final_duration:.2f}s ± 0.5s)")
        
        # Obter informações do vídeo final
        video_info = await video_builder.get_video_info(str(final_video_path))
        file_size = final_video_path.stat().st_size
        
        # ============================================================================
        # VALIDAÇÃO FINAL OBRIGATÓRIA (BUG FIX: detectar vídeo com duração incorreta)
        # ============================================================================
        final_video_duration = video_info['duration']
        
        logger.info(f"🎯 FINAL VALIDATION:")
        logger.info(f"   ├─ Audio duration: {audio_duration:.2f}s")
        logger.info(f"   ├─ Target (audio + padding): {final_duration:.2f}s")
        logger.info(f"   └─ Final video: {final_video_duration:.2f}s")
        
        # Tolerância: ±2 segundos do target
        tolerance = 2.0
        duration_diff = abs(final_video_duration - final_duration)
        
        if duration_diff > tolerance:
            logger.error(
                f"❌ FINAL VALIDATION FAILED! "
                f"Video duration ({final_video_duration:.2f}s) differs from target "
                f"({final_duration:.2f}s) by {duration_diff:.2f}s (tolerance: {tolerance}s)"
            )
            
            raise VideoProcessingException(
                "Final video duration validation failed",
                {
                    "audio_duration": audio_duration,
                    "target_duration": final_duration,
                    "actual_duration": final_video_duration,
                    "difference": duration_diff,
                    "tolerance": tolerance,
                    "conclusion": "Video processing completed but duration is incorrect. "
                                 "Check concatenation and trim steps in logs."
                }
            )
        
        # Validação de áudio: vídeo deve ser >= áudio
        if final_video_duration < audio_duration - 0.5:
            logger.error(
                f"❌ CRITICAL: Video ({final_video_duration:.2f}s) is shorter than audio ({audio_duration:.2f}s)!"
            )
            raise VideoProcessingException(
                "Video is shorter than audio",
                {
                    "video_duration": final_video_duration,
                    "audio_duration": audio_duration,
                    "problem": "Video cannot be shorter than audio"
                }
            )
        
        logger.info(f"✅ FINAL VALIDATION PASSED: Duration OK ({final_video_duration:.2f}s ≈ {final_duration:.2f}s)")
        
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
        
        # Deletar checkpoint após sucesso (Sprint-01)
        await _delete_checkpoint(job_id)
        
        # Metrics (Sprint-05)
        _metrics.jobs_completed += 1
        
        logger.info(f"🎉 Job {job_id} completed successfully!")
        logger.info(f"   ├─ Duration: {result.duration:.1f}s")
        logger.info(f"   ├─ Size: {result.file_size_mb}MB")
        logger.info(f"   ├─ Shorts used: {result.shorts_used}")
        logger.info(f"   └─ Processing time: {result.processing_time:.1f}s")
        
        return result
        
    except MakeVideoException as e:
        logger.error(f"❌ MakeVideo error: {e}", exc_info=True)
        
        # Metrics (Sprint-05)
        _metrics.jobs_failed += 1
        
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
        
        # Metrics (Sprint-05)
        _metrics.jobs_failed += 1
        
        await update_job_status(
            job_id,
            JobStatus.FAILED,
            error={
                "message": str(e),
                "type": type(e).__name__
            }
        )
        raise
    
    finally:
        # ===== P1 Optimization: Garbage Collection Aggressivo =====
        # Libera memória agressivamente após processar job
        import gc
        collected = gc.collect()
        logger.debug(f"🗑️ GC liberou {collected} objetos")


@celery_app.task(name='app.infrastructure.celery_tasks.cleanup_temp_files')
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


@celery_app.task(name='app.infrastructure.celery_tasks.cleanup_old_shorts')
def cleanup_old_shorts():
    """Limpa shorts não usados há muito tempo"""
    logger.info("🧹 Running shorts cache cleanup...")
    
    settings = get_settings()
    _, _, _, shorts_cache, _ = get_instances()
    
    days = settings['cleanup_shorts_cache_after_days']
    removed_count = shorts_cache.cleanup_old(days=days)
    
    logger.info(f"✅ Cleanup complete: {removed_count} old shorts removed")


@celery_app.task(name='app.infrastructure.celery_tasks.recover_orphaned_jobs')
def recover_orphaned_jobs():
    """
    Auto-recovery de jobs órfãos (Sprint-01)
    
    Detecta jobs travados em processamento há mais de 5 minutos
    e força sua re-execução do ponto onde pararam.
    
    Execução: A cada 2 minutos (Celery Beat)
    """
    logger.info("🔍 [AUTO-RECOVERY] Starting orphaned jobs detection...")
    
    settings = get_settings()
    store, _, _, _, _ = get_instances()
    
    # Configurável via env (default: 5 minutos)
    max_age_minutes = int(settings.get('orphan_detection_threshold_minutes', 5))
    
    try:
        # Detectar jobs órfãos
        orphaned_jobs = asyncio.run(store.find_orphaned_jobs(max_age_minutes=max_age_minutes))
        
        # Metrics (Sprint-05)
        _metrics.orphans_detected += len(orphaned_jobs)
        
        if not orphaned_jobs:
            logger.debug("✅ [AUTO-RECOVERY] No orphaned jobs found")
            return {
                "status": "success",
                "orphaned_count": 0,
                "recovered_count": 0,
                "failed_count": 0
            }
        
        logger.warning(f"⚠️ [AUTO-RECOVERY] Found {len(orphaned_jobs)} orphaned jobs (older than {max_age_minutes}min)")
        
        recovered_count = 0
        failed_count = 0
        
        for job in orphaned_jobs:
            age_minutes = (datetime.utcnow() - job.updated_at).total_seconds() / 60
            
            logger.info(
                f"🔧 [AUTO-RECOVERY] Attempting recovery of job {job.job_id} "
                f"(status={job.status}, age={age_minutes:.1f}min)"
            )
            
            try:
                # Tentar recuperar job
                success = asyncio.run(_recover_single_job(job))
                
                if success:
                    recovered_count += 1
                    _metrics.orphans_recovered += 1  # Metrics (Sprint-05)
                    logger.info(f"✅ [AUTO-RECOVERY] Job {job.job_id} recovered successfully")
                else:
                    failed_count += 1
                    _metrics.orphans_failed += 1  # Metrics (Sprint-05)
                    logger.error(f"❌ [AUTO-RECOVERY] Job {job.job_id} recovery failed")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ [AUTO-RECOVERY] Error recovering job {job.job_id}: {e}", exc_info=True)
        
        result = {
            "status": "completed",
            "orphaned_count": len(orphaned_jobs),
            "recovered_count": recovered_count,
            "failed_count": failed_count
        }
        
        logger.info(
            f"📊 [AUTO-RECOVERY] Complete: "
            f"{recovered_count} recovered, {failed_count} failed out of {len(orphaned_jobs)} orphaned"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [AUTO-RECOVERY] Critical error in recovery task: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


async def _recover_single_job(job: Job) -> bool:
    """
    Recupera um job individual do ponto onde parou
    
    Estratégia:
    1. Identificar última etapa completada via checkpoint
    2. Validar arquivos/dados dessa etapa
    3. Re-submeter job para continuar da próxima etapa
    
    Args:
        job: Job órfão a ser recuperado
    
    Returns:
        True se recuperado com sucesso, False caso contrário
    """
    store, _, _, _, _ = get_instances()
    settings = get_settings()
    
    try:
        # Carregar checkpoint (se existir)
        checkpoint = await _load_checkpoint(job.job_id)
        
        if not checkpoint:
            logger.warning(
                f"⚠️ [RECOVERY] No checkpoint found for {job.job_id}, "
                f"will restart from beginning"
            )
            checkpoint = {"completed_stages": []}
        
        logger.info(
            f"📍 [RECOVERY] Job {job.job_id} checkpoint: "
            f"completed stages: {checkpoint.get('completed_stages', [])}"
        )
        
        # Determinar próxima etapa a executar
        current_stage = job.status.value if job.status else "queued"
        next_stage = _determine_next_stage(current_stage, checkpoint)
        
        if not next_stage:
            # Job já estava em etapa final, marcar como failed
            logger.warning(
                f"⚠️ [RECOVERY] Job {job.job_id} was in final stage, marking as failed"
            )
            await update_job_status(
                job.job_id,
                JobStatus.FAILED,
                error={
                    "message": "Job orphaned in final stage, likely worker crash",
                    "recovery_attempted": True,
                    "original_stage": current_stage
                }
            )
            return False
        
        logger.info(f"🎯 [RECOVERY] Job {job.job_id} will resume from stage: {next_stage}")
        
        # Validar que arquivos/dados necessários existem
        validation_result = await _validate_job_prerequisites(job, next_stage)
        
        if not validation_result["valid"]:
            logger.error(
                f"❌ [RECOVERY] Job {job.job_id} prerequisite validation failed: "
                f"{validation_result['reason']}"
            )
            await update_job_status(
                job.job_id,
                JobStatus.FAILED,
                error={
                    "message": "Recovery failed: missing prerequisites",
                    "details": validation_result,
                    "recovery_attempted": True
                }
            )
            return False
        
        # Atualizar job para status "queued" para re-processamento
        job.status = JobStatus.QUEUED
        job.progress = _stage_to_progress(next_stage)
        job.updated_at = datetime.utcnow()
        
        # Salvar metadata de recuperação
        if not job.error:
            job.error = {}
        job.error["recovery_info"] = {
            "recovered_at": datetime.utcnow().isoformat(),
            "original_stage": current_stage,
            "resume_stage": next_stage.value if hasattr(next_stage, 'value') else str(next_stage),
            "age_minutes": (datetime.utcnow() - job.updated_at).total_seconds() / 60
        }
        
        await store.save_job(job)
        
        # Re-submeter job para Celery
        process_make_video.apply_async(
            args=[job.job_id],
            queue='make_video_queue'
        )
        
        logger.info(f"✅ [RECOVERY] Job {job.job_id} re-submitted successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ [RECOVERY] Error recovering job {job.job_id}: {e}", exc_info=True)
        return False


def _determine_next_stage(current_stage: str, checkpoint: dict) -> Optional[JobStatus]:
    """
    Determina próxima etapa a executar baseado em checkpoint
    
    Args:
        current_stage: Etapa atual (onde travou)
        checkpoint: Checkpoint com etapas completadas
    
    Returns:
        Nome da próxima etapa ou None se já estava no final
    """
    completed = set(checkpoint.get('completed_stages', []))
    
    # Mapeamento de stages em ordem
    stage_flow = [
        JobStatus.QUEUED,
        JobStatus.ANALYZING_AUDIO,
        JobStatus.FETCHING_SHORTS,
        JobStatus.DOWNLOADING_SHORTS,
        JobStatus.SELECTING_SHORTS,
        JobStatus.ASSEMBLING_VIDEO,
        JobStatus.GENERATING_SUBTITLES,
        JobStatus.FINAL_COMPOSITION,
    ]
    
    # Encontrar índice da stage atual
    try:
        if current_stage == "processing":
            # Status genérico, retornar primeira não completada
            for stage in stage_flow:
                if stage.value not in completed:
                    return stage
            return None
        
        current_idx = next(
            i for i, stage in enumerate(stage_flow)
            if stage.value == current_stage
        )
        
        # Retornar próxima stage
        if current_idx + 1 < len(stage_flow):
            return stage_flow[current_idx + 1]
        else:
            return None  # Já estava na última stage
            
    except StopIteration:
        # Stage desconhecida, começar do início
        return JobStatus.QUEUED


async def _validate_job_prerequisites(job: Job, next_stage: JobStatus) -> dict:
    """
    Valida que pré-requisitos para a próxima etapa existem
    
    Args:
        job: Job a ser validado
        next_stage: Próxima etapa a executar
    
    Returns:
        {"valid": bool, "reason": str}
    """
    settings = get_settings()
    
    try:
        # Validar baseado na próxima stage
        if next_stage == JobStatus.QUEUED:
            # Início, sem pré-requisitos
            return {"valid": True}
        
        if next_stage == JobStatus.ANALYZING_AUDIO:
            # Precisa de áudio
            audio_path = Path(settings['audio_upload_dir']) / job.job_id / "audio"
            
            # Procurar por extensões comuns
            found = False
            for ext in ['.mp3', '.wav', '.m4a', '.ogg', '']:
                test_path = audio_path.parent / f"audio{ext}"
                if test_path.exists():
                    found = True
                    break
            
            if not found:
                return {"valid": False, "reason": "Audio file not found"}
            return {"valid": True}
        
        if next_stage == JobStatus.FETCHING_SHORTS:
            # Precisa de audio_duration preenchido
            if not job.audio_duration:
                return {"valid": False, "reason": "Audio duration not analyzed"}
            return {"valid": True}
        
        if next_stage == JobStatus.DOWNLOADING_SHORTS:
            # Pode continuar, já tem query
            return {"valid": True}
        
        if next_stage == JobStatus.SELECTING_SHORTS:
            # Verificar se tem shorts baixados
            shorts_cache_dir = Path(settings['shorts_cache_dir'])
            if not shorts_cache_dir.exists() or not list(shorts_cache_dir.glob("*.mp4")):
                return {"valid": False, "reason": "No shorts available in cache"}
            return {"valid": True}
        
        if next_stage == JobStatus.ASSEMBLING_VIDEO:
            # Precisa de shorts selecionados (verificar em checkpoint futuro)
            return {"valid": True}
        
        if next_stage == JobStatus.GENERATING_SUBTITLES:
            # Precisa de vídeo intermediário
            temp_video = Path(settings['temp_dir']) / job.job_id / "video_no_audio.mp4"
            if not temp_video.exists():
                return {"valid": False, "reason": "Intermediate video not found"}
            return {"valid": True}
        
        if next_stage == JobStatus.FINAL_COMPOSITION:
            # Precisa de vídeo com áudio e legendas
            video_with_audio = Path(settings['temp_dir']) / job.job_id / "video_with_audio.mp4"
            subtitle_file = Path(settings['temp_dir']) / job.job_id / "subtitles.srt"
            
            if not video_with_audio.exists():
                return {"valid": False, "reason": "Video with audio not found"}
            if not subtitle_file.exists():
                return {"valid": False, "reason": "Subtitle file not found"}
            return {"valid": True}
        
        # Default: válido
        return {"valid": True}
        
    except Exception as e:
        logger.error(f"Error validating prerequisites: {e}")
        return {"valid": False, "reason": f"Validation error: {str(e)}"}


def _stage_to_progress(stage: JobStatus) -> float:
    """Mapeia stage para porcentagem de progresso"""
    stage_progress = {
        JobStatus.QUEUED: 0.0,
        JobStatus.ANALYZING_AUDIO: 5.0,
        JobStatus.FETCHING_SHORTS: 15.0,
        JobStatus.DOWNLOADING_SHORTS: 30.0,
        JobStatus.SELECTING_SHORTS: 70.0,
        JobStatus.ASSEMBLING_VIDEO: 75.0,
        JobStatus.GENERATING_SUBTITLES: 80.0,
        JobStatus.FINAL_COMPOSITION: 85.0,
    }
    return stage_progress.get(stage, 0.0)


# Funções auxiliares de checkpoint (Sprint-01)

async def _save_checkpoint(job_id: str, completed_stage: str):
    """Salva checkpoint de progresso"""
    store, _, _, _, _ = get_instances()
    key = f"make_video:checkpoint:{job_id}"
    
    try:
        # Carregar checkpoint existente
        existing_data = store.redis.get(key)
        if existing_data:
            checkpoint = json.loads(existing_data)
        else:
            checkpoint = {"completed_stages": []}
        
        # Adicionar stage completada
        if completed_stage not in checkpoint["completed_stages"]:
            checkpoint["completed_stages"].append(completed_stage)
        
        checkpoint["last_updated"] = datetime.utcnow().isoformat()
        
        # Salvar com TTL de 48 horas
        store.redis.setex(key, 172800, json.dumps(checkpoint))
        
        logger.debug(f"💾 [CHECKPOINT] Saved for {job_id}: stage={completed_stage}")
        
    except Exception as e:
        logger.error(f"Error saving checkpoint for {job_id}: {e}")


async def _load_checkpoint(job_id: str) -> Optional[dict]:
    """Carrega checkpoint de progresso"""
    store, _, _, _, _ = get_instances()
    key = f"make_video:checkpoint:{job_id}"
    
    try:
        data = store.redis.get(key)
        if data:
            return json.loads(data)
        return None
        
    except Exception as e:
        logger.error(f"Error loading checkpoint for {job_id}: {e}")
        return None


async def _delete_checkpoint(job_id: str):
    """Deleta checkpoint após job completar"""
    store, _, _, _, _ = get_instances()
    key = f"make_video:checkpoint:{job_id}"
    
    try:
        store.redis.delete(key)
        logger.debug(f"🗑️ [CHECKPOINT] Deleted for {job_id}")
    except Exception as e:
        logger.error(f"Error deleting checkpoint for {job_id}: {e}")


# =============================================================================
# SPRINT-02: Granular Stage Checkpoints
# =============================================================================

async def _save_stage_checkpoint(job_id: str, stage: str, data: dict):
    """Save granular checkpoint within a stage (Sprint-02)"""
    store, _, _, _, _ = get_instances()
    key = f"make_video:stage_checkpoint:{job_id}:{stage}"
    
    try:
        checkpoint = {
            "stage": stage,
            "data": data,
            "last_updated": datetime.utcnow().isoformat()
        }
        store.redis.setex(key, 172800, json.dumps(checkpoint))
        logger.debug(f"💾 [STAGE-CP] {stage}: {len(data.get('downloaded_ids', []))} items")
    except Exception as e:
        logger.error(f"Error saving stage checkpoint: {e}")


async def _load_stage_checkpoint(job_id: str, stage: str) -> Optional[dict]:
    """Load granular checkpoint within a stage (Sprint-02)"""
    store, _, _, _, _ = get_instances()
    key = f"make_video:stage_checkpoint:{job_id}:{stage}"
    
    try:
        data = store.redis.get(key)
        if data:
            checkpoint = json.loads(data)
            return checkpoint.get('data')
        return None
    except Exception as e:
        logger.error(f"Error loading stage checkpoint: {e}")
        return None


async def _delete_stage_checkpoint(job_id: str, stage: str):
    """Delete stage checkpoint (Sprint-02)"""
    store, _, _, _, _ = get_instances()
    key = f"make_video:stage_checkpoint:{job_id}:{stage}"
    
    try:
        store.redis.delete(key)
        logger.debug(f"🗑️ [STAGE-CP] Deleted {stage}")
    except Exception as e:
        logger.error(f"Error deleting stage checkpoint: {e}")


# =============================================================================
# SPRINT-03: Smart Timeout Management
# =============================================================================

def _calculate_stage_timeout(
    stage: JobStatus,
    audio_duration: float = 0.0,
    max_shorts: int = 10,
    retry_count: int = 0
) -> int:
    """Calculate dynamic timeout for stage (Sprint-03)"""
    
    base_timeouts = {
        JobStatus.QUEUED: 10,
        JobStatus.ANALYZING_AUDIO: 30,
        JobStatus.FETCHING_SHORTS: 60,
        JobStatus.DOWNLOADING_SHORTS: 300,
        JobStatus.SELECTING_SHORTS: 10,
        JobStatus.ASSEMBLING_VIDEO: 120,
        JobStatus.GENERATING_SUBTITLES: 180,
        JobStatus.FINAL_COMPOSITION: 300,
    }
    
    base = base_timeouts.get(stage, 300)
    
    # Dynamic scaling
    if stage == JobStatus.ANALYZING_AUDIO:
        timeout = base + int(audio_duration * 2)
    elif stage == JobStatus.FETCHING_SHORTS:
        timeout = base + (max_shorts * 5)
    elif stage == JobStatus.DOWNLOADING_SHORTS:
        timeout = base + (max_shorts * 10)
    elif stage == JobStatus.GENERATING_SUBTITLES:
        timeout = base + int(audio_duration * 30)
    elif stage == JobStatus.FINAL_COMPOSITION:
        timeout = base + int(audio_duration * 10)
    else:
        timeout = base
    
    # Retry escalation
    timeout = int(timeout * (1.5 ** retry_count))
    
    # Cap at 30 minutes
    return min(timeout, 1800)


# =============================================================================
# SPRINT-04: Circuit Breaker (Simplified)
# =============================================================================

class SimpleCircuitBreaker:
    """Simplified circuit breaker for external services (Sprint-04)"""
    
    def __init__(self, failure_threshold: int = 5):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.last_failure_time = None
        self.is_open = False
    
    def record_success(self):
        self.failure_count = 0
        self.is_open = False
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.error(f"🔌 [CIRCUIT] Opened after {self.failure_count} failures")
    
    def should_allow_request(self) -> bool:
        if not self.is_open:
            return True
        
        # Auto-reset after 60s
        if self.last_failure_time:
            elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
            if elapsed > 60:
                self.is_open = False
                self.failure_count = 0
                logger.info("🔌 [CIRCUIT] Attempting reset")
                return True
        
        return False


# Global circuit breakers
_circuit_breakers = {
    "download": SimpleCircuitBreaker(failure_threshold=10),
    "transcription": SimpleCircuitBreaker(failure_threshold=3),
}


# =============================================================================
# SPRINT-05: Metrics (In-memory counters, ready for Prometheus)
# =============================================================================

class SimpleMetrics:
    """Simple metrics tracking (Sprint-05)"""
    
    def __init__(self):
        self.jobs_started = 0
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.orphans_detected = 0
        self.orphans_recovered = 0
        self.orphans_failed = 0
    
    def reset(self):
        self.__init__()


_metrics = SimpleMetrics()
