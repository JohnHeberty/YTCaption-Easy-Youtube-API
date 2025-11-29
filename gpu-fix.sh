#!/bin/bash
################################################################################
# Script de Configuração NVIDIA Container Toolkit para Proxmox LXC
# 
# Descrição: Automatiza a instalação e configuração completa do NVIDIA Container
#            Toolkit em containers LXC do Proxmox com GPU passthrough
#
# Uso: sudo bash gpu-fix.sh
#
# Autor: YTCaption Team
# Data: 2025-11-29
################################################################################

set -e  # Interrompe em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funções de logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verifica se está rodando como root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        log_error "Este script precisa ser executado como root (sudo)"
        exit 1
    fi
    log_success "Executando como root"
}

# Detecta distribuição Linux
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        VERSION=$VERSION_ID
        log_info "Distribuição detectada: $DISTRO $VERSION"
    else
        log_error "Não foi possível detectar a distribuição"
        exit 1
    fi
}

# Verifica se NVIDIA GPU está disponível
check_nvidia_gpu() {
    log_info "Verificando disponibilidade da GPU NVIDIA..."
    
    if [ -c /dev/nvidia0 ]; then
        log_success "Dispositivos NVIDIA encontrados"
        ls -la /dev/nvidia* 2>/dev/null || true
    else
        log_warning "Dispositivos NVIDIA não encontrados em /dev/"
        log_warning "Certifique-se de que o GPU passthrough está configurado no Proxmox"
    fi
    
    # Verifica nvidia-smi se disponível
    if command -v nvidia-smi &> /dev/null; then
        log_info "Testando nvidia-smi..."
        nvidia-smi --query-gpu=name,driver_version --format=csv,noheader || log_warning "nvidia-smi falhou"
    fi
}

# Remove instalações antigas conflitantes
cleanup_old_installations() {
    log_info "Removendo instalações antigas e conflitantes..."
    
    # Para containers Docker que possam estar usando as libs
    if command -v docker &> /dev/null; then
        log_info "Parando containers Docker..."
        docker stop $(docker ps -q) 2>/dev/null || true
    fi
    
    # Remove bind mounts antigos do libnvidia-container
    if mountpoint -q /usr/lib/x86_64-linux-gnu/libnvidia-container.so.1 2>/dev/null; then
        log_info "Desmontando bind mount antigo de libnvidia-container.so.1..."
        umount /usr/lib/x86_64-linux-gnu/libnvidia-container.so.1 || true
    fi
    
    # Remove pacotes antigos
    apt-get remove --purge -y nvidia-container-toolkit* libnvidia-container* 2>/dev/null || true
    apt-get autoremove -y 2>/dev/null || true
    
    # Limpa arquivos residuais
    rm -rf /var/lib/dpkg/info/libnvidia-container* 2>/dev/null || true
    rm -rf /usr/lib/x86_64-linux-gnu/libnvidia-container.so* 2>/dev/null || true
    
    log_success "Limpeza concluída"
}

# Configura repositório NVIDIA Container Toolkit
setup_nvidia_repository() {
    log_info "Configurando repositório NVIDIA Container Toolkit..."
    
    # Instala dependências
    apt-get update
    apt-get install -y curl gnupg software-properties-common
    
    # Adiciona GPG key
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg --yes
    
    # Configura repositório genérico DEB para Debian/Ubuntu
    echo "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/amd64 /" | \
        tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    
    apt-get update
    
    log_success "Repositório configurado"
}

# Instala NVIDIA Container Toolkit
install_nvidia_toolkit() {
    log_info "Instalando NVIDIA Container Toolkit..."
    
    # Tenta instalação normal
    if apt-get install -y nvidia-container-toolkit; then
        log_success "NVIDIA Container Toolkit instalado com sucesso"
        return 0
    fi
    
    # Se falhar devido ao cross-device link, tenta workaround
    log_warning "Instalação falhou, aplicando workaround para LXC..."
    
    # Remove arquivo problemático se existir como bind mount
    if mountpoint -q /usr/lib/x86_64-linux-gnu/libnvidia-container.so.1 2>/dev/null; then
        umount /usr/lib/x86_64-linux-gnu/libnvidia-container.so.1 || true
    fi
    rm -f /usr/lib/x86_64-linux-gnu/libnvidia-container.so* 2>/dev/null || true
    
    # Remove estado do dpkg
    rm -rf /var/lib/dpkg/info/libnvidia-container* || true
    dpkg --configure -a
    
    # Tenta novamente
    apt-get install -y nvidia-container-toolkit
    
    log_success "NVIDIA Container Toolkit instalado"
}

# Configura Docker para usar runtime NVIDIA
configure_docker_runtime() {
    log_info "Configurando Docker runtime NVIDIA..."
    
    if ! command -v docker &> /dev/null; then
        log_warning "Docker não encontrado, pulando configuração do runtime"
        return 0
    fi
    
    # Usa nvidia-ctk para configurar
    nvidia-ctk runtime configure --runtime=docker
    
    log_success "Docker runtime configurado"
}

