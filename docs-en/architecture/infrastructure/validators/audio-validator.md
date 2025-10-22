# Audio Validator

## Overview

The **AudioValidator** provides comprehensive pre-processing validation for audio/video files before transcription. It uses FFprobe to efficiently extract metadata and validates format, codec, duration, sample rate, and file integrity without loading the entire file into memory.

**Key Features:**
- 🔍 **Fast Validation** - FFprobe metadata extraction (no decoding)
- ✅ **Format/Codec Checking** - Validates supported formats
- 📏 **Size/Duration Limits** - Prevents oversized files
- 🛡️ **Corruption Detection** - Tests file integrity
- ⏱️ **Processing Time Estimation** - Predicts transcription duration
- 📊 **Detailed Metadata** - Returns comprehensive file information

**Validation Speed:** ~0.3-1.0 seconds per file (metadata only, no decoding)

**Version:** v2.2 (2024)

---

## Architecture Position

```
┌─────────────────────────────────────────────┐
│         Presentation Layer                  │
│  ┌─────────────────────────────────────┐   │
│  │   POST /api/v1/transcribe            │   │
│  │   - Receives file upload             │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│       Application Layer                     │
│  ┌─────────────────────────────────────┐   │
│  │   TranscribeVideoUseCase            │   │
│  │   - Orchestrates workflow            │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│       Infrastructure Layer                  │
│  ┌─────────────────────────────────────┐   │
│  │   AudioValidator (THIS MODULE)      │◄──┼─── VALIDATES BEFORE PROCESSING
│  │   - Format/codec validation          │   │
│  │   - Size/duration limits             │   │
│  │   - Corruption detection             │   │
│  └─────────────────────────────────────┘   │
│           ↓ (if valid)                      │
│  ┌─────────────────────────────────────┐   │
│  │   WhisperTranscriptionService       │   │
│  │   - Processes validated files        │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

**Dependencies:**
- `subprocess` - FFprobe/FFmpeg execution
- `json` - Metadata parsing
- `pathlib.Path` - File handling
- **External**: FFprobe, FFmpeg binaries

---

## Data Structures

### AudioMetadata

```python
@dataclass
class AudioMetadata:
    """Validation result with comprehensive file metadata."""
    
    duration_seconds: float         # Total duration
    format_name: str                # Container format (mp4, webm, etc)
    codec_name: str                 # Audio codec (aac, opus, etc)
    sample_rate: int                # Sample rate in Hz
    channels: int                   # Number of audio channels
    bit_rate: Optional[int]         # Bitrate in bps (if available)
    file_size_bytes: int            # File size in bytes
    is_valid: bool                  # Validation passed
    validation_errors: List[str]    # List of validation errors
    
    @property
    def file_size_mb(self) -> float:
        """File size in MB."""
        return self.file_size_bytes / (1024 * 1024)
    
    @property
    def duration_formatted(self) -> str:
        """Duration as HH:MM:SS."""
        # Returns "01:23:45" format
