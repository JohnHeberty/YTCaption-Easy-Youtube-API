# 🔧 Installation Guide

Complete installation guide for Docker, local development, and production servers.

---

## Table of Contents

- [Docker Installation (Recommended)](#docker-installation-recommended)
- [Local Installation (Development)](#local-installation-development)
- [Production Server (Proxmox/Linux)](#production-server-proxmoxlinux)
- [GPU Support (NVIDIA CUDA)](#gpu-support-nvidia-cuda)
- [Monitoring Stack](#monitoring-stack)
- [Updating](#updating)
- [Uninstallation](#uninstallation)
- [Verification](#verification)

---

## 🐳 Docker Installation (Recommended)

### Prerequisites

- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **RAM**: Minimum 2GB (4GB recommended)
- **Storage**: 10GB free space
- **Network**: Internet connection for model downloads

### Installation Steps

#### 1. Clone Repository

```bash
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
```

#### 2. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit with your preferred editor
nano .env  # or vim, code, etc.
```

**Essential variables:**
```bash
# Whisper Model (tiny, base, small, medium, large)
WHISPER_MODEL=base

# API Workers
WORKERS=1

# YouTube Resilience v3.0
ENABLE_TOR_PROXY=false
ENABLE_MULTI_STRATEGY=true
YOUTUBE_MAX_RETRIES=5

# Parallel Transcription v2.0
ENABLE_PARALLEL_TRANSCRIPTION=false
PARALLEL_WORKERS=2
```

#### 3. Build and Start

```bash
# Start all services (API + Monitoring + Tor)
docker-compose up -d

# View logs
docker-compose logs -f whisper-api
```

#### 4. Wait for Services

**Whisper API** (120s startup for model loading):
```bash
# Monitor startup
docker-compose logs -f whisper-api | grep "Application startup complete"
```

**Tor Proxy** (30-60s for circuit establishment):
```bash
# Check Tor bootstrap
docker-compose logs tor-proxy | grep "Bootstrapped 100%"

# Expected: "Bootstrapped 100% (done): Done"
```

**Prometheus & Grafana** (15-30s):
```bash
# Check all services
docker-compose ps
```

#### 5. Verify Installation

```bash
# Health check
curl http://localhost:8000/health/ready

# Expected response:
# {"status":"ready","whisper_model":"base","tor_available":true}
```

**Test Tor proxy (if enabled):**
```bash
# Inside container
docker-compose exec whisper-api curl --socks5-hostname tor-proxy:9050 https://check.torproject.org/api/ip

# Expected: Tor exit node IP
```

#### 6. Access Services

- **API Documentation**: http://localhost:8000/docs
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/whisper2024)

---

## 💻 Local Installation (Development)

### Prerequisites

- **Python**: 3.11+
- **FFmpeg**: Latest version
- **Git**: Latest version
- **RAM**: Minimum 4GB
- **Storage**: 15GB free space

### Installation Steps

#### 1. Clone Repository

```bash
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
```

#### 2. Create Virtual Environment

```bash
# Create venv
python -m venv venv

# Activate venv
# Linux/macOS:
source venv/bin/activate

# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Windows CMD:
.\venv\Scripts\activate.bat
```

#### 3. Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```

**Dependencies installed:**
- FastAPI 0.115.0 (API framework)
- openai-whisper (transcription)
- yt-dlp 2025.10.14 (YouTube download)
- torch 2.3.1 + torchaudio (ML models)
- prometheus-client 0.21.0 (metrics)
- circuitbreaker 2.0.0 (resilience)
- fake-useragent 1.5.1 (anti-ban)
- aiolimiter 1.1.0 (rate limiting)

#### 4. Install FFmpeg

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Linux (CentOS/RHEL/Fedora):**
```bash
sudo dnf install ffmpeg  # Fedora
sudo yum install ffmpeg  # CentOS/RHEL (need EPEL)
```

**macOS:**
```bash
# Using Homebrew
brew install ffmpeg
```

**Windows:**
```powershell
# Using Chocolatey
choco install ffmpeg

# Or download from: https://ffmpeg.org/download.html
# Add to PATH manually
```

**Verify installation:**
```bash
ffmpeg -version
# Expected: ffmpeg version N-... (with libav*, libswscale, etc.)
```

#### 5. Configure Environment

```bash
cp .env.example .env
nano .env
```

**For local development:**
```bash
# Use smaller model for faster startup
WHISPER_MODEL=tiny

# Single worker for easier debugging
WORKERS=1

# Disable parallel for simpler testing
ENABLE_PARALLEL_TRANSCRIPTION=false

# Optional: Enable debug logging
LOG_LEVEL=DEBUG
```

#### 6. Start Development Server

```bash
# With auto-reload (recommended for development)
python -m uvicorn src.presentation.api.main:app --reload --host 0.0.0.0 --port 8000

# Or using environment variables
uvicorn src.presentation.api.main:app --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Loading Whisper model: tiny
INFO:     Application startup complete.
```

#### 7. Access API

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## 🖥️ Production Server (Proxmox/Linux)

### Method 1: Automated Script (Recommended)

The `start.sh` script automates hardware detection, Docker installation, and configuration.

#### Basic Usage

```bash
# 1. Clone repository
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API

# 2. Make executable
chmod +x scripts/start.sh

# 3. Run script (will guide you through setup)
./scripts/start.sh
```

**What the script does:**
- ✅ Detects CPU cores, RAM, GPU availability
- ✅ Installs Docker/Docker Compose if missing
- ✅ Configures `.env` based on hardware
- ✅ Recommends optimal Whisper model
- ✅ Starts all services with health checks
- ✅ Displays access URLs and next steps

#### Advanced Options

```bash
# View all options
./scripts/start.sh --help

# Specify Whisper model
./scripts/start.sh --model small

# Set API workers
./scripts/start.sh --workers 2

# Enable parallel transcription with 4 workers
./scripts/start.sh --parallel-workers 4

# Force CPU mode (disable GPU)
./scripts/start.sh --no-gpu

# Force rebuild Docker images
./scripts/start.sh --force-rebuild

# Combined options
./scripts/start.sh --model base --workers 2 --parallel-workers 4
```

#### Example Hardware Configurations

**Low-End Server (2 cores, 4GB RAM):**
```bash
./scripts/start.sh --model tiny --workers 1 --no-gpu
```

**Mid-Range Server (4 cores, 8GB RAM):**
```bash
./scripts/start.sh --model base --workers 2 --parallel-workers 2
```

**High-End Server (8+ cores, 16GB+ RAM, GPU):**
```bash
./scripts/start.sh --model medium --workers 4 --parallel-workers 4
```

### Method 2: Manual Installation

#### 1. Install Docker

```bash
# Official installation script
curl -fsSL https://get.docker.com | sh

# Add user to docker group
sudo usermod -aG docker $USER

# Apply group changes
newgrp docker

# Verify installation
docker --version
```

#### 2. Install Docker Compose

```bash
# Download latest version
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Make executable
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker-compose --version
```

#### 3. Clone and Configure

```bash
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
cp .env.example .env
nano .env
```

#### 4. Adjust Resource Limits

Edit `docker-compose.yml` to match your hardware:

```yaml
services:
  whisper-api:
    deploy:
      resources:
        limits:
          cpus: '4'        # Adjust to your CPU cores
          memory: 8G       # Adjust to your RAM
        reservations:
          memory: 4G
```

#### 5. Start Services

```bash
# Build and start
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

---

## 🎮 GPU Support (NVIDIA CUDA)

Enable GPU acceleration for faster Whisper transcription.

### Prerequisites

- **GPU**: NVIDIA GPU with CUDA Compute Capability 3.5+
- **Driver**: NVIDIA driver 450.80.02+ (Linux) or 452.39+ (Windows)
- **CUDA**: Compatible version (installed via NVIDIA Container Toolkit)

### Installation Steps

#### 1. Install NVIDIA Container Toolkit (Linux)

```bash
# Setup package repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
   && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
   && curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
         sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
         sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install toolkit
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker daemon
sudo nvidia-ctk runtime configure --runtime=docker

# Restart Docker
sudo systemctl restart docker

# Verify installation
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

**Expected output:**
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 525.xx.xx    Driver Version: 525.xx.xx    CUDA Version: 11.8   |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA GTX 1050 Ti  Off  | 00000000:01:00.0 Off |                  N/A |
| 30%   45C    P0    N/A /  75W |      0MiB /  4096MiB |      0%      Default |
+-------------------------------+----------------------+----------------------+
```

#### 2. Configure Docker Compose for GPU

Edit `docker-compose.yml`:

```yaml
services:
  whisper-api:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1  # or 'all' for all GPUs
              capabilities: [gpu]
```

#### 3. Configure Environment for GPU

Edit `.env`:

```bash
# Enable GPU
WHISPER_DEVICE=cuda

# Use larger model (GPU can handle it)
WHISPER_MODEL=medium

# Or for best quality (requires 8GB+ VRAM)
WHISPER_MODEL=large-v2
```

#### 4. Start with GPU

```bash
# Rebuild and start
docker-compose down
docker-compose up -d --build

# Verify GPU usage
docker-compose exec whisper-api nvidia-smi

# Check logs for CUDA initialization
docker-compose logs whisper-api | grep -i cuda
```

**Expected log output:**
```
INFO: CUDA available: True
INFO: CUDA device: NVIDIA GTX 1050 Ti
INFO: Loading Whisper model 'medium' on device 'cuda'
```

### GPU Troubleshooting

**GPU not detected:**
```bash
# Check NVIDIA driver
nvidia-smi

# Check Docker runtime
docker info | grep -i nvidia

# Recreate container
docker-compose down && docker-compose up -d
```

**Out of memory errors:**
- Reduce `WHISPER_MODEL` (medium → base → small → tiny)
- Disable parallel transcription: `ENABLE_PARALLEL_TRANSCRIPTION=false`
- Reduce `PARALLEL_WORKERS`

---

## 📊 Monitoring Stack

### Components

The Docker Compose setup includes:

1. **Prometheus** (port 9090) - Metrics collection
2. **Grafana** (port 3000) - Visualization dashboards
3. **Tor Proxy** (ports 8118/9050) - Optional anonymization

### Enable Monitoring

**In `.env`:**
```bash
# Monitoring is enabled by default in docker-compose.yml
# No additional configuration needed
```

**Access dashboards:**
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
  - **Username**: admin
  - **Password**: whisper2024

### Configure Grafana

1. Login to Grafana (http://localhost:3000)
2. Datasource is pre-configured (Prometheus at http://prometheus:9090)
3. Dashboards are auto-provisioned from `monitoring/grafana/dashboards/`

**Available dashboards:**
- YouTube Resilience v3.0 Metrics
- Whisper Transcription Performance
- API Performance & Health

### Disable Monitoring (Optional)

Edit `docker-compose.yml` and comment out:
```yaml
# services:
#   prometheus:
#     ...
#   grafana:
#     ...
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

---

## 🔄 Updating

### Docker Installation

```bash
cd YTCaption-Easy-Youtube-API

# Pull latest code
git pull origin main

# Rebuild and restart (preserves volumes)
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check logs
docker-compose logs -f whisper-api
```

### Local Installation

```bash
cd YTCaption-Easy-Youtube-API

# Pull latest code
git pull origin main

# Activate venv
source venv/bin/activate  # Linux/macOS
# or .\venv\Scripts\Activate.ps1  # Windows

# Update dependencies
pip install -r requirements.txt --upgrade

# Restart server
# CTRL+C to stop, then:
uvicorn src.presentation.api.main:app --reload
```

---

## 🗑️ Uninstallation

### Docker

```bash
cd YTCaption-Easy-Youtube-API

# Stop and remove containers, networks, volumes
docker-compose down -v

# Remove images (optional)
docker rmi $(docker images | grep whisper | awk '{print $3}')

# Remove directory
cd ..
rm -rf YTCaption-Easy-Youtube-API
```

### Local

```bash
cd YTCaption-Easy-Youtube-API

# Deactivate virtual environment
deactivate

# Remove directory
cd ..
rm -rf YTCaption-Easy-Youtube-API
```

---

## ✅ Verification

### 1. Health Check

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "whisper_model": "base",
  "version": "3.0.0"
}
```

### 2. Ready Check (Full Initialization)

```bash
curl http://localhost:8000/health/ready
```

**Expected response:**
```json
{
  "status": "ready",
  "whisper_model": "base",
  "tor_available": true,
  "circuit_breaker_state": "closed",
  "cache_size": 0
}
```

### 3. API Version

```bash
curl http://localhost:8000/api/v1/
```

**Expected response:**
```json
{
  "message": "YTCaption API",
  "version": "3.0.0",
  "features": ["youtube_resilience", "parallel_transcription", "monitoring"]
}
```

### 4. Test Transcription

**Using YouTube transcript (fast):**
```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "use_youtube_transcript": true
  }'
```

**Using Whisper (slower but supports all videos):**
```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "use_youtube_transcript": false
  }'
```

### 5. Metrics Endpoint

```bash
curl http://localhost:8000/metrics
```

**Expected output:**
```
# HELP youtube_download_attempts_total Total YouTube download attempts
# TYPE youtube_download_attempts_total counter
youtube_download_attempts_total{strategy="yt-dlp-default"} 1.0
...
```

### 6. Monitoring Dashboards

- **Prometheus**: http://localhost:9090/targets (all targets should be "UP")
- **Grafana**: http://localhost:3000 (dashboards should load data)

---

## 🆘 Troubleshooting

If you encounter issues during installation:

1. **Check logs**: `docker-compose logs -f` or console output
2. **Verify prerequisites**: Docker version, Python version, FFmpeg
3. **Check ports**: Ensure 8000, 9090, 3000 are not in use
4. **Consult documentation**: [Troubleshooting Guide](./05-troubleshooting.md)
5. **Common issues**: [Configuration Guide](./03-configuration.md)

---

## 📚 Next Steps

- **[Configuration](./03-configuration.md)** - Configure environment variables
- **[API Usage](./04-api-usage.md)** - Learn how to use the API
- **[Quick Start](./01-quick-start.md)** - 5-minute getting started guide

---

**Version**: 3.0.0  
**Last Updated**: October 2025  
**Contributors**: YTCaption Team

[← Back to User Guide](./README.md)
