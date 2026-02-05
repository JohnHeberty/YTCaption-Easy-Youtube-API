# 🔧 Endpoints Administrativos - make-video

## 📋 Sumário

Este documento descreve os endpoints administrativos implementados no serviço **make-video** para facilitar operações de manutenção, monitoramento e recuperação de falhas.

## ✅ Endpoints Implementados

### 1. `POST /admin/cleanup` - Limpeza do Sistema

**Descrição**: Realiza limpeza básica ou profunda (factory reset) do sistema.

**Parâmetros**:
- `deep` (bool, opcional, default=false): Ativa modo de limpeza profunda
- `purge_celery_queue` (bool, opcional, default=false): Remove jobs da fila Celery (apenas com deep=true)

**Modos de Operação**:

#### Modo Básico (`deep=false`)
Remove jobs expirados e arquivos órfãos antigos:
- Jobs com `expires_at < now()`
- Arquivos de audio/video sem job associado (>24h)
- Arquivos temporários antigos (>24h)

#### Modo Deep (`deep=true`)
**⚠️ ATENÇÃO: Factory Reset Completo**
- Executa `FLUSHDB` no Redis (remove TODOS os jobs)
- Deleta TODOS os arquivos (audio_uploads/, output_videos/, temp/)
- Limpa TODOS os arquivos temporários
- Opcional: Purga fila Celery (`purge_celery_queue=true`)

**Exemplo de Requisição**:
```bash
# Limpeza básica
curl -X POST "http://localhost:8000/admin/cleanup"

# Factory reset completo
curl -X POST "http://localhost:8000/admin/cleanup?deep=true&purge_celery_queue=true"
```

**Exemplo de Resposta**:
```json
{
  "message": "Cleanup completed successfully",
  "mode": "deep",
  "details": {
    "redis_flushed": true,
    "jobs_removed": 0,
    "files_deleted": {
      "audio": 5,
      "video": 3,
      "temp": 12
    },
    "space_freed_mb": 2450.5,
    "celery_queue_purged": true,
    "errors": []
  }
}
```

---

### 2. `GET /admin/stats` - Estatísticas do Sistema

**Descrição**: Retorna estatísticas completas sobre jobs, storage, cache e sistema.

**Exemplo de Requisição**:
```bash
curl -X GET "http://localhost:8000/admin/stats"
```

**Exemplo de Resposta**:
```json
{
  "jobs": {
    "queued": 5,
    "processing": 2,
    "completed": 150,
    "failed": 10,
    "total": 167
  },
  "storage": {
    "audio_uploads": {
      "count": 45,
      "size_mb": 1250.5
    },
    "output_videos": {
      "count": 38,
      "size_mb": 8900.2
    },
    "temp": {
      "count": 12,
      "size_mb": 350.8
    },
    "total_size_mb": 10501.5
  },
  "shorts_cache": {
    "cached_searches": 125,
    "blacklist_size": 8
  },
  "celery": {
    "active_workers": 2,
    "active_tasks": 3
  },
  "system": {
    "disk_total_gb": 500.0,
    "disk_used_gb": 245.3,
    "disk_free_gb": 254.7,
    "disk_usage_percent": 49.1
  }
}
```

**Dimensões Monitoradas**:
- **Jobs**: Contagem por status (queued, processing, completed, failed)
- **Storage**: Uso de disco por diretório (audio, video, temp)
- **Shorts Cache**: Buscas cacheadas e blacklist
- **Celery**: Workers ativos e tasks em execução (com graceful degradation)
- **System**: Espaço em disco total/usado/livre

---

### 3. `POST /admin/cleanup-orphans` - Recuperação de Jobs Órfãos

**Descrição**: Detecta e corrige jobs órfãos (stuck in processing) e arquivos sem job associado.

**Parâmetros**:
- `max_age_minutes` (int, opcional, default=30): Idade mínima (em minutos) para considerar job como órfão

**O que é um Job Órfão?**
Job no status `processing` há mais de X minutos sem atualização, indicando:
- Worker crashed
- Timeout sem tratamento
- Perda de conexão Redis
- Celery task stuck

