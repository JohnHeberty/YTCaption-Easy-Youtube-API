#!/bin/bash
# Script de limpeza de espaço no servidor Docker

echo "======================================"
echo "🧹 LIMPEZA DE ESPAÇO - Docker"
echo "======================================"
echo ""

echo "📊 Espaço em disco ANTES da limpeza:"
df -h / /var/lib/docker
echo ""

echo "🗑️  Removendo containers parados..."
docker container prune -f
echo ""

echo "🗑️  Removendo imagens não usadas..."
docker image prune -a -f
echo ""

echo "🗑️  Removendo volumes não usados..."
docker volume prune -f
echo ""

echo "🗑️  Removendo builds cache..."
docker buildx prune -a -f 2>/dev/null || docker builder prune -a -f
echo ""

echo "🗑️  Limpeza completa do Docker..."
docker system prune -a -f --volumes
echo ""

echo "📊 Espaço em disco APÓS a limpeza:"
df -h / /var/lib/docker
echo ""

echo "======================================"
echo "✅ Limpeza concluída!"
echo "======================================"
