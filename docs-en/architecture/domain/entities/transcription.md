# Transcription Entity

Main entity representing a complete video transcription.

---

## Overview

`Transcription` is a **Entity** from Domain-Driven Design (DDD), representing a complete transcription with:
- Unique identity (UUID)
- Mutable state (can add segments)
- Lifecycle (creation → processing → finalization)
- Encapsulated business rules

**File**: `src/domain/entities/transcription.py`

---

## Structure

```python
@dataclass
class Transcription:
    id: str                                    # Unique UUID
    youtube_url: Optional[YouTubeURL]          # Video URL
    segments: List[TranscriptionSegment]       # Segments with timestamp
    language: Optional[str]                    # Language ("en", "pt", etc.)
    created_at: datetime                       # Creation date
    processing_time: Optional[float]           # Processing time (seconds)
```

---

## Properties

### `duration` (readonly)
Returns total transcription duration in seconds.

```python
transcription.duration  # 125.5 (in seconds)
```

**Implementation**:
```python
@property
def duration(self) -> float:
    if not self.segments:
        return 0.0
    return max(segment.end for segment in self.segments)
```

### `is_complete` (readonly)
Checks if transcription is complete (has segments and language).

```python
transcription.is_complete  # True or False
```

**Implementation**:
```python
@property
def is_complete(self) -> bool:
    return len(self.segments) > 0 and self.language is not None
```

---

## Methods

### `add_segment(segment: TranscriptionSegment) -> None`
Adds a transcription segment.

```python
segment = TranscriptionSegment(
    text="Hello, world!",
    start=0.0,
    end=2.5
)
transcription.add_segment(segment)
```

---

### `get_full_text() -> str`
Returns full text by concatenating all segments.

```python
text = transcription.get_full_text()
# "Hello, world! This is a test. Goodbye!"
```

**Implementation**:
```python
def get_full_text(self) -> str:
    return " ".join(segment.text for segment in self.segments)
```

---

### `to_srt() -> str`
Converts transcription to SRT format (subtitles).

**Example output**:
```srt
1
00:00:00,000 --> 00:00:02,500
Hello, world!

2
00:00:02,500 --> 00:00:05,000
This is a test.
```

**Usage**:
```python
srt_content = transcription.to_srt()
with open("subtitles.srt", "w") as f:
    f.write(srt_content)
```

---

### `to_vtt() -> str`
Converts transcription to WebVTT format (web subtitles).

**Example output**:
```vtt
WEBVTT

00:00:00.000 --> 00:00:02.500
Hello, world!

00:00:02.500 --> 00:00:05.000
This is a test.
```

**Usage**:
```python
vtt_content = transcription.to_vtt()
with open("subtitles.vtt", "w") as f:
    f.write(vtt_content)
```

---

### `to_dict() -> dict`
Converts transcription to dictionary (serialization).

**Output**:
```python
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "video_id": "dQw4w9WgXcQ",
    "language": "en",
    "full_text": "Hello, world! This is a test.",
    "segments": [
        {
            "text": "Hello, world!",
            "start": 0.0,
            "end": 2.5,
            "duration": 2.5
        },
        {
            "text": "This is a test.",
            "start": 2.5,
            "end": 5.0,
            "duration": 2.5
        }
    ],
    "created_at": "2025-10-22T10:30:00",
    "processing_time": 12.5,
    "total_segments": 2
}
```

**Usage**:
```python
data = transcription.to_dict()
import json
json_str = json.dumps(data, indent=2)
```

---

## Creation

### Method 1: Default constructor
```python
from src.domain.entities import Transcription
from src.domain.value_objects import YouTubeURL

url = YouTubeURL.create("https://youtube.com/watch?v=dQw4w9WgXcQ")

transcription = Transcription(
    youtube_url=url,
    language="en"
)
# ID automatically generated (UUID4)
# created_at automatically set (now)
# segments initialized as empty list
```

### Method 2: With specific ID (reconstruction)
```python
transcription = Transcription(
    id="550e8400-e29b-41d4-a716-446655440000",
    youtube_url=url,
    language="en"
)
```

---

## Complete Example

