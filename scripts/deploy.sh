#!/bin/bash

# YTCaption - Deploy Script
# Sobe todos os serviços em produção com um único comando

set -e  # Exit on error

echo "🚀 YTCaption - Deploy Script"
echo "=============================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ Erro: Arquivo .env não encontrado!${NC}"
    echo ""
    echo "Por favor, crie o arquivo .env baseado no .env.example:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Edite com suas configurações"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓${NC} Arquivo .env encontrado"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Erro: Docker não está rodando!${NC}"
    echo ""
    echo "Inicie o Docker e tente novamente."
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker está rodando"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Erro: docker-compose não encontrado!${NC}"
    echo ""
    echo "Instale o Docker Compose:"
    echo "  https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker Compose disponível"
echo ""

# Ask for build type
echo "Escolha o modo de deploy:"
echo "  1) 🏗️  Build completo (recomendado para primeira vez ou após mudanças no código)"
echo "  2) 🚀 Deploy rápido (usa imagens existentes)"
echo ""
read -p "Digite 1 ou 2: " BUILD_CHOICE

case $BUILD_CHOICE in
    1)
        echo ""
        echo -e "${YELLOW}🏗️  Fazendo build completo...${NC}"
        echo ""
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        BUILD_TYPE="completo"
        ;;
    2)
        echo ""
        echo -e "${YELLOW}🚀 Deploy rápido...${NC}"
        echo ""
        docker-compose up -d
        BUILD_TYPE="rápido"
        ;;
    *)
        echo -e "${RED}❌ Opção inválida!${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✓${NC} Serviços iniciados com sucesso (deploy $BUILD_TYPE)"
echo ""

# Wait for services to start
echo "⏳ Aguardando serviços iniciarem..."
sleep 10

# Check services
echo ""
echo "🔍 Verificando status dos serviços..."
echo ""

SERVICES=(
    "orchestrator:http://localhost:8000/health"
    "video-downloader:http://localhost:8001/health"
    "audio-normalization:http://localhost:8002/health"
    "audio-transcriber:http://localhost:8003/health"
)

ALL_HEALTHY=true

for SERVICE in "${SERVICES[@]}"; do
    NAME="${SERVICE%%:*}"
    URL="${SERVICE##*:}"
    
    if curl -f -s "$URL" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $NAME"
    else
        echo -e "  ${RED}✗${NC} $NAME (não respondendo)"
        ALL_HEALTHY=false
    fi
done

echo ""

if [ "$ALL_HEALTHY" = true ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "📊 Status dos serviços:"
    echo "  • Orchestrator:        http://localhost:8000"
    echo "  • Video Downloader:    http://localhost:8001"
    echo "  • Audio Normalization: http://localhost:8002"
    echo "  • Audio Transcriber:   http://localhost:8003"
    echo ""
    echo "📚 Documentação da API:"
    echo "  • Swagger UI:          http://localhost:8000/docs"
    echo ""
    echo "🧪 Teste rápido:"
    echo "  curl http://localhost:8000/health"
    echo ""
    echo "📝 Ver logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "🛑 Parar serviços:"
    echo "  docker-compose down"
    echo ""
else
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}⚠️  Deploy concluído com avisos${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    echo "Alguns serviços não estão respondendo."
    echo "Verifique os logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "Ou verifique o status:"
    echo "  docker-compose ps"
    echo ""
fi

# Show running containers
echo "📦 Containers rodando:"
docker-compose ps
echo ""
