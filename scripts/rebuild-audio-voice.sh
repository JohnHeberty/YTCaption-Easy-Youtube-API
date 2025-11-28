#!/bin/bash
###############################################################################
# Script de Rebuild Limpo - Audio Voice Service
# 
# Executa rebuild completo sem cache, garantindo estado limpo dos containers.
# Inclui validação de health checks e logs iniciais.
#
# Uso: bash scripts/rebuild-audio-voice.sh
###############################################################################

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_DIR="$PROJECT_ROOT/services/audio-voice"

echo "🔨 =========================================="
echo "🔨 Audio Voice Service - Rebuild Limpo"
echo "🔨 =========================================="
echo ""

# Pré-validação: Verificar .env
echo "🔍 [1/7] Validando pré-condições..."

if [ ! -f "$SERVICE_DIR/.env" ]; then
    echo "❌ ERRO: .env não encontrado em $SERVICE_DIR"
    echo "ℹ️  Copie .env.example para .env e configure antes de continuar"
    exit 1
fi

if ! grep -q "^LOW_VRAM=" "$SERVICE_DIR/.env"; then
    echo "❌ ERRO: LOW_VRAM não definido no .env!"
    echo "ℹ️  Adicione LOW_VRAM=true ao .env"
    exit 1
fi

LOW_VRAM_VALUE=$(grep "^LOW_VRAM=" "$SERVICE_DIR/.env" | cut -d'=' -f2)
echo "✅ Pré-condições OK (LOW_VRAM=$LOW_VRAM_VALUE)"
echo ""

# Cleanup completo primeiro
echo "🧹 [2/7] Executando cleanup completo..."
bash "$SCRIPT_DIR/docker-cleanup-audio-voice.sh" || {
    echo "❌ Cleanup falhou!"
    exit 1
}
echo ""

# Rebuild sem cache
cd "$SERVICE_DIR"
echo "📦 [3/7] Building imagens Docker (sem cache)..."
echo "⏳ Isso pode levar 5-10 minutos..."
echo ""

if docker compose build --no-cache; then
    echo "✅ Build concluído com sucesso"
else
    echo "❌ Build falhou!"
    exit 1
fi
echo ""

# Subir serviços
echo "🚀 [4/7] Iniciando serviços..."
docker compose up -d

if [ $? -eq 0 ]; then
    echo "✅ Serviços iniciados"
else
    echo "❌ Falha ao iniciar serviços!"
    exit 1
fi
echo ""

# Aguardar health checks
echo "⏳ [5/7] Aguardando health checks (90 segundos)..."
echo "ℹ️  API precisa carregar modelos XTTS/F5-TTS..."

for i in {1..90}; do
    echo -n "."
    sleep 1
    
    # Verificar se API está healthy
    if docker ps --filter "name=audio-voice-api" --filter "health=healthy" --format '{{.Names}}' | grep -q "audio-voice-api"; then
        echo ""
        echo "✅ API healthy após ${i}s"
        break
    fi
    
    if [ $i -eq 90 ]; then
        echo ""
        echo "⚠️  Timeout aguardando health check da API"
    fi
done
echo ""

# Validar containers
echo "🔍 [6/7] Validando containers..."

API_STATUS=$(docker ps --filter "name=audio-voice-api" --format '{{.Status}}' | head -1)
CELERY_STATUS=$(docker ps --filter "name=audio-voice-celery" --format '{{.Status}}' | head -1)

echo "📊 Status dos containers:"
echo "   API:    $API_STATUS"
echo "   Celery: $CELERY_STATUS"
echo ""

if docker ps --filter "name=audio-voice-api" --filter "health=healthy" --format '{{.Names}}' | grep -q "audio-voice-api"; then
    echo "✅ API healthy"
else
    echo "⚠️  API não está healthy ainda"
    echo "📋 Últimos logs da API:"
    docker logs audio-voice-api --tail 30
    echo ""
    echo "⚠️  Aguarde mais alguns segundos e verifique: docker logs audio-voice-api -f"
fi

if docker ps --filter "name=audio-voice-celery" --format '{{.Names}}' | grep -q "audio-voice-celery"; then
    echo "✅ Celery rodando"
    
    # Verificar se Celery tem healthcheck
    if docker ps --filter "name=audio-voice-celery" --filter "health=healthy" --format '{{.Names}}' | grep -q "audio-voice-celery"; then
        echo "✅ Celery healthy"
    else
        CELERY_HEALTH=$(docker inspect audio-voice-celery --format '{{.State.Health.Status}}' 2>/dev/null || echo "no-healthcheck")
        if [ "$CELERY_HEALTH" == "no-healthcheck" ]; then
            echo "ℹ️  Celery sem healthcheck configurado (OK)"
        else
            echo "⚠️  Celery health: $CELERY_HEALTH"
        fi
    fi
else
    echo "❌ Celery não está rodando!"
    exit 1
fi
echo ""

# Verificar logs iniciais (LOW_VRAM mode)
echo "📋 [7/7] Verificando logs de inicialização..."
echo ""
echo "🔍 Procurando por LOW_VRAM mode nos logs do Celery..."

sleep 5  # Aguardar logs serem gerados

if docker logs audio-voice-celery 2>&1 | grep -q "LOW VRAM MODE"; then
    LOW_VRAM_LOG=$(docker logs audio-voice-celery 2>&1 | grep "LOW VRAM MODE" | tail -1)
    echo "✅ $LOW_VRAM_LOG"
else
    echo "⚠️  Não encontrado log de LOW_VRAM mode (ainda inicializando?)"
fi
echo ""

echo "🔍 Procurando por inicialização de engines..."
if docker logs audio-voice-celery 2>&1 | grep -q "F5TtsEngine initializing"; then
    F5TTS_LOG=$(docker logs audio-voice-celery 2>&1 | grep "F5TtsEngine initializing" | tail -1)
    echo "✅ $F5TTS_LOG"
fi

if docker logs audio-voice-celery 2>&1 | grep -q "XttsEngine initializing"; then
    XTTS_LOG=$(docker logs audio-voice-celery 2>&1 | grep "XttsEngine initializing" | tail -1)
    echo "✅ $XTTS_LOG"
fi
echo ""

echo "🎉 =========================================="
echo "🎉 Rebuild concluído com sucesso!"
echo "🎉 =========================================="
echo ""
echo "📊 Containers rodando:"
docker ps --filter "name=audio-voice" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "📋 Próximos passos:"
echo "   - Ver logs API:    docker logs audio-voice-api -f"
echo "   - Ver logs Celery: docker logs audio-voice-celery -f"
echo "   - Monitorar VRAM:  watch -n 1 nvidia-smi"
echo "   - Testar API:      curl http://localhost:8005/"
