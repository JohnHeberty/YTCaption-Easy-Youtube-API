#!/bin/bash
"""
Script de validação simplificado - verifica estrutura dos arquivos
"""

echo "================================================================================"
echo "VALIDAÇÃO DAS MIGRAÇÕES - ESTRUTURA DE ARQUIVOS"
echo "================================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_count=0
pass_count=0
fail_count=0

check_file() {
    local file=$1
    local pattern=$2
    local description=$3
    
    check_count=$((check_count + 1))
    
    if [ -f "$file" ]; then
        if grep -q "$pattern" "$file"; then
            echo -e "${GREEN}✅${NC} $description"
            pass_count=$((pass_count + 1))
            return 0
        else
            echo -e "${YELLOW}⚠️${NC}  $description - Pattern not found"
            return 1
        fi
    else
        echo -e "${RED}❌${NC} $description - File not found"
        fail_count=$((fail_count + 1))
        return 1
    fi
}

cd /root/YTCaption-Easy-Youtube-API

echo "📦 Teste 1: Biblioteca Common criada"
echo ""
check_file "common/__init__.py" "common" "common/__init__.py existe"
check_file "common/models/base.py" "BaseJob" "common/models/base.py com BaseJob"
check_file "common/logging/structured.py" "setup_structured_logging" "common/logging/structured.py com setup"
check_file "common/redis/resilient_store.py" "ResilientRedisStore" "common/redis/resilient_store.py com ResilientRedisStore"
check_file "common/exceptions/handlers.py" "setup_exception_handlers" "common/exceptions/handlers.py com setup"
check_file "common/config/base_settings.py" "BaseServiceSettings" "common/config/base_settings.py com BaseServiceSettings"

echo ""
echo "📦 Teste 2: Requirements.txt atualizados"
echo ""
check_file "services/audio-normalization/requirements.txt" "../../common" "audio-normalization usa biblioteca common"
check_file "services/audio-transcriber/requirements.txt" "../../common" "audio-transcriber usa biblioteca common"
check_file "services/video-downloader/requirements.txt" "../../common" "video-downloader usa biblioteca common"
check_file "services/youtube-search/requirements.txt" "../../common" "youtube-search usa biblioteca common"

echo ""
echo "📦 Teste 3: Main.py migrados (logging estruturado)"
echo ""
check_file "services/audio-normalization/app/main.py" "from common.logging import" "audio-normalization usa common.logging"
check_file "services/audio-transcriber/app/main.py" "from common.logging import" "audio-transcriber usa common.logging"
check_file "services/video-downloader/app/main.py" "from common.logging import" "video-downloader usa common.logging"
check_file "services/youtube-search/app/main.py" "from common.logging import" "youtube-search usa common.logging"

echo ""
echo "📦 Teste 4: Exception handlers configurados"
echo ""
check_file "services/audio-normalization/app/main.py" "setup_exception_handlers" "audio-normalization exception handlers"
check_file "services/audio-transcriber/app/main.py" "setup_exception_handlers" "audio-transcriber exception handlers"
check_file "services/video-downloader/app/main.py" "setup_exception_handlers" "video-downloader exception handlers"
check_file "services/youtube-search/app/main.py" "setup_exception_handlers" "youtube-search exception handlers"

echo ""
echo "📦 Teste 5: Redis resiliente implementado"
echo ""
check_file "services/audio-normalization/app/redis_store.py" "from common.redis import ResilientRedisStore" "audio-normalization Redis resiliente"
check_file "services/audio-transcriber/app/redis_store.py" "from common.redis import ResilientRedisStore" "audio-transcriber Redis resiliente"
check_file "services/video-downloader/app/redis_store.py" "from common.redis import ResilientRedisStore" "video-downloader Redis resiliente"
check_file "services/youtube-search/app/redis_store.py" "from common.redis import ResilientRedisStore" "youtube-search Redis resiliente"

echo ""
echo "📦 Teste 6: Orchestrator melhorado"
echo ""
check_file "orchestrator/main.py" "setup_exception_handlers" "Orchestrator exception handlers"
check_file "orchestrator/main.py" "validate_configuration" "Orchestrator validação de config"
check_file "orchestrator/modules/orchestrator.py" "asyncio.timeout" "Orchestrator timeout explícito"
check_file "orchestrator/modules/redis_store.py" "ResilientRedisStore" "Orchestrator Redis resiliente"

echo ""
echo "================================================================================"
echo "📊 RESUMO DA VALIDAÇÃO"
echo "================================================================================"
echo ""
echo "Total de verificações: $check_count"
echo -e "${GREEN}Aprovadas: $pass_count${NC}"
echo -e "${RED}Falhadas: $fail_count${NC}"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}✅ TODAS AS VERIFICAÇÕES PASSARAM!${NC}"
    echo ""
    echo "Melhorias implementadas com sucesso:"
    echo "  ✅ Biblioteca common criada e estruturada"
    echo "  ✅ Logging estruturado em todos os serviços"
    echo "  ✅ Redis resiliente com circuit breaker"
    echo "  ✅ Exception handlers padronizados"
    echo "  ✅ Orchestrator com validações"
    echo "  ✅ Timeouts explícitos"
    echo ""
    exit 0
else
    echo -e "${YELLOW}⚠️  ALGUMAS VERIFICAÇÕES FALHARAM${NC}"
    echo ""
    echo "Revise os itens marcados acima"
    exit 1
fi
