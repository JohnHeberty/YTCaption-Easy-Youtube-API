#!/bin/bash
# Script de teste para áudios longos no audio-transcriber
# Testa upload, monitoramento e download de transcrições

set -e

API_URL="${API_URL:-http://localhost:8003}"
AUDIO_FILE="${1:-saida_5.mp3}"

if [ ! -f "$AUDIO_FILE" ]; then
    echo "❌ Erro: Arquivo '$AUDIO_FILE' não encontrado"
    echo "Uso: $0 <caminho_do_arquivo.mp3>"
    exit 1
fi

FILE_SIZE=$(du -h "$AUDIO_FILE" | cut -f1)
echo "📁 Arquivo: $AUDIO_FILE ($FILE_SIZE)"
echo ""

# 1. Envia arquivo para transcrição
echo "🚀 1. Enviando arquivo para transcrição..."
RESPONSE=$(curl -s -X POST "$API_URL/jobs" \
  -F "file=@$AUDIO_FILE" \
  -F "language_in=pt" \
  -F "language_out=" \
  -H "accept: application/json")

JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "✅ Job criado: $JOB_ID"
echo ""

# 2. Monitora progresso
echo "⏳ 2. Monitorando progresso..."
COMPLETED=false
FAILED=false
LAST_PROGRESS=0

while [ "$COMPLETED" = false ] && [ "$FAILED" = false ]; do
    sleep 5
    
    STATUS_RESPONSE=$(curl -s "$API_URL/jobs/$JOB_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
    PROGRESS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['progress'])")
    
    if [ "$STATUS" = "completed" ]; then
        COMPLETED=true
        echo "✅ Transcrição concluída! (100%)"
    elif [ "$STATUS" = "failed" ]; then
        FAILED=true
        ERROR=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['error_message'])")
        echo "❌ Transcrição falhou: $ERROR"
    else
        # Mostra progresso apenas se mudou
        if [ "$PROGRESS" != "$LAST_PROGRESS" ]; then
            echo "   Status: $STATUS - Progresso: $PROGRESS%"
            LAST_PROGRESS=$PROGRESS
        fi
    fi
done
echo ""

if [ "$COMPLETED" = true ]; then
    # 3. Baixa resultado
    echo "📥 3. Baixando resultado..."
    OUTPUT_FILE=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['output_file'])")
    
    if [ "$OUTPUT_FILE" != "null" ] && [ -n "$OUTPUT_FILE" ]; then
        DOWNLOAD_URL="$API_URL/download/$JOB_ID"
        OUTPUT_NAME="transcription_${JOB_ID}.srt"
        
        curl -s -o "$OUTPUT_NAME" "$DOWNLOAD_URL"
        
        if [ -f "$OUTPUT_NAME" ]; then
            echo "✅ Transcrição salva em: $OUTPUT_NAME"
            echo ""
            echo "📄 Primeiras linhas da transcrição:"
            head -20 "$OUTPUT_NAME"
        else
            echo "❌ Erro ao baixar arquivo"
        fi
    fi
    
    # 4. Mostra estatísticas
    echo ""
    echo "📊 4. Estatísticas do Job:"
    echo "$STATUS_RESPONSE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"   Job ID: {d['id']}\")
print(f\"   Arquivo: {d['filename']}\")
print(f\"   Tamanho entrada: {d['file_size_input'] / (1024*1024):.2f} MB\")
print(f\"   Idioma detectado: {d['language_detected']}\")
print(f\"   Tempo de criação: {d['created_at']}\")
if d['transcription_text']:
    text_preview = d['transcription_text'][:200] + '...' if len(d['transcription_text']) > 200 else d['transcription_text']
    print(f\"   Texto (preview): {text_preview}\")
"
    
    exit 0
else
    exit 1
fi
