# LocalStorageService

Local storage implementation for temporary file management with automatic cleanup.

---

## Overview

`LocalStorageService` is the concrete implementation of the `IStorageService` interface, providing local filesystem-based temporary storage with automatic cleanup capabilities.

**Location**: `src/infrastructure/storage/local_storage.py`

**Implements**: [`IStorageService`](../../domain/interfaces/storage-service.md)

**Key Features**:
- ✅ Unique temporary directory creation with timestamps
- ✅ Automatic cleanup of old files/directories
- ✅ Async operations for non-blocking I/O
- ✅ Thread-safe file operations
- ✅ Storage usage monitoring
- ✅ Graceful error handling

---

## Architecture Position

```
┌─────────────────────────────────────┐
│        DOMAIN LAYER                 │
│   IStorageService (Interface)       │
└──────────────┬──────────────────────┘
               │ implements
┌──────────────▼──────────────────────┐
│   INFRASTRUCTURE LAYER              │
│   LocalStorageService (This)        │
│   - create_temp_directory()         │
│   - cleanup_old_files()             │
│   - cleanup_directory()             │
│   - get_temp_files()                │
│   - get_storage_usage()             │
└─────────────────────────────────────┘
```

---

## Class Definition

```python
class LocalStorageService(IStorageService):
    """
    Local storage service for temporary files.
    Implements automatic cleanup of old files.
    """
    
    def __init__(self, base_temp_dir: str = "./temp"):
        """
        Initialize storage service.
        
        Args:
            base_temp_dir: Base directory for temporary files
        """
```

---

## Methods

### `create_temp_directory() -> Path`

Creates a unique temporary directory with timestamp-based naming.

**Returns**: `Path` - Path to created directory

**Raises**: `StorageError` - If directory creation fails

**Implementation**:
```python
async def create_temp_directory(self) -> Path:
    # Create subdirectory with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    temp_dir = self.base_temp_dir / timestamp
    
    loop = asyncio.get_event_loop()
    # Create directory with permissions 0o755
    await loop.run_in_executor(
        None, 
        lambda: temp_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    )
    
    return temp_dir
```

**Naming Pattern**: `YYYYMMDD_HHMMSS_microseconds`

**Example**:
```python
storage = LocalStorageService(base_temp_dir="./temp")
temp_dir = await storage.create_temp_directory()
# Result: ./temp/20251022_143025_123456/
```

**Key Features**:
- Unique directory per request (microsecond precision)
- Async operation (non-blocking)
- Automatic parent directory creation
- Unix permissions: `0o755` (rwxr-xr-x)

---

### `cleanup_old_files(max_age_hours=24) -> int`

Removes files and directories older than the specified age.

**Parameters**:
- `max_age_hours: int` - Maximum age in hours (default: 24)

**Returns**: `int` - Number of items removed

**Raises**: `StorageError` - If cleanup fails

**Implementation**:
```python
async def cleanup_old_files(self, max_age_hours: int = 24) -> int:
    cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
    removed_count = 0
    
    # Iterate over temporary directories
    for item in self.base_temp_dir.iterdir():
        item_time = datetime.fromtimestamp(item.stat().st_mtime)
        
        if item_time < cutoff_time:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            
            removed_count += 1
    
    return removed_count
```

**Example**:
```python
# Remove files older than 12 hours
removed = await storage.cleanup_old_files(max_age_hours=12)
print(f"Removed {removed} old items")
```

**Use Cases**:
- Startup cleanup (remove stale files from previous runs)
- Periodic cleanup (scheduled background task)
- Manual cleanup (admin operation)

---

### `cleanup_directory(directory: Path) -> bool`

Removes a specific directory and all its contents.

**Parameters**:
- `directory: Path` - Directory to remove

**Returns**: `bool` - `True` if successfully removed

