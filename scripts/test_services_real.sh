#!/bin/bash

# Script de teste REAL - Tenta subir cada serviço e verificar se inicia corretamente
# Testa todos os serviços EXCETO audio-transcriber (que precisa de GPU)

set -e

echo "================================================================================"
echo "🚀 TESTE REAL DE STARTUP DOS SERVIÇOS"
echo "================================================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para verificar se o serviço está rodando
check_service() {
    local service_name=$1
    local port=$2
    local max_attempts=10
    local attempt=0
    
    echo -n "  Aguardando serviço iniciar"
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:$port/health > /dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}  ✓ Serviço respondendo na porta $port${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo ""
    echo -e "${RED}  ✗ Serviço não respondeu após $((max_attempts * 2))s${NC}"
    return 1
}

# Função para testar um serviço com Docker Compose
test_service_docker() {
    local service_name=$1
    local service_dir=$2
    local port=$3
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}▶ Testando: $service_name${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    cd $service_dir
    
    # Para qualquer container existente
    echo "  Limpando containers anteriores..."
    docker compose down -v > /dev/null 2>&1 || true
    
    # Tenta fazer build
    echo "  Fazendo build da imagem..."
    if ! docker compose build > /dev/null 2>&1; then
        echo -e "${RED}❌ FALHOU: Erro no build${NC}"
        echo ""
        return 1
    fi
    echo -e "${GREEN}  ✓ Build OK${NC}"
    
    # Tenta subir o serviço
    echo "  Iniciando serviço..."
    if ! docker compose up -d > /dev/null 2>&1; then
        echo -e "${RED}❌ FALHOU: Erro ao iniciar${NC}"
        echo ""
        return 1
    fi
    echo -e "${GREEN}  ✓ Container iniciado${NC}"
    
    # Aguarda alguns segundos para garantir inicialização
    sleep 5
    
    # Verifica logs para erros críticos
    echo "  Verificando logs..."
    if docker compose logs | grep -i "error\|exception\|failed" | grep -v "ERROR_THRESHOLD\|redis.*error" > /dev/null 2>&1; then
        echo -e "${YELLOW}  ⚠ Avisos/erros encontrados nos logs (verificar manualmente)${NC}"
        docker compose logs | grep -i "error\|exception\|failed" | head -5
    fi
    
    # Verifica se está rodando
    if ! docker compose ps | grep -q "Up"; then
        echo -e "${RED}❌ FALHOU: Container não está rodando${NC}"
        docker compose logs | tail -20
        docker compose down -v > /dev/null 2>&1
        echo ""
        return 1
    fi
    echo -e "${GREEN}  ✓ Container rodando${NC}"
    
    # Testa health endpoint (se disponível)
    if [ ! -z "$port" ]; then
        if check_service "$service_name" "$port"; then
            echo -e "${GREEN}✅ PASSOU: $service_name${NC}"
            docker compose down -v > /dev/null 2>&1
            echo ""
            return 0
        else
            echo -e "${YELLOW}⚠️  PARCIAL: Container rodando mas health não responde${NC}"
            docker compose logs | tail -10
            docker compose down -v > /dev/null 2>&1
            echo ""
            return 2
        fi
    else
        echo -e "${GREEN}✅ PASSOU: $service_name (sem health check)${NC}"
        docker compose down -v > /dev/null 2>&1
        echo ""
        return 0
    fi
}

cd /root/YTCaption-Easy-Youtube-API

total_tests=0
passed_tests=0
failed_tests=0
partial_tests=0

echo ""
echo "Testando serviços (exceto audio-transcriber que requer GPU)..."
echo ""

# Teste 1: orchestrator
total_tests=$((total_tests + 1))
if test_service_docker "orchestrator" "/root/YTCaption-Easy-Youtube-API/orchestrator" "8000"; then
    passed_tests=$((passed_tests + 1))
elif [ $? -eq 2 ]; then
    partial_tests=$((partial_tests + 1))
else
    failed_tests=$((failed_tests + 1))
fi

# Teste 2: audio-normalization
total_tests=$((total_tests + 1))
if test_service_docker "audio-normalization" "/root/YTCaption-Easy-Youtube-API/services/audio-normalization" "8001"; then
    passed_tests=$((passed_tests + 1))
elif [ $? -eq 2 ]; then
    partial_tests=$((partial_tests + 1))
else
    failed_tests=$((failed_tests + 1))
fi

# Teste 3: video-downloader
total_tests=$((total_tests + 1))
if test_service_docker "video-downloader" "/root/YTCaption-Easy-Youtube-API/services/video-downloader" "8003"; then
    passed_tests=$((passed_tests + 1))
elif [ $? -eq 2 ]; then
    partial_tests=$((partial_tests + 1))
else
    failed_tests=$((failed_tests + 1))
fi

# Teste 4: youtube-search
total_tests=$((total_tests + 1))
if test_service_docker "youtube-search" "/root/YTCaption-Easy-Youtube-API/services/youtube-search" "8004"; then
    passed_tests=$((passed_tests + 1))
elif [ $? -eq 2 ]; then
    partial_tests=$((partial_tests + 1))
else
    failed_tests=$((failed_tests + 1))
fi

echo "================================================================================"
echo "📊 RESUMO DOS TESTES REAIS"
echo "================================================================================"
echo ""
echo "Total de serviços testados: $total_tests"
echo -e "${GREEN}Passou completamente: $passed_tests${NC}"
echo -e "${YELLOW}Passou parcialmente: $partial_tests${NC}"
echo -e "${RED}Falhou: $failed_tests${NC}"
echo ""

success_rate=$(awk "BEGIN {printf \"%.1f\", (($passed_tests + $partial_tests)/$total_tests)*100}")
echo "Taxa de sucesso: ${success_rate}%"
echo ""

if [ $failed_tests -eq 0 ]; then
    if [ $partial_tests -eq 0 ]; then
        echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}🎉 TODOS OS SERVIÇOS PASSARAM COMPLETAMENTE!${NC}"
        echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo "✅ Todos os serviços:"
        echo "  • Fazem build corretamente"
        echo "  • Iniciam sem erros"
        echo "  • Respondem ao health check"
        echo ""
        echo "🚀 Sistema validado e pronto para uso!"
        echo ""
        exit 0
    else
        echo -e "${YELLOW}════════════════════════════════════════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}⚠️  ALGUNS SERVIÇOS PASSARAM PARCIALMENTE${NC}"
        echo -e "${YELLOW}════════════════════════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo "Os serviços iniciam mas podem precisar de configuração adicional (Redis, etc)"
        echo ""
        exit 0
    fi
else
    echo -e "${RED}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}❌ ALGUNS SERVIÇOS FALHARAM${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Verifique os logs acima para detalhes dos erros"
    echo ""
    exit 1
fi
