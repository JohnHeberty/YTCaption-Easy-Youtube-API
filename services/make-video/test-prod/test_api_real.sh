#!/bin/bash
# Teste de Integração Real via API HTTP

echo "=================================================="
echo "TESTE DE INTEGRAÇÃO: API HTTP"
echo "=================================================="

API_URL="http://localhost:8004"
AUDIO_FILE="/root/YTCaption-Easy-Youtube-API/services/make-video/tests/TEST-.ogg"

echo ""
echo "📋 Criando job via API..."
echo "   Áudio: $AUDIO_FILE"

# Verificar se áudio existe
if [ ! -f "$AUDIO_FILE" ]; then
    echo "❌ ERRO: Áudio não encontrado: $AUDIO_FILE"
    exit 1
fi

# Criar job usando endpoint correto: POST /make-video com upload
RESPONSE=$(curl -s -X POST "$API_URL/make-video" \
  -F "audio_file=@$AUDIO_FILE" \
  -F "query=test sync improvements" \
  -F "max_shorts=10" \
  -F "subtitle_language=pt" \
  -F "subtitle_style=dynamic" \
  -F "aspect_ratio=9:16" \
  -F "crop_position=center")

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Extrair job_id
JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_id', ''))" 2>/dev/null)

if [ -z "$JOB_ID" ]; then
    echo ""
    echo "❌ ERRO: Não foi possível criar job"
    exit 1
fi

echo ""
echo "✅ Job criado: $JOB_ID"
echo ""
echo "🔍 Monitorando job..."
echo ""

# Monitorar job (máximo 5 minutos)
TIMEOUT=300
ELAPSED=0
LAST_STATUS=""

while [ $ELAPSED -lt $TIMEOUT ]; do
    # Buscar status
    STATUS_RESPONSE=$(curl -s "$API_URL/jobs/$JOB_ID")
    
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)
    PROGRESS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress', 0))" 2>/dev/null)
    
    # Log se status mudou
    if [ "$STATUS" != "$LAST_STATUS" ]; then
        echo "[${ELAPSED}s] Status: $STATUS, Progress: ${PROGRESS}%"
        LAST_STATUS="$STATUS"
    fi
    
    # Verificar conclusão
    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo "✅ JOB COMPLETADO em ${ELAPSED}s"
        echo ""
        echo "📊 Status final:"
        echo "$STATUS_RESPONSE" | python3 -m json.tool
        echo ""
        
        # Verificar se vídeo foi gerado
        OUTPUT_DIR="/root/YTCaption-Easy-Youtube-API/services/make-video/data/approve"
        
        if [ -f "$OUTPUT_DIR/${JOB_ID}.mp4" ]; then
            SIZE=$(du -h "$OUTPUT_DIR/${JOB_ID}.mp4" | cut -f1)
            echo "✅ VÍDEO GERADO: $OUTPUT_DIR/${JOB_ID}.mp4 ($SIZE)"
        elif [ -f "$OUTPUT_DIR/final_video.mp4" ]; then
            SIZE=$(du -h "$OUTPUT_DIR/final_video.mp4" | cut -f1)
            echo "✅ VÍDEO GERADO: $OUTPUT_DIR/final_video.mp4 ($SIZE)"
        else
            echo "⚠️ Vídeo não encontrado em $OUTPUT_DIR"
            echo "Arquivos disponíveis:"
            ls -lh "$OUTPUT_DIR" | tail -10
        fi
        
        exit 0
    fi
    
    if [ "$STATUS" = "failed" ]; then
        echo ""
        echo "❌ JOB FALHOU em ${ELAPSED}s"
        echo ""
        echo "📊 Detalhes do erro:"
        echo "$STATUS_RESPONSE" | python3 -m json.tool
        exit 1
    fi
    
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

echo ""
echo "⏱️ TIMEOUT: Job não completou em ${TIMEOUT}s"
echo ""
echo "📊 Status atual:"
curl -s "$API_URL/jobs/$JOB_ID" | python3 -m json.tool
exit 1
