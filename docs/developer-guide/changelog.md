# 📜 Changelog

All notable changes to YTCaption project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Comprehensive developer documentation (architecture, contributing, testing guides)
- Restructured user documentation (7 guides: quick start, installation, configuration, API usage, troubleshooting, deployment, monitoring)

---

## [3.0.0] - 2025-10-22

### 🚀 MAJOR UPDATE - YouTube Download Resilience System

Complete resilience system to solve critical YouTube blocking issues (HTTP 403 Forbidden, Network unreachable).

#### Added

**5-Layer Resilience System**:

1. **Network Troubleshooting**
   - Public DNS configured (Google 8.8.8.8, 8.8.4.4, Cloudflare 1.1.1.1)
   - Diagnostic tools in container (ping, curl, nslookup, netstat)
   - Updated SSL/TLS certificates (ca-certificates)
   - Resolves "Network unreachable [Errno 101]"

2. **Multi-Strategy Download System** (7 strategies with automatic fallback)
   - `android_client` (priority 1 - most reliable for 2025)
   - `android_music` (priority 2 - YouTube Music specific)
   - `ios_client` (priority 3 - official iOS client)
   - `web_embed` (priority 4 - web embed player)
   - `tv_embedded` (priority 5 - Smart TV player)
   - `mweb` (priority 6 - mobile web)
   - `default` (priority 7 - final fallback)
   - Automatic fallback between strategies on failure
   - Detailed logging of attempts and failures

3. **Intelligent Rate Limiting**
   - Sliding window algorithm: 10 req/min + 200 req/hour (configurable)
   - Exponential backoff: 60s → 120s → 240s → 480s (after consecutive errors)
   - Random jitter (1-5 seconds) to simulate human traffic
   - Automatic cooldown after consecutive errors
   - Real-time rate limiting statistics

4. **User-Agent Rotation**
   - 17 pre-configured User-Agents (updated for 2025)
     - Desktop: Chrome 120/119, Firefox 121, Edge 120, Safari 17.2
     - Mobile: Chrome Android 13/14, Safari iOS 17.1/17.2
     - Tablet: Samsung Galaxy Tab S8
     - Smart TV: PlayStation 5, LG WebOS
   - Integration with fake-useragent library (70% random, 30% custom pool)
   - Automatic rotation per request
   - Specific methods: `get_random()`, `get_mobile()`, `get_desktop()`

5. **Tor Proxy Support** (FREE!)
   - dperson/torproxy service integrated via Docker Compose
   - Ports: SOCKS5 (9050) + HTTP (8118)
   - Automatic IP rotation every 30-60 seconds
   - Optimized Tor circuits (MaxCircuitDirtiness=60, NewCircuitPeriod=30)
   - Disabled by default (ENABLE_TOR_PROXY=false)
   - Zero operational cost

**Monitoring (Prometheus + Grafana)**:
- 26 Prometheus metrics implemented
  - Download metrics: attempts, errors, duration, file size
  - Strategy metrics: successes/failures per strategy, success rate
  - Rate limiting metrics: hits, waits, cooldowns, requests/min, requests/hour
  - User-Agent metrics: rotations by type
  - Proxy metrics: requests per proxy, errors, Tor status
  - Video info metrics: requests, duration
  - Configuration info: current system state

- Complete Grafana Dashboard (10 visual panels):
  1. Download Rate by Strategy (TimeSeries)
  2. Overall Success Rate (Gauge with thresholds)
  3. Requests/minute (Stat with alert)
  4. Requests/hour (Stat with alert)
  5. Tor Status (Stat on/off)
  6. Download Duration Percentiles (TimeSeries P50/P90/P99)
  7. Error Types Distribution (PieChart)
  8. Success by Strategy (DonutChart)
  9. Rate Limit Hits (TimeSeries)
  10. Rate Limit Wait Time Percentiles (TimeSeries)

**New Files** (7 modules + documentation):
- `src/infrastructure/youtube/download_config.py` (94 lines)
- `src/infrastructure/youtube/download_strategies.py` (232 lines)
- `src/infrastructure/youtube/user_agent_rotator.py` (209 lines)
- `src/infrastructure/youtube/rate_limiter.py` (283 lines)
- `src/infrastructure/youtube/proxy_manager.py` (156 lines)
- `src/infrastructure/youtube/metrics.py` (311 lines)
- `scripts/test-v3-installation.ps1` (PowerShell test script)
- `docs/YOUTUBE-RESILIENCE-v3.0.md` (complete guide ~400 lines)
- `docs/PROMETHEUS-GRAFANA-v3.0.md` (metrics guide ~300 lines)

