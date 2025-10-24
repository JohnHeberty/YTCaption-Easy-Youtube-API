# IVideoDownloader Interface

Interface (ABC) that defines the contract for video downloaders.

---

## Overview

`IVideoDownloader` is an **Interface** (Abstract Base Class) that:
- Defines the contract for YouTube video downloads
- Follows **Dependency Inversion Principle** (SOLID)
- Allows multiple implementations (yt-dlp, youtube-dl, etc.)

**File**: `src/domain/interfaces/video_downloader.py`

---

## Methods

### `download(url, output_path) -> VideoFile`
Downloads a YouTube video.

**Parameters**:
- `url: YouTubeURL` - Validated video URL
- `output_path: Path` - Path where to save the file

**Returns**: `VideoFile` - Entity representing the downloaded file

**Exceptions**: `VideoDownloadError` - Download error

```python
downloader: IVideoDownloader = YouTubeDownloader()
url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
video = await downloader.download(url, Path("temp/video.mp4"))
print(f"Downloaded: {video.file_size_mb:.2f} MB")
```

### `get_video_info(url) -> dict`
Gets video information without downloading it.

**Parameters**:
- `url: YouTubeURL` - Video URL

**Returns**: `dict` - Video information (title, duration, format, etc.)

**Exceptions**: `VideoDownloadError` - Error getting information

```python
info = await downloader.get_video_info(url)
print(f"Title: {info['title']}")
print(f"Duration: {info['duration']}s")
```

---

## Implementations

### `YouTubeDownloader` (Infrastructure)
Implementation using **yt-dlp** (v3.0 with Resilience System).

**Location**: `src/infrastructure/youtube/downloader.py`

**Features**:
- 7 download strategies (Standard → Tor)
- Adaptive rate limiting
- User-agent rotation
- Proxy support
- Circuit breaker pattern

---

## Usage Example

```python
from src.domain.interfaces import IVideoDownloader
from src.domain.value_objects import YouTubeURL
from src.infrastructure.youtube import YouTubeDownloader

# Use interface (not direct implementation)
async def download_video(downloader: IVideoDownloader, url_str: str):
    url = YouTubeURL.create(url_str)
    
    # Get information
    info = await downloader.get_video_info(url)
    print(f"Downloading: {info['title']}")
    
    # Download
    video = await downloader.download(url, Path("temp/video.mp4"))
    print(f"Success: {video.file_size_mb:.2f} MB")
    
    return video

# Inject implementation
downloader = YouTubeDownloader()
video = await download_video(downloader, "https://youtu.be/dQw4w9WgXcQ")
```

---

## Dependency Inversion

```python
# ❌ WRONG: Depend on concrete implementation
from src.infrastructure.youtube import YouTubeDownloader

class TranscribeVideoUseCase:
    def __init__(self):
        self.downloader = YouTubeDownloader()  # Tight coupling

# ✅ CORRECT: Depend on abstraction
from src.domain.interfaces import IVideoDownloader

class TranscribeVideoUseCase:
    def __init__(self, downloader: IVideoDownloader):
        self.downloader = downloader  # Flexible
```

**Benefits**:
- Testability (mock the interface)
- Flexibility (swap implementation)
- Decoupling (domain doesn't know infrastructure)

---

## Tests

```python
from unittest.mock import AsyncMock

class MockVideoDownloader(IVideoDownloader):
    async def download(self, url, output_path):
        return VideoFile(file_path=output_path, file_size_bytes=1024)
    
    async def get_video_info(self, url):
        return {"title": "Test Video", "duration": 120}

# Use mock in tests
async def test_transcribe_use_case():
    mock_downloader = MockVideoDownloader()
    use_case = TranscribeVideoUseCase(downloader=mock_downloader)
    
    result = await use_case.execute("https://youtu.be/123")
    assert result.success
```

---

[⬅️ Back](../README.md)

**Version**: 3.0.0