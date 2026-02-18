# Sistema de Rastreabilidade e Limpeza - Guia de Integração

## 📊 Visão Geral

Sistema completo para rastreamento de vídeos, limpeza automática e economização de espaço em disco.

### Componentes Principais

1. **VideoStatusStore** - Banco com 3 tabelas:
   - `approved_videos`: Vídeos aprovados (sem legendas)
   - `rejected_videos`: Vídeos rejeitados (com legendas)
   - `error_videos`: Vídeos com erro (não tentar novamente)

2. **CleanupService** - Limpeza automática a cada 10 minutos:
   - Detecta arquivos órfãos (sem tracking no DB)
   - Cataloga erros automaticamente
   - Remove temporários antigos
   - Monitora uso de disco

3. **FileOperations** - Movimentação eficiente:
   - **Move** arquivos (não copia)
   - Economiza espaço em disco
   - Tracking completo de localização

## 🔄 Fluxo de Arquivos (MOVE, não COPY)

```
1. Download     → data/raw/shorts/{video_id}.mp4
2. Transform    → data/transform/videos/{video_id}.mp4  (MOVE de raw/)
3. Approval     → data/approved/videos/{video_id}.mp4   (MOVE de transform/)
4. Rejection    → DELETE + registro no banco
```

## 🎯 Como Integrar no main.py

### 1. Imports no topo do arquivo

```python
from app.services.video_status_factory import get_video_status_store
from app.services.cleanup_service import CleanupService
from app.services.file_operations import FileOperations
```

### 2. Inicialização global (após `redis_store`)

```python
# Inicializar VideoStatusStore
video_status_store = get_video_status_store()

# Inicializar FileOperations
file_ops = FileOperations(data_dir="./data")

# Inicializar CleanupService
cleanup_service = CleanupService(
    video_status_store=video_status_store,
    data_dir="./data",
    cleanup_interval_minutes=10,     # Roda a cada 10min
    orphan_retention_hours=24,       # Considera órfão após 24h
    temp_retention_hours=6           # Limpa temp após 6h
)
```

### 3. Adicionar ao startup_event

```python
@app.on_event("startup")
async def startup_event():
    """Inicialização do serviço"""
    logger.info("🚀 Make-Video Service starting...")
    
    # Criar diretórios
    for dir_path in [...]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Criar diretório do banco
    Path("./data/database").mkdir(parents=True, exist_ok=True)
    
    # Iniciar cleanup automático (Redis)
    await redis_store.start_cleanup_task()
    logger.info("🧹 Redis cleanup task started")
    
    # Iniciar cleanup de arquivos órfãos
    await cleanup_service.start()
    logger.info("🧹 File cleanup service started (10min interval)")
    
    logger.info("✅ Make-Video Service ready!")
```

### 4. Adicionar ao shutdown_event

```python
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup ao desligar serviço"""
    logger.info("🛑 Make-Video Service shutting down...")
    
    # Parar CleanupService
    await cleanup_service.stop()
    logger.info("🛑 Cleanup service stopped")
```

## 🔧 Como Usar no Pipeline

### A. Na função download_shorts()

```python
# ANTES: Verificar apenas rejeitados
if blacklist.is_blacklisted(video_id):
    continue

# AGORA: Verificar rejeitados E erros
if video_status_store.is_rejected(video_id):
    logger.info(f"⏭️  Skipping {video_id} (rejected)")
    continue

if video_status_store.is_error(video_id):
    error_info = video_status_store.get_error(video_id)
    logger.warning(f"⏭️  Skipping {video_id} (error: {error_info['error_type']})")
    continue
```

### B. Na função transform_video()

```python
def transform_video(self, video_id: str) -> dict:
    """Transforma vídeo de raw/ → transform/ (MOVE)"""
    try:
        # MOVE arquivo de raw/ para transform/
        new_path = file_ops.move_to_transform(video_id)
        
        # Se precisa conversão H264
        if needs_h264_conversion(new_path):
            convert_to_h264(new_path)
        
        return {"success": True, "path": str(new_path)}
        
    except Exception as e:
        logger.error(f"Transform failed for {video_id}: {e}")
        
        # Catalogar erro
        video_status_store.add_error(
            video_id=video_id,
            error_type="transform_failed",
            error_message=str(e),
            error_traceback=traceback.format_exc(),
            stage="transform",
            file_path=str(file_ops.find_file(video_id))
        )
        
        # Limpar arquivo órfão
        file_ops.delete_rejected(video_id)
        
        raise
```

### C. Na função approve_video()

