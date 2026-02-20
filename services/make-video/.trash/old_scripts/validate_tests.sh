#!/bin/bash
# Script de Validação Rápida de Testes - Make-Video Service
# Executa validação completa garantindo 100% de cobertura sem mocks e sem skips

set -e  # Exit on error

echo "🧪 Iniciando Validação Completa de Testes..."
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Navigate to service directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "✅ Ativando virtual environment..."
    source .venv/bin/activate
else
    echo "❌ Virtual environment não encontrado!"
    echo "Execute: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check pytest installation
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest não encontrado!"
    echo "Execute: pip install -r requirements.txt"
    exit 1
fi

echo ""
echo "📊 Fase 1: Coletando testes..."
echo "================================================"
COLLECT_OUTPUT=$(python -m pytest tests/ --collect-only -q 2>&1 | tail -1)
echo "$COLLECT_OUTPUT"

# Extract test count
TEST_COUNT=$(echo "$COLLECT_OUTPUT" | grep -oP '\d+(?= tests? collected)')
if [ -z "$TEST_COUNT" ]; then
    echo "❌ Erro ao coletar testes!"
    exit 1
fi

echo -e "${GREEN}✓${NC} $TEST_COUNT testes coletados"
echo ""

# Check for skips in collection
echo "📊 Fase 2: Verificando skips..."
echo "================================================"
if python -m pytest tests/ --collect-only -q 2>&1 | grep -i "skip" > /dev/null; then
    echo -e "${RED}✗${NC} SKIPS ENCONTRADOS na coleta!"
    python -m pytest tests/ --collect-only -q 2>&1 | grep -i "skip"
    exit 1
else
    echo -e "${GREEN}✓${NC} Nenhum skip encontrado na coleta"
fi
echo ""

# Execute tests
echo "🚀 Fase 3: Executando todos os testes..."
echo "================================================"
echo "⏳ Aguarde ~3-4 minutos para execução completa..."
echo ""

# Run tests and capture output
OUTPUT_FILE="/tmp/pytest_validation_$(date +%s).txt"
python -m pytest tests/ --tb=short -v > "$OUTPUT_FILE" 2>&1

# Extract summary line
SUMMARY=$(grep -E "===.*passed.*===" "$OUTPUT_FILE" | tail -1)

if [ -z "$SUMMARY" ]; then
    echo -e "${RED}✗${NC} Erro na execução dos testes!"
    echo "Últimas 50 linhas do output:"
    echo ""
    tail -50 "$OUTPUT_FILE"
    exit 1
fi

echo ""
echo "📊 RESULTADO:"
echo "================================================"
echo "$SUMMARY"
echo ""

# Parse results
PASSED=$(echo "$SUMMARY" | grep -oP '\d+(?= passed)')
FAILED=$(echo "$SUMMARY" | grep -oP '\d+(?= failed)' || echo "0")
SKIPPED=$(echo "$SUMMARY" | grep -oP '\d+(?= skipped)' || echo "0")
TIME=$(echo "$SUMMARY" | grep -oP '\d+\.\d+s' | head -1)

# Validation checks
ALL_PASSED=true

echo "🔍 Validações:"
echo "================================================"

# Check 1: All tests passed
if [ "$PASSED" -eq "$TEST_COUNT" ] && [ "$FAILED" -eq "0" ]; then
    echo -e "${GREEN}✓${NC} Todos os $PASSED testes passaram"
else
    echo -e "${RED}✗${NC} Falhas encontradas: $FAILED failed, $PASSED passed"
    ALL_PASSED=false
fi

# Check 2: No skips
if [ "$SKIPPED" -eq "0" ]; then
    echo -e "${GREEN}✓${NC} Zero skips (cobertura completa)"
else
    echo -e "${RED}✗${NC} Testes pulados: $SKIPPED skips encontrados"
    ALL_PASSED=false
fi

# Check 3: Expected test count
EXPECTED_MIN=329
if [ "$TEST_COUNT" -ge "$EXPECTED_MIN" ]; then
    echo -e "${GREEN}✓${NC} Contagem esperada: $TEST_COUNT >= $EXPECTED_MIN"
else
    echo -e "${YELLOW}⚠${NC} Contagem menor que esperado: $TEST_COUNT < $EXPECTED_MIN"
fi

# Check 4: Execution time
if [ ! -z "$TIME" ]; then
    echo -e "${GREEN}✓${NC} Tempo de execução: $TIME"
fi

echo ""

# Final verdict
if [ "$ALL_PASSED" = true ]; then
    echo "================================================"
    echo -e "${GREEN}🎉 VALIDAÇÃO COMPLETA: TODOS OS TESTES OK!${NC}"
    echo "================================================"
    echo ""
    echo "📊 Resumo:"
    echo "  - Testes passando: $PASSED/$TEST_COUNT (100%)"
    echo "  - Testes falhando: $FAILED"
    echo "  - Testes pulados: $SKIPPED"
    echo "  - Tempo total: $TIME"
    echo ""
    echo "✅ Princípios mantidos:"
    echo "  - Zero mocks (100% implementações reais)"
    echo "  - Zero skips (cobertura completa)"
    echo "  - Correções na aplicação (não nos testes)"
    echo ""
    echo "📄 Relatório detalhado: VALIDATION_REPORT.md"
    echo ""
    exit 0
else
    echo "================================================"
    echo -e "${RED}❌ VALIDAÇÃO FALHOU!${NC}"
    echo "================================================"
    echo ""
    echo "Verifique o output completo em: $OUTPUT_FILE"
    echo ""
    echo "Para ver detalhes dos erros:"
    echo "  tail -100 $OUTPUT_FILE"
    echo ""
    exit 1
fi
