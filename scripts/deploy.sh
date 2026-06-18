#!/bin/bash

# YTCaption - Deploy Script
# Sobe todos os servicos com um unico comando

set -e

echo "YTCaption - Deploy Script"
echo "==========================="
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}ERRO: Docker nao esta rodando!${NC}"
    exit 1
fi
echo -e "${GREEN}OK${NC} Docker esta rodando"

# Check docker compose v2
if ! docker compose version > /dev/null 2>&1; then
    echo -e "${RED}ERRO: docker compose v2 nao encontrado!${NC}"
    exit 1
fi
echo -e "${GREEN}OK${NC} Docker Compose disponivel"
echo ""

echo "Escolha o modo de deploy:"
echo "  1) Build completo (recomendado para primeira vez ou apos mudancas no codigo)"
echo "  2) Deploy rapido (usa imagens existentes)"
echo ""
read -p "Digite 1 ou 2: " BUILD_CHOICE

SERVICES=(
    "se1-orchestrator"
    "se2-video-downloader"
    "se3-audio-normalization"
    "se4-audio-transcriber"
    "se5-make-video-clip"
    "se6-youtube-search"
    "se7-audio-generation"
)

deploy_service() {
    local svc="$1"
    local svc_dir="$REPO_ROOT/services/$svc"

    if [ ! -d "$svc_dir" ]; then
        echo -e "  ${YELLOW}SKIP${NC} $svc (dir not found)"
        return
    fi

    cd "$svc_dir"

    if [ "$BUILD_CHOICE" = "1" ]; then
        if docker compose build 2>&1 | tail -1; then
            echo -e "  ${GREEN}OK${NC} $svc build"
        else
            echo -e "  ${RED}ERRO${NC} $svc build"
            return 1
        fi
    fi

    if docker compose up -d 2>&1 | tail -1; then
        echo -e "  ${GREEN}OK${NC} $svc up"
    else
        echo -e "  ${RED}ERRO${NC} $svc up"
        return 1
    fi
}

case $BUILD_CHOICE in
    1)
        echo ""
        echo -e "${YELLOW}Build completo...${NC}"
        echo ""
        for svc in "${SERVICES[@]}"; do
            deploy_service "$svc"
        done
        ;;
    2)
        echo ""
        echo -e "${YELLOW}Deploy rapido...${NC}"
        echo ""
        for svc in "${SERVICES[@]}"; do
            deploy_service "$svc"
        done
        ;;
    *)
        echo -e "${RED}Opcao invalida!${NC}"
        exit 1
        ;;
esac

echo ""
echo "Aguardando servicos iniciarem..."
sleep 15

echo ""
echo "Verificando status dos servicos..."
echo ""

HEALTH_URLS=(
    "se1:http://localhost:8001/health"
    "se2:http://localhost:8002/health"
    "se3:http://localhost:8003/health"
    "se4:http://localhost:8004/health"
    "se5:http://localhost:8005/health"
    "se6:http://localhost:8006/health"
    "se7:http://localhost:8007/health"
)

ALL_HEALTHY=true

for ENTRY in "${HEALTH_URLS[@]}"; do
    NAME="${ENTRY%%:*}"
    URL="${ENTRY##*:}"
    if curl -f -s "$URL" > /dev/null 2>&1; then
        echo -e "  ${GREEN}OK${NC} $NAME"
    else
        echo -e "  ${RED}OFF${NC} $NAME"
        ALL_HEALTHY=false
    fi
done

echo ""

if [ "$ALL_HEALTHY" = true ]; then
    echo -e "${GREEN}Deploy concluido com sucesso!${NC}"
    echo ""
    echo "Portas:"
    echo "  se1: http://localhost:8001"
    echo "  se2: http://localhost:8002"
    echo "  se3: http://localhost:8003"
    echo "  se4: http://localhost:8004"
    echo "  se5: http://localhost:8005"
    echo "  se6: http://localhost:8006"
    echo "  se7: http://localhost:8007"
else
    echo -e "${YELLOW}Deploy concluido com avisos${NC}"
    echo "Verifique os logs: docker compose -f docker/docker-compose.yml logs -f"
fi

echo ""
echo "Containers:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "ytcaption|audio-|video-|youtube-|make-video-clip" || docker ps
echo ""