**Ações Executadas**:
1. **Detecção**: Busca jobs em processing com `updated_at > max_age_minutes`
2. **Fix Automático**: Marca job como `failed` com reason detalhado
3. **Cleanup**: Remove arquivos associados (audio/video/temp)
4. **Arquivos Órfãos**: Remove files sem job correspondente no Redis

**Exemplo de Requisição**:
```bash
# Detecta jobs órfãos (>30min)
curl -X POST "http://localhost:8000/admin/cleanup-orphans"

# Detecta jobs órfãos (>1h)
curl -X POST "http://localhost:8000/admin/cleanup-orphans?max_age_minutes=60"
```

**Exemplo de Resposta**:
```json
{
  "message": "Cleanup orphans completed",
  "orphaned_jobs": {
    "found": 2,
    "fixed": 2,
    "details": [
      {
        "job_id": "abc123",
        "age_minutes": 125,
        "action": "marked_as_failed",
        "reason": "Job stuck in processing for 125 minutes"
      },
      {
        "job_id": "def456",
        "age_minutes": 85,
        "action": "marked_as_failed",
        "reason": "Job stuck in processing for 85 minutes"
      }
    ]
  },
  "orphaned_files": {
    "found": 3,
    "deleted": 3,
    "space_freed_mb": 450.2,
    "details": [
      {
        "file": "audio_uploads/xyz789.mp3",
        "size_mb": 150.1,
        "action": "deleted"
      },
      {
        "file": "output_videos/xyz789.mp4",
        "size_mb": 300.1,
        "action": "deleted"
      }
    ]
  },
  "errors": []
}
```

---

## 🛠️ Métodos Auxiliares no RedisJobStore

### `get_stats() -> dict`
Retorna contagem de jobs por status.

**Retorno**:
```python
{
    "queued": int,
    "processing": int,
    "completed": int,
    "failed": int,
    "total": int
}
```

### `cleanup_all_jobs() -> int`
Remove TODOS os jobs do Redis (factory reset).

**Retorno**: Número de jobs removidos

### `find_orphaned_jobs(max_age_minutes: int = 30) -> List[Job]`
Encontra jobs órfãos (processing há mais de X minutos).

**Parâmetros**:
- `max_age_minutes`: Threshold de idade

**Retorno**: Lista de objetos Job órfãos

---

## 📊 Testes

