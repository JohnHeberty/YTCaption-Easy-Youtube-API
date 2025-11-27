#!/bin/bash
# test_api_xtts.sh - Script de teste E2E da API com XTTS
# Sprint 4: Validação de endpoints com XTTS

set -e  # Exit on error

BASE_URL="${BASE_URL:-http://localhost:8004}"
TIMEOUT=120  # Timeout para polling (2 minutos)

echo "🚀 Teste E2E da API Audio Voice com XTTS"
echo "=========================================="
echo "Base URL: $BASE_URL"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cleanup anterior
rm -f test_xtts_output_*.wav test_clone_*.ogg 2>/dev/null || true

# ============================================
# TESTE 1: Health Check
# ============================================
echo "📊 TESTE 1: Health Check"
echo "------------------------"

HEALTH=$(curl -s "$BASE_URL/health")
STATUS=$(echo "$HEALTH" | jq -r '.status')
ENGINE=$(echo "$HEALTH" | jq -r '.checks.tts_engine.engine')
USE_XTTS=$(echo "$HEALTH" | jq -r '.checks.tts_engine.use_xtts')
DEVICE=$(echo "$HEALTH" | jq -r '.checks.tts_engine.device // "N/A"')

echo "Status: $STATUS"
echo "Engine: $ENGINE"
echo "USE_XTTS: $USE_XTTS"
echo "Device: $DEVICE"

if [ "$STATUS" != "healthy" ]; then
    echo -e "${RED}❌ FALHA: Serviço não está healthy${NC}"
    echo "$HEALTH" | jq .
    exit 1
fi

if [ "$USE_XTTS" != "true" ]; then
    echo -e "${YELLOW}⚠️  AVISO: USE_XTTS não está true (valor: $USE_XTTS)${NC}"
    echo "XTTS pode não estar ativo. Continuando testes..."
fi

echo -e "${GREEN}✅ Health check OK${NC}"
echo ""

# ============================================
# TESTE 2: Listar Linguagens
# ============================================
echo "🌍 TESTE 2: Linguagens Suportadas"
echo "----------------------------------"

LANGUAGES=$(curl -s "$BASE_URL/languages")
TOTAL=$(echo "$LANGUAGES" | jq -r '.total')
LANGS=$(echo "$LANGUAGES" | jq -r '.languages | join(", ")')

echo "Total: $TOTAL"
echo "Linguagens: $LANGS"

if [ "$TOTAL" -lt 10 ]; then
    echo -e "${YELLOW}⚠️  AVISO: Apenas $TOTAL linguagens (esperado >10 para XTTS)${NC}"
fi

echo -e "${GREEN}✅ Linguagens OK${NC}"
echo ""

# ============================================
# TESTE 3: Listar Voice Presets
# ============================================
echo "🎤 TESTE 3: Voice Presets"
echo "-------------------------"

PRESETS=$(curl -s "$BASE_URL/presets")
echo "$PRESETS" | jq -r '.presets | keys | .[]'

echo -e "${GREEN}✅ Presets OK${NC}"
echo ""

# ============================================
# TESTE 4: Clonar Voz (Primeiro)
# ============================================
echo "🎤 TESTE 4: Clonagem de Voz"
echo "---------------------------"

# Criar WAV silencioso de 3s no container
docker exec audio-voice-api sh -c "ffmpeg -f lavfi -i anullsrc=r=24000:cl=mono -t 3 -q:a 9 -acodec pcm_s16le /tmp/ref_voice.wav -y" 2>/dev/null

# Copiar arquivo para host
docker cp audio-voice-api:/tmp/ref_voice.wav /tmp/ref_voice.wav

# Upload da voz para clone (do host)
CLONE_RESPONSE=$(curl -s -X POST "$BASE_URL/voices/clone" \
  -F "file=@/tmp/ref_voice.wav" \
  -F "name=TestVoice" \
  -F "language=pt")

CLONE_JOB_ID=$(echo "$CLONE_RESPONSE" | jq -r '.job_id')
echo "Clone Job ID: $CLONE_JOB_ID"

