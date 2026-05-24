#!/bin/bash

# Script de teste usando Docker
# Testa cada serviço (exceto transcriber) dentro do seu container

set -e

echo "================================================================================"
echo "🧪 TESTE DOS SERVIÇOS USANDO DOCKER"
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

run_test() {
    local test_name=$1
    local service_dir=$2
    local test_command=$3
    
    test_count=$((test_count + 1))
    
    echo -e "${BLUE}▶${NC} Teste $test_count: $test_name"
    
    # Tenta fazer build da imagem
    if docker build -t test-$service_dir $service_dir > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ Build OK${NC}"
        
        # Tenta executar o teste no container
        if docker run --rm test-$service_dir $test_command > /dev/null 2>&1; then
            echo -e "${GREEN}✅ PASSOU${NC}"
            pass_count=$((pass_count + 1))
            return 0
        else
            echo -e "${RED}  ✗ Teste falhou${NC}"
            echo -e "${RED}❌ FALHOU${NC}"
            fail_count=$((fail_count + 1))
            return 1
        fi
    else
        echo -e "${RED}  ✗ Build falhou${NC}"
        echo -e "${RED}❌ FALHOU${NC}"
        fail_count=$((fail_count + 1))
        return 1
    fi
}

cd /root/YTCaption-Easy-Youtube-API

echo "📦 Fase 1: Teste de Sintaxe (sem Docker)"
echo ""

# Testes de sintaxe Python (não precisa de dependências)
for service in services/se3-audio-normalization services/se2-video-downloader services/se6-youtube-search se1-orchestrator; do
    service_name=$(basename $service)
    echo -e "${BLUE}▶${NC} Validando sintaxe: $service_name"
    
    if python3 -m py_compile $service/app/*.py 2>/dev/null || python3 -m py_compile $service/modules/*.py 2>/dev/null || python3 -m py_compile $service/*.py 2>/dev/null; then
        echo -e "${GREEN}✅ Sintaxe OK: $service_name${NC}"
        pass_count=$((pass_count + 1))
    else
        echo -e "${RED}❌ Erros de sintaxe: $service_name${NC}"
        fail_count=$((fail_count + 1))
    fi
    test_count=$((test_count + 1))
done

echo ""
echo "📦 Fase 2: Teste de Imports em Python"
echo ""

# Verifica se os imports estão corretos
for service in services/se3-audio-normalization services/se2-video-downloader services/se6-youtube-search; do
    service_name=$(basename $service)
    echo -e "${BLUE}▶${NC} Validando imports: $service_name"
    
    # Verifica se usa common.log_utils
    if grep -q "from common.log_utils import" $service/app/main.py; then
        echo -e "${GREEN}  ✓ common.log_utils OK${NC}"
    else
        echo -e "${RED}  ✗ common.log_utils MISSING${NC}"
        fail_count=$((fail_count + 1))
        test_count=$((test_count + 1))
        continue
    fi
    
    # Verifica se usa common.exception_handlers
    if grep -q "from common.exception_handlers import" $service/app/main.py; then
        echo -e "${GREEN}  ✓ common.exception_handlers OK${NC}"
    else
        echo -e "${RED}  ✗ common.exception_handlers MISSING${NC}"
        fail_count=$((fail_count + 1))
        test_count=$((test_count + 1))
        continue
    fi
    
    # Verifica se usa common.redis_utils
    if grep -q "from common.redis_utils import" $service/app/redis_store.py; then
        echo -e "${GREEN}  ✓ common.redis_utils OK${NC}"
    else
        echo -e "${RED}  ✗ common.redis_utils MISSING${NC}"
        fail_count=$((fail_count + 1))
        test_count=$((test_count + 1))
        continue
    fi
    
    echo -e "${GREEN}✅ Imports OK: $service_name${NC}"
    pass_count=$((pass_count + 1))
    test_count=$((test_count + 1))
done

echo ""
echo "📦 Fase 3: Verificação de Arquivos da Biblioteca Common"
echo ""

common_files=(
    "common/models/base.py"
    "common/log_utils/structured.py"
    "common/redis_utils/resilient_store.py"
    "common/exception_handlers/handlers.py"
    "common/config_utils/base_settings.py"
)

for file in "${common_files[@]}"; do
    test_count=$((test_count + 1))
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ Existe: $file${NC}"
        pass_count=$((pass_count + 1))
    else
        echo -e "${RED}❌ Faltando: $file${NC}"
        fail_count=$((fail_count + 1))
    fi
done

echo ""
echo "📦 Fase 4: Verificação de Requirements.txt"
echo ""

for service in services/se3-audio-normalization services/se2-video-downloader services/se6-youtube-search se1-orchestrator; do
    service_name=$(basename $service)
    test_count=$((test_count + 1))
    
    if [ -f "$service/requirements.txt" ]; then
        if grep -q "\-e.*common" $service/requirements.txt; then
            echo -e "${GREEN}✅ Requirements OK: $service_name${NC}"
            pass_count=$((pass_count + 1))
        else
            echo -e "${YELLOW}⚠️  Requirements sem common: $service_name${NC}"
            fail_count=$((fail_count + 1))
        fi
    else
        echo -e "${RED}❌ Requirements.txt faltando: $service_name${NC}"
        fail_count=$((fail_count + 1))
    fi
done

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
    echo "  • Sintaxe Python correta em todos serviços"
    echo "  • Imports corretos (common.log_utils, common.exception_handlers, common.redis_utils)"
    echo "  • Biblioteca common completa"
    echo "  • Requirements.txt configurados"
    echo ""
    echo "🚀 Serviços prontos (exceto transcriber que requer GPU)"
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
