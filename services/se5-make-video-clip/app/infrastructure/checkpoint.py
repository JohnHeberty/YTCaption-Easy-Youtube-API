"""Checkpoint save/load/delete utilities."""
from __future__ import annotations

import json
from typing import Any

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

logger = get_logger(__name__)


def _get_store() -> Any:
    from .instances import get_instances
    store, _, _, _, _ = get_instances()
    return store


async def save_checkpoint(job_id: str, completed_stage: str) -> None:
    """Salva checkpoint de progresso"""
    store = _get_store()
    key = f"make_video:checkpoint:{job_id}"

    try:
        existing_data = store.redis.get(key)
        if existing_data:
            checkpoint = json.loads(existing_data)
        else:
            checkpoint = {"completed_stages": []}

        if completed_stage not in checkpoint["completed_stages"]:
            checkpoint["completed_stages"].append(completed_stage)

        checkpoint["last_updated"] = now_brazil().isoformat()
        store.redis.setex(key, 172800, json.dumps(checkpoint))
        logger.debug(f"💾 [CHECKPOINT] Saved for {job_id}: stage={completed_stage}")

    except Exception as e:
        logger.error(f"Error saving checkpoint for {job_id}: {e}")


async def load_checkpoint(job_id: str) -> dict[str, Any] | None:
    """Carrega checkpoint de progresso"""
    store = _get_store()
    key = f"make_video:checkpoint:{job_id}"

    try:
        data = store.redis.get(key)
        if data:
            return json.loads(data)
        return None

    except Exception as e:
        logger.error(f"Error loading checkpoint for {job_id}: {e}")
        return None


async def delete_checkpoint(job_id: str) -> None:
    """Deleta checkpoint após job completar"""
    store = _get_store()
    key = f"make_video:checkpoint:{job_id}"

    try:
        store.redis.delete(key)
        logger.debug(f"🗑️ [CHECKPOINT] Deleted for {job_id}")
    except Exception as e:
        logger.error(f"Error deleting checkpoint for {job_id}: {e}")


async def save_stage_checkpoint(job_id: str, stage: str, data: dict[str, Any]) -> None:
    """Save granular checkpoint within a stage (Sprint-02)"""
    store = _get_store()
    key = f"make_video:stage_checkpoint:{job_id}:{stage}"

    try:
        checkpoint = {
            "stage": stage,
            "data": data,
            "last_updated": now_brazil().isoformat()
        }
        store.redis.setex(key, 172800, json.dumps(checkpoint))
        logger.debug(f"💾 [STAGE-CP] {stage}: {len(data.get('downloaded_ids', []))} items")
    except Exception as e:
        logger.error(f"Error saving stage checkpoint: {e}")


async def load_stage_checkpoint(job_id: str, stage: str) -> dict[str, Any] | None:
    """Load granular checkpoint within a stage (Sprint-02)"""
    store = _get_store()
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


async def delete_stage_checkpoint(job_id: str, stage: str) -> None:
    """Delete stage checkpoint (Sprint-02)"""
    store = _get_store()
    key = f"make_video:stage_checkpoint:{job_id}:{stage}"

    try:
        store.redis.delete(key)
        logger.debug(f"🗑️ [STAGE-CP] Deleted {stage}")
    except Exception as e:
        logger.error(f"Error deleting stage checkpoint: {e}")
