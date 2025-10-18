# 🚀 YTCaption Startup Scripts Guide

## 📋 Available Scripts

### 1. `start.sh` - Automatic Startup Script

Complete startup script with automatic hardware detection and configuration.

**Features:**
- ✅ Detects CPU cores and RAM
- ✅ Detects NVIDIA GPU and CUDA
- ✅ Validates Docker and Docker Compose installation
- ✅ Checks disk space and network connectivity
- ✅ Automatically configures `.env` based on hardware
- ✅ Updates `docker-compose.yml` with optimal resources
- ✅ Recommends best Whisper model for your hardware
- ✅ Health check after startup

**Usage:**

```bash
# Make executable
chmod +x start.sh

# Normal start (automatic configuration)
./start.sh

# Force rebuild Docker images
./start.sh --force-rebuild

# Disable GPU (use CPU only)
./start.sh --no-gpu

# Specify Whisper model
./start.sh --model medium

# Combine options
./start.sh --model tiny --no-gpu --force-rebuild

# Show help
./start.sh --help
```

**Options:**
- `--force-rebuild` - Force rebuild Docker images (useful after code changes)
- `--no-gpu` - Disable GPU even if available (use CPU only)
- `--model MODEL` - Manually set Whisper model (tiny|base|small|medium|large)
- `--help` - Show help message

**What it does:**

1. **System Detection:**
   - Detects CPU cores and threads
   - Detects total RAM
   - Detects NVIDIA GPU and CUDA
   - Checks disk space

2. **Validation:**
   - Validates Docker installation
   - Validates Docker Compose installation
   - Checks if Docker daemon is running
   - Validates network connectivity
   - Checks if port 8000 is available

3. **Configuration:**
   - Creates/updates `.env` file with optimal settings
   - Updates `docker-compose.yml` with resource limits
   - Recommends best Whisper model for your hardware

4. **Startup:**
   - Starts Docker containers
   - Waits for health check
   - Shows access URLs and commands

**Automatic Model Recommendation:**

| Hardware | Recommended Model | Reason |
|----------|------------------|--------|
| GPU + 16GB+ RAM | medium | Best quality with GPU acceleration |
| GPU + <16GB RAM | base | Balanced for GPU with limited RAM |
| CPU 8+ cores + 16GB+ | base | Good quality on powerful CPU |
| CPU <8 cores or <16GB | tiny | Speed-optimized for limited resources |

**Automatic Resource Allocation:**

| System RAM | Docker Memory Limit | Docker Memory Reserved |
|------------|-------------------|----------------------|
| 16GB+ | 8GB | 4GB |
| 8-15GB | 6GB | 3GB |
| <8GB | 4GB | 2GB |

| CPU Cores | Docker CPU Limit | Docker CPU Reserved |
|-----------|-----------------|-------------------|
| 8+ cores | 6 cores | 4 cores |
| 4-7 cores | 4 cores | 2 cores |
| <4 cores | 2 cores | 1 core |

### 2. `stop.sh` - Stop Script

Gracefully stops all YTCaption services.

**Usage:**

```bash
# Make executable
chmod +x stop.sh

# Stop services
./stop.sh
```

### 3. `status.sh` - Status and Logs Script

Shows service status and recent logs.

**Usage:**

```bash
# Make executable
chmod +x status.sh

# Show status and logs
./status.sh
```

## 📦 Installation on Proxmox/Linux

### Step 1: Upload Files

Upload all project files to your Proxmox container/VM:

```bash
# Via SCP (from your local machine)
scp -r /path/to/ytcaption user@proxmox-ip:/home/user/

# Or via git
cd /home/user
git clone https://github.com/yourusername/ytcaption.git
cd ytcaption
```

### Step 2: Make Scripts Executable

```bash
chmod +x start.sh stop.sh status.sh
```

### Step 3: Run Startup Script

```bash
./start.sh
```

The script will guide you through the entire process!

## 🔧 Manual Installation (if needed)

If you prefer manual installation or the script fails:

### Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Activate the changes
newgrp docker

# Enable Docker on boot
sudo systemctl enable docker
sudo systemctl start docker
```

### Install Docker Compose

```bash
# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Make executable
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker-compose --version
```

### Install NVIDIA Drivers (for GPU support)

```bash
# Add NVIDIA repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install nvidia-docker2
sudo apt-get update
sudo apt-get install -y nvidia-docker2

