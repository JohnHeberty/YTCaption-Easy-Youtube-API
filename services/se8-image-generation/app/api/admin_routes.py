"""Admin routes for SE8 Image Generation."""
import os
import time

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
async def stats():
    """System statistics."""
    import app.services.worker as worker_mod
    queue_info = {}
    if worker_mod.worker_queue:
        queue_info = worker_mod.worker_queue.get_queue_info()

    output_dir = os.getenv("OUTPUT_DIR", "./data/outputs")
    output_count = 0
    output_size = 0
    if os.path.exists(output_dir):
        for f in os.listdir(output_dir):
            fp = os.path.join(output_dir, f)
            if os.path.isfile(fp):
                output_count += 1
                output_size += os.path.getsize(fp)

    return {
        "service": "se8-image-generation",
        "queue": queue_info,
        "outputs": {"count": output_count, "size_mb": round(output_size / (1024 * 1024), 1)},
    }


@router.post("/cleanup")
async def cleanup():
    """Cleanup old output files and job history."""
    cleaned = 0
    output_dir = os.getenv("OUTPUT_DIR", "./data/outputs")
    if os.path.exists(output_dir):
        cutoff = time.time() - 86400
        for f in os.listdir(output_dir):
            fp = os.path.join(output_dir, f)
            if os.path.isfile(fp) and os.path.getmtime(fp) < cutoff:
                os.remove(fp)
                cleaned += 1

    history_cleaned = 0
    import app.services.worker as worker_mod
    if worker_mod.worker_queue:
        history_cleaned = worker_mod.worker_queue.clear_all_history()

    return {
        "jobs_removed": history_cleaned,
        "files_deleted": cleaned,
        "message": f"Cleaned {history_cleaned} history entries and {cleaned} old output files",
    }
