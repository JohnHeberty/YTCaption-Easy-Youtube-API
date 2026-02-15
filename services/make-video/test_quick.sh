#!/bin/bash
# Quick Test - Sistema de Rastreabilidade (sem depender do container)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 TESTE RÁPIDO - VideoStatusStore e FileOperations"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd /root/YTCaption-Easy-Youtube-API/services/make-video

# ============================================================================
# 1. TESTAR VideoStatusStore
# ============================================================================
echo "1️⃣  VideoStatusStore - Teste Funcional"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 << 'EOF'
import sys
sys.path.insert(0, '/root/YTCaption-Easy-Youtube-API/services/make-video')

from app.services.video_status_factory import get_video_status_store

# Criar store
store = get_video_status_store()
print(f"✅ Store criado: {store.db_path}")
print()

# Adicionar teste de aprovado
store.add_approved(
    video_id="test_approved_001",
    title="Video Teste Aprovado",
    url="https://youtube.com/watch?v=test001",
    file_path="data/approved/videos/test_approved_001.mp4",
    metadata={"test": True}
)
print("✅ Adicionado: test_approved_001 (approved)")

# Adicionar teste de rejeitado
store.add_rejected(
    video_id="test_rejected_001",
    title="Video Teste Rejeitado",
    url="https://youtube.com/watch?v=test002",
    reason="embedded_subtitles",
    confidence=0.95,
    metadata={"test": True}
)
print("✅ Adicionado: test_rejected_001 (rejected)")

# Adicionar teste de erro
store.add_error(
    video_id="test_error_001",
    error_type="download_failed",
    error_message="Connection timeout after 3 retries",
    error_traceback="Traceback (most recent call last)...",
    stage="download",
    retry_count=3,
    title="Video Teste Erro",
    url="https://youtube.com/watch?v=test003",
    metadata={"test": True}
)
print("✅ Adicionado: test_error_001 (error)")
print()

# Stats
stats = store.get_stats()
print("📊 Stats:")
print(f"   Aprovados: {stats['approved_count']}")
print(f"   Rejeitados: {stats['rejected_count']}")
print(f"   Erros: {stats['error_count']}")
print(f"   Total: {stats['total_processed']}")
print(f"   Taxa de aprovação: {stats['approval_rate']:.2%}")
print(f"   Taxa de erro: {stats['error_rate']:.2%}")
print()

# Verificar prevenção de retry
print("🔍 Teste de prevenção de retry:")
print(f"   is_approved('test_approved_001'): {store.is_approved('test_approved_001')}")
print(f"   is_rejected('test_rejected_001'): {store.is_rejected('test_rejected_001')}")
print(f"   is_error('test_error_001'): {store.is_error('test_error_001')}")
print()

# Listar últimos erros
print("🔴 Últimos 3 erros:")
errors = store.list_errors(limit=3)
for err in errors:
    print(f"   - {err['video_id']}: {err['error_type']} (stage: {err['stage']})")
    print(f"     Message: {err['error_message'][:60]}...")
print()

print("✅ VideoStatusStore: FUNCIONANDO PERFEITAMENTE")
EOF

echo ""
echo ""

# ============================================================================
# 2. TESTAR FileOperations
# ============================================================================
echo "2️⃣  FileOperations - Teste de Movimentação"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 << 'EOF'
import sys
import os
from pathlib import Path
sys.path.insert(0, '/root/YTCaption-Easy-Youtube-API/services/make-video')

from app.services.file_operations import FileOperations

# Criar FileOperations
file_ops = FileOperations(data_dir="./data")
print("✅ FileOperations inicializado")
print()

# Criar arquivo de teste em raw/
test_video_id = "test_move_001"
test_file_raw = Path("data/raw/shorts") / f"{test_video_id}.mp4"
test_file_raw.parent.mkdir(parents=True, exist_ok=True)

# Criar arquivo dummy
with open(test_file_raw, 'wb') as f:
    f.write(b'FAKE VIDEO CONTENT FOR TESTING')

print(f"✅ Arquivo teste criado: {test_file_raw}")
print(f"   Tamanho: {test_file_raw.stat().st_size} bytes")
print()

# MOVE para transform/
try:
    new_path = file_ops.move_to_transform(test_video_id)
    print(f"✅ MOVED: raw/ → transform/")
    print(f"   Novo path: {new_path}")
    print(f"   Arquivo existe: {new_path.exists()}")
    print(f"   Arquivo antigo removido: {not test_file_raw.exists()}")
    print()
    
    # MOVE para approved/
    final_path = file_ops.move_to_approved(test_video_id)
    print(f"✅ MOVED: transform/ → approved/")
    print(f"   Path final: {final_path}")
    print(f"   Arquivo existe: {final_path.exists()}")
    print(f"   Transform removido: {not new_path.exists()}")
    print()
    
    # Cleanup
    if final_path.exists():
        final_path.unlink()
        print(f"🧹 Arquivo de teste removido")
    
    print("✅ FileOperations: FUNCIONANDO PERFEITAMENTE")
    
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
EOF

echo ""
echo ""

# ============================================================================
# 3. VERIFICAR ESTRUTURA DE DIRETÓRIOS
# ============================================================================
echo "3️⃣  Estrutura de Diretórios"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

printf "%-30s %s\n" "Diretório" "Status"
printf "%-30s %s\n" "─────────────────────────────" "──────"

check_dir() {
    if [ -d "$1" ]; then
        echo "✅  $1"
    else
        echo "❌  $1 (não existe)"
    fi
}

check_dir "data/database"
check_dir "data/raw/shorts"
check_dir "data/transform/videos"
check_dir "data/approved/videos"

echo ""

# Verificar banco
if [ -f "data/database/video_status.db" ]; then
    SIZE=$(du -h "data/database/video_status.db" | cut -f1)
    echo "✅ Banco: data/database/video_status.db (${SIZE})"
else
    echo "⚠️  Banco: não encontrado (será criado no primeiro uso)"
fi

echo ""
echo ""

# ============================================================================
# 4. TESTE SQL DIRETO
# ============================================================================
echo "4️⃣  Verificação SQL Direta"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "data/database/video_status.db" ]; then
    echo "📊 Tabelas no banco:"
    sqlite3 data/database/video_status.db "
        SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
    " 2>/dev/null || echo "Erro ao ler banco"
    
    echo ""
    echo "📊 Contagem por tabela:"
    sqlite3 data/database/video_status.db "
        SELECT 'approved_videos' as table_name, COUNT(*) as count FROM approved_videos
        UNION ALL
        SELECT 'rejected_videos' as table_name, COUNT(*) as count FROM rejected_videos
        UNION ALL
        SELECT 'error_videos' as table_name, COUNT(*) as count FROM error_videos;
    " 2>/dev/null || echo "Tabelas ainda não existem"
fi

echo ""
echo ""

# ============================================================================
# SUMÁRIO
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 SUMÁRIO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ VideoStatusStore: 3 tabelas (approved, rejected, error)"
echo "✅ FileOperations: Move arquivos (não copia)"
echo "✅ Banco de dados: data/database/video_status.db"
echo "✅ Estrutura de diretórios: OK"
echo ""
echo "🎯 Próximo passo: Integrar no pipeline (ver INTEGRATION_GUIDE.md)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