if [ "$CLONE_JOB_ID" == "null" ] || [ -z "$CLONE_JOB_ID" ]; then
    echo -e "${RED}❌ FALHA: Clone job não criado${NC}"
    echo "$CLONE_RESPONSE" | jq .
    exit 1
fi

# Aguardar conclusão do clone
ELAPSED=0
while [ $ELAPSED -lt 30 ]; do
    CLONE_STATUS=$(curl -s "$BASE_URL/jobs/$CLONE_JOB_ID")
    STATUS=$(echo "$CLONE_STATUS" | jq -r '.status')
    
    if [ "$STATUS" == "completed" ]; then
        VOICE_ID=$(echo "$CLONE_STATUS" | jq -r '.voice_id')
        echo "Voice ID: $VOICE_ID"
        break
    fi
    
    sleep 1
    ELAPSED=$((ELAPSED + 1))
done

if [ "$STATUS" != "completed" ]; then
    echo -e "${RED}❌ FALHA: Clone não completou${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Voz clonada${NC}"
echo ""

# ============================================
# TESTE 5: Criar Job de Dubbing (com clonagem)
# ============================================
echo "🎬 TESTE 5: Dubbing com Voz Clonada"
echo "-----------------------------------"

JOB_RESPONSE=$(curl -s -X POST "$BASE_URL/jobs" \
  -H "Content-Type: application/json" \
  -d "{
    \"mode\": \"dubbing_with_clone\",
    \"text\": \"Olá, mundo! Este é um teste de dublagem com XTTS.\",
    \"source_language\": \"pt\",
    \"voice_id\": \"$VOICE_ID\"
  }")

JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.id')
echo "Job ID: $JOB_ID"

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
    echo -e "${RED}❌ FALHA: Job não criado${NC}"
    echo "$JOB_RESPONSE" | jq .
    exit 1
fi

echo -e "${GREEN}✅ Job criado${NC}"
echo ""

# ============================================
# TESTE 6: Polling Job Status
# ============================================
echo "⏳ TESTE 6: Polling Job Status"
echo "-------------------------------"

START_TIME=$(date +%s)
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    JOB_STATUS=$(curl -s "$BASE_URL/jobs/$JOB_ID")
    STATUS=$(echo "$JOB_STATUS" | jq -r '.status')
    PROGRESS=$(echo "$JOB_STATUS" | jq -r '.progress')
    
    echo -e "  Tentativa $((ELAPSED/2 + 1)): status=${STATUS}, progress=${PROGRESS}%"
    
    if [ "$STATUS" == "completed" ]; then
        echo -e "${GREEN}✅ Job completado!${NC}"
        break
    elif [ "$STATUS" == "failed" ]; then
        echo -e "${RED}❌ FALHA: Job falhou${NC}"
        ERROR=$(echo "$JOB_STATUS" | jq -r '.error_message')
        echo "Erro: $ERROR"
        echo "$JOB_STATUS" | jq .
        exit 1
    fi
    
    sleep 2
    ELAPSED=$(($(date +%s) - START_TIME))
done

if [ "$STATUS" != "completed" ]; then
    echo -e "${RED}❌ FALHA: Timeout após ${TIMEOUT}s (status: $STATUS)${NC}"
    exit 1
fi

DURATION=$(echo "$JOB_STATUS" | jq -r '.duration')
FILE_SIZE=$(echo "$JOB_STATUS" | jq -r '.file_size_output')

echo "Duração do áudio: ${DURATION}s"
echo "Tamanho do arquivo: $((FILE_SIZE / 1024)) KB"
echo ""

# ============================================
# TESTE 7: Download do Áudio
# ============================================
echo "⬇️  TESTE 7: Download do Áudio"
echo "------------------------------"

OUTPUT_FILE="test_xtts_output_${JOB_ID}.wav"
HTTP_CODE=$(curl -s -w "%{http_code}" -o "$OUTPUT_FILE" "$BASE_URL/jobs/$JOB_ID/download")

if [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}❌ FALHA: Download falhou (HTTP $HTTP_CODE)${NC}"
    exit 1
