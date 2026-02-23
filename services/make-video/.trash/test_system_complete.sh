#!/bin/bash
# Script de Teste Completo - Sistema de Rastreabilidade
# Testa todos os endpoints e funcionalidades do novo sistema

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 TESTE COMPLETO - Sistema de Rastreabilidade e Cleanup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

BASE_URL="http://localhost:8004"
cd /root/YTCaption-Easy-Youtube-API/services/make-video

# ============================================================================
# 1. HEALTH CHECK
# ============================================================================
echo "1️⃣  HEALTH CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s "$BASE_URL/health" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/health"
echo ""
echo ""

# ============================================================================
# 2. VERIFICAR BANCO DE DADOS ATUAL
# ============================================================================
echo "2️⃣  BANCO DE DADOS - Estado Atual"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verificar se novo banco existe
if [ -f "data/database/video_status.db" ]; then
    echo "✅ Novo banco encontrado: data/database/video_status.db"
    echo ""
    
    echo "📊 Contagem de registros:"
    sqlite3 data/database/video_status.db "
        SELECT 'Approved' as type, COUNT(*) as count FROM approved_videos
        UNION ALL
        SELECT 'Rejected' as type, COUNT(*) as count FROM rejected_videos
        UNION ALL
        SELECT 'Errors' as type, COUNT(*) as count FROM error_videos;
    " 2>/dev/null || echo "Erro ao ler banco (tabelas podem não existir ainda)"
else
    echo "⚠️  Novo banco não encontrado (será criado na primeira execução)"
fi

# Verificar banco antigo
if [ -f "data/raw/shorts/blacklist.db" ]; then
    echo ""
    echo "⚠️  Banco antigo ainda existe: data/raw/shorts/blacklist.db"
    BLACKLIST_COUNT=$(sqlite3 data/raw/shorts/blacklist.db "SELECT COUNT(*) FROM blacklist" 2>/dev/null || echo "0")
    echo "   Registros no blacklist antigo: $BLACKLIST_COUNT"
fi
echo ""
echo ""

# ============================================================================
# 3. VERIFICAR ARQUIVOS NAS PASTAS
# ============================================================================
echo "3️⃣  ARQUIVOS NAS PASTAS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RAW_COUNT=$(find data/raw/shorts -maxdepth 1 -type f -name '*.mp4' 2>/dev/null | wc -l)
TRANSFORM_COUNT=$(find data/transform/videos -maxdepth 1 -type f -name '*.mp4' 2>/dev/null | wc -l)
APPROVED_COUNT=$(find data/approved/videos -maxdepth 1 -type f -name '*.mp4' 2>/dev/null | wc -l)

echo "📁 data/raw/shorts/        : $RAW_COUNT arquivos"
echo "📁 data/transform/videos/  : $TRANSFORM_COUNT arquivos"
echo "📁 data/approved/videos/   : $APPROVED_COUNT arquivos"

if [ $RAW_COUNT -gt 0 ]; then
    echo ""
    echo "🔍 Primeiros 5 arquivos em raw/:"
    find data/raw/shorts -maxdepth 1 -type f -name '*.mp4' -printf '%f\n' 2>/dev/null | head -5
fi

if [ $TRANSFORM_COUNT -gt 0 ]; then
    echo ""
    echo "🔍 Primeiros 5 arquivos em transform/:"
    find data/transform/videos -maxdepth 1 -type f -name '*.mp4' -printf '%f\n' 2>/dev/null | head -5
fi

if [ $APPROVED_COUNT -gt 0 ]; then
    echo ""
    echo "🔍 Primeiros 5 arquivos em approved/:"
    find data/approved/videos -maxdepth 1 -type f -name '*.mp4' -printf '%f\n' 2>/dev/null | head -5
fi
echo ""
echo ""

# ============================================================================
# 4. TESTAR VideoStatusStore DIRETAMENTE
# ============================================================================
echo "4️⃣  TESTAR VideoStatusStore (Python)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 << 'EOF'
import sys
sys.path.insert(0, '/root/YTCaption-Easy-Youtube-API/services/make-video')

