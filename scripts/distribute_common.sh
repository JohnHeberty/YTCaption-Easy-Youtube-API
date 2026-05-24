#!/bin/bash

# Script para distribuir biblioteca common para todos os serviços
# Cada serviço terá sua própria cópia da common em sync

set -e

echo "================================================================================"
echo "📦 DISTRIBUINDO BIBLIOTECA COMMON PARA OS SERVIÇOS"
echo "================================================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ROOT_DIR="/root/YTCaption-Easy-Youtube-API"
COMMON_SOURCE="$ROOT_DIR/common"

# Lista de serviços (exceto transcriber)
SERVICES=(
    "services/se1-orchestrator"
    "services/se3-audio-normalization"
    "services/se2-video-downloader"
    "services/se6-youtube-search"
)

# Verifica se common existe
if [ ! -d "$COMMON_SOURCE" ]; then
    echo -e "${RED}❌ Erro: Pasta common não encontrada em $COMMON_SOURCE${NC}"
    exit 1
fi

echo -e "${BLUE}Origem:${NC} $COMMON_SOURCE"
echo ""

total=0
success=0
failed=0

for service in "${SERVICES[@]}"; do
    total=$((total + 1))
    service_path="$ROOT_DIR/$service"
    target_path="$service_path/common"
    
    echo -e "${BLUE}▶ Processando:${NC} $service"
    
    if [ ! -d "$service_path" ]; then
        echo -e "${RED}  ✗ Serviço não encontrado: $service_path${NC}"
        failed=$((failed + 1))
        continue
    fi
    
    # Remove common antiga se existir
    if [ -d "$target_path" ]; then
        echo "  Removendo common antiga..."
        rm -rf "$target_path"
    fi
    
    # Copia common para o serviço
    echo "  Copiando biblioteca common..."
    cp -r "$COMMON_SOURCE" "$target_path"
    
    # Remove arquivos desnecessários
    find "$target_path" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$target_path" -name "*.pyc" -delete 2>/dev/null || true
    
    # Verifica se copiou corretamente
    if [ -f "$target_path/setup.py" ]; then
        echo -e "${GREEN}  ✓ Common copiada com sucesso${NC}"
        
        # Lista módulos copiados
        modules=$(ls -1 "$target_path" | grep -v "^__" | grep -v "\.py$" | wc -l)
        echo "  Módulos: $modules"
        
        success=$((success + 1))
    else
        echo -e "${RED}  ✗ Erro ao copiar common${NC}"
        failed=$((failed + 1))
    fi
    
    echo ""
done

echo "================================================================================"
echo "📊 RESUMO DA DISTRIBUIÇÃO"
echo "================================================================================"
echo ""
echo "Total de serviços: $total"
echo -e "${GREEN}Sucesso: $success${NC}"
echo -e "${RED}Falha: $failed${NC}"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}🎉 BIBLIOTECA COMMON DISTRIBUÍDA COM SUCESSO!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "✅ Cada serviço agora tem sua própria cópia da common"
    echo "✅ Serviços podem rodar em VMs separadas"
    echo "✅ Builds Docker funcionarão independentemente"
    echo ""
    echo "Próximos passos:"
    echo "  1. Atualizar requirements.txt de cada serviço"
    echo "  2. Atualizar Dockerfiles para usar ./common"
    echo "  3. Testar builds individuais"
    echo ""
    exit 0
else
    echo -e "${RED}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}❌ ALGUNS SERVIÇOS FALHARAM${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    exit 1
fi
