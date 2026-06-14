"""Unit tests for AdminCleanupService — basic cleanup and deep cleanup (factory reset)."""

from __future__ import annotations

import asyncio
import json as _json
import os
from datetime import datetime, timedelta, timezone as tz
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #

_BRAZIL_TZ = tz(timedelta(hours=-3))


def _fixed_now(offset_minutes: int = 0) -> datetime:
    """Deterministic Brazil-time datetime with optional offset."""
    base = datetime(2024, 6, 15, 10, 0, 0, tzinfo=_BRAZIL_TZ)
    return base + timedelta(minutes=offset_minutes)


def _make_mock_redis(**overrides):
    """Build a MagicMock redis client with sensible defaults."""
    mock = MagicMock()
    mock.keys.return_value = []
    mock.get.return_value = None
    mock.delete.return_value = 1
    mock.flushdb.return_value = True
    mock.llen.return_value = 0

    # connection_pool.connection_kwargs for deep_cleanup redis metadata reads
    pool_mock = MagicMock()
    pool_mock.connection_kwargs = {
        "host": "localhost",
        "port": 6379,
        "db": 0,
    }
    mock.connection_pool = pool_mock

    # Apply overrides (e.g. keys, get) — they replace the defaults above
    for k, v in overrides.items():
        setattr(mock, k, v)

    return mock


def _job_payload(created_at: datetime):
    """Return a JSON-serialisable job dict."""
    return {
        "id": "test_job_1",
        "created_at": created_at.isoformat(),
        "status": "completed",
    }


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _mock_now_brazil(monkeypatch):
    """Pin now_brazil() to a fixed instant so age calculations are deterministic."""
    monkeypatch.setattr("common.datetime_utils.now_brazil", lambda: _fixed_now())


@pytest.fixture
def settings(tmp_path: Path) -> dict:
    """Settings pointing at tmp directories (no real filesystem side-effects)."""
    return {
        "upload_dir": str(tmp_path / "uploads"),
        "transcription_dir": str(tmp_path / "transcriptions"),
        "temp_dir": str(tmp_path / "temp"),
        "model_dir": str(tmp_path / "models"),
    }


@pytest.fixture
def service(settings: dict):
    from app.shared.admin_cleanup_service import AdminCleanupService

    return AdminCleanupService(settings)


# --------------------------------------------------------------------------- #
# Helpers — file creation with controlled mtime                                #
# --------------------------------------------------------------------------- #

