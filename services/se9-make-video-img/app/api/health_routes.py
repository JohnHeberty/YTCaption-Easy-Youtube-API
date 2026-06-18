"""Health check routes."""
import shutil

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Check service health including dependencies."""
    checks = {}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.se7_url}/health")
            checks["se7"] = "ok" if resp.status_code == 200 else "error"
    except Exception:
        checks["se7"] = "unreachable"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.se8_url}/health")
            checks["se8"] = "ok" if resp.status_code == 200 else "error"
    except Exception:
        checks["se8"] = "unreachable"

    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3)
        checks["disk"] = "ok" if free_gb > 5 else "low"
    except Exception:
        checks["disk"] = "unknown"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "service": "make-video-img",
        "version": settings.version,
        "checks": checks,
    }


@router.get("/ping")
async def ping():
    """Simple ping endpoint."""
    return {"pong": True}
