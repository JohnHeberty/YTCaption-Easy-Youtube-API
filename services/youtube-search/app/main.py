import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import List
import logging

# Common library imports
from common.log_utils import setup_structured_logging, get_logger
from common.exception_handlers import setup_exception_handlers

from .core.models import Job, SearchRequest, JobStatus, SearchType, JobListResponse
from .domain.processor import YouTubeSearchProcessor
from .infrastructure.redis_store import RedisJobStore
from .infrastructure.celery_tasks import youtube_search_task
from .shared.exceptions import (
    YouTubeSearchException, 
    ServiceException, 
    InvalidRequestError,
    exception_handler
)
from .core.config import get_settings
from .middleware.rate_limiter import RateLimiterMiddleware

# Configuration
settings = get_settings()
setup_structured_logging(
    service_name="youtube-search",
    log_level=settings['log_level'],
    log_dir=settings.get('log_dir', './logs'),
    json_format=True
)
logger = get_logger(__name__)

# ============================================================================
# LIFECYCLE
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — replaces deprecated @app.on_event."""
    # ---- startup ----
    try:
        await job_store.start_cleanup_task()
        logger.info("YouTube Search Service started successfully")
    except Exception as e:
        logger.error("Error during startup: %s", e)
        raise

    yield

    # ---- shutdown ----
    try:
        await job_store.stop_cleanup_task()
        logger.info("YouTube Search Service stopped gracefully")
    except Exception as e:
        logger.error("Error during shutdown: %s", e)


# Global instances
app = FastAPI(
    title="YouTube Search Service",
    description="Microservice for YouTube search operations with Celery + Redis and 24h cache",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup exception handlers from common library
setup_exception_handlers(app, debug=settings.get('debug', False))

# Exception handlers - mantidos para compatibilidade
app.add_exception_handler(YouTubeSearchException, exception_handler)
app.add_exception_handler(ServiceException, exception_handler)
app.add_exception_handler(InvalidRequestError, exception_handler)

# CORS middleware
if settings['cors']['enabled']:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings['cors']['origins'],
        allow_credentials=settings['cors']['credentials'],
        allow_methods=settings['cors']['methods'],
        allow_headers=settings['cors']['headers'],
    )

# Rate limiting middleware (per-IP sliding window)
_rl = settings.get('rate_limit', {})
if isinstance(_rl, dict) and _rl.get('enabled', True):
    app.add_middleware(
        RateLimiterMiddleware,
        max_requests=_rl.get('max_requests') or _rl.get('requests_per_minute', 100),
        window_seconds=_rl.get('window_seconds') or _rl.get('period_seconds', 60),
    )

# Use Redis as shared store
redis_url = settings['redis_url']
job_store = RedisJobStore(redis_url=redis_url)
processor = YouTubeSearchProcessor()

# Inject job_store reference into processor for progress updates
processor.job_store = job_store


def submit_celery_task(job: Job):
    """Submit job to Celery"""
    # Serialize job to dict
    job_dict = job.model_dump(mode='json')
    
    # Send to Celery queue
    task = youtube_search_task.apply_async(
        args=[job_dict],
        task_id=job.id  # Use job.id as task_id for tracking
    )
    
    return task


@app.post("/search/video-info", response_model=Job)
async def get_video_info(video_id: str) -> Job:
    """
    Get video information
    
    - **video_id**: YouTube video ID or URL
    """
    try:
        logger.info(f"Request for video info: {video_id}")
        
        # Create job
        new_job = Job.create_new(
            search_type=SearchType.VIDEO_INFO,
            video_id=video_id,
            cache_ttl_hours=settings['cache_ttl_hours']
        )
        
        # Check if job already exists
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} already completed (cache hit)")
                return existing_job
            elif existing_job.status == JobStatus.PROCESSING:
                logger.info(f"Job {new_job.id} is processing")
                return existing_job
        
        # Save new job
        job_store.save_job(new_job)
        
        # Submit to Celery
        submit_celery_task(new_job)
        
        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job
        
    except Exception as e:
        logger.error(f"Error creating video info job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/channel-info", response_model=Job)
async def get_channel_info(channel_id: str, include_videos: bool = False) -> Job:
    """
    Get channel information
    
    - **channel_id**: YouTube channel ID
    - **include_videos**: Include channel videos in response
    """
    try:
        logger.info(f"Request for channel info: {channel_id} (include_videos: {include_videos})")
        
        new_job = Job.create_new(
            search_type=SearchType.CHANNEL_INFO,
            channel_id=channel_id,
            include_videos=include_videos,
            cache_ttl_hours=settings['cache_ttl_hours']
        )
        
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} already completed (cache hit)")
                return existing_job
            elif existing_job.status == JobStatus.PROCESSING:
                logger.info(f"Job {new_job.id} is processing")
                return existing_job
        
        job_store.save_job(new_job)
        submit_celery_task(new_job)
        
        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job
        
    except Exception as e:
        logger.error(f"Error creating channel info job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/playlist-info", response_model=Job)
async def get_playlist_info(playlist_id: str) -> Job:
    """
    Get playlist information
    
    - **playlist_id**: YouTube playlist ID
    """
    try:
        logger.info(f"Request for playlist info: {playlist_id}")
        
        new_job = Job.create_new(
            search_type=SearchType.PLAYLIST_INFO,
            playlist_id=playlist_id,
            cache_ttl_hours=settings['cache_ttl_hours']
        )
        
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} already completed (cache hit)")
                return existing_job
            elif existing_job.status == JobStatus.PROCESSING:
                logger.info(f"Job {new_job.id} is processing")
                return existing_job
        
        job_store.save_job(new_job)
        submit_celery_task(new_job)
        
        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job
        
    except Exception as e:
        logger.error(f"Error creating playlist info job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/videos", response_model=Job)
async def search_videos(query: str, max_results: int = 10) -> Job:
    """
    Search for videos
    
    - **query**: Search query
    - **max_results**: Maximum number of results (unlimited)
    """
    try:
        logger.info(f"Search videos request: '{query}' (max: {max_results})")
        
        if max_results < 1:
            raise InvalidRequestError("max_results must be at least 1")
        
        new_job = Job.create_new(
            search_type=SearchType.VIDEO,
            query=query,
            max_results=max_results,
            cache_ttl_hours=settings['cache_ttl_hours']
        )
        
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} already completed (cache hit)")
                return existing_job
            elif existing_job.status == JobStatus.PROCESSING:
                logger.info(f"Job {new_job.id} is processing")
                return existing_job
        
        job_store.save_job(new_job)
        submit_celery_task(new_job)
        
        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job
        
    except InvalidRequestError:
        raise
    except Exception as e:
        logger.error(f"Error creating video search job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/related-videos", response_model=Job)
async def get_related_videos(video_id: str, max_results: int = 10) -> Job:
    """
    Get related videos
    
    - **video_id**: YouTube video ID
    - **max_results**: Maximum number of results (unlimited)
    """
    try:
        logger.info(f"Request for related videos: {video_id} (max: {max_results})")
        
        if max_results < 1:
            raise InvalidRequestError("max_results must be at least 1")
        
        new_job = Job.create_new(
            search_type=SearchType.RELATED_VIDEOS,
            video_id=video_id,
            max_results=max_results,
            cache_ttl_hours=settings['cache_ttl_hours']
        )
        
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} already completed (cache hit)")
                return existing_job
            elif existing_job.status == JobStatus.PROCESSING:
                logger.info(f"Job {new_job.id} is processing")
                return existing_job
        
        job_store.save_job(new_job)
        submit_celery_task(new_job)
        
        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job
        
    except InvalidRequestError:
        raise
    except Exception as e:
        logger.error(f"Error creating related videos job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/shorts", response_model=Job)
async def search_shorts(query: str, max_results: int = 10) -> Job:
    """
    Search for YouTube Shorts only
    
    Returns only videos with duration ≤60 seconds
    
    - **query**: Search query
    - **max_results**: Maximum number of shorts to return (unlimited)
    """
    try:
        logger.info(f"Search shorts request: '{query}' (max: {max_results})")
        
        if max_results < 1:
            raise InvalidRequestError("max_results must be at least 1")
        
        new_job = Job.create_new(
            search_type=SearchType.SHORTS,
            query=query,
            max_results=max_results,
            cache_ttl_hours=settings['cache_ttl_hours']
        )
        
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} already completed (cache hit)")
                return existing_job
            elif existing_job.status == JobStatus.PROCESSING:
                logger.info(f"Job {new_job.id} is processing")
                return existing_job
        
        job_store.save_job(new_job)
        submit_celery_task(new_job)
        
        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job
        
    except InvalidRequestError:
        raise
    except Exception as e:
        logger.error(f"Error creating shorts search job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job_status(job_id: str) -> Job:
    """
    Get job status and results
    
    - **job_id**: Job identifier
    """
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@app.get("/jobs", response_model=JobListResponse)
async def list_jobs(limit: int = 50) -> JobListResponse:
    """
    List all jobs
    
    - **limit**: Maximum number of jobs to return
    """
    jobs = job_store.list_jobs(limit=limit)
    return JobListResponse(jobs=jobs, total=len(jobs))


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Remove job and associated data from Redis
    
    IMPORTANT: Completely removes the job from the system:
    - Job from Redis
    - All cached results
    
    - **job_id**: Job identifier
    """
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        # Remove job from Redis
        job_store.delete_job(job_id)
        logger.info(f"🗑️ Job {job_id} removed from Redis")
        
        return {
            "message": "Job removed successfully",
            "job_id": job_id
        }
        
    except Exception as e:
        logger.error(f"❌ Error removing job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error removing job: {str(e)}"
        )


