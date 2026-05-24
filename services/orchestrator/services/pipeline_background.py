"""
Background pipeline execution service.

Extracted from main.py to eliminate dependency on module-level globals.
Uses DI factories for redis_store and orchestrator.
"""
from common.log_utils import get_logger

logger = get_logger(__name__)


async def execute_pipeline_background(job_id: str):
    """Executa pipeline em background"""
    from infrastructure.dependency_injection import get_pipeline_orchestrator
    from infrastructure.redis_store import get_store

    redis_store = get_store()
    orchestrator = get_pipeline_orchestrator(redis_store=redis_store)

    logger.info(f"BACKGROUND TASK STARTED for job {job_id}")
    try:
        job = redis_store.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in Redis!")
            return
        logger.info(f"Job {job_id} retrieved from Redis, status: {job.status}")
        if not orchestrator:
            logger.error(f"Orchestrator not initialized!")
            job.mark_as_failed("Orchestrator not available")
            redis_store.save_job(job)
            return
        logger.info(f"Executing pipeline for job {job_id}...")
        job = await orchestrator.execute_pipeline(job)
        logger.info(f"Pipeline execution finished for job {job_id}, status: {job.status}")
        redis_store.save_job(job)
        logger.info(f"Pipeline for job {job_id} finished with status: {job.status}")
    except Exception as e:
        logger.error(f"Pipeline execution failed for job {job_id}: {str(e)}", exc_info=True)
        try:
            job = redis_store.get_job(job_id)
            if job:
                job.mark_as_failed(str(e))
                redis_store.save_job(job)
                logger.info(f"Job {job_id} marked as failed in Redis")
        except Exception as save_error:
            logger.error(f"Failed to save error state for job {job_id}: {save_error}")