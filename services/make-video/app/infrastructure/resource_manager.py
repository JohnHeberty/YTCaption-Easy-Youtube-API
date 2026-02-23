"""
Sprint-06: Resource Management & Cleanup

Manages system resources (disk, memory) and performs cleanup of temporary files.
"""

import asyncio
import psutil
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """Resource limits configuration"""
    max_memory_mb: int = 2048  # 2GB
    max_disk_gb: float = 5.0   # 5GB free required
    max_concurrent_jobs: int = 5


class ResourceManager:
    """Manages system resources and limits"""
    
    def __init__(self, limits: ResourceLimits = None):
        self.limits = limits or ResourceLimits()
        self.temp_dirs = [Path('/tmp/makevideo'), Path('/tmp/ytcaption')]
    
    async def can_start_job(self, redis_store=None) -> Tuple[bool, str]:
        """
        Check if resources are available to start a new job
        
        Returns:
            (bool, str): (is_allowed, reason or "OK")
        """
        # Check memory
        memory = psutil.virtual_memory()
        if memory.available < self.limits.max_memory_mb * 1024 * 1024:
            return False, f"Low memory: {memory.available / 1024 / 1024:.0f}MB available"
        
        # Check disk
        disk = psutil.disk_usage('/')
        if disk.free < self.limits.max_disk_gb * 1024 * 1024 * 1024:
            return False, f"Low disk: {disk.free / 1024 / 1024 / 1024:.1f}GB free"
        
        # Check concurrent jobs (if redis_store provided)
        if redis_store:
            try:
                active_jobs = await redis_store.get_active_jobs_count()
                if active_jobs >= self.limits.max_concurrent_jobs:
                    return False, f"Max concurrent jobs reached: {active_jobs}"
            except Exception as e:
                logger.warning(f"Could not check concurrent jobs: {e}")
        
        return True, "OK"
    
    async def cleanup_stage(self, stage: str):
        """
        Cleanup files from previous processing stage.
        
        Stages: download, validation, build
        """
        for temp_dir in self.temp_dirs:
            try:
                # Find and remove stage-specific files
                pattern = f"*_{stage}_*"
                for file_path in temp_dir.rglob(pattern):
                    if file_path.is_file():
                        file_path.unlink()
                        logger.debug(f"Cleaned up: {file_path}")
            except Exception as e:
                logger.warning(f"Cleanup error for {stage}: {e}")
    
    async def cleanup_all(self):
        """Full cleanup of all temporary files"""
        cleaned_count = 0
        freed_bytes = 0
        
        for temp_dir in self.temp_dirs:
            try:
                if not temp_dir.exists():
                    continue
                    
                for file_path in temp_dir.rglob('*'):
                    if file_path.is_file():
                        try:
                            freed_bytes += file_path.stat().st_size
                            file_path.unlink()
                            cleaned_count += 1
                        except Exception as e:
                            logger.warning(f"Could not delete {file_path}: {e}")
            except Exception as e:
                logger.warning(f"Cleanup error for {temp_dir}: {e}")
        
        if cleaned_count > 0:
            logger.info(
                f"Cleanup completed: {cleaned_count} files, "
                f"freed {freed_bytes / 1024 / 1024:.1f}MB"
            )
    
    async def get_resource_stats(self) -> dict:
        """Get current resource usage statistics"""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "memory": {
                "percent": memory.percent,
                "available_mb": memory.available / 1024 / 1024,
                "used_mb": memory.used / 1024 / 1024,
                "total_mb": memory.total / 1024 / 1024
            },
            "disk": {
                "percent": disk.percent,
                "free_gb": disk.free / 1024 / 1024 / 1024,
                "used_gb": disk.used / 1024 / 1024 / 1024,
                "total_gb": disk.total / 1024 / 1024 / 1024
            }
        }


# Global instance
_resource_manager = None


def get_resource_manager(limits: ResourceLimits = None) -> ResourceManager:
    """Get or create resource manager singleton"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager(limits)
    return _resource_manager