```python
def approve_video(self, video_id: str, title: str = None, url: str = None):
    """Aprova vídeo e MOVE para data/approved/"""
    try:
        # MOVE de transform/ para approved/
        final_path = file_ops.move_to_approved(video_id)
        
        # Registrar no banco
        video_status_store.add_approved(
            video_id=video_id,
            title=title,
            url=url,
            file_path=str(final_path),
            metadata={"approved_at": datetime.now().isoformat()}
        )
        
        logger.info(f"✅ Approved: {video_id} → {final_path}")
        
    except Exception as e:
        logger.error(f"Approval failed for {video_id}: {e}")
        
        # Catalogar erro
        video_status_store.add_error(
            video_id=video_id,
            error_type="approval_failed",
            error_message=str(e),
            error_traceback=traceback.format_exc(),
            stage="approval",
            file_path=str(file_ops.find_file(video_id))
        )
        
        raise
```

### D. Na função reject_video()

```python
def reject_video(self, video_id: str, reason: str, confidence: float = 1.0):
    """Rejeita vídeo e DELETA arquivo"""
    try:
        # DELETE arquivo (qualquer stage)
        file_ops.delete_rejected(video_id)
        
        # Registrar no banco
        video_status_store.add_rejected(
            video_id=video_id,
            reason=reason,
            confidence=confidence,
            metadata={"rejected_at": datetime.now().isoformat()}
        )
        
        logger.info(f"❌ Rejected: {video_id} ({reason})")
        
    except Exception as e:
        logger.error(f"Rejection failed for {video_id}: {e}")
        raise
```

### E. Tratamento de erros gerais

```python
try:
    # Processar vídeo
    download_video(video_id)
    
except Exception as e:
    logger.error(f"Download failed for {video_id}: {e}")
    
    # Catalogar erro detalhado
    video_status_store.add_error(
        video_id=video_id,
        error_type="download_failed",
        error_message=str(e),
        error_traceback=traceback.format_exc(),
        stage="download",
        retry_count=1,
        metadata={
            "query": query,
            "timestamp": datetime.now().isoformat()
        }
    )
    
    # Limpar arquivo órfão se existir
    orphan_path = file_ops.find_file(video_id)
    if orphan_path:
        orphan_path.unlink()
```

## 📊 Endpoints de Admin (Opcional)

Adicionar ao main.py:

```python
@app.get("/admin/cleanup/report")
async def get_cleanup_report():
    """Relatório do último cleanup"""
    report = await cleanup_service.run_cleanup()
    return report

@app.post("/admin/cleanup/manual")
async def trigger_manual_cleanup():
    """Trigger manual de limpeza"""
    report = await cleanup_service.manual_cleanup()
    return {
        "status": "completed",
        "report": report
    }

@app.get("/admin/errors")
async def list_errors(limit: int = 50, offset: int = 0):
    """Lista vídeos com erro"""
    errors = video_status_store.list_errors(limit=limit, offset=offset)
    return {
        "errors": errors,
        "total": video_status_store.count_errors()
    }

@app.get("/admin/stats")
async def get_video_stats():
    """Estatísticas gerais do banco"""
    return video_status_store.get_stats()
```

## 🎯 Benefícios

1. ✅ **Rastreabilidade Total**: Cada vídeo tem histórico completo
2. ✅ **Zero Duplicação**: Arquivos são movidos, não copiados
3. ✅ **Economia de Espaço**: Sem arquivos órfãos ocupando disco
4. ✅ **Análise de Erros**: Todos os erros catalogados para debugging
5. ✅ **Prevenção de Retry**: Não tenta baixar vídeos com erro novamente
6. ✅ **Limpeza Automática**: CleanupService roda a cada 10min
7. ✅ **Recuperação de Aprovados**: Pode re-baixar se perder MP4

## 🔍 Queries SQL Úteis

```bash
# Ver todos os erros
sqlite3 data/database/video_status.db "SELECT * FROM error_videos ORDER BY attempted_at DESC LIMIT 10"

# Ver vídeos aprovados
sqlite3 data/database/video_status.db "SELECT video_id, file_path, approved_at FROM approved_videos ORDER BY approved_at DESC LIMIT 10"

# Ver estatísticas
sqlite3 data/database/video_status.db "SELECT COUNT(*) as approved FROM approved_videos UNION ALL SELECT COUNT(*) as rejected FROM rejected_videos UNION ALL SELECT COUNT(*) as errors FROM error_videos"
```

## ⚠️ Cuidados

1. **Migração do Banco**: O banco agora está em `data/database/video_status.db` (não mais em `data/raw/shorts/blacklist.db`)
2. **File Movement**: Use sempre `file_ops.move_*` ao invés de `shutil.copy`
3. **Error Tracking**: Sempre catalogar erros com `add_error()` antes de deletar arquivos
4. **Cleanup Service**: Não parar manualmente, ele gerencia os órfãos automaticamente
