# VideoFile Entity

Entity representing a downloaded video file.

---

## Overview

`VideoFile` is an **Entity** that encapsulates video file information:
- Unique identity (UUID)
- File path
- Metadata (size, format, original URL)
- Operations (check existence, delete)

**File**: `src/domain/entities/video_file.py`

---

## Structure

```python
@dataclass
class VideoFile:
    id: str                      # Unique UUID
    file_path: Path              # File path
    original_url: Optional[str]  # Original video URL
    file_size_bytes: int         # Size in bytes
    format: Optional[str]        # Format (mp4, webm, etc.)
    created_at: datetime         # Creation date
```

---

## Properties

### `exists` (readonly)
Checks if file exists on disk.

```python
video = VideoFile(file_path=Path("video.mp4"))
if video.exists:
    print("File found!")
```

### `file_size_mb` (readonly)
Returns file size in megabytes.

```python
print(f"Size: {video.file_size_mb:.2f} MB")  # "Size: 45.67 MB"
```

### `extension` (readonly)
Returns file extension.

```python
print(video.extension)  # ".mp4"
```

---

## Methods

### `delete() -> bool`
Removes file from disk.

**Returns**: `True` if deleted successfully, `False` otherwise.

```python
if video.delete():
    print("File removed!")
else:
    print("Failed to remove")
```

### `to_dict() -> dict`
Serializes to dictionary.

```python
data = video.to_dict()
# {
#     "id": "550e8400-e29b-41d4-a716-446655440000",
#     "file_path": "/temp/video.mp4",
#     "original_url": "https://youtube.com/watch?v=123",
#     "file_size_mb": 45.67,
#     "format": "mp4",
#     "exists": true,
#     "created_at": "2025-10-22T10:30:00"
# }
```

---

## Complete Example

```python
from pathlib import Path
from src.domain.entities import VideoFile

# Create VideoFile
video = VideoFile(
    file_path=Path("temp/video_123.mp4"),
    original_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
    file_size_bytes=47841280,  # ~45.6 MB
    format="mp4"
)

# Check information
print(f"ID: {video.id}")
print(f"Exists: {video.exists}")
print(f"Size: {video.file_size_mb:.2f} MB")
print(f"Extension: {video.extension}")

# Process video...
# (transcription, etc.)

# Clean up after use
if video.delete():
    print("Temporary file removed")
```

---

## Business Rules

1. **Unique ID**: UUID4 automatically generated
2. **Path Conversion**: Strings are automatically converted to `Path`
3. **Safe Delete**: `delete()` doesn't raise exception if file doesn't exist
4. **Size Calculation**: MB size calculated from bytes

---

## Tests

```python
def test_video_file_creation(tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_text("fake video")
    
    video = VideoFile(
        file_path=file_path,
        original_url="https://youtube.com/watch?v=123",
        file_size_bytes=1024,
        format="mp4"
    )
    
    assert video.id
    assert video.exists is True
    assert video.file_size_mb == 1024 / (1024 * 1024)
    assert video.extension == ".mp4"

def test_delete_video_file(tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_text("fake video")
    
    video = VideoFile(file_path=file_path)
    
    assert video.exists is True
    assert video.delete() is True
    assert video.exists is False
```

---

[⬅️ Back](../README.md)

**Version**: 3.0.0