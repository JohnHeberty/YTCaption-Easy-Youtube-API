#!/bin/bash
# Script de deploy do serviço make-video com workaround Celery
# Garante que o código mais atualizado seja copiado para o Docker

set -e

echo "🔧 Deploy make-video com workaround Celery/Kombu"
echo "================================================"

CD_DIR="/root/YTCaption-Easy-Youtube-API/services/make-video"
cd $CD_DIR

echo ""
echo "📥 1. Parando containers..."
docker compose down || true

echo ""
echo "🗑️  2. Removendo imagens antigas..."
docker rmi make-video-make-video make-video-make-video-celery make-video-make-video-celery-beat 2>/dev/null || true

echo ""
echo "🏗️  3. Building imagens (sem cache)..."
docker compose build --no-cache

echo ""
echo "🚀 4. Subindo containers..."
docker compose up -d

echo ""
echo "⏳ 5. Aguardando inicialização (30s)..."
sleep 30

echo ""
echo "▶️  6. Iniciando workers Celery..."
docker start ytcaption-make-video-celery 2>/dev/null || true
docker start ytcaption-make-video-celery-beat 2>/dev/null || true

echo ""
echo "⏳ 7. Aguardando workers (10s)..."
sleep 10

echo ""
echo "✅ 8. Verificando status..."
docker compose ps

echo ""
echo "🔍 9. Verificando workaround no código do container..."
if docker exec ytcaption-make-video grep -q "via Kombu workaround" /app/app/main.py 2>/dev/null; then
    echo "   ✅ Workaround ENCONTRADO no container!"
else
    echo "   ⚠️  Workaround NÃO encontrado - verificar build"
fi

echo ""
echo "🏥 10. Health check..."
curl -s http://localhost:8004/health | jq '.status, .service, .checks.redis.healthy' || echo "API ainda iniciando..."

echo ""
echo "================================================"
echo "✅ Deploy concluído!"
echo ""
echo "📋 Comandos úteis:"
echo "   docker compose logs -f make-video              # Logs API"
echo "   docker compose logs -f make-video-celery       # Logs Worker"
echo "   curl http://localhost:8004/health | jq .       # Health check"
echo ""
echo "🧪 Teste endpoint:"
echo '   curl -X POST http://localhost:8004/make-video \'
echo '     -F "audio_file=@audio.mp3" \'
echo '     -F "query=teste" \'
echo '     -F "max_shorts=10"'
echo ""
