#!/bin/bash
# 🧪 Script de Teste - Audio Transcriber Service
# Testa transcrição após correção do bug circuit breaker

set -e

echo "========================================================================"
echo "🧪 TESTE DE TRANSCRIÇÃO - Audio Transcriber"
echo "========================================================================"
echo ""

# Configuração
API_URL="${API_URL:-http://localhost:8004}"
TEST_FILE="/root/YTCaption-Easy-Youtube-API/services/audio-transcriber/tests/TEST-.ogg"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "📍 API URL: $API_URL"
echo "📁 Arquivo de teste: $TEST_FILE"
echo ""

# Verifica se arquivo existe
if [ ! -f "$TEST_FILE" ]; then
    echo -e "${RED}❌ Arquivo de teste não encontrado: $TEST_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Arquivo de teste encontrado ($(stat -c%s "$TEST_FILE") bytes)${NC}"
echo ""

# Teste 1: Health check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 TESTE 1: Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

HEALTH_RESPONSE=$(curl -s "$API_URL/health" || echo "error")

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✅ Serviço healthy${NC}"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    echo -e "${RED}❌ Serviço não está healthy${NC}"
    echo "$HEALTH_RESPONSE"
    exit 1
fi

echo ""

# Teste 2: Upload e transcrição
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎤 TESTE 2: Transcrição de Áudio"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "📤 Enviando arquivo para transcrição..."

RESPONSE=$(curl -s -X POST "$API_URL/jobs" \
  -F "file=@$TEST_FILE" \
  -F "language_in=auto" \
  -F "operation=transcribe")

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Extrai job_id
JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('id', data.get('job_id', '')))" 2>/dev/null || echo "")

if [ -z "$JOB_ID" ]; then
    echo -e "${RED}❌ Falha ao criar job de transcrição${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Job criado: $JOB_ID${NC}"
echo ""

# Aguarda processamento
echo "⏳ Aguardando processamento (máximo 60s)..."
echo ""

MAX_ATTEMPTS=60
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
    
    STATUS_RESPONSE=$(curl -s "$API_URL/jobs/$JOB_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null || echo "")
    
    echo -n "."
    
    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo ""
        echo -e "${GREEN}✅ Transcrição COMPLETA!${NC}"
        echo ""
        echo "Resultado:"
        echo "$STATUS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$STATUS_RESPONSE"
        
        # Valida resultado
        TEXT=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('transcription_text', ''))" 2>/dev/null || echo "")
        
        if [ -n "$TEXT" ]; then
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo -e "${GREEN}✅ TESTE PASSOU - Transcrição funcionando!${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "📝 Texto transcrito (prévia):"
            echo "   \"${TEXT:0:200}...\""
            echo ""
            exit 0
        fi
    elif [ "$STATUS" = "failed" ]; then
        echo ""
        echo ""
        echo -e "${RED}❌ Transcrição FALHOU${NC}"
        echo ""
        echo "Detalhes do erro:"
        echo "$STATUS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$STATUS_RESPONSE"
        echo ""
        
        ERROR_MSG=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error_message', ''))" 2>/dev/null || echo "")
        
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "${RED}❌ TESTE FALHOU${NC}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Erro: $ERROR_MSG"
        echo ""
        
        if echo "$ERROR_MSG" | grep -q "get_circuit_breaker"; then
            echo -e "${YELLOW}⚠️  Erro de circuit_breaker ainda presente!${NC}"
            echo "   Possíveis causas:"
            echo "   1. Cache Python (.pyc) ainda não foi limpo"
            echo "   2. Container precisa ser reconstruído (não apenas restart)"
            echo ""
            echo "   Solução:"
            echo "   cd /root/YTCaption-Easy-Youtube-API/services/audio-transcriber"
            echo "   docker-compose down"
            echo "   docker-compose up -d --build"
        fi
        
        exit 1
    fi
done

echo ""
echo ""
echo -e "${YELLOW}⚠️  TIMEOUT - Transcrição não completou em 60s${NC}"
echo "   Status atual: $STATUS"
echo ""
echo "   Verifique logs:"
echo "   docker logs audio-transcriber-celery --tail 50"
exit 2
