#!/bin/bash

################################################################################
# YTCaption - Automatic Startup Script for Proxmox/Linux
# 
# This script will:
# - Detect system resources (CPU cores, RAM)
# - Validate Docker and Docker Compose installation
# - Configure environment to use 100% of available resources
# - Start the application
#
# Usage: ./start.sh [options]
# Options:
#   --force-rebuild    Force rebuild Docker images
#   --no-gpu          Disable GPU even if available
#   --model MODEL     Set Whisper model (tiny|base|small|medium|large)
#   --help            Show this help message
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
FORCE_REBUILD=false
DISABLE_GPU=false
WHISPER_MODEL=""

################################################################################
# Functions
################################################################################

print_header() {
    echo -e "${BLUE}"
    echo "=================================="
    echo "   YTCaption Startup Script"
    echo "=================================="
    echo -e "${NC}"
}

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
    echo -e "${BLUE}ℹ $1${NC}"
}

show_help() {
    echo "Usage: ./start.sh [options]"
    echo ""
    echo "Options:"
    echo "  --force-rebuild    Force rebuild Docker images"
    echo "  --no-gpu          Disable GPU even if available"
    echo "  --model MODEL     Set Whisper model (tiny|base|small|medium|large)"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./start.sh                          # Normal start"
    echo "  ./start.sh --force-rebuild          # Rebuild and start"
    echo "  ./start.sh --model medium --no-gpu  # Use medium model on CPU"
}

check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root is not recommended"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

detect_cpu_cores() {
    print_info "Detecting CPU cores..."
    
    # Get number of CPU cores
    CPU_CORES=$(nproc)
    CPU_THREADS=$(nproc --all)
    
    print_success "Detected: $CPU_CORES cores / $CPU_THREADS threads"
    
    # Use 100% of available CPU cores for Docker limits
    DOCKER_CPUS="$CPU_CORES"
    DOCKER_CPUS_RESERVATION="$CPU_CORES"
    print_info "Using 100% of CPU cores: $CPU_CORES"
    
    # Note: WORKERS=1 (single Uvicorn worker) is optimal for this application
    # Multiple Uvicorn workers would compete for the same Whisper model in memory
    # Parallel processing is handled by PARALLEL_WORKERS in transcription layer
    
    export DOCKER_CPUS
    export DOCKER_CPUS_RESERVATION
}

detect_ram() {
    print_info "Detecting RAM..."
    
    # Get total RAM in GB
    TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
    
    print_success "Detected: ${TOTAL_RAM_GB}GB RAM"
    
    # Use 100% of available RAM for Docker
    DOCKER_MEMORY="${TOTAL_RAM_GB}G"
    DOCKER_MEMORY_RESERVATION="${TOTAL_RAM_GB}G"
    print_info "Using 100% of RAM: ${TOTAL_RAM_GB}GB"
    
    export DOCKER_MEMORY
    export DOCKER_MEMORY_RESERVATION
}

detect_gpu() {
    if [ "$DISABLE_GPU" = true ]; then
        print_info "GPU detection disabled by user"
        WHISPER_DEVICE="cpu"
        GPU_AVAILABLE=false
        return
    fi
    
    print_info "Detecting GPU..."
    
    # Check for NVIDIA GPU
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi &> /dev/null; then
            GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1)
            print_success "NVIDIA GPU detected: $GPU_NAME"
            
            # Check for CUDA
            if command -v nvcc &> /dev/null; then
                CUDA_VERSION=$(nvcc --version | grep "release" | awk '{print $5}' | cut -d',' -f1)
                print_success "CUDA detected: $CUDA_VERSION"
                WHISPER_DEVICE="cuda"
                GPU_AVAILABLE=true
            else
                print_warning "CUDA not found. GPU will not be used."
                WHISPER_DEVICE="cpu"
                GPU_AVAILABLE=false
            fi
        else
            print_info "No NVIDIA GPU detected"
            WHISPER_DEVICE="cpu"
            GPU_AVAILABLE=false
        fi
    else
        print_info "nvidia-smi not found. Using CPU only."
        WHISPER_DEVICE="cpu"
        GPU_AVAILABLE=false
    fi
    
    export WHISPER_DEVICE
}

recommend_whisper_model() {
    if [ -n "$WHISPER_MODEL" ]; then
        print_info "Using user-specified model: $WHISPER_MODEL"
        return
    fi
    
    print_info "Recommending Whisper model based on hardware..."
    
    # Recommend model based on hardware
    if [ "$GPU_AVAILABLE" = true ]; then
        if [ "$TOTAL_RAM_GB" -ge 16 ]; then
            WHISPER_MODEL="medium"
            print_success "Recommended: medium (with GPU)"
        else
            WHISPER_MODEL="base"
            print_success "Recommended: base (GPU with limited RAM)"
        fi
    else
        if [ "$CPU_CORES" -ge 8 ] && [ "$TOTAL_RAM_GB" -ge 16 ]; then
            WHISPER_MODEL="base"
            print_success "Recommended: base (powerful CPU)"
        else
            WHISPER_MODEL="tiny"
            print_success "Recommended: tiny (CPU-optimized for speed)"
        fi
    fi
    
    export WHISPER_MODEL
}

