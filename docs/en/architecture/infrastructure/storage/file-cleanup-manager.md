# FileCleanupManager

Automatic temporary file management with context managers, periodic cleanup, and TTL-based deletion.

---

## Overview

`FileCleanupManager` provides advanced temporary file lifecycle management with automatic cleanup, file tracking, and background cleanup tasks. It ensures zero memory leaks and proper cleanup even when errors occur.

**Location**: `src/infrastructure/storage/file_cleanup_manager.py`

**Key Features**:
- ✅ File tracking with Set-based registry
- ✅ Periodic background cleanup task
- ✅ Context managers for guaranteed cleanup
- ✅ TTL (Time-To-Live) based deletion
- ✅ Thread-safe operations
- ✅ Automatic cleanup on shutdown
- ✅ Empty directory removal

---

## Components

### 1. TempFileContext (Sync Context Manager)

Context manager for synchronous temporary file handling.

```python
class TempFileContext:
    """Context manager for temp files with auto-cleanup."""
    
    def __init__(self, file_path: Path, cleanup_on_error: bool = True):
        ...
    
    def __enter__(self) -> Path:
        return self.file_path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._should_cleanup and (self.cleanup_on_error or exc_type is None):
            self._cleanup()
```

**Usage**:
```python
with TempFileContext(Path("temp/video.mp4")) as temp_file:
    # Download/process file
    download_video(url, temp_file)
# File automatically deleted on exit
```

**Features**:
- Automatic cleanup on context exit
- Optional cleanup on error
- `keep()` method to preserve file

### 2. temp_file_async (Async Context Manager)

Async version for non-blocking cleanup.

```python
@asynccontextmanager
async def temp_file_async(file_path: Path, cleanup_on_error: bool = True):
    try:
        yield file_path
    finally:
        if cleanup_on_error or not asyncio.current_task().cancelled():
            await asyncio.to_thread(file_path.unlink)
```

**Usage**:
```python
async with temp_file_async(Path("temp/audio.wav")) as temp_file:
    await process_audio(temp_file)
# File automatically deleted (async)
```

### 3. FileCleanupManager (Main Manager)

Core manager for tracking and periodic cleanup.

```python
class FileCleanupManager:
    """
    Automatic temporary file cleanup manager.
    
    Features:
    - File tracking
    - Periodic cleanup
    - Forced shutdown cleanup
    - Thread-safe
    """
    
    def __init__(
        self,
        base_temp_dir: Path,
        default_ttl_hours: int = 24,
        cleanup_interval_minutes: int = 30
    ):
        ...
```

---

## Methods

### File Tracking

#### `track_file(file_path: Path)`

Adds file to tracking registry for future cleanup.

```python
manager = FileCleanupManager(Path("./temp"))
temp_file = Path("./temp/video.mp4")
manager.track_file(temp_file)
```

**Use Case**: Track files that should be cleaned up later.

#### `untrack_file(file_path: Path)`

Removes file from tracking (file was moved/processed).

```python
# File was processed and moved to permanent storage
manager.untrack_file(temp_file)
```

### Cleanup Operations

#### `cleanup_file(file_path: Path) -> bool`

Removes specific file and untracks it.

```python
success = await manager.cleanup_file(Path("./temp/old_video.mp4"))
```

**Returns**: `True` if successfully removed

#### `cleanup_directory(directory: Path, recursive: bool = True) -> bool`

Removes directory and its contents.

```python
# Remove entire temp directory
await manager.cleanup_directory(Path("./temp/session_123"), recursive=True)
```

**Features**:
- Recursive deletion (default)
- Automatically untracks contained files
- Safe for non-existent directories

#### `cleanup_old_files(max_age_hours: Optional[int] = None) -> dict`

Removes files older than specified age.

```python
# Remove files older than 12 hours
result = await manager.cleanup_old_files(max_age_hours=12)

# Result:
{
    "removed_count": 15,
    "removed_size_bytes": 524288000,
    "removed_size_mb": 500.0,
    "errors": 0,
    "tracked_files_remaining": 5
}
```

**Algorithm**:
1. Check all tracked files
2. Compare file mtime with cutoff time
3. Delete old files
4. Remove empty directories
5. Return statistics

### Periodic Cleanup

#### `start_periodic_cleanup()`

Starts background cleanup task.

```python
manager = FileCleanupManager(
    base_temp_dir=Path("./temp"),
    default_ttl_hours=24,
    cleanup_interval_minutes=30
)
manager.start_periodic_cleanup()
# Cleanup runs every 30 minutes
```

**Implementation**:
```python
async def _periodic_cleanup_loop(self):
    while self._running:
        await asyncio.sleep(self.cleanup_interval_minutes * 60)
        await self.cleanup_old_files()
```

#### `stop_periodic_cleanup()`

Stops background cleanup task.

```python
await manager.stop_periodic_cleanup()
```

**Use Case**: Application shutdown.

### Statistics

#### `get_stats() -> dict`

Returns manager statistics.

```python
stats = manager.get_stats()

# Result:
{
    "tracked_files": 10,
    "total_size_bytes": 104857600,
    "total_size_mb": 100.0,
    "periodic_cleanup_running": True,
    "default_ttl_hours": 24,
    "cleanup_interval_minutes": 30
}
```

---

## Usage Patterns

### 1. Application Lifecycle

