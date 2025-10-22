# YouTubeDownloader

**Path**: `src/infrastructure/youtube/downloader.py`

---

## 📋 Overview

**Responsibility**: Main orchestrator for YouTube video downloads (Facade Pattern)

**Layer**: Infrastructure Layer

**Version**: v3.0 (YouTube Resilience System)

**Dependencies**:
- `DownloadConfig` - Centralized configurations
- `StrategyManager` - Manages 7 download strategies
- `RateLimiter` - Rate limiting + Circuit Breaker
- `UserAgentRotator` - Rotates 17 User-Agents
- `ProxyManager` - Manages Tor proxy (SOCKS5)
- `YouTubeMetrics` - Records 26 Prometheus metrics

---

## 🎯 Purpose

Coordinate all **5 resilience layers** to ensure 95% success rate for YouTube downloads:

1. **DNS Resilience** - Google DNS + Cloudflare
2. **Multi-Strategy Download** - 7 sequential strategies
3. **Rate Limiting** - Requests/min control + Circuit Breaker
4. **User-Agent Rotation** - 17 different UAs
5. **Tor Proxy** - IP anonymization

---

## 🏗️ Architecture

### Applied Patterns

| Pattern | Application |
|---------|-------------|
| **Facade** | Simplifies access to 5 resilience subsystems |
| **Dependency Injection** | Receives `DownloadConfig` via constructor |
| **Retry with Exponential Backoff** | `delay = min(min_delay * 2^attempt, max_delay)` |
| **Circuit Breaker** | Stops after N failures, waits timeout |

---

## 📚 Public Interface

### `download(youtube_url: str) -> str`

**Description**: Downloads audio from a YouTube video

**Parameters**:
- `youtube_url` (str): Video URL (`https://youtube.com/watch?v=VIDEO_ID`)

**Returns**:
- `str`: Absolute path of downloaded audio file (`.m4a` or `.webm`)

**Exceptions**:
| Exception | When | Solution |
|-----------|------|----------|
| `AllStrategiesFailedError` | All 7 strategies failed | Enable Tor, reduce rate limit |
| `CircuitBreakerOpenError` | Circuit breaker open (too many failures) | Wait timeout (60s default) |
| `RateLimitExceededError` | Requests/min limit reached | Wait cooldown |
| `NetworkUnreachableError` | Tor offline or DNS failed | Check Tor, test DNS |

---

## 🔄 Execution Flow

```
┌─────────────────────────────────────────┐
│  download(youtube_url)                  │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│ 1. RateLimiter.check()                  │
│    • Check requests/min                 │
│    • Check circuit breaker status       │
│    • If OPEN: raise CircuitBreakerOpen  │
└────────────┬────────────────────────────┘
             │ OK
             ↓
┌─────────────────────────────────────────┐
│ 2. UserAgentRotator.get_random()        │
│    • Select 1 of 17 UAs                 │
│    • Chrome/Firefox/Safari/Edge         │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│ 3. ProxyManager.configure()             │
│    • If ENABLE_TOR_PROXY=true           │
│    • Configure SOCKS5: tor-proxy:9050   │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│ 4. StrategyManager.try_all()            │
│    • Try strategies 1-7 sequentially    │
│    • Strategy 1: Direct (no cookies)    │
│    • Strategy 2: Cookies (browser)      │
│    • Strategy 3: Mobile UA              │
│    • Strategy 4: Referer header         │
│    • Strategy 5: Extract format         │
│    • Strategy 6: Embedded player        │
│    • Strategy 7: OAuth2 fallback        │
└────────┬────────────┬───────────────────┘
         │            │
      SUCCESS      FAILURE
         │            │
         ↓            ↓
┌─────────────┐  ┌─────────────────────────┐
│ Metrics     │  │ 5. Exponential Backoff  │
│ .record_    │  │    delay = min * 2^att  │
│  success()  │  │    time.sleep(delay)    │
│             │  └─────────┬───────────────┘
│ Return      │            │
│ audio_path  │            ↓
└─────────────┘  ┌─────────────────────────┐
                 │ 6. Retry (up to MAX)    │
                 │    attempt += 1         │
                 │    if attempt < MAX:    │
                 │        goto step 4      │
                 └─────────┬───────────────┘
                           │ ALL FAILED
                           ↓
                 ┌─────────────────────────┐
                 │ Metrics.record_failure()│
                 │ Circuit Breaker opens   │
                 │ raise AllStrategiesFail │
                 └─────────────────────────┘
```