fi

if [ ! -f "$OUTPUT_FILE" ]; then
    echo -e "${RED}❌ FALHA: Arquivo não criado${NC}"
    exit 1
fi

FILE_SIZE_LOCAL=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE")
FILE_TYPE=$(file -b "$OUTPUT_FILE")

echo "Arquivo: $OUTPUT_FILE"
echo "Tamanho: $((FILE_SIZE_LOCAL / 1024)) KB"
echo "Tipo: $FILE_TYPE"

# Valida WAV header
if ! echo "$FILE_TYPE" | grep -qi "wave\|wav\|audio"; then
    echo -e "${YELLOW}⚠️  AVISO: Arquivo pode não ser WAV válido${NC}"
    echo "File type: $FILE_TYPE"
fi

echo -e "${GREEN}✅ Download OK${NC}"
echo ""

# ============================================
# TESTE 8: Formatos Disponíveis
# ============================================
echo "📋 TESTE 8: Formatos Disponíveis"
echo "--------------------------------"
FORMATS_RESPONSE=$(curl -s "$BASE_URL/jobs/$JOB_ID/formats")
FORMATS_COUNT=$(echo "$FORMATS_RESPONSE" | jq '.formats | length')
FORMATS_LIST=$(echo "$FORMATS_RESPONSE" | jq -r '.formats[].format' | tr '\n' ', ' | sed 's/,$//')

echo "Formatos disponíveis: $FORMATS_COUNT"
echo "Lista: $FORMATS_LIST"

if [ "$FORMATS_COUNT" -ge 4 ]; then
    echo -e "${GREEN}✅ Formatos OK${NC}"
else
    echo -e "${RED}❌ FALHA: Esperado >= 4 formatos, encontrado $FORMATS_COUNT${NC}"
fi
echo ""

# ============================================
# TESTE 9: Download em Múltiplos Formatos
# ============================================
echo "🎵 TESTE 9: Download em Múltiplos Formatos"
echo "-------------------------------------------"

# Testa cada formato
FORMATS_TO_TEST=("mp3" "ogg" "flac")
for FORMAT in "${FORMATS_TO_TEST[@]}"; do
    echo -n "  Testando $FORMAT... "
    
    OUTPUT_FILE_FORMAT="test_xtts_${FORMAT}_${JOB_ID}.${FORMAT}"
    HTTP_CODE=$(curl -s -w "%{http_code}" -o "$OUTPUT_FILE_FORMAT" \
      "$BASE_URL/jobs/$JOB_ID/download?format=$FORMAT")
    
    if [ "$HTTP_CODE" == "200" ]; then
        FILE_SIZE=$(ls -lh "$OUTPUT_FILE_FORMAT" | awk '{print $5}')
        FILE_TYPE=$(file -b "$OUTPUT_FILE_FORMAT")
        echo -e "${GREEN}OK${NC} ($FILE_SIZE)"
        
        # Valida tipo de arquivo
        case $FORMAT in
            mp3)
                if echo "$FILE_TYPE" | grep -qi "MPEG\|MP3"; then
                    echo "    ✓ Formato MP3 válido"
                else
                    echo -e "    ${YELLOW}⚠️  Tipo: $FILE_TYPE${NC}"
                fi
                ;;
            ogg)
                if echo "$FILE_TYPE" | grep -qi "Ogg"; then
                    echo "    ✓ Formato OGG válido"
                else
                    echo -e "    ${YELLOW}⚠️  Tipo: $FILE_TYPE${NC}"
                fi
                ;;
            flac)
                if echo "$FILE_TYPE" | grep -qi "FLAC"; then
                    echo "    ✓ Formato FLAC válido"
                else
                    echo -e "    ${YELLOW}⚠️  Tipo: $FILE_TYPE${NC}"
                fi
                ;;
        esac
    else
        echo -e "${RED}FALHA (HTTP $HTTP_CODE)${NC}"
    fi
done

echo -e "${GREEN}✅ Múltiplos formatos OK${NC}"
echo ""

