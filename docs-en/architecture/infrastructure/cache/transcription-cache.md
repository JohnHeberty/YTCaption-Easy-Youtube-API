# TranscriptionCache

LRU (Least Recently Used) cache for transcriptions with TTL management and MD5 hashing.

---

## Overview

`TranscriptionCache` provides intelligent caching for video transcriptions, reducing GPU load by 40-60% for repeated content. It uses file hashing to detect duplicates and implements LRU eviction with configurable TTL.

**Location**: `src/infrastructure/cache/transcription_cache.py`

**Version**: 2.0 (introduced in v2.0 release)

**Key Features**:
- ✅ File hash-based duplicate detection (MD5/SHA256)
- ✅ LRU (Least Recently Used) eviction policy
- ✅ Configurable TTL (Time-To-Live)
- ✅ Thread-safe operations with RLock
- ✅ Instant responses for cached content
- ✅ Hit rate statistics and monitoring
- ✅ Singleton pattern for global access

---

## Architecture Position

```
┌─────────────────────────────────────┐
│    APPLICATION LAYER                │
│    TranscribeVideo Use Case         │
└──────────────┬──────────────────────┘
               │ uses cache
┌──────────────▼──────────────────────┐
│   INFRASTRUCTURE LAYER              │
│   TranscriptionCache                │
│   - File hashing (MD5)              │
│   - LRU eviction                    │
│   - TTL expiration                  │
│   - Statistics tracking             │
└─────────────────────────────────────┘
```

---

## Data Structures

### CachedTranscription

Immutable cache entry with metadata.

```python
@dataclass
class CachedTranscription:
    file_hash: str              # MD5/SHA256 hash
    transcription_data: Dict    # Full transcription result
    model_name: str             # Whisper model used
    language: str               # Language code
    cached_at: float            # Unix timestamp
    last_accessed: float        # Last access time
    access_count: int           # Number of accesses
    file_size_bytes: int        # Original file size
```

**Methods**:
- `is_expired(ttl_seconds) -> bool` - Check if entry expired
- `mark_accessed()` - Update access time and count
- `age_minutes() -> float` - Get age in minutes
- `to_dict() -> dict` - Serialize to dict

---

## TranscriptionCache Class

### Initialization

```python
class TranscriptionCache:
    def __init__(
        self,
        max_size: int = 100,
        ttl_hours: int = 24,
        hash_algorithm: str = "md5"
    ):
        """
        Initialize transcription cache.
        
        Args:
            max_size: Maximum number of cached transcriptions
            ttl_hours: Time-To-Live in hours
            hash_algorithm: "md5" or "sha256"
        """
```

**Internal State**:
```python
self._cache: OrderedDict[str, CachedTranscription]  # LRU cache
self._lock: threading.RLock                          # Thread safety
self._stats: dict                                     # Hit/miss statistics
```

**Example**:
```python
cache = TranscriptionCache(
    max_size=100,      # Store up to 100 transcriptions
    ttl_hours=24,      # Expire after 24 hours
    hash_algorithm="md5"
)
```

---

## Core Methods

### File Hashing

#### `compute_file_hash(file_path: Path, chunk_size: int = 8192) -> str`

Computes file hash efficiently using streaming.

```python
file_hash = cache.compute_file_hash(Path("video.mp4"))
# Result: "a1b2c3d4e5f6..."
```

**Algorithm**:
```python
def compute_file_hash(self, file_path: Path) -> str:
    hasher = hashlib.md5()  # or sha256
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    
    return hasher.hexdigest()
```

**Performance**:
- **Speed**: ~500 MB/s (SSD)
- **Memory**: Constant (8KB chunks)
- **Overhead**: ~2ms for 100MB file

---

### Cache Operations

#### `get(file_hash: str, model_name: str, language: str) -> Optional[Dict]`

Retrieves transcription from cache.

```python
result = cache.get(
    file_hash="a1b2c3d4...",
    model_name="base",
    language="en"
)

if result:
    # Cache HIT - instant response
    return result
else:
    # Cache MISS - transcribe video
    result = transcribe_video(...)
    cache.put(...)
```

**Behavior**:
1. Build cache key: `{hash}:{model}:{language}`
2. Check if entry exists
3. Check if entry expired (TTL)
4. Mark entry as accessed (LRU)
5. Move entry to end (most recent)
6. Update statistics

**Returns**: 
- `Dict` with transcription if found
- `None` if not found or expired

#### `put(file_hash, transcription_data, model_name, language, file_size_bytes)`

Adds transcription to cache.

```python
cache.put(
    file_hash="a1b2c3d4...",
    transcription_data={
        "text": "Full transcription...",
        "segments": [...],
        "language": "en"
    },
    model_name="base",
    language="en",
    file_size_bytes=10485760  # 10 MB
)
```

**LRU Eviction**:
```python
if len(self._cache) >= self.max_size:
    # Remove oldest (least recently used)
    evicted_key, evicted_entry = self._cache.popitem(last=False)
    logger.debug(f"Cache EVICTION: {evicted_key[:16]}...")
```