```

**Example:**
```python
AudioMetadata(
    duration_seconds=3645.23,
    format_name='mov,mp4,m4a,3gp,3g2,mj2',
    codec_name='aac',
    sample_rate=48000,
    channels=2,
    bit_rate=128000,
    file_size_bytes=458752000,
    is_valid=True,
    validation_errors=[]
)
```

---

## Validation Constraints

### Supported Formats

**Audio Codecs:**
```python
SUPPORTED_AUDIO_CODECS = {
    'aac', 'mp3', 'opus', 'vorbis', 'flac', 
    'pcm_s16le', 'pcm_s24le', 'pcm_f32le', 
    'wav', 'alac', 'wmav2'
}
```

**Container Formats:**
```python
SUPPORTED_FORMATS = {
    # Video containers
    'mp4', 'webm', 'mkv', 'avi', 'mov', 'flv', 'wmv',
    # Audio containers
    'mp3', 'aac', 'ogg', 'opus', 'flac', 'wav', 'm4a'
}
```

### Size/Duration Limits

| Constraint | Value | Reason |
|------------|-------|--------|
| **MAX_DURATION_HOURS** | 10 hours | Prevents extremely long processing |
| **MIN_DURATION_SECONDS** | 0.5 seconds | Requires meaningful audio |
| **MAX_FILE_SIZE_GB** | 5 GB | Memory/storage limits |
| **MIN_SAMPLE_RATE** | 8000 Hz | Quality threshold |
| **MAX_SAMPLE_RATE** | 48000 Hz | Whisper processes at 16kHz anyway |

**Adjusting Limits:**
```python
validator = AudioValidator()
validator.MAX_DURATION_HOURS = 20  # Allow longer files
validator.MAX_FILE_SIZE_GB = 10    # Allow larger files
```

---

## Core Methods

### 1. File Validation

#### `validate_file(file_path: Path, strict: bool = False) -> AudioMetadata`

Comprehensive file validation with metadata extraction.

**Parameters:**
- `file_path: Path` - File to validate
- `strict: bool = False` - Apply stricter validation rules

**Validation Steps:**
1. Check file exists
2. Validate file extension (if `strict=True`)
3. Check file size (not empty, not too large)
4. Extract metadata with FFprobe
5. Validate duration (min/max)
6. Validate codec (if `strict=True`)
7. Validate sample rate
8. Validate channels exist

**Returns:** `AudioMetadata` with `is_valid` and `validation_errors`

**Usage Example:**
```python
from pathlib import Path
from src.infrastructure.validators.audio_validator import AudioValidator

validator = AudioValidator()

# Validate uploaded video
metadata = validator.validate_file(
    file_path=Path("uploads/video.mp4"),
    strict=True
)

if metadata.is_valid:
    logger.info(
        f"Valid file: {metadata.duration_formatted}, "
        f"{metadata.file_size_mb:.2f}MB, {metadata.codec_name}"
    )
    # Proceed with transcription
else:
    logger.error(f"Invalid file: {metadata.validation_errors}")
    raise ValidationError(metadata.validation_errors)
```

**Strict vs. Non-Strict Mode:**

| Validation | Non-Strict | Strict |
|------------|-----------|--------|
| File extension | Warning only | Error if unsupported |
| Audio codec | Warning only | Error if unsupported |
| Duration limits | Enforced | Enforced |
| File size limits | Enforced | Enforced |
| Sample rate | Warning if high | Warning if high |

---

### 2. Metadata Extraction

#### `_extract_metadata_ffprobe(file_path: Path) -> Dict`

Internal method: Extracts audio metadata using FFprobe.

**FFprobe Command:**
```bash
ffprobe \
  -v error \
  -print_format json \
  -show_format \
  -show_streams \
  -select_streams a:0 \
  input.mp4
```

**Returns:**
```python
{
    'duration': 3645.23,
    'format': 'mov,mp4,m4a,3gp,3g2,mj2',
    'codec': 'aac',
    'sample_rate': 48000,
    'channels': 2,
    'bit_rate': 128000
}
```

**Error Handling:**
- FFprobe command failure → Exception with stderr
- Timeout (>30s) → Exception
- JSON parse error → Exception
- No audio stream → Retry without stream filter

---

### 3. Processing Time Estimation

#### `estimate_processing_time(metadata: AudioMetadata, model_name: str = "base", device: str = "cpu") -> Tuple[float, float]`

Estimates transcription time based on benchmarks.

**Processing Factors** (audio seconds per processing second):

| Model | CPU | CUDA |
|-------|-----|------|
| **tiny** | 2.0x | 10.0x |
| **base** | 1.5x | 8.0x |
| **small** | 0.8x | 5.0x |
| **medium** | 0.4x | 3.0x |
| **large** | 0.2x | 2.0x |
| **turbo** | 1.0x | 6.0x |

**Formula:**
```python
estimated_time = duration / factor
min_time = estimated_time * 1.15 * 0.8  # +15% overhead, -20% margin
max_time = estimated_time * 1.15 * 1.5  # +15% overhead, +50% margin
```

**Usage Example:**
```python
metadata = validator.validate_file(Path("video.mp4"))