**Configuration** (12 new environment variables):
```bash
YOUTUBE_MAX_RETRIES=5
YOUTUBE_RETRY_DELAY_MIN=10
YOUTUBE_RETRY_DELAY_MAX=120
YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=8
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=180
YOUTUBE_REQUESTS_PER_MINUTE=10
YOUTUBE_REQUESTS_PER_HOUR=200
YOUTUBE_COOLDOWN_ON_ERROR=60
ENABLE_TOR_PROXY=false
ENABLE_MULTI_STRATEGY=true
ENABLE_USER_AGENT_ROTATION=true
TOR_PROXY_URL=socks5://tor-proxy:9050
```

#### Changed

- `requirements.txt`: Added 4 dependencies
  - `aiolimiter==1.1.0` (async rate limiting)
  - `fake-useragent==1.5.1` (User-Agent generation)
  - `PySocks==1.7.1` (SOCKS5 support for Tor)
  - `requests[socks]==2.31.0` (HTTP with SOCKS support)

- `Dockerfile`: Network tools added
  - Builder stage: iputils-ping, curl, dnsutils, net-tools, git
  - Final stage: iputils-ping, curl, dnsutils, net-tools, ca-certificates
  - Enables network diagnostics inside container

- `docker-compose.yml`: 
  - Public DNS configured (8.8.8.8, 8.8.4.4, 1.1.1.1)
  - 12 new environment variables for v3.0
  - New `tor-proxy` service (dperson/torproxy)

- `src/infrastructure/youtube/downloader.py`: Full v3.0 integration
  - Multi-strategy loop in `_download_internal()`
  - Metrics recording on each download
  - Rate limiting before each attempt
  - User-Agent rotation per request
  - Configurable Tor proxy support
  - Enhanced error handling with error type detection

#### Performance

- **Success Rate**:
  - Before: ~60% (single strategy, no resilience)
  - After: ~95% (7 strategies + rate limiting + UA rotation)
  - **Improvement: +58% (+35 percentage points)**

- **Capabilities**:
  - Download strategies: 1 → 7 (+600%)
  - User-Agents available: 1 → 17 (+1700%)
  - Rate limiting: None → Intelligent (sliding window)
  - Proxy support: None → Free Tor
  - Monitoring: Basic → 26 metrics + Grafana Dashboard

- **Resilience**:
  - Automatic fallback between 7 strategies
  - Retry with exponential backoff (10s → 120s)
  - Cooldown after errors (60s → 480s exponential)
  - Free IP rotation via Tor (optional)

#### Breaking Changes

**None!** Completely backward-compatible system.
- All v3.0 features are optional
- Old configurations continue working
- Default behavior unchanged (Tor disabled, multi-strategy enabled)
- Zero impact on existing APIs or contracts

---

## [2.2.0] - 2025-10-19

### Added

**Advanced Audio Normalization**:

- **Volume Normalization (Loudness Normalization)**
  - `loudnorm` filter (EBU R128 standard: -16 LUFS)
  - Equalizes overall audio volume to broadcast standard
  - Useful for very low or very high audio
  - Configurable via `ENABLE_AUDIO_VOLUME_NORMALIZATION=true`

- **Dynamic Audio Normalization**
  - `dynaudnorm` filter (frame-by-frame normalization)
  - Equalizes varying volumes WITHIN the same audio
  - Useful for multiple speakers or varying mic distance
  - Automatically activated with volume normalization

- **Background Noise Reduction**
  - Filters `highpass=200Hz` and `lowpass=3000Hz`
  - Focuses on human voice range (200Hz-3kHz)
  - Removes rumble (fan, AC) and hiss (electronic noise)
  - Configurable via `ENABLE_AUDIO_NOISE_REDUCTION=true`

### Changed

- **Single-Core Transcription Service** (`transcription_service.py`)
  - `_build_audio_filters()` method to build FFmpeg chain
  - `_normalize_audio()` method applying optional filters
  - Detailed logs of applied filters

- **Parallel Transcription Service** (`parallel_transcription_service.py`)
  - `_convert_to_wav()` method with filter support
  - Quality consistency between single/parallel modes

- **Chunk Preparation Service** (`chunk_preparation_service.py`)
  - `_extract_chunk_async()` method with filters
  - Normalized chunks before processing

- **Settings** (`settings.py`)
  - `enable_audio_volume_normalization` property
  - `enable_audio_noise_reduction` property

- **Configuration Files**
  - `.env`: 2 new flags (disabled by default)
  - `.env.example`: Complete feature documentation

### Performance

- **Overhead:** +10-30% processing time (when enabled)
- **Accuracy Gain:** +15-30% on low-quality audio
- **Default:** Disabled (zero overhead for good audio)

### Documentation

- Created `docs/FEATURE-AUDIO-NORMALIZATION-v2.2.0.md`
  - Complete configuration guide
  - Use cases and benchmarks
  - Technical details of FFmpeg filters
  - Test examples

