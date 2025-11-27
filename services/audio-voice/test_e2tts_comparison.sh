#!/bin/bash

###############################################################################
# Script de Teste Comparativo E2-TTS vs XTTS
# - Testa o novo modelo E2-TTS (com suporte a emoções)
# - Compara qualidade de áudio XTTS vs F5-TTS (E2-TTS)
# - Valida cache de modelos e redução de chiado
###############################################################################

set -e

API_URL="http://localhost:8005"
VOICE_FILE="tests/Teste.ogg"

# Texto de teste (mesmo usado anteriormente)
TEST_TEXT="Olá! Este é um teste do sistema de síntese de voz com clonagem neural em português brasileiro. \
Estamos comparando a qualidade do modelo E2-TTS, que adiciona suporte emocional e prosódia avançada, \
com o modelo XTTS estável. O E2-TTS deve produzir áudio mais natural e expressivo, especialmente em \
conteúdos emocionais. Vamos avaliar se a redução de chiado está funcionando corretamente e se o cache \
de modelos está persistindo entre reinicializações. Este texto tem emoções variadas: alegria, surpresa, \
e seriedade técnica, para testar a capacidade de expressão do novo modelo de emoção."

echo "=================================="
echo "🧪 TESTE E2-TTS vs XTTS"
echo "=================================="
echo ""

# Verificar se audio-voice está rodando
echo "📡 Verificando API..."
if ! curl -s -f "$API_URL/health" > /dev/null; then
    echo "❌ API não está respondendo em $API_URL"
    echo "Execute: docker restart audio-voice-api audio-voice-celery"
    exit 1
fi
echo "✅ API respondendo"
echo ""

# PASSO 1: Cleanup
echo "🧹 PASSO 1: Limpando sistema..."
echo "=================================="
cleanup_response=$(curl -s -X POST "$API_URL/admin/cleanup" \
    -H "Content-Type: application/json" || echo '{"error":"endpoint_not_found"}')
echo "$cleanup_response" | jq '.' 2>/dev/null || echo "$cleanup_response"
echo ""
sleep 2

# PASSO 2: Clone com XTTS
echo "🎤 PASSO 2: Clonando voz com XTTS..."
echo "=================================="
if [ ! -f "$VOICE_FILE" ]; then
    echo "❌ Arquivo $VOICE_FILE não encontrado"
    exit 1
fi

xtts_clone_response=$(curl -s -X POST "$API_URL/voices/clone" \
    -F "file=@$VOICE_FILE" \
    -F "name=TesteComparacao_XTTS_E2TTS" \
    -F "language=pt-BR" \
    -F "tts_engine=xtts")

echo "$xtts_clone_response" | jq '.'

# Pode retornar job_id (assíncrono) ou voice_id (síncrono)
clone_job_id=$(echo "$xtts_clone_response" | jq -r '.job_id // empty')
if [ -n "$clone_job_id" ]; then
    echo "⏳ Aguardando clone XTTS (job: $clone_job_id)..."
    for i in {1..60}; do
        job_status=$(curl -s "$API_URL/jobs/$clone_job_id")
        status=$(echo "$job_status" | jq -r '.status // empty')
        
        if [ "$status" = "completed" ]; then
            voice_id_xtts=$(echo "$job_status" | jq -r '.result.voice_id // .voice_id // empty')
            echo "✅ Clone XTTS concluído!"
            echo "$job_status" | jq '.'
            break
        elif [ "$status" = "failed" ]; then
            echo "❌ Clone XTTS falhou:"
            echo "$job_status" | jq '.'
            exit 1
        fi
        echo "   Status: $status (tentativa $i/60)"
        sleep 2
    done
else
    voice_id_xtts=$(echo "$xtts_clone_response" | jq -r '.voice_id // .id // empty')
fi

if [ -z "$voice_id_xtts" ]; then
    echo "❌ Falha ao clonar voz com XTTS"
    exit 1
fi
echo "✅ Voz XTTS clonada: $voice_id_xtts"
echo ""
sleep 2

# PASSO 3: Clone com F5-TTS (E2-TTS)
echo "🎭 PASSO 3: Clonando voz com F5-TTS (E2-TTS)..."
echo "=================================="
f5tts_clone_response=$(curl -s -X POST "$API_URL/voices/clone" \
    -F "file=@$VOICE_FILE" \
    -F "name=TesteComparacao_F5TTS_E2TTS" \
    -F "language=pt-BR" \
    -F "tts_engine=f5tts")

echo "$f5tts_clone_response" | jq '.'

# Pode retornar job_id (assíncrono) ou voice_id (síncrono)
clone_job_id=$(echo "$f5tts_clone_response" | jq -r '.job_id // empty')
if [ -n "$clone_job_id" ]; then
    echo "⏳ Aguardando clone F5-TTS (job: $clone_job_id)..."
    for i in {1..60}; do
        job_status=$(curl -s "$API_URL/jobs/$clone_job_id")
        status=$(echo "$job_status" | jq -r '.status // empty')
        
        if [ "$status" = "completed" ]; then
            voice_id_f5tts=$(echo "$job_status" | jq -r '.result.voice_id // .voice_id // empty')
            echo "✅ Clone F5-TTS concluído!"
            echo "$job_status" | jq '.'
            break
        elif [ "$status" = "failed" ]; then
            echo "❌ Clone F5-TTS falhou:"
            echo "$job_status" | jq '.'
            exit 1
        fi
        echo "   Status: $status (tentativa $i/60)"
        sleep 2
    done