# Estimate processing time
min_time, max_time = validator.estimate_processing_time(
    metadata=metadata,
    model_name="base",
    device="cuda"
)

logger.info(
    f"Estimated processing time: {min_time:.0f}s - {max_time:.0f}s "
    f"for {metadata.duration_formatted} video"
)

# 1-hour video with base/CUDA:
# Output: "Estimated processing time: 331s - 622s for 01:00:00 video"
# (5.5 - 10.4 minutes)
```

**Real-World Examples:**

| Video Duration | Model | Device | Estimated Time |
|----------------|-------|--------|----------------|
| 10 minutes | base | CPU | 4.6 - 8.6 min |
| 10 minutes | base | CUDA | 0.86 - 1.6 min |
| 1 hour | small | CPU | 5.5 - 10.4 min |
| 1 hour | small | CUDA | 8.3 - 15.5 min |
| 2 hours | large | CPU | 48 - 90 min |
| 2 hours | large | CUDA | 8 - 15 min |

---

### 4. Corruption Detection

#### `check_corruption(file_path: Path) -> Tuple[bool, Optional[str]]`

Tests file integrity by attempting to decode first 5 seconds.

**FFmpeg Test Command:**
```bash
ffmpeg \
  -v error \
  -i input.mp4 \
  -t 5 \          # Test first 5 seconds only
  -f null \       # Discard output
  -
```

**Returns:**
- `(False, None)` - File is valid
- `(True, "error message")` - File is corrupted

**Usage Example:**
```python
is_corrupted, error_msg = validator.check_corruption(Path("video.mp4"))

if is_corrupted:
    logger.error(f"Corrupted file detected: {error_msg}")
    raise ValidationError(f"File is corrupted: {error_msg}")
else:
    logger.info("File integrity check passed")
```

**Common Corruption Errors:**
- `"Invalid data found when processing input"` - Corrupt headers
- `"moov atom not found"` - Incomplete MP4 file
- `"Decoding timed out"` - Severely damaged file
- `"End of file"` - Truncated download

**Performance:** ~1-3 seconds per file (decodes only 5 seconds)

---

## Usage Patterns

### Pattern 1: API Request Validation

```python
from fastapi import HTTPException, UploadFile
from src.infrastructure.validators.audio_validator import AudioValidator

validator = AudioValidator()

async def transcribe_endpoint(file: UploadFile):
    """Validate uploaded file before transcription."""
    
    # Save uploaded file
    temp_path = Path(f"uploads/{file.filename}")
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    # Validate file
    metadata = validator.validate_file(temp_path, strict=True)
    
    if not metadata.is_valid:
        temp_path.unlink()  # Delete invalid file
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Invalid audio file",
                "reasons": metadata.validation_errors
            }
        )
    
    # Check corruption
    is_corrupted, error_msg = validator.check_corruption(temp_path)
    if is_corrupted:
        temp_path.unlink()
        raise HTTPException(
            status_code=422,
            detail={"error": "Corrupted file", "message": error_msg}
        )
    
    # Estimate processing time
    min_time, max_time = validator.estimate_processing_time(
        metadata, model_name="base", device="cuda"
    )
    
    logger.info(
        f"Valid file received: {metadata.duration_formatted}, "
        f"estimated processing: {min_time:.0f}-{max_time:.0f}s"
    )
    
    # Proceed with transcription
    result = await transcription_service.transcribe(temp_path)
    return result
```

### Pattern 2: Batch File Validation

```python
from pathlib import Path
from typing import List, Tuple