```python
from src.domain.entities import Transcription
from src.domain.value_objects import TranscriptionSegment, YouTubeURL

# 1. Create transcription
url = YouTubeURL.create("https://youtube.com/watch?v=dQw4w9WgXcQ")
transcription = Transcription(
    youtube_url=url,
    language="en"
)

# 2. Add segments
segments_data = [
    {"text": "Never gonna give you up", "start": 0.0, "end": 2.5},
    {"text": "Never gonna let you down", "start": 2.5, "end": 5.0},
    {"text": "Never gonna run around", "start": 5.0, "end": 7.5},
]

for seg_data in segments_data:
    segment = TranscriptionSegment(**seg_data)
    transcription.add_segment(segment)

# 3. Check state
print(f"Complete: {transcription.is_complete}")      # True
print(f"Duration: {transcription.duration}s")        # 7.5
print(f"Segments: {len(transcription.segments)}")    # 3

# 4. Get full text
full_text = transcription.get_full_text()
print(full_text)
# "Never gonna give you up Never gonna let you down Never gonna run around"

# 5. Export to SRT
srt_content = transcription.to_srt()
with open("rickroll.srt", "w", encoding="utf-8") as f:
    f.write(srt_content)

# 6. Serialize to JSON
import json
data = transcription.to_dict()
with open("transcription.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
```

---

## Business Rules

1. **Unique ID**: Always generated as UUID4 if not specified
2. **Ordered Segments**: Segments must be added in chronological order
3. **Completeness**: Complete transcription = has segments + has language
4. **Duration**: Calculated from last segment (`max(segment.end)`)
5. **Language**: ISO 639-1 code (2 letters: "en", "pt", "es", etc.)

---

## Tests

```python
# tests/unit/domain/entities/test_transcription.py
import pytest
from src.domain.entities import Transcription
from src.domain.value_objects import TranscriptionSegment, YouTubeURL

def test_create_transcription():
    url = YouTubeURL.create("https://youtube.com/watch?v=123")
    transcription = Transcription(youtube_url=url, language="en")
    
    assert transcription.id  # UUID generated
    assert transcription.youtube_url == url
    assert transcription.language == "en"
    assert len(transcription.segments) == 0

def test_add_segment():
    transcription = Transcription(language="en")
    segment = TranscriptionSegment(text="Hello", start=0.0, end=2.0)
    
    transcription.add_segment(segment)
    
    assert len(transcription.segments) == 1
    assert transcription.segments[0] == segment

def test_get_full_text():
    transcription = Transcription(language="en")
    transcription.add_segment(TranscriptionSegment(text="Hello", start=0.0, end=1.0))
    transcription.add_segment(TranscriptionSegment(text="World", start=1.0, end=2.0))
    
    assert transcription.get_full_text() == "Hello World"

def test_duration():
    transcription = Transcription(language="en")
    transcription.add_segment(TranscriptionSegment(text="A", start=0.0, end=2.5))
    transcription.add_segment(TranscriptionSegment(text="B", start=2.5, end=7.5))
    
    assert transcription.duration == 7.5

def test_is_complete():
    transcription = Transcription()
    assert not transcription.is_complete  # No segments, no language
    
    transcription.language = "en"
    assert not transcription.is_complete  # Has language, but no segments
    
    transcription.add_segment(TranscriptionSegment(text="A", start=0.0, end=1.0))
    assert transcription.is_complete  # Has both!

def test_to_srt():
    transcription = Transcription(language="en")
    transcription.add_segment(TranscriptionSegment(text="Hello", start=0.0, end=2.5))
    
    srt = transcription.to_srt()
    
    assert "1\n" in srt
    assert "00:00:00,000 --> 00:00:02,500" in srt
    assert "Hello" in srt

def test_to_vtt():
    transcription = Transcription(language="en")
    transcription.add_segment(TranscriptionSegment(text="Hello", start=0.0, end=2.5))
    
    vtt = transcription.to_vtt()
    
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:02.500" in vtt
    assert "Hello" in vtt

def test_to_dict():
    url = YouTubeURL.create("https://youtube.com/watch?v=123")
    transcription = Transcription(youtube_url=url, language="en")
    transcription.add_segment(TranscriptionSegment(text="Hi", start=0.0, end=1.0))
    
    data = transcription.to_dict()
    
    assert data["id"]
    assert data["youtube_url"] == str(url)
    assert data["video_id"] == "123"
    assert data["language"] == "en"
    assert data["full_text"] == "Hi"
    assert len(data["segments"]) == 1
    assert data["total_segments"] == 1
```

---

## Next Steps

- [VideoFile Entity](./video-file.md) - Video file entity
- [TranscriptionSegment Value Object](../value-objects/transcription-segment.md) - Transcription segment
- [YouTubeURL Value Object](../value-objects/youtube-url.md) - Validated URL

---

[⬅️ Back](../README.md)

**Version**: 3.0.0  
**Last Updated**: October 22, 2025