**Implementation**:
```python
async def cleanup_directory(self, directory: Path) -> bool:
    if not directory.exists():
        return True
    
    if not directory.is_dir():
        return False
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, shutil.rmtree, directory)
    
    return True
```

**Example**:
```python
# After video processing
temp_dir = await storage.create_temp_directory()
# ... process video ...
await storage.cleanup_directory(temp_dir)
```

**Key Features**:
- Async deletion (non-blocking)
- Recursive removal (deletes all contents)
- Safe handling of non-existent directories

---

### `get_temp_files() -> List[Path]`

Lists all temporary files (not directories).

**Returns**: `List[Path]` - List of file paths

**Implementation**:
```python
async def get_temp_files(self) -> List[Path]:
    if not self.base_temp_dir.exists():
        return []
    
    loop = asyncio.get_event_loop()
    items = await loop.run_in_executor(
        None,
        lambda: list(self.base_temp_dir.rglob("*"))
    )
    
    return [item for item in items if item.is_file()]
```

**Example**:
```python
files = await storage.get_temp_files()
for file in files:
    print(f"File: {file.name}, Size: {file.stat().st_size} bytes")
```

**Note**: Uses `rglob("*")` for recursive search.

---

### `get_storage_usage() -> dict`

Returns detailed storage usage statistics.

**Returns**: `dict` - Storage usage information

**Response Format**:
```python
{
    "total_files": 15,
    "total_size_bytes": 524288000,
    "total_size_mb": 500.0,
    "oldest_file": {
        "path": "./temp/20251020_100000_000000/video.mp4",
        "age_hours": 48.5
    },
    "newest_file": {
        "path": "./temp/20251022_143000_000000/audio.wav",
        "age_hours": 0.5
    }
}
```

**Implementation**:
```python
async def get_storage_usage(self) -> dict:
    files = await self.get_temp_files()
    
    # Calculate total size
    total_size = sum(f.stat().st_size for f in files if f.exists())
    
    # Find oldest and newest files
    file_times = [(f, f.stat().st_mtime) for f in files if f.exists()]
    oldest = min(file_times, key=lambda x: x[1]) if file_times else None
    newest = max(file_times, key=lambda x: x[1]) if file_times else None
    
    return {
        "total_files": len(files),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "oldest_file": {...},
        "newest_file": {...}
    }
```

**Example**:
```python
usage = await storage.get_storage_usage()
print(f"Total: {usage['total_files']} files")
print(f"Size: {usage['total_size_mb']} MB")
print(f"Oldest: {usage['oldest_file']['age_hours']} hours old")
```

---

## Usage Patterns

### 1. Basic Usage (Create + Cleanup)

```python
from src.infrastructure.storage import LocalStorageService

storage = LocalStorageService(base_temp_dir="./temp")

# Create temp directory
temp_dir = await storage.create_temp_directory()

try:
    # Download video to temp directory
    video_path = temp_dir / "video.mp4"
    await download_video(url, video_path)
    
    # Process video
    result = await process_video(video_path)
    
    return result
finally:
    # Always cleanup
    await storage.cleanup_directory(temp_dir)
```

### 2. Periodic Cleanup (Background Task)

```python
async def periodic_cleanup_task(storage: LocalStorageService):
    """Background task for periodic cleanup."""
    while True:
        try:
            removed = await storage.cleanup_old_files(max_age_hours=24)
            logger.info(f"Periodic cleanup: {removed} items removed")
        except Exception as e:
            logger.error(f"Periodic cleanup failed: {e}")
        
        # Wait 30 minutes
        await asyncio.sleep(30 * 60)

# Start background task
asyncio.create_task(periodic_cleanup_task(storage))
```

### 3. Startup Cleanup

```python
async def startup_cleanup(storage: LocalStorageService):
    """Cleanup old files on application startup."""
    logger.info("Starting cleanup on startup...")
    removed = await storage.cleanup_old_files(max_age_hours=24)
    logger.info(f"Startup cleanup: {removed} items removed")

# In main.py
@app.on_event("startup")
async def on_startup():
    storage = LocalStorageService()
    await startup_cleanup(storage)
```

