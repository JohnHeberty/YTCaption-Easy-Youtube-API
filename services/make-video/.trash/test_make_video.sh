#!/bin/bash

# test_make_video.sh - Teste do endpoint /make-video (geração de vídeo com legendas)
# Uso: ./test_make_video.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIO_FILE="$SCRIPT_DIR/TEST-.ogg"
SERVICE_URL="http://localhost:8004"
OUTPUT_DIR="$SCRIPT_DIR/../../data/output"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Emojis
CHECK="✅"
CROSS="❌"
ROCKET="🚀"
VIDEO="🎬"
CLOCK="⏱️"
FOLDER="📁"

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}${VIDEO}  TESTE DO ENDPOINT /make-video${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 1. Verificar se o arquivo de áudio existe
echo -e "${BLUE}1️⃣  Verificando arquivo de áudio...${NC}"
if [ ! -f "$AUDIO_FILE" ]; then
    echo -e "${CROSS} ${RED}Arquivo não encontrado: $AUDIO_FILE${NC}"
    exit 1
fi

FILE_SIZE=$(du -h "$AUDIO_FILE" | cut -f1)
echo -e "${CHECK} ${GREEN}Arquivo encontrado: TEST-.ogg (${FILE_SIZE})${NC}"
echo ""

# 2. Verificar se o container está rodando
echo -e "${BLUE}2️⃣  Verificando se o container está rodando...${NC}"
if ! docker ps | grep -q make-video; then
    echo -e "${YELLOW}Container não está rodando. Iniciando...${NC}"
    cd "$SCRIPT_DIR" || exit 1
    docker compose up -d
    echo -e "${CLOCK} Aguardando 10 segundos para o serviço iniciar..."
    sleep 10
fi

# Verificar se o serviço responde
if ! curl -s "$SERVICE_URL/health" > /dev/null 2>&1; then
    echo -e "${CROSS} ${RED}Serviço não está respondendo em $SERVICE_URL${NC}"
    echo -e "${YELLOW}Verificando logs:${NC}"
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" logs --tail=20 make-video
    exit 1
fi

echo -e "${CHECK} ${GREEN}Container rodando e respondendo${NC}"
echo ""

# 3. Criar diretório de output se não existir
echo -e "${BLUE}3️⃣  Preparando diretório de output...${NC}"
mkdir -p "$OUTPUT_DIR"
echo -e "${CHECK} ${GREEN}Diretório: $OUTPUT_DIR${NC}"

# Limpar arquivos antigos de teste
OLD_COUNT=$(find "$OUTPUT_DIR" -name "*.mp4" 2>/dev/null | wc -l)
if [ "$OLD_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}Encontrados $OLD_COUNT vídeos antigos no output${NC}"
fi
echo ""

# 4. Fazer upload do áudio e criar vídeo
echo -e "${BLUE}4️⃣  ${ROCKET} Enviando áudio para /make-video...${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

RESPONSE=$(curl -s -X POST "$SERVICE_URL/make-video" \
    -F "audio=@$AUDIO_FILE" \
    -F "language=pt" \
    -F "num_videos=2" \
    -w "\nHTTP_CODE:%{http_code}" | tee /tmp/make_video_response.txt)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)

if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "201" ] && [ "$HTTP_CODE" != "202" ]; then
    echo -e "${CROSS} ${RED}Erro HTTP: $HTTP_CODE${NC}"
    cat /tmp/make_video_response.txt
    exit 1
fi

# Extrair job_id da resposta
JOB_ID=$(grep -oP '"job_id":\s*"\K[^"]+' /tmp/make_video_response.txt | head -1)

if [ -z "$JOB_ID" ]; then
    echo -e "${CROSS} ${RED}Não foi possível obter job_id da resposta${NC}"
    cat /tmp/make_video_response.txt
    exit 1
fi

echo -e "${CHECK} ${GREEN}Job criado com sucesso!${NC}"
echo -e "${CYAN}Job ID: ${JOB_ID}${NC}"
echo ""

# 5. Monitorar progresso do job
echo -e "${BLUE}5️⃣  ${CLOCK} Monitorando progresso do job...${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

MAX_ATTEMPTS=60  # 5 minutos (60 * 5s)
ATTEMPT=0
STATUS="processing"

