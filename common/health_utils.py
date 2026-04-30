"""
Standardized health check utilities for YTCaption microservices.

Provides:
- CheckResult: Dataclass for individual check results
- ServiceHealthChecker: Orchestrates multiple checks and produces standardized /health responses

Usage:
    checker = ServiceHealthChecker("audio-normalization")
    checker.add_check("redis", check_redis_fn)
    checker.add_check("disk", check_disk_fn)
    result = await checker.check_all()
    # result = {"status": "healthy", "service": "audio-normalization", "checks": {...}, ...}
"""
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import datetime, timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")

    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)


@dataclass
class CheckResult:
    """Result of a single health check.

    Attributes:
        name: Name of the check (e.g., "redis", "disk", "ffmpeg")
        status: One of "ok", "warning", "error"
        detail: Optional detail message
        latency_ms: How long the check took in milliseconds
    """
    name: str
    status: str  # "ok", "warning", "error"
    detail: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        result = {"status": self.status}
        if self.detail:
            result["message"] = self.detail
        if self.latency_ms > 0:
            result["latency_ms"] = round(self.latency_ms, 2)
        return result


class ServiceHealthChecker:
    """Orchestrates health checks for a microservice.

    Usage:
        checker = ServiceHealthChecker("my-service")
        checker.add_check("redis", lambda: check_redis(redis_url))
        checker.add_check("disk", lambda: check_disk("/tmp"))
        result = await checker.check_all()
    """

    def __init__(self, service_name: str, version: str = "unknown"):
        self.service_name = service_name
        self.version = version
        self._checks: Dict[str, Callable] = {}

    def add_check(self, name: str, check_fn: Callable) -> None:
        """Add a health check function.

        Args:
            name: Name of the check
            check_fn: Callable that returns a CheckResult or dict with 'status' key
        """
        self._checks[name] = check_fn

    async def check_all(self) -> Dict[str, Any]:
        """Run all registered checks and return standardized health response.

        Returns:
            Dict with keys: status, service, version, timestamp, checks
        """
        checks_results: Dict[str, Any] = {}
        overall_status = "healthy"

        for name, check_fn in self._checks.items():
            start = time.monotonic()
            try:
                result = check_fn()
                if isinstance(result, CheckResult):
                    checks_results[name] = result.to_dict()
                    status = result.status
                elif isinstance(result, dict):
                    checks_results[name] = result
                    status = result.get("status", "ok")
                else:
                    checks_results[name] = {"status": "ok"}
                    status = "ok"
            except Exception as e:
                latency = (time.monotonic() - start) * 1000
                checks_results[name] = {"status": "error", "message": str(e), "latency_ms": round(latency, 2)}
                status = "error"

            if status == "error":
                overall_status = "unhealthy"
            elif status == "warning" and overall_status != "unhealthy":
                overall_status = "degraded"

        return {
            "status": overall_status,
            "service": self.service_name,
            "version": self.version,
            "timestamp": now_brazil().isoformat(),
            "checks": checks_results,
        }

    @staticmethod
    def check_redis(redis_client) -> CheckResult:
        """Check Redis connectivity.

        Args:
            redis_client: Redis client instance (must have .ping() method)

        Returns:
            CheckResult with ok/error status
        """
        try:
            start = time.monotonic()
            result = redis_client.ping()
            latency = (time.monotonic() - start) * 1000
            if result:
                return CheckResult(name="redis", status="ok", latency_ms=latency)
            return CheckResult(name="redis", status="error", detail="Redis ping returned False")
        except Exception as e:
            return CheckResult(name="redis", status="error", detail=str(e))

    @staticmethod
    def check_disk(path: str, min_free_gb: float = 1.0) -> CheckResult:
        """Check disk space.

        Args:
            path: Path to check disk space for
            min_free_gb: Minimum free space in GB for "ok" status

        Returns:
            CheckResult with ok/warning/error status
        """
        try:
            stat = shutil.disk_usage(path)
            free_gb = stat.free / (1024 ** 3)
            percent_free = (stat.free / stat.total) * 100

            if percent_free <= 5:
                status = "error"
            elif percent_free <= 10 or free_gb < min_free_gb:
                status = "warning"
            else:
                status = "ok"

            return CheckResult(
                name="disk",
                status=status,
                detail=f"Free: {free_gb:.2f} GB ({percent_free:.1f}%)",
            )
        except Exception as e:
            return CheckResult(name="disk", status="error", detail=str(e))

    @staticmethod
    def check_ffmpeg() -> CheckResult:
        """Check ffmpeg availability.

        Returns:
            CheckResult with ok/error status and version info
        """
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version_line = result.stdout.split("\n")[0]
                return CheckResult(name="ffmpeg", status="ok", detail=version_line)
            return CheckResult(name="ffmpeg", status="error", detail="ffmpeg returned non-zero exit code")
        except FileNotFoundError:
            return CheckResult(name="ffmpeg", status="error", detail="ffmpeg not found")
        except subprocess.TimeoutExpired:
            return CheckResult(name="ffmpeg", status="error", detail="ffmpeg check timed out")
        except Exception as e:
            return CheckResult(name="ffmpeg", status="error", detail=str(e))

    @staticmethod
    def check_celery(celery_app) -> CheckResult:
        """Check Celery worker availability.

        Args:
            celery_app: Celery app instance

        Returns:
            CheckResult with ok/warning/error status
        """
        try:
            inspect = celery_app.control.inspect(timeout=3.0)
            active = inspect.active()
            if active and len(active) > 0:
                worker_count = len(active)
                return CheckResult(name="celery", status="ok", detail=f"{worker_count} worker(s) active")
            return CheckResult(name="celery", status="warning", detail="No active workers")
        except Exception as e:
            return CheckResult(name="celery", status="warning", detail=str(e))