def validate_batch(file_paths: List[Path]) -> Tuple[List[Path], List[Tuple[Path, List[str]]]]:
    """Validate multiple files and return valid/invalid lists."""
    validator = AudioValidator()
    
    valid_files = []
    invalid_files = []
    
    for file_path in file_paths:
        metadata = validator.validate_file(file_path, strict=False)
        
        if metadata.is_valid:
            valid_files.append(file_path)
        else:
            invalid_files.append((file_path, metadata.validation_errors))
    
    logger.info(
        f"Batch validation: {len(valid_files)} valid, "
        f"{len(invalid_files)} invalid"
    )
    
    return valid_files, invalid_files
```

### Pattern 3: Pre-Processing Filter

```python
async def pre_process_video(video_path: Path) -> bool:
    """Check if video needs pre-processing."""
    validator = AudioValidator()
    metadata = validator.validate_file(video_path)
    
    # Check if resampling needed
    needs_resampling = metadata.sample_rate != 16000
    
    # Check if channel mixing needed
    needs_channel_mix = metadata.channels != 1
    
    # Check if codec conversion needed
    needs_conversion = metadata.codec_name not in ['pcm_s16le', 'wav']
    
    if needs_resampling or needs_channel_mix or needs_conversion:
        logger.info(
            f"Pre-processing required: "
            f"resample={needs_resampling}, "
            f"channel_mix={needs_channel_mix}, "
            f"convert={needs_conversion}"
        )
        return True
    
    return False
```

### Pattern 4: User Feedback with Estimates

```python
from fastapi import BackgroundTasks

async def transcribe_with_estimate(
    file_path: Path,
    background_tasks: BackgroundTasks
) -> dict:
    """Provide user with processing time estimate."""
    validator = AudioValidator()
    
    # Validate and get metadata
    metadata = validator.validate_file(file_path, strict=True)
    
    if not metadata.is_valid:
        raise HTTPException(422, detail=metadata.validation_errors)
    
    # Estimate processing time
    min_time, max_time = validator.estimate_processing_time(
        metadata, model_name="base", device="cuda"
    )
    
    # Return estimate to user immediately
    response = {
        "message": "Transcription started",
        "video_duration": metadata.duration_formatted,
        "estimated_time_seconds": {
            "min": int(min_time),
            "max": int(max_time)
        },
        "file_size_mb": round(metadata.file_size_mb, 2)
    }
    
    # Start transcription in background
    background_tasks.add_task(transcribe_async, file_path)
    
    return response
```

---

## Configuration

Validation limits can be adjusted per use case:

```python
# config/settings.py
class Settings(BaseSettings):
    # Audio Validation Limits
    MAX_VIDEO_DURATION_HOURS: int = 10
    MIN_VIDEO_DURATION_SECONDS: float = 0.5
    MAX_FILE_SIZE_GB: int = 5
    AUDIO_VALIDATION_STRICT: bool = False  # Strict mode by default
```

**Environment Variables:**
```bash
MAX_VIDEO_DURATION_HOURS=10
MIN_VIDEO_DURATION_SECONDS=0.5
MAX_FILE_SIZE_GB=5
AUDIO_VALIDATION_STRICT=false
```

---

## Error Messages

**Common Validation Errors:**

| Error | Meaning | Solution |
|-------|---------|----------|
| `File does not exist` | Path invalid | Check file path |
| `File is empty (0 bytes)` | Empty file uploaded | Re-upload valid file |
| `File too large: X GB (max: 5GB)` | Exceeds size limit | Compress video or split |
| `File too short: X s (min: 0.5s)` | Not enough audio | Upload longer clip |
| `File too long: X h (max: 10h)` | Exceeds duration limit | Split into chunks |
| `Unsupported audio codec: X` | Codec not supported | Convert to AAC/MP3 |
| `No audio channels detected` | No audio stream | Check file has audio |
| `FFprobe failed: X` | Cannot read file | File corrupted/invalid |

---

## Testing

### Unit Test Example

```python
# tests/unit/test_audio_validator.py
import pytest
from pathlib import Path
from src.infrastructure.validators.audio_validator import AudioValidator, AudioMetadata

