# 🔧 Troubleshooting Guide

Complete guide to solving common problems with diagnosis and solutions.

---

## 📋 Table of Contents

1. [Installation Errors](#installation-errors)
2. [Docker Errors](#docker-errors)
3. [Memory Errors (OOM)](#memory-errors-oom)
4. [YouTube Download Errors (v3.0)](#youtube-download-errors-v30)
5. [Transcription Errors](#transcription-errors)
6. [FFmpeg Errors](#ffmpeg-errors)
7. [API Errors](#api-errors)
8. [Performance Issues](#performance-issues)
9. [Monitoring (Prometheus/Grafana)](#monitoring-prometheusgrafana)

---

## Installation Errors

### ❌ Docker not found

**Error:**
```
docker: command not found
```

**Cause**: Docker is not installed.

**Solution:**
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Verify
docker --version
```

---

### ❌ Docker Compose not found

**Error:**
```
docker-compose: command not found
```

**Solution:**
```bash
# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify
docker-compose --version
```

---

### ❌ Permission denied (Docker)

**Error:**
```
permission denied while trying to connect to the Docker daemon socket
```

**Cause**: User not in `docker` group.

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Or use sudo
sudo docker-compose up -d
```

---

### ❌ Port 8000 already in use

**Error:**
```
Error starting userland proxy: listen tcp 0.0.0.0:8000: bind: address already in use
```

**Cause**: Another application is using port 8000.

**Solution 1 - Change port:**
```bash
# Edit .env
PORT=8001

# Edit docker-compose.yml
ports:
  - "8001:8001"

# Restart
docker-compose down
docker-compose up -d
```

**Solution 2 - Kill process:**
```bash
# Linux
sudo lsof -i :8000
sudo kill -9 <PID>

# Windows PowerShell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
```

---

## Docker Errors

### ❌ Container won't start

**Error:**
```
Container ytcaption exited with code 1
```

**Diagnosis:**
```bash
docker-compose logs whisper-api
```

**Common solutions:**

1. **Missing `.env` file:**
```bash
cp .env.example .env
nano .env  # Edit configuration
```

2. **Invalid `.env` syntax:**
```bash
# Correct: WHISPER_MODEL=base
# Wrong: WHISPER_MODEL = base (spaces)
```

3. **Rebuild containers:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

### ❌ Container keeps restarting

**Error:**
```
Restarting (1) X seconds ago
```

**Cause**: Fatal error during initialization.

**Diagnosis:**
```bash
docker-compose logs --tail=50 whisper-api
```

**Solutions:**

1. **Check RAM:**
```bash
free -h
# If RAM < 4GB, use smaller model
WHISPER_MODEL=tiny
```

2. **Check disk space:**
```bash
df -h
# If disk full, clean temp files
docker-compose exec whisper-api rm -rf /app/temp/*
```

3. **Check model download:**
```bash
# Model might be downloading (can take 5-10 minutes first time)
docker-compose logs -f whisper-api | grep "Loading"
```

---

### ❌ Build fails

**Error:**
```
ERROR [internal] load metadata for docker.io/library/python:3.11-slim
```

**Cause**: Network issue or Docker Hub connection problem.

**Solution:**
```bash
# Clear Docker cache
docker builder prune -a

# Retry build
docker-compose build --no-cache
```

---

## Memory Errors (OOM)

### ❌ Out of Memory (OOM Killed)

**Error:**
```
Killed
```

or

```
Subprocess killed (likely OOM - Out of Memory)
```

**Cause**: Not enough RAM for model + transcription.

**Diagnosis:**
```bash
# Check RAM usage
docker stats

# Check logs
docker-compose logs whisper-api | grep -i "kill\|memory\|oom"
```

**Solutions:**

**1. Use smaller model:**
```bash
# In .env
WHISPER_MODEL=tiny  # or base (instead of medium/large)
```

**2. Reduce concurrent requests:**
```bash
MAX_CONCURRENT_REQUESTS=1
```

**3. Disable parallel transcription:**
```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
```

**4. Increase Docker RAM limit:**
```yaml
# In docker-compose.yml
services:
  whisper-api:
    deploy:
      resources:
        limits:
          memory: 8G  # Increase from 4G
```

**5. Add swap memory (Linux):**
```bash
# Create 4GB swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Verify
free -h
```

---

## YouTube Download Errors (v3.0)

### 🆕 ❌ HTTP 403 Forbidden

**Error:**
```
VideoDownloadError: HTTP Error 403: Forbidden
```

or

```
YouTube download failed: HTTP 403
```

**Cause**: YouTube is blocking the download (most common issue).

**Why it happens:**
- IP-based rate limiting
- Geographic restrictions
- YouTube anti-bot detection
- Too many requests from same IP

**Solutions (try in order):**

**1. Enable Tor Proxy (recommended, FREE):**
```bash
# In .env
ENABLE_TOR_PROXY=true
TOR_PROXY_URL=socks5://tor-proxy:9050

# Restart
docker-compose down
docker-compose up -d

# Wait for Tor to bootstrap (30-60s)
docker-compose logs tor-proxy | grep "Bootstrapped 100%"

# Test
curl http://localhost:8000/health/ready
```

**2. Enable multi-strategy (should already be enabled):**
```bash
ENABLE_MULTI_STRATEGY=true
ENABLE_USER_AGENT_ROTATION=true
```

**3. Reduce YouTube request rate:**
```bash
YOUTUBE_REQUESTS_PER_MINUTE=5  # Down from 10
YOUTUBE_REQUESTS_PER_HOUR=100  # Down from 200
```

**4. Increase retry attempts:**
```bash
YOUTUBE_MAX_RETRIES=7  # Up from 5
YOUTUBE_RETRY_DELAY_MAX=300  # Up from 120
```

**5. Check DNS configuration:**
```yaml
# In docker-compose.yml
services:
  whisper-api:
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
```

**6. Use external proxy (paid):**
```bash
# If Tor doesn't work, use commercial proxy
TOR_PROXY_URL=http://your-proxy:port
```

---

### 🆕 ❌ Network unreachable

**Error:**
```
NetworkError: [Errno 101] Network unreachable
```

or

```
Failed to download: Network is unreachable
```

**Cause**: DNS resolution failure or network connectivity issue.

**Diagnosis:**
```bash
# Test DNS from container
docker-compose exec whisper-api ping -c 3 youtube.com

# Test DNS resolution
docker-compose exec whisper-api nslookup youtube.com

# Test Tor connection (if enabled)
docker-compose exec whisper-api curl --socks5 tor-proxy:9050 https://check.torproject.org
```

**Solutions:**

**1. Fix DNS in docker-compose.yml:**
```yaml
services:
  whisper-api:
    dns:
      - 8.8.8.8  # Google DNS
      - 8.8.4.4
      - 1.1.1.1  # Cloudflare DNS
```

**2. Restart containers:**
```bash
docker-compose down
docker-compose up -d
```

**3. Check internet connection:**
```bash
# From host
ping youtube.com
```

**4. Enable Tor (bypass network restrictions):**
```bash
ENABLE_TOR_PROXY=true
```

---

### 🆕 ❌ All download strategies failed

**Error:**
```
VideoDownloadError: All 7 download strategies failed
```

or

```
Failed to download after trying all strategies
```

**Cause**: YouTube blocking all download methods.

**Diagnosis:**
```bash
# Check logs for detailed strategy failures
docker-compose logs whisper-api | grep -A 5 "Trying strategy"

# Example output:
# 🎯 Trying strategy: android_client (priority 1)
# ⚠️  Strategy 'android_client' failed: HTTP Error 403
# 🎯 Trying strategy: ios_client (priority 3)
# ⚠️  Strategy 'ios_client' failed: HTTP Error 403
```

**Solutions:**

**1. Enable Tor immediately:**
```bash
ENABLE_TOR_PROXY=true
```

**2. Wait and retry (rate limiting):**
```bash
# Wait 5-10 minutes
# YouTube may have rate limited your IP
```

**3. Check if video is region-locked:**
```bash
# Try from browser first
# If works in browser but not API, use Tor
```

**4. Verify yt-dlp is updated:**
```bash
# Update container (includes latest yt-dlp)
git pull
docker-compose build --no-cache
docker-compose up -d
```

---

### 🆕 ❌ Circuit Breaker is open

**Error:**
```
ServiceTemporarilyUnavailable: Circuit breaker 'youtube_download' is open
```

**Cause**: Too many consecutive failures triggered circuit breaker protection.

**What is Circuit Breaker?**
- After 8 consecutive failures (default), circuit "opens"
- Prevents cascading failures
- Auto-recovery after 180 seconds (default)

**Diagnosis:**
```bash
# Check circuit breaker status
curl http://localhost:8000/health/ready

# Check Grafana dashboard
# http://localhost:3000 → YouTube Resilience v3.0
```

**Solutions:**

**1. Wait for auto-recovery (3 minutes):**
```bash
# Circuit will automatically attempt recovery after YOUTUBE_CIRCUIT_BREAKER_TIMEOUT
# Default: 180 seconds
```

**2. Enable Tor to prevent future failures:**
```bash
ENABLE_TOR_PROXY=true

# Restart to reset circuit breaker
docker-compose restart whisper-api
```

**3. Adjust circuit breaker settings:**
```bash
# Make circuit breaker less sensitive
YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=15  # Up from 8
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=300  # Up from 180
```

**4. Restart service (immediate reset):**
```bash
docker-compose restart whisper-api
```

---

### 🆕 ❌ Tor proxy not working

**Error:**
```
Failed to connect to Tor proxy
```

or

```
[Errno 111] Connection refused (tor-proxy:9050)
```

**Diagnosis:**
```bash
# Check if Tor container is running
docker-compose ps tor-proxy

# Check Tor logs
docker-compose logs tor-proxy

# Test Tor connection
docker-compose exec whisper-api curl --socks5 tor-proxy:9050 https://check.torproject.org
```

**Solutions:**

**1. Wait for Tor to bootstrap:**
```bash
# Tor takes 30-60 seconds to establish circuit
docker-compose logs tor-proxy | grep "Bootstrapped"

# Expected output:
# Bootstrapped 100% (done): Done
```

**2. Restart Tor container:**
```bash
docker-compose restart tor-proxy

# Wait 60 seconds
sleep 60
```

**3. Check Tor configuration:**
```yaml
# In docker-compose.yml
tor-proxy:
  image: dperson/torproxy
  ports:
    - "9050:9050"  # SOCKS5
  environment:
    - TOR_MaxCircuitDirtiness=60
    - TOR_NewCircuitPeriod=30
```

**4. Use external Tor:**
```bash
# If container Tor doesn't work
# Install Tor on host
sudo apt install tor

# Use host Tor
TOR_PROXY_URL=socks5://host.docker.internal:9050
```

---

### 🆕 ❌ Rate limit exceeded

**Error:**
```
RateLimitExceeded: YouTube rate limit exceeded (10 requests/minute)
```

**Cause**: Too many YouTube requests in short time.

**Solutions:**

**1. Reduce request rate:**
```bash
YOUTUBE_REQUESTS_PER_MINUTE=5  # Down from 10
YOUTUBE_REQUESTS_PER_HOUR=100  # Down from 200
```

**2. Wait for rate limit window to reset:**
```bash
# Wait 60 seconds for per-minute limit
# Wait 1 hour for per-hour limit
```

**3. Enable Tor (new IP):**
```bash
ENABLE_TOR_PROXY=true
# Tor rotates IP every 30-60 seconds
```

---

## Transcription Errors

### ❌ Transcription failed

**Error:**
```
TranscriptionError: Whisper transcription failed
```

**Common causes and solutions:**

**1. Audio file corrupted:**
```bash
# Solution: Retry with different format
YOUTUBE_FORMAT=bestaudio  # Instead of worstaudio
```

**2. Model not loaded:**
```bash
# Check logs
docker-compose logs whisper-api | grep "Loading model"

# Solution: Wait for model to load (first run takes 2-5 minutes)
```

**3. Out of memory:**
```bash
# Solution: Use smaller model
WHISPER_MODEL=tiny
```

**4. Invalid audio format:**
```bash
# Solution: Check FFmpeg logs
docker-compose logs whisper-api | grep -i "ffmpeg\|audio"
```

---

## FFmpeg Errors

### ❌ FFmpeg not found

**Error:**
```
FFmpegError: ffmpeg not found in PATH
```

**Solution:**
```bash
# In Docker (shouldn't happen, but if it does):
docker-compose exec whisper-api apt-get update && apt-get install -y ffmpeg

# Verify
docker-compose exec whisper-api ffmpeg -version
```

---

### ❌ Audio conversion failed

**Error:**
```
FFmpegError: Failed to convert audio
```

**Diagnosis:**
```bash
# Check FFmpeg capabilities
curl http://localhost:8000/metrics | jq '.ffmpeg'
```

**Solution:**
```bash
# Try different audio format
YOUTUBE_FORMAT=bestaudio

# Disable audio processing
ENABLE_AUDIO_VOLUME_NORMALIZATION=false
ENABLE_AUDIO_NOISE_REDUCTION=false
```

---

## API Errors

### ❌ API not responding

**Error:**
```
curl: (7) Failed to connect to localhost port 8000: Connection refused
```

**Diagnosis:**
```bash
# Check if container is running
docker-compose ps

# Check logs
docker-compose logs whisper-api

# Check port binding
docker-compose port whisper-api 8000
```

**Solutions:**

**1. Container not running:**
```bash
docker-compose up -d
```

**2. Still initializing:**
```bash
# Wait for "Application startup complete"
docker-compose logs -f whisper-api
```

**3. Port conflict:**
```bash
# Change port in .env and docker-compose.yml
PORT=8001
```

---

### ❌ Request timeout

**Error:**
```
504 Gateway Timeout
```

**Cause**: Transcription took longer than REQUEST_TIMEOUT.

**Solution:**
```bash
# Increase timeout (in .env)
REQUEST_TIMEOUT=7200  # 2 hours

# Or use faster method
# In request body:
"use_youtube_transcript": true
```

---

## Performance Issues

### ⚠️ Slow transcription

**Issue**: Transcription takes too long.

**Diagnosis:**
```bash
# Check processing time in response
curl -X POST http://localhost:8000/api/v1/transcribe \
  -d '{"youtube_url":"..."}' \
  | jq '.processing_time'

# Check CPU usage
docker stats
```

**Solutions:**

**1. Use smaller model:**
```bash
WHISPER_MODEL=tiny  # Fastest
```

**2. Enable parallel transcription:**
```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4
```

**3. Use GPU (if available):**
```bash
WHISPER_DEVICE=cuda
```

**4. Use YouTube transcript (fastest):**
```json
{
  "youtube_url": "...",
  "use_youtube_transcript": true
}
```

---

### ⚠️ High memory usage

**Issue**: Container using too much RAM.

**Diagnosis:**
```bash
docker stats whisper-api
```

**Solutions:**

**1. Reduce concurrent requests:**
```bash
MAX_CONCURRENT_REQUESTS=1
```

**2. Disable parallel:**
```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
```

**3. Use smaller model:**
```bash
WHISPER_MODEL=base  # or tiny
```

**4. Enable periodic cleanup:**
```bash
ENABLE_PERIODIC_CLEANUP=true
CLEANUP_INTERVAL_MINUTES=15
```

---

## Monitoring (Prometheus/Grafana)

### ❌ Prometheus not collecting metrics

**Issue**: Prometheus not showing data.

**Diagnosis:**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check if metrics endpoint works
curl http://localhost:8000/metrics
```

**Solutions:**

**1. Check Prometheus config:**
```bash
cat monitoring/prometheus.yml
# Verify whisper-api target exists
```

**2. Restart Prometheus:**
```bash
docker-compose restart prometheus
```

---

### ❌ Grafana dashboards empty

**Issue**: Grafana dashboards show no data.

**Diagnosis:**
```bash
# Check Grafana datasource
# Navigate to: http://localhost:3000/datasources

# Test Prometheus connection
curl http://prometheus:9090/api/v1/query?query=up
```

**Solutions:**

**1. Re-import dashboards:**
```bash
# Dashboards in: monitoring/grafana/dashboards/
# Import via Grafana UI
```

**2. Check datasource URL:**
```
# Should be: http://prometheus:9090
# NOT: http://localhost:9090
```

**3. Restart Grafana:**
```bash
docker-compose restart grafana
```

---

## 🆘 Still Having Issues?

If you're still experiencing problems:

1. **Check logs:**
```bash
docker-compose logs whisper-api --tail=100
```

2. **Check system resources:**
```bash
docker stats
free -h
df -h
```

3. **Enable debug logging:**
```bash
LOG_LEVEL=DEBUG
docker-compose restart whisper-api
```

4. **Get detailed health status:**
```bash
curl http://localhost:8000/health/ready | jq
```

5. **Check YouTube Resilience metrics (v3.0):**
```bash
# View Grafana dashboard
http://localhost:3000

# Or check Prometheus directly
curl http://localhost:8000/metrics | grep youtube
```

6. **Report issue:**
- Include logs (`docker-compose logs whisper-api`)
- Include config (`.env` without sensitive data)
- Include error message
- Include system info (RAM, CPU, OS)
- Open issue on GitHub

---

## 📚 Next Steps

- **[Configuration Guide](./03-configuration.md)** - Adjust settings
- **[Deployment Guide](./06-deployment.md)** - Production setup
- **[Monitoring Guide](./07-monitoring.md)** - Setup monitoring

---

**Version**: 3.0.0  
**Last Updated**: October 2025  
**Contributors**: YTCaption Team

[← Back to User Guide](./README.md)
