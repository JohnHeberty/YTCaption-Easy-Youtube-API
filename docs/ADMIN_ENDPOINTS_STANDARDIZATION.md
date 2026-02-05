# 🎯 Padronização de Endpoints Administrativos

**Data**: Fevereiro 2026  
**Status**: ✅ **COMPLETO**

---

## 📋 Visão Geral

Todos os 4 microserviços principais agora possuem endpoints administrativos **100% padronizados** para facilitar operações, monitoramento e recuperação de falhas.

## 🏗️ Microserviços Padronizados

| Serviço | Porta | Status | Endpoints Admin |
|---------|-------|--------|-----------------|
| **make-video** | 8004 | ✅ COMPLETO | 6/6 |
| **audio-transcriber** | 8005 | ✅ COMPLETO | 6/6 |
| **video-downloader** | 8002 | ✅ COMPLETO | 6/6 |
| **audio-normalization** | 8001 | ✅ COMPLETO | 6/6 |

---

## 📡 Endpoints Implementados (Todos os Serviços)

### 1. POST /admin/cleanup
**Descrição**: Limpeza do sistema (básica ou profunda - factory reset)

**Parâmetros**:
- `deep` (bool, default=false): Ativa modo de limpeza profunda
- `purge_celery_queue` (bool, default=false): Remove jobs da fila Celery

**Modos**:
- **Básico**: Remove jobs expirados + arquivos órfãos >24h
- **Deep**: FLUSHDB Redis + delete all files + optional Celery purge

**Uso**:
```bash
# Limpeza básica
curl -X POST "http://localhost:8004/admin/cleanup"

# Factory reset
curl -X POST "http://localhost:8004/admin/cleanup?deep=true&purge_celery_queue=true"
```

---

### 2. GET /admin/stats
**Descrição**: Estatísticas completas do sistema

**Retorna**:
- Jobs por status (queued/processing/completed/failed)
- Storage usage (arquivos + tamanho em MB)
- Celery workers (com graceful degradation)
- System disk space

**Uso**:
```bash
curl "http://localhost:8004/admin/stats"
```

---

### 3. POST /admin/cleanup-orphans
**Descrição**: Detecção e fix automático de jobs órfãos

**Parâmetros**:
- `max_age_minutes` (int, default=30): Threshold para considerar órfão

**Ações**:
- Detecta jobs stuck in processing >X minutes
- Marca como failed com reason detalhado
- Remove arquivos associados
- Calcula espaço liberado

**Uso**:
```bash
curl -X POST "http://localhost:8004/admin/cleanup-orphans?max_age_minutes=60"
```

---

### 4. GET /admin/queue ⭐ NOVO
**Descrição**: Informações detalhadas da fila de jobs

**Retorna**:
- Total de jobs
- Jobs por status (queued/processing/completed/failed)
- Job mais antigo (oldest_job)
- Job mais novo (newest_job)

**Uso**:
```bash
curl "http://localhost:8004/admin/queue"
```

**Exemplo de Resposta**:
```json
{
  "status": "success",
  "queue": {
    "total_jobs": 150,
    "by_status": {
      "queued": 5,
      "processing": 2,
      "completed": 140,
      "failed": 3
    },
    "oldest_job": {
      "job_id": "abc123",
      "created_at": "2026-02-01T10:00:00",
      "status": "completed"
    },
    "newest_job": {
      "job_id": "xyz789",
      "created_at": "2026-02-04T15:30:00",
      "status": "queued"
    }
  }
}
```

---

### 5. GET /jobs/orphaned ⭐ NOVO
**Descrição**: Lista jobs órfãos (stuck in processing)

**Parâmetros**:
- `max_age_minutes` (int, default=30): Idade mínima para considerar órfão

**Retorna**:
- Count de órfãos encontrados
- Lista detalhada com job_id, status, idade, timestamps

**Uso**:
```bash
# Órfãos >30min
curl "http://localhost:8004/jobs/orphaned"

# Órfãos >1h
curl "http://localhost:8004/jobs/orphaned?max_age_minutes=60"
```

