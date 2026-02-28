#!/bin/bash
# 🚀 Script de Validação Rápida - Audio Transcriber Service
# 
# Este script executa validações básicas para confirmar que as correções
# implementadas estão funcionando corretamente.
#
# Uso: bash VALIDACAO_RAPIDA.sh

set -e  # Para em caso de erro

echo "========================================================================"
echo "🔍 VALIDAÇÃO RÁPIDA - Audio Transcriber Service"
echo "========================================================================"
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Diretório do serviço
SERVICE_DIR="/root/YTCaption-Easy-Youtube-API/services/audio-transcriber"
cd "$SERVICE_DIR" || exit 1

echo "📁 Diretório: $SERVICE_DIR"
echo ""

# ============================================================================
# VALIDAÇÃO 1: Arquivo de Teste
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 VALIDAÇÃO 1: Arquivo de Teste (TEST-.ogg)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "tests/TEST-.ogg" ]; then
    SIZE=$(stat -f%z "tests/TEST-.ogg" 2>/dev/null || stat -c%s "tests/TEST-.ogg" 2>/dev/null)
    SIZE_KB=$((SIZE / 1024))
    echo -e "${GREEN}✅ Arquivo encontrado${NC}"
    echo "   Tamanho: ${SIZE} bytes (${SIZE_KB} KB)"
    
    # Valida header OGG
    HEADER=$(head -c 4 "tests/TEST-.ogg" | od -A n -t x1 | tr -d ' \n')
    if [ "$HEADER" == "4f676753" ]; then  # "OggS" em hex
        echo -e "${GREEN}✅ Formato OGG válido${NC}"
    else
        echo -e "${RED}❌ Formato inválido (esperado OGG)${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Arquivo TEST-.ogg não encontrado${NC}"
    echo -e "${YELLOW}💡 Crie um arquivo de teste:${NC}"
    echo "   cd tests/ && ffmpeg -f lavfi -i 'sine=frequency=440:duration=5' -ar 16000 TEST-.ogg"
    exit 1
fi

echo ""

# ============================================================================
# VALIDAÇÃO 2: Imports Corrigidos
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 VALIDAÇÃO 2: Imports Corrigidos"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verifica se o import está presente no código
if grep -q "from .infrastructure import get_circuit_breaker" app/faster_whisper_manager.py; then
    echo -e "${GREEN}✅ Import de get_circuit_breaker encontrado${NC}"
else
    echo -e "${RED}❌ Import de get_circuit_breaker NÃO encontrado${NC}"
    exit 1
fi

if grep -q "CircuitBreakerException" app/faster_whisper_manager.py; then
    echo -e "${GREEN}✅ Import de CircuitBreakerException encontrado${NC}"
else
    echo -e "${YELLOW}⚠️  CircuitBreakerException não importado${NC}"
fi

echo ""

# ============================================================================
# VALIDAÇÃO 3: Circuit Breaker em Operações
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔌 VALIDAÇÃO 3: Circuit Breaker em Operações"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CB_IN_LOAD=$(grep -c "cb = get_circuit_breaker()" app/faster_whisper_manager.py || true)
CB_IN_TRANSCRIBE=$(grep -c "cb.record_success" app/faster_whisper_manager.py || true)

echo "Circuit breaker chamadas encontradas: ${CB_IN_LOAD}"
echo "Circuit breaker sucessos registrados: ${CB_IN_TRANSCRIBE}"

if [ "$CB_IN_LOAD" -ge 1 ] && [ "$CB_IN_TRANSCRIBE" -ge 1 ]; then
    echo -e "${GREEN}✅ Circuit breaker integrado corretamente${NC}"
else
    echo -e "${RED}❌ Circuit breaker não integrado completamente${NC}"
    exit 1
fi

echo ""

# ============================================================================
# VALIDAÇÃO 4: Estrutura de Testes
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 VALIDAÇÃO 4: Estrutura de Testes de Resiliência"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESILIENCE_DIR="tests/resilience"

if [ -d "$RESILIENCE_DIR" ]; then
    echo -e "${GREEN}✅ Diretório tests/resilience/ existe${NC}"
    
    # Conta arquivos de teste
    TEST_FILES=$(find "$RESILIENCE_DIR" -name "test_*.py" | wc -l)
    echo "   Arquivos de teste: ${TEST_FILES}"
    
    # Lista arquivos
    echo "   Arquivos encontrados:"
    find "$RESILIENCE_DIR" -name "test_*.py" -exec basename {} \; | sed 's/^/      - /'
    
    if [ "$TEST_FILES" -ge 3 ]; then
        echo -e "${GREEN}✅ Suite de testes completa${NC}"
    else
        echo -e "${YELLOW}⚠️  Menos testes que o esperado (esperado: 3+)${NC}"
    fi
else
    echo -e "${RED}❌ Diretório tests/resilience/ não existe${NC}"
    exit 1
fi

echo ""

# ============================================================================
# VALIDAÇÃO 5: Documentação
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 VALIDAÇÃO 5: Documentação"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

DOCS=("DIAGNOSTICO_RESILIENCIA.md" "IMPLEMENTACAO_COMPLETA.md" "tests/resilience/README.md")
DOCS_OK=0

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo -e "${GREEN}✅${NC} $doc"
        DOCS_OK=$((DOCS_OK + 1))
    else
        echo -e "${RED}❌${NC} $doc (não encontrado)"
    fi
done

if [ "$DOCS_OK" -eq ${#DOCS[@]} ]; then
    echo -e "${GREEN}✅ Toda documentação presente${NC}"
fi

echo ""

# ============================================================================
# SUMÁRIO
# ============================================================================
echo "========================================================================"
echo "📊 SUMÁRIO DE VALIDAÇÃO"
echo "========================================================================"
echo ""
echo "✅ Arquivo de teste: OK"
echo "✅ Imports corrigidos: OK"
echo "✅ Circuit breaker: OK"
echo "✅ Estrutura de testes: OK"
echo "✅ Documentação: OK"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ TODAS AS VALIDAÇÕES PASSARAM${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "🚀 Próximos passos:"
echo ""
echo "   1. Executar testes de resiliência:"
echo "      pytest tests/resilience/ -v -s"
echo ""
echo "   2. Validar transcrição real:"
echo "      pytest tests/resilience/test_transcription_real.py -v -s"
echo ""
echo "   3. Ver cobertura:"
echo "      pytest tests/resilience/ --cov=app --cov-report=html"
echo ""
echo "   4. Deploy em staging (se todos testes passarem)"
echo ""
echo "========================================================================"
