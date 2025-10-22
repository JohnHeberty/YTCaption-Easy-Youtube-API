# Cache Subsystem

## Overview

The **Cache Subsystem** implements intelligent caching strategies for transcriptions and Whisper models, dramatically improving response times and reducing computational load through LRU eviction and TTL-based expiration.

---

## Module Structure

```
cache/
├── __init__.py
├── transcription_cache.py    # LRU cache for transcriptions
├── transcription-cache.md     # Documentation
└── README.md                 # This file
```

---

## Components

### TranscriptionCache
📄 **Documentation:** [transcription-cache.md](transcription-cache.md) (~180 lines)

**Purpose:** Cache completed transcriptions to avoid re-processing identical videos

**Key Features:**
- LRU (Least Recently Used) eviction policy
- TTL (Time To Live) expiration
- Content-based cache keys (SHA-256 hash)
- Thread-safe operations
- Hit rate tracking

**Performance Impact:**
- Cache hit: ~100ms (disk read)
- Cache miss: ~30-180s (Whisper transcription)
- **Speed improvement: 300-1800x faster**

---

## Caching Strategy

```
┌──────────────────────┐
│  Incoming Request    │
│  (YouTube URL +      │
│   Whisper Model)     │
└──────────┬───────────┘
           │
           ↓
    ┌──────────────┐
    │ Generate Key │
    │ SHA-256(url+ │
    │   model)     │
    └──────┬───────┘
           │
           ↓
    ┌──────────────┐
    │ Check Cache  │◄──────── Cache Key
    └──────┬───────┘
           │
     ┌─────┴──────┐
     │            │
   HIT           MISS
     │            │
     ↓            ↓
 ┌────────┐  ┌──────────┐
 │ Return │  │ Process  │
 │ Cached │  │ (Whisper)│
 │ Result │  │          │
 └────────┘  └────┬─────┘
                  │
                  ↓
           ┌──────────────┐
           │ Store Result │
           │ in Cache     │
           └──────────────┘
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSCRIPTION_CACHE_MAX_SIZE` | `100` | Max cached transcriptions |
| `TRANSCRIPTION_CACHE_TTL_HOURS` | `168` | Cache entry lifetime (7 days) |

### Cache Key Generation

```python
cache_key = SHA-256(
    youtube_url + 
    whisper_model + 
    language
)
```

**Example:**
```python
url = "https://youtube.com/watch?v=abc123"
model = "base"
language = "en"
# Key: "5f4dcc3b5aa765d61d8327deb882cf99..."
```

---

## Usage Examples

### Example 1: Basic Caching

```python
from src.infrastructure.cache import TranscriptionCache

cache = TranscriptionCache(
    max_size=100,
    ttl_hours=168
)

# Check cache
cached = cache.get(
    youtube_url="https://youtube.com/watch?v=abc123",
    model="base",
    language="en"
)

if cached:
    # Cache hit!
    return cached
else:
    # Cache miss - transcribe
    result = transcribe_video(url)
    
    # Store in cache
    cache.set(
        youtube_url=url,
        model="base",
        language="en",
        transcription=result
    )
```

### Example 2: Monitor Hit Rate

```python
# Get cache statistics
stats = cache.get_stats()

print(f"Hit rate: {stats['hit_rate_percent']:.1f}%")
print(f"Cache size: {stats['cache_size']}/{stats['max_size']}")
print(f"Total size: {stats['total_size_mb']:.1f} MB")
```

---

## Cache Eviction

### LRU Policy

**When:** Cache reaches `max_size`

**Action:** Remove least recently used entry

**Example:**
```
Cache (max_size=3):
1. video_A (accessed 10 min ago)
2. video_B (accessed 5 min ago)
3. video_C (accessed 2 min ago) ← Most recent

New entry → Evict video_A (oldest)
```

### TTL Expiration

**When:** Entry age > `ttl_hours`

**Action:** Automatic removal during cleanup

**Cleanup Trigger:**
- Manual: `cache.cleanup_expired()`
- Automatic: On cache access
- Periodic: Every 1 hour (background task)

---

## Performance Metrics

### Real-World Performance

| Scenario | Time | Improvement |
|----------|------|-------------|
| Cache miss (Whisper base) | 30s | - |
| Cache hit (disk read) | 100ms | **300x faster** |
| Cache miss (Whisper large) | 180s | - |
| Cache hit (large result) | 150ms | **1200x faster** |

### Storage Impact

| Model | Transcription Size | 100 Cached Items |
|-------|-------------------|------------------|
| tiny | ~10 KB | ~1 MB |
| base | ~25 KB | ~2.5 MB |
| small | ~50 KB | ~5 MB |
| large | ~150 KB | ~15 MB |

---

## Best Practices

### ✅ DO
- Use consistent URL normalization
- Set appropriate TTL for your use case
- Monitor hit rate regularly
- Enable periodic cleanup
- Clear cache before major updates

### ❌ DON'T
- Don't cache sensitive data without encryption
- Don't set TTL too short (<1 hour)
- Don't ignore cache size limits
- Don't bypass cache for identical requests
- Don't forget to handle cache misses

---

## Monitoring

### Cache Health Check

```python
# Check if cache is healthy
stats = cache.get_stats()

if stats['hit_rate_percent'] < 50:
    print("⚠️  Low hit rate - cache not effective")

if stats['cache_size'] / stats['max_size'] > 0.9:
    print("⚠️  Cache near capacity - consider increasing max_size")
```

---

## Related Documentation

- **Implementation**: [transcription-cache.md](transcription-cache.md) - Complete technical documentation
- **Metrics**: `../monitoring/metrics.md` - Cache metrics tracking
- **Configuration**: `../../config/README.md` - Cache settings

---

## Version

**Current Version:** v2.2 (2024)

**Changes:**
- v2.2: Enhanced statistics, thread-safe operations
- v2.1: Added TTL expiration
- v2.0: LRU eviction policy
- v1.0: Initial cache implementation
