"""
Process Monitor and Cleanup

Tracks and kills orphaned FFmpeg/subprocess processes to prevent resource leaks.
"""
import asyncio
import logging
import psutil
from typing import List, Set
from pathlib import Path

logger = logging.getLogger(__name__)

# Process monitoring configuration - following Netflix/Google standards
FFMPEG_MAX_AGE_SECONDS = 3600         # 1 hour - kill FFmpeg older than this
DEFAULT_CLEANUP_INTERVAL_MINUTES = 10  # Cleanup every 10 minutes
SECONDS_PER_MINUTE = 60                # Conversion constant
SECONDS_PER_HOUR = 3600                # Conversion constant


class ProcessMonitor:
    """Monitor and cleanup orphaned processes"""
    
    def __init__(self):
        """Initialize process monitor"""
        self.tracked_pids: Set[int] = set()
        logger.info("✅ ProcessMonitor initialized")
    
    def track_process(self, pid: int):
        """Add process to tracking list"""
        self.tracked_pids.add(pid)
        logger.debug(f"Tracking process: PID {pid}")
    
    def untrack_process(self, pid: int):
        """Remove process from tracking list"""
        self.tracked_pids.discard(pid)
        logger.debug(f"Stopped tracking process: PID {pid}")
    
    async def kill_orphaned_processes(self) -> int:
        """
        Kill all tracked processes that are still running
        
        Returns:
            Number of processes killed
        """
        killed_count = 0
        
        for pid in list(self.tracked_pids):
            try:
                process = psutil.Process(pid)
                
                # Check if still running
                if process.is_running():
                    logger.warning(
                        f"⚠️ Killing orphaned process: PID {pid} "
                        f"({process.name()})"
                    )
                    
                    # Try graceful termination first
                    process.terminate()
                    
                    try:
                        # Wait up to 5 seconds
                        process.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        # Force kill if didn't terminate
                        logger.warning(f"Force killing: PID {pid}")
                        process.kill()
                        process.wait(timeout=2)
                    
                    killed_count += 1
                
                self.untrack_process(pid)
            
            except psutil.NoSuchProcess:
                # Process already dead
                self.untrack_process(pid)
            
            except Exception as e:
                logger.error(f"Failed to kill process {pid}: {e}")
        
        if killed_count > 0:
            logger.info(f"✅ Killed {killed_count} orphaned processes")
        
        return killed_count
    
    async def find_ffmpeg_orphans(self) -> List[int]:
        """
        Find FFmpeg processes that may be orphaned
        
        Returns:
            List of PIDs
        """
        orphans = []
        
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                if 'ffmpeg' in proc.info['name'].lower():
                    # Check if running for more than 1 hour (likely orphaned)
                    import time
                    age_seconds = time.time() - proc.info['create_time']
                    
                    if age_seconds > FFMPEG_MAX_AGE_SECONDS:
                        logger.warning(
                            f"⚠️ Found long-running FFmpeg process: "
                            f"PID {proc.info['pid']} (age: {age_seconds / SECONDS_PER_HOUR:.1f}h)"
                        )
                        orphans.append(proc.info['pid'])
            
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return orphans
    
    async def cleanup_all_ffmpeg(self) -> int:
        """
        Kill ALL FFmpeg processes (emergency cleanup)
        
        ⚠️ Use with caution - kills all ffmpeg processes on system
        
        Returns:
            Number of processes killed
        """
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'ffmpeg' in proc.info['name'].lower():
                    logger.warning(
                        f"⚠️ Emergency kill FFmpeg: PID {proc.info['pid']}"
                    )
                    
                    proc.kill()
                    killed_count += 1
            
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if killed_count > 0:
            logger.info(f"✅ Emergency cleanup: killed {killed_count} FFmpeg processes")
        
        return killed_count


# Global process monitor instance
_process_monitor = None


def get_process_monitor() -> ProcessMonitor:
    """Get global ProcessMonitor instance (singleton)"""
    global _process_monitor
    
    if _process_monitor is None:
        _process_monitor = ProcessMonitor()
    
    return _process_monitor


async def periodic_orphan_cleanup(interval_minutes: int = DEFAULT_CLEANUP_INTERVAL_MINUTES):
    """
    Background task to periodically cleanup orphaned processes
    
    Run this as a Celery beat task or async background task.
    
    Args:
        interval_minutes: How often to run cleanup
    """
    monitor = get_process_monitor()
    
    logger.info(
        f"🔄 Starting periodic orphan cleanup "
        f"(interval: {interval_minutes}min)"
    )
    
    while True:
        try:
            # Find and log long-running FFmpeg
            orphans = await monitor.find_ffmpeg_orphans()
            
            if orphans:
                logger.warning(
                    f"⚠️ Found {len(orphans)} potentially orphaned FFmpeg processes"
                )
            
            # Kill tracked orphans
            await monitor.kill_orphaned_processes()
            
        except Exception as e:
            logger.error(f"❌ Orphan cleanup error: {e}")
        
        # Wait for next interval
        await asyncio.sleep(interval_minutes * SECONDS_PER_MINUTE)