```python
from src.infrastructure.storage import FileCleanupManager
from pathlib import Path

# Initialize
cleanup_manager = FileCleanupManager(
    base_temp_dir=Path("./temp"),
    default_ttl_hours=24,
    cleanup_interval_minutes=30
)

# Startup: cleanup old files from previous runs
@app.on_event("startup")
async def startup():
    await cleanup_manager.cleanup_old_files()
    cleanup_manager.start_periodic_cleanup()

# Shutdown: stop cleanup and remove tracked files
@app.on_event("shutdown")
async def shutdown():
    await cleanup_manager.stop_periodic_cleanup()
    await cleanup_manager.cleanup_all_tracked()
```

### 2. Request-Scoped Cleanup

```python
async def process_video_endpoint(url: str):
    temp_dir = Path("./temp") / generate_session_id()
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Track directory
    cleanup_manager.track_file(temp_dir)
    
    try:
        video_path = temp_dir / "video.mp4"
        
        # Download and process
        await download_video(url, video_path)
        result = await transcribe_video(video_path)
        
        return result
    finally:
        # Cleanup after processing
        await cleanup_manager.cleanup_directory(temp_dir)
```

### 3. Context Manager Pattern

```python
async def download_and_process(url: str):
    temp_path = Path("./temp/video.mp4")
    
    async with temp_file_async(temp_path) as file:
        await download_video(url, file)
        result = await process_video(file)
        return result
    # File auto-deleted here
```

### 4. Selective File Preservation

```python
def process_important_file(file_path: Path):
    context = TempFileContext(file_path)
    
    with context as temp_file:
        result = process_file(temp_file)
        
        if result.is_important:
            context.keep()  # Don't delete
            move_to_permanent_storage(temp_file)
        
        return result
```

---

## Configuration

From `src/config/settings.py`:

```python
# Cleanup settings
cleanup_on_startup: bool = True
cleanup_after_processing: bool = True
max_temp_age_hours: int = 24

# Periodic cleanup
enable_periodic_cleanup: bool = True
cleanup_interval_minutes: int = 30
```

**Integration**:
```python
from src.config.settings import settings

manager = FileCleanupManager(
    base_temp_dir=Path(settings.temp_dir),
    default_ttl_hours=settings.max_temp_age_hours,
    cleanup_interval_minutes=settings.cleanup_interval_minutes
)
```

---

## Thread Safety

**Locking Strategy**: Uses `threading.RLock()` for file tracking set.

```python
# Thread-safe tracking
with self._lock:
    self._tracked_files.add(file_path)
```

**Async Operations**: All I/O operations use `asyncio.to_thread()`.

```python
# Non-blocking file deletion
await asyncio.to_thread(file_path.unlink)
```

---

## Performance

### Periodic Cleanup
- **Interval**: Configurable (default 30 min)
- **Impact**: Minimal (runs in background)
- **Overhead**: ~10ms per 100 files

### File Tracking
- **Data Structure**: `Set[Path]` (O(1) add/remove)
- **Memory**: ~100 bytes per tracked file
- **Typical Load**: 10-50 tracked files

---

## Testing

```python
import pytest
from pathlib import Path
from src.infrastructure.storage import FileCleanupManager, temp_file_async

@pytest.mark.asyncio
async def test_cleanup_old_files():
    manager = FileCleanupManager(
        base_temp_dir=Path("./test_temp"),
        default_ttl_hours=1
    )
    
    # Create old file
    old_file = Path("./test_temp/old.txt")
    old_file.write_text("test")
    manager.track_file(old_file)
    
    # Set mtime to 2 hours ago
    import time
    old_time = time.time() - (2 * 3600)
    os.utime(old_file, (old_time, old_time))
    
    # Cleanup
    result = await manager.cleanup_old_files()
    
    assert result["removed_count"] >= 1
    assert not old_file.exists()

@pytest.mark.asyncio
async def test_context_manager():
    temp_path = Path("./test_temp/temp.txt")
    
    async with temp_file_async(temp_path) as file:
        file.write_text("test data")
        assert file.exists()
    
    # File should be deleted after context
    assert not temp_path.exists()
```

---

## Error Handling

### Failed Cleanup

```python
try:
    await manager.cleanup_file(problematic_file)
except Exception as e:
    logger.error(f"Cleanup failed: {e}")
    # Manager continues with other files
```

**Behavior**: Errors logged but don't stop batch cleanup.

### Shutdown Cleanup

```python
# Ensures cleanup even on errors
async def shutdown():
    try:
        await manager.cleanup_all_tracked()
    except Exception as e:
        logger.error(f"Shutdown cleanup failed: {e}")
```

---

## Related Documentation

- **LocalStorageService**: [local-storage.md](./local-storage.md)
- **Use Case**: [CleanupFiles](../../application/use-cases/cleanup-files.md)
- **Config**: [Settings](../../config/README.md)

---

## Best Practices

### ✅ DO

```python
# Always use context managers
async with temp_file_async(path) as file:
    await process(file)

# Track files that need later cleanup
manager.track_file(temp_file)

# Start periodic cleanup in production
manager.start_periodic_cleanup()
```

### ❌ DON'T

```python
# Don't forget to untrack moved files
# manager.untrack_file(moved_file)  # Missing!

# Don't block with synchronous cleanup in async context
# Use await manager.cleanup_file() instead

# Don't use extremely short cleanup intervals
# cleanup_interval_minutes=1  # Too frequent!
```

---

## Version History

| Version | Changes |
|---------|---------|
| **v2.0** | Initial FileCleanupManager |
| **v2.1** | Added context managers, file tracking |
| **v3.0** | Periodic cleanup, statistics |

---

[← Back](./README.md)

**Version**: 3.0.0
