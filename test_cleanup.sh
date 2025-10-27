#!/bin/bash

# Script de Teste - Limpeza Total dos Microserviços
# Testa se o endpoint /admin/cleanup está funcionando corretamente

echo "======================================================================"
echo "🧪 TESTE DE LIMPEZA TOTAL DOS MICROSERVIÇOS"
echo "======================================================================"
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# URLs dos microserviços
VIDEO_DOWNLOADER="http://localhost:8001"
AUDIO_NORMALIZATION="http://localhost:8002"
AUDIO_TRANSCRIBER="http://localhost:8003"

# Função para verificar se serviço está rodando
check_service() {
    local name=$1
    local url=$2
    
    echo -n "Verificando $name... "
    if curl -s -f "$url/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Online${NC}"
        return 0
    else
        echo -e "${RED}✗ Offline${NC}"
        return 1
    fi
}

# Função para obter estatísticas antes
get_stats() {
    local name=$1
    local url=$2
    
    echo ""
    echo -e "${YELLOW}📊 Estatísticas de $name ANTES da limpeza:${NC}"
    curl -s "$url/admin/stats" | jq '.'
}

# Função para executar limpeza
cleanup() {
    local name=$1
    local url=$2
    
    echo ""
    echo -e "${YELLOW}🔥 Executando limpeza em $name...${NC}"
    
    # Medir tempo de resposta
    start=$(date +%s.%N)
    response=$(curl -s -X POST "$url/admin/cleanup")
    end=$(date +%s.%N)
    
    # Calcular tempo
    duration=$(echo "$end - $start" | bc)
    
    echo "Resposta:"
    echo "$response" | jq '.'
    
    echo ""
    echo -e "⏱️  Tempo de resposta: ${GREEN}${duration}s${NC}"
    
    # Validar tempo de resposta (deve ser < 1s)
    if (( $(echo "$duration < 1.0" | bc -l) )); then
        echo -e "${GREEN}✓ Resposta resiliente (< 1s)${NC}"
    else
        echo -e "${RED}✗ Resposta lenta (> 1s)${NC}"
    fi
}

# Função para aguardar limpeza completar
wait_cleanup() {
    local name=$1
    echo ""
    echo -e "${YELLOW}⏳ Aguardando limpeza de $name completar...${NC}"
    sleep 5
}

# Função para verificar se limpou
verify_cleanup() {
    local name=$1
    local url=$2
    
    echo ""
    echo -e "${YELLOW}📊 Estatísticas de $name APÓS a limpeza:${NC}"
    stats=$(curl -s "$url/admin/stats")
    echo "$stats" | jq '.'
    
    # Verificar se total_jobs é 0
    total_jobs=$(echo "$stats" | jq -r '.total_jobs // 0')
    
    echo ""
    if [ "$total_jobs" -eq 0 ]; then
        echo -e "${GREEN}✓ Redis zerado (0 jobs)${NC}"
    else
        echo -e "${RED}✗ Redis ainda tem $total_jobs jobs${NC}"
    fi
}

echo "======================================================================"
echo "1. Verificando serviços..."
echo "======================================================================"

services_ok=true

check_service "Video Downloader" "$VIDEO_DOWNLOADER" || services_ok=false
check_service "Audio Normalization" "$AUDIO_NORMALIZATION" || services_ok=false
check_service "Audio Transcriber" "$AUDIO_TRANSCRIBER" || services_ok=false

if [ "$services_ok" = false ]; then
    echo ""
    echo -e "${RED}❌ Alguns serviços estão offline. Inicie-os com:${NC}"
    echo "   docker compose up -d"
    exit 1
fi

echo ""
echo "======================================================================"
echo "2. Estatísticas ANTES da limpeza"
echo "======================================================================"

get_stats "Video Downloader" "$VIDEO_DOWNLOADER"
get_stats "Audio Normalization" "$AUDIO_NORMALIZATION"
get_stats "Audio Transcriber" "$AUDIO_TRANSCRIBER"

echo ""
echo "======================================================================"
echo "3. Executando limpeza TOTAL"
echo "======================================================================"
echo ""
echo -e "${RED}⚠️  ATENÇÃO: Isto irá remover TODOS os jobs, arquivos e modelos!${NC}"
echo -n "Continuar? (y/N): "
read -r response

if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "Operação cancelada."
    exit 0
fi

cleanup "Video Downloader" "$VIDEO_DOWNLOADER"
wait_cleanup "Video Downloader"

cleanup "Audio Normalization" "$AUDIO_NORMALIZATION"
wait_cleanup "Audio Normalization"

cleanup "Audio Transcriber" "$AUDIO_TRANSCRIBER"
wait_cleanup "Audio Transcriber"

echo ""
echo "======================================================================"
echo "4. Verificando resultados"
echo "======================================================================"

verify_cleanup "Video Downloader" "$VIDEO_DOWNLOADER"
verify_cleanup "Audio Normalization" "$AUDIO_NORMALIZATION"
verify_cleanup "Audio Transcriber" "$AUDIO_TRANSCRIBER"

echo ""
echo "======================================================================"
echo "5. Verificando logs"
echo "======================================================================"
echo ""
echo -e "${YELLOW}📝 Logs recentes (últimas 20 linhas):${NC}"
echo ""

echo "--- Video Downloader ---"
docker compose logs --tail=20 video-downloader 2>/dev/null | grep -i "limpeza\|cleanup" || echo "Nenhum log de limpeza"

echo ""
echo "--- Audio Normalization ---"
docker compose logs --tail=20 audio-normalization 2>/dev/null | grep -i "limpeza\|cleanup" || echo "Nenhum log de limpeza"

echo ""
echo "--- Audio Transcriber ---"
docker compose logs --tail=20 audio-transcriber 2>/dev/null | grep -i "limpeza\|cleanup" || echo "Nenhum log de limpeza"

echo ""
echo "======================================================================"
echo "✅ TESTE CONCLUÍDO"
echo "======================================================================"
echo ""
echo "Para ver logs completos:"
echo "  docker compose logs -f video-downloader"
echo "  docker compose logs -f audio-normalization"
echo "  docker compose logs -f audio-transcriber"
echo ""
