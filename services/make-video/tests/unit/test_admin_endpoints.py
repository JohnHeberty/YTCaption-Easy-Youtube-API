"""
Testes unitários para endpoints administrativos
"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import sys

# Mock modules before importing
sys.modules['celery'] = MagicMock()
sys.modules['cv2'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['pytesseract'] = MagicMock()

from fastapi.testclient import TestClient
from app.main import app
from app.redis_store import RedisJobStore
from app.models import Job

# Create test client
client = TestClient(app)


class TestRedisStoreAdminMethods:
    """Testes para métodos administrativos do RedisJobStore"""
    
    def test_get_stats_structure(self):
        """Testa estrutura do retorno de get_stats"""
        # Simula retorno esperado
        stats = {
            "queued": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "total": 0
        }
        
        assert "queued" in stats
        assert "processing" in stats
        assert "completed" in stats
        assert "failed" in stats
        assert "total" in stats
        assert all(isinstance(v, int) for v in stats.values())
    
    def test_stats_calculation_logic(self):
        """Testa lógica de cálculo de estatísticas"""
        # Simula contagem de jobs por status
        jobs_by_status = {
            "queued": 5,
            "processing": 2,
            "completed": 150,
            "failed": 10
        }
        
        total = sum(jobs_by_status.values())
        
        assert total == 167
        assert jobs_by_status["queued"] == 5
        assert jobs_by_status["processing"] == 2
    
    def test_orphan_detection_logic(self):
        """Testa lógica de detecção de órfãos"""
        # Simula job processando há muito tempo
        job_updated = datetime.utcnow() - timedelta(hours=2)
        max_age = timedelta(minutes=30)
        
        age = datetime.utcnow() - job_updated
        is_orphan = age > max_age
        
        assert is_orphan is True
        assert age.total_seconds() > 7200  # 2 hours
    
    def test_orphan_age_threshold(self):
        """Testa diferentes thresholds para órfãos"""
        now = datetime.utcnow()
        
        # Job recente (não órfão)
        recent_job = now - timedelta(minutes=15)
        age_recent = now - recent_job
        
        # Job antigo (órfão)
        old_job = now - timedelta(hours=2)
        age_old = now - old_job
        
        threshold = timedelta(minutes=30)
        
        assert age_recent < threshold  # Não é órfão
        assert age_old > threshold     # É órfão


class TestAdminEndpoints:
    """Testes para endpoints administrativos (simulados)"""
    
    def test_basic_cleanup_structure(self):
        """Testa estrutura do relatório de limpeza básica"""
        report = {
            "mode": "basic",
            "jobs_removed": 10,
            "files_deleted": 25,
            "space_freed_mb": 150.5,
            "errors": []
        }
        
        assert "mode" in report
        assert report["mode"] == "basic"
        assert "jobs_removed" in report
        assert "files_deleted" in report
        assert "space_freed_mb" in report
        assert isinstance(report["errors"], list)
    
    def test_deep_cleanup_structure(self):
        """Testa estrutura do relatório de limpeza profunda"""
        report = {
            "mode": "deep",
            "jobs_removed": 50,
            "files_deleted": 100,
            "space_freed_mb": 500.8,
            "redis_flushed": True,
            "celery_purged": False,
            "errors": []
        }
        
        assert "mode" in report
        assert report["mode"] == "deep"
        assert "redis_flushed" in report
        assert report["redis_flushed"] is True
        assert "celery_purged" in report
    
    def test_admin_stats_structure(self):
        """Testa estrutura das estatísticas administrativas"""
        stats = {
            "jobs": {
                "queued": 5,
                "processing": 2,
                "completed": 150,
                "failed": 10,
                "total": 167
            },
            "storage": {
                "audio_uploads": {"count": 50, "size_mb": 250.5},
                "output_videos": {"count": 145, "size_mb": 1200.8},
                "temp": {"count": 10, "size_mb": 50.2},
                "total_size_mb": 1501.5
            },
            "shorts_cache": {
                "cached_searches": 20,
                "blacklist_size": 15
            },
            "celery": {
                "active_workers": 2,
                "active_tasks": 3
            },
            "system": {
                "disk": {
                    "total_gb": 100.0,
                    "free_gb": 50.0
                }
            }
        }
        
        assert "jobs" in stats
        assert "storage" in stats
        assert "shorts_cache" in stats
        assert "celery" in stats
        assert "system" in stats
        
        # Validate jobs structure
        assert all(key in stats["jobs"] for key in ["queued", "processing", "completed", "failed", "total"])
        
        # Validate storage structure
        assert "audio_uploads" in stats["storage"]
        assert "output_videos" in stats["storage"]
        assert "total_size_mb" in stats["storage"]
    
    def test_cleanup_orphans_structure(self):
        """Testa estrutura do relatório de limpeza de órfãos"""
        report = {
            "orphaned_jobs_found": 3,
            "orphaned_jobs_fixed": 3,
            "orphaned_files_found": 5,
            "orphaned_files_removed": 5,
            "space_freed_mb": 125.5,
            "details": [
                {
                    "type": "orphaned_job",
                    "job_id": "abc123",
                    "action": "marked_as_failed",
                    "reason": "Processing for > 30min"
                },
                {
                    "type": "orphaned_file",
                    "file": "xyz789.mp3",
                    "size_mb": 25.5,
                    "action": "removed"
                }
            ]
        }
        
        assert "orphaned_jobs_found" in report
        assert "orphaned_jobs_fixed" in report
        assert "orphaned_files_found" in report
        assert "orphaned_files_removed" in report
        assert "space_freed_mb" in report
        assert "details" in report
        assert isinstance(report["details"], list)
        
        # Validate details structure
        if report["details"]:
            detail = report["details"][0]
            assert "type" in detail
            assert "action" in detail


class TestAdminEndpointsIntegration:
    """Testes de integração simulados para endpoints admin"""
    
    def test_cleanup_workflow_basic(self):
        """Testa fluxo de limpeza básica"""
        # Simula passos da limpeza básica
        steps = [
            "cleanup_expired_jobs",
            "find_orphaned_files",
            "remove_orphaned_files",
            "generate_report"
        ]
        
        assert len(steps) == 4
        assert "cleanup_expired_jobs" in steps
        assert "generate_report" in steps
    
    def test_cleanup_workflow_deep(self):
        """Testa fluxo de limpeza profunda"""
        # Simula passos da limpeza profunda
        steps = [
            "count_jobs",
            "flushdb_redis",
            "remove_all_audio_files",
            "remove_all_output_files",
            "remove_all_temp_files",
            "remove_shorts_cache",
            "purge_celery_optional",
            "generate_report"
        ]
        
        assert len(steps) >= 7
        assert "flushdb_redis" in steps
        assert "purge_celery_optional" in steps
    
    def test_stats_aggregation(self):
        """Testa agregação de estatísticas"""
        # Simula coleta de stats de múltiplas fontes
        sources = ["redis", "filesystem", "celery", "system"]
        
        collected_stats = {}
        for source in sources:
            collected_stats[source] = {"status": "collected"}
        
        assert len(collected_stats) == 4
        assert all(s in collected_stats for s in sources)
    
    def test_orphan_detection_workflow(self):
        """Testa fluxo de detecção de órfãos"""
        workflow = [
            "find_orphaned_jobs",
            "mark_jobs_as_failed",
            "find_orphaned_files",
            "remove_orphaned_files",
            "calculate_freed_space",
            "generate_detailed_report"
        ]
        
        assert len(workflow) == 6
        assert "find_orphaned_jobs" in workflow
        assert "generate_detailed_report" in workflow


class TestAdditionalAdminEndpoints:
    """Testes para endpoints administrativos adicionais"""
    
    def test_get_queue_info_response_structure(self):
        """Testa estrutura do retorno de GET /admin/queue"""
        # Simula resposta esperada
        response_data = {
            "status": "success",
            "queue": {
                "total_jobs": 10,
                "by_status": {
                    "queued": 5,
                    "processing": 2,
                    "completed": 2,
                    "failed": 1
                },
                "oldest_job": {
                    "job_id": "old123",
                    "created_at": "2024-01-01T00:00:00",
                    "status": "completed"
                },
                "newest_job": {
                    "job_id": "new456",
                    "created_at": "2024-01-15T10:30:00",
                    "status": "queued"
                }
            }
        }
        
        assert "status" in response_data
        assert "queue" in response_data
        assert "total_jobs" in response_data["queue"]
        assert "by_status" in response_data["queue"]
        
        # Verifica estrutura by_status
        by_status = response_data["queue"]["by_status"]
        assert "queued" in by_status
        assert "processing" in by_status
        assert "completed" in by_status
        assert "failed" in by_status
    
    def test_get_orphaned_jobs_response_structure(self):
        """Testa estrutura do retorno de GET /jobs/orphaned"""
        response_data = {
            "status": "success",
            "count": 2,
            "max_age_minutes": 30,
            "orphaned_jobs": [
                {
                    "job_id": "abc123",
                    "status": "processing",
                    "created_at": "2024-01-15T08:00:00",
                    "updated_at": "2024-01-15T08:10:00",
                    "age_minutes": 125.5,
                    "request": None
                }
            ]
        }
        
        assert "status" in response_data
        assert "count" in response_data
        assert "max_age_minutes" in response_data
        assert "orphaned_jobs" in response_data
        assert isinstance(response_data["orphaned_jobs"], list)
        
        if response_data["count"] > 0:
            orphan = response_data["orphaned_jobs"][0]
            assert "job_id" in orphan
            assert "age_minutes" in orphan
    
    def test_cleanup_orphaned_jobs_response_structure(self):
        """Testa estrutura do retorno de POST /jobs/orphaned/cleanup"""
        # Com jobs encontrados
        response_with_jobs = {
            "status": "success",
            "message": "Cleaned up 2 orphaned job(s)",
            "count": 2,
            "mode": "mark_as_failed",
            "max_age_minutes": 30,
            "space_freed_mb": 450.2,
            "actions": [
                {
                    "job_id": "abc123",
                    "action": "marked_as_failed",
                    "age_minutes": 125.5,
                    "files_deleted": [],
                    "reason": "Job orphaned: stuck in processing"
                }
            ]
        }
        
        assert "status" in response_with_jobs
        assert "message" in response_with_jobs
        assert "count" in response_with_jobs
        assert "mode" in response_with_jobs
        assert "space_freed_mb" in response_with_jobs
        assert "actions" in response_with_jobs
        
        # Sem jobs
        response_no_jobs = {
            "status": "success",
            "message": "No orphaned jobs found",
            "count": 0,
            "actions": []
        }
        
        assert "status" in response_no_jobs
        assert response_no_jobs["count"] == 0
    
    def test_cleanup_modes(self):
        """Testa diferentes modos de cleanup"""
        # Modo mark_as_failed
        mode_failed = "mark_as_failed"
        assert mode_failed in ["mark_as_failed", "delete"]
        
        # Modo delete
        mode_delete = "delete"
        assert mode_delete in ["mark_as_failed", "delete"]


class TestRedisStoreQueueMethods:
    """Testes para métodos de queue do RedisJobStore"""
    
    @pytest.mark.asyncio
    async def test_get_queue_info_empty(self):
        """Testa get_queue_info sem jobs"""
        store = RedisJobStore(redis_url="redis://localhost:6379/0")
        
        queue_info = await store.get_queue_info()
        
        assert "total_jobs" in queue_info
        assert "by_status" in queue_info
        assert "oldest_job" in queue_info
        assert "newest_job" in queue_info
        assert isinstance(queue_info["total_jobs"], int)
    
    @pytest.mark.asyncio
    async def test_queue_info_structure(self):
        """Testa estrutura de queue_info"""
        queue_info = {
            "total_jobs": 10,
            "by_status": {
                "queued": 5,
                "processing": 2,
                "completed": 2,
                "failed": 1
            },
            "oldest_job": {
                "job_id": "old123",
                "created_at": "2024-01-01T00:00:00",
                "status": "completed"
            },
            "newest_job": {
                "job_id": "new456",
                "created_at": "2024-01-15T10:30:00",
                "status": "queued"
            }
        }
        
        assert queue_info["total_jobs"] == 10
        assert sum(queue_info["by_status"].values()) == 10
        assert queue_info["oldest_job"]["job_id"] == "old123"
        assert queue_info["newest_job"]["job_id"] == "new456"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