**Exemplo de Resposta**:
```json
{
  "status": "success",
  "count": 2,
  "max_age_minutes": 30,
  "orphaned_jobs": [
    {
      "job_id": "abc123",
      "status": "processing",
      "created_at": "2026-02-04T10:00:00",
      "updated_at": "2026-02-04T10:05:00",
      "age_minutes": 125.5,
      "request": {...}
    }
  ]
}
```

---

### 6. POST /jobs/orphaned/cleanup ⭐ NOVO
**Descrição**: Cleanup granular de jobs órfãos

**Parâmetros**:
- `max_age_minutes` (int, default=30): Threshold para órfãos
- `mark_as_failed` (bool, default=true): Se true, marca como failed; se false, deleta

**Ações**:
1. Encontra jobs órfãos
2. Marca como failed (ou deleta completamente)
3. Remove arquivos associados (audio/video/temp)
4. Calcula espaço liberado em MB

**Uso**:
```bash
# Marca órfãos como failed
curl -X POST "http://localhost:8004/jobs/orphaned/cleanup?mark_as_failed=true"

# Deleta órfãos completamente
curl -X POST "http://localhost:8004/jobs/orphaned/cleanup?mark_as_failed=false"
```

**Exemplo de Resposta**:
```json
{
  "status": "success",
  "message": "Cleaned up 2 orphaned job(s)",
  "count": 2,
  "mode": "mark_as_failed",
  "max_age_minutes": 30,
  "space_freed_mb": 450.2,
  "actions": [
    {
      "job_id": "abc123",
      "action": "marked_as_failed",
      "age_minutes": 125.5,
      "files_deleted": [
        {"file": "uploads/abc123.mp3", "size_mb": 150.1}
      ],
      "reason": "Job orphaned: stuck in processing for 125.5 minutes"
    }
  ]
}
```

---

## 🛠️ Métodos Adicionados ao RedisJobStore

Todos os serviços agora possuem os seguintes métodos em `app/redis_store.py`:

### 1. `get_stats() -> dict`
Retorna contagem de jobs por status.

### 2. `cleanup_all_jobs() -> int`
Remove TODOS os jobs do Redis (factory reset).

### 3. `find_orphaned_jobs(max_age_minutes: int) -> List[Job]`
Encontra jobs órfãos (processing há muito tempo).

### 4. `get_queue_info() -> dict` ⭐ NOVO
Retorna estatísticas completas da fila.

### 5. `delete_job(job_id: str) -> bool` ⭐ NOVO
Deleta job individual do Redis.

---

## 📊 Diferenças por Serviço

### Prefixos Redis

| Serviço | Prefixo Redis |
|---------|---------------|
| make-video | `make_video:job:` |
| audio-transcriber | `transcription_job:` |
| video-downloader | (usa estrutura existente) |
| audio-normalization | `audio_job:` |

### Diretórios de Arquivos

#### make-video
- `audio_uploads/` - Áudios enviados
- `output_videos/` - Vídeos gerados
- `temp/` - Arquivos temporários

#### audio-transcriber
- `uploads/` - Áudios para transcrição
- `transcriptions/` - Transcrições geradas
- `temp/` - Arquivos temporários

#### video-downloader
- `cache/` - Vídeos baixados
- `temp/` - Arquivos temporários

#### audio-normalization
- `uploads/` - Áudios originais
- `processed/` - Áudios normalizados
- `temp/` - Arquivos temporários

---

## 🎯 Casos de Uso

### 1. Monitoramento Contínuo
```bash
# Verifica fila a cada 5 minutos
*/5 * * * * curl -s http://localhost:8004/admin/queue | jq '.queue.by_status'
```

### 2. Detecção Proativa de Órfãos
```bash
# Verifica órfãos a cada 15 minutos
*/15 * * * * curl -s http://localhost:8004/jobs/orphaned | jq '.count'
```

### 3. Cleanup Automático
```bash
# Cleanup automático de órfãos (>60min) a cada hora
0 * * * * curl -X POST "http://localhost:8004/jobs/orphaned/cleanup?max_age_minutes=60"
```

