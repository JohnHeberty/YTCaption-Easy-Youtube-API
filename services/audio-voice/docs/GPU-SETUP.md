# GPU Setup Guide - Sprint 1

**Objetivo:** Configurar ambiente GPU para RVC + XTTS  
**CUDA Version:** 12.1  
**Minimum GPU:** NVIDIA RTX 2000+ / Tesla T4+ (Compute Capability ≥7.0)  
**Minimum VRAM:** 12GB (16GB+ recommended)

---

## 📋 Prerequisites

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA RTX 2060 (12GB) | NVIDIA RTX 4090 (24GB) |
| VRAM | 12GB | 16GB+ |
| RAM | 32GB | 64GB |
| Storage | 100GB free | 250GB+ free |
| Compute Capability | ≥7.0 | ≥8.0 |

**Compatible GPUs:**
- ✅ RTX 2000 series (2060 12GB, 2070, 2080, 2080 Ti)
- ✅ RTX 3000 series (3060 12GB, 3070, 3080, 3090)
- ✅ RTX 4000 series (4060 Ti 16GB, 4070, 4080, 4090)
- ✅ Tesla T4, V100, A100, A10
- ✅ Quadro RTX series

**Incompatible GPUs:**
- ❌ GTX 1000 series (too old, Compute Cap <7.0)
- ❌ GTX 900 series and below
- ❌ Any GPU with <12GB VRAM

---

## 🔧 Installation Steps

### 1. Install NVIDIA Drivers

#### Ubuntu/Debian

```bash
# Check if driver is already installed
nvidia-smi

# If not, install latest driver (≥470.xx)
sudo apt-get update
sudo apt-get install -y nvidia-driver-535  # ou superior

# Reboot
sudo reboot

# Verify
nvidia-smi
```

Expected output:
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 535.xx.xx    Driver Version: 535.xx.xx    CUDA Version: 12.2  |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA GeForce ...  Off  | 00000000:01:00.0  On |                  N/A |
|  0%   45C    P8    15W / 350W |   1024MiB / 24576MiB |      0%      Default |
+-------------------------------+----------------------+----------------------+
```

#### Verify Compute Capability

```bash
nvidia-smi --query-gpu=compute_cap --format=csv,noheader
```

Should return `7.0` or higher (e.g., `7.5`, `8.0`, `8.6`, `8.9`).

---

### 2. Install Docker

```bash
# Remove old versions
sudo apt-get remove docker docker-engine docker.io containerd runc

# Install dependencies
sudo apt-get update
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verify
docker --version
docker compose version
```

Expected output:
```
Docker version 24.0.x, build xxx
Docker Compose version v2.20.x
```

---

### 3. Install NVIDIA Container Toolkit

```bash
# Configure repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | \
    sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install nvidia-docker2
sudo apt-get update
sudo apt-get install -y nvidia-docker2

# Restart Docker
sudo systemctl restart docker

# Verify
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

**Expected:** Should show same output as `nvidia-smi` on host.

---

### 4. Configure Docker for Non-Root User (Optional)

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Re-login or refresh groups
newgrp docker

# Verify
docker run hello-world
```

---

## ✅ Validation

Run automated validation script:

```bash
cd /path/to/services/audio-voice
./scripts/validate-gpu.sh
```

**Expected output:**
```
==================================================
  GPU Validation Script - Sprint 1
  Audio Voice Service - RVC + XTTS
==================================================

1. Checking NVIDIA Driver...
NVIDIA GeForce RTX 4090, 535.129.03, 24576 MiB
✓ NVIDIA driver installed

2. Checking Docker...
✓ Docker installed: 24.0.7

3. Checking Docker Compose...
✓ Docker Compose installed: 2.21.0

4. Checking NVIDIA Container Toolkit...
✓ NVIDIA Container Toolkit working

5. Checking GPU Memory...
✓ GPU Memory: 24576MB (≥12GB required)

6. Checking GPU Compute Capability...
✓ Compute Capability: 8.9 (≥7.0 required)

7. Checking Dockerfile-gpu...
✓ docker/Dockerfile-gpu found

8. Checking docker-compose-gpu.yml...
✓ docker-compose-gpu.yml found

==================================================
  Validation Summary
==================================================
Checks passed: 8
Checks failed: 0

✓ GPU environment READY for Sprint 1! ✓
```

---

## 🚀 Usage

### Build GPU Image

```bash
cd /path/to/services/audio-voice

# Build
docker compose -f docker-compose-gpu.yml build

# Build without cache (clean build)
docker compose -f docker-compose-gpu.yml build --no-cache
```

### Run Tests (Inside Container)

```bash
# Run GPU detection tests
docker compose -f docker-compose-gpu.yml run --rm audio-voice-service \
    pytest tests/test_gpu_detection.py -v