@pytest.fixture
def validator():
    return AudioValidator()

def test_valid_mp4_file(validator, sample_video_mp4):
    """Test validation of valid MP4 video."""
    metadata = validator.validate_file(sample_video_mp4)
    
    assert metadata.is_valid
    assert metadata.duration_seconds > 0
    assert metadata.codec_name in validator.SUPPORTED_AUDIO_CODECS
    assert len(metadata.validation_errors) == 0

def test_file_not_exists(validator):
    """Test validation of non-existent file."""
    metadata = validator.validate_file(Path("nonexistent.mp4"))
    
    assert not metadata.is_valid
    assert "File does not exist" in metadata.validation_errors

def test_empty_file(validator, tmp_path):
    """Test validation of empty file."""
    empty_file = tmp_path / "empty.mp4"
    empty_file.touch()
    
    metadata = validator.validate_file(empty_file)
    
    assert not metadata.is_valid
    assert "File is empty (0 bytes)" in metadata.validation_errors

def test_unsupported_codec_strict(validator, sample_video_unsupported_codec):
    """Test strict mode rejects unsupported codec."""
    metadata = validator.validate_file(sample_video_unsupported_codec, strict=True)
    
    assert not metadata.is_valid
    assert any("Unsupported audio codec" in err for err in metadata.validation_errors)

def test_processing_time_estimation(validator, sample_video_mp4):
    """Test processing time estimation."""
    metadata = validator.validate_file(sample_video_mp4)
    
    min_time, max_time = validator.estimate_processing_time(
        metadata, model_name="base", device="cuda"
    )
    
    assert min_time > 0
    assert max_time > min_time
    assert max_time < metadata.duration_seconds * 2  # Reasonable estimate

def test_corruption_detection_valid(validator, sample_video_mp4):
    """Test corruption detection on valid file."""
    is_corrupted, error_msg = validator.check_corruption(sample_video_mp4)
    
    assert not is_corrupted
    assert error_msg is None

def test_metadata_properties(validator, sample_video_mp4):
    """Test AudioMetadata computed properties."""
    metadata = validator.validate_file(sample_video_mp4)
    
    # Test file_size_mb property
    assert metadata.file_size_mb == metadata.file_size_bytes / (1024 * 1024)
    
    # Test duration_formatted property
    assert isinstance(metadata.duration_formatted, str)
    assert ":" in metadata.duration_formatted  # HH:MM:SS format
```

---

## Related Documentation

- **FFmpeg Optimizer**: `docs-en/architecture/infrastructure/utils/ffmpeg-optimizer.md` (Metadata extraction)
- **API Usage Guide**: `docs-en/04-API-USAGE.md` (File upload validation)
- **Troubleshooting**: `docs-en/08-TROUBLESHOOTING.md` (Validation errors)
- **DTOs**: `src/application/dtos/transcription_dtos.py` (Request validation)

---

## Best Practices

### ✅ DO
- Always validate files **before** processing
- Use strict mode for user uploads (security)
- Provide clear error messages to users
- Check corruption for uploaded files
- Return processing time estimates to users
- Log validation results for monitoring

### ❌ DON'T
- Don't process files without validation (wastes resources)
- Don't decode entire file for validation (use FFprobe)
- Don't ignore validation errors
- Don't set overly strict limits (balance usability)
- Don't trust file extensions (validate actual format)
- Don't skip corruption checks for large files

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v2.2 | 2024 | Complete audio validation system with corruption detection |
| v2.1 | 2024 | Added processing time estimation |
| v2.0 | 2024 | FFprobe-based metadata extraction |
| v1.0 | 2023 | Basic file validation |