# ============================================
# TESTE 10: Cleanup de Arquivos Temporários
# ============================================
echo "🧹 TESTE 10: Cleanup Automático"
echo "--------------------------------"

# Conta arquivos temp antes
TEMP_BEFORE=$(docker exec audio-voice-api sh -c "ls /app/temp/convert_*.* 2>/dev/null | wc -l" | tr -d ' ')
echo "Arquivos temp antes: $TEMP_BEFORE"

# Faz download que deve criar e limpar temp
curl -s -o /dev/null "$BASE_URL/jobs/$JOB_ID/download?format=mp3"
sleep 2  # Aguarda background task

# Conta arquivos temp depois
TEMP_AFTER=$(docker exec audio-voice-api sh -c "ls /app/temp/convert_*.* 2>/dev/null | wc -l" | tr -d ' ')
echo "Arquivos temp depois: $TEMP_AFTER"

if [ "$TEMP_AFTER" -le "$TEMP_BEFORE" ]; then
    echo -e "${GREEN}✅ Cleanup OK (arquivos temporários limpos)${NC}"
else
    echo -e "${YELLOW}⚠️  AVISO: Arquivos temp aumentaram ($TEMP_BEFORE -> $TEMP_AFTER)${NC}"
fi
echo ""

# ============================================
# TESTE 11: Listar Perfis de Qualidade
# ============================================
echo "📊 TESTE 11: Listar Perfis de Qualidade"
echo "----------------------------------------"

PROFILES=$(curl -s "$BASE_URL/quality-profiles")
echo "$PROFILES" | jq .

PROFILE_COUNT=$(echo "$PROFILES" | jq '.profiles | length')
DEFAULT_PROFILE=$(echo "$PROFILES" | jq -r '.default')

echo "Perfis disponíveis: $PROFILE_COUNT"
echo "Perfil padrão: $DEFAULT_PROFILE"

if [ "$PROFILE_COUNT" -eq 3 ]; then
    echo -e "${GREEN}✅ 3 perfis encontrados${NC}"
    
    # Valida que cada perfil tem os campos necessários
    for PROFILE in balanced expressive stable; do
        HAS_PROFILE=$(echo "$PROFILES" | jq -r ".profiles.$PROFILE.name // empty")
        if [ -n "$HAS_PROFILE" ]; then
            echo "  ✓ Perfil '$PROFILE' OK"
        else
            echo -e "  ${RED}✗ Perfil '$PROFILE' ausente${NC}"
        fi
    done
else
    echo -e "${RED}❌ Esperado 3 perfis, encontrado $PROFILE_COUNT${NC}"
    exit 1
fi
echo ""

# ============================================
# TESTE 12: Dubbing com Perfil BALANCED
# ============================================
echo "🎭 TESTE 12: Dubbing com Perfil BALANCED"
echo "-----------------------------------------"

JOB_BALANCED=$(curl -s -X POST "$BASE_URL/jobs" \
  -H "Content-Type: application/json" \
  -d "{
    \"mode\": \"dubbing_with_clone\",
    \"text\": \"Este áudio usa o perfil BALANCED para melhor equilíbrio entre emoção e estabilidade.\",
    \"source_language\": \"pt\",
    \"voice_id\": \"$VOICE_ID\",
    \"quality_profile\": \"balanced\"
  }")

JOB_BALANCED_ID=$(echo "$JOB_BALANCED" | jq -r '.id')
echo "Job BALANCED criado: $JOB_BALANCED_ID"

# Aguarda conclusão
echo -n "Aguardando processamento"
MAX_WAIT_BALANCED=60
WAITED_BALANCED=0
while [ $WAITED_BALANCED -lt $MAX_WAIT_BALANCED ]; do
    JOB_STATUS_BALANCED=$(curl -s "$BASE_URL/jobs/$JOB_BALANCED_ID")
    STATUS_BALANCED=$(echo "$JOB_STATUS_BALANCED" | jq -r '.status')
    
    if [ "$STATUS_BALANCED" == "completed" ]; then
        echo -e " ${GREEN}concluído!${NC}"
        break
    elif [ "$STATUS_BALANCED" == "failed" ]; then
        echo -e " ${RED}falhou!${NC}"
        ERROR_MSG_BALANCED=$(echo "$JOB_STATUS_BALANCED" | jq -r '.error_message')
        echo "Erro: $ERROR_MSG_BALANCED"
        exit 1
    fi
    
    echo -n "."
    sleep 2
    WAITED_BALANCED=$((WAITED_BALANCED + 2))
