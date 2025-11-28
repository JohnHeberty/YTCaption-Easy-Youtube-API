#!/bin/bash
###############################################################################
# Teste: Validar Container Único por Serviço
# 
# Garante que apenas 1 container de cada tipo (API + Celery) está rodando.
#
# Uso: bash scripts/test-single-container.sh
###############################################################################

set -e

echo "🧪 Testando: Apenas 1 container de cada tipo..."
echo ""

API_COUNT=$(docker ps --filter "name=audio-voice-api" --format '{{.Names}}' | wc -l)
CELERY_COUNT=$(docker ps --filter "name=audio-voice-celery" --format '{{.Names}}' | wc -l)

echo "📊 Resultado:"
echo "   API containers:    $API_COUNT"
echo "   Celery containers: $CELERY_COUNT"
echo ""

FAILED=0

if [ "$API_COUNT" -ne 1 ]; then
    echo "❌ ERRO: $API_COUNT containers API rodando (esperado: 1)"
    echo "   Containers encontrados:"
    docker ps --filter "name=audio-voice-api" --format '   - {{.Names}} ({{.Status}})'
    FAILED=1
else
    echo "✅ Exatamente 1 container API rodando"
fi

if [ "$CELERY_COUNT" -ne 1 ]; then
    echo "❌ ERRO: $CELERY_COUNT containers Celery rodando (esperado: 1)"
    echo "   Containers encontrados:"
    docker ps --filter "name=audio-voice-celery" --format '   - {{.Names}} ({{.Status}})'
    FAILED=1
else
    echo "✅ Exatamente 1 container Celery rodando"
fi

echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 TESTE PASSOU: Containers únicos validados!"
    exit 0
else
    echo "💥 TESTE FALHOU: Múltiplos containers detectados!"
    echo ""
    echo "🔧 Solução: Execute cleanup e rebuild"
    echo "   bash scripts/docker-cleanup-audio-voice.sh"
    echo "   bash scripts/rebuild-audio-voice.sh"
    exit 1
fi