try:
    from app.services.video_status_factory import get_video_status_store
    
    store = get_video_status_store()
    stats = store.get_stats()
    
    print(f"✅ VideoStatusStore OK")
    print(f"   📊 Stats:")
    print(f"      - Aprovados: {stats['approved_count']}")
    print(f"      - Rejeitados: {stats['rejected_count']}")
    print(f"      - Erros: {stats['error_count']}")
    print(f"      - Total processado: {stats['total_processed']}")
    print(f"      - Taxa de aprovação: {stats['approval_rate']:.2%}")
    print(f"      - Taxa de erro: {stats['error_rate']:.2%}")
    
    # Listar últimos 3 erros (se houver)
    errors = store.list_errors(limit=3)
    if errors:
        print(f"\n   🔴 Últimos erros:")
        for err in errors:
            print(f"      - {err['video_id']}: {err['error_type']} (stage: {err['stage']})")
    
    # Listar últimos 3 aprovados (se houver)
    approved = store.list_approved(limit=3)
    if approved:
        print(f"\n   ✅ Últimos aprovados:")
        for appr in approved:
            print(f"      - {appr['video_id']}: {appr.get('title', 'N/A')}")
    
    # Listar últimos 3 rejeitados (se houver)
    rejected = store.list_rejected(limit=3)
    if rejected:
        print(f"\n   ❌ Últimos rejeitados:")
        for rej in rejected:
            print(f"      - {rej['video_id']}: {rej['rejection_reason']} (conf: {rej['confidence']:.2f})")

except Exception as e:
    print(f"❌ Erro ao testar VideoStatusStore: {e}")
    import traceback
    traceback.print_exc()
EOF

echo ""
echo ""

# ============================================================================
# 5. TESTAR ENDPOINTS DA API
# ============================================================================
echo "5️⃣  TESTAR ENDPOINTS DA API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 5.1 Endpoint raiz
echo "📍 GET / (Documentação)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")
echo "   Status: $HTTP_CODE"
if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ OK"
else
    echo "   ⚠️  Esperado 200, recebido $HTTP_CODE"
fi
echo ""

# 5.2 Health endpoint
echo "📍 GET /health"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
echo "   Status: $HTTP_CODE"
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "503" ]; then
    HEALTH_STATUS=$(curl -s "$BASE_URL/health" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    echo "   Health Status: $HEALTH_STATUS"
    if [ "$HEALTH_STATUS" = "healthy" ]; then
        echo "   ✅ Serviço saudável"
    else
        echo "   ⚠️  Serviço unhealthy (pode estar inicializando)"
    fi
else
    echo "   ❌ Erro inesperado"
fi
echo ""

# 5.3 Docs endpoint
echo "📍 GET /docs (Swagger UI)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/docs")
echo "   Status: $HTTP_CODE"
if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ OK - Swagger disponível"
else
    echo "   ⚠️  Docs indisponível"
fi
echo ""
echo ""

# ============================================================================
# 6. TESTE DO PIPELINE COMPLETO (/download)
# ============================================================================
echo "6️⃣  TESTE DO PIPELINE COMPLETO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏳ Executando pipeline com 5 vídeos (pode demorar 2-3 minutos)..."
echo ""

# Salvar estado antes
APPROVED_BEFORE=$(find data/approved/videos -maxdepth 1 -type f -name '*.mp4' 2>/dev/null | wc -l)

# Executar pipeline
RESPONSE=$(curl -s -X POST "$BASE_URL/download" \
    -F "query=Videos Satisfatorios" \
    -F "max_shorts=5" 2>&1)

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Extrair job_id
JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_id', ''))" 2>/dev/null)

if [ -n "$JOB_ID" ]; then
    echo ""
    echo "✅ Job criado: $JOB_ID"
    echo "🔍 Monitorando progresso..."
    echo ""
    
    # Monitorar por até 3 minutos
    MAX_CHECKS=36  # 36 * 5s = 3min
    CHECK_COUNT=0
    
    while [ $CHECK_COUNT -lt $MAX_CHECKS ]; do
        sleep 5
        CHECK_COUNT=$((CHECK_COUNT + 1))
        
        JOB_STATUS=$(curl -s "$BASE_URL/jobs/$JOB_ID" 2>/dev/null)
        STATUS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        
        echo "   [${CHECK_COUNT}/${MAX_CHECKS}] Status: $STATUS"
        
        if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
            echo ""
            echo "📊 Resultado Final:"
            echo "$JOB_STATUS" | python3 -m json.tool 2>/dev/null || echo "$JOB_STATUS"
            break
        fi
        
        # Mostrar progresso se disponível
        DOWNLOADED=$(echo "$JOB_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('result', {}).get('stats', {}).get('downloaded', 0))" 2>/dev/null || echo "0")
        if [ "$DOWNLOADED" != "0" ]; then
            echo "      Downloaded: $DOWNLOADED"
        fi
    done
    
    # Verificar arquivos aprovados após
    APPROVED_AFTER=$(find data/approved/videos -maxdepth 1 -type f -name '*.mp4' 2>/dev/null | wc -l)
    DELTA=$((APPROVED_AFTER - APPROVED_BEFORE))
    
    echo ""
    echo "📊 Resultado do Pipeline:"
    echo "   Aprovados antes: $APPROVED_BEFORE"
    echo "   Aprovados depois: $APPROVED_AFTER"
    echo "   Novos aprovados: $DELTA"
    
    if [ $DELTA -gt 0 ]; then
        echo "   ✅ Pipeline funcionando (novos vídeos aprovados)"
    else
        echo "   ⚠️  Nenhum vídeo novo aprovado (pode ser normal se todos tinham legendas)"
    fi