# Configura nvidia-container-runtime para LXC
configure_for_lxc() {
    log_info "Configurando nvidia-container-runtime para ambiente LXC..."
    
    mkdir -p /etc/nvidia-container-runtime
    
    cat > /etc/nvidia-container-runtime/config.toml << 'EOF'
disable-require = false

[nvidia-container-cli]
environment = []
load-kmods = true
no-cgroups = true
ldconfig = "@/sbin/ldconfig"

[nvidia-container-runtime]
log-level = "info"
mode = "legacy"

[nvidia-container-runtime.modes.csv]
mount-spec-path = "/etc/nvidia-container-runtime/host-files-for-container.d"

[nvidia-container-runtime.modes.cdi]
default-kind = "runtime.nvidia.com"
EOF
    
    log_success "Configuração LXC aplicada (no-cgroups=true, mode=legacy)"
}

# Configura bind mount do libcuda.so se disponível
setup_libcuda_mount() {
    log_info "Configurando acesso ao libcuda.so..."
    
    # Procura libcuda.so no sistema
    LIBCUDA_PATH=$(find /usr/lib* -name "libcuda.so.*.*.* " -type f 2>/dev/null | head -1)
    
    if [ -z "$LIBCUDA_PATH" ]; then
        log_warning "libcuda.so não encontrado no sistema"
        log_warning "Será necessário configurar bind mounts do host Proxmox"
        log_warning "Consulte GPU-TROUBLESHOOTING.md para instruções"
        return 0
    fi
    
    log_info "libcuda.so encontrado: $LIBCUDA_PATH"
    
    # Cria links simbólicos se necessário
    CUDA_VERSION=$(basename "$LIBCUDA_PATH" | sed 's/libcuda.so.//')
    
    if [ ! -e /usr/lib/x86_64-linux-gnu/libcuda.so.1 ]; then
        ln -sf "$LIBCUDA_PATH" /usr/lib/x86_64-linux-gnu/libcuda.so.1
        log_success "Link simbólico criado: libcuda.so.1"
    fi
    
    if [ ! -e /usr/lib/x86_64-linux-gnu/libcuda.so ]; then
        ln -sf "$LIBCUDA_PATH" /usr/lib/x86_64-linux-gnu/libcuda.so
        log_success "Link simbólico criado: libcuda.so"
    fi
    
    ldconfig
}

# Reinicia Docker daemon
restart_docker() {
    if ! command -v docker &> /dev/null; then
        return 0
    fi
    
    log_info "Reiniciando Docker daemon..."
    systemctl restart docker
    sleep 2
    log_success "Docker reiniciado"
}

# Testa configuração
test_configuration() {
    log_info "=========================================="
    log_info "Testando configuração..."
    log_info "=========================================="
    
    # Teste 1: Verifica runtime nvidia
    if command -v docker &> /dev/null; then
        log_info "Teste 1: Verificando runtimes Docker"
        if docker info 2>/dev/null | grep -q nvidia; then
            log_success "Runtime nvidia detectado"
        else
            log_warning "Runtime nvidia não encontrado em 'docker info'"
        fi
    fi
    
    # Teste 2: nvidia-container-cli
    log_info "Teste 2: Verificando nvidia-container-cli"
    if nvidia-container-cli --load-kmods info 2>&1 | grep -q "NVRM version"; then
        log_success "nvidia-container-cli funcionando"
        nvidia-container-cli --load-kmods info | head -10
    else
        log_warning "nvidia-container-cli com problemas"
    fi
    
    # Teste 3: Container de teste (se Docker disponível)
    if command -v docker &> /dev/null; then
        log_info "Teste 3: Testando container com GPU"
        if docker run --rm --runtime=nvidia -e NVIDIA_VISIBLE_DEVICES=all \
           -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
           nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi 2>&1 | grep -q "NVIDIA-SMI"; then
            log_success "Container teste executou nvidia-smi com sucesso!"
        else
            log_warning "Teste de container falhou - pode precisar de bind mounts adicionais"
        fi
    fi
}

# Gera relatório final
generate_report() {
    log_info "=========================================="
    log_info "INSTALAÇÃO CONCLUÍDA"
    log_info "=========================================="
    
    echo ""
    log_success "NVIDIA Container Toolkit instalado e configurado"
    echo ""
    
    echo "Próximos passos:"
    echo "1. Se PyTorch não detectar GPU, configure bind mounts do host Proxmox"
    echo "   Consulte: GPU-TROUBLESHOOTING.md"
    echo ""
    echo "2. Para usar GPU em containers Docker, adicione ao docker-compose.yml:"
    echo "   runtime: nvidia"
    echo "   environment:"
    echo "     - NVIDIA_VISIBLE_DEVICES=all"
    echo "     - NVIDIA_DRIVER_CAPABILITIES=compute,utility"
    echo ""
    echo "3. Teste com:"
    echo "   docker run --rm --runtime=nvidia --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi"
    echo ""
    
    if [ -c /dev/nvidia0 ]; then
        echo "GPU detectada:"
        nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi não disponível)"
    fi
    
    echo ""
    log_info "Para mais informações, consulte /var/log/nvidia-container-toolkit-install.log"
}

# Função principal
main() {
    echo "=========================================="
    echo "NVIDIA Container Toolkit Installer"
    echo "Para Proxmox LXC com GPU Passthrough"
    echo "=========================================="
    echo ""
    
    # Executa etapas
    check_root
    detect_distro
    check_nvidia_gpu
    cleanup_old_installations
    setup_nvidia_repository
    install_nvidia_toolkit
    configure_docker_runtime
    configure_for_lxc
    setup_libcuda_mount
    restart_docker
    test_configuration
    generate_report
    
    log_success "Script concluído com sucesso!"
}

# Executa com logging
main 2>&1 | tee /var/log/nvidia-container-toolkit-install.log