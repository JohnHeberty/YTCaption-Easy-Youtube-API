# SPRINT 1 - Infraestrutura Docker + CUDA

**Duração Estimada:** 3-5 dias  
**Responsável:** DevOps Engineer + Backend Engineer  
**Dependências:** Nenhuma (primeira sprint)

---

## 1. OBJETIVO

Preparar infraestrutura Docker com suporte CUDA para executar RVC em GPU, garantindo que:
- ✅ Container inicia com CUDA disponível
- ✅ GPU é detectada e utilizável
- ✅ Health checks validam GPU
- ✅ Ambiente reproduzível e documentado

---

## 2. PRÉ-REQUISITOS

### Hardware

- GPU NVIDIA com CUDA Compute Capability ≥7.0 (RTX 2000+, Tesla T4+, A100, etc.)
- ≥12GB VRAM (16GB+ recomendado)
- ≥32GB RAM sistema
- ≥100GB disco livre

### Software (Host)

- Docker ≥20.10
- Docker Compose ≥1.29
- NVIDIA Driver ≥470.xx (para CUDA 11.8+)
- nvidia-docker2 (NVIDIA Container Toolkit)

### Validação de Pré-requisitos

```bash
# Verificar GPU
nvidia-smi

# Verificar Docker
docker --version
docker-compose --version

# Verificar nvidia-docker
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

**Critério:** Todos os comandos acima devem executar sem erros.

---

## 3. TAREFAS

### 3.1 TESTES (Red Phase)

#### 3.1.1 Criar `tests/test_gpu_detection.py`

```python
"""
Testes de detecção e disponibilidade de GPU
Sprint 1: Infraestrutura
"""
import pytest
import torch


class TestGPUDetection:
    """
    Testes para validar que GPU está disponível e funcional
    """
    
    def test_cuda_available(self):
        """GPU NVIDIA deve estar disponível via CUDA"""
        assert torch.cuda.is_available(), "CUDA not available - GPU required for RVC"
    
    def test_cuda_device_count(self):
        """Deve haver pelo menos 1 GPU disponível"""
        device_count = torch.cuda.device_count()
        assert device_count >= 1, f"Expected ≥1 GPU, found {device_count}"
    
    def test_cuda_device_name(self):
        """Nome da GPU deve ser identificável"""
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            assert len(device_name) > 0, "GPU name should not be empty"
            assert "NVIDIA" in device_name or "Tesla" in device_name or "GeForce" in device_name, \
                f"Unexpected GPU: {device_name}"
    
    def test_cuda_memory_available(self):
        """GPU deve ter memória suficiente (≥12GB)"""
        if torch.cuda.is_available():
            device = torch.cuda.current_device()
            total_memory = torch.cuda.get_device_properties(device).total_memory
            total_memory_gb = total_memory / (1024**3)
            
            assert total_memory_gb >= 12.0, \
                f"GPU has {total_memory_gb:.1f}GB VRAM, minimum 12GB required"
    
    def test_cuda_compute_capability(self):
        """GPU deve ter Compute Capability ≥7.0 (RTX 2000+)"""
        if torch.cuda.is_available():
            device = torch.cuda.current_device()
            capability = torch.cuda.get_device_capability(device)
            major, minor = capability
            
            assert major >= 7, \
                f"GPU Compute Capability {major}.{minor} too old, need ≥7.0"
    
    def test_simple_gpu_operation(self):
        """Deve conseguir executar operação simples na GPU"""
        if torch.cuda.is_available():
            device = torch.device('cuda:0')
            
            # Cria tensor na GPU
            x = torch.randn(100, 100, device=device)
            y = torch.randn(100, 100, device=device)
            
            # Operação na GPU
            z = torch.matmul(x, y)
            
            assert z.device.type == 'cuda', "Operation should execute on GPU"
            assert z.shape == (100, 100), "Result shape incorrect"


