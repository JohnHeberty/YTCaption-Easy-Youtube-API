# Video Info API Route

## Overview

The **POST /api/v1/video/info** endpoint retrieves comprehensive YouTube video metadata without downloading the video. It provides language detection, subtitle availability, processing time estimates, and Whisper model recommendations to help users make informed decisions before transcription.

**Key Features:**
- 📹 **Fast Metadata Extraction** - No video download required
- 🌍 **Language Detection** - Automatic language identification with confidence score
- 📝 **Subtitle Discovery** - Lists manual and auto-generated subtitles
- 🤖 **Smart Recommendations** - Suggests YouTube transcripts vs. Whisper
- ⏱️ **Processing Estimates** - Predicts transcription time
- ⚡ **Rate Limiting** - 10 requests/minute per IP
- 🔒 **Circuit Breaker Protection** - Prevents cascading failures

**Endpoint:** `POST /api/v1/video/info`  
**Version:** v2.2 (2024)

---

## Architecture Position

```
┌─────────────────────────────────────────────┐
│   Client (Browser/App)                      │
│   - Sends POST /api/v1/video/info          │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   Presentation Layer                        │
│  ┌─────────────────────────────────────┐   │
│  │   Rate Limiting Middleware          │   │ ← 10 req/min/IP
│  │   (SlowAPI)                          │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │   get_video_info() ROUTE            │◄──┼─── THIS ENDPOINT
│  │   (THIS MODULE)                      │   │
│  │   - YouTube URL validation           │   │
│  │   - Video metadata extraction        │   │
│  │   - Language detection               │   │
│  │   - Subtitle discovery               │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   Infrastructure Layer                      │
│  ┌─────────────────────────────────────┐   │
│  │   YouTubeDownloader                  │   │
│  │   - get_video_info_with_language()  │   │
│  │   - yt-dlp integration               │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

**Dependencies:**
- `fastapi` - Web framework
- `slowapi` - Rate limiting
- **DTOs**: `VideoInfoResponseDTO`, `LanguageDetectionDTO`, `SubtitlesInfoDTO`, `WhisperRecommendationDTO`
- **Downloader**: `IVideoDownloader` interface

---

## Request Specification

### HTTP Method & Endpoint

```http
POST /api/v1/video/info
Content-Type: application/json
```

### Request Body (TranscribeRequestDTO)

```python
@dataclass
class TranscribeRequestDTO:
    youtube_url: str            # Full YouTube video URL
    language: str = "auto"      # Not used for video info (metadata only)
```

**JSON Schema:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

### Request Parameters

#### `youtube_url` (required)

**Type:** `string`  
**Format:** Full YouTube URL

**Supported Formats:**
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID&t=30s`

**Example:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

---

## Response Specification

### Success Response (200 OK)

**VideoInfoResponseDTO:**
```python
@dataclass
class VideoInfoResponseDTO:
    video_id: str                                   # YouTube video ID
    title: str                                      # Video title
    duration_seconds: float                         # Duration in seconds
    duration_formatted: str                         # HH:MM:SS format
    uploader: Optional[str]                         # Channel name
    upload_date: Optional[str]                      # YYYYMMDD format
    view_count: Optional[int]                       # View count
    description_preview: str                        # First 200 chars
    language_detection: Optional[LanguageDetectionDTO]
    subtitles: SubtitlesInfoDTO
    whisper_recommendation: Optional[WhisperRecommendationDTO]
    warnings: List[str]                             # Processing warnings
```

**Example Response:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration_seconds": 213.5,
  "duration_formatted": "00:03:33",
  "uploader": "Rick Astley",
  "upload_date": "20091025",
  "view_count": 1234567890,
  "description_preview": "The official video for "Never Gonna Give You Up" by Rick Astley. The new album 'Are We There Yet?' is out now...",
  "language_detection": {
    "detected_language": "en",
    "confidence": 0.98,
    "method": "youtube_metadata"
  },
  "subtitles": {
    "available": ["en", "es", "fr", "pt"],
    "manual_languages": ["en"],
    "auto_languages": ["es", "fr", "pt"],
    "total": 4
  },
  "whisper_recommendation": {
    "should_use_youtube_transcript": true,
    "reason": "Manual subtitles available in English with high quality",
    "estimated_time_whisper": 45.2,
    "estimated_time_youtube": 2.3
  },
  "warnings": [
    "Manual subtitles available in 1 languages. You can use YouTube transcripts instead of Whisper for faster results."
  ]
}
```

### Nested DTOs

#### LanguageDetectionDTO

```python
@dataclass
class LanguageDetectionDTO:
    detected_language: str      # ISO 639-1 code (e.g., "en", "pt")
    confidence: float           # 0.0 to 1.0
    method: str                 # Detection method used
