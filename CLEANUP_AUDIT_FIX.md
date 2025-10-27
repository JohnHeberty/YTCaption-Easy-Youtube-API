# 🔥 Auditoria e Correção do Endpoint `/admin/cleanup`

## 📋 Problema Identificado

O endpoint `/admin/cleanup` dos 3 microserviços **NÃO estava limpando completamente o sistema**:

### ❌ Antes (Problemas):
1. ❌ **Redis**: Apenas jobs expirados eram removidos (não TODOS)
2. ❌ **Arquivos**: Apenas arquivos antigos (baseado em TTL)
3. ❌ **Modelos Whisper**: Nunca eram removidos (~500MB cada)
4. ❌ **Fila do Redis**: Não era zerada completamente

**Resultado:** Sistema nunca era completamente resetado, arquivos e jobs se acumulavam.

---

## ✅ Solução Implementada

Agora o endpoint `/admin/cleanup` faz **LIMPEZA TOTAL** em todos os 3 microserviços:

### 🔴 Audio-Transcriber

**Limpa ABSOLUTAMENTE TUDO:**
1. ✅ **TODOS os jobs** do Redis (`transcription_job:*`)
2. ✅ **TODOS os arquivos** de `uploads/`
3. ✅ **TODOS os arquivos** de `transcriptions/`
4. ✅ **TODOS os arquivos** de `temp/`
5. ✅ **TODOS os modelos** Whisper em `models/` (~500MB cada)

**Arquivo:** `services/audio-transcriber/app/main.py`

### 🟡 Audio-Normalization

**Limpa ABSOLUTAMENTE TUDO:**
1. ✅ **TODOS os jobs** do Redis (`normalization_job:*`)
2. ✅ **TODOS os arquivos** de `uploads/`
3. ✅ **TODOS os arquivos** de `processed/`
4. ✅ **TODOS os arquivos** de `temp/`

**Arquivo:** `services/audio-normalization/app/main.py`

### 🟢 Video-Downloader

**Limpa ABSOLUTAMENTE TUDO:**
1. ✅ **TODOS os jobs** do Redis (`video_job:*`)
2. ✅ **TODOS os arquivos** de `cache/`
3. ✅ **TODOS os arquivos** de `downloads/`
4. ✅ **TODOS os arquivos** de `temp/`

**Arquivo:** `services/video-downloader/app/main.py`

---

## 🎯 Como Usar

### 1. Limpar Audio-Transcriber

```bash
curl -X POST http://localhost:8003/admin/cleanup

# Response:
{
  "message": "🔥 LIMPEZA TOTAL iniciada em background - TUDO será removido!",
  "cleanup_id": "cleanup_total_20251027_143022",
  "status": "processing",
  "warning": "Esta operação removerá TODOS os jobs, arquivos e modelos do sistema",
  "note": "Verifique os logs para acompanhar o progresso e resultados."
}
```

### 2. Limpar Audio-Normalization

```bash
curl -X POST http://localhost:8002/admin/cleanup
```

### 3. Limpar Video-Downloader

```bash
curl -X POST http://localhost:8001/admin/cleanup
```

### 4. Limpar TUDO de Uma Vez

```bash
# Script para limpar os 3 microserviços
curl -X POST http://localhost:8001/admin/cleanup  # Video
curl -X POST http://localhost:8002/admin/cleanup  # Audio Norm
curl -X POST http://localhost:8003/admin/cleanup  # Audio Trans
```

---

## 📊 Logs de Exemplo

### Antes da Limpeza:
```
2025-10-27 14:30:00 - INFO - Redis: 15 jobs ativos
2025-10-27 14:30:00 - INFO - Uploads: 23 arquivos (145.2MB)
2025-10-27 14:30:00 - INFO - Models: 3 modelos Whisper (1.5GB)
```

### Durante a Limpeza:
```
2025-10-27 14:30:15 - WARNING - 🔥 INICIANDO LIMPEZA TOTAL DO SISTEMA - TUDO SERÁ REMOVIDO!
2025-10-27 14:30:15 - INFO - 🗑️  Redis: 15 jobs removidos
2025-10-27 14:30:16 - INFO - 🗑️  Uploads: 23 arquivos removidos
2025-10-27 14:30:17 - INFO - 🗑️  Transcriptions: 18 arquivos removidos
2025-10-27 14:30:18 - INFO - 🗑️  Temp: 5 arquivos removidos
2025-10-27 14:30:25 - WARNING - 🗑️  Models: 3 arquivos de modelo removidos (1500.00MB)
```

### Resultado Final:
```
2025-10-27 14:30:25 - WARNING - 🔥 LIMPEZA TOTAL CONCLUÍDA: 15 jobs do Redis + 49 arquivos + 3 modelos removidos (1645.2MB liberados)
```

---

## 🛡️ Resiliência

### ✅ Características:

1. **Não Bloqueante**: Retorna em < 500ms
2. **Background**: Executa em BackgroundTasks do FastAPI
3. **Async I/O**: Usa `asyncio.to_thread()` para operações de arquivo
4. **Error Handling**: Captura erros individuais, continua limpeza
5. **Logging Detalhado**: Cada operação é logada
6. **Relatório Completo**: Retorna estatísticas de limpeza

### Exemplo de Erro Parcial:
```json
{
  "message": "🔥 LIMPEZA TOTAL CONCLUÍDA: 15 jobs + 45 arquivos removidos (1200MB liberados) ⚠️ com 2 erros",
  "jobs_removed": 15,
  "files_deleted": 45,
  "models_deleted": 2,
  "space_freed_mb": 1200.5,
  "errors": [
    "Upload/file123.mp3: Permission denied",
    "Models/tiny.pt: File in use"
  ]
}
```

