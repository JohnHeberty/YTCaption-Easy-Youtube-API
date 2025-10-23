# TranscriptionSegment Value Object

Value Object representing a transcription segment.

---

## Overview

`TranscriptionSegment` is an immutable **Value Object** representing:
- Transcribed text
- Start timestamp (seconds)
- End timestamp (seconds)
- SRT/VTT formatting

**File**: `src/domain/value_objects/transcription_segment.py`

---

## Structure

```python
@dataclass(frozen=True)  # Immutable
class TranscriptionSegment:
    text: str    # Transcribed text
    start: float # Start timestamp (seconds)
    end: float   # End timestamp (seconds)
```

---

## Properties

### `duration` (readonly)
Returns segment duration in seconds.

```python
segment = TranscriptionSegment(
    text="Hello world",
    start=1.5,
    end=3.8
)
print(segment.duration)  # 2.3
```

---

## Validation

The `__post_init__` validates:

```python
# ✅ Valid
segment = TranscriptionSegment("Hello", start=0, end=2.5)

# ❌ Invalid: negative start
TranscriptionSegment("Hello", start=-1, end=2)  # ValueError

# ❌ Invalid: end < start
TranscriptionSegment("Hello", start=5, end=3)  # ValueError

# ❌ Invalid: empty text
TranscriptionSegment("", start=0, end=2)  # ValueError
```

---

## Formatting Methods

### `to_srt_format(index: int) -> str`
Formats to SubRip (SRT) - uses **comma** as decimal separator.

```python
segment = TranscriptionSegment("Hello world", start=1.5, end=3.8)
print(segment.to_srt_format(1))

# Output:
# 1
# 00:00:01,500 --> 00:00:03,800
# Hello world
```

### `to_vtt_format() -> str`
Formats to WebVTT - uses **dot** as decimal separator.

```python
segment = TranscriptionSegment("Hello world", start=1.5, end=3.8)
print(segment.to_vtt_format())

# Output:
# 00:00:01.500 --> 00:00:03.800
# Hello world
```

---

## Timestamp Format

Both methods use `HH:MM:SS,mmm` (SRT) or `HH:MM:SS.mmm` (VTT):

```python
# Examples:
0.0    → 00:00:00,000
1.5    → 00:00:01,500
65.250 → 00:01:05,250
3661.5 → 01:01:01,500
```

---

## Complete Example

```python
from src.domain.value_objects import TranscriptionSegment

# Create segments
segments = [
    TranscriptionSegment("Never gonna give you up", start=0.0, end=2.5),
    TranscriptionSegment("Never gonna let you down", start=2.5, end=5.0),
    TranscriptionSegment("Never gonna run around", start=5.0, end=7.8),
]

# Export to SRT
srt_content = "\n\n".join(
    seg.to_srt_format(i+1) for i, seg in enumerate(segments)
)
print(srt_content)

# Export to VTT
vtt_content = "WEBVTT\n\n" + "\n\n".join(
    seg.to_vtt_format() for seg in segments
)
print(vtt_content)

# Calculate total duration
total_duration = sum(seg.duration for seg in segments)
print(f"Duration: {total_duration:.2f}s")  # 7.80s
```

---

## Business Rules

1. **Immutability**: `frozen=True` prevents modifications
2. **Positive Timestamps**: `start >= 0`
3. **Temporal Order**: `end >= start`
4. **Required Text**: Cannot be empty
5. **Decimal Format**: 3 decimal places (milliseconds)

---

## Tests

```python
def test_segment_creation():
    segment = TranscriptionSegment("Hello", start=1.0, end=3.0)
    assert segment.text == "Hello"
    assert segment.duration == 2.0

def test_segment_validation_negative_start():
    with pytest.raises(ValueError):
        TranscriptionSegment("Hello", start=-1, end=2)

def test_segment_validation_end_before_start():
    with pytest.raises(ValueError):
        TranscriptionSegment("Hello", start=5, end=3)

def test_segment_validation_empty_text():
    with pytest.raises(ValueError):
        TranscriptionSegment("", start=0, end=2)

def test_segment_srt_format():
    segment = TranscriptionSegment("Hello", start=1.5, end=3.8)
    srt = segment.to_srt_format(1)
    assert "1\n" in srt
    assert "00:00:01,500 --> 00:00:03,800" in srt
    assert "Hello" in srt

def test_segment_vtt_format():
    segment = TranscriptionSegment("Hello", start=1.5, end=3.8)
    vtt = segment.to_vtt_format()
    assert "00:00:01.500 --> 00:00:03.800" in vtt
    assert "Hello" in vtt

def test_segment_immutable():
    segment = TranscriptionSegment("Hello", start=0, end=2)
    with pytest.raises(FrozenInstanceError):
        segment.text = "Goodbye"
```

---

[⬅️ Back](../README.md)

**Version**: 3.0.0