```

**Example:**
```json
{
  "detected_language": "en",
  "confidence": 0.98,
  "method": "youtube_metadata"
}
```

**Detection Methods:**
- `"youtube_metadata"` - From YouTube's video language field
- `"subtitle_analysis"` - Analyzed from available subtitles
- `"title_description"` - NLP analysis of title/description
- `"audio_detection"` - Whisper language detection on sample

#### SubtitlesInfoDTO

```python
@dataclass
class SubtitlesInfoDTO:
    available: List[str]        # All available subtitle languages
    manual_languages: List[str] # Manually created subtitles
    auto_languages: List[str]   # Auto-generated captions
    total: int                  # Total count
```

**Example:**
```json
{
  "available": ["en", "es", "fr", "pt", "de"],
  "manual_languages": ["en", "es"],
  "auto_languages": ["fr", "pt", "de"],
  "total": 5
}
```

**Subtitle Quality:**
- **Manual** (high quality): Human-created, accurate timing
- **Auto** (variable quality): YouTube auto-generated, may have errors

#### WhisperRecommendationDTO

```python
@dataclass
class WhisperRecommendationDTO:
    should_use_youtube_transcript: bool  # Recommendation
    reason: str                          # Explanation
    estimated_time_whisper: Optional[float]  # Seconds (Whisper)
    estimated_time_youtube: Optional[float]  # Seconds (YouTube)
```

**Example:**
```json
{
  "should_use_youtube_transcript": true,
  "reason": "Manual subtitles available in English with high quality",
  "estimated_time_whisper": 45.2,
  "estimated_time_youtube": 2.3
}
```

**Recommendation Logic:**
- Manual subtitles exist → Use YouTube (20x faster)
- Auto-captions exist → Consider YouTube (faster, lower quality)
- No subtitles → Use Whisper (slower, better quality)

---

## Warnings System

### Automatic Warnings

**Duration-Based Warnings:**

| Duration | Warning |
|----------|---------|
| > 1 hour | "Video is long (>1h). Processing may take 20-30 minutes with 'base' model." |
| > 2 hours | "Video is very long (>2h). Processing may take significant time. Consider using 'tiny' or 'base' model for faster results." |
| > 3 hours | "Video exceeds recommended maximum duration (3h). Processing may fail or timeout. Consider processing shorter videos." |

**Subtitle-Based Warnings:**

| Condition | Warning |
|-----------|---------|
| Manual subtitles exist | "Manual subtitles available in X languages. You can use YouTube transcripts instead of Whisper for faster results." |
| Only auto-captions | "Auto-generated captions available in X languages. You can use them for faster results, but quality may vary." |

**Example Warnings Array:**
```json
{
  "warnings": [
    "Video is very long (>2h). Processing may take significant time. Consider using 'tiny' or 'base' model for faster results.",
    "Manual subtitles available in 2 languages. You can use YouTube transcripts instead of Whisper for faster results."
  ]
}
```

---

## Error Responses

### 400 Bad Request - Invalid URL

**Trigger:** Malformed YouTube URL

```json
{
  "error": "ValidationError",
  "message": "Invalid YouTube URL: Must be a valid YouTube URL",
  "request_id": "abc-123-def",
  "details": {}
}
```

### 404 Not Found - Video Not Found

**Trigger:** Video doesn't exist, is private, or age-restricted

```json
{
  "error": "VideoDownloadError",
  "message": "Video is unavailable",
  "request_id": "abc-123-def",
  "details": {
    "url": "https://www.youtube.com/watch?v=INVALID"
  }
}
```

### 429 Too Many Requests - Rate Limit

**Trigger:** More than 10 requests per minute from same IP

```json
{
  "error": "RateLimitExceeded",
  "message": "Rate limit exceeded: 10 per 1 minute",
  "request_id": "abc-123-def",
  "details": {
    "limit": "10/minute",
    "retry_after_seconds": 60
  }
}
```

**Response Headers:**
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
```

### 500 Internal Server Error

**Trigger:** Unexpected error during metadata extraction

```json
{
  "error": "InternalServerError",
  "message": "Failed to get video information",
  "request_id": "abc-123-def",
  "details": {}
}
```

