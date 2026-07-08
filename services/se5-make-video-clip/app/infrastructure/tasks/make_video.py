"""Make-video pipeline task."""
from __future__ import annotations

import asyncio
import random
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Any

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from ..celery_config import celery_app
from ...core.config import get_settings
from ...core.models import Job, JobStatus, ShortInfo, JobResult
from ...shared.exceptions import MakeVideoException
from ...shared.exceptions_v2 import (
    AudioException as AudioProcessingException,
    VideoException as VideoProcessingException,
    SubtitleGenerationException,
    MicroserviceException,
    ErrorCode
)
from ...shared.events import EventPublisher
from ...shared.domain_integration import process_job_with_domain
from ..instances import get_instances
from ..base import update_job_status
from ..checkpoint import save_checkpoint, delete_checkpoint
from ..file_logger import FileLogger
from ..simple_metrics import simple_metrics as _metrics

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name='app.infrastructure.celery_tasks.process_make_video',
    time_limit=3600,
    soft_time_limit=3300,
    acks_late=True,
    reject_on_worker_lost=True
)
def process_make_video(self, job_id: str) -> None:
    """Task principal: Processa criação de vídeo completa."""
    logger.info(f"🎬 Starting make-video job: {job_id}")

    settings = get_settings()
    use_domain = settings.get('use_domain_driven_architecture', False)

    if use_domain:
        logger.info(f"🏗️  Using Domain-Driven Architecture")

    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if use_domain:
            loop.run_until_complete(_process_make_video_with_domain(job_id))
        else:
            loop.run_until_complete(_process_make_video_async(job_id))

    except Exception as e:
        logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        store, _, _, _, _ = get_instances()
        existing_job = store.get_job(job_id)

        if existing_job and existing_job.status == JobStatus.FAILED and existing_job.error:
            logger.info(
                f"ℹ️ Preserving existing structured error for job {job_id}: "
                f"{existing_job.error.get('message', 'n/a')}"
            )
            return

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


async def _process_make_video_with_domain(job_id: str) -> Any:
    """Processamento assíncrono usando Domain-Driven Design."""
    store, api_client, video_builder, shorts_cache, subtitle_gen = get_instances()
    settings = get_settings()

    from ..instances import video_validator, blacklist
    if video_validator is None or blacklist is None:
        get_instances()

    event_publisher = EventPublisher(redis_url=settings['redis_url'])

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


