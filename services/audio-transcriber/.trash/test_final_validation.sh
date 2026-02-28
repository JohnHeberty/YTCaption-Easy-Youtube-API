#!/bin/bash
# Teste final de validação: Word-level timestamps

API_URL="http://localhost:8004"
TEST_FILE="/root/YTCaption-Easy-Youtube-API/services/audio-transcriber/tests/TEST-.ogg"

echo "═══════════════════════════════════════════════════════════════════════"
echo "🎯 VALIDAÇÃO FINAL: Word-Level Timestamps"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

# 1. Verifica engines disponíveis
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TESTE 1: Endpoint /engines (dropdown)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ENGINES_RESPONSE=$(curl -s "${API_URL}/engines")
TOTAL_ENGINES=$(echo "$ENGINES_RESPONSE" | jq '.engines | length')
WORD_TIMESTAMP_ENGINES=$(echo "$ENGINES_RESPONSE" | jq '[.engines[] | select(.features.word_timestamps == true)] | length')

echo "✅ Engines disponíveis: $TOTAL_ENGINES"
echo "✅ Engines com word-timestamps: $WORD_TIMESTAMP_ENGINES"
echo ""
echo "Engines detalhados:"
echo "$ENGINES_RESPONSE" | jq -r '.engines[] | "  [\(.id)]: available=\(.available), word_timestamps=\(.features.word_timestamps), precision=\(.features.word_timestamps_precision)"'
echo ""

if [ "$WORD_TIMESTAMP_ENGINES" -lt 1 ]; then
  echo "❌ ERRO: Nenhum engine com word-timestamps disponível!"
  exit 1
fi

# 2. Teste de transcrição com faster-whisper
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TESTE 2: Transcrição com faster-whisper (word-level)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESPONSE=$(curl -s -X POST "${API_URL}/jobs" \
  -F "file=@${TEST_FILE}" \
  -F "language_in=pt" \
  -F "engine=faster-whisper")

JOB_ID=$(echo "$RESPONSE" | jq -r '.id')

if [ -z "$JOB_ID" ] || [ "$JOB_ID" == "null" ]; then
  echo "❌ ERRO ao criar job"
  exit 1
fi

echo "✅ Job criado: $JOB_ID"
echo ""

# Aguarda processamento
echo "⏳ Aguardando processamento..."
for i in {1..40}; do
  sleep 2
  JOB=$(curl -s "${API_URL}/jobs/${JOB_ID}")
  STATUS=$(echo "$JOB" | jq -r '.status')
  
  if [ "$STATUS" == "completed" ]; then
    echo ""
    echo "✅ Transcrição completa!"
    break
  elif [ "$STATUS" == "failed" ]; then
    echo ""
    echo "❌ Transcrição falhou:"
    echo "$JOB" | jq '{error_message}'
    exit 1
  fi
  
  echo -n "."
done

echo ""

# 3. Validação de word-level timestamps
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TESTE 3: Validação de timestamps palavra por palavra"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

JOB=$(curl -s "${API_URL}/jobs/${JOB_ID}")

# Estatísticas
TOTAL_SEGMENTS=$(echo "$JOB" | jq '.transcription_segments | length')
SEGMENTS_WITH_WORDS=$(echo "$JOB" | jq '[.transcription_segments[] | select(.words != null and (.words | length) > 0)] | length')
TOTAL_WORDS=$(echo "$JOB" | jq '[.transcription_segments[].words // [] | length] | add // 0')

echo "📊 Estatísticas:"
echo "   Segmentos: $TOTAL_SEGMENTS"
echo "   Segmentos com words: $SEGMENTS_WITH_WORDS"
echo "   Total de palavras: $TOTAL_WORDS"
echo ""

# Validação
if [ "$TOTAL_WORDS" -gt 0 ]; then
  echo "✅ WORD-LEVEL TIMESTAMPS: FUNCIONANDO"
  echo ""
  
  # Mostra exemplo de palavras
  echo "🔍 Exemplo de palavras transcritas (primeiras 5):"
  echo "$JOB" | jq '.transcription_segments[0].words[0:5] | .[] | "   [\(.start)s - \(.end)s] \(.word) (prob: \(.probability | . * 100 | round / 100))"' -r
  echo ""
  
  # Verifica estrutura completa
  FIRST_WORD=$(echo "$JOB" | jq '.transcription_segments[0].words[0]')
  HAS_WORD=$(echo "$FIRST_WORD" | jq 'has("word")')
  HAS_START=$(echo "$FIRST_WORD" | jq 'has("start")')
  HAS_END=$(echo "$FIRST_WORD" | jq 'has("end")')
  HAS_PROB=$(echo "$FIRST_WORD" | jq 'has("probability")')
  
  echo "✅ Validação de estrutura:"
  echo "   - Campo 'word': $HAS_WORD"
  echo "   - Campo 'start': $HAS_START"
  echo "   - Campo 'end': $HAS_END"
  echo "   - Campo 'probability': $HAS_PROB"
  echo ""
  
  if [ "$HAS_WORD" == "true" ] && [ "$HAS_START" == "true" ] && [ "$HAS_END" == "true" ] && [ "$HAS_PROB" == "true" ]; then
    echo "✅ Estrutura completa OK!"
    echo ""
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 TODOS OS TESTES PASSARAM!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "✅ Engine faster-whisper funcionando com word-level timestamps"
    echo "✅ Total de $TOTAL_WORDS palavras transcritas"
    echo "✅ Cada palavra tem: word, start, end, probability"
    echo "✅ Endpoint /engines retornando opções (dropdown OK)"
    echo ""
    exit 0
  else
    echo "❌ ERRO: Estrutura incompleta!"
    exit 1
  fi
else
  echo "❌ WORD-LEVEL TIMESTAMPS: NÃO ENCONTRADO"
  echo ""
  echo "Primeira palavra encontrada:"
  echo "$JOB" | jq '.transcription_segments[0].words[0] // {}'
  exit 1
fi
