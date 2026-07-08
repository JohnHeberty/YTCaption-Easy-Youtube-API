"""Job recovery task (Sprint-01)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from ..celery_config import celery_app
from ...core.config import get_settings
from ...core.models import Job, JobStatus
from ..instances import get_instances
from ..base import update_job_status
from ..checkpoint import load_checkpoint
from ..simple_metrics import simple_metrics as _metrics

logger = get_logger(__name__)


@celery_app.task(name='app.infrastructure.celery_tasks.recover_orphaned_jobs')
def recover_orphaned_jobs() -> dict[str, Any]:
    """
    Auto-recovery de jobs órfãos (Sprint-01).

    Detecta jobs travados em processamento há mais de 5 minutos
    e força sua re-execução do ponto onde pararam.

    Execução: A cada 2 minutos (Celery Beat)
    """
    logger.info("🔍 [AUTO-RECOVERY] Starting orphaned jobs detection...")

    settings = get_settings()
    store, _, _, _, _ = get_instances()

    max_age_minutes = int(settings.get('orphan_detection_threshold_minutes', 5))

    try:
        orphaned_jobs = store.find_orphaned_jobs(max_age_minutes=max_age_minutes)

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
            age_minutes = (now_brazil() - job.updated_at).total_seconds() / 60

            logger.info(
                f"🔧 [AUTO-RECOVERY] Attempting recovery of job {job.job_id} "
                f"(status={job.status}, age={age_minutes:.1f}min)"
            )

            try:
                loop = asyncio.get_event_loop()
                success = loop.run_until_complete(_recover_single_job(job))

                if success:
                    recovered_count += 1
                    _metrics.orphans_recovered += 1
                    logger.info(f"✅ [AUTO-RECOVERY] Job {job.job_id} recovered successfully")
                else:
                    failed_count += 1
                    _metrics.orphans_failed += 1
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
    """Recupera um job individual do ponto onde parou."""
    from .make_video import process_make_video

    store, _, _, _, _ = get_instances()
    settings = get_settings()

    try:
        checkpoint = await load_checkpoint(job.job_id)

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

        current_stage = job.status.value if job.status else "queued"
        next_stage = _determine_next_stage(current_stage, checkpoint)

        if not next_stage:
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

        job.status = JobStatus.QUEUED
        job.progress = _stage_to_progress(next_stage)
        job.updated_at = now_brazil()

        if not job.error:
            job.error = {}
        job.error["recovery_info"] = {
            "recovered_at": now_brazil().isoformat(),
            "original_stage": current_stage,
            "resume_stage": next_stage.value if hasattr(next_stage, 'value') else str(next_stage),
            "age_minutes": (now_brazil() - job.updated_at).total_seconds() / 60
        }

        store.save_job(job)

        process_make_video.apply_async(
            args=[job.job_id],
            queue='make_video_queue'
        )

        logger.info(f"✅ [RECOVERY] Job {job.job_id} re-submitted successfully")
        return True

    except Exception as e:
        logger.error(f"❌ [RECOVERY] Error recovering job {job.job_id}: {e}", exc_info=True)
        return False


def _determine_next_stage(current_stage: str, checkpoint: dict[str, Any]) -> JobStatus | None:
    """Determina próxima etapa a executar baseado em checkpoint."""
    completed = set(checkpoint.get('completed_stages', []))

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

    try:
        if current_stage == "processing":
            for stage in stage_flow:
                if stage.value not in completed:
                    return stage
            return None

        current_idx = next(
            i for i, stage in enumerate(stage_flow)
            if stage.value == current_stage
        )

        if current_idx + 1 < len(stage_flow):
            return stage_flow[current_idx + 1]
        else:
            return None

    except StopIteration:
        return JobStatus.QUEUED


async def _validate_job_prerequisites(job: Job, next_stage: JobStatus) -> dict[str, Any]:
    """Valida que pré-requisitos para a próxima etapa existem."""
    settings = get_settings()

    try:
        if next_stage == JobStatus.QUEUED:
            return {"valid": True}

        if next_stage == JobStatus.ANALYZING_AUDIO:
            audio_path = Path(settings['audio_upload_dir']) / job.job_id / "audio"

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
            if not job.audio_duration:
                return {"valid": False, "reason": "Audio duration not analyzed"}
            return {"valid": True}

        if next_stage == JobStatus.DOWNLOADING_SHORTS:
            return {"valid": True}

        if next_stage == JobStatus.SELECTING_SHORTS:
            shorts_cache_dir = Path(settings['shorts_cache_dir'])
            job_shorts_dir = shorts_cache_dir / job.job_id
            if not job_shorts_dir.exists() or not list(job_shorts_dir.glob("*.mp4")):
                return {"valid": False, "reason": f"No shorts available for job {job.job_id}"}
            return {"valid": True}

        if next_stage == JobStatus.ASSEMBLING_VIDEO:
            return {"valid": True}

        if next_stage == JobStatus.GENERATING_SUBTITLES:
            temp_video = Path('/tmp/make-video-temp') / job.job_id / "video_no_audio.mp4"
            if not temp_video.exists():
                return {"valid": False, "reason": "Intermediate video not found"}
            return {"valid": True}

        if next_stage == JobStatus.FINAL_COMPOSITION:
            video_with_audio = Path('/tmp/make-video-temp') / job.job_id / "video_with_audio.mp4"
            subtitle_file = Path('/tmp/make-video-temp') / job.job_id / "subtitles.srt"

            if not video_with_audio.exists():
                return {"valid": False, "reason": "Video with audio not found"}
            if not subtitle_file.exists():
                return {"valid": False, "reason": "Subtitle file not found"}
            return {"valid": True}

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
