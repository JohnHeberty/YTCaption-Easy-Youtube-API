#!/bin/bash
set -e

API_URL="http://localhost:8005"
AUDIO_FILE="./tests/Teste.ogg"

echo "=========================================="
echo "🎯 E2-TTS EMOTION MODEL - PRODUCTION TEST"
echo "=========================================="
echo "Model: E2TTS (SWivid/E2-TTS)"
echo "Audio: $(basename $AUDIO_FILE)"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# Verificar se arquivo existe
if [ ! -f "$AUDIO_FILE" ]; then
    echo "❌ Arquivo não encontrado: $AUDIO_FILE"
    exit 1
fi

# Verificar duração do áudio
echo "🔍 Verificando áudio..."
FILE_SIZE=$(stat -c%s "$AUDIO_FILE")
echo "   Tamanho: ${FILE_SIZE} bytes"
echo ""

# Step 1: Clone de voz com E2-TTS
echo "📋 Step 1: Voice Clone com E2-TTS (Emotion Model)"
echo "   Enviando requisição..."

CLONE_RESPONSE=$(curl -s -X POST "${API_URL}/voices/clone" \
  -F "file=@${AUDIO_FILE}" \
  -F "name=E2TTS_Production_$(date +%H%M%S)" \
  -F "language=pt-BR" \
  -F "tts_engine=f5tts")

CLONE_JOB_ID=$(echo "$CLONE_RESPONSE" | jq -r '.id // .job_id')

if [ "$CLONE_JOB_ID" == "null" ] || [ -z "$CLONE_JOB_ID" ]; then
    echo "❌ Erro ao criar job de clone!"
    echo "$CLONE_RESPONSE" | jq '.'
    exit 1
fi

echo "   ✅ Job criado: $CLONE_JOB_ID"
echo ""

# Poll clone job
echo "   Aguardando conclusão da clonagem..."
VOICE_ID=""
for i in {1..60}; do
  sleep 5
  STATUS_RESPONSE=$(curl -s "${API_URL}/jobs/${CLONE_JOB_ID}")
  STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
  
  echo -ne "   Tentativa $i/60: Status=$STATUS\r"
  
  if [ "$STATUS" = "completed" ]; then
    VOICE_ID=$(echo "$STATUS_RESPONSE" | jq -r '.voice_id')
    ENGINE_USED=$(echo "$STATUS_RESPONSE" | jq -r '.tts_engine_used // "unknown"')
    echo ""
    echo "   ✅ Clone concluído!"
    echo "   Voice ID: $VOICE_ID"
    echo "   Engine usado: $ENGINE_USED"
    
    # Verificar se foi F5-TTS
    if [ "$ENGINE_USED" != "f5tts" ]; then
        echo "   ⚠️  AVISO: Engine usado foi $ENGINE_USED (esperado: f5tts)"
    fi
    break
  elif [ "$STATUS" = "failed" ]; then
    echo ""
    echo "   ❌ Clone falhou!"
    echo "$STATUS_RESPONSE" | jq '.'
    exit 1
  fi
done

echo ""

if [ -z "$VOICE_ID" ]; then
  echo "❌ Timeout no voice clone (5 minutos)"
  exit 1
fi

# Step 2: Síntese com E2-TTS
echo "📋 Step 2: Síntese com E2-TTS (Emotion Model)"
TEXT="Olá! Este é um teste completo do modelo E2-TTS com suporte emocional. Estou muito feliz e animado de testar este sistema incrível de síntese de voz com emoções naturais e expressivas!"

echo "   Texto: \"${TEXT:0:80}...\""
echo "   Enviando requisição..."

SYNTH_RESPONSE=$(curl -s -X POST "${API_URL}/jobs" \
  -F "text=${TEXT}" \
  -F "source_language=pt-BR" \
  -F "mode=dubbing_with_clone" \
  -F "voice_id=${VOICE_ID}" \
  -F "tts_engine=f5tts" \
  -F "quality_profile_id=f5tts_balanced")

SYNTH_JOB_ID=$(echo "$SYNTH_RESPONSE" | jq -r '.id')

if [ "$SYNTH_JOB_ID" == "null" ] || [ -z "$SYNTH_JOB_ID" ]; then
    echo "❌ Erro ao criar job de síntese!"
    echo "$SYNTH_RESPONSE" | jq '.'
    exit 1
fi

echo "   ✅ Job criado: $SYNTH_JOB_ID"
echo ""

# Poll synthesis job
echo "   Aguardando conclusão da síntese (pode levar ~3min em CPU)..."
for i in {1..120}; do
  sleep 5
  RESPONSE=$(curl -s "${API_URL}/jobs/${SYNTH_JOB_ID}")
  STATUS=$(echo "$RESPONSE" | jq -r '.status')
  
  echo -ne "   Tentativa $i/120: Status=$STATUS\r"
  
  if [ "$STATUS" = "completed" ]; then
    echo ""
    echo "   ✅ Síntese concluída!"
    
    ENGINE_USED=$(echo "$RESPONSE" | jq -r '.tts_engine_used')
    DURATION=$(echo "$RESPONSE" | jq -r '.duration')
    FILE_SIZE=$(echo "$RESPONSE" | jq -r '.file_size_output')
    
    echo "   Engine usado: $ENGINE_USED"
    echo "   Duração: ${DURATION}s"
    echo "   Tamanho: ${FILE_SIZE} bytes"
    
    # Verificar se foi F5-TTS
    if [ "$ENGINE_USED" != "f5tts" ]; then
        echo "   ⚠️  AVISO: Engine usado foi $ENGINE_USED (esperado: f5tts)"
        echo "   Possível fallback para XTTS!"
    fi
    
    # Download áudio
    echo ""
    echo "📥 Baixando áudio gerado..."
    OUTPUT_FILE="test_e2tts_production_output.wav"
    curl -s "${API_URL}/jobs/${SYNTH_JOB_ID}/download" -o "$OUTPUT_FILE"
    
    if [ -f "$OUTPUT_FILE" ]; then
      DOWNLOADED_SIZE=$(stat -c%s "$OUTPUT_FILE")
      echo "   ✅ Áudio salvo: $OUTPUT_FILE"
      echo "   Tamanho: ${DOWNLOADED_SIZE} bytes"
      
      # File info
      echo ""
      echo "🔍 Informações do Áudio Gerado:"
      file "$OUTPUT_FILE"
      
      echo ""
      echo "=========================================="
      echo "✅ TESTE CONCLUÍDO COM SUCESSO!"
      echo "=========================================="
      echo "Output: $OUTPUT_FILE"
      echo "Model: E2TTS (Emotion Support)"
      echo "Engine: $ENGINE_USED"
      echo "Quality: f5tts_balanced (NFE 40)"
      echo ""
      
      # Verificar se realmente usou E2-TTS
      if [ "$ENGINE_USED" = "f5tts" ]; then
          echo "🎉 E2-TTS FUNCIONANDO PERFEITAMENTE!"
      else
          echo "⚠️  ATENÇÃO: Fallback para XTTS detectado!"
          echo "Verificar logs: docker logs audio-voice-celery | grep -A10 F5-TTS"
      fi
      
    else
      echo "❌ Falha ao baixar áudio"
      exit 1
    fi
    
    break
  elif [ "$STATUS" = "failed" ]; then
    echo ""
    echo "   ❌ Síntese falhou!"
    echo "$RESPONSE" | jq '.'
    exit 1
  fi
done

if [ "$STATUS" != "completed" ]; then
    echo ""
    echo "❌ Timeout na síntese (10 minutos)"
    exit 1
fi
