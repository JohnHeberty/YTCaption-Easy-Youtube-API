#!/bin/bash

# Script de teste de BUILD dos serviços
# Apenas testa se as imagens Docker podem ser construídas corretamente

set -e

echo "================================================================================"
echo "🐳 TESTE DE BUILD DOS SERVIÇOS DOCKER"
echo "================================================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

total_tests=0
passed_tests=0
failed_tests=0

test_build() {
    local service_name=$1
    local service_dir=$2
    
    total_tests=$((total_tests + 1))
    
    echo -e "${BLUE}▶ Testando build: $service_name${NC}"
    echo "  Diretório: $service_dir"
    
    cd "$service_dir"
    
    # Verifica se Dockerfile existe
    if [ ! -f "Dockerfile" ]; then
        echo -e "${RED}  ✗ Dockerfile não encontrado${NC}"
        echo -e "${RED}❌ FALHOU: $service_name${NC}"
        echo ""
        failed_tests=$((failed_tests + 1))
        return 1
    fi
    
    echo "  Fazendo build da imagem..."
    
    # Tenta fazer build
    if docker build -t ytcaption-test-$service_name . > /tmp/docker-build-$service_name.log 2>&1; then
        echo -e "${GREEN}  ✓ Build OK${NC}"
        
        # Verifica o tamanho da imagem
        image_size=$(docker images ytcaption-test-$service_name --format "{{.Size}}" | head -1)
        echo "  Tamanho da imagem: $image_size"
        
        echo -e "${GREEN}✅ PASSOU: $service_name${NC}"
        echo ""
        passed_tests=$((passed_tests + 1))
        return 0
    else
        echo -e "${RED}  ✗ Build falhou${NC}"
        echo "  Últimas linhas do log:"
        tail -20 /tmp/docker-build-$service_name.log | sed 's/^/    /'
        echo -e "${RED}❌ FALHOU: $service_name${NC}"
        echo ""
        failed_tests=$((failed_tests + 1))
        return 1
    fi
}

cd /root/YTCaption-Easy-Youtube-API

echo "Testando builds dos serviços (exceto audio-transcriber que requer GPU)..."
echo ""

# Teste 1: orchestrator
test_build "orchestrator" "/root/YTCaption-Easy-Youtube-API/orchestrator"

# Teste 2: audio-normalization
test_build "audio-normalization" "/root/YTCaption-Easy-Youtube-API/services/audio-normalization"

# Teste 3: video-downloader
test_build "video-downloader" "/root/YTCaption-Easy-Youtube-API/services/video-downloader"

# Teste 4: youtube-search
test_build "youtube-search" "/root/YTCaption-Easy-Youtube-API/services/youtube-search"

echo "================================================================================"
echo "📊 RESUMO DOS TESTES DE BUILD"
echo "================================================================================"
echo ""
echo "Total de serviços testados: $total_tests"
echo -e "${GREEN}Builds bem-sucedidos: $passed_tests${NC}"
echo -e "${RED}Builds falhados: $failed_tests${NC}"
echo ""

if [ $passed_tests -gt 0 ]; then
    echo "Imagens criadas:"
    docker images | grep ytcaption-test | sed 's/^/  /'
    echo ""
fi

success_rate=$(awk "BEGIN {printf \"%.1f\", ($passed_tests/$total_tests)*100}")
echo "Taxa de sucesso: ${success_rate}%"
echo ""

if [ $failed_tests -eq 0 ]; then
    echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}🎉 TODOS OS BUILDS PASSARAM!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "✅ Todos os serviços:"
    echo "  • Dockerfiles válidos"
    echo "  • Dependências instaladas corretamente"
    echo "  • Biblioteca common incluída no build"
    echo "  • Imagens Docker criadas com sucesso"
    echo ""
    echo "🚀 Pronto para próxima fase: testes de startup!"
    echo ""
    exit 0
else
    echo -e "${RED}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}❌ ALGUNS BUILDS FALHARAM${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Verifique os logs acima para detalhes dos erros"
    echo "Logs completos em: /tmp/docker-build-*.log"
    echo ""
    exit 1
fi