### 503 Service Unavailable - Circuit Breaker

**Trigger:** YouTube API circuit breaker is open

```json
{
  "error": "ServiceTemporarilyUnavailable",
  "message": "YouTube API is temporarily unavailable. Circuit breaker 'youtube_downloader' is open. Please try again later.",
  "request_id": "abc-123-def",
  "details": {
    "retry_after_seconds": 60
  }
}
```

---

## Rate Limiting

### Configuration

**Default Limit:** 10 requests per minute per IP address

**Implementation:** SlowAPI

**Decorator:**
```python
@limiter.limit("10/minute")
async def get_video_info(...):
    ...
```

### Rate Limit Headers

```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1640000000
```

---

## Usage Examples

### Example 1: Basic Video Info (cURL)

```bash
curl -X POST "http://localhost:8000/api/v1/video/info" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
  }'
```

### Example 2: Python with Decision Logic

```python
import requests

def get_transcription_plan(youtube_url: str):
    """Get video info and decide transcription strategy."""
    
    response = requests.post(
        "http://localhost:8000/api/v1/video/info",
        json={"youtube_url": youtube_url}
    )
    
    if response.status_code != 200:
        print(f"Error: {response.json()}")
        return None
    
    info = response.json()
    
    print(f"Title: {info['title']}")
    print(f"Duration: {info['duration_formatted']}")
    print(f"Language: {info['language_detection']['detected_language']}")
    print(f"Subtitles: {info['subtitles']['total']} available")
    
    # Check recommendation
    rec = info.get('whisper_recommendation')
    if rec and rec['should_use_youtube_transcript']:
        print(f"\n✅ Recommendation: Use YouTube transcript")
        print(f"   Reason: {rec['reason']}")
        print(f"   Estimated time: {rec['estimated_time_youtube']:.1f}s")
        return "youtube"
    else:
        print(f"\n⚙️  Recommendation: Use Whisper")
        if rec:
            print(f"   Estimated time: {rec['estimated_time_whisper']:.1f}s")
        return "whisper"
    
    # Print warnings
    if info['warnings']:
        print("\n⚠️  Warnings:")
        for warning in info['warnings']:
            print(f"   - {warning}")

# Usage
strategy = get_transcription_plan("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
```

### Example 3: JavaScript with UI Updates

```javascript
async function checkVideoBeforeTranscribe(youtubeUrl) {
  const response = await fetch('http://localhost:8000/api/v1/video/info', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ youtube_url: youtubeUrl })
  });
  
  if (!response.ok) {
    const error = await response.json();
    console.error(`Error: ${error.message}`);
    return;
  }
  
  const info = await response.json();
  
  // Update UI with video info
  document.getElementById('video-title').textContent = info.title;
  document.getElementById('duration').textContent = info.duration_formatted;
  document.getElementById('language').textContent = 
    info.language_detection?.detected_language || 'Unknown';
  
  // Show subtitle availability
  const subtitlesDiv = document.getElementById('subtitles-info');
  if (info.subtitles.total > 0) {
    subtitlesDiv.innerHTML = `
      ✅ ${info.subtitles.manual_languages.length} manual, 
      ${info.subtitles.auto_languages.length} auto-generated
    `;
  } else {
    subtitlesDiv.innerHTML = '❌ No subtitles available';
  }
  
  // Show recommendation
  const rec = info.whisper_recommendation;
  if (rec?.should_use_youtube_transcript) {
    document.getElementById('recommendation').innerHTML = `
      <strong>Recommendation:</strong> Use YouTube transcript 
      (${rec.estimated_time_youtube.toFixed(1)}s vs 
      ${rec.estimated_time_whisper.toFixed(1)}s with Whisper)
    `;
  }
  
  // Show warnings
  if (info.warnings.length > 0) {
    const warningsDiv = document.getElementById('warnings');
    warningsDiv.innerHTML = info.warnings
      .map(w => `<div class="warning">⚠️ ${w}</div>`)
      .join('');
  }
}
```

### Example 4: Batch Video Analysis