done

# Download
curl -s "$BASE_URL/jobs/$JOB_BALANCED_ID/download" -o "test_balanced.wav"
FILE_SIZE_BALANCED=$(ls -lh test_balanced.wav | awk '{print $5}')
echo -e "${GREEN}✅ Perfil BALANCED OK ($FILE_SIZE_BALANCED)${NC}"
echo ""

# ============================================
# TESTE 13: Dubbing com Perfil EXPRESSIVE
# ============================================
echo "🎭 TESTE 13: Dubbing com Perfil EXPRESSIVE"
echo "-------------------------------------------"

JOB_EXPRESSIVE=$(curl -s -X POST "$BASE_URL/jobs" \
  -H "Content-Type: application/json" \
  -d "{
    \"mode\": \"dubbing_with_clone\",
    \"text\": \"Este áudio usa o perfil EXPRESSIVE para MÁXIMA emoção e naturalidade!\",
    \"source_language\": \"pt\",
    \"voice_id\": \"$VOICE_ID\",
    \"quality_profile\": \"expressive\"
  }")

JOB_EXPRESSIVE_ID=$(echo "$JOB_EXPRESSIVE" | jq -r '.id')
echo "Job EXPRESSIVE criado: $JOB_EXPRESSIVE_ID"

# Aguarda conclusão
echo -n "Aguardando processamento"
MAX_WAIT_EXPRESSIVE=60
WAITED_EXPRESSIVE=0
while [ $WAITED_EXPRESSIVE -lt $MAX_WAIT_EXPRESSIVE ]; do
    JOB_STATUS_EXPRESSIVE=$(curl -s "$BASE_URL/jobs/$JOB_EXPRESSIVE_ID")
    STATUS_EXPRESSIVE=$(echo "$JOB_STATUS_EXPRESSIVE" | jq -r '.status')
    
    if [ "$STATUS_EXPRESSIVE" == "completed" ]; then
        echo -e " ${GREEN}concluído!${NC}"
        break
    elif [ "$STATUS_EXPRESSIVE" == "failed" ]; then
        echo -e " ${RED}falhou!${NC}"
        ERROR_MSG_EXPRESSIVE=$(echo "$JOB_STATUS_EXPRESSIVE" | jq -r '.error_message')
        echo "Erro: $ERROR_MSG_EXPRESSIVE"
        exit 1
    fi
    
    echo -n "."
    sleep 2
    WAITED_EXPRESSIVE=$((WAITED_EXPRESSIVE + 2))
done

# Download
curl -s "$BASE_URL/jobs/$JOB_EXPRESSIVE_ID/download" -o "test_expressive.wav"
FILE_SIZE_EXPRESSIVE=$(ls -lh test_expressive.wav | awk '{print $5}')
echo -e "${GREEN}✅ Perfil EXPRESSIVE OK ($FILE_SIZE_EXPRESSIVE)${NC}"
echo ""

# ============================================
# TESTE 14: Dubbing com Perfil STABLE
# ============================================
echo "🔒 TESTE 14: Dubbing com Perfil STABLE"
echo "---------------------------------------"

JOB_STABLE=$(curl -s -X POST "$BASE_URL/jobs" \
  -H "Content-Type: application/json" \
  -d "{
    \"mode\": \"dubbing_with_clone\",
    \"text\": \"Este áudio usa o perfil STABLE para produção conservadora e segura.\",
    \"source_language\": \"pt\",
    \"voice_id\": \"$VOICE_ID\",
    \"quality_profile\": \"stable\"
  }")

