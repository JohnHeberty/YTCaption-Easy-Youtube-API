#!/bin/bash
# validate-gpu.sh - Script de validação de GPU para Sprint 1
# Valida que ambiente está pronto para RVC + XTTS com CUDA

set -e

echo "=================================================="
echo "  GPU Validation Script - Sprint 1"
echo "  Audio Voice Service - RVC + XTTS"
echo "=================================================="
echo ""

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para printar com cores
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "ℹ $1"
}

# Contadores
CHECKS_PASSED=0
CHECKS_FAILED=0

# 1. Verificar nvidia-smi
echo "1. Checking NVIDIA Driver..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    print_success "NVIDIA driver installed"
    ((CHECKS_PASSED++))
else
    print_error "nvidia-smi not found - install NVIDIA drivers"
    ((CHECKS_FAILED++))
    exit 1
fi
echo ""

# 2. Verificar Docker
echo "2. Checking Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d ' ' -f3 | tr -d ',')
    print_success "Docker installed: $DOCKER_VERSION"
    ((CHECKS_PASSED++))
else
    print_error "Docker not found - install Docker ≥20.10"
    ((CHECKS_FAILED++))
    exit 1
fi
echo ""

# 3. Verificar Docker Compose
echo "3. Checking Docker Compose..."
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version --short)
    print_success "Docker Compose installed: $COMPOSE_VERSION"
    ((CHECKS_PASSED++))
else
    print_error "Docker Compose not found - install docker-compose ≥1.29"
    ((CHECKS_FAILED++))
    exit 1
fi
echo ""

# 4. Verificar NVIDIA Container Toolkit
echo "4. Checking NVIDIA Container Toolkit..."
if docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    print_success "NVIDIA Container Toolkit working"
    ((CHECKS_PASSED++))
else
    print_error "NVIDIA Container Toolkit not working - install nvidia-docker2"
    print_info "Run: sudo apt-get install -y nvidia-docker2 && sudo systemctl restart docker"
    ((CHECKS_FAILED++))
    exit 1
fi
echo ""

# 5. Verificar GPU Memory
echo "5. Checking GPU Memory..."
GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1)
if [ "$GPU_MEM" -ge 12000 ]; then
    print_success "GPU Memory: ${GPU_MEM}MB (≥12GB required)"
    ((CHECKS_PASSED++))
else
    print_warning "GPU Memory: ${GPU_MEM}MB (<12GB - may cause OOM errors)"
    print_info "RVC + XTTS requires ≥12GB VRAM (16GB+ recommended)"
    ((CHECKS_PASSED++))
fi
echo ""

# 6. Verificar Compute Capability
echo "6. Checking GPU Compute Capability..."
COMPUTE_CAP=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -n 1)
COMPUTE_MAJOR=$(echo $COMPUTE_CAP | cut -d. -f1)
if [ "$COMPUTE_MAJOR" -ge 7 ]; then
    print_success "Compute Capability: $COMPUTE_CAP (≥7.0 required)"
    ((CHECKS_PASSED++))
else
    print_error "Compute Capability: $COMPUTE_CAP (<7.0 - GPU too old)"
    print_info "RVC requires Compute Capability ≥7.0 (RTX 2000+, Tesla T4+)"
    ((CHECKS_FAILED++))
fi
echo ""

# 7. Verificar se Dockerfile-gpu existe
echo "7. Checking Dockerfile-gpu..."
if [ -f "docker/Dockerfile-gpu" ]; then
    print_success "docker/Dockerfile-gpu found"
    ((CHECKS_PASSED++))
else
    print_error "docker/Dockerfile-gpu not found"
    ((CHECKS_FAILED++))
fi
echo ""

# 8. Verificar se docker-compose-gpu.yml existe
echo "8. Checking docker-compose-gpu.yml..."
if [ -f "docker-compose-gpu.yml" ]; then
    print_success "docker-compose-gpu.yml found"
    ((CHECKS_PASSED++))
else
    print_error "docker-compose-gpu.yml not found"
    ((CHECKS_FAILED++))
fi
echo ""

# 9. Test build (opcional - pode ser lento)
if [ "$1" == "--build" ]; then
    echo "9. Testing Docker build..."
    if docker compose -f docker-compose-gpu.yml build --no-cache; then
        print_success "Docker build successful"
        ((CHECKS_PASSED++))
    else
        print_error "Docker build failed"
        ((CHECKS_FAILED++))
    fi
    echo ""
fi

# Resumo
echo "=================================================="
echo "  Validation Summary"
echo "=================================================="
echo -e "Checks passed: ${GREEN}$CHECKS_PASSED${NC}"
if [ $CHECKS_FAILED -gt 0 ]; then
    echo -e "Checks failed: ${RED}$CHECKS_FAILED${NC}"
    echo ""
    print_error "GPU environment NOT ready for Sprint 1"
    exit 1
else
    echo -e "Checks failed: ${GREEN}0${NC}"
    echo ""
    print_success "GPU environment READY for Sprint 1! ✓"
    echo ""
    print_info "Next steps:"
    echo "  1. Build image: docker compose -f docker-compose-gpu.yml build"
    echo "  2. Run tests: docker compose -f docker-compose-gpu.yml run --rm audio-voice-service pytest tests/test_gpu_detection.py -v"
    echo "  3. Start service: docker compose -f docker-compose-gpu.yml up -d"
    exit 0
fi
