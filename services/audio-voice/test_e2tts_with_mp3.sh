#!/bin/bash
set -e

API_URL="http://localhost:8005"
AUDIO_FILE="/home/john/YTCaption-Easy-Youtube-API/services/audio-transcriber/uploads/c3344fe9fa83_transcribe_pt.mp3"

echo "=========================================="
echo "E2-TTS EMOTION MODEL - PRODUCTION TEST"
echo "Model: E2TTS_v1_Base (SWivid/E2-TTS)"
echo "Audio: $(basename $AUDIO_FILE)"
echo "=========================================="
echo ""

# Step 1: Clone voice
echo "📋 Step 1: Voice Clone com E2-TTS"
CLONE_RESPONSE=$(curl -s -X POST "${API_URL}/voices/clone" \
  -F "file=@${AUDIO_FILE}" \
  -F "name=E2TTS_Test_$(date +%H%M%S)" \
  -F "language=pt-BR" \
  -F "tts_engine=f5tts")

CLONE_JOB_ID=$(echo "$CLONE_RESPONSE" | jq -r '.id // .job_id')
echo "Job ID: $CLONE_JOB_ID"

# Poll clone
echo "Aguardando clone..."
for i in {1..60}; do
  sleep 5
  STATUS=$(curl -s "${API_URL}/jobs/${CLONE_JOB_ID}" | jq -r '.status')
  
  if [ "$STATUS" = "completed" ]; then
    VOICE_ID=$(curl -s "${API_URL}/jobs/${CLONE_JOB_ID}" | jq -r '.voice_id')
    echo "✅ Clone concluído! Voice ID: $VOICE_ID"
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "❌ Clone falhou!"
    curl -s "${API_URL}/jobs/${CLONE_JOB_ID}" | jq '.'
    exit 1
  fi
  
  echo "Status: $STATUS ($i/60)"
done

if [ -z "$VOICE_ID" ]; then
  echo "❌ Timeout"
  exit 1
fi

echo ""

# Step 2: Synthesize
echo "📋 Step 2: Síntese com E2-TTS (Emotion Model)"
TEXT="Olá! Este é um teste do modelo E2-TTS com suporte a emoções. Estou muito feliz e animado!"

SYNTH_RESPONSE=$(curl -s -X POST "${API_URL}/jobs" \
  -F "text=${TEXT}" \
  -F "source_language=pt-BR" \
  -F "mode=dubbing_with_clone" \
  -F "voice_id=${VOICE_ID}" \
  -F "tts_engine=f5tts" \
  -F "quality_profile_id=f5tts_balanced")

SYNTH_JOB_ID=$(echo "$SYNTH_RESPONSE" | jq -r '.id')
echo "Job ID: $SYNTH_JOB_ID"

# Poll synthesis
echo "Aguardando síntese..."
for i in {1..120}; do
  sleep 5
  RESPONSE=$(curl -s "${API_URL}/jobs/${SYNTH_JOB_ID}")
  STATUS=$(echo "$RESPONSE" | jq -r '.status')
  
  if [ "$STATUS" = "completed" ]; then
    echo "✅ Síntese concluída!"
    echo "$RESPONSE" | jq '{status, tts_engine_used, duration, file_size_output}'
    
    curl -s "${API_URL}/jobs/${SYNTH_JOB_ID}/download" -o test_e2tts_final.wav
    echo ""
    echo "✅ Áudio salvo: test_e2tts_final.wav"
    ls -lh test_e2tts_final.wav
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "❌ Síntese falhou!"
    echo "$RESPONSE" | jq '.'
    exit 1
  fi
  
  echo "Status: $STATUS ($i/120)"
done