### 4. Factory Reset (Desenvolvimento)
```bash
# Reset completo do serviço
curl -X POST "http://localhost:8004/admin/cleanup?deep=true&purge_celery_queue=true"
```

### 5. Troubleshooting Workflow
```bash
# 1. Verifica estado da fila
curl http://localhost:8004/admin/queue | jq

# 2. Identifica órfãos
curl http://localhost:8004/jobs/orphaned | jq

# 3. Corrige órfãos
curl -X POST http://localhost:8004/jobs/orphaned/cleanup | jq

# 4. Verifica estatísticas
curl http://localhost:8004/admin/stats | jq
```

---

## 📈 Estatísticas de Implementação

### Código Adicionado

| Serviço | Linhas em main.py | Linhas em redis_store.py | Total |
|---------|-------------------|--------------------------|-------|
| make-video | +203 | +50 | +253 |
| audio-transcriber | +233 | +100 | +333 |
| video-downloader | +179 | +103 | +282 |
| audio-normalization | +232 | +104 | +336 |
| **TOTAL** | **+847** | **+357** | **+1204** |

### Testes

| Serviço | Testes Unitários | Status |
|---------|------------------|--------|
| make-video | 18 tests | ✅ 100% passing |
| audio-transcriber | - | ⏭️ (não criados) |
| video-downloader | - | ⏭️ (não criados) |
| audio-normalization | - | ⏭️ (não criados) |

---

## ✅ Checklist de Padronização

### Endpoints Core
- [x] POST /admin/cleanup (todos os 4 serviços)
- [x] GET /admin/stats (todos os 4 serviços)
- [x] POST /admin/cleanup-orphans (todos os 4 serviços)

### Novos Endpoints (Padronização Completa)
- [x] GET /admin/queue (todos os 4 serviços)
- [x] GET /jobs/orphaned (todos os 4 serviços)
- [x] POST /jobs/orphaned/cleanup (todos os 4 serviços)

### Métodos Redis Store
- [x] get_stats() (todos os 4 serviços)
- [x] cleanup_all_jobs() (todos os 4 serviços)
- [x] find_orphaned_jobs() (todos os 4 serviços)
- [x] get_queue_info() ⭐ (todos os 4 serviços)
- [x] delete_job() ⭐ (todos os 4 serviços)

### Documentação
- [x] Endpoint raiz (/) atualizado (todos os 4 serviços)
- [x] Docstrings completas (todos os 4 serviços)
- [x] README específico (make-video)
- [x] Documento de padronização geral (este arquivo)

### Git
- [x] Commit make-video (3fa251a)
- [x] Commit outros serviços (c952621)
- [x] Push para main

---

## 🚀 Próximos Passos (Opcional)

### Observabilidade
- [ ] Métricas Prometheus para todos os endpoints
- [ ] Dashboard Grafana unificado
- [ ] Alertas automáticos para órfãos

### Testes
- [ ] Testes unitários para audio-transcriber
- [ ] Testes unitários para video-downloader
- [ ] Testes unitários para audio-normalization
- [ ] Testes de integração end-to-end

### Automação
- [ ] Scripts de monitoramento central
- [ ] Auto-healing configurável
- [ ] Webhooks para notificações

---

## 🎉 Conclusão

### Status Final: ✅ **PADRONIZAÇÃO COMPLETA**

Todos os 4 microserviços agora possuem:
- ✅ **6 endpoints administrativos** padronizados
- ✅ **5 métodos Redis Store** auxiliares
- ✅ **Resiliência**: Circuit breaker, graceful degradation
- ✅ **Observabilidade**: Logs estruturados, métricas completas
- ✅ **Documentação**: Inline docs + OpenAPI automático
- ✅ **Alinhamento arquitetural**: 100% consistente

**Benefícios Alcançados**:
- 🎯 Facilita operações em todos os serviços
- 📊 Monitoramento unificado e consistente
- 🔧 Recuperação de falhas padronizada
- 🏗️ Arquitetura coesa e profissional

---

**Data de Conclusão**: 4 de Fevereiro de 2026  
**Versão**: 2.0.0  
**Commits**: 3fa251a (make-video), c952621 (outros serviços)
