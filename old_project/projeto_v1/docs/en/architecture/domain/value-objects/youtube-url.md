# YouTubeURL Value Object

Value Object representing validated YouTube URLs.

---

## Overview

`YouTubeURL` is an immutable **Value Object** that encapsulates:
- Validated YouTube URL
- Extracted video ID
- Automatic validation via regex

**File**: `src/domain/value_objects/youtube_url.py`

---

## Structure

```python
@dataclass(frozen=True)  # Immutable
class YouTubeURL:
    url: str       # Full URL
    video_id: str  # Video ID (e.g., "dQw4w9WgXcQ")
```

---

## Creation

### `create(url: str) -> YouTubeURL`
Factory method to create validated instances.

```python
from src.domain.value_objects import YouTubeURL

# Valid URLs
url1 = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
url2 = YouTubeURL.create("https://youtu.be/dQw4w9WgXcQ")
url3 = YouTubeURL.create("https://m.youtube.com/watch?v=dQw4w9WgXcQ")

print(url1.video_id)  # "dQw4w9WgXcQ"

# Invalid URL raises exception
try:
    invalid = YouTubeURL.create("https://vimeo.com/123456")
except ValueError as e:
    print(e)  # "Invalid YouTube URL"
```

---

## Supported Formats

| Format | Example |
|--------|---------|
| Standard | `https://www.youtube.com/watch?v=VIDEO_ID` |
| Short | `https://youtu.be/VIDEO_ID` |
| Mobile | `https://m.youtube.com/watch?v=VIDEO_ID` |
| Embed | `https://www.youtube.com/embed/VIDEO_ID` |

---

## Validation

Regex used:
```python
_YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.|m\.)?'
    r'(youtube\.com|youtu\.be)/'
    r'(watch\?v=|embed/)?([a-zA-Z0-9_-]{11})'
)
```

**Rules**:
- Protocol: http or https (optional)
- Domain: youtube.com, youtu.be, m.youtube.com
- Video ID: 11 alphanumeric characters + `-_`

---

## Complete Example

```python
from src.domain.value_objects import YouTubeURL

# Create validated URL
url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# Access properties (readonly)
print(f"URL: {url.url}")
print(f"Video ID: {url.video_id}")

# Pass to services
downloader.download(url)
transcriber.transcribe(url)

# Comparison (value equality)
url1 = YouTubeURL.create("https://youtu.be/dQw4w9WgXcQ")
url2 = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(url1.video_id == url2.video_id)  # True (same video)
```

---

## Business Rules

1. **Immutability**: `frozen=True` prevents modifications
2. **Validation**: Raises `ValueError` for invalid URLs
3. **Video ID**: Always 11 characters
4. **Factory Pattern**: Use `create()`, not direct constructor

---

## Tests

```python
def test_youtube_url_valid():
    url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert url.video_id == "dQw4w9WgXcQ"

def test_youtube_url_short_format():
    url = YouTubeURL.create("https://youtu.be/dQw4w9WgXcQ")
    assert url.video_id == "dQw4w9WgXcQ"

def test_youtube_url_invalid():
    with pytest.raises(ValueError):
        YouTubeURL.create("https://vimeo.com/123456")

def test_youtube_url_immutable():
    url = YouTubeURL.create("https://youtu.be/123")
    with pytest.raises(FrozenInstanceError):
        url.video_id = "456"
```

---

[⬅️ Back](../README.md)

**Version**: 3.0.0