@pytest.mark.skipif(not torch.cuda.is_available(), reason="GPU tests require CUDA")
class TestGPUPerformance:
    """
    Testes de performance básica da GPU
    """
    
    def test_gpu_faster_than_cpu(self):
        """GPU deve ser mais rápida que CPU para operações grandes"""
        import time
        
        size = 5000
        
        # CPU
        x_cpu = torch.randn(size, size)
        y_cpu = torch.randn(size, size)
        
        start_cpu = time.time()
        z_cpu = torch.matmul(x_cpu, y_cpu)
        cpu_time = time.time() - start_cpu
        
        # GPU
        device = torch.device('cuda:0')
        x_gpu = torch.randn(size, size, device=device)
        y_gpu = torch.randn(size, size, device=device)
        
        # Warmup
        _ = torch.matmul(x_gpu, y_gpu)
        torch.cuda.synchronize()
        
        start_gpu = time.time()
        z_gpu = torch.matmul(x_gpu, y_gpu)
        torch.cuda.synchronize()
        gpu_time = time.time() - start_gpu
        
        speedup = cpu_time / gpu_time
        
        assert speedup > 5.0, \
            f"GPU should be >5x faster, got {speedup:.1f}x (CPU: {cpu_time:.3f}s, GPU: {gpu_time:.3f}s)"
```

#### 3.1.2 Criar `tests/test_docker_health.py`

```python
"""
Testes de health check do container Docker
Sprint 1: Infraestrutura
"""
import pytest
import subprocess
import json