else
    echo "❌ Não foi possível extrair job_id da resposta"
fi

echo ""
echo ""

# ============================================================================
# 7. VERIFICAR ESTADO PÓS-PIPELINE
# ============================================================================
echo "7️⃣  ESTADO PÓS-PIPELINE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Recarregar stats do banco
python3 << 'EOF'
import sys
sys.path.insert(0, '/root/YTCaption-Easy-Youtube-API/services/make-video')

try:
    from app.services.video_status_factory import get_video_status_store
    
    store = get_video_status_store()
    stats = store.get_stats()
    
    print(f"📊 Stats Atualizados:")
    print(f"   - Aprovados: {stats['approved_count']}")
    print(f"   - Rejeitados: {stats['rejected_count']}")
    print(f"   - Erros: {stats['error_count']}")
    print(f"   - Total: {stats['total_processed']}")
    
    if stats['error_count'] > 0:
        print(f"\n🔴 Últimos erros registrados:")
        errors = store.list_errors(limit=5)
        for err in errors:
            print(f"   - {err['video_id']}: {err['error_type']}")
            print(f"     Stage: {err['stage']}, Message: {err['error_message'][:60]}...")

except Exception as e:
    print(f"❌ Erro: {e}")
EOF

echo ""
echo ""

# ============================================================================
# 8. TESTE DE CLEANUP SERVICE (se implementado)
# ============================================================================
echo "8️⃣  CLEANUP SERVICE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verificar se há endpoint de cleanup
CLEANUP_ENDPOINT="$BASE_URL/admin/cleanup/report"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$CLEANUP_ENDPOINT" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Cleanup endpoint disponível"
    echo "📊 Último relatório:"
    curl -s "$CLEANUP_ENDPOINT" | python3 -m json.tool 2>/dev/null
elif [ "$HTTP_CODE" = "404" ]; then
    echo "⚠️  Cleanup endpoint ainda não implementado (/admin/cleanup/report)"
    echo "   (Ver INTEGRATION_GUIDE.md para implementar)"
else
    echo "⚠️  Cleanup endpoint indisponível (código: $HTTP_CODE)"
fi

echo ""
echo ""

# ============================================================================
# 9. SUMÁRIO FINAL
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 SUMÁRIO FINAL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Banco de dados
if [ -f "data/database/video_status.db" ]; then
    echo "✅ Banco de dados: OK (data/database/video_status.db)"
else
    echo "❌ Banco de dados: NÃO ENCONTRADO"
fi

# VideoStatusStore
STORE_OK=$(python3 -c "
import sys
sys.path.insert(0, '/root/YTCaption-Easy-Youtube-API/services/make-video')
try:
    from app.services.video_status_factory import get_video_status_store
    store = get_video_status_store()
    print('OK')
except:
    print('FAIL')
" 2>/dev/null)

if [ "$STORE_OK" = "OK" ]; then
    echo "✅ VideoStatusStore: FUNCIONANDO"
else
    echo "❌ VideoStatusStore: COM PROBLEMAS"
fi

# API
if curl -s -f "$BASE_URL/health" > /dev/null 2>&1; then
    echo "✅ API: RESPONDENDO"
else
    echo "❌ API: SEM RESPOSTA"
fi

# Pipeline
if [ $DELTA -gt 0 ]; then
    echo "✅ Pipeline: FUNCIONANDO ($DELTA vídeos aprovados)"
elif [ -n "$JOB_ID" ]; then
    echo "⚠️  Pipeline: EXECUTADO (mas sem novos aprovados)"
else
    echo "❌ Pipeline: NÃO TESTADO"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Teste completo finalizado!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