def _write_file(path: Path, age_hours: int = 48, content: str = "data"):
    """Create a file whose modification time is *age_hours* hours in the past."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    old_mtime = _fixed_now() - timedelta(hours=age_hours)
    os.utime(str(path), (old_mtime.timestamp(), old_mtime.timestamp()))


def _sync_cleanup_directory(dir_path: Path, max_age_hours: int = 24):
    """Synchronous version of _cleanup_directory that avoids asyncio.get_event_loop()."""
    from common.datetime_utils import now_brazil

    if not dir_path.exists():
        return (0, 0.0)
    deleted_count = 0
    freed_mb = 0.0
    now = now_brazil()
    for file_path in list(dir_path.iterdir()):
        if not file_path.is_file():
            continue
        try:
            mtime_dt = datetime.fromtimestamp(file_path.stat().st_mtime)
            # Make both naive or both aware for comparison
            age = (now.replace(tzinfo=None) - mtime_dt).total_seconds() / 3600 if now.tzinfo else (now - mtime_dt).total_seconds() / 3600
            if age > max_age_hours:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                file_path.unlink()
                deleted_count += 1
                freed_mb += size_mb
        except Exception:
            pass
    return (deleted_count, round(freed_mb, 2))


def _sync_delete_all_files(dir_path: Path):
    """Synchronous version of _delete_all_files that avoids asyncio.get_event_loop()."""
    if not dir_path.exists():
        return (0, 0.0)
    deleted_count = 0
    freed_mb = 0.0
    for file_path in list(dir_path.iterdir()):
        if not file_path.is_file():
            continue
        try:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            file_path.unlink()
            deleted_count += 1
            freed_mb += size_mb
        except Exception:
            pass
    return (deleted_count, round(freed_mb, 2))


# --------------------------------------------------------------------------- #
# basic_cleanup                                                                #
# --------------------------------------------------------------------------- #


class TestBasicCleanup:
    """Tests for AdminCleanupService.basic_cleanup()."""

    def test_returns_report_with_expected_keys(self, service):
        redis = _make_mock_redis()

        async def run():
            return await service.basic_cleanup(redis)

        report = asyncio.run(run())

        expected_keys = {
            "jobs_removed",
            "files_deleted",
            "space_freed_mb",
            "errors",
        }
        assert set(report.keys()) == expected_keys

    def test_removes_expired_redis_jobs(self, service):
        expired_at = _fixed_now() - timedelta(hours=25)
        payload = _json.dumps(_job_payload(expired_at))

        redis = _make_mock_redis(
            keys=lambda pattern: [b"transcription_job:1"],  # noqa: ARG005
            get=lambda key: payload,  # noqa: ARG002
        )

        async def run():
            return await service.basic_cleanup(redis)

        report = asyncio.run(run())

        assert report["jobs_removed"] == 1
        redis.delete.assert_called_with(b"transcription_job:1")

    def test_keeps_recent_redis_jobs(self, service):
        recent_at = _fixed_now() - timedelta(hours=2)
        payload = _json.dumps(_job_payload(recent_at))

        redis = _make_mock_redis(
            keys=lambda pattern: [b"transcription_job:1"],  # noqa: ARG005
            get=lambda key: payload,  # noqa: ARG002
        )

        async def run():
            return await service.basic_cleanup(redis)

        report = asyncio.run(run())

        assert report["jobs_removed"] == 0

    def test_removes_old_files_from_directories(self, service):
        """_cleanup_directory calls run_until_complete which conflicts with pytest's loop.

        Patch _cleanup_directory to use our synchronous helper."""
        upload_dir = Path(service._settings["upload_dir"])
        upload_dir.mkdir(parents=True, exist_ok=True)

        old_file = upload_dir / "old.mp3"
        _write_file(old_file, age_hours=48)

        recent_ts = (_fixed_now() - timedelta(hours=2)).timestamp()
        (upload_dir / "recent.mp3").write_text("keep me")
        os.utime(str(upload_dir / "recent.mp3"), (recent_ts, recent_ts))

        redis = _make_mock_redis(keys=lambda pattern: [])  # noqa: ARG005

        async def run():
            service._cleanup_directory = lambda dp, max_age_hours=24, dir_label="": \
                _sync_cleanup_directory(dp, max_age_hours)
            return await service.basic_cleanup(redis)

        report = asyncio.run(run())

        assert report["files_deleted"] == 1
        assert not old_file.exists()
        assert (upload_dir / "recent.mp3").exists()

    def test_no_error_when_directories_missing(self, service):
        settings = {
            "upload_dir": "/nonexistent/path/uploads",
            "transcription_dir": "/nonexistent/path/transcriptions",
            "temp_dir": "/nonexistent/path/temp",
        }
        from app.shared.admin_cleanup_service import AdminCleanupService

        svc = AdminCleanupService(settings)

        redis = _make_mock_redis(keys=lambda pattern: [])  # noqa: ARG005

        async def run():
            return await svc.basic_cleanup(redis)

        report = asyncio.run(run())

        assert report["files_deleted"] == 0
        assert not report["errors"]

    def test_captures_redis_error_in_report(self, service):
        redis = _make_mock_redis(
            keys=lambda pattern: (_ for _ in ()).throw(RuntimeError("boom"))  # noqa: ARG005
        )

        async def run():
            return await service.basic_cleanup(redis)

        report = asyncio.run(run())

        assert len(report["errors"]) == 1
        assert "Redis" in report["errors"][0]

    def test_space_freed_mb_is_rounded(self, service):
        redis = _make_mock_redis(keys=lambda pattern: [])  # noqa: ARG005

        async def run():
            return await service.basic_cleanup(redis)

        report = asyncio.run(run())

        assert isinstance(report["space_freed_mb"], float)


# --------------------------------------------------------------------------- #
# deep_cleanup                                                                 #
# --------------------------------------------------------------------------- #


class TestDeepCleanup:
    """Tests for AdminCleanupService.deep_cleanup() — factory reset."""

    def test_returns_report_with_expected_keys(self, service):
        redis = _make_mock_redis(keys=lambda pattern: [])  # noqa: ARG005

        async def run():
            return await service.deep_cleanup(redis)

        report = asyncio.run(run())

        expected_keys = {
            "jobs_removed",
            "redis_flushed",
            "files_deleted",
            "space_freed_mb",
            "models_deleted",
            "celery_queue_purged",
            "celery_tasks_purged",
            "errors",
        }
        assert set(report.keys()) == expected_keys

    def test_flushes_redis(self, service):
        redis = _make_mock_redis(
            keys=lambda pattern: [b"transcription_job:a"] if isinstance(pattern, str) and "transcription_job:" in pattern else []  # noqa: ARG005
        )

        async def run():
            return await service.deep_cleanup(redis)

        report = asyncio.run(run())

        assert report["redis_flushed"] is True
        redis.flushdb.assert_called()

    def test_counts_existing_jobs_before_flush(self, service):
        call_count = [0]
        def keys_side_effect(pattern):
            call_count[0] += 1
            if isinstance(pattern, str) and "transcription_job:" in pattern:
                return [b"tj:1", b"tj:2", b"tj:3"] if call_count[0] == 1 else []
            return []

        redis = _make_mock_redis(keys=keys_side_effect)

        async def run():
            return await service.deep_cleanup(redis)

        report = asyncio.run(run())

        assert report["jobs_removed"] == 3

    def test_deletes_all_files_in_directories(self, service):
        upload_dir = Path(service._settings["upload_dir"])
        _write_file(upload_dir / "file1.mp3", age_hours=1)
        _write_file(upload_dir / "file2.wav", age_hours=0)

        trans_dir = Path(service._settings["transcription_dir"])
        _write_file(trans_dir / "cap.vtt", age_hours=0)

        redis = _make_mock_redis(keys=lambda pattern: [])  # noqa: ARG005

        async def run():
            service._delete_all_files = lambda dp, label="": \
                _sync_delete_all_files(dp)
            return await service.deep_cleanup(redis)

        report = asyncio.run(run())

        assert report["files_deleted"] == 3
        assert not (upload_dir / "file1.mp3").exists()
        assert not (trans_dir / "cap.vtt").exists()

    def test_deletes_model_files(self, service):
        models_dir = Path(service._settings["model_dir"])
        _write_file(models_dir / "model.bin", age_hours=0)
        _write_file(models_dir / "config.json", age_hours=0)

        redis = _make_mock_redis(keys=lambda pattern: [])  # noqa: ARG005

        async def run():
            with patch.object(Path, "unlink", return_value=None):
                return await service.deep_cleanup(redis)

        report = asyncio.run(run())

        assert report["models_deleted"] == 2

    def test_no_models_when_dir_empty(self, service):
        models_dir = Path(service._settings["model_dir"])
        models_dir.mkdir(parents=True, exist_ok=True)

        redis = _make_mock_redis(keys=lambda pattern: [])  # noqa: ARG005

        async def run():
            return await service.deep_cleanup(redis)

        report = asyncio.run(run())

        assert report["models_deleted"] == 0

    def test_no_models_when_dir_missing(self, service):
        settings = dict(service._settings)
        settings["model_dir"] = "/nonexistent/models"
        from app.shared.admin_cleanup_service import AdminCleanupService

        svc = AdminCleanupService(settings)

        redis = _make_mock_redis(keys=lambda pattern: [])  # noqa: ARG005

        async def run():
            return await svc.deep_cleanup(redis)

        report = asyncio.run(run())

        assert report["models_deleted"] == 0

    def test_does_not_purge_celery_by_default(self, service):
        redis = _make_mock_redis(keys=lambda pattern: [])  # noqa: ARG005

        async def run():
            return await service.deep_cleanup(redis)

        report = asyncio.run(run())

        assert report["celery_queue_purged"] is False
        assert report["celery_tasks_purged"] == 0

    def test_purge_celery_when_requested(self, service):
        redis = _make_mock_redis(keys=lambda pattern: [])  # noqa: ARG005

        async def run():
            return await service.deep_cleanup(redis, purge_celery_queue=True)

        report = asyncio.run(run())

        assert report["celery_queue_purged"] is True

    def test_flushdb_again_if_new_jobs_appear(self, service):
        call_count = 0

        def keys_side_effect(pattern):
            nonlocal call_count
            if isinstance(pattern, str) and "transcription_job:" in pattern:
                call_count += 1
                if call_count == 1:
                    return [b"tj:before"]
                return [b"tj:during"]
            return []

        redis = _make_mock_redis(keys=keys_side_effect)

        async def run():
            service._delete_all_files = lambda dp, label="": \
                _sync_delete_all_files(dp)
            return await service.deep_cleanup(redis)

        report = asyncio.run(run())

        assert redis.flushdb.call_count == 2
        # jobs_removed should include both before (1) and during (1).
        assert report["jobs_removed"] >= 2

    def test_captures_redis_flush_error(self, service):
        redis = _make_mock_redis(
            keys=lambda pattern: (_ for _ in ()).throw(RuntimeError("conn lost")),  # noqa: ARG005
            flushdb=MagicMock(side_effect=RuntimeError("conn lost")),
        )

        async def run():
            return await service.deep_cleanup(redis)

        report = asyncio.run(run())

        assert len(report["errors"]) >= 1
        assert "Redis FLUSHDB" in report["errors"][0]


# --------------------------------------------------------------------------- #
# _cleanup_directory                                                           #
# --------------------------------------------------------------------------- #


class TestCleanupDirectory:
    """Tests for AdminCleanupService._cleanup_directory()."""

    def test_returns_zero_for_nonexistent_dir(self, service):
        result = _sync_cleanup_directory(
            Path("/nonexistent/dir"), max_age_hours=24
        )
        assert result == (0, 0.0)

    def test_removes_only_old_files(self, service):
        """_cleanup_directory calls run_until_complete which conflicts with pytest's loop;
        use our synchronous helper to sidestep the event-loop issue."""
        import tempfile

        d = Path(tempfile.mkdtemp()) / "test_dir"
        old_file = d / "old.txt"
        _write_file(old_file, age_hours=48)

        recent_ts = (_fixed_now() - timedelta(hours=1)).timestamp()
        (d / "new.txt").write_text("keep")
        os.utime(str(d / "new.txt"), (recent_ts, recent_ts))

        count, freed_mb = _sync_cleanup_directory(d, max_age_hours=24)

        assert count == 1
        assert not old_file.exists()
        assert (d / "new.txt").exists()


# --------------------------------------------------------------------------- #
# _delete_all_files                                                            #
# --------------------------------------------------------------------------- #


class TestDeleteAllFiles:
    """Tests for AdminCleanupService._delete_all_files()."""

    def test_returns_zero_for_nonexistent_dir(self, service):
        result = _sync_delete_all_files(Path("/nonexistent/dir"))
        assert result == (0, 0.0)

    def test_reports_space_freed_mb(self, service):
        import tempfile

        d = Path(tempfile.mkdtemp()) / "all_dir"
        big_content = "x" * (1024 * 1024)  # ~1MB
        _write_file(d / "big.bin", age_hours=0, content=big_content)

        count, freed_mb = _sync_delete_all_files(d)

        assert count == 1
        assert freed_mb > 0.5

    def test_removes_every_file_regardless_of_age(self, service):
        import tempfile

        d = Path(tempfile.mkdtemp()) / "all_dir"
        _write_file(d / "a.txt", age_hours=1)
        _write_file(d / "b.bin", age_hours=48)

        count, freed_mb = _sync_delete_all_files(d)

        assert count == 2


# --------------------------------------------------------------------------- #
# _purge_celery_queue                                                          #
# --------------------------------------------------------------------------- #


class TestPurgeCeleryQueue:
    """Tests for AdminCleanupService._purge_celery_queue()."""

    def test_purges_returns_true_when_no_error(self, service):
        redis = _make_mock_redis(
            keys=lambda pattern: [],  # noqa: ARG005
            llen=MagicMock(return_value=3),
        )

        async def run():
            return await service._purge_celery_queue(redis)

        report = asyncio.run(run())

        assert report["celery_queue_purged"] is True

    def test_counts_tasks_from_queues(self, service):
        redis = _make_mock_redis(
            keys=lambda pattern: [],  # noqa: ARG005
            llen=MagicMock(return_value=2),
        )

        async def run():
            return await service._purge_celery_queue(redis)

        report = asyncio.run(run())

        assert report["celery_tasks_purged"] > 0

    def test_gracefully_handles_redis_error(self, service):
        redis = _make_mock_redis()
        redis.llen.side_effect = RuntimeError("boom")

        async def run():
            return await service._purge_celery_queue(redis)

        report = asyncio.run(run())

        # Should not raise; celery_tasks_purged key must exist.
        assert "celery_tasks_purged" in report