### Cobertura de Testes
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video
pytest tests/unit/test_admin_endpoints.py -v
```

**Resultados**: 12/12 testes passing (100%)

### Estrutura de Testes

#### TestRedisStoreAdminMethods (4 tests)
- ✅ `test_get_stats_structure` - Valida estrutura do retorno
- ✅ `test_stats_calculation_logic` - Valida cálculos de agregação
- ✅ `test_orphan_detection_logic` - Valida lógica de detecção de órfãos
- ✅ `test_orphan_age_threshold` - Valida thresholds de idade

#### TestAdminEndpoints (4 tests)
- ✅ `test_basic_cleanup_structure` - Valida resposta de cleanup básico
- ✅ `test_deep_cleanup_structure` - Valida resposta de cleanup profundo
- ✅ `test_admin_stats_structure` - Valida resposta de stats
- ✅ `test_cleanup_orphans_structure` - Valida resposta de orphan cleanup

#### TestAdminEndpointsIntegration (4 tests)
- ✅ `test_cleanup_workflow_basic` - Testa workflow de cleanup básico
- ✅ `test_cleanup_workflow_deep` - Testa workflow de factory reset
- ✅ `test_stats_aggregation` - Testa agregação de estatísticas
- ✅ `test_orphan_detection_workflow` - Testa workflow de detecção

---

## 🔒 Segurança e Resiliência

### Circuit Breaker Redis
Todos os métodos utilizam `ResilientRedisStore` que implementa:
- **Circuit breaker** para falhas Redis
- **Retry automático** com backoff exponencial
- **Graceful degradation** em caso de falha

### Proteções de Factory Reset
- `deep=false` por padrão (requer explicitação)
- Logs de WARNING antes de FLUSHDB
- Confirmação visual nos endpoints
- Purge Celery apenas com flag explícita

### Graceful Degradation
- **Celery stats**: Se Celery indisponível, retorna `{"error": "..."}`
- **File operations**: Continua mesmo se alguns arquivos falharem
- **Error tracking**: Lista de erros detalhada no response

### Validação de Parâmetros
- **Pydantic**: Validação automática de tipos
- **Range checks**: max_age_minutes >= 1
- **Boolean flags**: Validação de deep/purge_celery_queue

---

## 📈 Casos de Uso

### 1. Monitoramento Proativo
```bash
# Verifica estatísticas a cada 5 minutos (cron)
*/5 * * * * curl -s http://localhost:8000/admin/stats | jq '.jobs'
```

### 2. Limpeza Periódica
```bash
# Cleanup básico diário (remove expirados)
0 3 * * * curl -X POST http://localhost:8000/admin/cleanup
```

### 3. Recuperação de Falhas
```bash
# Detecta e corrige órfãos a cada 30 minutos
*/30 * * * * curl -X POST http://localhost:8000/admin/cleanup-orphans
```

### 4. Manutenção Mensal
```bash
# Factory reset completo (desenvolvimento)
curl -X POST "http://localhost:8000/admin/cleanup?deep=true&purge_celery_queue=true"
```

### 5. Troubleshooting
```bash
# 1. Verifica stats
curl http://localhost:8000/admin/stats | jq

# 2. Identifica órfãos
curl -X POST http://localhost:8000/admin/cleanup-orphans?max_age_minutes=15 | jq

# 3. Se necessário, cleanup completo
curl -X POST http://localhost:8000/admin/cleanup | jq
```

---

## 🎯 Comparação com Outros Microserviços

| Endpoint | make-video | audio-transcriber | video-downloader | audio-normalization |
|----------|------------|-------------------|------------------|---------------------|
| `POST /admin/cleanup` | ✅ | ✅ | ✅ | ✅ |
| `GET /admin/stats` | ✅ | ✅ | ✅ | ✅ |
| `POST /admin/cleanup-orphans` | ✅ | ✅ | ❌ | ✅ |

**Status**: ✅ **Alinhamento arquitetural completo**

---

## 📝 Logs Estruturados

Todos os endpoints geram logs estruturados (JSON) para observabilidade:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "service": "make-video",
  "endpoint": "/admin/cleanup",
  "action": "cleanup_completed",
  "details": {
    "mode": "deep",
    "jobs_removed": 0,
    "files_deleted": 20,
    "space_freed_mb": 2450.5
  }
}
```

---

## 🚀 Próximos Passos (Opcionais)

### Integração com Observabilidade
- [ ] Métricas Prometheus para jobs/storage/orphans
- [ ] Alertas automáticos para orphans detectados
- [ ] Dashboard Grafana para visualização

### Testes Avançados
- [ ] Testes de integração com Redis real
- [ ] Testes end-to-end em Docker
- [ ] Performance tests para cleanup em larga escala

### Automação
- [ ] Cron jobs para cleanup periódico
- [ ] Webhooks para notificações de órfãos
- [ ] Auto-healing para jobs stuck

---

## 📚 Referências

- **Documentação API**: http://localhost:8000/docs (Swagger UI)
- **Análise Comparativa**: [ANALISE_ENDPOINTS_ADMIN.md](./ANALISE_ENDPOINTS_ADMIN.md)
- **Código Fonte**:
  - [app/main.py](./app/main.py) - Endpoints principais
  - [app/redis_store.py](./app/redis_store.py) - Métodos auxiliares
  - [tests/unit/test_admin_endpoints.py](./tests/unit/test_admin_endpoints.py) - Testes unitários

---

**Última Atualização**: Janeiro 2024  
**Versão**: 1.0.0  
**Status**: ✅ Produção
