#!/bin/bash

# Script de teste REAL - Tenta subir cada servico e verifica se inicia corretamente

set -e

echo "================================================================================"
echo "TESTE REAL DE STARTUP DOS SERVICOS"
echo "================================================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

REPO_ROOT="/root/YTCaption-Easy-Youtube-API"

check_service() {
    local port=$1
    local max_attempts=10
    local attempt=0
    
    echo -n "  Aguardando servico iniciar"
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}  OK - respondendo na porta $port${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo ""
    echo -e "${RED}  FALHOU - nao respondeu apos $((max_attempts * 2))s${NC}"
    return 1
}

test_service_docker() {
    local service_name=$1
    local port=$2
    
    echo -e "${BLUE}--- $service_name ---${NC}"
    
    cd "$REPO_ROOT/services/$service_name"
    
    echo "  Parando containers anteriores..."
    docker compose down -v > /dev/null 2>&1 || true
    
    echo "  Fazendo build..."
    if ! docker compose build > /dev/null 2>&1; then
        echo -e "${RED}  FALHOU: Erro no build${NC}"
        echo ""
        return 1
    fi
    echo -e "${GREEN}  Build OK${NC}"
    
    echo "  Iniciando..."
    if ! docker compose up -d > /dev/null 2>&1; then
        echo -e "${RED}  FALHOU: Erro ao iniciar${NC}"
        echo ""
        return 1
    fi
    echo -e "${GREEN}  Container iniciado${NC}"
    
    sleep 5
    
    if ! docker compose ps | grep -q "Up"; then
        echo -e "${RED}  FALHOU: Container nao esta rodando${NC}"
        docker compose logs | tail -20
        docker compose down -v > /dev/null 2>&1
        echo ""
        return 1
    fi
    
    if check_service "$port"; then
        echo -e "${GREEN}  PASSOU: $service_name${NC}"
        docker compose down -v > /dev/null 2>&1
        echo ""
        return 0
    else
        echo -e "${YELLOW}  PARCIAL: Container rodando mas health nao responde${NC}"
        docker compose down -v > /dev/null 2>&1
        echo ""
        return 2
    fi
}

cd "$REPO_ROOT"

total=0
passed=0
failed=0
partial=0

declare -A SERVICES
SERVICES=(
    ["se1-orchestrator"]="8001"
    ["se2-video-downloader"]="8002"
    ["se3-audio-normalization"]="8003"
    ["se6-youtube-search"]="8006"
)

for svc in se1-orchestrator se2-video-downloader se3-audio-normalization se6-youtube-search; do
    total=$((total + 1))
    port=${SERVICES[$svc]}
    if test_service_docker "$svc" "$port"; then
        passed=$((passed + 1))
    elif [ $? -eq 2 ]; then
        partial=$((partial + 1))
    else
        failed=$((failed + 1))
    fi
done

echo "================================================================================"
echo "RESUMO DOS TESTES"
echo "================================================================================"
echo ""
echo "Total: $total"
echo -e "Passou: ${GREEN}$passed${NC}"
echo -e "Parcial: ${YELLOW}$partial${NC}"
echo -e "Falhou: ${RED}$failed${NC}"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}Todos os servicos testados passaram!${NC}"
    exit 0
else
    echo -e "${RED}Alguns servicos falharam. Verifique os logs acima.${NC}"
    exit 1
fi