# Restart Docker
sudo systemctl restart docker

# Test GPU
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

## 🎯 Quick Start Examples

### Example 1: Start on a CPU-only server

```bash
./start.sh --no-gpu --model tiny
```

This will:
- Use CPU only (no GPU)
- Use tiny model (fastest)
- Detect RAM and CPU cores
- Configure optimal settings

### Example 2: Start with GPU acceleration

```bash
./start.sh --model medium
```

This will:
- Auto-detect GPU if available
- Use medium model (high quality)
- Configure for GPU acceleration

### Example 3: Force rebuild after code changes

```bash
./start.sh --force-rebuild
```

This will:
- Stop all containers
- Rebuild Docker images from scratch
- Start with fresh configuration

### Example 4: Development mode

```bash
# First time
./start.sh --model tiny

# After code changes
./start.sh --force-rebuild --model tiny

# Check status
./status.sh

# Stop
./stop.sh
```

## 🐛 Troubleshooting

### Port 8000 already in use

```bash
# Find what's using port 8000
sudo netstat -tulpn | grep 8000

# Or
sudo ss -tulpn | grep 8000

# Stop the service and try again
./start.sh
```

### Docker daemon not running

```bash
# Start Docker
sudo systemctl start docker

# Enable on boot
sudo systemctl enable docker

# Check status
sudo systemctl status docker
```

### Permission denied errors

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Logout and login again, or:
newgrp docker

# Try again
./start.sh
```

### GPU not detected

```bash
# Check if NVIDIA drivers are installed
nvidia-smi

# Check if nvidia-docker is installed
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# If not working, install nvidia-docker2
sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

### Insufficient memory

The script will warn you if RAM is low. Solutions:

```bash
# Use a lighter model
./start.sh --model tiny

# Or manually edit docker-compose.yml to reduce memory limits
# Then start normally
./start.sh
```

## 📊 Resource Requirements

### Minimum Requirements

- **CPU:** 2 cores
- **RAM:** 4GB
- **Disk:** 10GB free space
- **Network:** Internet connection for Docker images

### Recommended Requirements

- **CPU:** 4+ cores
- **RAM:** 8GB+
- **Disk:** 20GB+ free space
- **GPU:** NVIDIA GPU with CUDA support (optional but highly recommended)

### Optimal Requirements

- **CPU:** 8+ cores
- **RAM:** 16GB+
- **Disk:** 50GB+ free space
- **GPU:** NVIDIA GPU with 6GB+ VRAM

## 🔄 Common Commands

```bash
# Start
./start.sh

# Stop
./stop.sh

# Status and logs
./status.sh

# Follow logs in real-time
docker-compose logs -f

# Restart
./stop.sh && ./start.sh

# Rebuild and restart
./start.sh --force-rebuild

# Update configuration
nano .env
./stop.sh
./start.sh
```

## 🎓 Advanced Usage

### Custom Configuration

Edit `.env` before starting:

```bash
nano .env
./start.sh
```

### Custom Docker Compose

Edit `docker-compose.yml` for advanced settings:

```bash
nano docker-compose.yml
./start.sh --force-rebuild
```

### Run on Different Port

Edit `.env`:

```bash
PORT=9000
```

Then restart:

```bash
./stop.sh
./start.sh
```

### Enable GPU in Docker Compose

The start script does this automatically, but you can manually add to `docker-compose.yml`:

```yaml
services:
  whisper-api:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

## 📝 Logs

Logs are stored in:
- Container logs: `docker-compose logs`
- Application logs: `./logs/app.log`
- Backup .env files: `.env.backup.YYYYMMDD_HHMMSS`

## 🆘 Getting Help

If you encounter issues:

1. Check logs: `./status.sh`
2. Check Docker status: `docker ps`
3. Check system resources: `htop` or `top`
4. Run script with verbose output: `bash -x ./start.sh`
5. Open an issue on GitHub with logs and error messages

## ✅ Validation Checklist

The start script validates:

- [x] Root user warning
- [x] CPU cores detection
- [x] RAM detection
- [x] GPU detection
- [x] CUDA detection
- [x] Docker installation
- [x] Docker daemon running
- [x] Docker Compose installation
- [x] Disk space (minimum 10GB)
- [x] Network connectivity
- [x] Docker Hub accessibility
- [x] Port 8000 availability
- [x] .env.example file exists
- [x] docker-compose.yml exists

If all checks pass ✅, the service will start successfully!