async def _process_make_video_async(job_id: str) -> None:
    """Processamento assíncrono do vídeo (implementação legada)."""
    from ..helpers import transform_crop_and_validate_video
    from ..instances import video_validator, blacklist

    job_logger = FileLogger.get_job_logger(job_id)
    job_logger.info("="*80)
    job_logger.info(f"🎬 STARTING MAKE-VIDEO JOB: {job_id}")
    job_logger.info("="*80)

    store, api_client, video_builder, shorts_cache, subtitle_gen = get_instances()
    settings = get_settings()

    job_logger.debug(f"Settings loaded: {list(settings.keys())}")

    job = store.get_job(job_id)
    if not job:
        job_logger.error(f"❌ Job {job_id} not found in Redis")
        raise MakeVideoException(f"Job {job_id} not found")

    job_logger.info(f"Job loaded: max_shorts={job.max_shorts} (no query - uses approved videos)")

    try:
        from ..pipeline.video_pipeline import VideoPipeline
        pipeline = VideoPipeline()
        pipeline.cleanup_stale_validations(job_id, max_age_minutes=30)
        pipeline.cleanup_orphaned_files(max_age_minutes=30)
        job_logger.info("🧹 Cleanup completed: stale files removed from all pipeline folders")
    except Exception as e:
        job_logger.warning(f"⚠️  Cleanup warning: {e}")

    try:
        # Etapa 1: Analisar áudio
        logger.info(f"📊 [1/7] Analyzing audio...")
        await update_job_status(job_id, JobStatus.ANALYZING_AUDIO, progress=5.0)

        audio_dir = Path(settings['audio_upload_dir'])
        audio_path = None
        for ext in ['.ogg', '.mp3', '.wav', '.m4a']:
            test_path = audio_dir / f"{job_id}{ext}"
            if test_path.exists():
                audio_path = test_path
                break

        if not audio_path:
            raise AudioProcessingException(f"Audio file not found for job {job_id}")

        audio_duration = await video_builder.get_audio_duration(str(audio_path))

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

        padding_ms = int(settings.get('video_trim_padding_ms', 1000))
        padding_seconds = padding_ms / 1000.0
        target_duration = audio_duration + padding_seconds

        job.audio_duration = audio_duration
        job.target_video_duration = target_duration
        store.save_job(job)

        logger.info(f"🎵 Audio: {audio_duration:.1f}s + {padding_seconds:.2f}s padding → Target: {target_duration:.1f}s")

        await save_checkpoint(job_id, "analyzing_audio_completed")

        # Etapa 2: Buscar shorts APROVADOS
        logger.info(f"🔍 [2/7] Fetching approved shorts from data/approved/videos/...")
        await update_job_status(job_id, JobStatus.FETCHING_SHORTS, progress=15.0)

        approved_dir = Path("data/approved/videos")
        if not approved_dir.exists():
            raise VideoProcessingException(
                "No approved videos folder found. Run /download first to get approved videos.",
                ErrorCode.NO_SHORTS_FOUND
            )

        approved_files = list(approved_dir.glob("*.mp4"))
        if not approved_files:
            raise VideoProcessingException(
                "No approved videos available. Run /download first to get approved videos.",
                ErrorCode.NO_SHORTS_FOUND
            )

        shorts_list = []
        for video_file in approved_files:
            video_id = video_file.stem
            shorts_list.append({
                'video_id': video_id,
                'url': f'https://www.youtube.com/shorts/{video_id}',
                'title': f'Approved short: {video_id}',
                'duration': None
            })

        logger.info(f"✅ Found {len(shorts_list)} approved shorts in data/approved/videos/")
        job_logger.info(f"✅ Found {len(shorts_list)} approved shorts: {[s['video_id'] for s in shorts_list[:5]]}...")

        if not shorts_list:
            raise VideoProcessingException(
                "No approved shorts found in data/approved/videos/",
                ErrorCode.NO_SHORTS_FOUND
            )

        await save_checkpoint(job_id, "fetching_shorts_completed")

        # Etapa 3: USAR VÍDEOS APROVADOS
        job_logger.info("="*60)
        job_logger.info(f"📦 [3/7] USING APPROVED VIDEOS FROM data/approved/videos/")
        job_logger.info("="*60)
        logger.info(f"📦 [3/7] Using pre-approved videos...")
        await update_job_status(job_id, JobStatus.DOWNLOADING_SHORTS, progress=25.0)

        approved_shorts = []
        approved_dir = Path("data/approved/videos")

        for short_info in shorts_list:
            video_id = short_info['video_id']
            video_path = approved_dir / f"{video_id}.mp4"

            if not video_path.exists():
                job_logger.warning(f"⚠️ Approved video not found: {video_id}")
                continue

            try:
                video_info = await video_builder.get_video_info(str(video_path))
                duration = video_info['duration']

                approved_shorts.append({
                    'video_id': video_id,
                    'duration_seconds': duration,
                    'file_path': str(video_path),
                    'resolution': video_info.get('resolution', '1080x1920'),
                    'fps': int(video_info.get('fps', 30)),
                    'title': short_info.get('title', '')
                })

                job_logger.debug(f"✅ Loaded approved video: {video_id} ({duration:.1f}s)")

            except Exception as e:
                job_logger.warning(f"⚠️ Error reading video {video_id}: {e}")
                continue

        logger.info(f"📦 Loaded {len(approved_shorts)} approved videos from data/approved/videos/")

        if not approved_shorts:
            raise VideoProcessingException(
                "No approved videos could be loaded",
                ErrorCode.NO_VALID_SHORTS
            )

        total_available = sum(s['duration_seconds'] for s in approved_shorts)
        logger.info(f"📊 Total available duration: {total_available:.1f}s (need {target_duration:.1f}s)")

        await update_job_status(job_id, JobStatus.DOWNLOADING_SHORTS, progress=60.0)
        await save_checkpoint(job_id, "downloading_shorts_completed")

        # Etapa 4: Selecionar shorts aleatoriamente
        logger.info(f"🎲 [4/7] Selecting shorts randomly...")
        await update_job_status(job_id, JobStatus.SELECTING_SHORTS, progress=70.0)

        logger.info(f"📊 DEBUG: approved_shorts count = {len(approved_shorts)}, target_duration = {target_duration:.1f}s")
        for i, s in enumerate(approved_shorts[:10]):
            logger.info(f"  [{i}] {s['video_id']}: {s['duration_seconds']:.1f}s")

        random.shuffle(approved_shorts)

        selected_shorts = []
        total_duration = 0.0

        for short in approved_shorts:
            if total_duration >= target_duration:
                logger.info(f"🎯 Breaking loop: total_duration={total_duration:.1f}s >= target_duration={target_duration:.1f}s")
                break
            selected_shorts.append(short)
            total_duration += short['duration_seconds']
            logger.info(f"  ✓ Added {short['video_id']}: {short['duration_seconds']:.1f}s (cumulative: {total_duration:.1f}s)")

        logger.info(f"🎯 Selected {len(selected_shorts)} shorts ({total_duration:.1f}s / target {target_duration:.1f}s)")

        if not selected_shorts:
            raise VideoProcessingException(
                "No shorts available for video creation",
                ErrorCode.NO_VALID_SHORTS
            )

        if total_duration < audio_duration:
            logger.warning(
                f"⚠️ Selected shorts duration ({total_duration:.1f}s) less than audio duration ({audio_duration:.1f}s). "
                f"Video may need padding or you may need to run /download to get more approved videos."
            )

        await save_checkpoint(job_id, "selecting_shorts_completed")

        # Etapa 5: Montar vídeo (sem áudio)
        logger.info(f"🎬 [5/7] Assembling video...")
        await update_job_status(job_id, JobStatus.ASSEMBLING_VIDEO, progress=75.0)

        video_files = [s['file_path'] for s in selected_shorts]
        temp_video_path = Path("/tmp/make-video-temp") / job_id / "video_no_audio.mp4"
        temp_video_path.parent.mkdir(parents=True, exist_ok=True)

        await video_builder.concatenate_videos(
            video_files=video_files,
            output_path=str(temp_video_path),
            aspect_ratio=job.aspect_ratio,
            crop_position=job.crop_position,
            remove_audio=True
        )

        logger.info(f"✅ Video assembled: {temp_video_path}")

        # Validação pós-concatenação
        concat_info = await video_builder.get_video_info(str(temp_video_path))
        concat_duration = concat_info['duration']
        expected_duration = sum(s['duration_seconds'] for s in selected_shorts)

        logger.info(f"📊 CONCATENATION VALIDATION:")
        logger.info(f"   ├─ Expected: {expected_duration:.2f}s (sum of {len(selected_shorts)} shorts)")
        logger.info(f"   └─ Actual: {concat_duration:.2f}s")

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
                ErrorCode.CONCATENATION_FAILED,
                details={
                    "expected_duration": expected_duration,
                    "actual_duration": concat_duration,
                    "difference": concat_diff,
                    "tolerance": concat_tolerance,
                    "shorts_count": len(selected_shorts),
                    "conclusion": "Frame duplication during concatenation. Check FFmpeg concat filter."
                }
            )

        logger.info(f"✅ CONCATENATION VALIDATION PASSED: Duration OK ({concat_duration:.2f}s ≈ {expected_duration:.2f}s)")

        await save_checkpoint(job_id, "assembling_video_completed")

        # Etapa 6: Gerar legendas
        logger.info(f"📝 [6/7] Generating subtitles...")
        await update_job_status(job_id, JobStatus.GENERATING_SUBTITLES, progress=80.0)

        segments = []
        retry_attempt = 0
        max_backoff = 300
        MAX_SUBTITLE_RETRIES = 5

        while not segments and retry_attempt < MAX_SUBTITLE_RETRIES:
            retry_attempt += 1

            try:
                if retry_attempt > 1:
                    logger.info(f"🔄 Subtitle generation retry #{retry_attempt}")
                    await update_job_status(
                        job_id,
                        JobStatus.GENERATING_SUBTITLES,
                        progress=80.0,
                        stage_updates={
                            "generating_subtitles": {
                                "status": "retrying",
                                "metadata": {
                                    "retry_attempt": retry_attempt,
                                    "reason": "Previous attempt failed or timed out"
                                }
                            }
                        }
                    )

                segments = await api_client.transcribe_audio(str(audio_path), job.subtitle_language)
                logger.info(f"✅ Subtitles generated: {len(segments)} segments (attempt #{retry_attempt})")

            except MicroserviceException as e:
                backoff_seconds = min(5 * (2 ** (retry_attempt - 1)), max_backoff)

                logger.warning(
                    f"⚠️ Subtitle generation failed (attempt #{retry_attempt}): {e}",
                    exc_info=False
                )
                logger.info(f"🔄 Retrying in {backoff_seconds}s...")

                await update_job_status(
                    job_id,
                    JobStatus.GENERATING_SUBTITLES,
                    progress=80.0,
                    stage_updates={
                        "generating_subtitles": {
                            "status": "waiting_retry",
                            "metadata": {
                                "retry_attempt": retry_attempt,
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "retry_in_seconds": backoff_seconds,
                                "next_retry_at": (now_brazil() + timedelta(seconds=backoff_seconds)).isoformat()
                            }
                        }
                    }
                )

                await asyncio.sleep(backoff_seconds)

            except Exception as e:
                backoff_seconds = min(5 * (2 ** (retry_attempt - 1)), max_backoff)

                logger.warning(
                    f"⚠️ Unexpected error during subtitle generation (attempt #{retry_attempt}): {e}",
                    exc_info=True
                )
                logger.info(f"🔄 Retrying in {backoff_seconds}s...")

                await update_job_status(
                    job_id,
                    JobStatus.GENERATING_SUBTITLES,
                    progress=80.0,
                    stage_updates={
                        "generating_subtitles": {
                            "status": "waiting_retry",
                            "metadata": {
                                "retry_attempt": retry_attempt,
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "retry_in_seconds": backoff_seconds,
                                "next_retry_at": (now_brazil() + timedelta(seconds=backoff_seconds)).isoformat()
                            }
                        }
                    }
                )

                await asyncio.sleep(backoff_seconds)

        if not segments or len(segments) == 0:
            error_details = {
                "retry_attempts": retry_attempt,
                "max_retries": MAX_SUBTITLE_RETRIES,
                "last_error": "Subtitle generation failed after maximum retries",
                "segments_received": len(segments) if segments else 0,
                "audio_duration": audio_duration,
                "subtitle_language": job.subtitle_language,
                "recommendation": "Check audio-transcriber service health and logs"
            }
            logger.error(
                f"❌ CRITICAL: Failed to generate subtitles after {MAX_SUBTITLE_RETRIES} attempts. "
                f"Segments received: {len(segments) if segments else 0}. "
                f"Audio transcriber may be down or misconfigured."
            )
            raise SubtitleGenerationException(
                reason=f"Failed to generate subtitles after {MAX_SUBTITLE_RETRIES} retry attempts",
                subtitle_path="N/A",
                details=error_details
            )

        # Conversão: Segments → Word Cues
        from ..services.subtitle_generator import segments_to_weighted_word_cues

        raw_cues = []

        has_word_timestamps = any(segment.get('words') for segment in segments)

        if has_word_timestamps:
            logger.info("✅ Using word-level timestamps from Whisper")
            for segment in segments:
                words = segment.get('words', [])
                for word_data in words:
                    raw_cues.append({
                        'start': word_data['start'],
                        'end': word_data['end'],
                        'text': word_data['word']
                    })
        else:
            logger.info("🔧 Using weighted timestamps by word length")
            raw_cues = segments_to_weighted_word_cues(segments)

        logger.info(f"📊 Transcription: {len(segments)} segments, {len(raw_cues)} words")

        if segments:
            logger.info(f"DEBUG first segment: {segments[0]}")
        else:
            logger.error("❌ NO SEGMENTS from transcriber!")

        if not raw_cues or len(raw_cues) == 0:
            error_details = {
                "segments_count": len(segments),
                "raw_cues_count": len(raw_cues) if raw_cues else 0,
                "has_word_timestamps": has_word_timestamps,
                "first_segment": segments[0] if segments else None,
                "problem": "No valid word cues extracted from transcription segments",
                "recommendation": "Check transcription format and word-level timestamp availability"
            }
            logger.error(
                f"❌ CRITICAL: NO WORDS extracted from {len(segments)} segments! "
                f"has_word_timestamps={has_word_timestamps}"
            )
            raise SubtitleGenerationException(
                reason="No valid word cues extracted from transcription",
                subtitle_path="N/A",
                details=error_details
            )

        # Aplicar speech-gated subtitles (VAD)
        logger.info(f"🎙️ [6.5/7] Applying speech gating (VAD)...")
        await update_job_status(job_id, JobStatus.GENERATING_SUBTITLES, progress=82.0)

        try:
            from ..services.subtitle_postprocessor import process_subtitles_with_vad
            gated_cues, vad_ok = process_subtitles_with_vad(str(audio_path), raw_cues)

            if vad_ok:
                logger.info(f"✅ Speech gating OK: {len(gated_cues)}/{len(raw_cues)} cues (silero-vad)")
            else:
                logger.warning(f"⚠️ Speech gating fallback: {len(gated_cues)}/{len(raw_cues)} cues (webrtcvad/RMS)")

            final_cues = gated_cues

        except Exception as e:
            logger.error(f"⚠️ Speech gating failed: {e}, usando cues originais")
            final_cues = raw_cues
            vad_ok = False

        # Gerar SRT direto dos final_cues
        subtitle_path = Path('/tmp/make-video-temp') / job_id / "subtitles.srt"
        words_per_caption = int(settings.get('words_per_caption', 2))

        logger.info(f"DEBUG: final_cues count = {len(final_cues)}")
        if not final_cues:
            logger.error("❌ CRITICAL: final_cues is EMPTY! Cannot generate SRT!")
            raise SubtitleGenerationException(
                reason="No valid subtitle cues after speech gating (VAD processing)",
                subtitle_path=str(subtitle_path),
                details={
                    "raw_cues_count": len(raw_cues),
                    "final_cues_count": 0,
                    "vad_ok": vad_ok,
                    "problem": "All subtitle cues were filtered out during VAD processing",
                    "recommendation": "Check VAD threshold settings or audio quality"
                }
            )

        from ..services.subtitle_generator import write_srt_from_word_cues

        write_srt_from_word_cues(
            final_cues,
            str(subtitle_path),
            words_per_caption=words_per_caption
        )

        if subtitle_path.exists():
            srt_size = subtitle_path.stat().st_size
            logger.info(f"DEBUG: SRT file created, size = {srt_size} bytes")
            if srt_size == 0:
                logger.error("❌ CRITICAL: SRT file is EMPTY (0 bytes)!")
        else:
            logger.error(f"❌ CRITICAL: SRT file NOT created at {subtitle_path}!")

        num_captions_expected = len(final_cues) // words_per_caption
        logger.info(
            f"✅ Speech-gated subtitles: {len(final_cues)} words → "
            f"~{num_captions_expected} captions, {words_per_caption} words/caption, "
            f"vad_ok={vad_ok}, timestamps_preserved=True"
        )

        await save_checkpoint(job_id, "generating_subtitles_completed")

        # Etapa 7: Composição final
        logger.info(f"🎨 [7/7] Final composition...")
        await update_job_status(job_id, JobStatus.FINAL_COMPOSITION, progress=85.0)

        video_with_audio_path = Path('/tmp/make-video-temp') / job_id / "video_with_audio.mp4"
        await video_builder.add_audio(
            video_path=str(temp_video_path),
            audio_path=str(audio_path),
            output_path=str(video_with_audio_path)
        )

        logger.info(f"✅ Audio added")

        final_video_path = Path(settings['output_dir']) / f"{job_id}_final.mp4"
        await video_builder.burn_subtitles(
            video_path=str(video_with_audio_path),
            subtitle_path=str(subtitle_path),
            output_path=str(final_video_path),
            style=job.subtitle_style
        )

        logger.info(f"✅ Subtitles burned")

        # Validação de Sync Áudio-Vídeo
        logger.info(f"🔍 [7.5/8] Validating A/V synchronization...")

        from ..services.sync_validator import SyncValidator

        sync_validator = SyncValidator(tolerance_seconds=0.5)

        try:
            is_valid, drift, sync_metadata = await sync_validator.validate_sync(
                video_path=str(final_video_path),
                audio_path=str(audio_path),
                video_builder=video_builder,
                job_id=job_id
            )

            logger.info(
                f"✅ A/V sync validated: drift={drift:.3f}s ({sync_metadata['drift_percentage']:.2f}%)"
            )

        except Exception as sync_error:
            logger.warning(
                f"⚠️ A/V sync validation failed (non-critical): {sync_error}",
                extra={
                    "error": str(sync_error),
                    "video_path": str(final_video_path),
                    "audio_path": str(audio_path)
                }
            )

        # Etapa 8: Trimming final
        logger.info(f"✂️ [8/8] Trimming video to target duration...")
        await update_job_status(job_id, JobStatus.FINAL_COMPOSITION, progress=92.0)

        padding_ms = int(settings.get('video_trim_padding_ms', 1000))
        padding_seconds = padding_ms / 1000.0
        final_duration = audio_duration + padding_seconds

        if final_duration <= audio_duration:
            raise VideoProcessingException(
                "Invalid trim configuration: video would be shorter than or equal to audio",
                ErrorCode.INVALID_TRIM_CONFIG,
                details={
                    "audio_duration": audio_duration,
                    "padding_ms": padding_ms,
                    "final_duration": final_duration,
                    "suggestion": "Increase VIDEO_TRIM_PADDING_MS to at least 100ms"
                }
            )

        pre_trim_info = await video_builder.get_video_info(str(final_video_path))
        current_duration = pre_trim_info['duration']

        logger.info(f"📊 Trim analysis:")
        logger.info(f"   ├─ Audio duration: {audio_duration:.2f}s")
        logger.info(f"   ├─ Padding: {padding_ms}ms ({padding_seconds:.2f}s)")
        logger.info(f"   ├─ Target final: {final_duration:.2f}s")
        logger.info(f"   └─ Current video: {current_duration:.2f}s")

        if current_duration < audio_duration - 0.5:
            raise VideoProcessingException(
                f"ERRO CRÍTICO: Vídeo ({current_duration:.2f}s) é menor que áudio ({audio_duration:.2f}s)!",
                ErrorCode.INSUFFICIENT_DURATION,
                details={
                    "video_duration": current_duration,
                    "audio_duration": audio_duration,
                    "target_duration": final_duration,
                    "problem": "Vídeo não pode ser menor que áudio"
                }
            )

        if abs(current_duration - final_duration) > 0.5:
            logger.info(f"✂️ Trimming needed: {current_duration:.2f}s → {final_duration:.2f}s")

            trimmed_video_path = Path('/tmp/make-video-temp') / job_id / f"{job_id}_trimmed.mp4"

            await video_builder.trim_video(
                video_path=str(final_video_path),
                output_path=str(trimmed_video_path),
                max_duration=final_duration
            )

            shutil.move(str(trimmed_video_path), str(final_video_path))

            logger.info(f"✅ Video trimmed and replaced")
        else:
            logger.info(f"⏭️ Trim skipped: video duration ({current_duration:.2f}s) already matches target ({final_duration:.2f}s ± 0.5s)")

        video_info = await video_builder.get_video_info(str(final_video_path))
        file_size = final_video_path.stat().st_size

        # Validação final obrigatória
        final_video_duration = video_info['duration']

        logger.info(f"🎯 FINAL VALIDATION:")
        logger.info(f"   ├─ Audio duration: {audio_duration:.2f}s")
        logger.info(f"   ├─ Target (audio + padding): {final_duration:.2f}s")
        logger.info(f"   └─ Final video: {final_video_duration:.2f}s")

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
                ErrorCode.PROCESSING_STAGE_FAILED,
                details={
                    "audio_duration": audio_duration,
                    "target_duration": final_duration,
                    "actual_duration": final_video_duration,
                    "difference": duration_diff,
                    "tolerance": tolerance,
                    "conclusion": "Video processing completed but duration is incorrect. "
                                 "Check concatenation and trim steps in logs."
                }
            )

        if final_video_duration < audio_duration - 0.5:
            logger.error(
                f"❌ CRITICAL: Video ({final_video_duration:.2f}s) is shorter than audio ({audio_duration:.2f}s)!"
            )
            raise VideoProcessingException(
                "Video is shorter than audio",
                ErrorCode.INSUFFICIENT_DURATION,
                details={
                    "video_duration": final_video_duration,
                    "audio_duration": audio_duration,
                    "problem": "Video cannot be shorter than audio"
                }
            )

        logger.info(f"✅ FINAL VALIDATION PASSED: Duration OK ({final_video_duration:.2f}s ≈ {final_duration:.2f}s)")

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
            processing_time=(now_brazil() - job.created_at).total_seconds()
        )

        job.result = result
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.completed_at = now_brazil()
        job.expires_at = job.completed_at + timedelta(hours=24)
        store.save_job(job)

        await delete_checkpoint(job_id)

        _metrics.jobs_completed += 1

        logger.info(f"🎉 Job {job_id} completed successfully!")
        logger.info(f"   ├─ Duration: {result.duration:.1f}s")
        logger.info(f"   ├─ Size: {result.file_size_mb}MB")
        logger.info(f"   ├─ Shorts used: {result.shorts_used}")
        logger.info(f"   └─ Processing time: {result.processing_time:.1f}s")

        return result

    except MakeVideoException as e:
        logger.error(f"❌ MakeVideo error: {e}", exc_info=True)

        _metrics.jobs_failed += 1

        await update_job_status(
            job_id,
            JobStatus.FAILED,
            error={
                "message": e.message,
                "code": e.error_code.value if hasattr(e, 'error_code') else "UNKNOWN",
                "details": e.details if hasattr(e, 'details') else {}
            }
        )
        raise

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)

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
        try:
            from ..pipeline.video_pipeline import VideoPipeline
            pipeline_cleanup = VideoPipeline()
            pipeline_cleanup.cleanup_orphaned_files(max_age_minutes=30)
            job_logger.info("🧹 Final cleanup: orphaned files removed from all pipeline folders")
        except Exception as e:
            job_logger.warning(f"⚠️  Final cleanup warning: {e}")

        import gc
        collected = gc.collect()
        logger.debug(f"🗑️ GC liberou {collected} objetos")
