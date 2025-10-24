# IStorageService Interface

Interface (ABC) that defines the contract for storage management.

---

## Overview

`IStorageService` is an **Interface** that:
- Defines the contract for temporary file management
- Follows the **Dependency Inversion Principle** (SOLID)
- Allows multiple implementations (local, cloud, etc.)

**File**: `src/domain/interfaces/storage_service.py`

---

## Methods

### `create_temp_directory() -> Path`
Creates a temporary directory.

**Returns**: `Path` - Path of the created directory

```python
storage: IStorageService = LocalStorageService()
temp_dir = await storage.create_temp_directory()
print(f"Directory: {temp_dir}")  # "temp/session_abc123"
```

### `cleanup_old_files(max_age_hours=24) -> int`
Removes old files from temporary storage.

**Parameters**:
- `max_age_hours: int` - Maximum age of files in hours (default: 24h)

**Returns**: `int` - Number of files removed

```python
removed = await storage.cleanup_old_files(max_age_hours=12)
print(f"Removed: {removed} files")
```

### `cleanup_directory(directory) -> bool`
Removes a directory and all its contents.

**Parameters**:
- `directory: Path` - Directory to be removed

**Returns**: `bool` - `True` if successfully removed

```python
success = await storage.cleanup_directory(temp_dir)
if success:
    print("Directory cleaned!")
```

### `get_temp_files() -> List[Path]`
Lists all temporary files.

**Returns**: `List[Path]` - List of file paths

```python
files = await storage.get_temp_files()
for file in files:
    print(f"- {file} ({file.stat().st_size} bytes)")
```

### `get_storage_usage() -> dict`
Gets storage usage information.

**Returns**: `dict` - Usage information (total, used, free)

```python
usage = await storage.get_storage_usage()
print(f"Total: {usage['total_gb']:.2f} GB")
print(f"Used: {usage['used_gb']:.2f} GB")
print(f"Free: {usage['free_gb']:.2f} GB")
```

---

## Implementations

### `LocalStorageService` (Infrastructure)
Implementation for local storage.

**Location**: `src/infrastructure/storage/local_storage.py`

**Features**:
- Manages `temp/` directory at project root
- Automatic cleanup of old files
- Thread-safe (async locks)
- Robust error handling

---

## Usage Example

```python
from src.domain.interfaces import IStorageService
from src.infrastructure.storage import LocalStorageService

async def process_video(storage: IStorageService, video_url: str):
    # Create temporary directory
    temp_dir = await storage.create_temp_directory()
    
    try:
        # Download video
        video_path = temp_dir / "video.mp4"
        await downloader.download(video_url, video_path)
        
        # Process...
        transcription = await transcribe(video_path)
        
        return transcription
    
    finally:
        # Clean directory
        await storage.cleanup_directory(temp_dir)

# Inject implementation
storage = LocalStorageService(base_dir=Path("temp"))
result = await process_video(storage, "https://youtu.be/123")
```

---

## Dependency Inversion

```python
# ❌ WRONG: Depend on concrete implementation
from src.infrastructure.storage import LocalStorageService

class TranscribeUseCase:
    def __init__(self):
        self.storage = LocalStorageService()  # Coupling

# ✅ CORRECT: Depend on abstraction
from src.domain.interfaces import IStorageService

class TranscribeUseCase:
    def __init__(self, storage: IStorageService):
        self.storage = storage  # Flexible
```

**Benefits**:
- Test with mock (no I/O)
- Switch implementation (local → S3)
- Domain decoupled from infrastructure

---

## Tests

```python
class MockStorageService(IStorageService):
    async def create_temp_directory(self):
        return Path("/tmp/test")
    
    async def cleanup_old_files(self, max_age_hours=24):
        return 0
    
    async def cleanup_directory(self, directory):
        return True
    
    async def get_temp_files(self):
        return []
    
    async def get_storage_usage(self):
        return {"total_gb": 100, "used_gb": 50, "free_gb": 50}

# Use mock in tests
async def test_transcribe_use_case():
    mock_storage = MockStorageService()
    use_case = TranscribeUseCase(storage=mock_storage)
    
    result = await use_case.execute("https://youtu.be/123")
    assert result.success
```

---

[⬅️ Back](../README.md)

**Version**: 3.0.0