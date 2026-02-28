#!/bin/bash
# Script de validação pós-deploy do audio-transcriber
# Versão: 2.1.0 - SOLID + Alta Resiliência

set -e

echo "🔍 ===== VALIDAÇÃO DO AUDIO-TRANSCRIBER ====="
echo ""

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configurações
API_URL="${API_URL:-http://localhost:8003}"
TIMEOUT=10

# Funções auxiliares
check_passed() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
}

check_failed() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    exit 1
}

check_warning() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

# 1. Verificar containers
echo "📦 1. Verificando containers..."
CONTAINERS=$(docker ps --filter name=audio-transcriber --format "{{.Names}}" | wc -l)
if [ "$CONTAINERS" -eq 3 ]; then
    check_passed "3 containers rodando (API, Celery Worker, Celery Beat)"
else
    check_failed "Esperado 3 containers, encontrado $CONTAINERS"
fi

# 2. Verificar health da API
echo ""
echo "🏥 2. Verificando health da API..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/health" --max-time $TIMEOUT || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    check_passed "API respondendo (HTTP 200)"
else
    check_failed "API não respondendo corretamente (HTTP $HTTP_CODE)"
fi

# 3. Verificar health detalhado
echo ""
echo "🔬 3. Verificando health detalhado..."
HEALTH_RESPONSE=$(curl -s "${API_URL}/health/detailed" --max-time $TIMEOUT || echo "{}")
OVERALL_HEALTHY=$(echo "$HEALTH_RESPONSE" | grep -o '"overall_healthy":[^,}]*' | cut -d':' -f2 | tr -d ' ')

if [ "$OVERALL_HEALTHY" = "true" ]; then
    check_passed "Sistema geral saudável"
    
    # Verifica componentes individuais
    REDIS_HEALTHY=$(echo "$HEALTH_RESPONSE" | grep -o '"redis":{"component":"redis","healthy":[^,}]*' | grep -o 'healthy":[^,]*' | cut -d':' -f2 | tr -d ' ')
    if [ "$REDIS_HEALTHY" = "true" ]; then
        check_passed "  Redis: OK"
    else
        check_warning "  Redis: Unhealthy"
    fi
    
    CELERY_HEALTHY=$(echo "$HEALTH_RESPONSE" | grep -o '"celery":{"component":"celery_worker","healthy":[^,}]*' | grep -o 'healthy":[^,]*' | cut -d':' -f2 | tr -d ' ')
    if [ "$CELERY_HEALTHY" = "true" ]; then
        check_passed "  Celery: OK"
    else
        check_warning "  Celery: Unhealthy"
    fi
else
    check_failed "Sistema geral unhealthy"
fi

# 4. Verificar healthcheck dos containers
echo ""
echo "🩺 4. Verificando healthcheck dos containers..."

API_HEALTH=$(docker inspect audio-transcriber-api --format='{{.State.Health.Status}}' 2>/dev/null || echo "no-healthcheck")
if [ "$API_HEALTH" = "healthy" ]; then
    check_passed "API container: healthy"
elif [ "$API_HEALTH" = "no-healthcheck" ]; then
    check_warning "API container: sem healthcheck configurado"
else
    check_failed "API container: $API_HEALTH"
fi

CELERY_HEALTH=$(docker inspect audio-transcriber-celery --format='{{.State.Health.Status}}' 2>/dev/null || echo "no-healthcheck")
if [ "$CELERY_HEALTH" = "healthy" ]; then
    check_passed "Celery Worker container: healthy"
elif [ "$CELERY_HEALTH" = "starting" ]; then
    check_warning "Celery Worker container: iniciando... (aguarde alguns minutos)"
elif [ "$CELERY_HEALTH" = "no-healthcheck" ]; then
    check_failed "Celery Worker container: SEM HEALTHCHECK! Atualizar docker-compose.yml"
else
    check_warning "Celery Worker container: $CELERY_HEALTH (pode estar iniciando)"
fi

BEAT_RUNNING=$(docker ps --filter name=audio-transcriber-beat --format "{{.Names}}" | wc -l)
if [ "$BEAT_RUNNING" -eq 1 ]; then
    check_passed "Celery Beat container: rodando"
else
    check_failed "Celery Beat container: não encontrado"
fi

# 5. Verificar logs recentes
echo ""
echo "📋 5. Verificando logs recentes..."

echo "   API (últimas 5 linhas):"
docker logs audio-transcriber-api --tail 5 2>&1 | sed 's/^/     /'

echo ""
echo "   Celery Worker (últimas 5 linhas):"
docker logs audio-transcriber-celery --tail 5 2>&1 | sed 's/^/     /'

echo ""
echo "   Celery Beat (últimas 5 linhas):"
docker logs audio-transcriber-beat --tail 5 2>&1 | sed 's/^/     /'

# 6. Verificar tarefas Celery
echo ""
echo "🔧 6. Verificando tarefas Celery registradas..."
CELERY_INSPECT=$(docker exec audio-transcriber-celery celery -A app.celery_config inspect registered 2>&1 | grep -E "(transcribe_audio|cleanup_orphan_jobs|cleanup_expired_jobs)" || echo "")

if echo "$CELERY_INSPECT" | grep -q "transcribe_audio"; then
    check_passed "Task 'transcribe_audio' registrada"
else
    check_failed "Task 'transcribe_audio' NÃO registrada"
fi

if echo "$CELERY_INSPECT" | grep -q "cleanup_orphan_jobs"; then
    check_passed "Task 'cleanup_orphan_jobs' registrada"
else
    check_warning "Task 'cleanup_orphan_jobs' NÃO registrada (verificar celery_tasks.py)"
fi

if echo "$CELERY_INSPECT" | grep -q "cleanup_expired_jobs"; then
    check_passed "Task 'cleanup_expired_jobs' registrada"
else
    check_warning "Task 'cleanup_expired_jobs' NÃO registrada"
fi

# 7. Teste de cleanup manual
echo ""
echo "🧹 7. Testando endpoint de cleanup manual..."
CLEANUP_RESPONSE=$(curl -s -X POST "${API_URL}/admin/cleanup-orphans" --max-time $TIMEOUT || echo "{}")
CLEANUP_SUCCESS=$(echo "$CLEANUP_RESPONSE" | grep -o '"success":[^,}]*' | cut -d':' -f2 | tr -d ' ')

if [ "$CLEANUP_SUCCESS" = "true" ]; then
    check_passed "Cleanup manual funcionando"
    ORPHANS_FOUND=$(echo "$CLEANUP_RESPONSE" | grep -o '"orphans_found":[0-9]*' | cut -d':' -f2)
    echo "     Órfãos encontrados: $ORPHANS_FOUND"
else
    check_warning "Cleanup manual não retornou sucesso (pode ser esperado se sem órfãos)"
fi

# 8. Resumo
echo ""
echo "======================================"
echo "🎉 VALIDAÇÃO CONCLUÍDA COM SUCESSO!"
echo "======================================"
echo ""
echo "📊 Próximos passos:"
echo "   1. Monitorar logs por 10-15 minutos"
echo "   2. Verificar se órfãos são limpos automaticamente"
echo "   3. Testar criação de novos jobs"
echo "   4. Validar processamento end-to-end"
echo ""
echo "🔗 Endpoints úteis:"
echo "   Health básico:    ${API_URL}/health"
echo "   Health detalhado: ${API_URL}/health/detailed"
echo "   Cleanup manual:   ${API_URL}/admin/cleanup-orphans (POST)"
echo ""
