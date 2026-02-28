#!/bin/bash
# Validação de Suporte GPU - Audio Transcriber
# Executar após: docker compose up -d

set -e

echo "🔍 =========================================="
echo "   VALIDAÇÃO DE GPU - AUDIO TRANSCRIBER"
echo "=========================================="
echo ""

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função de checagem
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ PASSOU${NC}"
        return 0
    else
        echo -e "${RED}❌ FALHOU${NC}"
        return 1
    fi
}

# 1. Container está rodando?
echo "📦 1. Verificando se container está rodando..."
docker ps | grep audio-transcriber-api > /dev/null
check_status

# 2. PyTorch instalado?
echo ""
echo "🐍 2. Verificando instalação do PyTorch..."
docker exec audio-transcriber-api python -c "import torch; print(f'PyTorch: {torch.__version__}')" 2>/dev/null
check_status

# 3. CUDA disponível?
echo ""
echo "🎮 3. Verificando CUDA disponível no PyTorch..."
CUDA_CHECK=$(docker exec audio-transcriber-api python -c "import torch; print(torch.cuda.is_available())" 2>/dev/null)
echo "CUDA Available: $CUDA_CHECK"
if [ "$CUDA_CHECK" == "True" ]; then
    echo -e "${GREEN}✅ CUDA DISPONÍVEL${NC}"
else
    echo -e "${RED}❌ CUDA NÃO DISPONÍVEL${NC}"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   1. Verificar nvidia-smi no host: nvidia-smi"
    echo "   2. Verificar runtime: docker exec audio-transcriber-api bash -c 'ls /usr/lib/x86_64-linux-gnu/libcuda*'"
    echo "   3. Verificar variáveis: docker exec audio-transcriber-api env | grep NVIDIA"
    echo "   4. Reconstruir: docker compose down && docker compose build --no-cache && docker compose up -d"
    exit 1
fi

# 4. Qual versão CUDA?
echo ""
echo "📊 4. Verificando versão CUDA..."
docker exec audio-transcriber-api python -c "import torch; print(f'CUDA Version: {torch.version.cuda}')" 2>/dev/null
check_status

# 5. Qual GPU?
echo ""
echo "🎯 5. Identificando GPU..."
GPU_NAME=$(docker exec audio-transcriber-api python -c "import torch; print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')" 2>/dev/null)
echo "GPU: $GPU_NAME"
if [ "$GPU_NAME" != "N/A" ]; then
    echo -e "${GREEN}✅ GPU DETECTADA: $GPU_NAME${NC}"
else
    echo -e "${RED}❌ GPU NÃO DETECTADA${NC}"
fi

# 6. Verificar logs do container
echo ""
echo "📋 6. Verificando logs (últimas 20 linhas)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker logs audio-transcriber-api --tail 20 | grep -i "cuda\|gpu\|device\|warning\|error" || echo "Nenhuma mensagem relevante encontrada"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 7. Verificar Whisper Device Config
echo ""
echo "⚙️  7. Verificando configuração Whisper Device..."
WHISPER_DEVICE=$(docker exec audio-transcriber-api bash -c 'echo $WHISPER_DEVICE' 2>/dev/null)
echo "WHISPER_DEVICE: $WHISPER_DEVICE"
if [ "$WHISPER_DEVICE" == "cuda" ]; then
    echo -e "${GREEN}✅ CONFIGURADO PARA USAR GPU${NC}"
else
    echo -e "${YELLOW}⚠️  CONFIGURADO PARA: $WHISPER_DEVICE${NC}"
fi

# 8. Verificar variáveis NVIDIA
echo ""
echo "🔧 8. Verificando variáveis NVIDIA..."
docker exec audio-transcriber-api env | grep NVIDIA || echo "Variáveis NVIDIA não encontradas"

# 9. Teste rápido de GPU
echo ""
echo "🧪 9. Teste rápido de alocação GPU..."
docker exec audio-transcriber-api python -c "
import torch
if torch.cuda.is_available():
    try:
        x = torch.randn(100, 100).cuda()
        y = x @ x.T
        print(f'✅ Alocação GPU bem-sucedida')
        print(f'   Tensor shape: {y.shape}')
        print(f'   Device: {y.device}')
        del x, y
        torch.cuda.empty_cache()
    except Exception as e:
        print(f'❌ Erro ao alocar GPU: {e}')
else:
    print('❌ CUDA não disponível para teste')
" 2>/dev/null
check_status

# 10. Verificar memória GPU
echo ""
echo "💾 10. Verificando memória GPU..."
docker exec audio-transcriber-api python -c "
import torch
if torch.cuda.is_available():
    allocated = torch.cuda.memory_allocated(0) / 1024**2  # MB
    reserved = torch.cuda.memory_reserved(0) / 1024**2    # MB
    total = torch.cuda.get_device_properties(0).total_memory / 1024**2  # MB
    print(f'   Alocada: {allocated:.2f} MB')
    print(f'   Reservada: {reserved:.2f} MB')
    print(f'   Total: {total:.2f} MB')
    print(f'   Livre: {total - allocated:.2f} MB')
else:
    print('   N/A - CUDA não disponível')
" 2>/dev/null

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ VALIDAÇÃO COMPLETA!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📌 Próximos passos:"
echo "   1. Testar transcrição: curl -X POST http://localhost:8005/jobs -F 'file=@test.mp3' -F 'language_in=pt'"
echo "   2. Monitorar logs: docker logs -f audio-transcriber-api"
echo "   3. Verificar performance com nvidia-smi durante transcrição"
echo ""
