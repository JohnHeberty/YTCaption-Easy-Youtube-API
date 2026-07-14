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
from ...core.constants import BYTES_PER_MB
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

MAX_SUBTITLE_RETRIES = 5
MAX_BACKOFF_SECONDS = 300
CONCAT_TOLERANCE = 2.0
FINAL_TOLERANCE = 2.0


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
    logger.info("Starting make-video job: %s", job_id)

    settings = get_settings()
    use_domain = settings.get('use_domain_driven_architecture', False)

    if use_domain:
        logger.info("Using Domain-Driven Architecture")

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
        logger.error("Job %s failed: %s", job_id, e, exc_info=True)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        store, _, _, _, _ = get_instances()
        existing_job = store.get_job(job_id)

        if existing_job and existing_job.status == JobStatus.FAILED and existing_job.error:
            logger.info(
                "Preserving existing structured error for job %s: %s",
                job_id, existing_job.error.get('message', 'n/a')
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

    import redis.asyncio as aioredis
    redis_client = await aioredis.from_url(settings['redis_url'])
    event_publisher = EventPublisher(redis_client=redis_client)

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


# ---------------------------------------------------------------------------
#  Pipeline stage functions (extracted from _process_make_video_async)
# ---------------------------------------------------------------------------

async def _analyze_audio(
    job_id: str,
    job: Job,
    store: Any,
    video_builder: Any,
    settings: dict[str, Any],
) -> tuple[Path, float, float]:
    """Stage 1: Find audio file, validate duration, compute target.

    Returns (audio_path, audio_duration, target_duration).
    """
    logger.info("[1/7] Analyzing audio...")
    await update_job_status(job_id, JobStatus.PROCESSING, progress=5.0)

    audio_dir = Path(settings['audio_upload_dir'])
    audio_path = None
    for ext in ('.ogg', '.mp3', '.wav', '.m4a'):
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

    logger.info("Audio: %.1fs + %.2fs padding -> Target: %.1fs", audio_duration, padding_seconds, target_duration)

    await save_checkpoint(job_id, "analyzing_audio_completed")
    return audio_path, audio_duration, target_duration


async def _fetch_approved_shorts(job_id: str, job_logger: Any) -> list[dict[str, Any]]:
    """Stage 2: Discover approved video files on disk.

    Returns list of dicts with video_id, url, title, duration keys.
    """
    logger.info("[2/7] Fetching approved shorts from data/approved/videos/...")
    await update_job_status(job_id, JobStatus.PROCESSING, progress=15.0)

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

    logger.info("Found %d approved shorts in data/approved/videos/", len(shorts_list))
    job_logger.info("Found %d approved shorts: %s...", len(shorts_list), [s['video_id'] for s in shorts_list[:5]])

    if not shorts_list:
        raise VideoProcessingException(
            "No approved shorts found in data/approved/videos/",
            ErrorCode.NO_SHORTS_FOUND
        )

    await save_checkpoint(job_id, "fetching_shorts_completed")
    return shorts_list


async def _load_approved_videos(
    job_id: str,
    shorts_list: list[dict[str, Any]],
    video_builder: Any,
    job_logger: Any,
    target_duration: float,
) -> list[dict[str, Any]]:
    """Stage 3: Load metadata for each approved video.

    Returns list of dicts with video_id, duration_seconds, file_path, resolution, fps, title.
    """
    job_logger.info("=" * 60)
    job_logger.info("[3/7] USING APPROVED VIDEOS FROM data/approved/videos/")
    job_logger.info("=" * 60)
    logger.info("[3/7] Using pre-approved videos...")
    await update_job_status(job_id, JobStatus.PROCESSING, progress=25.0)

    approved_shorts = []
    approved_dir = Path("data/approved/videos")

    for short_info in shorts_list:
        video_id = short_info['video_id']
        video_path = approved_dir / f"{video_id}.mp4"

        if not video_path.exists():
            job_logger.warning("Approved video not found: %s", video_id)
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

            job_logger.debug("Loaded approved video: %s (%.1fs)", video_id, duration)

        except Exception as e:
            job_logger.warning("Error reading video %s: %s", video_id, e)
            continue

    logger.info("Loaded %d approved videos from data/approved/videos/", len(approved_shorts))

    if not approved_shorts:
        raise VideoProcessingException(
            "No approved videos could be loaded",
            ErrorCode.NO_VALID_SHORTS
        )

    total_available = sum(s['duration_seconds'] for s in approved_shorts)
    logger.info("Total available duration: %.1fs (need %.1fs)", total_available, target_duration)

    await update_job_status(job_id, JobStatus.PROCESSING, progress=60.0)
    await save_checkpoint(job_id, "downloading_shorts_completed")
    return approved_shorts


def _select_shorts_randomly(
    approved_shorts: list[dict[str, Any]],
    target_duration: float,
    audio_duration: float,
) -> list[dict[str, Any]]:
    """Stage 4: Randomly select shorts until target duration is met.

    Returns list of selected short dicts.
    """
    logger.info("[4/7] Selecting shorts randomly...")

    random.shuffle(approved_shorts)

    selected_shorts: list[dict[str, Any]] = []
    total_duration = 0.0

    for short in approved_shorts:
        if total_duration >= target_duration:
            break
        selected_shorts.append(short)
        total_duration += short['duration_seconds']

    logger.info("Selected %d shorts (%.1fs / target %.1fs)", len(selected_shorts), total_duration, target_duration)

    if not selected_shorts:
        raise VideoProcessingException(
            "No shorts available for video creation",
            ErrorCode.NO_VALID_SHORTS
        )

    if total_duration < audio_duration:
        logger.warning(
            "Selected shorts duration (%.1fs) less than audio duration (%.1fs). "
            "Video may need padding or you may need to run /download to get more approved videos.",
            total_duration, audio_duration
        )

    return selected_shorts


async def _assemble_video(
    job_id: str,
    selected_shorts: list[dict[str, Any]],
    video_builder: Any,
    job: Job,
) -> Path:
    """Stage 5: Concatenate selected shorts into a single video (no audio).

    Returns path to assembled video.
    """
    logger.info("[5/7] Assembling video...")
    await update_job_status(job_id, JobStatus.PROCESSING, progress=75.0)

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

    logger.info("Video assembled: %s", temp_video_path)

    concat_info = await video_builder.get_video_info(str(temp_video_path))
    concat_duration = concat_info['duration']
    expected_duration = sum(s['duration_seconds'] for s in selected_shorts)

    concat_diff = abs(concat_duration - expected_duration)
    if concat_diff > CONCAT_TOLERANCE:
        logger.error(
            "CONCATENATION VALIDATION FAILED! "
            "Concatenated video (%.2fs) differs from expected "
            "(%.2fs) by %.2fs (tolerance: %.2fs)",
            concat_duration, expected_duration, concat_diff, CONCAT_TOLERANCE
        )
        raise VideoProcessingException(
            "Concatenation produced incorrect duration",
            ErrorCode.CONCATENATION_FAILED,
            details={
                "expected_duration": expected_duration,
                "actual_duration": concat_duration,
                "difference": concat_diff,
                "tolerance": CONCAT_TOLERANCE,
                "shorts_count": len(selected_shorts),
                "conclusion": "Frame duplication during concatenation. Check FFmpeg concat filter."
            }
        )

    logger.info("CONCATENATION VALIDATION PASSED: Duration OK (%.2fs ~ %.2fs)", concat_duration, expected_duration)

    await save_checkpoint(job_id, "assembling_video_completed")
    return temp_video_path


async def _transcribe_with_retry(
    job_id: str,
    audio_path: Path,
    job: Job,
    api_client: Any,
) -> list[dict[str, Any]]:
    """Stage 6a: Transcribe audio with exponential backoff retry.

    Returns list of transcription segments.
    """
    logger.info("[6/7] Generating subtitles...")
    await update_job_status(job_id, JobStatus.PROCESSING, progress=80.0)

    segments: list[dict[str, Any]] = []
    retry_attempt = 0

    while not segments and retry_attempt < MAX_SUBTITLE_RETRIES:
        retry_attempt += 1

        try:
            if retry_attempt > 1:
                logger.info("Subtitle generation retry #%d", retry_attempt)
                await update_job_status(
                    job_id,
                    JobStatus.PROCESSING,
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
            logger.info("Subtitles generated: %d segments (attempt #%d)", len(segments), retry_attempt)

        except MicroserviceException as e:
            backoff_seconds = min(5 * (2 ** (retry_attempt - 1)), MAX_BACKOFF_SECONDS)

            logger.warning(
                "Subtitle generation failed (attempt #%d): %s",
                retry_attempt, e, exc_info=False
            )
            logger.info("Retrying in %ds...", backoff_seconds)

            await _update_retry_status(
                job_id, retry_attempt, e, backoff_seconds
            )
            await asyncio.sleep(backoff_seconds)

        except Exception as e:
            backoff_seconds = min(5 * (2 ** (retry_attempt - 1)), MAX_BACKOFF_SECONDS)

            logger.warning(
                "Unexpected error during subtitle generation (attempt #%d): %s",
                retry_attempt, e, exc_info=True
            )
            logger.info("Retrying in %ds...", backoff_seconds)

            await _update_retry_status(
                job_id, retry_attempt, e, backoff_seconds
            )
            await asyncio.sleep(backoff_seconds)

    if not segments:
        error_details = {
            "retry_attempts": retry_attempt,
            "max_retries": MAX_SUBTITLE_RETRIES,
            "last_error": "Subtitle generation failed after maximum retries",
            "segments_received": 0,
            "audio_duration": job.audio_duration,
            "subtitle_language": job.subtitle_language,
            "recommendation": "Check audio-transcriber service health and logs"
        }
        logger.error(
            "CRITICAL: Failed to generate subtitles after %d attempts. "
            "Audio transcriber may be down or misconfigured.",
            MAX_SUBTITLE_RETRIES
        )
        raise SubtitleGenerationException(
            reason=f"Failed to generate subtitles after {MAX_SUBTITLE_RETRIES} retry attempts",
            subtitle_path="N/A",
            details=error_details
        )

    return segments


async def _update_retry_status(
    job_id: str,
    retry_attempt: int,
    error: Exception,
    backoff_seconds: int,
) -> None:
    """Update job status with retry metadata."""
    await update_job_status(
        job_id,
        JobStatus.PROCESSING,
        progress=80.0,
        stage_updates={
            "generating_subtitles": {
                "status": "waiting_retry",
                "metadata": {
                    "retry_attempt": retry_attempt,
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "retry_in_seconds": backoff_seconds,
                    "next_retry_at": (now_brazil() + timedelta(seconds=backoff_seconds)).isoformat()
                }
            }
        }
    )


def _convert_segments_to_cues(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 6b: Convert transcription segments to word-level cues.

    Returns list of dicts with start, end, text keys.
    """
    from ..services.subtitle_generator import segments_to_weighted_word_cues

    raw_cues: list[dict[str, Any]] = []
    has_word_timestamps = any(segment.get('words') for segment in segments)

    if has_word_timestamps:
        logger.info("Using word-level timestamps from Whisper")
        for segment in segments:
            for word_data in segment.get('words', []):
                raw_cues.append({
                    'start': word_data['start'],
                    'end': word_data['end'],
                    'text': word_data['word']
                })
    else:
        logger.info("Using weighted timestamps by word length")
        raw_cues = segments_to_weighted_word_cues(segments)

    logger.info("Transcription: %d segments, %d words", len(segments), len(raw_cues))

    if segments:
        logger.debug("First segment: %s", segments[0])

    if not raw_cues:
        error_details = {
            "segments_count": len(segments),
            "raw_cues_count": 0,
            "has_word_timestamps": has_word_timestamps,
            "first_segment": segments[0] if segments else None,
            "problem": "No valid word cues extracted from transcription segments",
            "recommendation": "Check transcription format and word-level timestamp availability"
        }
        logger.error(
            "CRITICAL: NO WORDS extracted from %d segments! has_word_timestamps=%s",
            len(segments), has_word_timestamps
        )
        raise SubtitleGenerationException(
            reason="No valid word cues extracted from transcription",
            subtitle_path="N/A",
            details=error_details
        )

    return raw_cues


def _apply_vad_filtering(
    audio_path: Path,
    raw_cues: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """Stage 6c: Apply speech-gated subtitle filtering (VAD).

    Returns (gated_cues, vad_ok).
    """
    logger.info("[6.5/7] Applying speech gating (VAD)...")

    try:
        from ..services.subtitle_postprocessor import process_subtitles_with_vad
        gated_cues, vad_ok = process_subtitles_with_vad(str(audio_path), raw_cues)

        if vad_ok:
            logger.info("Speech gating OK: %d/%d cues (silero-vad)", len(gated_cues), len(raw_cues))
        else:
            logger.warning("Speech gating fallback: %d/%d cues (webrtcvad/RMS)", len(gated_cues), len(raw_cues))

        return gated_cues, vad_ok

    except Exception as e:
        logger.error("Speech gating failed: %s, using original cues", e)
        return raw_cues, False


def _generate_srt(
    job_id: str,
    final_cues: list[dict[str, Any]],
    settings: dict[str, Any],
) -> Path:
    """Stage 6d: Generate SRT file from word cues.

    Returns path to SRT file.
    """
    from ..services.subtitle_generator import write_srt_from_word_cues

    subtitle_path = Path('/tmp/make-video-temp') / job_id / "subtitles.srt"
    words_per_caption = int(settings.get('words_per_caption', 2))

    if not final_cues:
        logger.error("CRITICAL: final_cues is EMPTY! Cannot generate SRT!")
        raise SubtitleGenerationException(
            reason="No valid subtitle cues after speech gating (VAD processing)",
            subtitle_path=str(subtitle_path),
            details={
                "final_cues_count": 0,
                "problem": "All subtitle cues were filtered out during VAD processing",
                "recommendation": "Check VAD threshold settings or audio quality"
            }
        )

    write_srt_from_word_cues(
        final_cues,
        str(subtitle_path),
        words_per_caption=words_per_caption
    )

    if subtitle_path.exists():
        srt_size = subtitle_path.stat().st_size
        if srt_size == 0:
            logger.error("CRITICAL: SRT file is EMPTY (0 bytes)!")
    else:
        logger.error("CRITICAL: SRT file NOT created at %s!", subtitle_path)

    num_captions_expected = len(final_cues) // words_per_caption
    logger.info(
        "Speech-gated subtitles: %d words -> ~%d captions, %d words/caption",
        len(final_cues), num_captions_expected, words_per_caption
    )

    return subtitle_path


async def _compose_final_video(
    job_id: str,
    temp_video_path: Path,
    audio_path: Path,
    subtitle_path: Path,
    video_builder: Any,
    settings: dict[str, Any],
    job: Job,
) -> Path:
    """Stage 7: Add audio and burn subtitles into video.

    Returns path to composed video.
    """
    logger.info("[7/7] Final composition...")
    await update_job_status(job_id, JobStatus.PROCESSING, progress=85.0)

    video_with_audio_path = Path('/tmp/make-video-temp') / job_id / "video_with_audio.mp4"
    await video_builder.add_audio(
        video_path=str(temp_video_path),
        audio_path=str(audio_path),
        output_path=str(video_with_audio_path)
    )
    logger.info("Audio added")

    final_video_path = Path(settings['output_dir']) / f"{job_id}_final.mp4"
    await video_builder.burn_subtitles(
        video_path=str(video_with_audio_path),
        subtitle_path=str(subtitle_path),
        output_path=str(final_video_path),
        style=job.subtitle_style
    )
    logger.info("Subtitles burned")

    return final_video_path


async def _validate_av_sync(
    job_id: str,
    final_video_path: Path,
    audio_path: Path,
    video_builder: Any,
) -> None:
    """Stage 7.5: Validate audio/video synchronization (non-critical)."""
    logger.info("[7.5/8] Validating A/V synchronization...")

    from ..services.sync_validator import SyncValidator
    sync_validator = SyncValidator(tolerance_seconds=0.5)

    try:
        is_valid, drift, sync_metadata = await sync_validator.validate_sync(
            video_path=str(final_video_path),
            audio_path=str(audio_path),
            video_builder=video_builder,
            job_id=job_id
        )
        logger.info("A/V sync validated: drift=%.3fs (%.2f%%)", drift, sync_metadata['drift_percentage'])
    except Exception as sync_error:
        logger.warning(
            "A/V sync validation failed (non-critical): %s",
            sync_error,
            extra={
                "error": str(sync_error),
                "video_path": str(final_video_path),
                "audio_path": str(audio_path)
            }
        )


async def _validate_and_trim(
    job_id: str,
    final_video_path: Path,
    audio_path: Path,
    video_builder: Any,
    settings: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    """Stage 8: Trim video to target duration and validate final output.

    Returns (final_video_path, video_info).
    """
    logger.info("[8/8] Trimming video to target duration...")
    await update_job_status(job_id, JobStatus.PROCESSING, progress=92.0)

    padding_ms = int(settings.get('video_trim_padding_ms', 1000))
    padding_seconds = padding_ms / 1000.0
    audio_duration = (await video_builder.get_audio_duration(str(audio_path)))
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

    logger.info("Trim analysis:")
    logger.info("  Audio duration: %.2fs", audio_duration)
    logger.info("  Padding: %dms (%.2fs)", padding_ms, padding_seconds)
    logger.info("  Target final: %.2fs", final_duration)
    logger.info("  Current video: %.2fs", current_duration)

    if current_duration < audio_duration - 0.5:
        raise VideoProcessingException(
            "ERRO CRITICO: Video (%.2fs) is shorter than audio (%.2fs)!" % (current_duration, audio_duration),
            ErrorCode.INSUFFICIENT_DURATION,
            details={
                "video_duration": current_duration,
                "audio_duration": audio_duration,
                "target_duration": final_duration,
                "problem": "Video cannot be shorter than audio"
            }
        )

    if abs(current_duration - final_duration) > 0.5:
        logger.info("Trimming needed: %.2fs -> %.2fs", current_duration, final_duration)

        trimmed_video_path = Path('/tmp/make-video-temp') / job_id / f"{job_id}_trimmed.mp4"
        await video_builder.trim_video(
            video_path=str(final_video_path),
            output_path=str(trimmed_video_path),
            max_duration=final_duration
        )
        shutil.move(str(trimmed_video_path), str(final_video_path))
        logger.info("Video trimmed and replaced")
    else:
        logger.info("Trim skipped: video duration (%.2fs) already matches target (%.2fs +/- 0.5s)", current_duration, final_duration)

    video_info = await video_builder.get_video_info(str(final_video_path))
    final_video_duration = video_info['duration']

    logger.info("FINAL VALIDATION:")
    logger.info("  Audio duration: %.2fs", audio_duration)
    logger.info("  Target (audio + padding): %.2fs", final_duration)
    logger.info("  Final video: %.2fs", final_video_duration)

    duration_diff = abs(final_video_duration - final_duration)
    if duration_diff > FINAL_TOLERANCE:
        logger.error(
            "FINAL VALIDATION FAILED! "
            "Video duration (%.2fs) differs from target "
            "(%.2fs) by %.2fs (tolerance: %.2fs)",
            final_video_duration, final_duration, duration_diff, FINAL_TOLERANCE
        )
        raise VideoProcessingException(
            "Final video duration validation failed",
            ErrorCode.PROCESSING_STAGE_FAILED,
            details={
                "audio_duration": audio_duration,
                "target_duration": final_duration,
                "actual_duration": final_video_duration,
                "difference": duration_diff,
                "tolerance": FINAL_TOLERANCE,
                "conclusion": "Video processing completed but duration is incorrect. "
                             "Check concatenation and trim steps in logs."
            }
        )

    if final_video_duration < audio_duration - 0.5:
        logger.error(
            "CRITICAL: Video (%.2fs) is shorter than audio (%.2fs)!",
            final_video_duration, audio_duration
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

    logger.info("FINAL VALIDATION PASSED: Duration OK (%.2fs ~ %.2fs)", final_video_duration, final_duration)
    return final_video_path, video_info


def _build_result(
    job_id: str,
    job: Job,
    selected_shorts: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    final_video_path: Path,
    video_info: dict[str, Any],
) -> JobResult:
    """Build the final JobResult from pipeline outputs."""
    file_size = final_video_path.stat().st_size

    return JobResult(
        video_url=f"/download/{job_id}",
        video_file=final_video_path.name,
        file_size=file_size,
        file_size_mb=round(file_size / BYTES_PER_MB, 2),
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
                position_in_video=sum(
                    selected_shorts[j]['duration_seconds'] for j in range(i)
                )
            )
            for i, s in enumerate(selected_shorts)
        ],
        subtitle_segments=len(segments),
        processing_time=(now_brazil() - job.created_at).total_seconds()
    )


# ---------------------------------------------------------------------------
#  Main orchestrator (legacy path)
# ---------------------------------------------------------------------------

def _build_make_video_result(
    job_id: str,
    job: Any,
    selected_shorts: list[Any],
    segments: list[dict[str, Any]],
    final_video_path: str,
    video_info: dict[str, Any],
) -> JobResult:
    """Build the final JobResult from processing outputs."""
    result = _build_result(
        job_id, job, selected_shorts, segments, final_video_path, video_info
    )
    job.result = result
    job.status = JobStatus.COMPLETED
    job.progress = 100.0
    job.completed_at = now_brazil()
    job.expires_at = job.completed_at + timedelta(hours=24)
    return result


async def _handle_make_video_error(job_id: str, e: Exception) -> None:
    """Handle errors from make-video processing by updating job status."""
    logger.error("Error in make-video: %s", e, exc_info=True)
    _metrics.jobs_failed += 1

    if isinstance(e, MakeVideoException):
        await update_job_status(
            job_id,
            JobStatus.FAILED,
            error={
                "message": e.message,
                "code": e.error_code.value if hasattr(e, 'error_code') else "UNKNOWN",
                "details": e.details if hasattr(e, 'details') else {}
            }
        )
    else:
        await update_job_status(
            job_id,
            JobStatus.FAILED,
            error={
                "message": str(e),
                "type": type(e).__name__
            }
        )
    raise


async def _process_make_video_async(job_id: str) -> None:
    """Processamento assíncrono do vídeo (implementação legada)."""
    job_logger = FileLogger.get_job_logger(job_id)
    job_logger.info("=" * 80)
    job_logger.info("STARTING MAKE-VIDEO JOB: %s", job_id)
    job_logger.info("=" * 80)

    store, api_client, video_builder, shorts_cache, subtitle_gen = get_instances()
    settings = get_settings()

    job = store.get_job(job_id)
    if not job:
        job_logger.error("Job %s not found in Redis", job_id)
        raise MakeVideoException(f"Job {job_id} not found")

    job_logger.info("Job loaded: max_shorts=%s (no query - uses approved videos)", job.max_shorts)

    try:
        from app.pipeline.video_pipeline import VideoPipeline
        pipeline = VideoPipeline()
        pipeline.cleanup_stale_validations(job_id, max_age_minutes=30)
        pipeline.cleanup_orphaned_files(max_age_minutes=30)
        job_logger.info("Cleanup completed: stale files removed from all pipeline folders")
    except Exception as e:
        job_logger.warning("Cleanup warning: %s", e)

    try:
        audio_path, audio_duration, target_duration = await _analyze_audio(
            job_id, job, store, video_builder, settings
        )
        shorts_list = await _fetch_approved_shorts(job_id, job_logger)
        approved_shorts = await _load_approved_videos(
            job_id, shorts_list, video_builder, job_logger, target_duration
        )
        selected_shorts = _select_shorts_randomly(
            approved_shorts, target_duration, audio_duration
        )
        temp_video_path = await _assemble_video(
            job_id, selected_shorts, video_builder, job
        )
        segments = await _transcribe_with_retry(job_id, audio_path, job, api_client)
        raw_cues = _convert_segments_to_cues(segments)
        final_cues, vad_ok = _apply_vad_filtering(audio_path, raw_cues)
        subtitle_path = _generate_srt(job_id, final_cues, settings)

        await save_checkpoint(job_id, "generating_subtitles_completed")

        final_video_path = await _compose_final_video(
            job_id, temp_video_path, audio_path, subtitle_path,
            video_builder, settings, job
        )
        await _validate_av_sync(job_id, final_video_path, audio_path, video_builder)

        final_video_path, video_info = await _validate_and_trim(
            job_id, final_video_path, audio_path, video_builder, settings
        )

        result = _build_make_video_result(
            job_id, job, selected_shorts, segments, final_video_path, video_info
        )
        store.save_job(job)

        await delete_checkpoint(job_id)
        _metrics.jobs_completed += 1

        logger.info("Job %s completed successfully!", job_id)
        logger.info("  Duration: %.1fs", result.duration)
        logger.info("  Size: %sMB", result.file_size_mb)
        logger.info("  Shorts used: %d", result.shorts_used)
        logger.info("  Processing time: %.1fs", result.processing_time)

        return result

    except Exception as e:
        await _handle_make_video_error(job_id, e)

    finally:
        try:
            from app.pipeline.video_pipeline import VideoPipeline
            pipeline_cleanup = VideoPipeline()
            pipeline_cleanup.cleanup_orphaned_files(max_age_minutes=30)
            job_logger.info("Final cleanup: orphaned files removed from all pipeline folders")
        except Exception as e:
            job_logger.warning("Final cleanup warning: %s", e)

        import gc
        collected = gc.collect()
        logger.debug("GC liberated %d objects", collected)