else
    voice_id_f5tts=$(echo "$f5tts_clone_response" | jq -r '.voice_id // .id // empty')
fi

if [ -z "$voice_id_f5tts" ]; then
    echo "❌ Falha ao clonar voz com F5-TTS"
    exit 1
fi
echo "✅ Voz F5-TTS clonada: $voice_id_f5tts"
echo ""
sleep 2

# PASSO 4: Gerar áudio com XTTS
echo "🔊 PASSO 4: Gerando áudio com XTTS..."
echo "=================================="
xtts_job_response=$(curl -s -X POST "$API_URL/jobs" \
    -F "text=$TEST_TEXT" \
    -F "source_language=pt-BR" \
    -F "mode=dubbing_with_clone" \
    -F "voice_id=$voice_id_xtts" \
    -F "tts_engine=xtts" \
    -F "quality_profile_id=xtts_balanced")

echo "$xtts_job_response" | jq '.'

job_id_xtts=$(echo "$xtts_job_response" | jq -r '.id // .job_id // empty')
if [ -z "$job_id_xtts" ]; then
    echo "❌ Falha ao criar job XTTS"
    exit 1
fi

# Aguardar conclusão XTTS
echo "⏳ Aguardando processamento XTTS (job: $job_id_xtts)..."
for i in {1..60}; do
    status_response=$(curl -s "$API_URL/jobs/$job_id_xtts")
    status=$(echo "$status_response" | jq -r '.status // empty')
    
    if [ "$status" = "completed" ]; then
        echo "✅ XTTS concluído!"
        echo "$status_response" | jq '.'
        
        # Download do áudio
        output_file="output_xtts_e2tts_comparison.wav"
        curl -s -o "$output_file" "$API_URL/jobs/$job_id_xtts/download"
        file_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null)
        echo "📥 Download: $output_file ($(echo "scale=2; $file_size/1024" | bc) KB)"
        break
    elif [ "$status" = "failed" ]; then
        echo "❌ Job XTTS falhou:"
        echo "$status_response" | jq '.'
        exit 1
    fi
    
    echo "   Status: $status (tentativa $i/60)"
    sleep 2
done
echo ""

# PASSO 5: Gerar áudio com F5-TTS (E2-TTS)
echo "🎨 PASSO 5: Gerando áudio com F5-TTS (E2-TTS)..."
echo "=================================="
f5tts_job_response=$(curl -s -X POST "$API_URL/jobs" \
    -F "text=$TEST_TEXT" \
    -F "source_language=pt-BR" \
    -F "mode=dubbing_with_clone" \
    -F "voice_id=$voice_id_f5tts" \
    -F "tts_engine=f5tts" \
    -F "quality_profile_id=f5tts_ultra_quality")

echo "$f5tts_job_response" | jq '.'

job_id_f5tts=$(echo "$f5tts_job_response" | jq -r '.id // .job_id // empty')
if [ -z "$job_id_f5tts" ]; then
    echo "❌ Falha ao criar job F5-TTS"
    exit 1
fi

# Aguardar conclusão F5-TTS
echo "⏳ Aguardando processamento F5-TTS (job: $job_id_f5tts)..."
for i in {1..60}; do
    status_response=$(curl -s "$API_URL/jobs/$job_id_f5tts")
    status=$(echo "$status_response" | jq -r '.status // empty')
    
    if [ "$status" = "completed" ]; then
        echo "✅ F5-TTS (E2-TTS) concluído!"
        echo "$status_response" | jq '.'
        
        # Download do áudio
        output_file="output_f5tts_e2tts_comparison.wav"
        curl -s -o "$output_file" "$API_URL/jobs/$job_id_f5tts/download"
        file_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null)
        echo "📥 Download: $output_file ($(echo "scale=2; $file_size/1024" | bc) KB)"
        break
    elif [ "$status" = "failed" ]; then
        echo "❌ Job F5-TTS falhou:"
        echo "$status_response" | jq '.'
        exit 1
    fi
    
    echo "   Status: $status (tentativa $i/60)"
    sleep 2
done
echo ""

# PASSO 6: Verificar cache de modelos
echo "📦 PASSO 6: Verificando cache de modelos..."
echo "=================================="
echo "XTTS models cache:"
docker exec audio-voice-api ls -lh /app/models/xtts/ 2>/dev/null || echo "⚠️  Container não encontrado ou cache vazio"
echo ""
echo "F5-TTS/E2-TTS models cache:"
docker exec audio-voice-api ls -lh /app/models/f5tts/ 2>/dev/null || echo "⚠️  Container não encontrado ou cache vazio"
echo ""

# RESUMO
echo "=================================="
echo "✅ TESTE CONCLUÍDO"
echo "=================================="
echo ""
echo "📊 Resultados:"
echo "   - XTTS: output_xtts_e2tts_comparison.wav"
echo "   - F5-TTS (E2-TTS): output_f5tts_e2tts_comparison.wav"
echo ""
echo "🎧 Comparação de Qualidade:"
echo "   1. Ouça ambos os arquivos"
echo "   2. Avalie chiado/hiss (deve estar reduzido em F5-TTS)"
echo "   3. Compare naturalidade e expressão emocional (E2-TTS deve ser melhor)"
echo "   4. Verifique clareza e prosódia"
echo ""
echo "🔍 Checklist:"
echo "   [ ] Chiado/hiss reduzido no F5-TTS?"
echo "   [ ] E2-TTS mais expressivo que antes?"
echo "   [ ] XTTS mantém qualidade estável?"
echo "   [ ] Cache de modelos funcionando?"
echo ""