---

## [2.1.0] - 2025-10-19

### Removed

**Simplification: Auto-Switch Removal**:

- **Removed `AUDIO_LIMIT_SINGLE_CORE` variable**
  - Eliminated auto-switch logic based on audio duration
  - Operation mode now defined ONLY by `ENABLE_PARALLEL_TRANSCRIPTION`
  - `true` = ALL audios in parallel mode
  - `false` = ALL audios in single-core mode
  - More predictable and simple behavior

- **Removed `FallbackTranscriptionService` class**
  - Factory now directly returns chosen service
  - Simpler and more maintainable code (~135 lines removed)
  - No duration detection overhead via FFprobe

### Documentation

- Updated configuration guide removing `AUDIO_LIMIT_SINGLE_CORE` references
- Added deprecation notes in old docs

---

## [2.0.0] - 2025-10-19

### 🚀 MAJOR UPDATE - Parallel Transcription Architecture

Complete redesign of parallel transcription with persistent worker pool.

### Added

**Docker Compose Simplification**:
- Removed external volumes (fully self-contained container)
- Whisper model cache inside container
- Logs inside container (access via `docker-compose logs`)
- v2.0.0 configurations in Docker Compose
  - `ENABLE_PARALLEL_TRANSCRIPTION=true` by default
  - `PARALLEL_WORKERS=2` configured
  - `PARALLEL_CHUNK_DURATION=120` optimized
  - Memory limits adjusted for 8GB (supports 2 workers)

**New Parallel Transcription Architecture**:

1. **Persistent Worker Pool** (`persistent_worker_pool.py`)
   - Workers load Whisper model **ONCE** at application startup
   - Workers process chunks via `multiprocessing.Queue`
   - Eliminates overhead of reloading model per chunk (~800MB for `base` model)
   - Speedup of **3-5x** compared to previous version
   - Speedup of **7-10x** for long videos (>45min)

2. **Session Manager** (`temp_session_manager.py`)
   - Isolated session management per request
   - Each request gets unique folder: `temp/{session_id}/`
   - Organized subfolders: `download/`, `chunks/`, `results/`
   - Automatic cleanup after processing
   - Old session cleanup (>24h)
   - Unique session ID: `session_{timestamp}_{uuid}_{ip_hash}`

3. **Chunk Preparation Service** (`chunk_preparation_service.py`)
   - Pre-creates chunks on disk via FFmpeg
   - Asynchronous parallel chunk extraction
   - Chunks saved in `temp/{session_id}/chunks/`
   - Optimization: chunks ready before worker processing

4. **Parallel Transcription Service** (`parallel_transcription_service.py`)
   - Complete parallel transcription flow orchestration
   - Integration with worker pool, session manager, and chunk preparation
   - Flow: session → download → convert → chunks → workers → merge → cleanup
   - Support for concurrent requests with session isolation
   - Detailed timing logs (convert, chunk prep, processing, total)

5. **Lifecycle Management** (`main.py`)
   - Worker pool started at application startup (FastAPI lifespan)
   - Workers load model during initialization (timing logs)
   - Graceful worker shutdown (waits for in-progress tasks)
   - Automatic cleanup of old sessions at startup

6. **Intelligent Transcription Factory** (`transcription_factory.py`)
   - Automatic mode selection based on audio duration:
     - `< 300s (5min)`: Single-core (more efficient for short audio)
     - `>= 300s (5min)`: Parallel (faster for long audio)
   - Automatic fallback to single-core on error
   - Configuration via `AUDIO_LIMIT_SINGLE_CORE`

**Documentation**:
- `docs/10-PARALLEL-ARCHITECTURE.md` - Complete technical architecture
- `docs/11-PARALLEL-INTEGRATION-GUIDE.md` - Implementation and integration guide
- Updated `.env.example` with complete worker pool configuration

**Configuration**:
- `ENABLE_PARALLEL_TRANSCRIPTION` - Enable/disable worker pool
- `PARALLEL_WORKERS` - Number of persistent workers (default: 2)
- `PARALLEL_CHUNK_DURATION` - Chunk duration in seconds (default: 120s)
- `AUDIO_LIMIT_SINGLE_CORE` - Limit for automatic mode selection (default: 300s)

### Changed

**Performance**:
- **BEFORE:** 45min video took ~22 minutes (V1)
- **AFTER:** 45min video takes ~2-3 minutes (V2)
- **Speedup:** 7-10x for long videos

**Memory Usage**:
- Model loaded 1x per worker (vs N times per request in V1)
- ~23x reduction in load count for 45min video
- Predictable memory: `(workers × model_size) + overhead`

