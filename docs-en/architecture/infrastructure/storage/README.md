# Storage Subsystem

## Overview

The **Storage Subsystem** handles all file operations, temporary file management, and cleanup policies. It provides atomic writes, safe file handling, and automated cleanup to prevent disk space exhaustion.

---

## Module Structure

```
storage/
├── __init__.py
├── local_storage.py           # Main storage implementation
├── file_cleanup_manager.py    # Automated cleanup
├── local-storage.md            # Documentation
├── file-cleanup-manager.md    # Documentation
└── README.md                  # This file
```

---

## Components

### 1. LocalStorageService
📄 **Documentation:** [local-storage.md](local-storage.md) (~150 lines)

**Responsibilities:**
- File save/read operations
- Directory management
- Atomic writes with temp files
- Storage usage reporting

**Key Methods:**
- `save_file(content, filename, subdir)` - Save with atomic write
- `read_file(file_path)` - Read file contents
- `delete_file(file_path)` - Remove file
- `get_storage_usage()` - Disk usage statistics

### 2. FileCleanupManager
📄 **Documentation:** [file-cleanup-manager.md](file-cleanup-manager.md) (~120 lines)

**Responsibilities:**
- Automatic file cleanup (TTL-based)
- Periodic cleanup scheduling
- File age tracking
- Session management

**Key Features:**
- Background cleanup every 1 hour
- Default TTL: 24 hours
- Track file creation timestamps
- Manual cleanup trigger

---

## Data Flow

```
┌─────────────────┐
│   Use Cases     │
│   (Application) │
└────────┬────────┘
         │
         ↓
┌─────────────────┐      ┌──────────────────┐
│ LocalStorage    │◄─────┤ FileCleanup      │
│ Service         │      │ Manager          │
└────────┬────────┘      └─────────┬────────┘
         │                         │
         ↓                         ↓
┌─────────────────────────────────────┐
│   File System (/temp)               │
│   - Audio files (.wav)              │
│   - Video files (.mp4)              │
│   - Temporary transcription data    │
└─────────────────────────────────────┘
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMP_DIR` | `./temp` | Base temporary directory |
| `MAX_TEMP_AGE_HOURS` | `24` | File TTL before cleanup |
| `CLEANUP_AFTER_PROCESSING` | `true` | Auto-delete after transcription |

---

## Usage Examples

### Example 1: Save Audio File

```python
from src.infrastructure.storage import LocalStorageService

storage = LocalStorageService(base_temp_dir="./temp")

# Save audio file
file_path = await storage.save_file(
    content=audio_data,
    filename="video_audio.wav",
    subdir="audio"
)
# Returns: Path("./temp/audio/video_audio.wav")
```

### Example 2: Automatic Cleanup

```python
from src.infrastructure.storage import FileCleanupManager

cleanup_manager = FileCleanupManager(
    storage_service=storage,
    max_age_hours=24
)

# Start periodic cleanup (every 1 hour)
cleanup_manager.start_periodic_cleanup()

# Track file for cleanup
cleanup_manager.track_file(file_path)

# Manual cleanup
await cleanup_manager.cleanup_old_files()
```

---

## Best Practices

### ✅ DO
- Use `save_file()` for atomic writes
- Track files with `FileCleanupManager`
- Set appropriate TTL for your use case
- Monitor storage usage regularly
- Enable periodic cleanup in production

### ❌ DON'T
- Don't bypass storage service for direct file writes
- Don't keep files indefinitely
- Don't disable cleanup in production
- Don't forget to handle storage full errors
- Don't use blocking I/O operations

---

## Monitoring

### Storage Metrics

```python
# Get storage statistics
stats = await storage.get_storage_usage()

# Example output:
# {
#     "total_files": 145,
#     "total_size_mb": 2340.5,
#     "temp_files": 23,
#     "cache_files": 12
# }
```

---

## Related Documentation

- **Config Settings**: `../config/README.md` - Storage configuration
- **Use Cases**: `../../application/` - Storage service usage
- **Monitoring**: `../monitoring/metrics.md` - Storage metrics

---

## Version

**Current Version:** v2.2 (2024)

**Changes:**
- v2.2: Enhanced cleanup manager with session tracking
- v2.1: Added periodic cleanup background task
- v2.0: Atomic writes implementation
- v1.0: Initial local storage service