---

## ⚠️ AVISOS IMPORTANTES

### 🔴 ATENÇÃO:
- ✅ Este endpoint **REMOVE TUDO** sem confirmação
- ✅ **Não há rollback** - dados são permanentemente deletados
- ✅ Modelos Whisper serão **re-baixados** na próxima transcrição (~500MB)
- ✅ Jobs em execução serão **cancelados**

### 🎯 Use Este Endpoint Para:
- ✅ Resetar completamente o sistema
- ✅ Liberar espaço em disco
- ✅ Desenvolvimento/testes
- ✅ Manutenção periódica

### ⛔ NÃO Use em Produção sem:
- Backup de dados importantes
- Notificação aos usuários
- Janela de manutenção agendada

---

## 📈 Comparação: Antes vs Depois

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Jobs Redis** | Só expirados | ✅ **TODOS** |
| **Uploads** | Só antigos | ✅ **TODOS** |
| **Processed** | Só antigos | ✅ **TODOS** |
| **Transcriptions** | Só antigos | ✅ **TODOS** |
| **Temp** | Parcial | ✅ **TODOS** |
| **Models Whisper** | ❌ Nunca | ✅ **TODOS** |
| **Tempo Response** | Bloqueava | ✅ < 500ms |
| **Background** | ❌ Não | ✅ Sim |
| **Logs** | Básico | ✅ Detalhado |
| **Relatório** | Simples | ✅ Completo |

---

## 🧪 Testes

### 1. Teste Manual

```bash
# 1. Crie alguns jobs
curl -X POST http://localhost:8003/jobs -F "audio_file=@test.mp3"

# 2. Verifique que existem
curl http://localhost:8003/admin/stats

# 3. Limpe tudo
curl -X POST http://localhost:8003/admin/cleanup

# 4. Verifique logs
docker compose logs audio-transcriber | grep "LIMPEZA"

# 5. Verifique que está vazio
curl http://localhost:8003/admin/stats
# Deve retornar: {"total_jobs": 0, ...}
```

### 2. Teste de Resiliência

```bash
# Limpeza deve retornar imediatamente
time curl -X POST http://localhost:8003/admin/cleanup
# real    0m0.450s  ✅ < 500ms
```

---

## 📝 Código Implementado

### Função Principal (_perform_cleanup / _perform_total_cleanup)

```python
async def _perform_cleanup():
    """
    Executa limpeza COMPLETA do sistema em background
    
    ZERA ABSOLUTAMENTE TUDO:
    - TODOS os jobs do Redis (não só expirados)
    - TODOS os arquivos de uploads/
    - TODOS os arquivos de transcriptions/
    - TODOS os arquivos temporários
    - TODOS os modelos baixados em models/
    """
    try:
        report = {
            "jobs_removed": 0,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "models_deleted": 0,
            "errors": []
        }
        
        logger.warning("🔥 INICIANDO LIMPEZA TOTAL DO SISTEMA - TUDO SERÁ REMOVIDO!")
        
        # 1. LIMPAR TODOS OS JOBS DO REDIS
        keys = job_store.redis.keys("transcription_job:*")
        if keys:
            for key in keys:
                job_store.redis.delete(key)
            report["jobs_removed"] = len(keys)
        
        # 2-5. LIMPAR TODOS OS ARQUIVOS
        # (implementação completa nos arquivos)
        
        return report
    except Exception as e:
        logger.error(f"❌ Erro na limpeza total: {e}")
```

### Endpoint

```python
@app.post("/admin/cleanup")
async def manual_cleanup(background_tasks: BackgroundTasks):
    """🔥 LIMPEZA TOTAL DO SISTEMA (RESILIENTE)"""
    cleanup_job_id = f"cleanup_total_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Agenda limpeza TOTAL em background
    background_tasks.add_task(_perform_cleanup)
    
    return {
        "message": "🔥 LIMPEZA TOTAL iniciada em background - TUDO será removido!",
        "cleanup_id": cleanup_job_id,
        "status": "processing",
        "warning": "Esta operação removerá TODOS os jobs, arquivos e modelos do sistema"
    }
```

---

## ✅ Checklist de Validação

- [x] Audio-Transcriber: Limpa TODOS jobs do Redis
- [x] Audio-Transcriber: Limpa TODOS arquivos (uploads, transcriptions, temp)
- [x] Audio-Transcriber: Limpa TODOS modelos Whisper
- [x] Audio-Normalization: Limpa TODOS jobs do Redis
- [x] Audio-Normalization: Limpa TODOS arquivos (uploads, processed, temp)
- [x] Video-Downloader: Limpa TODOS jobs do Redis
- [x] Video-Downloader: Limpa TODOS arquivos (cache, downloads, temp)
- [x] Todos: Retornam em < 500ms (background)
- [x] Todos: Logs detalhados
- [x] Todos: Error handling robusto
- [x] Todos: Documentação atualizada

---

## 🎓 Conclusão

O endpoint `/admin/cleanup` agora executa **limpeza completa e total** do sistema:

✅ **Redis**: Zerado (TODOS os jobs)  
✅ **Arquivos**: Zerados (inputs, outputs, temp)  
✅ **Modelos**: Zerados (incluindo Whisper)  
✅ **Resiliência**: Background, não bloqueia API  
✅ **Logs**: Detalhados e informativos  

**Sistema pode ser completamente resetado com um único comando!**

---

*Auditoria e correção realizadas em: 27 de Outubro de 2025*  
*Arquivos modificados: 3 (audio-transcriber, audio-normalization, video-downloader)*
