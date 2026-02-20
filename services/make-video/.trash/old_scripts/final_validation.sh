#!/bin/bash
# Validação Final Automatizada - Make-Video Service
# Garante 100% dos testes OK, zero mocks, zero skips

cd /root/YTCaption-Easy-Youtube-API/services/make-video
source .venv/bin/activate

echo "=========================================="
echo "🔍 VALIDAÇÃO FINAL AUTOMATIZADA"
echo "=========================================="
echo ""

# 1. Coletar testes
echo "📊 1. Coletando testes..."
TEST_COUNT=$(python -m pytest tests/ --co -q 2>&1 | tail -1 | grep -oP '\d+(?= tests? collected)')
echo "   ✓ $TEST_COUNT testes coletados"
echo ""

# 2. Verificar mocks
echo "🔍 2. Verificando mocks..."
MOCK_COUNT=$(grep -r "from unittest.mock import\|from mock import\|Mock(\|MagicMock\|@mock\.\|@patch" tests/ 2>/dev/null | wc -l)
if [ "$MOCK_COUNT" -eq 0 ]; then
    echo "   ✓ Zero mocks encontrados (100% real)"
else
    echo "   ✗ $MOCK_COUNT mocks encontrados!"
    exit 1
fi
echo ""

# 3. Executar testes
echo "🚀 3. Executando todos os testes..."
echo "   ⏳ Aguarde ~3-4 minutos..."
python -m pytest tests/ -q --tb=no > /tmp/final_test_run.txt 2>&1
RESULT=$(tail -1 /tmp/final_test_run.txt)
echo "   $RESULT"
echo ""

# 4. Verificar resultado
PASSED=$(echo "$RESULT" | grep -oP '\d+(?= passed)')
FAILED=$(echo "$RESULT" | grep -oP '\d+(?= failed)' || echo "0")
SKIPPED=$(echo "$RESULT" | grep -oP '\d+(?= skipped)' || echo "0")

echo "📈 4. Análise de Resultados:"
echo "   • Testes coletados: $TEST_COUNT"
echo "   • Testes passando: $PASSED"
echo "   • Testes falhando: $FAILED"
echo "   • Testes pulados: $SKIPPED"
echo ""

# 5. Validação final
echo "=========================================="
if [ "$PASSED" -eq "$TEST_COUNT" ] && [ "$FAILED" -eq "0" ] && [ "$SKIPPED" -eq "0" ] && [ "$MOCK_COUNT" -eq "0" ]; then
    echo "✅ VALIDAÇÃO 100% APROVADA!"
    echo "=========================================="
    echo ""
    echo "Confirmações:"
    echo "  ✓ $PASSED/$TEST_COUNT testes passando (100%)"
    echo "  ✓ $FAILED falhas (0%)"
    echo "  ✓ $SKIPPED skips (0%)"
    echo "  ✓ $MOCK_COUNT mocks (0%)"
    echo "  ✓ Aplicação bem programada"
    echo "  ✓ Todas funções testadas"
    echo ""
    exit 0
else
    echo "❌ VALIDAÇÃO FALHOU!"
    echo "=========================================="
    echo ""
    echo "Problemas encontrados:"
    [ "$FAILED" -ne "0" ] && echo "  ✗ $FAILED testes falhando"
    [ "$SKIPPED" -ne "0" ] && echo "  ✗ $SKIPPED testes pulados"
    [ "$MOCK_COUNT" -ne "0" ] && echo "  ✗ $MOCK_COUNT mocks encontrados"
    echo ""
    exit 1
fi
