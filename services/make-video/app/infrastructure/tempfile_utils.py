"""
Temporary File Utilities with Context Managers

Provides automatic cleanup of temporary files and directories using context managers.
Prevents disk space leaks from abandoned temp files.
"""
import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator

logger = logging.getLogger(__name__)

# Default cleanup configuration - following industry standards
DEFAULT_TEMP_FILE_MAX_AGE_HOURS = 24  # Delete temp files older than 24h
SECONDS_PER_HOUR = 3600                # Conversion constant


@contextmanager
def temp_file(
    suffix: Optional[str] = None,
    prefix: Optional[str] = "make_video_",
    dir: Optional[str] = None,
    delete: bool = True
) -> Generator[Path, None, None]:
    """
    Context manager for temporary files with guaranteed cleanup
    
    Usage:
        with temp_file(suffix='.mp4') as tmp:
            process_video(tmp)
        # File automatically deleted here
    
    Args:
        suffix: File extension (e.g., '.mp4', '.srt')
        prefix: Filename prefix
        dir: Directory for temp file (default: system temp)
        delete: Whether to delete file on exit (default: True)
    
    Yields:
        Path object for the temporary file
    """
    fd = None
    path = None
    
    try:
        # Create temporary file
        fd, temp_path = tempfile.mkstemp(
            suffix=suffix or '',
            prefix=prefix or 'make_video_',
            dir=dir
        )
        
        path = Path(temp_path)
        
        logger.debug(f"Created temp file: {path}")
        
        yield path
    
    finally:
        # Cleanup
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass  # Already closed
        
        if delete and path and path.exists():
            try:
                path.unlink()
                logger.debug(f"Deleted temp file: {path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file {path}: {e}")


@contextmanager
def temp_dir(
    suffix: Optional[str] = None,
    prefix: Optional[str] = "make_video_",
    dir: Optional[str] = None,
    delete: bool = True
) -> Generator[Path, None, None]:
    """
    Context manager for temporary directories with guaranteed cleanup
    
    Usage:
        with temp_dir() as tmpdir:
            process_files_in(tmpdir)
        # Directory automatically deleted here
    
    Args:
        suffix: Directory name suffix
        prefix: Directory name prefix
        dir: Parent directory (default: system temp)
        delete: Whether to delete directory on exit (default: True)
    
    Yields:
        Path object for the temporary directory
    """
    path = None
    
    try:
        # Create temporary directory
        temp_path = tempfile.mkdtemp(
            suffix=suffix or '',
            prefix=prefix or 'make_video_',
            dir=dir
        )
        
        path = Path(temp_path)
        
        logger.debug(f"Created temp directory: {path}")
        
        yield path
    
    finally:
        # Cleanup
        if delete and path and path.exists():
            try:
                shutil.rmtree(path)
                logger.debug(f"Deleted temp directory: {path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp directory {path}: {e}")


@contextmanager
def temp_file_copy(
    source: Path,
    suffix: Optional[str] = None,
    prefix: Optional[str] = "copy_"
) -> Generator[Path, None, None]:
    """
    Context manager that copies a file to temp location and cleans up
    
    Useful when you need to modify a file without affecting the original.
    
    Usage:
        with temp_file_copy(original_path) as tmp:
            modify_video(tmp)
        # Temp copy automatically deleted here
    
    Args:
        source: Source file to copy
        suffix: File extension (inferred from source if not provided)
        prefix: Filename prefix
    
    Yields:
        Path object for the temporary copy
    """
    if suffix is None:
        suffix = source.suffix
    
    with temp_file(suffix=suffix, prefix=prefix) as tmp:
        shutil.copy2(source, tmp)
        logger.debug(f"Copied {source} → {tmp}")
        
        yield tmp


