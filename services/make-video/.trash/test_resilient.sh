#!/bin/bash
set -e

echo "🧪 Teste de Resiliência do /download"
echo "======================================"
echo ""

cd /root/YTCaption-Easy-Youtube-API/services/make-video

# Limpar ambiente
echo "1. Limpando ambiente..."
python3 -c "import sqlite3; c=sqlite3.connect('data/raw/shorts/blacklist.db'); c.execute('DELETE FROM blacklist'); c.commit(); c.close()"
find data/raw/shorts -maxdepth 1 -type f -name '*.mp4' -delete 2>/dev/null || true
find data/transform/videos -maxdepth 1 -type f -name '*.mp4' -delete 2>/dev/null || true
echo "   ✅ Ambiente limpo"
echo ""

# Criar job
echo "2. Criando job com 10 vídeos..."
RESP=$(curl -s -X POST "http://localhost:8004/download" \
  -F "query=Videos Satisfatorios" \
  -F "max_shorts=10")

echo "$RESP" | jq '.job_id, .message, .estimated_duration_minutes'
JOB_ID=$(echo "$RESP" | jq -r '.job_id')
echo "   📋 Job ID: $JOB_ID"
echo ""

# Monitorar por 30 segundos
echo "3. Monitorando job..."
for i in {1..6}; do
  sleep 5
  STATUS=$(curl -s "http://localhost:8004/jobs/$JOB_ID" | jq -r '{status,progress,health}')
  echo "   [$((i*5))s] $STATUS"
done
echo ""

# Resultado final
echo "4. Resultado final:"
curl -s "http://localhost:8004/jobs/$JOB_ID" | jq '{
  job_id,
  status,
  progress,
  health,
  stats: .stages.download_pipeline.metadata.stats
}'
echo ""
echo "✅ Teste completo!"
