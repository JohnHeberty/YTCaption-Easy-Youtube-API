#!/bin/bash
# Validação da Sprint 4 - Integração XTTS + RVC
# TDD: Red-Green-Refactor

set -e

echo "=================================================="
echo "  VALIDAÇÃO SPRINT 4 - INTEGRAÇÃO XTTS + RVC"
echo "=================================================="
echo

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Contadores
PASSED=0
FAILED=0
WARNINGS=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

echo "=== 1. VALIDAR ARQUIVOS CRIADOS ==="
echo

# Testes
if [ -f "tests/test_xtts_rvc_integration.py" ]; then
    lines=$(wc -l < tests/test_xtts_rvc_integration.py)
    if [ "$lines" -gt 300 ]; then
        check_pass "test_xtts_rvc_integration.py criado ($lines linhas)"
    else
        check_fail "test_xtts_rvc_integration.py muito pequeno ($lines linhas)"
    fi
else
    check_fail "test_xtts_rvc_integration.py NÃO encontrado"
fi

echo
echo "=== 2. VALIDAR MODIFICAÇÕES EM xtts_client.py ==="
echo

# Verifica imports RVC
if grep -q "from \.models import.*RvcModel.*RvcParameters" app/xtts_client.py; then
    check_pass "Imports RVC adicionados em xtts_client.py"
else
    check_fail "Imports RVC NÃO encontrados em xtts_client.py"
fi

# Verifica inicialização RVC client
if grep -q "self.rvc_client = None" app/xtts_client.py; then
    check_pass "Inicialização RVC client (lazy load)"
else
    check_fail "RVC client NÃO inicializado"
fi

# Verifica método _load_rvc_client
if grep -q "def _load_rvc_client" app/xtts_client.py; then
    check_pass "Método _load_rvc_client() criado"
else
    check_fail "Método _load_rvc_client() NÃO encontrado"
fi

# Verifica parâmetros RVC em generate_dubbing
if grep -q "enable_rvc: bool = False" app/xtts_client.py; then
    check_pass "Parâmetro enable_rvc adicionado"
else
    check_fail "Parâmetro enable_rvc NÃO encontrado"
fi

if grep -q "rvc_model: Optional" app/xtts_client.py; then
    check_pass "Parâmetro rvc_model adicionado"
else
    check_fail "Parâmetro rvc_model NÃO encontrado"
fi

if grep -q "rvc_params: Optional" app/xtts_client.py; then
    check_pass "Parâmetro rvc_params adicionado"
else
    check_fail "Parâmetro rvc_params NÃO encontrado"
fi

# Verifica ponto de inserção RVC
if grep -q "PONTO DE INSERÇÃO RVC" app/xtts_client.py; then
    check_pass "Ponto de inserção RVC marcado"
else
    check_warn "Comentário de inserção RVC não encontrado"
fi

# Verifica conversão RVC
if grep -q "await self.rvc_client.convert_audio" app/xtts_client.py; then
    check_pass "Chamada RVC convert_audio implementada"
else
    check_fail "Conversão RVC NÃO implementada"
fi

# Verifica fallback
if grep -q -i "fallback" app/xtts_client.py && grep -q "RVC conversion failed" app/xtts_client.py; then
    check_pass "Fallback para XTTS em caso de erro RVC"
else
    check_fail "Fallback RVC NÃO implementado"
fi

echo
echo "=== 3. VALIDAR MODIFICAÇÕES EM processor.py ==="
echo

# Verifica imports
if grep -q "from \.models import.*RvcModel" app/processor.py; then
    check_pass "Imports RVC adicionados em processor.py"
else
    check_fail "Imports RVC NÃO encontrados em processor.py"
fi

# Verifica rvc_model_store
if grep -q "self.rvc_model_store" app/processor.py; then
    check_pass "Atributo rvc_model_store adicionado"
else
    check_fail "rvc_model_store NÃO encontrado"
fi

# Verifica construção de RvcParameters
if grep -q "RvcParameters(" app/processor.py; then
    check_pass "Construção de RvcParameters implementada"
else
    check_fail "RvcParameters NÃO construído no processor"
fi

# Verifica chamada com parâmetros RVC
if grep -q "enable_rvc=" app/processor.py && grep -q "rvc_model=" app/processor.py; then
    check_pass "Parâmetros RVC passados para generate_dubbing()"
else
    check_fail "Parâmetros RVC NÃO passados corretamente"
fi

echo
echo "=== 4. VALIDAR MODIFICAÇÕES EM models.py ==="
echo

# Verifica campos RVC no Job
if grep -q "enable_rvc:" app/models.py; then
    check_pass "Campo enable_rvc adicionado ao Job"
else
    check_fail "Campo enable_rvc NÃO encontrado no Job"
fi

if grep -q "rvc_model_id:" app/models.py; then
    check_pass "Campo rvc_model_id adicionado ao Job"
else
    check_fail "Campo rvc_model_id NÃO encontrado"
fi

if grep -q "rvc_pitch:" app/models.py; then
    check_pass "Campo rvc_pitch adicionado ao Job"
else
    check_fail "Campo rvc_pitch NÃO encontrado"
fi

if grep -q "rvc_f0_method:" app/models.py; then
    check_pass "Campo rvc_f0_method adicionado ao Job"