### 4. Monitoring Storage

```python
async def monitor_storage(storage: LocalStorageService):
    """Monitor storage usage periodically."""
    usage = await storage.get_storage_usage()
    
    if usage['total_size_mb'] > 1000:  # 1 GB threshold
        logger.warning(f"High storage usage: {usage['total_size_mb']} MB")
        
        # Trigger aggressive cleanup
        removed = await storage.cleanup_old_files(max_age_hours=12)
        logger.info(f"Emergency cleanup: {removed} items removed")
```

---

## Configuration

Settings from `src/config/settings.py`:

```python
# Storage configuration
temp_dir: str = "./temp"
cleanup_on_startup: bool = True
cleanup_after_processing: bool = True
max_temp_age_hours: int = 24

# Periodic cleanup (v2.0)
enable_periodic_cleanup: bool = True
cleanup_interval_minutes: int = 30
```

**Related**: [Config Layer](../../config/README.md)

---

## Error Handling

### StorageError

Raised when storage operations fail.

```python
from src.domain.exceptions import StorageError

try:
    temp_dir = await storage.create_temp_directory()
except StorageError as e:
    logger.error(f"Storage error: {e}")
    # Handle error (retry, fallback, etc.)
```

**Common Causes**:
- Disk full
- Permission denied
- Invalid path
- I/O errors

---

## Thread Safety

**Async Operations**: All methods use `asyncio.get_event_loop().run_in_executor()` for non-blocking I/O.

**Example**:
```python
# This is non-blocking
await loop.run_in_executor(None, shutil.rmtree, directory)

# Other tasks can run concurrently
```

**Concurrency**: Safe for concurrent use from multiple async tasks.

---

## Performance Considerations

### Directory Creation
- **Time**: ~1ms (SSD), ~10ms (HDD)
- **Overhead**: Minimal (timestamp generation + mkdir)

### Cleanup Operations
- **Time**: Depends on file count (100 files ~100ms)
- **Optimization**: Runs in executor (doesn't block event loop)

### Storage Usage Query
- **Time**: O(n) where n = number of files
- **Optimization**: Cached results (consider caching for high-frequency queries)

---

## Testing

### Unit Test Example

```python
import pytest
from src.infrastructure.storage import LocalStorageService

@pytest.mark.asyncio
async def test_create_temp_directory():
    storage = LocalStorageService(base_temp_dir="./test_temp")
    
    temp_dir = await storage.create_temp_directory()
    
    assert temp_dir.exists()
    assert temp_dir.is_dir()
    assert temp_dir.parent == storage.base_temp_dir
    
    # Cleanup
    await storage.cleanup_directory(temp_dir)

@pytest.mark.asyncio
async def test_cleanup_old_files():
    storage = LocalStorageService(base_temp_dir="./test_temp")
    
    # Create old directory (manually set mtime)
    old_dir = await storage.create_temp_directory()
    # ... set mtime to 48 hours ago ...
    
    removed = await storage.cleanup_old_files(max_age_hours=24)
    
    assert removed >= 1
    assert not old_dir.exists()
```

---

## Related Documentation

- **Interface**: [IStorageService](../../domain/interfaces/storage-service.md)
- **File Cleanup Manager**: [FileCleanupManager](./file-cleanup-manager.md)
- **Use Case**: [CleanupFiles](../../application/use-cases/cleanup-files.md)
- **Config**: [Settings](../../config/README.md)

---

## Version History

| Version | Changes |
|---------|---------|
| **v1.0** | Initial implementation |
| **v2.0** | Added `get_storage_usage()`, async optimization |
| **v2.1** | Improved error handling, thread safety |
| **v3.0** | Enhanced logging, permission management |

---

[← Back](./README.md)

**Version**: 3.0.0
