#!/bin/bash
# ============================================================================
# Script de Rollback - Audio Transcriber Service
# ============================================================================
# Reverte para versão anterior em caso de problemas
# ============================================================================

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Audio-Transcriber Rollback                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Confirmar rollback
log_warning "ATENÇÃO: Isso irá reverter para a versão anterior!"
read -p "Continuar com rollback? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Rollback cancelado"
    exit 0
fi

# 1. Parar serviços atuais
log_info "Parando serviços atuais..."
docker compose -f docker-compose.prod.yml down
log_success "Serviços parados"

# 2. Restaurar imagem anterior
log_info "Listando imagens disponíveis..."
docker images | grep audio-transcriber | head -5

log_info "Digite o IMAGE ID da versão anterior (ou ENTER para cancelar):"
read -r OLD_IMAGE_ID

if [ -z "$OLD_IMAGE_ID" ]; then
    log_info "Rollback cancelado"
    exit 0
fi

# 3. Tag da imagem antiga como production
log_info "Restaurando imagem $OLD_IMAGE_ID..."
docker tag "$OLD_IMAGE_ID" audio-transcriber:production
log_success "Imagem restaurada"

# 4. Subir serviços com versão antiga
log_info "Subindo serviços com versão anterior..."
docker compose -f docker-compose.prod.yml up -d
log_success "Serviços iniciados"

# 5. Aguardar healthcheck
log_info "Aguardando healthcheck..."
sleep 10

MAX_RETRIES=20
RETRY_COUNT=0
PORT=${PORT:-8003}

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:${PORT}/health >/dev/null 2>&1; then
        log_success "API respondendo!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 3
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    log_error "API não respondeu após rollback!"
    log_info "Verificando logs..."
    docker compose -f docker-compose.prod.yml logs --tail=50
    exit 1
fi

# 6. Resumo
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  Rollback Completo! ✅                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
log_info "Serviços rodando com versão anterior:"
docker compose -f docker-compose.prod.yml ps
echo ""
log_success "Rollback concluído com sucesso!"