check_docker() {
    print_info "Checking Docker installation..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed!"
        echo ""
        echo "Install Docker with:"
        echo "  curl -fsSL https://get.docker.com | sh"
        echo "  sudo usermod -aG docker \$USER"
        echo "  newgrp docker"
        exit 1
    fi
    
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | cut -d',' -f1)
    print_success "Docker installed: $DOCKER_VERSION"
    
    # Check if Docker daemon is running
    if ! docker ps &> /dev/null; then
        print_error "Docker daemon is not running!"
        echo ""
        echo "Start Docker with:"
        echo "  sudo systemctl start docker"
        echo "  sudo systemctl enable docker"
        exit 1
    fi
    
    print_success "Docker daemon is running"
}

check_docker_compose() {
    print_info "Checking Docker Compose installation..."
    
    # Check for docker-compose (standalone)
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version | awk '{print $4}' | cut -d',' -f1)
        print_success "Docker Compose installed: $COMPOSE_VERSION"
        COMPOSE_CMD="docker-compose"
        return
    fi
    
    # Check for docker compose (plugin)
    if docker compose version &> /dev/null 2>&1; then
        COMPOSE_VERSION=$(docker compose version --short)
        print_success "Docker Compose (plugin) installed: $COMPOSE_VERSION"
        COMPOSE_CMD="docker compose"
        return
    fi
    
    # Not found
    print_error "Docker Compose is not installed!"
    echo ""
    echo "Install Docker Compose with:"
    echo "  sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose"
    echo "  sudo chmod +x /usr/local/bin/docker-compose"
    exit 1
}

check_disk_space() {
    print_info "Checking disk space..."
    
    # Get available space in GB
    AVAILABLE_SPACE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
    
    if [ "$AVAILABLE_SPACE" -lt 10 ]; then
        print_error "Insufficient disk space! At least 10GB required."
        print_info "Available: ${AVAILABLE_SPACE}GB"
        exit 1
    fi
    
    print_success "Available disk space: ${AVAILABLE_SPACE}GB"
}

check_network() {
    print_info "Checking network connectivity..."
    
    if ping -c 1 8.8.8.8 &> /dev/null; then
        print_success "Network connection OK"
    else
        print_error "No network connection!"
        exit 1
    fi
    
    # Check Docker Hub connectivity
    if curl -s --max-time 5 https://hub.docker.com &> /dev/null; then
        print_success "Docker Hub accessible"
    else
        print_warning "Docker Hub may not be accessible"
    fi
}

check_ports() {
    print_info "Checking if port 8000 is available..."
    
    if netstat -tuln 2>/dev/null | grep -q ":8000 " || ss -tuln 2>/dev/null | grep -q ":8000 "; then
        print_error "Port 8000 is already in use!"
        echo ""
        echo "Stop the service using port 8000 or change the port in .env file"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "Port 8000 is available"
    fi
}

create_env_file() {
    print_info "Configuring environment..."
    
    if [ ! -f .env.example ]; then
        print_error ".env.example file not found!"
        exit 1
    fi
    
    # Backup existing .env if exists
    if [ -f .env ]; then
        cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
        print_info "Existing .env backed up"
    fi
    
    # Copy and configure .env
    cp .env.example .env
    
    # Update with detected values
    sed -i "s/WHISPER_MODEL=.*/WHISPER_MODEL=$WHISPER_MODEL/" .env
    sed -i "s/WHISPER_DEVICE=.*/WHISPER_DEVICE=$WHISPER_DEVICE/" .env
    
    # Note: WORKERS is NOT changed (stays at 1 from .env.example)
    # Single Uvicorn worker is optimal for this application
    
    # Configure parallel transcription
    # Enable parallel for multi-core systems (4+ cores)
    if [ "$CPU_CORES" -ge 4 ]; then
        sed -i "s/ENABLE_PARALLEL_TRANSCRIPTION=.*/ENABLE_PARALLEL_TRANSCRIPTION=true/" .env
        # Auto-detect optimal workers (use all cores)
        sed -i "s/PARALLEL_WORKERS=.*/PARALLEL_WORKERS=0/" .env
        print_success "Parallel transcription enabled (auto-detect $CPU_CORES cores)"
    else
        sed -i "s/ENABLE_PARALLEL_TRANSCRIPTION=.*/ENABLE_PARALLEL_TRANSCRIPTION=false/" .env
        print_info "Parallel transcription disabled (requires 4+ CPU cores)"
    fi
    
    print_success ".env file configured"
}