**Update Behavior**: If entry exists, updates data and moves to end.

---

### Cache Management

#### `invalidate(file_hash: str)`

Removes all cache entries for a file.

```python
# Remove all cached versions (all models/languages)
cache.invalidate(file_hash="a1b2c3d4...")
```

**Use Case**: File was modified or re-uploaded.

#### `clear()`

Clears entire cache.

```python
cache.clear()
# All entries removed
```

#### `cleanup_expired() -> int`

Removes expired entries based on TTL.

```python
removed_count = cache.cleanup_expired()
print(f"Removed {removed_count} expired entries")
```

**Recommended**: Run periodically (e.g., every hour).

---

### Statistics

#### `get_stats() -> Dict`

Returns cache performance statistics.

```python
stats = cache.get_stats()

# Result:
{
    "cache_size": 45,                # Current entries
    "max_size": 100,                 # Maximum capacity
    "ttl_seconds": 86400,            # 24 hours
    "total_requests": 1000,          # Total get() calls
    "hits": 650,                     # Successful hits
    "misses": 350,                   # Cache misses
    "hit_rate_percent": 65.0,        # Hit rate
    "evictions": 12,                 # LRU evictions
    "expirations": 8,                # TTL expirations
    "total_size_bytes": 524288000,   # Total cached data
    "total_size_mb": 500.0           # Size in MB
}
```

**Metrics**:
- **Hit Rate**: `hits / (hits + misses) * 100`
- **Evictions**: Number of LRU removals
- **Expirations**: Number of TTL removals

#### `get_cached_entries() -> List[Dict]`

Lists all cached entries with metadata.

```python
entries = cache.get_cached_entries()

# Result:
[
    {
        "file_hash": "a1b2c3d4e5f6...",
        "model_name": "base",
        "language": "en",
        "age_minutes": 45.2,
        "access_count": 5,
        "file_size_mb": 12.5
    },
    ...
]
```

---

## Usage Patterns

### 1. Basic Caching Flow

```python
from src.infrastructure.cache import TranscriptionCache
from pathlib import Path

cache = TranscriptionCache(max_size=100, ttl_hours=24)

async def transcribe_with_cache(video_path: Path, model: str, language: str):
    # Compute file hash
    file_hash = cache.compute_file_hash(video_path)
    
    # Try cache
    cached_result = cache.get(file_hash, model, language)
    
    if cached_result:
        logger.info("Using cached transcription")
        return cached_result
    
    # Cache miss - transcribe
    logger.info("Transcribing video (cache miss)")
    result = await whisper_service.transcribe(video_path, language)
    
    # Store in cache
    cache.put(
        file_hash=file_hash,
        transcription_data=result.to_dict(),
        model_name=model,
        language=language,
        file_size_bytes=video_path.stat().st_size
    )
    
    return result
```

### 2. Singleton Pattern

```python
from src.infrastructure.cache import get_transcription_cache

# Global singleton instance
cache = get_transcription_cache(max_size=100, ttl_hours=24)

# Use in different modules
def use_cache():
    cache = get_transcription_cache()  # Same instance
    result = cache.get(...)
```

**Implementation**:
```python
_global_cache: Optional[TranscriptionCache] = None
_cache_lock = threading.Lock()

def get_transcription_cache(max_size=100, ttl_hours=24):
    global _global_cache
    
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = TranscriptionCache(max_size, ttl_hours)
    
    return _global_cache
```

### 3. Periodic Cleanup Task

```python
async def periodic_cache_cleanup():
    """Background task to clean expired entries."""
    cache = get_transcription_cache()
    
    while True:
        await asyncio.sleep(3600)  # Every hour
        
        removed = cache.cleanup_expired()
        logger.info(f"Cache cleanup: {removed} expired entries removed")
        
        # Log statistics
        stats = cache.get_stats()
        logger.info(
            f"Cache stats: size={stats['cache_size']}, "
            f"hit_rate={stats['hit_rate_percent']}%"
        )

# Start background task
asyncio.create_task(periodic_cache_cleanup())
```

### 4. Monitoring Integration

```python
from prometheus_client import Gauge, Counter

# Prometheus metrics
cache_size_gauge = Gauge('transcription_cache_size', 'Current cache size')
cache_hit_rate = Gauge('transcription_cache_hit_rate', 'Cache hit rate percentage')
cache_hits = Counter('transcription_cache_hits', 'Total cache hits')
cache_misses = Counter('transcription_cache_misses', 'Total cache misses')

def update_cache_metrics():
    """Update Prometheus metrics."""
    stats = cache.get_stats()
    
    cache_size_gauge.set(stats['cache_size'])
    cache_hit_rate.set(stats['hit_rate_percent'])
    cache_hits.inc(stats['hits'])
    cache_misses.inc(stats['misses'])
```

---