while [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; do
    ATTEMPT=$((ATTEMPT + 1))
    
    # Consultar status do job
    JOB_STATUS=$(curl -s "$SERVICE_URL/jobs/$JOB_ID")
    
    # Extrair campos
    STATUS=$(echo "$JOB_STATUS" | grep -oP '"status":\s*"\K[^"]+' | head -1)
    STAGE=$(echo "$JOB_STATUS" | grep -oP '"current_stage":\s*"\K[^"]+' | head -1)
    PROGRESS=$(echo "$JOB_STATUS" | grep -oP '"progress":\s*\K[0-9]+' | head -1)
    
    # Mostrar progresso
    TIMESTAMP=$(date '+%H:%M:%S')
    echo -e "${YELLOW}[$TIMESTAMP] Status: ${STATUS} | Stage: ${STAGE} | Progress: ${PROGRESS}%${NC}"
    
    # Verificar se completou
    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo -e "${CHECK} ${GREEN}Job completado com sucesso!${NC}"
        break
    fi
    
    # Verificar se falhou
    if [ "$STATUS" = "failed" ] || [ "$STATUS" = "error" ]; then
        echo ""
        echo -e "${CROSS} ${RED}Job falhou!${NC}"
        echo "$JOB_STATUS" | jq '.' 2>/dev/null || echo "$JOB_STATUS"
        exit 1
    fi
    
    # Aguardar antes da próxima verificação
    sleep 5
done

if [ "$STATUS" != "completed" ]; then
    echo ""
    echo -e "${CROSS} ${RED}Timeout: Job não completou em 5 minutos${NC}"
    exit 1
fi

echo ""

# 6. Verificar vídeos gerados
echo -e "${BLUE}6️⃣  ${FOLDER} Verificando vídeos gerados...${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Aguardar um pouco para garantir que os arquivos foram escritos
sleep 2

# Listar vídeos no diretório de output
VIDEO_COUNT=$(find "$OUTPUT_DIR" -name "*.mp4" -newer "$AUDIO_FILE" 2>/dev/null | wc -l)

if [ "$VIDEO_COUNT" -eq 0 ]; then
    echo -e "${CROSS} ${RED}Nenhum vídeo novo encontrado no output!${NC}"
    echo -e "${YELLOW}Conteúdo do diretório de output:${NC}"
    ls -lah "$OUTPUT_DIR"
    exit 1
fi

echo -e "${CHECK} ${GREEN}Encontrados $VIDEO_COUNT vídeos novos!${NC}"
echo ""

# Listar vídeos com detalhes
echo -e "${CYAN}Vídeos gerados:${NC}"
find "$OUTPUT_DIR" -name "*.mp4" -newer "$AUDIO_FILE" -exec sh -c '
    file="$1"
    filename=$(basename "$file")
    size=$(du -h "$file" | cut -f1)
    echo "  ${VIDEO} $filename ($size)"
' _ {} \;

echo ""

# 7. Verificar metadados dos vídeos (se ffprobe estiver disponível)
echo -e "${BLUE}7️⃣  Verificando metadados dos vídeos...${NC}"
if command -v ffprobe &> /dev/null; then
    for video in $(find "$OUTPUT_DIR" -name "*.mp4" -newer "$AUDIO_FILE"); do
        filename=$(basename "$video")
        echo -e "${CYAN}${filename}:${NC}"
        
        # Duração
        DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$video" 2>/dev/null | cut -d'.' -f1)
        if [ -n "$DURATION" ]; then
            echo -e "  ⏱️  Duração: ${DURATION}s"
        fi
        
        # Resolução
        RESOLUTION=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$video" 2>/dev/null)
        if [ -n "$RESOLUTION" ]; then
            echo -e "  📐 Resolução: ${RESOLUTION}"
        fi
        
        # Codec
        CODEC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$video" 2>/dev/null)
        if [ -n "$CODEC" ]; then
            echo -e "  🎨 Codec: ${CODEC}"
        fi
        
        echo ""
    done
else
    echo -e "${YELLOW}ffprobe não disponível. Pulando verificação de metadados.${NC}"
fi

# 8. Resumo final
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${CHECK} TESTE COMPLETO - SUCESSO${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}✓ Áudio enviado: TEST-.ogg (${FILE_SIZE})${NC}"
echo -e "${GREEN}✓ Job ID: ${JOB_ID}${NC}"
echo -e "${GREEN}✓ Status: ${STATUS}${NC}"
echo -e "${GREEN}✓ Vídeos gerados: ${VIDEO_COUNT}${NC}"
echo -e "${GREEN}✓ Diretório output: ${OUTPUT_DIR}${NC}"
echo ""
echo -e "${BLUE}Para visualizar os vídeos:${NC}"
echo -e "  ${CYAN}ls -lh $OUTPUT_DIR/*.mp4${NC}"
echo ""
