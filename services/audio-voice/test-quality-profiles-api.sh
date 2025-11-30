#!/bin/bash
# Script de validação rápida dos endpoints quality-profiles

set -e

API_BASE="http://localhost:8005"

echo "🧪 Validação de Endpoints - Quality Profiles"
echo "============================================="
echo ""

# Teste 1: Listar todos os perfis (GET /quality-profiles)
echo "1️⃣ GET /quality-profiles"
RESPONSE=$(curl -s "${API_BASE}/quality-profiles")
XTTS_COUNT=$(echo "$RESPONSE" | jq '.xtts_profiles | length' 2>/dev/null || echo "0")
F5TTS_COUNT=$(echo "$RESPONSE" | jq '.f5tts_profiles | length' 2>/dev/null || echo "0")
echo "   ✅ XTTS profiles: ${XTTS_COUNT}"
echo "   ✅ F5-TTS profiles: ${F5TTS_COUNT}"
echo ""

# Teste 2: Listar perfis de engine específico (GET /quality-profiles/{engine})
echo "2️⃣ GET /quality-profiles/xtts"
XTTS_RESPONSE=$(curl -s "${API_BASE}/quality-profiles/xtts")
XTTS_SPECIFIC=$(echo "$XTTS_RESPONSE" | jq '. | length' 2>/dev/null || echo "0")
echo "   ✅ XTTS profiles via engine endpoint: ${XTTS_SPECIFIC}"
echo ""

# Teste 3: Verificar se endpoints legacy foram removidos
echo "3️⃣ Verificar remoção de endpoints legacy"

echo "   🔍 GET /quality-profiles-legacy"
LEGACY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/quality-profiles-legacy")
if [ "$LEGACY_STATUS" == "404" ]; then
    echo "   ✅ Endpoint legacy removido (404)"
else
    echo "   ❌ ERRO: Endpoint legacy ainda existe (${LEGACY_STATUS})"
fi

echo "   🔍 POST /quality-profiles-legacy-form"
LEGACY_FORM_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_BASE}/quality-profiles-legacy-form")
if [ "$LEGACY_FORM_STATUS" == "404" ]; then
    echo "   ✅ Endpoint legacy-form removido (404)"
else
    echo "   ❌ ERRO: Endpoint legacy-form ainda existe (${LEGACY_FORM_STATUS})"
fi

echo "   🔍 DELETE /quality-profiles/{name}"
LEGACY_DELETE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "${API_BASE}/quality-profiles/test")
if [ "$LEGACY_DELETE_STATUS" == "404" ]; then
    echo "   ✅ Endpoint legacy DELETE removido (404)"
else
    echo "   ❌ ERRO: Endpoint legacy DELETE ainda existe (${LEGACY_DELETE_STATUS})"
fi
echo ""

# Teste 4: Criar perfil de teste (POST /quality-profiles)
echo "4️⃣ POST /quality-profiles (criar perfil XTTS)"
CREATE_PAYLOAD='{
  "name": "Teste Auto",
  "description": "Perfil criado automaticamente",
  "engine": "xtts",
  "is_default": false,
  "parameters": {
    "temperature": 0.75,
    "repetition_penalty": 1.5,
    "top_p": 0.9,
    "top_k": 60,
    "length_penalty": 1.2,
    "speed": 1.0,
    "enable_text_splitting": false
  }
}'

CREATE_RESPONSE=$(curl -s -X POST "${API_BASE}/quality-profiles" \
  -H "Content-Type: application/json" \
  -d "$CREATE_PAYLOAD")

CREATED_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id' 2>/dev/null || echo "")
if [ -n "$CREATED_ID" ] && [ "$CREATED_ID" != "null" ]; then
    echo "   ✅ Perfil criado: ${CREATED_ID}"
    
    # Teste 5: Buscar perfil criado
    echo ""
    echo "5️⃣ GET /quality-profiles/xtts/${CREATED_ID}"
    GET_PROFILE=$(curl -s "${API_BASE}/quality-profiles/xtts/${CREATED_ID}")
    PROFILE_NAME=$(echo "$GET_PROFILE" | jq -r '.name' 2>/dev/null || echo "")
    if [ "$PROFILE_NAME" == "Teste Auto" ]; then
        echo "   ✅ Perfil encontrado: ${PROFILE_NAME}"
    else
        echo "   ❌ ERRO: Perfil não encontrado ou nome incorreto"
    fi
    
    # Teste 6: Duplicar perfil
    echo ""
    echo "6️⃣ POST /quality-profiles/xtts/${CREATED_ID}/duplicate"
    DUPLICATE_RESPONSE=$(curl -s -X POST "${API_BASE}/quality-profiles/xtts/${CREATED_ID}/duplicate?new_name=Cópia%20Auto")
    DUPLICATE_ID=$(echo "$DUPLICATE_RESPONSE" | jq -r '.id' 2>/dev/null || echo "")
    if [ -n "$DUPLICATE_ID" ] && [ "$DUPLICATE_ID" != "null" ]; then
        echo "   ✅ Perfil duplicado: ${DUPLICATE_ID}"
    else
        echo "   ❌ ERRO: Falha ao duplicar perfil"
    fi
    
    # Teste 7: Deletar perfis de teste
    echo ""
    echo "7️⃣ DELETE /quality-profiles/xtts/${CREATED_ID}"
    DELETE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "${API_BASE}/quality-profiles/xtts/${CREATED_ID}")
    if [ "$DELETE_STATUS" == "204" ]; then
        echo "   ✅ Perfil deletado (204)"
    else
        echo "   ❌ ERRO: Falha ao deletar (${DELETE_STATUS})"
    fi
    
    if [ -n "$DUPLICATE_ID" ] && [ "$DUPLICATE_ID" != "null" ]; then
        echo ""
        echo "8️⃣ DELETE /quality-profiles/xtts/${DUPLICATE_ID}"
        DELETE_DUP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "${API_BASE}/quality-profiles/xtts/${DUPLICATE_ID}")
        if [ "$DELETE_DUP_STATUS" == "204" ]; then
            echo "   ✅ Cópia deletada (204)"
        else
            echo "   ❌ ERRO: Falha ao deletar cópia (${DELETE_DUP_STATUS})"
        fi
    fi
else
    echo "   ❌ ERRO: Falha ao criar perfil"
    echo "   Response: $CREATE_RESPONSE"
fi

echo ""
echo "============================================="
echo "✅ Validação completa!"
