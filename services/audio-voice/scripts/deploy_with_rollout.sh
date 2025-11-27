#!/bin/bash
# Script de deployment com controle de feature flags para rollout gradual
# Uso: ./deploy_with_rollout.sh [alpha|beta|ga|disable]

set -e

PHASE=${1:-"disabled"}
VALID_PHASES=("disabled" "alpha" "beta" "ga")

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}🚀 Deployment com Rollout Gradual${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Validar fase
if [[ ! " ${VALID_PHASES[@]} " =~ " ${PHASE} " ]]; then
    echo -e "${RED}❌ Fase inválida: ${PHASE}${NC}"
    echo -e "Fases válidas: ${VALID_PHASES[*]}"
    exit 1
fi

echo -e "📋 Fase selecionada: ${YELLOW}${PHASE}${NC}"
echo ""

# Configurar variáveis de ambiente baseado na fase
case $PHASE in
    "disabled")
        export FEATURE_F5TTS_ENABLED=false
        export FEATURE_F5TTS_PHASE=disabled
        export FEATURE_F5TTS_PERCENTAGE=0
        echo -e "${YELLOW}🔒 F5-TTS: DESABILITADO${NC}"
        ;;
    
    "alpha")
        export FEATURE_F5TTS_ENABLED=true
        export FEATURE_F5TTS_PHASE=alpha
        export FEATURE_F5TTS_PERCENTAGE=10
        echo -e "${GREEN}🐛 F5-TTS: ALPHA (10% usuários)${NC}"
        ;;
    
    "beta")
        export FEATURE_F5TTS_ENABLED=true
        export FEATURE_F5TTS_PHASE=beta
        export FEATURE_F5TTS_PERCENTAGE=50
        echo -e "${GREEN}🧪 F5-TTS: BETA (50% usuários)${NC}"
        ;;
    
    "ga")
        export FEATURE_F5TTS_ENABLED=true
        export FEATURE_F5TTS_PHASE=ga
        export FEATURE_F5TTS_PERCENTAGE=100
        echo -e "${GREEN}🎉 F5-TTS: GA (100% usuários)${NC}"
        ;;
esac

echo ""
echo -e "${GREEN}🔧 Variáveis de ambiente:${NC}"
echo "  FEATURE_F5TTS_ENABLED=${FEATURE_F5TTS_ENABLED}"
echo "  FEATURE_F5TTS_PHASE=${FEATURE_F5TTS_PHASE}"
echo "  FEATURE_F5TTS_PERCENTAGE=${FEATURE_F5TTS_PERCENTAGE}"
echo ""

# Confirmar deploy
read -p "Continuar com deploy? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}❌ Deploy cancelado${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}📦 Iniciando deployment...${NC}"
echo ""

# 1. Build da imagem
echo -e "${GREEN}1️⃣  Building Docker image...${NC}"
docker-compose build audio-voice

# 2. Stop serviços antigos
echo -e "${GREEN}2️⃣  Stopping old services...${NC}"
docker-compose down

# 3. Start novos serviços com feature flags
echo -e "${GREEN}3️⃣  Starting new services...${NC}"
docker-compose up -d

# 4. Wait for health check
echo -e "${GREEN}4️⃣  Waiting for health check...${NC}"
sleep 10

MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Service is healthy!${NC}"
        break
    fi
    
    RETRY=$((RETRY+1))
    echo -n "."
    sleep 2
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo -e "${RED}❌ Health check failed after ${MAX_RETRIES} attempts${NC}"
    echo -e "${YELLOW}📋 Logs:${NC}"
    docker-compose logs --tail=50 audio-voice
    exit 1
fi

echo ""

# 5. Smoke tests
echo -e "${GREEN}5️⃣  Running smoke tests...${NC}"

# Test 1: Health endpoint
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "  ✅ Health check OK"
else
    echo -e "  ${RED}❌ Health check FAILED${NC}"
    exit 1
fi

# Test 2: Feature flags endpoint
if curl -f http://localhost:8000/feature-flags > /dev/null 2>&1; then
    echo -e "  ✅ Feature flags endpoint OK"
else
    echo -e "  ${YELLOW}⚠️  Feature flags endpoint not available${NC}"
fi

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ Deployment completo!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Mostrar status atual
echo -e "${GREEN}📊 Status atual:${NC}"
echo "  Phase: ${FEATURE_F5TTS_PHASE}"
echo "  Percentage: ${FEATURE_F5TTS_PERCENTAGE}%"
echo ""

# Instruções de próximos passos
case $PHASE in
    "alpha")
        echo -e "${YELLOW}📋 Próximos passos (ALPHA):${NC}"
        echo "  1. Monitorar logs: docker-compose logs -f audio-voice"
        echo "  2. Verificar métricas por 3-5 dias"
        echo "  3. Se OK, promover para BETA: ./deploy_with_rollout.sh beta"
        echo "  4. Se problemas, rollback: ./deploy_with_rollout.sh disabled"
        ;;
    
    "beta")
        echo -e "${YELLOW}📋 Próximos passos (BETA):${NC}"
        echo "  1. Monitorar logs: docker-compose logs -f audio-voice"
        echo "  2. Executar A/B testing"
        echo "  3. Verificar métricas por 5-7 dias"
        echo "  4. Se OK, promover para GA: ./deploy_with_rollout.sh ga"
        echo "  5. Se problemas, rollback: ./deploy_with_rollout.sh alpha"
        ;;
    
    "ga")
        echo -e "${GREEN}🎉 F5-TTS agora está em GA (100%)!${NC}"
        echo ""
        echo -e "${YELLOW}📋 Próximos passos (GA):${NC}"
        echo "  1. Monitorar por 7+ dias"
        echo "  2. Atualizar documentação"
        echo "  3. Comunicar aos usuários"
        echo "  4. Celebrar! 🍾"
        ;;
    
    "disabled")
        echo -e "${YELLOW}📋 F5-TTS está desabilitado${NC}"
        echo "  Sistema usando apenas XTTS (backward compatible)"
        ;;
esac

echo ""