else
    check_fail "Campo rvc_f0_method NÃO encontrado"
fi

# Conta total de campos RVC (deve ser ~8)
rvc_fields=$(grep -c "rvc_" app/models.py || echo "0")
if [ "$rvc_fields" -ge 8 ]; then
    check_pass "Total de campos RVC no Job: $rvc_fields"
else
    check_fail "Poucos campos RVC: $rvc_fields (esperado ≥8)"
fi

echo
echo "=== 5. VALIDAR ESTRUTURA DOS TESTES ==="
echo

# Verifica classes de teste
if grep -q "class TestXTTSClientRvcIntegration" tests/test_xtts_rvc_integration.py; then
    check_pass "Classe TestXTTSClientRvcIntegration criada"
else
    check_fail "TestXTTSClientRvcIntegration NÃO encontrada"
fi

if grep -q "class TestProcessorRvcIntegration" tests/test_xtts_rvc_integration.py; then
    check_pass "Classe TestProcessorRvcIntegration criada"
else
    check_fail "TestProcessorRvcIntegration NÃO encontrada"
fi

if grep -q "class TestBackwardCompatibility" tests/test_xtts_rvc_integration.py; then
    check_pass "Classe TestBackwardCompatibility criada"
else
    check_fail "TestBackwardCompatibility NÃO encontrada"
fi

# Conta testes
test_count=$(grep -c "async def test_" tests/test_xtts_rvc_integration.py || echo "0")
if [ "$test_count" -ge 10 ]; then
    check_pass "Total de testes: $test_count (≥10 esperado)"
else
    check_warn "Poucos testes: $test_count (recomendado ≥10)"
fi

# Verifica fixtures
if grep -q "@pytest.fixture" tests/test_xtts_rvc_integration.py; then
    fixtures=$(grep -c "@pytest.fixture" tests/test_xtts_rvc_integration.py || echo "0")
    check_pass "Fixtures criadas: $fixtures"
else
    check_warn "Nenhuma fixture encontrada"
fi

echo
echo "=== 6. VALIDAR BACKWARD COMPATIBILITY ==="
echo

# Verifica defaults opcionais
if grep -q "enable_rvc: bool = False" app/xtts_client.py; then
    check_pass "enable_rvc é opcional (default=False)"
else
    check_fail "enable_rvc NÃO é opcional"
fi

if grep -q "rvc_model: Optional" app/xtts_client.py && grep -q "= None" app/xtts_client.py; then
    check_pass "rvc_model é opcional (default=None)"
else
    check_fail "rvc_model NÃO é opcional"
fi

if grep -q "rvc_params: Optional" app/xtts_client.py && grep -q "= None" app/xtts_client.py; then
    check_pass "rvc_params é opcional (default=None)"
else
    check_fail "rvc_params NÃO é opcional"
fi

# Verifica teste de compatibilidade
if grep -q "test_old_code_still_works" tests/test_xtts_rvc_integration.py; then
    check_pass "Teste de backward compatibility implementado"
else
    check_warn "Teste de backward compat não encontrado"
fi

echo
echo "=== 7. RESUMO DA SPRINT 4 ==="
echo

# Conta arquivos modificados
modified_files=0
[ -f "app/xtts_client.py" ] && ((modified_files++))
[ -f "app/processor.py" ] && ((modified_files++))
[ -f "app/models.py" ] && ((modified_files++))

# Conta arquivos criados
created_files=0
[ -f "tests/test_xtts_rvc_integration.py" ] && ((created_files++))

echo "Arquivos modificados: $modified_files"
echo "Arquivos criados: $created_files"
echo

# Conta linhas totais de código Sprint 4
xtts_lines=$(wc -l < app/xtts_client.py)
processor_lines=$(wc -l < app/processor.py)
models_lines=$(wc -l < app/models.py)
test_lines=$(wc -l < tests/test_xtts_rvc_integration.py)

total_lines=$((xtts_lines + processor_lines + models_lines + test_lines))

echo "Total de linhas (todos arquivos): $total_lines"
echo "  - xtts_client.py: $xtts_lines linhas"
echo "  - processor.py: $processor_lines linhas"
echo "  - models.py: $models_lines linhas"
echo "  - test_xtts_rvc_integration.py: $test_lines linhas"
echo

echo "=================================================="
echo -e "${GREEN}Checks passaram:${NC} $PASSED"
if [ "$WARNINGS" -gt 0 ]; then
    echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
fi
if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}Checks falharam:${NC} $FAILED"
fi
echo "=================================================="
echo

# Resultado final
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}✓ SPRINT 4 VALIDADA COM SUCESSO!${NC}"
    echo
    echo "Próximos passos:"
    echo "1. Rodar testes no Docker:"
    echo "   docker-compose -f docker-compose-gpu.yml run --rm audio-voice-service pytest tests/test_xtts_rvc_integration.py -v"
    echo
    echo "2. Após testes passarem (Green Phase), implementar Sprint 5 (Unit Tests Suite)"
    exit 0
else
    echo -e "${RED}✗ SPRINT 4 INCOMPLETA${NC}"
    echo "Corrija os erros acima antes de prosseguir."
    exit 1
fi
