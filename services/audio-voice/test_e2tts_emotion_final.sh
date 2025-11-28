#!/bin/bash
set -e

API_URL="http://localhost:8005"
AUDIO_FILE="./tests/output_clone_analysis/cloned_audio.wav"

echo "=========================================="
echo "E2-TTS EMOTION MODEL TEST"
echo "Model: SWivid/E2-TTS (E2TTS_v1_Base)"
echo "=========================================="
echo ""

# Cleanup
echo "🧹 Cleanup de testes anteriores..."
rm -f test_e2tts_emotion_*.wav 2>/dev/null || true

# Step 1: Clone voice with E2-TTS
echo "📋 Step 1: Voice Clone com E2-TTS (Emotion Model)"
CLONE_RESPONSE=$(curl -s -X POST "${API_URL}/voices/clone" \
  -F "file=@${AUDIO_FILE}" \
  -F "name=E2TTS_Emotion_Test_$(date +%s)" \
  -F "language=pt-BR" \
  -F "tts_engine=f5tts")

echo "   Response: $CLONE_RESPONSE"
CLONE_JOB_ID=$(echo "$CLONE_RESPONSE" | jq -r '.id // .job_id')
echo "   Job ID: $CLONE_JOB_ID"

# Poll clone job
echo "   Aguardando conclusão da clonagem..."
for i in {1..60}; do
  sleep 3
  STATUS_RESPONSE=$(curl -s "${API_URL}/jobs/${CLONE_JOB_ID}")
  STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
  
  if [ "$STATUS" = "completed" ]; then
    VOICE_ID=$(echo "$STATUS_RESPONSE" | jq -r '.voice_id')
    echo "   ✅ Voice Clone concluído!"
    echo "   Voice ID: $VOICE_ID"
    echo "   Engine: $(echo "$STATUS_RESPONSE" | jq -r '.tts_engine_used')"
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "   ❌ Clone falhou!"
    echo "$STATUS_RESPONSE" | jq '.'
    exit 1
  fi
  
  echo "   Status: $STATUS (tentativa $i/60)"
done

if [ -z "$VOICE_ID" ]; then
  echo "❌ Timeout no voice clone"
  exit 1
fi

echo ""

# Step 2: Synthesize com E2-TTS (teste de emoção)
echo "📋 Step 2: Síntese com E2-TTS - Teste de Emoção"
TEXT="Olá! Este é um teste do modelo E2-TTS com suporte emocional. Estou muito feliz e animado de testar este novo modelo!"

SYNTH_RESPONSE=$(curl -s -X POST "${API_URL}/jobs" \
  -F "text=${TEXT}" \
  -F "source_language=pt-BR" \
  -F "mode=dubbing_with_clone" \
  -F "voice_id=${VOICE_ID}" \
  -F "tts_engine=f5tts" \
  -F "quality_profile_id=f5tts_balanced")

SYNTH_JOB_ID=$(echo "$SYNTH_RESPONSE" | jq -r '.id')
echo "   Job ID: $SYNTH_JOB_ID"

# Poll synthesis job
echo "   Aguardando conclusão da síntese..."
for i in {1..120}; do
  sleep 3
  STATUS_RESPONSE=$(curl -s "${API_URL}/jobs/${SYNTH_JOB_ID}")
  STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
  
  if [ "$STATUS" = "completed" ]; then
    echo "   ✅ Síntese concluída!"
    echo "   Engine: $(echo "$STATUS_RESPONSE" | jq -r '.tts_engine_used')"
    echo "   Duration: $(echo "$STATUS_RESPONSE" | jq -r '.duration')s"
    echo "   File Size: $(echo "$STATUS_RESPONSE" | jq -r '.file_size_output') bytes"
    
    # Download audio
    echo ""
    echo "📥 Downloading áudio..."
    curl -s "${API_URL}/jobs/${SYNTH_JOB_ID}/download" -o test_e2tts_emotion_output.wav
    
    # Validate
    if [ -f test_e2tts_emotion_output.wav ]; then
      FILE_SIZE=$(stat -c%s test_e2tts_emotion_output.wav)
      echo "   ✅ Áudio baixado: test_e2tts_emotion_output.wav (${FILE_SIZE} bytes)"
      
      # File info
      echo ""
      echo "🔍 Informações do Áudio:"
      file test_e2tts_emotion_output.wav
      
      echo ""
      echo "=========================================="
      echo "✅ E2-TTS EMOTION MODEL TEST COMPLETED!"
      echo "=========================================="
      echo "Output: test_e2tts_emotion_output.wav"
      echo "Model: E2TTS_v1_Base (SWivid/E2-TTS)"
      echo "Engine: f5tts"
      echo "Quality: balanced (NFE 40)"
      echo ""
    else
      echo "❌ Falha ao baixar áudio"
      exit 1
    fi
    
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "   ❌ Síntese falhou!"
    echo "$STATUS_RESPONSE" | jq '.'
    exit 1
  fi
  
  echo "   Status: $STATUS (tentativa $i/120)"
done
