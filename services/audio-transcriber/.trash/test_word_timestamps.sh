#!/bin/bash
# Teste de word-level timestamps com faster-whisper

API_URL="http://localhost:8004"
TEST_FILE="/root/YTCaption-Easy-Youtube-API/services/audio-transcriber/tests/TEST-.ogg"

echo "========================================================================"
echo "🧪 TESTE DE WORD-LEVEL TIMESTAMPS - Faster-Whisper"
echo "========================================================================"
echo ""

# 1. Verifica engines disponíveis
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Engines disponíveis:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s "${API_URL}/engines" | jq -r '.engines[] | "  [\(.id)]: word_timestamps=\(.features.word_timestamps), precision=\(.features.word_timestamps_precision)"'
echo ""

# 2. Cria job com faster-whisper
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎤 Criando job de transcrição com faster-whisper..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESPONSE=$(curl -s -X POST "${API_URL}/jobs" \
  -F "file=@${TEST_FILE}" \
  -F "language_in=auto" \
  -F "engine=faster-whisper")

JOB_ID=$(echo "$RESPONSE" | jq -r '.id // .job_id // empty')

if [ -z "$JOB_ID" ]; then
  echo "❌ Erro ao criar job"
  echo "$RESPONSE" | jq '.'
  exit 1
fi

echo "✅ Job criado: $JOB_ID"
echo ""

# 3. Aguarda processamento
echo "⏳ Aguardando processamento (máximo 60s)..."
for i in {1..60}; do
  sleep 1
  STATUS=$(curl -s "${API_URL}/jobs/${JOB_ID}" | jq -r '.status')
  
  if [ "$STATUS" == "completed" ]; then
    echo ""
    echo "✅ Transcrição COMPLETA!"
    break
  elif [ "$STATUS" == "failed" ]; then
    echo ""
    echo "❌ Transcrição FALHOU"
    curl -s "${API_URL}/jobs/${JOB_ID}" | jq '{status, error_message}'
    exit 1
  fi
  
  echo -n "."
done

echo ""
echo ""

# 4. Verifica word-level timestamps
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 VALIDAÇÃO: Word-Level Timestamps"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESULT=$(curl -s "${API_URL}/jobs/${JOB_ID}")

# Extrai segmentos
SEGMENTS=$(echo "$RESULT" | jq '.transcription_segments // []')
NUM_SEGMENTS=$(echo "$SEGMENTS" | jq 'length')

echo "📊 Estatísticas:"
echo "   - Segmentos: $NUM_SEGMENTS"

# Verifica se tem words
HAS_WORDS=$(echo "$SEGMENTS" | jq '[.[] | select(.words != null and (.words | length) > 0)] | length')

if [ "$HAS_WORDS" -gt 0 ]; then
  echo "   - Segmentos com words: $HAS_WORDS"
  
  # Mostra primeiro segmento com words
  echo ""
  echo "🔍 Exemplo de segmento com words:"
  echo "$SEGMENTS" | jq '[.[] | select(.words != null and (.words | length) > 0)][0] | {
    text,
    start,
    end,
    words: [.words[] | {word, start, end, probability}]
  }'
  
  # Conta total de palavras
  TOTAL_WORDS=$(echo "$SEGMENTS" | jq '[.[] | select(.words != null) | .words | length] | add // 0')
  echo ""
  echo "✅ WORD-LEVEL TIMESTAMPS: SIM"
  echo "   Total de palavras com timestamps: $TOTAL_WORDS"
  
else
  echo ""
  echo "❌ WORD-LEVEL TIMESTAMPS: NÃO ENCONTRADO"
  echo ""
  echo "📋 Estrutura do primeiro segmento:"
  echo "$SEGMENTS" | jq '.[0] // {}'
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
