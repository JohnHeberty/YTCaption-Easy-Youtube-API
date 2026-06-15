#!/bin/bash
# ============================================================================
# Script de Health Check - Audio Transcriber Service
# ============================================================================
# Verifica saúde completa do serviço
# ============================================================================

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PORT=${PORT:-8003}
API_URL="http://localhost:${PORT}"

# Funções
check() {
    local name=$1
    local command=$2
    
    echo -n "  • $name... "
    if eval "$command" &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
        return 0
    else
        echo -e "${RED}❌${NC}"
        return 1
    fi
}

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Audio-Transcriber Health Check                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

ERRORS=0

# 1. Containers
echo "🐳 Docker Containers:"
check "API Container" "docker ps | grep -q audio-transcriber-api" || ERRORS=$((ERRORS+1))
check "Celery Container" "docker ps | grep -q audio-transcriber-celery" || ERRORS=$((ERRORS+1))
check "Beat Container" "docker ps | grep -q audio-transcriber-beat" || ERRORS=$((ERRORS+1))
echo ""

# 2. API Endpoints
echo "🌐 API Endpoints:"
check "Health Check" "curl -sf ${API_URL}/health" || ERRORS=$((ERRORS+1))
check "Languages" "curl -sf ${API_URL}/languages" || ERRORS=$((ERRORS+1))
check "Models" "curl -sf ${API_URL}/models" || ERRORS=$((ERRORS+1))
echo ""

# 3. Celery
echo "⚙️  Celery:"
check "Worker Active" "docker exec audio-transcriber-celery python -c 'from app.celery_config import celery_app; i = celery_app.control.inspect(); exit(0 if i.stats() else 1)'" || ERRORS=$((ERRORS+1))
check "Beat Active" "docker ps | grep -q audio-transcriber-beat" || ERRORS=$((ERRORS+1))
echo ""

# 4. Recursos
echo "💾 Recursos:"
check "Disk Space" "[ $(df -h . | tail -1 | awk '{print $5}' | sed 's/%//') -lt 90 ]" || ERRORS=$((ERRORS+1))
check "Uploads Dir" "[ -d ./uploads ]" || ERRORS=$((ERRORS+1))
check "Models Dir" "[ -d ./models ]" || ERRORS=$((ERRORS+1))
echo ""

# 5. Logs
echo "📜 Últimos Erros (última hora):"
RECENT_ERRORS=$(docker compose -f docker/docker-compose.prod.yml logs --since 1h 2>&1 | grep -i "error\|exception\|failed" | wc -l || echo "0")
if [ "$RECENT_ERRORS" -gt 10 ]; then
    echo -e "  ${RED}⚠️  $RECENT_ERRORS erros encontrados${NC}"
    ERRORS=$((ERRORS+1))
else
    echo -e "  ${GREEN}✅ $RECENT_ERRORS erros (OK)${NC}"
fi
echo ""

# Resumo
echo "════════════════════════════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ Sistema SAUDÁVEL - Todos os checks passaram!${NC}"
    exit 0
else
    echo -e "${RED}❌ Sistema com PROBLEMAS - $ERRORS check(s) falharam${NC}"
    echo ""
    echo "💡 Para mais detalhes:"
    echo "  docker compose -f docker/docker-compose.prod.yml logs --tail=100"
    exit 1
fi
