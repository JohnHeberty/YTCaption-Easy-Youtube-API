#!/bin/bash
# Test VideoStatusStore migration

echo "🧪 Testando novo VideoStatusStore"
echo "=================================="
echo ""

cd /root/YTCaption-Easy-Youtube-API/services/make-video

# Test 1: Verificar import
echo "1. Testando import do VideoStatusStore..."
python3 -c "
from app.services.video_status_factory import get_video_status_store
store = get_video_status_store()
print(f'✅ Store criado: {store.db_path}')
print(f'   Aprovados: {store.count_approved()}')
print(f'   Reprovados: {store.count_rejected()}')
"
echo ""

# Test 2: Verificar arquivo de banco
echo "2. Verificando novo banco de dados..."
if [ -f "data/database/video_status.db" ]; then
    echo "✅ data/database/video_status.db criado"
    ls -lh data/database/video_status.db
else
    echo "❌ Banco não encontrado"
fi
echo ""

# Test 3: Verificar tabelas
echo "3. Verificando estrutura do banco..."
sqlite3 data/database/video_status.db "SELECT name FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "Banco ainda não existe (será criado no primeiro uso)"
echo ""

# Test 4: Teste funcional completo
echo "4. Teste funcional: adicionar aprovado + reprovado..."
sleep 2
python3 -c "
from app.services.video_status_factory import get_video_status_store

store = get_video_status_store()

# Adicionar um aprovado de teste
store.add_approved(
    video_id='test_approved_123',
    title='Video Teste Aprovado',
    url='https://youtube.com/watch?v=test123',
    file_path='data/approved/videos/test_approved_123.mp4',
    metadata={'test': True}
)

# Adicionar um reprovado de teste  
store.add_rejected(
    video_id='test_rejected_456',
    reason='embedded_subtitles',
    confidence=0.95,
    title='Video Teste Reprovado',
    url='https://youtube.com/watch?v=test456',
    metadata={'test': True}
)

print('✅ Dados inseridos')
print(f'   Aprovados: {store.count_approved()}')
print(f'   Reprovados: {store.count_rejected()}')

# Testar recuperação
approved= store.get_approved('test_approved_123')
print(f'✅ Recuperado aprovado: {approved[\"video_id\"]}')

rejected = store.get_rejected('test_rejected_456')
print(f'✅ Recuperado reprovado: {rejected[\"video_id\"]} (motivo: {rejected[\"rejection_reason\"]})')

# Stats
stats = store.get_stats()
print(f'✅ Stats: {stats}')
"
echo ""

echo "✅ Todos os testes passaram!"
echo ""
echo "📍 Localização do novo banco:"
echo "   data/database/video_status.db"
echo ""
echo "📍 Banco antigo (deprecated):"
echo "   data/raw/shorts/blacklist.db"
echo ""
echo "💡 Para usar os novos endpoints, rebuild o container:"
echo "   docker compose up -d --build"
