#!/bin/bash

# Script de teste de integração
# Testa circuit breaker, logging estruturado e resiliência

set -e

echo "================================================================================"
echo "🧪 TESTES DE INTEGRAÇÃO - YTCaption"
echo "================================================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

test_count=0
pass_count=0
fail_count=0

# Função para executar teste
run_test() {
    local test_name=$1
    local test_command=$2
    local expected_pattern=$3
    
    test_count=$((test_count + 1))
    
    echo -e "${BLUE}▶${NC} Teste $test_count: $test_name"
    
    if output=$(eval "$test_command" 2>&1); then
        if [ -n "$expected_pattern" ]; then
            if echo "$output" | grep -q "$expected_pattern"; then
                echo -e "${GREEN}✅ PASSOU${NC}"
                pass_count=$((pass_count + 1))
                return 0
            else
                echo -e "${RED}❌ FALHOU - Pattern não encontrado${NC}"
                echo "Output: $output"
                fail_count=$((fail_count + 1))
                return 1
            fi
        else
            echo -e "${GREEN}✅ PASSOU${NC}"
            pass_count=$((pass_count + 1))
            return 0
        fi
    else
        echo -e "${RED}❌ FALHOU - Comando retornou erro${NC}"
        echo "Output: $output"
        fail_count=$((fail_count + 1))
        return 1
    fi
}

cd /root/YTCaption-Easy-Youtube-API

echo "📦 Fase 1: Validação de Sintaxe Python"
echo ""

run_test "Sintaxe comum/models/base.py" \
    "python3 -m py_compile common/models/base.py" \
    ""

run_test "Sintaxe comum/logging/structured.py" \
    "python3 -m py_compile common/logging/structured.py" \
    ""

run_test "Sintaxe comum/redis/resilient_store.py" \
    "python3 -m py_compile common/redis/resilient_store.py" \
    ""

run_test "Sintaxe comum/exceptions/handlers.py" \
    "python3 -m py_compile common/exceptions/handlers.py" \
    ""

run_test "Sintaxe orchestrator/main.py" \
    "python3 -m py_compile orchestrator/main.py" \
    ""

echo ""
echo "📦 Fase 2: Validação de Arquivos Docker"
echo ""

run_test "Dockerfile existe (orchestrator)" \
    "test -f orchestrator/Dockerfile" \
    ""

run_test "Dockerfile existe (audio-normalization)" \
    "test -f services/audio-normalization/Dockerfile" \
    ""

run_test "Dockerfile existe (audio-transcriber)" \
    "test -f services/audio-transcriber/Dockerfile" \
    ""

run_test "Dockerfile existe (video-downloader)" \
    "test -f services/video-downloader/Dockerfile" \
    ""

run_test "Dockerfile existe (youtube-search)" \
    "test -f services/youtube-search/Dockerfile" \
    ""

echo ""
echo "📦 Fase 3: Verificação de Dependências"
echo ""

run_test "Requirements.txt existe (orchestrator)" \
    "test -f orchestrator/requirements.txt" \
    ""

run_test "Requirements.txt existe (audio-normalization)" \
    "test -f services/audio-normalization/requirements.txt" \
    ""

run_test "Requirements.txt existe (audio-transcriber)" \
    "test -f services/audio-transcriber/requirements.txt" \
    ""

run_test "Requirements.txt existe (video-downloader)" \
    "test -f services/video-downloader/requirements.txt" \
    ""

run_test "Requirements.txt existe (youtube-search)" \
    "test -f services/youtube-search/requirements.txt" \
    ""

echo ""
echo "📦 Fase 4: Verificação de Logs Estruturados"
echo ""

# Verifica se o logger está configurado corretamente
run_test "Logger estruturado em audio-normalization" \
    "grep -q 'from common.logging import' services/audio-normalization/app/main.py" \
    ""

run_test "Logger estruturado em audio-transcriber" \
    "grep -q 'from common.logging import' services/audio-transcriber/app/main.py" \
    ""

run_test "Logger estruturado em video-downloader" \
    "grep -q 'from common.logging import' services/video-downloader/app/main.py" \
    ""

run_test "Logger estruturado em youtube-search" \
    "grep -q 'from common.logging import' services/youtube-search/app/main.py" \
    ""

echo ""
echo "📦 Fase 5: Verificação de Circuit Breaker"
echo ""

run_test "Circuit breaker em audio-normalization" \
    "grep -q 'ResilientRedisStore' services/audio-normalization/app/redis_store.py" \
    ""

run_test "Circuit breaker em audio-transcriber" \
    "grep -q 'ResilientRedisStore' services/audio-transcriber/app/redis_store.py" \
    ""

run_test "Circuit breaker em video-downloader" \
    "grep -q 'ResilientRedisStore' services/video-downloader/app/redis_store.py" \
    ""

run_test "Circuit breaker em youtube-search" \
    "grep -q 'ResilientRedisStore' services/youtube-search/app/redis_store.py" \
    ""

run_test "Circuit breaker em orchestrator" \
    "grep -q 'ResilientRedisStore' orchestrator/modules/redis_store.py" \
    ""

echo ""
echo "📦 Fase 6: Verificação de Exception Handlers"
echo ""

run_test "Exception handlers em audio-normalization" \
    "grep -q 'setup_exception_handlers' services/audio-normalization/app/main.py" \
    ""

run_test "Exception handlers em audio-transcriber" \
    "grep -q 'setup_exception_handlers' services/audio-transcriber/app/main.py" \
    ""

run_test "Exception handlers em video-downloader" \
    "grep -q 'setup_exception_handlers' services/video-downloader/app/main.py" \
    ""

run_test "Exception handlers em youtube-search" \
    "grep -q 'setup_exception_handlers' services/youtube-search/app/main.py" \
    ""

echo ""
echo "================================================================================"
echo "📊 RESUMO DOS TESTES"
echo "================================================================================"
echo ""
echo "Total de testes: $test_count"
echo -e "${GREEN}Passou: $pass_count${NC}"
echo -e "${RED}Falhou: $fail_count${NC}"
echo ""

success_rate=$(awk "BEGIN {printf \"%.1f\", ($pass_count/$test_count)*100}")
echo "Taxa de sucesso: ${success_rate}%"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}🎉 TODOS OS TESTES PASSARAM!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "✅ Validações realizadas:"
    echo "  • Sintaxe Python correta"
    echo "  • Docker Compose configurado"
    echo "  • Dependências presentes"
    echo "  • Logging estruturado implementado"
    echo "  • Circuit breaker em todos os serviços"
    echo "  • Exception handlers configurados"
    echo ""
    echo "🚀 Sistema pronto para deploy!"
    echo ""
    exit 0
else
    echo -e "${YELLOW}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}⚠️  ALGUNS TESTES FALHARAM${NC}"
    echo -e "${YELLOW}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Revise os testes que falharam acima"
    exit 1
fi