class TempFileManager:
    """
    Manager for multiple temporary files with batch cleanup
    
    Useful when you need to track multiple temp files and ensure
    they're all cleaned up, even if exceptions occur.
    
    Usage:
        manager = TempFileManager()
        try:
            tmp1 = manager.create_file(suffix='.mp4')
            tmp2 = manager.create_file(suffix='.srt')
            process(tmp1, tmp2)
        finally:
            manager.cleanup_all()
    """
    
    def __init__(self, prefix: str = "make_video_"):
        self.prefix = prefix
        self.files: list[Path] = []
        self.dirs: list[Path] = []
    
    def create_file(
        self,
        suffix: Optional[str] = None,
        dir: Optional[str] = None
    ) -> Path:
        """Create and track a temporary file"""
        fd, temp_path = tempfile.mkstemp(
            suffix=suffix or '',
            prefix=self.prefix,
            dir=dir
        )
        
        os.close(fd)
        path = Path(temp_path)
        self.files.append(path)
        
        logger.debug(f"Created tracked temp file: {path}")
        
        return path
    
    def create_dir(
        self,
        suffix: Optional[str] = None,
        dir: Optional[str] = None
    ) -> Path:
        """Create and track a temporary directory"""
        temp_path = tempfile.mkdtemp(
            suffix=suffix or '',
            prefix=self.prefix,
            dir=dir
        )
        
        path = Path(temp_path)
        self.dirs.append(path)
        
        logger.debug(f"Created tracked temp directory: {path}")
        
        return path
    
    def cleanup_all(self):
        """Clean up all tracked temporary files and directories"""
        errors = []
        
        # Delete files
        for path in self.files:
            if path.exists():
                try:
                    path.unlink()
                    logger.debug(f"Deleted tracked temp file: {path}")
                except Exception as e:
                    errors.append((path, e))
                    logger.warning(f"Failed to delete temp file {path}: {e}")
        
        # Delete directories
        for path in self.dirs:
            if path.exists():
                try:
                    shutil.rmtree(path)
                    logger.debug(f"Deleted tracked temp directory: {path}")
                except Exception as e:
                    errors.append((path, e))
                    logger.warning(f"Failed to delete temp directory {path}: {e}")
        
        # Clear lists
        self.files.clear()
        self.dirs.clear()
        
        if errors:
            logger.warning(
                f"⚠️ Failed to cleanup {len(errors)} temporary items"
            )
        else:
            logger.debug("✅ All temporary items cleaned up")
    
    def __enter__(self):
        """Support using as context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Automatic cleanup on context exit"""
        self.cleanup_all()
        return False


def cleanup_old_temp_files(
    directory: Optional[str] = None,
    prefix: str = "make_video_",
    max_age_hours: int = DEFAULT_TEMP_FILE_MAX_AGE_HOURS
):
    """
    Cleanup old temporary files that weren't properly deleted
    
    Useful for periodic cleanup jobs to prevent disk space leaks.
    
    Args:
        directory: Directory to scan (default: system temp)
        prefix: Only delete files/dirs with this prefix
        max_age_hours: Delete files older than this many hours
    
    Returns:
        Number of items deleted
    """
    import time
    
    if directory is None:
        directory = tempfile.gettempdir()
    
    scan_dir = Path(directory)
    now = time.time()
    max_age_seconds = max_age_hours * SECONDS_PER_HOUR
    deleted_count = 0
    
    logger.info(f"🧹 Scanning for old temp files in: {scan_dir}")
    
    for item in scan_dir.iterdir():
        # Check if matches our prefix
        if not item.name.startswith(prefix):
            continue
        
        try:
            # Check age
            age_seconds = now - item.stat().st_mtime
            
            if age_seconds > max_age_seconds:
                logger.info(
                    f"Deleting old temp item (age: {age_seconds / SECONDS_PER_HOUR:.1f}h): {item.name}"
                )
                
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
                
                deleted_count += 1
        
        except Exception as e:
            logger.warning(f"Failed to cleanup {item}: {e}")
    
    logger.info(f"✅ Cleaned up {deleted_count} old temp items")
    
    return deleted_count
