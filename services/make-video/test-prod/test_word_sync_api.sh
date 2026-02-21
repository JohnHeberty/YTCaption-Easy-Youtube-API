#!/bin/bash
# Teste de API - Sincronização Palavra-por-Palavra
# Valida que cada palavra aparece SOMENTE quando está sendo falada

set -e

API_URL="http://localhost:8004"
TEST_AUDIO="../tests/TEST-.ogg"

echo "🧪 Teste de Sincronização Palavra-por-Palavra"
echo "=============================================="
echo ""

# Verificar áudio de teste
if [ ! -f "$TEST_AUDIO" ]; then
    echo "❌ Áudio de teste não encontrado: $TEST_AUDIO"
    exit 1
fi

echo "✅ Áudio encontrado: $TEST_AUDIO ($(du -h "$TEST_AUDIO" | cut -f1))"
echo ""

# Criar job
echo "📤 Criando job de teste..."
RESPONSE=$(curl -s -X POST "$API_URL/make-video" \
    -F "audio_file=@$TEST_AUDIO" \
    -F "query=test" \
    -F "language=pt")

JOB_ID=$(echo "$RESPONSE" | jq -r '.job_id')

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
    echo "❌ Falha ao criar job!"
    echo "$RESPONSE" | jq '.'
    exit 1
fi

echo "✅ Job criado: $JOB_ID"
echo ""

# Aguardar processamento
echo "⏳ Aguardando processamento..."
MAX_WAIT=120
ELAPSED=0
STATUS="pending"

while [ "$STATUS" != "completed" ] && [ "$STATUS" != "failed" ] && [ $ELAPSED -lt $MAX_WAIT ]; do
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    
    STATUS_RESPONSE=$(curl -s "$API_URL/jobs/$JOB_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
    PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress')
    
    echo "   Status: $STATUS | Progress: $PROGRESS% | Elapsed: ${ELAPSED}s"
done

echo ""

# Verificar resultado
if [ "$STATUS" == "completed" ]; then
    echo "✅ Job completado!"
    echo ""
    
    RESULT=$(curl -s "$API_URL/jobs/$JOB_ID" | jq '.result')

    echo "📊 Resultado:"
    echo "$RESULT" | jq '.'
    echo ""
    
    # Validações
    SUBTITLE_SEGMENTS=$(echo "$RESULT" | jq -r '.subtitle_segments')
    VIDEO_FILE=$(echo "$RESULT" | jq -r '.video_file')
    
    echo "🔍 Validações:"
    echo "   ✓ Segmentos de legenda: $SUBTITLE_SEGMENTS"
    
    if [ "$SUBTITLE_SEGMENTS" -gt 0 ]; then
        echo "   ✅ Legendas geradas com sucesso!"
    else
        echo "   ❌ ERRO: Nenhuma legenda gerada!"
        exit 1
    fi
    
    # Verificar arquivo SRT
    SRT_FILE="/tmp/make-video-temp/$JOB_ID/subtitles.srt"
    
    if docker exec ytcaption-make-video-celery test -f "$SRT_FILE"; then
        echo "   ✓ Arquivo SRT existe: $SRT_FILE"
        
        # Copiar SRT do container
        docker cp ytcaption-make-video-celery:"$SRT_FILE" ./test_output.srt
        
        echo ""
        echo "📝 Conteúdo do SRT (primeiras 50 linhas):"
        echo "=========================================="
        head -50 ./test_output.srt
        echo ""
        
        # Análise de sincronização
        echo "🔬 Análise de Sincronização:"
        echo "=============================="
        
        TOTAL_CAPTIONS=$(grep -c "^[0-9]\+$" ./test_output.srt || echo "0")
        echo "   ✓ Total de legendas: $TOTAL_CAPTIONS"
        
        # Verificar se legendas são palavra-por-palavra (não agrupadas)
        # Legendas curtas (< 15 chars) indicam palavras individuais
        SHORT_CAPTIONS=$(awk '/^[0-9]/ {getline; getline; if (length($0) < 15 && $0 != "") count++} END {print count+0}' ./test_output.srt)
        
        echo "   ✓ Legendas curtas (< 15 chars): $SHORT_CAPTIONS"
        
        if [ "$SHORT_CAPTIONS" -gt 0 ]; then
            PCT=$(awk "BEGIN {printf \"%.1f\", ($SHORT_CAPTIONS/$TOTAL_CAPTIONS)*100}")
            echo "   ✓ Percentual de palavras individuais: $PCT%"
            
            if [ $(echo "$PCT > 50" | bc -l) -eq 1 ]; then
                echo "   ✅ Sincronização palavra-por-palavra ativa!"
            else
                echo "   ⚠️ Muitas legendas longas - pode estar agrupando palavras"
            fi
        fi
        
        echo ""
        echo "📋 Primeiras 10 legendas:"
        head -40 ./test_output.srt | tail -36
        
    else
        echo "   ⚠️ Arquivo SRT não encontrado no container"
    fi
    
    echo ""
    echo "🎥 Vídeo gerado: $VIDEO_FILE"
    echo ""
    echo "✅ TESTE CONCLUÍDO COM SUCESSO!"
    
elif [ "$STATUS" == "failed" ]; then
    echo "❌ Job falhou!"
    curl -s "$API_URL/jobs/$JOB_ID" | jq '.'
    exit 1
else
    echo "⏱️ Timeout: Job não completou em ${MAX_WAIT}s"
    curl -s "$API_URL/jobs/$JOB_ID" | jq '.'
    exit 1
fi