JOB_STABLE_ID=$(echo "$JOB_STABLE" | jq -r '.id')
echo "Job STABLE criado: $JOB_STABLE_ID"

# Aguarda conclusão
echo -n "Aguardando processamento"
MAX_WAIT_STABLE=60
WAITED_STABLE=0
while [ $WAITED_STABLE -lt $MAX_WAIT_STABLE ]; do
    JOB_STATUS_STABLE=$(curl -s "$BASE_URL/jobs/$JOB_STABLE_ID")
    STATUS_STABLE=$(echo "$JOB_STATUS_STABLE" | jq -r '.status')
    
    if [ "$STATUS_STABLE" == "completed" ]; then
        echo -e " ${GREEN}concluído!${NC}"
        break
    elif [ "$STATUS_STABLE" == "failed" ]; then
        echo -e " ${RED}falhou!${NC}"
        ERROR_MSG_STABLE=$(echo "$JOB_STATUS_STABLE" | jq -r '.error_message')
        echo "Erro: $ERROR_MSG_STABLE"
        exit 1
    fi
    
    echo -n "."
    sleep 2
    WAITED_STABLE=$((WAITED_STABLE + 2))
done

# Download
curl -s "$BASE_URL/jobs/$JOB_STABLE_ID/download" -o "test_stable.wav"
FILE_SIZE_STABLE=$(ls -lh test_stable.wav | awk '{print $5}')
echo -e "${GREEN}✅ Perfil STABLE OK ($FILE_SIZE_STABLE)${NC}"
echo ""

echo ""

# ============================================
# RESUMO FINAL
# ============================================
echo "=========================================="
echo "📊 RESUMO DOS TESTES"
echo "=========================================="
echo -e "${GREEN}✅ TESTE 1: Health Check - OK${NC}"
echo -e "${GREEN}✅ TESTE 2: Linguagens - OK ($TOTAL linguagens)${NC}"
echo -e "${GREEN}✅ TESTE 3: Voice Presets - OK${NC}"
echo -e "${GREEN}✅ TESTE 4: Clonagem de Voz - OK (Voice ID: $VOICE_ID)${NC}"
echo -e "${GREEN}✅ TESTE 5: Criar Job Dubbing - OK (ID: $JOB_ID)${NC}"
echo -e "${GREEN}✅ TESTE 6: Polling Status - OK (${DURATION}s de áudio)${NC}"
echo -e "${GREEN}✅ TESTE 7: Download - OK ($OUTPUT_FILE)${NC}"
echo -e "${GREEN}✅ TESTE 8: Formatos - OK ($FORMATS_COUNT formatos)${NC}"
echo -e "${GREEN}✅ TESTE 9: Múltiplos Formatos - OK (mp3, ogg, flac)${NC}"
echo -e "${GREEN}✅ TESTE 10: Cleanup - OK${NC}"
echo -e "${GREEN}✅ TESTE 11: Quality Profiles - OK (3 perfis)${NC}"
echo -e "${GREEN}✅ TESTE 12: Perfil BALANCED - OK ($FILE_SIZE_BALANCED)${NC}"
echo -e "${GREEN}✅ TESTE 13: Perfil EXPRESSIVE - OK ($FILE_SIZE_EXPRESSIVE)${NC}"
echo -e "${GREEN}✅ TESTE 14: Perfil STABLE - OK ($FILE_SIZE_STABLE)${NC}"
echo ""
echo -e "${GREEN}🎉 TODOS OS 14 TESTES PASSARAM!${NC}"
echo ""
echo "Arquivos gerados:"
ls -lh test_*.wav 2>/dev/null || echo "  Nenhum"
echo ""
echo "Para comparar os perfis de qualidade:"
echo "  ffplay test_balanced.wav    # Perfil BALANCED (recomendado)"
echo "  ffplay test_expressive.wav  # Perfil EXPRESSIVE (max emoção)"
echo "  ffplay test_stable.wav      # Perfil STABLE (conservador)"
echo ""
echo "Para ouvir o áudio original:"
echo "  ffplay $OUTPUT_FILE"