---

## 📊 Emitted Metrics

### Counters

- `youtube_download_success_total` - Total successful downloads
- `youtube_download_failure_total` - Total failures (all strategies)
- `youtube_403_forbidden_total` - HTTP 403 Forbidden errors
- `youtube_network_error_total` - Network errors (Tor offline, DNS)
- `youtube_strategy_success_total{strategy="1-7"}` - Successes per strategy

### Gauges

- `youtube_circuit_breaker_open` - 1 if open, 0 if closed
- `youtube_cooldown_active` - 1 if in cooldown, 0 otherwise
- `youtube_retries_before_success` - Number of retries until success

### Histograms

- `youtube_request_duration_seconds` - Download time (p50, p95, p99)

---

## 🧪 Usage Example

```python
from src.infrastructure.youtube.downloader import YouTubeDownloader
from src.infrastructure.youtube.download_config import DownloadConfig

# Load configurations from .env
config = DownloadConfig.from_env()

# Instantiate downloader
downloader = YouTubeDownloader(config)

try:
    # Download
    audio_path = downloader.download(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    
    print(f"✅ Download success: {audio_path}")
    # Output: /app/temp/dQw4w9WgXcQ.m4a
    
except AllStrategiesFailedError as e:
    print(f"❌ All 7 strategies failed: {e}")
    print("Solution: Enable Tor or reduce rate limit")
    
except CircuitBreakerOpenError:
    print("⚠️ Circuit breaker open (too many failures)")
    print("Wait 60s (CIRCUIT_BREAKER_TIMEOUT)")
    
except RateLimitExceededError as e:
    print(f"⏱️ Rate limit reached: {e}")
    print("Wait cooldown or increase limits in .env")
```

---

## 🔗 Relationships

### Uses (Composition)

| Module | Purpose |
|--------|---------|
| [DownloadConfig](./download-config.md) | Configurations (retries, timeouts, rate limits) |
| [StrategyManager](./download-strategies.md) | Manages 7 download strategies |
| [RateLimiter](./rate-limiter.md) | Rate limiting + Circuit Breaker |
| [UserAgentRotator](./user-agent-rotator.md) | Rotates 17 User-Agents |
| [ProxyManager](./proxy-manager.md) | Manages Tor proxy (SOCKS5) |
| [YouTubeMetrics](./metrics.md) | Records 26 Prometheus metrics |

### Used By

- `TranscribeVideoUseCase` ([Application Layer](../../application/use-cases.md))

### Implements

- `IVideoDownloader` ([Domain Layer](../../domain/interfaces.md))

---

## 🐛 Debugging

### Enable detailed logs

```bash
# .env
LOG_LEVEL=DEBUG

# Logs show:
# - Strategy being tried
# - Selected User-Agent
# - Configured proxy (Tor)
# - Time for each attempt
# - Failure reason for each strategy
```

### View real-time metrics

```bash
# Grafana
http://localhost:3000
Dashboard: YouTube Resilience v3.0

# Prometheus
http://localhost:9090
Query: rate(youtube_download_success_total[5m])
```

---

## 📖 References

### Diagrams

- [YouTube Resilience Flow](../../../diagrams/youtube-resilience-flow.md)
- [Design Patterns - Facade](../../../diagrams/design-patterns.md#facade)
- [Design Patterns - Circuit Breaker](../../../diagrams/design-patterns.md#circuit-breaker)

### Related Modules

- [DownloadConfig](./download-config.md) - Configurations
- [DownloadStrategies](./download-strategies.md) - 7 strategies
- [RateLimiter](./rate-limiter.md) - Rate limiting
- [Metrics](./metrics.md) - Prometheus

### User Guides

- [Configuration - YouTube Resilience](../../../user-guide/03-configuration.md#youtube-resilience-v30)
- [Troubleshooting - HTTP 403](../../../user-guide/05-troubleshooting.md#http-403-forbidden)
- [Monitoring - Grafana](../../../user-guide/07-monitoring.md)

---

**Version**: 3.0.0  
**Last updated**: 22/10/2025  
**Author**: [@JohnHeberty](https://github.com/JohnHeberty)

---

**[← Back to YouTube Module](./README.md)** | **[Next: DownloadConfig →](./download-config.md)**