# Run Docker health tests
docker compose -f docker-compose-gpu.yml run --rm audio-voice-service \
    pytest tests/test_docker_health.py -v

# Run all tests
docker compose -f docker-compose-gpu.yml run --rm audio-voice-service \
    pytest tests/ -v

# With coverage
docker compose -f docker-compose-gpu.yml run --rm audio-voice-service \
    pytest --cov=app --cov-report=html --cov-report=term tests/
```

### Start Service

```bash
# Start in background
docker compose -f docker-compose-gpu.yml up -d

# View logs
docker compose -f docker-compose-gpu.yml logs -f

# Check health
docker compose -f docker-compose-gpu.yml ps

# Stop
docker compose -f docker-compose-gpu.yml down
```

### Monitor GPU Usage

```bash
# Host
watch -n 1 nvidia-smi

# Inside container
docker compose -f docker-compose-gpu.yml exec audio-voice-service \
    watch -n 1 nvidia-smi
```

---

## 🐛 Troubleshooting

### Issue 1: `nvidia-smi` not found

**Symptoms:**
```
bash: nvidia-smi: command not found
```

**Solution:**
```bash
# Install NVIDIA drivers
sudo apt-get update
sudo apt-get install -y nvidia-driver-535
sudo reboot
```

---

### Issue 2: `docker: Error response from daemon: could not select device driver "" with capabilities: [[gpu]]`

**Symptoms:**
```
docker: Error response from daemon: could not select device driver "" 
with capabilities: [[gpu]].
```

**Solution:**
```bash
# Install nvidia-docker2
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Verify
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

---

### Issue 3: `CUDA not available` inside container

**Symptoms:**
```python
import torch
assert torch.cuda.is_available()  # AssertionError
```

**Checklist:**
1. ✅ NVIDIA driver installed on host? (`nvidia-smi`)
2. ✅ nvidia-docker2 installed? (`docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi`)
3. ✅ Using `docker-compose-gpu.yml`? (not `docker-compose.yml`)
4. ✅ Image built from `Dockerfile-gpu`?
5. ✅ Environment variables set? (`NVIDIA_VISIBLE_DEVICES=all`)

**Debug:**
```bash
# Check if GPU is visible inside container
docker compose -f docker-compose-gpu.yml run --rm audio-voice-service nvidia-smi

# Check CUDA with Python
docker compose -f docker-compose-gpu.yml run --rm audio-voice-service \
    python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}')"
```

---

### Issue 4: OOM (Out of Memory)

**Symptoms:**
```
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB
```

**Solutions:**

1. **Check VRAM:**
```bash
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
```

2. **Increase Docker memory limit:**
```yaml
# docker-compose-gpu.yml
deploy:
  resources:
    limits:
      memory: 16G  # Increase from 12G
```

3. **Reduce batch size / use FP16** (Sprint 9 - Performance)

4. **Clear CUDA cache:**
```python
import torch
torch.cuda.empty_cache()
```

---

### Issue 5: Slow performance (GPU not being used)

**Symptoms:**
- Generation takes >30s for 10s audio
- `nvidia-smi` shows 0% GPU utilization

**Debug:**
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"Current device: {torch.cuda.current_device()}")
print(f"Device name: {torch.cuda.get_device_name(0)}")

# Check if model is on GPU
# (Sprint 3+)
```

**Solutions:**
1. Verify `XTTS_DEVICE=cuda` in environment
2. Check model loaded on GPU (not CPU)
3. Ensure data tensors moved to GPU

---

## 📚 References

- **NVIDIA Driver:** https://www.nvidia.com/Download/index.aspx
- **Docker:** https://docs.docker.com/engine/install/ubuntu/
- **NVIDIA Container Toolkit:** https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
- **PyTorch CUDA:** https://pytorch.org/get-started/locally/
- **CUDA Compatibility:** https://docs.nvidia.com/deploy/cuda-compatibility/

---

## ✅ Sprint 1 Acceptance Criteria

After completing this guide:

- [ ] `nvidia-smi` works on host
- [ ] Docker installed (≥20.10)
- [ ] nvidia-docker2 installed and working
- [ ] `./scripts/validate-gpu.sh` passes all checks
- [ ] `docker compose -f docker-compose-gpu.yml build` succeeds
- [ ] `pytest tests/test_gpu_detection.py -v` all green (inside container)
- [ ] GPU memory ≥12GB
- [ ] Compute Capability ≥7.0

**Status:** Sprint 1 Complete! ✅

---

**Next Sprint:** Sprint 2 - Install RVC dependencies
