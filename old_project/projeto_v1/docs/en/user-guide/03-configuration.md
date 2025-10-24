# ⚙️ Configuration Guide

Complete guide to all environment variables (`.env`) - explained one by one.

---

## 📋 Table of Contents

1. [Application Settings](#application-settings)
2. [Server Settings](#server-settings)
3. [Whisper Settings](#whisper-settings)
4. [Parallel Transcription Settings](#parallel-transcription-settings)
5. [YouTube Settings](#youtube-settings)
6. [YouTube Resilience v3.0](#youtube-resilience-v30)
7. [Storage Settings](#storage-settings)
8. [API Settings](#api-settings)
9. [Logging Settings](#logging-settings)
10. [Performance Settings](#performance-settings)
11. [Recommended Scenarios](#-recommended-configurations-by-scenario)

---

## Application Settings

### `APP_NAME`
**Application name displayed in logs and documentation.**

```bash
APP_NAME=Whisper Transcription API
```

- **Type**: String
- **Default**: `Whisper Transcription API`
- **When to change**: Branding customization

---

### `APP_VERSION`
**Application version for release control.**

```bash
APP_VERSION=3.0.0
```

- **Type**: String (Semantic Versioning)
- **Default**: `3.0.0`
- **When to change**: After major changes

---

### `APP_ENVIRONMENT`
**Execution environment (affects logging and behavior).**

```bash
APP_ENVIRONMENT=production
```

- **Type**: String
- **Values**: `production`, `development`, `staging`
- **Default**: `production`
- **Impact**:
  - `production`: Minimal logs, optimizations enabled
  - `development`: Verbose logs, hot-reload
  - `staging`: Hybrid for testing

---

## Server Settings

### `HOST`
**IP address the server listens on.**

```bash
HOST=0.0.0.0
```

- **Type**: IP Address
- **Common values**:
  - `0.0.0.0`: All interfaces (Docker/production)
  - `127.0.0.1`: Localhost only (development)
- **Default**: `0.0.0.0`
- **When to change**: Restrictive security (localhost only)

---

### `PORT`
**TCP port where API listens.**

```bash
PORT=8000
```

- **Type**: Integer (1-65535)
- **Default**: `8000`
- **When to change**: Port conflict, specific firewall rules
- **Note**: Changing requires updating `docker-compose.yml` ports

---

## Whisper Settings

### `WHISPER_MODEL`
**AI model used for transcription.**

```bash
WHISPER_MODEL=base
```

- **Type**: String
- **Values**: `tiny`, `base`, `small`, `medium`, `large`, `turbo`
- **Default**: `base`

| Model | Size | RAM/Worker | Accuracy | Speed | Recommended Use |
|--------|---------|------------|----------|------------|-----------------|
| `tiny` | 39M | ~400MB | ⭐⭐ | ⚡⚡⚡⚡⚡ | Development, testing |
| `base` | 74M | ~800MB | ⭐⭐⭐ | ⚡⚡⚡⚡ | **Production (default)** |
| `small` | 244M | ~1.5GB | ⭐⭐⭐⭐ | ⚡⚡⚡ | High quality, powerful CPU |
| `medium` | 769M | ~3GB | ⭐⭐⭐⭐⭐ | ⚡⚡ | GPU or dedicated server |
| `large` | 1550M | ~6GB | ⭐⭐⭐⭐⭐ | ⚡ | Powerful GPU, maximum quality |

**When to use each**:
- **tiny**: Tests, development, maximum speed
- **base**: ✅ **Recommended** - ideal balance
- **small**: Podcasts, interviews (high quality)
- **medium**: Professional transcriptions with GPU
- **large**: Academic, official subtitles

---

### `WHISPER_DEVICE`
**Processing device.**

```bash
WHISPER_DEVICE=cpu
```

- **Type**: String
- **Values**: `cpu`, `cuda`
- **Default**: `cpu`

**CPU**:
- ✅ Works on any server
- ⚠️ Slower (30min for 1h of audio)
- 💰 Economical

**CUDA (NVIDIA GPU)**:
- ✅ 10-20x faster
- ⚠️ Requires NVIDIA GPU + drivers
- 💰 Server with GPU needed

**How to verify GPU:**
```bash
nvidia-smi
```

---

### `WHISPER_LANGUAGE`
**Default language for transcription.**

```bash
WHISPER_LANGUAGE=auto
```

- **Type**: String (ISO 639-1)
- **Default**: `auto` (automatic detection)
- **Values**: `auto`, `pt`, `en`, `es`, `fr`, `de`, `it`, `ja`, `ko`, `zh`

**When to specify**:
- ✅ **auto**: Let Whisper detect (recommended)
- ✅ **pt**: If all videos are in Portuguese (slight improvement)
- ✅ **en**: If all videos are in English

**Note**: Specifying language can improve accuracy by ~5-10%

---

## Parallel Transcription Settings

### `ENABLE_PARALLEL_TRANSCRIPTION`
**Enable/disable parallel processing.**

```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
```

- **Type**: Boolean
- **Values**: `true`, `false`
- **Default**: `false`

**When to enable (`true`)**:
- ✅ CPU with 4+ cores
- ✅ Sufficient RAM (8GB+)
- ✅ Long videos (10+ minutes)
- ✅ Want maximum speed

**When to disable (`false`)**:
- ✅ CPU with 2 cores or less
- ✅ Limited RAM (4GB or less)
- ✅ Short videos (<5 min)
- ✅ Stability > speed

**Benefit**: 3-4x faster on multi-core CPUs

---

### `PARALLEL_WORKERS`
**Number of workers for parallel processing.**

```bash
PARALLEL_WORKERS=2
```

- **Type**: Integer
- **Values**: `2`, `4`, `6`, `8`
- **Default**: `2` (conservative)

**Configuration by scenario**:

| CPU Cores | Total RAM | PARALLEL_WORKERS | RAM Used (base model) |
|-----------|-----------|------------------|----------------------|
| 2 cores | 4GB | Disable parallel | ~800MB |
| 4 cores | 8GB | `2` ✅ | ~1.6GB |
| 8 cores | 16GB | `4` | ~3.2GB |
| 16 cores | 32GB+ | `8` | ~6-8GB |

**RAM calculation**:
```
Required RAM = PARALLEL_WORKERS × RAM_per_model
```

Example:
- `base` model = 800MB
- 4 workers = 4 × 800MB = **3.2GB RAM**

**Recommendations**:
- **2**: ✅ **Conservative** - works in most cases
- **4**: Aggressive - requires 16GB+ RAM
- **8+**: Dedicated servers only

---

### `PARALLEL_CHUNK_DURATION`
**Duration of each audio chunk processed in parallel.**

```bash
PARALLEL_CHUNK_DURATION=120
```

- **Type**: Integer (seconds)
- **Values**: `60`, `90`, `120`, `180`, `240`
- **Default**: `120` (2 minutes)

**How to choose**:

| Value | Chunks (30min) | Overhead | Recommended Use |
|-------|----------------|----------|-----------------|
| `60` | 30 chunks | High | Many cores (8+) |
| `90` | 20 chunks | Medium | Balanced |
| `120` ✅ | 15 chunks | Low | **Default (recommended)** |
| `180` | 10 chunks | Very low | Few cores (2-4) |
| `240` | 7 chunks | Minimal | Limited CPU |

**Trade-off**:
- ⬇️ Smaller chunks (60s) = More parallelism, more overhead
- ⬆️ Larger chunks (240s) = Less parallelism, less overhead

---

## YouTube Settings

### `YOUTUBE_FORMAT`
**Audio quality downloaded from YouTube.**

```bash
YOUTUBE_FORMAT=worstaudio
```

- **Type**: String
- **Values**: `worstaudio`, `bestaudio`
- **Default**: `worstaudio`

**Why "worstaudio"?**
- ✅ Download 10x faster
- ✅ Less disk usage
- ✅ Whisper works well with low quality
- ✅ Sufficient for transcription

**When to use "bestaudio"**:
- Detailed audio analysis
- Music/complex sounds
- You have bandwidth and disk to spare

---

### `MAX_VIDEO_SIZE_MB`
**Maximum allowed video size (in MB).**

```bash
MAX_VIDEO_SIZE_MB=2500
```

- **Type**: Integer (megabytes)
- **Default**: `2500` (2.5GB)
- **Recommended limit**: 500MB - 5000MB

**Approximate calculation**:
```
1 hour of audio (worstaudio) ≈ 30-50MB
```

**When to adjust**:
- `500`: Short videos only (<30min)
- `1500`: ✅ Up to 1 hour
- `2500`: ✅ **Default** - up to 3 hours
- `5000`: Very long videos (lectures, livestreams)

---

### `MAX_VIDEO_DURATION_SECONDS`
**Maximum allowed video duration (in seconds).**

```bash
MAX_VIDEO_DURATION_SECONDS=10800
```

- **Type**: Integer (seconds)
- **Default**: `10800` (3 hours)

**Useful conversions**:
```
1800 = 30 minutes
3600 = 1 hour
7200 = 2 hours
10800 = 3 hours ✅ (default)
14400 = 4 hours
```

**When to adjust**:
- `1800`: Short videos only
- `3600`: Up to 1 hour (classes, tutorials)
- `7200`: Up to 2 hours (lectures)
- `10800`: ✅ **Default** - up to 3 hours
- `21600`: Livestreams, long podcasts (6 hours)

---

### `DOWNLOAD_TIMEOUT`
**Timeout for YouTube download (in seconds).**

```bash
DOWNLOAD_TIMEOUT=900
```

- **Type**: Integer (seconds)
- **Default**: `900` (15 minutes)

**When to adjust**:
- `300`: Fast internet (5 min)
- `600`: Default (10 min)
- `900`: ✅ **Recommended** - 15 minutes
- `1800`: Slow internet or large videos (30 min)

---

## YouTube Resilience v3.0

**Resilience system to solve YouTube blocks (HTTP 403, Network unreachable).**

### `YOUTUBE_MAX_RETRIES`
**Maximum number of download attempts.**

```bash
YOUTUBE_MAX_RETRIES=5
```

- **Type**: Integer
- **Values**: `1`, `3`, `5`, `7`, `10`
- **Default**: `5` ✅

**How it works**:
- System tries up to N times before giving up
- Each attempt uses a different strategy (if multi-strategy enabled)
- Delay between attempts is exponential (YOUTUBE_RETRY_DELAY)

**When to increase** (`7` or `10`):
- Very unstable network
- YouTube blocking frequently
- Server in high-latency region
- Want maximum persistence

**When to decrease** (`1` or `3`):
- Want to fail fast
- Have external fallback
- Download not critical

---

### `YOUTUBE_RETRY_DELAY_MIN` / `YOUTUBE_RETRY_DELAY_MAX`
**Minimum/maximum delay between retries (seconds).**

```bash
YOUTUBE_RETRY_DELAY_MIN=10
YOUTUBE_RETRY_DELAY_MAX=120
```

- **Type**: Integer (seconds)
- **Default**: `10` / `120` ✅

**How it works**:
- Delay is randomly chosen between MIN and MAX
- Increases exponentially with each attempt
- Example with defaults (10-120):
  - 1st attempt: 10-30s
  - 2nd attempt: 30-60s
  - 3rd attempt: 60-120s
  - 4th attempt: 120s (max)

**Configurations by scenario**:

| Scenario | MIN | MAX | Behavior | When to Use |
|---------|-----|-----|---------------|-------------|
| **Aggressive** | 5 | 30 | Fail fast, less wait | Tests, debugging |
| **Default** ✅ | 10 | 120 | Balance | Normal production |
| **Conservative** | 30 | 300 | More chances, more wait | YouTube blocking a lot |

**Why random delay?**
- ✅ Looks like human traffic (not a bot)
- ✅ Avoids synchronization (multiple workers)
- ✅ Distributes load on YouTube

---

### `YOUTUBE_CIRCUIT_BREAKER_THRESHOLD`
**Number of consecutive failures to open circuit breaker.**

```bash
YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=8
```

- **Type**: Integer
- **Values**: `5`, `8`, `10`, `15`
- **Default**: `8` ✅

**How it works** (Circuit Breaker Pattern):
1. **Closed** (normal): Download attempts pass through
2. **Open** (blocked): After N failures, stops trying (returns immediate error)
3. **Half-Open** (test): After timeout, allows 1 test attempt

**When to increase** (`10` or `15`):
- YouTube with sporadic blocks
- Want more persistence before giving up

**When to decrease** (`5`):
- Want to fail fast after problems
- Have automatic alerts

---

### `YOUTUBE_CIRCUIT_BREAKER_TIMEOUT`
**Wait time before trying again after circuit breaker opens (seconds).**

```bash
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=180
```

- **Type**: Integer (seconds)
- **Default**: `180` (3 minutes) ✅

**How it works**:
- Circuit breaker opens after N failures
- Waits TIMEOUT seconds
- Enters "Half-Open" state (allows 1 test)
- If test passes: returns to normal (Closed)
- If test fails: returns to Open (waits more TIMEOUT)

**Suggested values**:
- `60`: Quick recovery (1 min)
- `180`: ✅ **Default** - balanced (3 min)
- `300`: Conservative (5 min)
- `600`: Very conservative (10 min)

---

### `YOUTUBE_REQUESTS_PER_MINUTE`
**Request limit per minute (rate limiting).**

```bash
YOUTUBE_REQUESTS_PER_MINUTE=10
```

- **Type**: Integer
- **Values**: `5`, `10`, `15`, `20`, `30`
- **Default**: `10` ✅

**Why rate limiting?**
- ✅ Avoids automatic YouTube ban
- ✅ Looks like human traffic (not bot)
- ✅ Distributes server load
- ✅ Prevents abuse detection

**Configurations by scenario**:

| Scenario | Value | Behavior | When to Use |
|---------|-------|---------------|-------------|
| **Very Conservative** | 5 | 5 downloads/min | YouTube blocking a lot |
| **Conservative** | 8 | 8 downloads/min | Public server |
| **Default** ✅ | 10 | 10 downloads/min | Normal production |
| **Aggressive** | 15 | 15 downloads/min | Dedicated server |
| **Very Aggressive** | 20-30 | 20-30 downloads/min | ⚠️ Risk of ban |

**⚠️ Warning**: YouTube may ban if detecting >30 req/min consistently.

---

### `YOUTUBE_REQUESTS_PER_HOUR`
**Request limit per hour (global rate limiting).**

```bash
YOUTUBE_REQUESTS_PER_HOUR=200
```

- **Type**: Integer
- **Values**: `100`, `200`, `300`, `500`, `1000`
- **Default**: `200` ✅

**Dual window**:
- System uses 2 windows: minute + hour
- Blocks if ANY one reaches limit
- Example: 10/min AND 200/hour

**Configurations by scenario**:

| Scenario | /hour | /day estimated | When to Use |
|---------|-------|---------------|-------------|
| **Conservative** | 100 | ~2.4k | Public server |
| **Default** ✅ | 200 | ~4.8k | Normal production |
| **Aggressive** | 500 | ~12k | High volume |
| **Very Aggressive** | 1000 | ~24k | ⚠️ Dedicated server only |

**Note**: YouTube may have undocumented limits of its own.

---

### `YOUTUBE_COOLDOWN_ON_ERROR`
**Cooldown time after consecutive errors (seconds).**

```bash
YOUTUBE_COOLDOWN_ON_ERROR=60
```

- **Type**: Integer (seconds)
- **Values**: `30`, `60`, `120`, `300`
- **Default**: `60` ✅

**How it works** (Exponential Backoff):
- 1st error: 60s pause
- 2nd consecutive error: 120s pause (2x)
- 3rd consecutive error: 240s pause (4x)
- 4th consecutive error: 480s pause (8x)
- Success resets the counter

**When to increase** (`120` or `300`):
- YouTube blocking aggressively
- Want to avoid permanent ban
- Prefer waiting more between attempts

**When to decrease** (`30`):
- Errors are rare
- Want quick recovery

---

### `ENABLE_TOR_PROXY`
**Enable Tor proxy (FREE, anonymous, IP rotation).**

```bash
ENABLE_TOR_PROXY=false
```

- **Type**: Boolean
- **Values**: `true`, `false`
- **Default**: `false` ✅ (disabled)

**What is Tor?**
- Network of anonymous and free proxies
- Automatic IP change every 30-60 seconds
- YouTube sees Tor IP, not your real IP
- **ZERO COST** (alternative to paid proxies)

**Why use Tor? (`true`)**
- ✅ **FREE** (no monthly fees)
- ✅ Bypass IP blocks
- ✅ Anonymity (YouTube doesn't see your IP)
- ✅ Automatic IP rotation
- ✅ Bypass regional blocks

**Why NOT use Tor? (`false`)** ✅
- ⚠️ Slower (latency +500ms~2s)
- ⚠️ Tor IPs may be on YouTube blacklist
- ⚠️ Some Tor IPs are blocked
- ⚠️ Download may be slower

**When to enable** (`true`):
- ❌ YouTube is blocking your IP
- ❌ Frequent 403 Forbidden error
- ❌ Persistent "Network unreachable"
- ❌ No budget for paid proxies ($50-200/month)
- ✅ Want anonymity

**When to disable** (`false`) ✅:
- ✅ Direct connection working well
- ✅ Want maximum speed
- ✅ Tor has many errors

**Tor Service** (included in docker-compose.yml):
- Container: `tor-proxy` (dperson/torproxy)
- SOCKS5 port: `9050` (for Python/yt-dlp)
- HTTP port: `8118` (for browsers)
- IP rotation: 30-60 seconds automatic
- Optimized config: MaxCircuitDirtiness=60, NewCircuitPeriod=30

**Test Tor**:
```bash
# Check if Tor is running
docker ps | grep tor-proxy

# View logs
docker logs whisper-tor-proxy

# Test connection
docker exec whisper-api curl --socks5 tor-proxy:9050 https://check.torproject.org
```

---

### `TOR_PROXY_URL`
**Tor proxy URL (if enabled).**

```bash
TOR_PROXY_URL=socks5://tor-proxy:9050
```

- **Type**: String (URL)
- **Format**: `socks5://HOST:PORT` or `http://HOST:PORT`
- **Default**: `socks5://tor-proxy:9050` ✅

**When to change**:
- Use external Tor (outside Docker): `socks5://localhost:9050`
- Use custom HTTP proxy: `http://my-proxy:8080`
- Use commercial Tor service: `socks5://tor-commercial.com:9050`

**Valid formats**:
- `socks5://tor-proxy:9050` (SOCKS5 - recommended)
- `socks5://localhost:9050` (local Tor)
- `http://proxy.com:8080` (HTTP proxy)
- `https://proxy.com:443` (HTTPS proxy)

---

### `ENABLE_MULTI_STRATEGY`
**Enable multi-strategy download system (7 fallback strategies).**

```bash
ENABLE_MULTI_STRATEGY=true
```

- **Type**: Boolean
- **Values**: `true`, `false`
- **Default**: `true` ✅ (recommended)

**What does it do?**
- Tries 7 different download strategies
- Automatic fallback if one fails
- Increases success rate from 60% → 95% (+58%)
- Each strategy uses different YouTube clients (Android, iOS, Web, TV, etc.)

**Strategies (in priority order)**:
1. **android_client** (priority 1) - Most reliable in 2025
2. **android_music** (priority 2) - YouTube Music specific
3. **ios_client** (priority 3) - Official iOS client
4. **web_embed** (priority 4) - Web embed player
5. **tv_embedded** (priority 5) - Smart TV player
6. **mweb** (priority 6) - Mobile web
7. **default** (priority 7) - Final fallback

**When to enable** (`true`) ✅:
- ✅ Production (always)
- ✅ Want maximum success rate
- ✅ YouTube is blocking
- ✅ Unstable connection

**When to disable** (`false`):
- Debugging (want to test specific strategy)
- Want to fail fast (no fallback attempts)
- Development/testing

**Logging**:
```
🎯 Trying strategy: android_client (priority 1)
✅ Download completed with strategy 'android_client'
```

Or if it fails:
```
🎯 Trying strategy: android_client (priority 1)
⚠️  Strategy 'android_client' failed: HTTP Error 403
🔄 Trying next strategy...
🎯 Trying strategy: ios_client (priority 3)
✅ Download completed with strategy 'ios_client'
```

---

### `ENABLE_USER_AGENT_ROTATION`
**Enable User-Agent rotation for each request.**

```bash
ENABLE_USER_AGENT_ROTATION=true
```

- **Type**: Boolean
- **Values**: `true`, `false`
- **Default**: `true` ✅ (recommended)

**What does it do?**
- Rotates User-Agent (browser/device) for each request
- 17 pre-configured UAs (updated for 2025)
- Integration with fake-useragent library (70% random, 30% custom)
- Looks like varied human traffic (not bot with fixed UA)

**User-Agents included**:

**Desktop**:
- Chrome 120.0.0.0 (Windows 10)
- Chrome 119.0.0.0 (macOS)
- Firefox 121.0 (Windows 10)
- Edge 120.0.0.0 (Windows 11)
- Safari 17.2 (macOS Sonoma)

**Mobile**:
- Chrome 120 Mobile (Android 13)
- Chrome 119 Mobile (Android 14)
- Safari iOS 17.1 (iPhone 15 Pro)
- Safari iOS 17.2 (iPhone 15 Pro Max)

**Tablet**:
- Samsung Galaxy Tab S8 (Android 13)

**Smart TV / Console**:
- PlayStation 5
- LG WebOS 6.0

**Why UA rotation?**
- ✅ Avoids bot detection (fixed UA is suspicious)
- ✅ Looks like diversified human traffic
- ✅ Bypass fingerprinting
- ✅ Improves success rate

**When to enable** (`true`) ✅:
- ✅ Production (always)
- ✅ YouTube detecting bot
- ✅ Want to look like human traffic
- ✅ Combination with multi-strategy

**When to disable** (`false`):
- Debugging (want specific UA)
- Reproducible tests
- Development

**UA Mix**:
- 70%: fake-useragent library (newest and most varied UAs)
- 30%: Custom pool (17 tested and working UAs)

---

## YouTube Resilience Summary (v3.0)

**Quick summary of resilience settings**:

```bash
# === Rate Limiting (avoid ban) ===
YOUTUBE_REQUESTS_PER_MINUTE=10          # Limit per minute
YOUTUBE_REQUESTS_PER_HOUR=200           # Limit per hour

# === Retry Logic (persistence) ===
YOUTUBE_MAX_RETRIES=5                   # Maximum attempts
YOUTUBE_RETRY_DELAY_MIN=10              # Minimum delay (s)
YOUTUBE_RETRY_DELAY_MAX=120             # Maximum delay (s)
YOUTUBE_COOLDOWN_ON_ERROR=60            # Cooldown after errors (s)

# === Circuit Breaker (protection) ===
YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=8     # Failures to open
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=180     # Timeout for retry (s)

# === Advanced Features ===
ENABLE_TOR_PROXY=false                  # Enable if blocked ⚠️
TOR_PROXY_URL=socks5://tor-proxy:9050   # Tor URL
ENABLE_MULTI_STRATEGY=true              # ✅ Keep enabled
ENABLE_USER_AGENT_ROTATION=true         # ✅ Keep enabled
```

**Use case scenarios**:

| Problem | Solution | Configuration |
|----------|---------|--------------|
| **YouTube blocking (403)** | Enable Tor + Multi-Strategy | `ENABLE_TOR_PROXY=true` |
| **Network unreachable** | Check DNS + Enable Tor | Check `docker-compose.yml` dns |
| **Rate limit too high** | Reduce limits | `YOUTUBE_REQUESTS_PER_MINUTE=5` |
| **Slow download** | Disable Tor (if enabled) | `ENABLE_TOR_PROXY=false` |
| **Sporadic failures** | Increase retries | `YOUTUBE_MAX_RETRIES=7` |
| **Persistent ban** | Longer cooldown + Tor | `YOUTUBE_COOLDOWN_ON_ERROR=300` |

---

## Storage Settings

### `TEMP_DIR`
**Directory for temporary files.**

```bash
TEMP_DIR=/app/temp
```

- **Type**: Path (relative or absolute)
- **Default**: `/app/temp`
- **When to change**: Switch disk/volume

**Absolute path example**:
```bash
TEMP_DIR=/mnt/storage/ytcaption-temp
```

---

### `CLEANUP_ON_STARTUP`
**Clean temporary files on startup.**

```bash
CLEANUP_ON_STARTUP=true
```

- **Type**: Boolean
- **Values**: `true`, `false`
- **Default**: `true`

**Recommendation**: Leave `true` to avoid garbage accumulation

---

### `CLEANUP_AFTER_PROCESSING`
**Clean temporary files after each transcription.**

```bash
CLEANUP_AFTER_PROCESSING=true
```

- **Type**: Boolean
- **Values**: `true`, `false`
- **Default**: `true`

**When to disable (`false`)**:
- Debug (analyze downloaded files)
- Audio cache
- ⚠️ Requires periodic manual cleanup

---

### `MAX_TEMP_AGE_HOURS`
**Maximum age of temp files before cleanup.**

```bash
MAX_TEMP_AGE_HOURS=24
```

- **Type**: Integer (hours)
- **Default**: `24` (1 day)
- **Values**: `1`, `6`, `12`, `24`, `48`, `72`

---

## API Settings

### `MAX_CONCURRENT_REQUESTS`
**Maximum number of simultaneous transcriptions.**

```bash
MAX_CONCURRENT_REQUESTS=3
```

- **Type**: Integer
- **Default**: `3`

**Calculation**:
```
Required RAM = MAX_CONCURRENT_REQUESTS × RAM_per_model
```

Example:
- 3 requests × 800MB (base) = **2.4GB RAM**

**Recommendations by RAM**:
- 4GB RAM: `MAX_CONCURRENT_REQUESTS=2`
- 8GB RAM: `MAX_CONCURRENT_REQUESTS=3` ✅
- 16GB RAM: `MAX_CONCURRENT_REQUESTS=6`
- 32GB+ RAM: `MAX_CONCURRENT_REQUESTS=10`

---

### `REQUEST_TIMEOUT`
**Timeout for each request (in seconds).**

```bash
REQUEST_TIMEOUT=3600
```

- **Type**: Integer (seconds)
- **Default**: `3600` (1 hour)

**When to adjust**:
- `1800`: Videos up to 30min
- `3600`: ✅ **Default** - up to 1 hour
- `7200`: Videos up to 2 hours
- `10800`: Videos up to 3 hours

---

### `ENABLE_CORS`
**Enable CORS (for browser access).**

```bash
ENABLE_CORS=true
```

- **Type**: Boolean
- **Values**: `true`, `false`
- **Default**: `true`

**When to disable**: Backend-only API (no web frontend)

---

### `CORS_ORIGINS`
**Allowed origins for CORS.**

```bash
CORS_ORIGINS=*
```

- **Type**: String (comma-separated URLs)
- **Default**: `*` (all origins)

**Examples**:
```bash
# Allow all (development)
CORS_ORIGINS=*

# Specific domain only (production)
CORS_ORIGINS=https://my-site.com

# Multiple domains
CORS_ORIGINS=https://my-site.com,https://app.my-site.com
```

---

## Logging Settings

### `LOG_LEVEL`
**Log detail level.**

```bash
LOG_LEVEL=INFO
```

- **Type**: String
- **Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Default**: `INFO`

| Level | Detail | Use |
|-------|--------|-----|
| `DEBUG` | Maximum | Development |
| `INFO` ✅ | Moderate | **Production (default)** |
| `WARNING` | Warnings only | Silent production |
| `ERROR` | Errors only | Minimal |

---

### `LOG_FORMAT`
**Log output format.**

```bash
LOG_FORMAT=json
```

- **Type**: String
- **Values**: `json`, `text`
- **Default**: `json`

**JSON**: Ideal for parsing, log tools (ELK, Grafana)  
**TEXT**: More human-readable

---

### `LOG_FILE`
**Log file path.**

```bash
LOG_FILE=/app/logs/app.log
```

- **Type**: Path
- **Default**: `/app/logs/app.log`

---

## Performance Settings

### `WORKERS`
**Number of Uvicorn workers (API processes).**

```bash
WORKERS=1
```

- **Type**: Integer
- **Values**: `1`, `2`, `4`
- **Default**: `1` ✅

**⚠️ IMPORTANT**: For this application, `WORKERS=1` is **optimal**!

**Why?**
- Application is I/O bound (waits for download, FFmpeg)
- Multiple workers compete for Whisper model
- FastAPI async/await already handles concurrency

**When to use > 1**:
- Very high traffic (100+ req/s)
- RAM to spare (8GB+ per worker)
- You disabled parallel transcription

---

## 📊 Recommended Configurations by Scenario

### Small Server (4GB RAM, 2 cores)
```bash
WHISPER_MODEL=tiny
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=false
MAX_CONCURRENT_REQUESTS=2
WORKERS=1
```

### Medium Server (8GB RAM, 4 cores) ✅ **Default**
```bash
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2
MAX_CONCURRENT_REQUESTS=3
WORKERS=1
```

### Large Server (16GB+ RAM, 8+ cores)
```bash
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4
MAX_CONCURRENT_REQUESTS=6
WORKERS=1
```

### Server with GPU
```bash
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
ENABLE_PARALLEL_TRANSCRIPTION=false  # GPU is already fast
MAX_CONCURRENT_REQUESTS=4
WORKERS=1
```

---

## 📚 Next Steps

- **[API Usage](./04-api-usage.md)** - Learn how to use the API
- **[Troubleshooting](./05-troubleshooting.md)** - Solve common problems
- **[Installation](./02-installation.md)** - Installation guide

---

**Version**: 3.0.0  
**Last Updated**: October 2025  
**Contributors**: YTCaption Team

[← Back to User Guide](./README.md)