```python
import requests
from typing import List, Dict

def analyze_playlist(video_urls: List[str]) -> Dict:
    """Analyze multiple videos and provide summary."""
    
    results = {
        'total_duration': 0,
        'languages': {},
        'with_subtitles': 0,
        'recommend_youtube': 0,
        'recommend_whisper': 0,
        'warnings': []
    }
    
    for url in video_urls:
        try:
            response = requests.post(
                "http://localhost:8000/api/v1/video/info",
                json={"youtube_url": url}
            )
            
            if response.status_code == 200:
                info = response.json()
                
                # Aggregate statistics
                results['total_duration'] += info['duration_seconds']
                
                lang = info['language_detection']['detected_language']
                results['languages'][lang] = results['languages'].get(lang, 0) + 1
                
                if info['subtitles']['total'] > 0:
                    results['with_subtitles'] += 1
                
                rec = info.get('whisper_recommendation', {})
                if rec.get('should_use_youtube_transcript'):
                    results['recommend_youtube'] += 1
                else:
                    results['recommend_whisper'] += 1
                
                results['warnings'].extend(info['warnings'])
        
        except Exception as e:
            print(f"Error analyzing {url}: {e}")
    
    # Print summary
    hours = results['total_duration'] / 3600
    print(f"Total duration: {hours:.1f} hours")
    print(f"Languages: {results['languages']}")
    print(f"With subtitles: {results['with_subtitles']}/{len(video_urls)}")
    print(f"Recommend YouTube: {results['recommend_youtube']}")
    print(f"Recommend Whisper: {results['recommend_whisper']}")
    
    return results
```

---

## Performance Characteristics

### Response Time

| Operation | Time |
|-----------|------|
| Video info extraction | 1-3 seconds |
| Language detection | <0.5 seconds |
| Subtitle discovery | <1 second |
| Total response time | 2-5 seconds |

**Factors:**
- **Network speed**: YouTube API response time
- **Video metadata size**: More subtitles = slightly slower
- **Circuit breaker state**: OPEN = instant failure

---

## Testing

### Unit Test Example

```python
# tests/integration/test_video_info_route.py
import pytest
from fastapi.testclient import TestClient
from src.presentation.api.main import app

client = TestClient(app)

def test_video_info_success():
    """Test successful video info retrieval."""
    response = client.post(
        "/api/v1/video/info",
        json={
            "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "video_id" in data
    assert "title" in data
    assert "duration_seconds" in data
    assert "language_detection" in data
    assert "subtitles" in data
    assert isinstance(data["warnings"], list)

def test_video_info_invalid_url():
    """Test invalid YouTube URL."""
    response = client.post(
        "/api/v1/video/info",
        json={"youtube_url": "not-a-youtube-url"}
    )
    
    assert response.status_code == 400
    error = response.json()
    assert error["error"] == "ValidationError"

def test_rate_limiting():
    """Test rate limiting (10 requests per minute)."""
    url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    
    # Make 10 requests
    for i in range(10):
        response = client.post("/api/v1/video/info", json={"youtube_url": url})
        assert response.status_code in [200, 400, 404]
    
    # 11th request should be rate limited
    response = client.post("/api/v1/video/info", json={"youtube_url": url})
    assert response.status_code == 429

def test_subtitle_discovery():
    """Test subtitle information in response."""
    response = client.post(
        "/api/v1/video/info",
        json={"youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"}
    )
    
    data = response.json()
    subtitles = data["subtitles"]
    
    assert "available" in subtitles
    assert "manual_languages" in subtitles
    assert "auto_languages" in subtitles
    assert subtitles["total"] == len(subtitles["available"])
```

---

## Related Documentation

- **Transcription Route**: `docs-en/architecture/presentation/routes/transcription.md` (Main endpoint)
- **YouTube Downloader**: `src/infrastructure/youtube/downloader.py` (Metadata extraction)
- **DTOs**: `src/application/dtos/transcription_dtos.py` (Response models)
- **API Usage Guide**: `docs-en/04-API-USAGE.md` (User guide)

---

## Best Practices

### ✅ DO
- Call this endpoint before `/transcribe` for large videos
- Use recommendations to choose transcription strategy
- Check warnings before processing
- Handle rate limits with exponential backoff
- Cache video info to avoid repeated calls
- Use subtitle availability to optimize workflow

### ❌ DON'T
- Don't ignore processing time estimates
- Don't skip this endpoint for videos >1 hour
- Don't assume all videos have subtitles
- Don't ignore language detection confidence
- Don't retry immediately on rate limit
- Don't download video just to get metadata

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v2.2 | 2024 | Added Circuit Breaker protection, improved warnings |
| v2.1 | 2024 | Added rate limiting (10 req/min), enhanced error handling |
| v2.0 | 2024 | Language detection, Whisper recommendations |
| v1.0 | 2023 | Initial video info endpoint |