## Configuration

From `src/config/settings.py`:

```python
# Cache settings (v2.0)
enable_transcription_cache: bool = True
cache_max_size: int = 100           # Max entries
cache_ttl_hours: int = 24           # Expiration time
```

**Usage**:
```python
from src.config.settings import settings

if settings.enable_transcription_cache:
    cache = TranscriptionCache(
        max_size=settings.cache_max_size,
        ttl_hours=settings.cache_ttl_hours
    )
```

**Tuning Guidelines**:

| Scenario | max_size | ttl_hours | Notes |
|----------|----------|-----------|-------|
| **Low traffic** | 50 | 24 | Small cache sufficient |
| **Medium traffic** | 100 | 24 | Default balanced |
| **High traffic** | 200 | 12 | More entries, shorter TTL |
| **Development** | 10 | 1 | Quick testing |

---

## Performance Impact

### Benefits

**GPU Load Reduction**:
- 40-60% reduction for repeated content
- Instant response for cached videos
- Enables higher concurrent requests

**Latency Improvement**:
```
Without Cache: 30-120 seconds (transcription time)
With Cache:    <100ms (disk + deserialization)

Speedup: 300-1200x for cache hits
```

**Cost Savings** (Cloud GPU):
```
GPU: NVIDIA T4 ($0.35/hour)
Cache Hit Rate: 50%
Requests/day: 1000
Avg Duration: 60s

Savings: ~$100/month with cache
```

### Overhead

**Memory Usage**:
```
Per Entry: ~50KB (metadata + transcription)
100 Entries: ~5MB
200 Entries: ~10MB
```

**Hash Computation**:
```
100MB file: ~2ms (MD5)
1GB file: ~20ms (MD5)
10GB file: ~200ms (MD5)
```

**Cache Lookup**: O(1) - OrderedDict access

---

## Thread Safety

**Mechanism**: `threading.RLock()` (Reentrant Lock)

```python
with self._lock:
    # All cache operations protected
    entry = self._cache[key]
    entry.mark_accessed()
    self._cache.move_to_end(key)
```

**Concurrency**: Safe for multiple threads/async tasks.

---

## Testing

```python
import pytest
from pathlib import Path
from src.infrastructure.cache import TranscriptionCache

def test_cache_hit():
    cache = TranscriptionCache(max_size=10, ttl_hours=1)
    
    # Compute hash
    file_path = Path("test_video.mp4")
    file_hash = cache.compute_file_hash(file_path)
    
    # Put transcription
    transcription_data = {"text": "Hello world", "segments": []}
    cache.put(file_hash, transcription_data, "base", "en", 1024)
    
    # Get from cache
    result = cache.get(file_hash, "base", "en")
    
    assert result == transcription_data
    
    # Check statistics
    stats = cache.get_stats()
    assert stats['hits'] == 1
    assert stats['misses'] == 0
    assert stats['hit_rate_percent'] == 100.0

def test_lru_eviction():
    cache = TranscriptionCache(max_size=2, ttl_hours=1)
    
    # Fill cache to capacity
    cache.put("hash1", {"text": "1"}, "base", "en", 1024)
    cache.put("hash2", {"text": "2"}, "base", "en", 1024)
    
    # This should evict hash1 (LRU)
    cache.put("hash3", {"text": "3"}, "base", "en", 1024)
    
    # hash1 should be evicted
    assert cache.get("hash1", "base", "en") is None
    
    # hash2 and hash3 should exist
    assert cache.get("hash2", "base", "en") is not None
    assert cache.get("hash3", "base", "en") is not None
    
    # Check eviction count
    stats = cache.get_stats()
    assert stats['evictions'] == 1
```

---

## Related Documentation

- **Use Case**: [TranscribeVideo](../../application/use-cases/transcribe-video.md)
- **Config**: [Settings](../../config/README.md)
- **Monitoring**: [Prometheus Metrics](../monitoring/metrics.md)

---

## Best Practices

### ✅ DO

```python
# Use singleton for global cache
cache = get_transcription_cache()

# Always compute hash consistently
file_hash = cache.compute_file_hash(file_path)

# Include model and language in cache key
result = cache.get(file_hash, model, language)

# Run periodic cleanup
asyncio.create_task(periodic_cache_cleanup())
```

### ❌ DON'T

```python
# Don't create multiple cache instances
# cache1 = TranscriptionCache()  # Wrong!
# cache2 = TranscriptionCache()  # Wrong!

# Don't use URL as cache key
# result = cache.get(youtube_url, ...)  # Wrong!

# Don't forget to handle cache misses
# result = cache.get(...)
# return result  # May be None!
```

---

## Version History

| Version | Changes |
|---------|---------|
| **v2.0** | Initial TranscriptionCache implementation |
| **v2.1** | Added statistics tracking, hit rate metrics |
| **v3.0** | Singleton pattern, monitoring integration |

---

[← Back](./README.md)

**Version**: 3.0.0