update_docker_compose() {
    print_info "Updating docker-compose.yml with system resources..."
    
    if [ ! -f docker-compose.yml ]; then
        print_error "docker-compose.yml not found!"
        exit 1
    fi
    
    # Backup original
    if [ ! -f docker-compose.yml.original ]; then
        cp docker-compose.yml docker-compose.yml.original
    fi
    
    # Update CPU and memory limits using sed
    sed -i "s/cpus: '[0-9]*'/cpus: '$DOCKER_CPUS'/" docker-compose.yml
    sed -i "s/memory: [0-9]*G/memory: $DOCKER_MEMORY/" docker-compose.yml
    
    # Update reservations
    sed -i "/reservations:/,/memory:/ s/cpus: '[0-9]*'/cpus: '$DOCKER_CPUS_RESERVATION'/" docker-compose.yml
    sed -i "/reservations:/,/memory:/ s/memory: [0-9]*G/memory: $DOCKER_MEMORY_RESERVATION/" docker-compose.yml
    
    print_success "docker-compose.yml updated"
}

show_configuration() {
    echo ""
    echo -e "${BLUE}==================================${NC}"
    echo -e "${BLUE}  Configuration Summary${NC}"
    echo -e "${BLUE}==================================${NC}"
    echo -e "CPU Cores:        ${GREEN}$CPU_CORES (100% allocated)${NC}"
    echo -e "Docker CPUs:      ${GREEN}$DOCKER_CPUS${NC}"
    echo -e "Uvicorn Workers:  ${GREEN}1 (single worker, optimal)${NC}"
    
    # Show parallel transcription config
    if [ "$CPU_CORES" -ge 4 ]; then
        echo -e "Parallel Transc:  ${GREEN}ENABLED (auto-detect $CPU_CORES cores)${NC}"
    else
        echo -e "Parallel Transc:  ${YELLOW}DISABLED (needs 4+ cores)${NC}"
    fi
    
    echo -e "Total RAM:        ${GREEN}${TOTAL_RAM_GB}GB (100% allocated)${NC}"
    echo -e "Docker Memory:    ${GREEN}$DOCKER_MEMORY${NC}"
    echo -e "Whisper Device:   ${GREEN}$WHISPER_DEVICE${NC}"
    echo -e "Whisper Model:    ${GREEN}$WHISPER_MODEL${NC}"
    echo -e "GPU Available:    ${GREEN}$GPU_AVAILABLE${NC}"
    echo -e "${BLUE}==================================${NC}"
    echo ""
}

start_application() {
    print_info "Starting YTCaption..."
    echo ""
    
    if [ "$FORCE_REBUILD" = true ]; then
        print_info "Force rebuilding Docker images..."
        $COMPOSE_CMD down
        $COMPOSE_CMD build --no-cache
    fi
    
    # Start the application
    $COMPOSE_CMD up -d
    
    if [ $? -eq 0 ]; then
        print_success "YTCaption started successfully!"
        echo ""
        print_info "Waiting for service to be ready..."

        # Wait for health check (max 20 seconds)
        for i in {1..20}; do
            if curl -s http://localhost:8000/health &> /dev/null; then
                echo ""
                print_success "Service is ready!"
                echo ""
                echo -e "${GREEN}==================================${NC}"
                echo -e "${GREEN}  YTCaption is running!${NC}"
                echo -e "${GREEN}==================================${NC}"
                echo ""
                echo -e "API URL:        ${BLUE}http://localhost:8000${NC}"
                echo -e "Documentation:  ${BLUE}http://localhost:8000/docs${NC}"
                echo -e "Health Check:   ${BLUE}http://localhost:8000/health${NC}"
                echo ""
                echo -e "View logs:      ${YELLOW}$COMPOSE_CMD logs -f${NC}"
                echo -e "Stop service:   ${YELLOW}$COMPOSE_CMD down${NC}"
                echo ""
                return 0
            fi
            sleep 1
            echo -n "."
        done
        
        echo ""
        print_warning "Service started but health check timed out"
        echo ""
        echo "Check logs with: $COMPOSE_CMD logs -f"
    else
        print_error "Failed to start YTCaption!"
        echo ""
        echo "Check logs with: $COMPOSE_CMD logs"
        exit 1
    fi
}

################################################################################
# Main Script
################################################################################

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force-rebuild)
            FORCE_REBUILD=true
            shift
            ;;
        --no-gpu)
            DISABLE_GPU=true
            shift
            ;;
        --model)
            WHISPER_MODEL="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Start script
print_header

# Run all checks
check_root
detect_cpu_cores
detect_ram
detect_gpu
recommend_whisper_model
check_docker
check_docker_compose
check_disk_space
check_network
check_ports

# Configure and start
create_env_file
update_docker_compose
show_configuration

# Ask for confirmation
read -p "Start YTCaption with this configuration? (Y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    print_info "Startup cancelled by user"
    exit 0
fi

start_application

print_success "All done! 🎉"
