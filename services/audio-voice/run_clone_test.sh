#!/bin/bash

# Script para rodar teste de qualidade de clonagem de voz
# Executa tudo dentro do container Docker sem rodar API

set -e

echo "================================="
echo "🧪 Voice Clone Quality Test"
echo "================================="
echo ""

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verifica se o arquivo de teste existe
if [ ! -f "tests/Teste.mp3" ]; then
    echo -e "${RED}❌ Error: tests/Teste.mp3 not found!${NC}"
    echo "Please record your voice saying 'Oi, tudo bem?' and save as tests/Teste.mp3"
    exit 1
fi

echo -e "${GREEN}✅ Test audio found: tests/Teste.mp3${NC}"
echo ""

# Para containers se estiverem rodando
echo -e "${YELLOW}🛑 Stopping running containers...${NC}"
docker compose down 2>/dev/null || true
echo ""

# Cria Dockerfile temporário com dependências extras
echo -e "${YELLOW}🔨 Building test container with analysis dependencies...${NC}"
cat > Dockerfile.test << 'EOF'
FROM audio-voice-api:latest

USER root

# Instala dependências de análise
RUN python -m pip install --no-cache-dir \
    soundfile==0.12.1 \
    matplotlib==3.8.2 \
    scipy==1.11.4 \
    scikit-learn==1.3.2

USER appuser
EOF

# Build da imagem base se necessário
docker build -t audio-voice-api -f Dockerfile .

# Build da imagem de teste
docker build -t audio-voice-test -f Dockerfile.test .
echo ""

# Cria diretório de output
mkdir -p tests/output_clone_analysis
chmod 777 tests/output_clone_analysis

# Roda teste dentro do container
echo -e "${YELLOW}🚀 Running voice clone quality test...${NC}"
echo ""
docker run --rm \
  -v "$(pwd)/tests:/app/tests" \
  -v "$(pwd)/app:/app/app" \
  -u root \
  audio-voice-test \
  bash -c "mkdir -p /app/tests/output_clone_analysis && chmod 777 /app/tests/output_clone_analysis && python /app/tests/test_voice_clone_quality.py"

echo ""
echo -e "${GREEN}✅ Test completed!${NC}"
echo ""
echo "📁 Results saved in: tests/output_clone_analysis/"
ls -lh tests/output_clone_analysis/
echo ""
echo -e "${YELLOW}📊 Check the JSON file for detailed metrics${NC}"
echo -e "${YELLOW}📈 Check the PNG file for visual comparison${NC}"
echo ""

# Limpa Dockerfile temporário
rm -f Dockerfile.test