class TestDockerHealth:
    """
    Testes para validar health checks do container
    """
    
    def test_health_endpoint_responds(self):
        """Endpoint /health deve responder com 200"""
        # Este teste roda dentro do container
        import requests
        
        response = requests.get("http://localhost:8000/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
    
    def test_health_response_structure(self):
        """Response /health deve ter estrutura esperada"""
        import requests
        
        response = requests.get("http://localhost:8000/health")
        data = response.json()
        
        assert "status" in data, "Missing 'status' field"
        assert "gpu" in data, "Missing 'gpu' field"
        assert "version" in data, "Missing 'version' field"
    
    def test_health_gpu_detected(self):
        """Health check deve reportar GPU disponível"""
        import requests
        
        response = requests.get("http://localhost:8000/health")
        data = response.json()
        
        assert data["gpu"]["available"] is True, "GPU not detected in health check"
        assert data["gpu"]["device_count"] >= 1, "No GPU devices found"
        assert "device_name" in data["gpu"], "GPU name missing"


@pytest.mark.docker
class TestDockerBuild:
    """
    Testes que validam build do Docker (rodam no host)
    """
    
    def test_dockerfile_gpu_exists(self):
        """Dockerfile-gpu deve existir"""
        from pathlib import Path
        dockerfile = Path("docker/Dockerfile-gpu")
        assert dockerfile.exists(), "Dockerfile-gpu not found in docker/"
    
    def test_docker_compose_gpu_exists(self):
        """docker-compose-gpu.yml deve existir"""
        from pathlib import Path
        compose_file = Path("docker-compose-gpu.yml")
        assert compose_file.exists(), "docker-compose-gpu.yml not found"
    
    def test_docker_image_builds(self):
        """Imagem Docker deve buildar sem erros"""
        result = subprocess.run(
            ["docker", "build", "-f", "docker/Dockerfile-gpu", "-t", "audio-voice-rvc:test", "."],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Docker build failed:\n{result.stderr}"
    
    def test_docker_compose_validates(self):
        """docker-compose-gpu.yml deve validar sem erros"""
        result = subprocess.run(
            ["docker-compose", "-f", "docker-compose-gpu.yml", "config"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"docker-compose validation failed:\n{result.stderr}"
```

**Validação:** Rodar `pytest tests/test_gpu_detection.py tests/test_docker_health.py -v`

**Resultado Esperado:** ❌ TODOS OS TESTES DEVEM FALHAR (arquivos Docker não existem ainda)

---

### 3.2 IMPLEMENTAÇÃO (Green Phase)

#### 3.2.1 Criar `docker/Dockerfile-gpu`

```dockerfile
# Dockerfile com suporte CUDA para RVC
# Sprint 1: Infraestrutura

FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# Metadata
LABEL maintainer="audio-voice-team"
LABEL description="Audio Voice Service with XTTS + RVC (GPU)"
LABEL version="2.1.0-rvc"

# Argumentos de build
ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_VERSION=3.10

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CUDA_HOME=/usr/local/cuda \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python3-pip \
    # Audio
    ffmpeg \
    libsndfile1 \
    # Build tools
    build-essential \
    cmake \
    git \
    # Utilities
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Criar symlink python -> python3.10
RUN ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python && \
    ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3

# Atualizar pip
RUN python -m pip install --upgrade pip setuptools wheel

# Criar diretório de trabalho
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar PyTorch com CUDA (antes de outras deps)
RUN pip install torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 \
    --index-url https://download.pytorch.org/whl/cu121

# Instalar dependências Python
RUN pip install -r requirements.txt

# Copiar código da aplicação
COPY app/ ./app/
COPY run.py .

# Criar diretórios necessários
RUN mkdir -p /app/models/rvc \
    /app/processed \
    /app/uploads \
    /app/temp \
    /app/logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import torch; import requests; \
                   assert torch.cuda.is_available(), 'CUDA not available'; \
                   r = requests.get('http://localhost:8000/health'); \
                   assert r.status_code == 200, 'Health check failed'; \
                   exit(0)"

# Expor porta
EXPOSE 8000

# Comando de inicialização
CMD ["python", "run.py"]
```

#### 3.2.2 Criar `docker-compose-gpu.yml`

```yaml
# Docker Compose com suporte GPU
# Sprint 1: Infraestrutura

version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile-gpu
    image: audio-voice-rvc:latest
    container_name: audio-voice-api-gpu
    
    # GPU access
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    
    environment:
      # FastAPI
      - HOST=0.0.0.0
      - PORT=8000
      - WORKERS=1  # 1 worker por GPU
      - LOG_LEVEL=info
      
      # XTTS
      - XTTS_DEVICE=cuda
      - XTTS_USE_DEEPSPEED=false
      - XTTS_CACHE_DIR=/app/models
      
      # RVC (será usado em sprints futuras)
      - RVC_DEVICE=cuda
      - RVC_MODELS_DIR=/app/models/rvc
      - RVC_ENABLE=false  # Desabilitado até Sprint 3
      
      # Redis
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      
      # Celery
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    
    ports:
      - "8000:8000"
    
    volumes:
      - ./app:/app/app
      - ./models:/app/models
      - ./processed:/app/processed
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    
    depends_on:
      redis:
        condition: service_healthy
    
    networks:
      - audio-voice-network
    
    restart: unless-stopped
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile-gpu
    image: audio-voice-rvc:latest
    container_name: audio-voice-worker-gpu
    
    # GPU access
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    
    command: ["celery", "-A", "app.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
    
    environment:
      - XTTS_DEVICE=cuda
      - RVC_DEVICE=cuda
      - RVC_ENABLE=false
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    
    volumes:
      - ./app:/app/app
      - ./models:/app/models
      - ./processed:/app/processed
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    
    depends_on:
      redis:
        condition: service_healthy
    
    networks:
      - audio-voice-network
    
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: audio-voice-redis
    
    ports:
      - "6379:6379"
    
    volumes:
      - redis-data:/data
    
    networks:
      - audio-voice-network
    
    restart: unless-stopped
    
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

networks:
  audio-voice-network:
    driver: bridge

volumes:
  redis-data:
    driver: local
```

#### 3.2.3 Atualizar `app/main.py` - Health Check com GPU

```python
# Adicionar ao app/main.py (existente)

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint com informações de GPU
    
    Returns:
        dict: Status do serviço e GPU
    """
    import torch
    from datetime import datetime
    
    gpu_info = {
        "available": torch.cuda.is_available(),
        "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
    }
    
    if torch.cuda.is_available():
        gpu_info["device_name"] = torch.cuda.get_device_name(0)
        gpu_info["cuda_version"] = torch.version.cuda
        
        # VRAM info
        device = torch.cuda.current_device()
        total_memory = torch.cuda.get_device_properties(device).total_memory
        allocated_memory = torch.cuda.memory_allocated(device)
        
        gpu_info["vram_total_gb"] = round(total_memory / (1024**3), 2)
        gpu_info["vram_allocated_gb"] = round(allocated_memory / (1024**3), 2)
        gpu_info["vram_free_gb"] = round((total_memory - allocated_memory) / (1024**3), 2)
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.0-rvc",
        "gpu": gpu_info,
        "services": {
            "xtts": "ready",
            "rvc": "disabled"  # Será "ready" após Sprint 3
        }
    }
```

#### 3.2.4 Criar script de validação `scripts/validate-gpu.sh`

```bash
#!/bin/bash
# Script de validação de GPU
# Sprint 1: Infraestrutura

set -e

echo "==================================="
echo "GPU Validation Script"
echo "==================================="
echo ""

# Check 1: nvidia-smi
echo "✓ Checking nvidia-smi..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ nvidia-smi not found. Install NVIDIA drivers."
    exit 1
fi
nvidia-smi
echo ""

# Check 2: Docker
echo "✓ Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Install Docker."
    exit 1
fi
docker --version
echo ""

# Check 3: Docker Compose
echo "✓ Checking Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Install Docker Compose."
    exit 1
fi
docker-compose --version
echo ""

# Check 4: nvidia-docker (NVIDIA Container Toolkit)
echo "✓ Checking NVIDIA Container Toolkit..."
if ! docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "❌ NVIDIA Container Toolkit not working. Install nvidia-docker2."
    exit 1
fi
echo "NVIDIA Container Toolkit is working!"
echo ""

# Check 5: GPU Memory
echo "✓ Checking GPU VRAM..."
VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1)
if [ "$VRAM" -lt 12000 ]; then
    echo "⚠️  Warning: GPU has ${VRAM}MB VRAM, recommended ≥12GB"
else
    echo "GPU has ${VRAM}MB VRAM ✓"
fi
echo ""

echo "==================================="
echo "✅ All GPU checks passed!"
echo "==================================="
```

#### 3.2.5 Criar documentação `docs/GPU-SETUP.md`

```markdown
# GPU Setup Guide

## Pré-requisitos

### 1. NVIDIA Driver

Instalar driver NVIDIA ≥470.xx:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y nvidia-driver-535

# Verificar instalação
nvidia-smi
```

### 2. NVIDIA Container Toolkit

```bash
# Adicionar repositório
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Instalar
sudo apt update
sudo apt install -y nvidia-docker2

# Reiniciar Docker
sudo systemctl restart docker

# Testar
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### 3. Validar Setup

```bash
chmod +x scripts/validate-gpu.sh
./scripts/validate-gpu.sh
```

## Build e Run

```bash
# Build
docker-compose -f docker-compose-gpu.yml build

# Run
docker-compose -f docker-compose-gpu.yml up -d

# Verificar logs
docker-compose -f docker-compose-gpu.yml logs -f api

# Verificar health
curl http://localhost:8000/health | jq
```

## Troubleshooting

### GPU não detectada

```bash
# Verificar driver
nvidia-smi

# Verificar Docker vê GPU
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Verificar logs do container
docker logs audio-voice-api-gpu
```

### OOM (Out of Memory)

```bash
# Limpar cache CUDA
docker exec -it audio-voice-api-gpu python -c "import torch; torch.cuda.empty_cache()"

# Reduzir workers
# Em docker-compose-gpu.yml: WORKERS=1
```
```

---

### 3.3 REFATORAÇÃO

#### 3.3.1 Otimizar Dockerfile

- Reduzir layers (combinar RUN statements)
- Adicionar .dockerignore
- Multi-stage build (se aplicável)

#### 3.3.2 Criar `.dockerignore`

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
*.egg-info/
dist/
build/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/
*.log

# Data
processed/
uploads/
temp/
models/rvc/*.pth
models/rvc/*.index

# Git
.git/
.gitignore

# Docs
docs/
*.md
!README.md

# Tests
tests/
pytest.ini
.pytest_cache/

# CI/CD
.github/
.gitlab-ci.yml
```

#### 3.3.3 Documentar comandos úteis

Criar `scripts/docker-commands.sh`:

```bash
#!/bin/bash
# Comandos úteis Docker GPU

# Build
docker-compose -f docker-compose-gpu.yml build --no-cache

# Start
docker-compose -f docker-compose-gpu.yml up -d

# Stop
docker-compose -f docker-compose-gpu.yml down

# Logs
docker-compose -f docker-compose-gpu.yml logs -f api

# Shell no container
docker exec -it audio-voice-api-gpu bash

# Verificar GPU no container
docker exec -it audio-voice-api-gpu nvidia-smi

# Limpar tudo
docker-compose -f docker-compose-gpu.yml down -v
docker system prune -af
```

---

## 4. CRITÉRIOS DE ACEITAÇÃO

### ✅ Checklist

- [ ] **Dockerfile-gpu** existe e builda sem erros
- [ ] **docker-compose-gpu.yml** existe e valida sem erros
- [ ] Container **inicia** sem erros
- [ ] **GPU detectada** dentro do container (`nvidia-smi` funciona)
- [ ] **PyTorch** detecta CUDA (`torch.cuda.is_available() == True`)
- [ ] **Health check** retorna status "healthy" com info GPU
- [ ] **Todos os testes** em `test_gpu_detection.py` passam ✅
- [ ] **Todos os testes** em `test_docker_health.py` passam ✅
- [ ] **Script de validação** `validate-gpu.sh` passa ✅
- [ ] **Documentação** GPU-SETUP.md está completa
- [ ] **Coverage** ≥85% nos testes de infra

### Comando de Validação Final

```bash
# Build
docker-compose -f docker-compose-gpu.yml build

# Start
docker-compose -f docker-compose-gpu.yml up -d

# Aguardar 60s para health check
sleep 60

# Testar health
curl -f http://localhost:8000/health || exit 1

# Rodar testes dentro do container
docker exec -it audio-voice-api-gpu pytest tests/test_gpu_detection.py -v

# Verificar GPU
docker exec -it audio-voice-api-gpu nvidia-smi

# Limpar
docker-compose -f docker-compose-gpu.yml down
```

**Resultado Esperado:** ✅ TODOS OS COMANDOS EXECUTAM SEM ERROS

---

## 5. ENTREGÁVEIS

### Arquivos Criados

```
docker/
├── Dockerfile-gpu               ✅ NOVO

docker-compose-gpu.yml           ✅ NOVO

app/
└── main.py                      🔄 MODIFICADO (health check com GPU)

tests/
├── test_gpu_detection.py        ✅ NOVO
└── test_docker_health.py        ✅ NOVO

scripts/
├── validate-gpu.sh              ✅ NOVO
└── docker-commands.sh           ✅ NOVO

docs/
└── GPU-SETUP.md                 ✅ NOVO

.dockerignore                    ✅ NOVO
```

### Documentação Atualizada

- [x] GPU-SETUP.md com instruções completas
- [x] README.md com seção "GPU Support"
- [x] docker-commands.sh com comandos úteis

---

## 6. PRÓXIMOS PASSOS

Após completar esta sprint:

1. ✅ Marcar Sprint 1 como completa no SPRINTS.md
2. ✅ Commit changes: `git commit -m "feat(rvc): Sprint 1 - Docker GPU infrastructure"`
3. ✅ Push: `git push origin feature/f5tts-ptbr-migration`
4. ▶️ Iniciar **Sprint 2** (ler `sprints/SPRINT-02-DEPS.md`)

---

## 7. TROUBLESHOOTING

### Problema: CUDA not available no container

**Solução:**
```bash
# Verificar nvidia-docker
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Se falhar, reinstalar nvidia-docker2
sudo apt remove nvidia-docker2
sudo apt install nvidia-docker2
sudo systemctl restart docker
```

### Problema: Build timeout ou lento

**Solução:**
```bash
# Aumentar timeout no docker-compose-gpu.yml
services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile-gpu
      args:
        BUILDKIT_INLINE_CACHE: 1
    environment:
      DOCKER_BUILDKIT: 1
```

### Problema: Health check sempre unhealthy

**Solução:**
```bash
# Verificar logs
docker logs audio-voice-api-gpu

# Testar health manualmente
docker exec -it audio-voice-api-gpu curl http://localhost:8000/health

# Desabilitar health check temporariamente para debug
# Comentar seção healthcheck no docker-compose-gpu.yml
```

---

**Sprint 1 Completa!** 🎉

Próxima: **Sprint 2 - Instalação de Dependências RVC** →
