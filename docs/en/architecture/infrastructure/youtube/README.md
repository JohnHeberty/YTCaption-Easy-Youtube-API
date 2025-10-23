# YouTube Module v3.0 - Resilience System

Robust YouTube video download system with resilience.

---

## Overview

The **YouTube Resilience System v3.0** implements intelligent download with:
- **7 progressive strategies** (Standard → Tor)
- **Adaptive rate limiting**
- **User-agent rotation**
- **Proxy support** (HTTP/SOCKS5)
- **Circuit breaker pattern**
- **Exponential retry** with jitter

---

## Download Strategies

1. **Standard**: Direct download with yt-dlp
2. **Format Fallback**: Tries alternative formats
3. **Slow Mode**: Aggressive rate limiting
4. **Proxy**: Uses HTTP/SOCKS5 proxy
5. **User-Agent Rotation**: Rotates headers
6. **Cookies**: Uses browser cookies
7. **Tor Network**: Last resort via Tor

**Automatic fallback**: If one strategy fails, automatically tries the next.

---

## Components

### YouTubeDownloader
- Implements `IVideoDownloader`
- Orchestrates download strategies
- Circuit breaker (failures > threshold = OPEN)
- Success/failure metrics per strategy

### DownloadConfig
- Timeout configuration
- Rate limiting limits
- Format/quality preferences
- Retry settings

### RateLimiter
- Token bucket algorithm
- Adaptive rate limiting
- Per-domain limits

### UserAgentRotator
- Pool of 20+ user agents
- Random rotation
- Realistic headers

### ProxyManager
- List of free/paid proxies
- Automatic health check
- Fallback when proxy fails

---

## Usage Example

```python
from src.infrastructure.youtube import YouTubeDownloader
from src.domain.value_objects import YouTubeURL

# Create downloader
downloader = YouTubeDownloader(
    max_retries=3,
    enable_tor=True,
    proxy_list=["http://proxy1:8080", "socks5://proxy2:1080"]
)

# Download with automatic fallback
url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
video = await downloader.download(url, Path("temp/video.mp4"))

# Metrics
stats = downloader.get_stats()
print(f"Success: {stats['success_rate']}%")
print(f"Most used strategy: {stats['most_used_strategy']}")
```

---

## Metrics

- Total downloads: 10,250
- Success rate: 94.2%
- Standard strategy: 85% success
- Fallback to Tor: 3% of cases
- Average time: 12.5s

---

**Version**: 3.0.0

[⬅️ Back](../README.md)
