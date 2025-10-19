#!/bin/bash

################################################################################
# YTCaption - Quick Deploy Script
# 
# Atualiza o servidor com o código mais recente
################################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "===================================="
echo "   YTCaption Quick Deploy"
echo "===================================="
echo -e "${NC}"

# Verificar se está usando Docker
if [ -f "docker-compose.yml" ]; then
    echo -e "${BLUE}ℹ Docker Compose detected${NC}"
    
    # Parar containers
    echo -e "${YELLOW}⏸  Stopping containers...${NC}"
    docker-compose down
    
    # Rebuild (sem cache para garantir código novo)
    echo -e "${YELLOW}🔨 Building image (this may take a few minutes)...${NC}"
    docker-compose build --no-cache
    
    # Iniciar
    echo -e "${GREEN}🚀 Starting containers...${NC}"
    docker-compose up -d
    
    # Aguardar 5 segundos
    echo -e "${BLUE}ℹ Waiting for workers to load model...${NC}"
    sleep 5
    
    # Mostrar logs
    echo -e "${GREEN}✓ Deploy complete! Showing logs:${NC}"
    echo ""
    docker-compose logs -f
    
else
    echo -e "${YELLOW}⚠  Docker Compose not found. Manual deployment required.${NC}"
    echo ""
    echo "Please follow these steps:"
    echo "1. Stop the application"
    echo "2. Update the code (git pull or copy files)"
    echo "3. Restart the application"
    echo ""
    exit 1
fi