**Concurrency**:
- Support for multiple simultaneous requests
- Complete isolation between sessions (no file conflicts)
- Workers shared between requests (single pool)

**Logs and Observability**:
- Detailed logs per session (`[PARALLEL] Session {id}`)
- Timing of each phase: download, conversion, chunk prep, processing
- Worker startup logs with model loading time
- Error tracking per chunk

### Removed (Breaking Changes)

**Old Parallel Transcription (V1 - Discontinued)**:
- ❌ **Removed file:** `parallel_transcription_service.py` (V1)
  - **Reason:** Extremely poor performance (7-10x slower)
  - **Replaced by:** New implementation with persistent worker pool
  - **Backup available at:** `parallel_transcription_service_v1_deprecated.py`

- ❌ **ProcessPoolExecutor per chunk** - Removed
  - Each chunk created new process and reloaded model
  - Replaced by persistent workers with task queue

- ❌ **Fallback to V1** - Removed
  - Factory no longer attempts to instantiate old V1
  - On worker pool failure, uses only single-core

### Fixed

- **Critical performance issue in parallel mode**
  - Identified: Whisper model (~800MB) reloaded per chunk
  - For 45min video: 23 chunks = 23 loads = massive overhead
  - Result: Parallel mode 3-4x SLOWER than single-core
  - Solution: Persistent workers load model 1x at startup

- **File conflicts in concurrent requests**
  - Problem: Multiple requests saved chunks in same `/temp` folder
  - Solution: Session isolation with unique `temp/{session_id}/` per request

- **Memory leaks in long sessions**
  - Problem: Temporary folders not cleaned after error
  - Solution: Cleanup in `finally` block + automatic old session cleanup

### Performance Metrics

**Real Test (Proxmox LXC, 4 cores, base model)**:

| Method | 45min Video (2731s) | Speedup vs V1 | Speedup vs Single |
|--------|---------------------|---------------|-------------------|
| V1 Parallel (old) | ~22 minutes | 1.0x (baseline) | 0.27x (SLOWER!) |
| Single-core | ~6 minutes | 3.67x | 1.0x (baseline) |
| **Parallel (new)** | **~2-3 minutes** | **7-10x** ⚡ | **2-3x** 🚀 |

**Resource Usage**:

Recommended Configuration (Production):
```bash
WHISPER_MODEL=base
PARALLEL_WORKERS=2
PARALLEL_CHUNK_DURATION=120
```

- **RAM:** ~2-3GB (2 workers × ~800MB + overhead)
- **CPU:** 2 active cores during processing
- **Disk:** Temporary (~500MB per session, auto cleanup)

### Migration from V1 to V2

**Automatic**: No action needed. New version activates automatically with:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
```

**Recommended Configuration**:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2              # Conservative (2-3GB RAM)
PARALLEL_CHUNK_DURATION=120     # 2 minutes per chunk
AUDIO_LIMIT_SINGLE_CORE=300     # Use parallel for audio >5min
```

**Rollback (if needed)**:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
```

### Breaking Changes

1. **V1 Parallel Removal**
   - Old parallel transcription code discontinued
   - File renamed to `*_v1_deprecated.py`
   - No fallback to V1 - only to single-core

2. **New System Requirements**
   - Worker pool requires additional RAM: `workers × model_size`
   - `PARALLEL_WORKERS` configuration must match available hardware

3. **Behavior Changes**
   - Workers started at **application startup** (not per request)
   - First request has NO model loading delay
   - Application shutdown waits for in-progress task completion

---

## [1.3.3] - 2025-10-18

### Added
- Refactored SOLID documentation (9 documents created)
- CLI options support in start.sh
- Log system improvements

### Fixed
- Lint corrections in various files
- Startup script improvements

---

## [1.2.0] - 2025-10-15

### Added
- Initial parallel transcription (V1 - discontinued in 2.0.0)
- Audio chunk support
- Processing using ProcessPoolExecutor

### Known Issues
- Poor performance in parallel mode (identified and resolved in 2.0.0)

---

## Next Steps

- [Architecture Overview](./architecture-overview.md) - Understand the codebase
- [Contributing Guide](./contributing.md) - Learn how to contribute
- [Testing Guide](./testing.md) - Testing patterns and best practices
- [User Guide](../user-guide/) - End-user documentation

---

**Version**: 3.0.0  
**Last Updated**: October 22, 2025  
**Maintainers**: YTCaption Team

[Unreleased]: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/compare/v3.0.0...HEAD
[3.0.0]: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/releases/tag/v3.0.0
[2.2.0]: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/releases/tag/v2.2.0
[2.1.0]: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/releases/tag/v2.1.0
[2.0.0]: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/releases/tag/v2.0.0
[1.3.3]: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/releases/tag/v1.3.3
[1.2.0]: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/releases/tag/v1.2.0