@app.get("/jobs/{job_id}/download")
async def download_results(job_id: str):
    """
    Download job results as JSON file
    
    Returns the search results in JSON format for compatibility with orchestrator.
    Unlike other microservices that return binary files (audio/video),
    this service returns structured search data.
    
    - **job_id**: Job identifier
    """
    from fastapi.responses import Response
    import json
    
    try:
        job = job_store.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.is_expired:
            raise HTTPException(status_code=410, detail="Job expired")
        
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=425,
                detail=f"Results not ready. Status: {job.status.value}"
            )
        
        if not job.result:
            raise HTTPException(status_code=404, detail="No results available")
        
        # Create filename based on search type
        filename = f"youtube_search_{job.search_type.value}_{job_id}.json"
        
        # Convert result to JSON
        result_json = json.dumps(job.result, indent=2, ensure_ascii=False)
        
        logger.info(f"📥 Downloading results for job {job_id}: {len(result_json)} bytes")
        
        return Response(
            content=result_json,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}/wait", response_model=Job)
async def wait_for_job_completion(job_id: str, timeout: int = 600) -> Job:
    """
    🔄 **Wait for job completion (long polling)**
    
    This endpoint keeps the connection open until:
    - ✅ Job completes successfully
    - ❌ Job fails
    - ⏱️ Timeout is reached (default: 600s = 10min)
    
    **Parameters:**
    - `job_id`: Job identifier
    - `timeout`: Maximum wait time in seconds (default: 600)
    
    **Example:**
    ```
    GET /jobs/{job_id}/wait?timeout=300
    ```
    
    **Behavior:**
    - Checks status every 2 seconds
    - Returns immediately if job is already completed/failed
    - Maintains connection with keep-alive
    
    **Returns:** Complete job object when finished
    """
    from datetime import datetime, timedelta
    
    start_time = now_brazil()
    max_wait = timedelta(seconds=timeout)
    poll_interval = 2  # Check every 2 seconds
    
    logger.info(f"Client waiting for job {job_id} completion (timeout: {timeout}s)")
    
    try:
        while now_brazil() - start_time < max_wait:
            job = job_store.get_job(job_id)
            
            if not job:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
            
            # Check if job finished (success or error)
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                elapsed = (now_brazil() - start_time).total_seconds()
                logger.info(f"Job {job_id} finished with status {job.status.value} after {elapsed:.1f}s")
                return job
            
            # Job still processing - wait for next poll
            logger.debug(f"Job {job_id} still processing: {job.status.value} ({job.progress}%)")
            await asyncio.sleep(poll_interval)
        
        # Timeout reached
        elapsed = (now_brazil() - start_time).total_seconds()
        logger.warning(f"Timeout waiting for job {job_id} after {elapsed:.1f}s")
        raise HTTPException(
            status_code=408,  # Request Timeout
            detail=f"Timeout waiting for job completion after {timeout}s. Use GET /jobs/{job_id} to check current status."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error waiting for job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/cleanup")
async def manual_cleanup(
    deep: bool = False,
    purge_celery_queue: bool = False
):
    """
    🧹 SYSTEM CLEANUP
    
    ⚠️ IMPORTANT: SYNCHRONOUS execution (no background tasks or Celery)
    Client WAITS for complete execution before receiving response.
    
    **Operation modes:**
    
    1. **Basic cleanup** (deep=false):
       - Remove expired jobs (>24h)
       - Redis cleanup
    
    2. **Deep cleanup** (deep=true) - ⚠️ FACTORY RESET:
       - ALL Redis database (FLUSHDB using DB from .env)
       - **OPTIONAL:** ALL Celery queue jobs (purge_celery_queue=true)
    
    **Parameters:**
    - deep (bool): If true, does COMPLETE cleanup (factory reset)
    - purge_celery_queue (bool): If true, cleans CELERY QUEUE too
    """
    cleanup_type = "TOTAL" if deep else "basic"
    logger.warning(f"🔥 Starting {cleanup_type} SYNCHRONOUS cleanup (purge_celery={purge_celery_queue})")
    
    try:
        if deep:
            result = await _perform_total_cleanup(purge_celery_queue)
        else:
            result = await _perform_basic_cleanup()
        
        logger.info(f"✅ {cleanup_type} cleanup COMPLETED successfully")
        return result
        
    except Exception as e:
        logger.error(f"❌ ERROR in {cleanup_type} cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error during cleanup: {str(e)}")


async def _perform_basic_cleanup():
    """Execute BASIC cleanup: Remove only expired jobs"""
    try:
        report = {
            "jobs_removed": 0,
            "errors": []
        }
        
        # Remove expired jobs
        expired_count = await job_store.cleanup_expired()
        report["jobs_removed"] = expired_count
        
        report["message"] = f"🧹 Basic cleanup completed: {expired_count} expired jobs removed"
        
        logger.info(report["message"])
        return report
        
    except Exception as e:
        logger.error(f"❌ Error in basic cleanup: {e}")
        return {"error": str(e), "jobs_removed": 0}


async def _perform_total_cleanup(purge_celery_queue: bool = False):
    """Execute TOTAL cleanup: Factory reset of the system"""
    from urllib.parse import urlparse
    from redis import Redis
    
    try:
        report = {
            "jobs_removed": 0,
            "redis_flushed": False,
            "celery_queue_purged": False,
            "celery_tasks_purged": 0,
            "errors": []
        }
        
        logger.warning("🔥 STARTING TOTAL SYSTEM CLEANUP - EVERYTHING WILL BE REMOVED!")
        
        # 1. FLUSHDB on Redis
        try:
            redis_url = settings['redis_url']
            parsed = urlparse(redis_url)
            redis_host = parsed.hostname or 'localhost'
            redis_port = parsed.port or 6379
            redis_db = int(parsed.path.strip('/')) if parsed.path else 0
            
            logger.warning(f"🔥 Executing FLUSHDB on Redis {redis_host}:{redis_port} DB={redis_db}")
            
            redis = Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
            
            # Count jobs BEFORE cleaning
            keys_before = redis.keys("youtube_search:job:*")
            report["jobs_removed"] = len(keys_before)
            
            # FLUSHDB - Remove ALL content from current database
            redis.flushdb()
            report["redis_flushed"] = True
            
            logger.info(f"✅ Redis FLUSHDB executed: {len(keys_before)} jobs + all other keys removed")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning Redis: {e}")
            report["errors"].append(f"Redis FLUSHDB: {str(e)}")
        
        # 2. CLEAN CELERY QUEUE (IF REQUESTED)
        if purge_celery_queue:
            try:
                from .infrastructure.celery_config import celery_app
                
                logger.warning("🔥 Cleaning Celery queue 'youtube_search_queue'...")
                
                redis_celery = Redis.from_url(settings['redis_url'])
                
                # Revoke all active/scheduled tasks
                try:
                    inspect = celery_app.control.inspect()
                    active_tasks = inspect.active()
                    
                    if active_tasks:
                        for worker, tasks in active_tasks.items():
                            for task in tasks:
                                task_id = task.get('id')
                                logger.warning(f"   🛑 Revoking active task: {task_id}")
                                celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')
                        logger.info(f"   ✓ {sum(len(t) for t in active_tasks.values())} active tasks revoked")
                    
                    scheduled_tasks = inspect.scheduled()
                    if scheduled_tasks:
                        for worker, tasks in scheduled_tasks.items():
                            for task in tasks:
                                task_id = task.get('id') or task.get('request', {}).get('id')
                                if task_id:
                                    logger.warning(f"   🛑 Revoking scheduled task: {task_id}")
                                    celery_app.control.revoke(task_id, terminate=True)
                        logger.info(f"   ✓ {sum(len(t) for t in scheduled_tasks.values())} scheduled tasks revoked")
                    
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not revoke tasks: {e}")
                
                # Queue names in Redis
                queue_keys = [
                    "youtube_search_queue",
                    "celery",
                    "_kombu.binding.youtube_search_queue",
                    "_kombu.binding.celery",
                    "unacked",
                    "unacked_index",
                ]
                
                tasks_purged = 0
                for queue_key in queue_keys:
                    queue_len = redis_celery.llen(queue_key)
                    if queue_len > 0:
                        logger.info(f"   Queue '{queue_key}': {queue_len} tasks")
                        tasks_purged += queue_len
                    
                    deleted = redis_celery.delete(queue_key)
                    if deleted:
                        logger.info(f"   ✓ Queue '{queue_key}' removed")
                
                # Remove Celery result keys
                celery_result_keys = redis_celery.keys("celery-task-meta-*")
                if celery_result_keys:
                    redis_celery.delete(*celery_result_keys)
                    logger.info(f"   ✓ {len(celery_result_keys)} Celery results removed")
                
                report["celery_queue_purged"] = True
                report["celery_tasks_purged"] = tasks_purged
                logger.warning(f"🔥 Celery queue purged: {tasks_purged} tasks removed")
                
            except Exception as e:
                logger.error(f"❌ Error cleaning Celery queue: {e}")
                report["errors"].append(f"Celery purge: {str(e)}")
        
        report["message"] = (
            f"🔥 TOTAL CLEANUP COMPLETED: "
            f"{report['jobs_removed']} Redis jobs removed"
        )
        
        if report["errors"]:
            report["message"] += f" ⚠️ with {len(report['errors'])} errors"
        
        logger.warning(report["message"])
        return report
        
    except Exception as e:
        logger.error(f"❌ Error in total cleanup: {e}")
        return {"error": str(e), "jobs_removed": 0}


@app.get("/admin/stats")
async def get_stats():
    """
    Complete system statistics
    """
    from .infrastructure.celery_config import celery_app
    
    stats = job_store.get_stats()
    
    # Add Celery statistics
    try:
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()
        stats["celery"] = {
            "active_workers": len(active_tasks) if active_tasks else 0,
            "active_tasks": sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0,
            "broker": "redis",
            "backend": "redis",
            "queue": "youtube_search_queue"
        }
    except Exception as e:
        stats["celery"] = {
            "error": str(e),
            "status": "unavailable"
        }
    
    return stats


@app.get("/admin/queue")
async def get_queue_stats():
    """
    Celery queue specific statistics
    """
    from .infrastructure.celery_config import celery_app
    
    try:
        inspect = celery_app.control.inspect()
        
        active_workers = inspect.active()
        registered = inspect.registered()
        scheduled = inspect.scheduled()
        
        return {
            "broker": "redis",
            "queue_name": "youtube_search_queue",
            "active_workers": len(active_workers) if active_workers else 0,
            "registered_tasks": list(registered.values())[0] if registered else [],
            "active_tasks": active_workers if active_workers else {},
            "scheduled_tasks": scheduled if scheduled else {},
            "is_running": active_workers is not None
        }
    except Exception as e:
        return {
            "error": str(e),
            "is_running": False
        }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint — exposes job counts by status."""
    from fastapi.responses import Response

    svc = "youtube_search"
    stats: dict = {}
    try:
        stats = job_store.get_stats()
    except Exception as _e:
        logger.warning("Metrics: failed to get stats: %s", _e)

    by_status = stats.get("by_status", {})
    total = stats.get("total_jobs", 0)

    lines = [
        f"# HELP {svc}_jobs_total Jobs in Redis store by status",
        f"# TYPE {svc}_jobs_total gauge",
    ]
    for _status, _count in by_status.items():
        lines.append(f'{svc}_jobs_total{{status="{_status}"}} {_count}')
    lines += [
        f"# HELP {svc}_jobs_store_total Total jobs in Redis store",
        f"# TYPE {svc}_jobs_store_total gauge",
        f"{svc}_jobs_store_total {total}",
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/health")
async def health_check():
    """Deep health check - validates critical resources"""
    import shutil
    from pathlib import Path
    
    health_status = {
        "status": "healthy",
        "service": "youtube-search",
        "version": settings['version'],
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    is_healthy = True
    
    # 1. Check Redis
    try:
        job_store.redis.ping()
        stats = job_store.get_stats()
        health_status["checks"]["redis"] = {
            "status": "ok",
            "message": "Connected",
            "jobs": stats
        }
    except Exception as e:
        health_status["checks"]["redis"] = {"status": "error", "message": str(e)}
        is_healthy = False
    
    # 2. Check disk space
    try:
        logs_dir = Path(settings['log_dir'])
        logs_dir.mkdir(exist_ok=True, parents=True)
        stat = shutil.disk_usage(logs_dir)
        free_gb = stat.free / (1024**3)
        total_gb = stat.total / (1024**3)
        percent_free = (stat.free / stat.total) * 100
        
        disk_status = "ok" if percent_free > 10 else "warning" if percent_free > 5 else "critical"
        if percent_free <= 5:
            is_healthy = False
            
        health_status["checks"]["disk_space"] = {
            "status": disk_status,
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "percent_free": round(percent_free, 2)
        }
    except Exception as e:
        health_status["checks"]["disk_space"] = {"status": "error", "message": str(e)}
        is_healthy = False
    
    # 3. Check Celery workers
    try:
        from .infrastructure.celery_config import celery_app
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            health_status["checks"]["celery_workers"] = {
                "status": "ok",
                "workers": len(active_workers),
                "active_tasks": sum(len(tasks) for tasks in active_workers.values())
            }
        else:
            health_status["checks"]["celery_workers"] = {
                "status": "warning",
                "message": "No active workers detected"
            }
    except Exception as e:
        health_status["checks"]["celery_workers"] = {"status": "error", "message": str(e)}
    
    # 4. Check ytbpy library
    try:
        from .services.ytbpy import video
        health_status["checks"]["ytbpy"] = {"status": "ok", "message": "Library loaded"}
    except Exception as e:
        health_status["checks"]["ytbpy"] = {"status": "error", "message": str(e)}
        is_healthy = False
    
    # Update overall status
    health_status["status"] = "healthy" if is_healthy else "unhealthy"
    
    status_code = 200 if is_healthy else 503
    
    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "YouTube Search Service",
        "version": settings['version'],
        "status": "running",
        "endpoints": {
            "health": "/health (GET) - Health check",
            "search_video_info": "/search/video-info (POST) - Get video information",
            "search_channel_info": "/search/channel-info (POST) - Get channel information",
            "search_playlist_info": "/search/playlist-info (POST) - Get playlist information",
            "search_videos": "/search/videos (POST) - Search videos",
            "search_shorts": "/search/shorts (POST) - Search YouTube Shorts (≤60s)",
            "search_related_videos": "/search/related-videos (POST) - Get related videos",
            "get_job": "/jobs/{job_id} (GET) - Get job status",
            "list_jobs": "/jobs (GET) - List all jobs",
            "delete_job": "/jobs/{job_id} (DELETE) - Delete job",
            "admin_stats": "/admin/stats (GET) - System statistics",
            "admin_queue": "/admin/queue (GET) - Celery queue stats",
            "admin_cleanup": "/admin/cleanup (POST) - System cleanup",
            "docs": "/docs - API documentation"
        }
    }
