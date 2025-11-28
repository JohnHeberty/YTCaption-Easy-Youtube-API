#!/bin/bash
################################################################################
# validate-optimization.sh - Valida otimizações de Dockerfile
#
# Uso: ./validate-optimization.sh [pre|post]
#   pre  - Validações ANTES do build
#   post - Validações DEPOIS do build
#
# Exemplo:
#   ./validate-optimization.sh pre
#   docker build -t audio-voice:3.0.0 .
#   ./validate-optimization.sh post
################################################################################

set -e

MODE=${1:-pre}
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="validation-${MODE}-${TIMESTAMP}.log"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funções de output
info() {
    echo -e "${BLUE}ℹ${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}✓${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}✗${NC} $1" | tee -a "$LOG_FILE"
}

# Header
echo "========================================================================"
echo "  VALIDAÇÃO DE OTIMIZAÇÃO - Audio Voice Service"
echo "  Modo: $MODE | $(date)"
echo "========================================================================"
echo ""

################################################################################
# VALIDAÇÕES PRÉ-BUILD
################################################################################
if [ "$MODE" == "pre" ]; then
    info "Executando validações PRÉ-BUILD..."
    echo ""
    
    # 1. Verifica espaço em disco
    info "[1/7] Verificando espaço em disco..."
    ROOT_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    ROOT_AVAIL=$(df -h / | tail -1 | awk '{print $4}')
    
    if [ "$ROOT_USAGE" -lt 50 ]; then
        success "Espaço em disco OK: ${ROOT_USAGE}% usado, ${ROOT_AVAIL} disponível"
    elif [ "$ROOT_USAGE" -lt 70 ]; then
        warning "Espaço em disco aceitável: ${ROOT_USAGE}% usado, ${ROOT_AVAIL} disponível"
    else
        error "CRÍTICO: Espaço em disco muito baixo: ${ROOT_USAGE}% usado, ${ROOT_AVAIL} disponível"
        echo "  Recomendação: Libere espaço antes de continuar!"
        exit 1
    fi
    echo ""
    
    # 2. Verifica se .dockerignore existe e está otimizado
    info "[2/7] Verificando .dockerignore..."
    if [ ! -f .dockerignore ]; then
        error ".dockerignore não encontrado!"
        echo "  Recomendação: cp .dockerignore.optimized .dockerignore"
        exit 1
    fi
    
    # Verifica se .dockerignore exclui pastas críticas
    REQUIRED_EXCLUDES=("tests/" "docs/" "sprints_" "benchmarks/" "notebooks/")
    MISSING_EXCLUDES=()
    
    for exclude in "${REQUIRED_EXCLUDES[@]}"; do
        if ! grep -q "$exclude" .dockerignore; then
            MISSING_EXCLUDES+=("$exclude")
        fi
    done
    
    if [ ${#MISSING_EXCLUDES[@]} -eq 0 ]; then
        success ".dockerignore está completo"
    else
        warning ".dockerignore pode estar incompleto. Faltam: ${MISSING_EXCLUDES[*]}"
        echo "  Recomendação: Adicione exclusões ou use .dockerignore.optimized"
    fi
    echo ""
    
    # 3. Verifica contexto de build
    info "[3/7] Calculando tamanho do contexto de build..."
    
    # Simula o que Docker vai copiar (respeitando .dockerignore)
    CONTEXT_SIZE=$(tar --exclude-from=.dockerignore -czf - . 2>/dev/null | wc -c | awk '{print $1/1024/1024}')
    CONTEXT_SIZE_MB=$(printf "%.2f" $CONTEXT_SIZE)
    
    if (( $(echo "$CONTEXT_SIZE < 1" | bc -l) )); then
        success "Contexto de build otimizado: ${CONTEXT_SIZE_MB} MB"
    elif (( $(echo "$CONTEXT_SIZE < 5" | bc -l) )); then
        warning "Contexto de build aceitável: ${CONTEXT_SIZE_MB} MB"
    else
        error "Contexto de build muito grande: ${CONTEXT_SIZE_MB} MB"
        echo "  Recomendação: Verifique .dockerignore e remova arquivos desnecessários"
    fi
    echo ""
    
    # 4. Verifica se Dockerfile usa multi-stage
    info "[4/7] Verificando Dockerfile..."
    if ! [ -f Dockerfile ]; then
        error "Dockerfile não encontrado!"
        exit 1
    fi
    
    if grep -q "FROM.*AS builder" Dockerfile && grep -q "FROM.*AS runtime" Dockerfile; then
        success "Dockerfile usa multi-stage build ✓"
    else
        warning "Dockerfile NÃO usa multi-stage build"
        echo "  Recomendação: cp Dockerfile.optimized Dockerfile"
    fi
    
    # Verifica se baixa modelos durante build
    if grep -q "create_default_speaker.py" Dockerfile && ! grep -q "^#.*create_default_speaker.py" Dockerfile; then
        error "Dockerfile BAIXA MODELOS durante build (create_default_speaker.py)"
        echo "  Recomendação: Comente essa linha e use scripts/download_models.py no runtime"
    else
        success "Dockerfile NÃO baixa modelos durante build ✓"
    fi
    echo ""
    
    # 5. Verifica se BuildKit está ativado
    info "[5/7] Verificando BuildKit..."
    if [ "$DOCKER_BUILDKIT" == "1" ]; then
        success "BuildKit ativado ✓"
    else
        warning "BuildKit NÃO está ativado"
        echo "  Recomendação: export DOCKER_BUILDKIT=1"
    fi
    echo ""
    
    # 6. Verifica imagens Docker existentes
    info "[6/7] Verificando imagens Docker antigas..."
    OLD_IMAGES=$(docker images -q audio-voice 2>/dev/null | wc -l)
    if [ "$OLD_IMAGES" -gt 3 ]; then
        warning "Existem $OLD_IMAGES imagens audio-voice antigas"
        echo "  Recomendação: docker image prune -a"
    else
        success "Quantidade de imagens OK ($OLD_IMAGES imagens)"
    fi
    echo ""
    
    # 7. Verifica cache do Docker
    info "[7/7] Verificando cache do Docker..."
    DOCKER_SIZE=$(docker system df 2>/dev/null | grep "Build Cache" | awk '{print $3}' || echo "N/A")
    info "Cache de build: $DOCKER_SIZE"
    
    if [ "$DOCKER_SIZE" != "N/A" ]; then
        success "Docker system df executado com sucesso"
        echo "  Dica: Se cache > 10 GB, considere: docker builder prune"
    fi
    echo ""
    
    # Resumo PRE-BUILD
    echo "========================================================================"
    echo "  RESUMO PRÉ-BUILD"
    echo "========================================================================"
    echo "Espaço disponível: ${ROOT_AVAIL}"
    echo "Contexto de build: ${CONTEXT_SIZE_MB} MB"
    echo "Imagens antigas: $OLD_IMAGES"
    echo ""
    echo "✅ Validações PRÉ-BUILD concluídas!"
    echo "Você pode prosseguir com o build."
    echo ""
    echo "Comando sugerido:"
    echo "  export DOCKER_BUILDKIT=1"
    echo "  docker build --target runtime -t audio-voice:3.0.0 ."
    echo ""

################################################################################
# VALIDAÇÕES PÓS-BUILD
################################################################################
elif [ "$MODE" == "post" ]; then
    info "Executando validações PÓS-BUILD..."
    echo ""
    
    # 1. Verifica se imagem foi criada
    info "[1/6] Verificando imagem criada..."
    if docker images | grep -q "audio-voice.*3.0.0"; then
        success "Imagem audio-voice:3.0.0 criada com sucesso ✓"
    else
        error "Imagem audio-voice:3.0.0 NÃO encontrada!"
        echo "  Verifique se o build foi concluído com sucesso"
        exit 1
    fi
    echo ""
    
    # 2. Verifica tamanho da imagem
    info "[2/6] Verificando tamanho da imagem..."
    IMAGE_SIZE=$(docker images audio-voice:3.0.0 --format "{{.Size}}")
    IMAGE_SIZE_GB=$(docker images audio-voice:3.0.0 --format "{{.Size}}" | sed 's/GB//' | sed 's/MB//' | awk '{print $1}')
    
    info "Tamanho da imagem: $IMAGE_SIZE"
    
    # Compara com versão anterior (se existir)
    if docker images | grep -q "audio-voice.*latest"; then
        OLD_SIZE=$(docker images audio-voice:latest --format "{{.Size}}")
        info "Tamanho anterior: $OLD_SIZE"
    fi
    
    # Regra: imagem deve ser < 15 GB
    if [[ "$IMAGE_SIZE" == *"MB"* ]]; then
        success "Imagem muito otimizada: $IMAGE_SIZE ✓"
    elif [[ "$IMAGE_SIZE" == *"GB"* ]]; then
        if (( $(echo "$IMAGE_SIZE_GB < 12" | bc -l) )); then
            success "Tamanho da imagem OK: $IMAGE_SIZE ✓"
        elif (( $(echo "$IMAGE_SIZE_GB < 15" | bc -l) )); then
            warning "Imagem um pouco grande: $IMAGE_SIZE"
        else
            error "Imagem muito grande: $IMAGE_SIZE"
            echo "  Esperado: < 12 GB"
        fi
    fi
    echo ""
    
    # 3. Verifica camadas da imagem
    info "[3/6] Analisando camadas da imagem..."
    LAYERS=$(docker history audio-voice:3.0.0 --no-trunc | wc -l)
    info "Número de camadas: $LAYERS"
    
    if [ "$LAYERS" -lt 15 ]; then
        success "Número de camadas otimizado ($LAYERS) ✓"
    else
        warning "Muitas camadas ($LAYERS). Multi-stage pode reduzir isso."
    fi
    echo ""
    
    # 4. Verifica se build-essential está na imagem final
    info "[4/6] Verificando se build-essential foi removido..."
    if docker run --rm audio-voice:3.0.0 dpkg -l | grep -q "build-essential"; then
        error "build-essential AINDA ESTÁ na imagem final!"
        echo "  Recomendação: Use multi-stage build"
    else
        success "build-essential removido corretamente ✓"
    fi
    echo ""
    
    # 5. Verifica espaço em disco pós-build
    info "[5/6] Verificando espaço em disco pós-build..."
    ROOT_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    ROOT_AVAIL=$(df -h / | tail -1 | awk '{print $4}')
    
    info "Espaço usado: ${ROOT_USAGE}% | Disponível: ${ROOT_AVAIL}"
    
    if [ "$ROOT_USAGE" -lt 70 ]; then
        success "Espaço em disco OK pós-build ✓"
    elif [ "$ROOT_USAGE" -lt 85 ]; then
        warning "Espaço em disco ficando baixo: ${ROOT_USAGE}%"
        echo "  Recomendação: docker system prune -af"
    else
        error "CRÍTICO: Disco quase cheio: ${ROOT_USAGE}%"
        echo "  Execute IMEDIATAMENTE: docker system prune -af --volumes"
    fi
    echo ""
    
    # 6. Testa se container inicia
    info "[6/6] Testando se container inicia..."
    if docker run --rm -d --name audio-voice-test audio-voice:3.0.0 > /dev/null 2>&1; then
        sleep 5
        if docker ps | grep -q "audio-voice-test"; then
            success "Container inicia corretamente ✓"
            docker stop audio-voice-test > /dev/null 2>&1 || true
        else
            error "Container iniciou mas falhou"
            docker logs audio-voice-test 2>&1 | tail -20
            docker rm -f audio-voice-test > /dev/null 2>&1 || true
        fi
    else
        error "Falha ao iniciar container"
        echo "  Verifique logs com: docker logs audio-voice-test"
    fi
    echo ""
    
    # Resumo PÓS-BUILD
    echo "========================================================================"
    echo "  RESUMO PÓS-BUILD"
    echo "========================================================================"
    echo "Imagem criada: ✓ audio-voice:3.0.0"
    echo "Tamanho: $IMAGE_SIZE"
    echo "Camadas: $LAYERS"
    echo "Espaço disponível: ${ROOT_AVAIL} (${ROOT_USAGE}% usado)"
    echo ""
    echo "✅ Validações PÓS-BUILD concluídas!"
    echo ""
    echo "Próximos passos:"
    echo "  1. Testar container: docker-compose up -d"
    echo "  2. Baixar modelos: docker-compose exec audio-voice python scripts/download_models.py"
    echo "  3. Validar API: curl http://localhost:8005/health"
    echo ""

else
    error "Modo inválido: $MODE"
    echo "Uso: $0 [pre|post]"
    exit 1
fi

echo "Log salvo em: $LOG_FILE"
echo "========================================================================"
