#!/bin/bash
# ============================================================================
# Script de Deploy - Audio Transcriber Service
# ============================================================================
# Faz deploy do serviço em produção com validações
# ============================================================================

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funções auxiliares
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Banner
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Audio-Transcriber Production Deploy                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Validações pré-deploy
log_info "Validando ambiente..."

# 1. Verificar se está no diretório correto
if [ ! -f "docker/docker/docker-compose.prod.yml" ]; then
    log_error "docker/docker/docker-compose.prod.yml nao encontrado!"
    log_error "Execute este script do diretório services/audio-transcriber/"
    exit 1
fi

# 2. Verificar .env
if [ ! -f ".env" ]; then
    log_error "Arquivo .env não encontrado!"
    log_info "Copie .env.example para .env e configure:"
    log_info "  cp .env.example .env"
    exit 1
fi

# 3. Verificar variáveis críticas
source .env
if [ -z "$REDIS_URL" ]; then
    log_error "REDIS_URL não configurado no .env!"
    exit 1
fi

if [ -z "$WHISPER_MODEL" ]; then
    log_warning "WHISPER_MODEL não configurado, usando 'base'"
    WHISPER_MODEL="base"
fi

log_success "Validações OK"

# 4. Verificar rede Docker
log_info "Verificando rede Docker..."
if ! docker network inspect ytcaption_network &>/dev/null; then
    log_info "Criando rede ytcaption_network..."
    docker network create ytcaption_network
    log_success "Rede criada"
else
    log_success "Rede já existe"
fi

# 5. Criar diretórios necessários
log_info "Criando diretórios..."
mkdir -p uploads transcriptions models temp logs
chmod 755 uploads transcriptions models temp logs
log_success "Diretórios criados"

# 6. Build da imagem
log_info "Building imagem de produção..."
log_info "  Modelo: $WHISPER_MODEL"
log_info "  Device: CPU"

DOCKER_BUILDKIT=1 docker compose -f docker/docker-compose.prod.yml build \
    --build-arg BUILD_ENV=production

if [ $? -ne 0 ]; then
    log_error "Falha no build!"
    exit 1
fi
log_success "Build completo"

# 7. Parar serviços antigos se existirem
log_info "Parando serviços antigos..."
docker compose -f docker/docker-compose.prod.yml down 2>/dev/null || true
log_success "Serviços antigos parados"

# 8. Subir serviços
log_info "Subindo serviços..."
docker compose -f docker/docker-compose.prod.yml up -d

if [ $? -ne 0 ]; then
    log_error "Falha ao subir serviços!"
    exit 1
fi
log_success "Serviços iniciados"

# 9. Aguardar healthcheck
log_info "Aguardando healthcheck da API..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:${PORT:-8003}/health >/dev/null 2>&1; then
        log_success "API está saudável!"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    log_error "API não respondeu após ${MAX_RETRIES} tentativas"
    log_info "Verificando logs..."
    docker compose -f docker/docker-compose.prod.yml logs --tail=50 audio-transcriber-service
    exit 1
fi

# 10. Verificar Celery
log_info "Verificando Celery worker..."
sleep 5

if docker exec audio-transcriber-celery python -c "from app.celery_config import celery_app; i = celery_app.control.inspect(); exit(0 if i.stats() else 1)" 2>/dev/null; then
    log_success "Celery worker está ativo!"
else
    log_warning "Celery worker pode não estar funcionando corretamente"
fi

# 11. Resumo
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Deploy Completo! 🎉                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
log_info "Serviços rodando:"
docker compose -f docker/docker-compose.prod.yml ps
echo ""
log_info "Endpoints:"
echo "  • API: http://localhost:${PORT:-8003}"
echo "  • Docs: http://localhost:${PORT:-8003}/docs"
echo "  • Health: http://localhost:${PORT:-8003}/health"
echo ""
log_info "Logs:"
echo "  • Todos: docker compose -f docker/docker-compose.prod.yml logs -f"
echo "  • API: docker compose -f docker/docker-compose.prod.yml logs -f audio-transcriber-service"
echo "  • Celery: docker compose -f docker/docker-compose.prod.yml logs -f celery-worker"
echo ""
log_info "Comandos úteis:"
echo "  • Status: make prod-status"
echo "  • Logs: make prod-logs"
echo "  • Restart: docker compose -f docker/docker-compose.prod.yml restart"
echo "  • Down: docker compose -f docker/docker-compose.prod.yml down"
echo ""
log_success "Deploy concluído com sucesso!"
