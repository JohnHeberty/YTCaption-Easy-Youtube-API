# 🔧 Gerenciamento de Cache - Audio Normalization Service

## 📋 Endpoints Administrativos

Agora o serviço tem os mesmos controles administrativos do **video-download-service**.

## 🗑️ Limpeza de Cache

### 1. **Limpeza Manual de Expirados**
```bash
POST /admin/cleanup
```

**O que faz**:
- Remove jobs expirados do Redis
- Deleta arquivos processados expirados
- Deleta arquivos de upload órfãos

**Exemplo**:
```bash
curl -X POST http://localhost:8001/admin/cleanup

# Resposta:
{
  "message": "Limpeza concluída",
  "jobs_removed": 5,
  "timestamp": "2025-10-24T18:30:00"
}
```

### 2. **Limpar TODO o Cache** ⚠️
```bash
DELETE /admin/cache
```

**O que faz**:
- ⚠️ Remove TODOS os jobs do Redis
- ⚠️ Deleta TODOS os arquivos processados
- ⚠️ Deleta TODOS os arquivos de upload
- **CUIDADO**: Ação irreversível!

**Exemplo**:
```bash
curl -X DELETE http://localhost:8001/admin/cache

# Resposta:
{
  "message": "Cache completamente limpo",
  "redis_keys_deleted": 15,
  "processed_files_deleted": 12,
  "upload_files_deleted": 3,
  "timestamp": "2025-10-24T18:35:00"
}
```

## 📊 Estatísticas

### 3. **Estatísticas Completas**
```bash
GET /admin/stats
```

**O que mostra**:
- Total de jobs (queued, processing, completed, failed)
- Arquivos processados (quantidade + tamanho)
- Arquivos de upload (quantidade + tamanho)
- Celery workers ativos
- Tasks em execução

**Exemplo**:
```bash
curl http://localhost:8001/admin/stats

# Resposta:
{
  "total_jobs": 25,
  "by_status": {
    "queued": 2,
    "processing": 1,
    "completed": 20,
    "failed": 2
  },
  "processed_files": {
    "count": 20,
    "total_size_mb": 45.3
  },
  "upload_files": {
    "count": 3,
    "total_size_mb": 12.5
  },
  "celery": {
    "active_workers": 1,
    "active_tasks": 1,
    "broker": "redis",
    "backend": "redis"
  }
}
```

### 4. **Estatísticas da Fila**
```bash
GET /admin/queue
```

**O que mostra**:
- Workers ativos
- Tasks registradas
- Tasks em execução
- Status da fila

**Exemplo**:
```bash
curl http://localhost:8001/admin/queue

# Resposta:
{
  "broker": "redis",
  "active_workers": 1,
  "registered_tasks": [
    "normalize_audio_task",
    "cleanup_expired_jobs_task"
  ],
  "active_tasks": {
    "celery@a4d05d121ef7": [
      {
        "id": "abc123def_invm",
        "name": "normalize_audio_task",
        "time_start": 1729800000.0
      }
    ]
  },
  "is_running": true
}
```

### 5. **Health Check Avançado**
```bash
GET /health
```

**O que verifica**:
- Celery workers
- Redis broker
- Redis store
- Job store
- Cache cleanup task

**Exemplo**:
```bash
curl http://localhost:8001/health

# Resposta (tudo OK):
{
  "status": "healthy",
  "service": "audio-normalization-service",
  "version": "2.0.0",
  "celery": {
    "healthy": true,
    "workers_active": 1,
    "broker": "redis"
  },
  "redis": {
    "healthy": true,
    "connection": "✅ Ativo"
  },
  "details": {
    "celery_workers": "✅ Ativo",
    "redis_broker": "✅ Ativo",
    "redis_store": "✅ Ativo",
    "job_store": "✅ Ativo",
    "cache_cleanup": "✅ Ativo"
  }
}

# Resposta (com problema):
{
  "status": "degraded",
  "service": "audio-normalization-service",
  ...
  "details": {
    "celery_workers": "❌ Problema",
    ...
  }
}
```

## 🎯 Casos de Uso

### Cenário 1: Limpeza Periódica
```bash
# Rodar diariamente (cron)
0 3 * * * curl -X POST http://localhost:8001/admin/cleanup
```

### Cenário 2: Espaço em Disco Cheio
```bash
# Ver quanto está usando
curl http://localhost:8001/admin/stats | jq '.processed_files'

# Limpar tudo se necessário
curl -X DELETE http://localhost:8001/admin/cache
```

### Cenário 3: Monitoramento
```bash
# Verificar saúde a cada 30s
watch -n 30 'curl -s http://localhost:8001/health | jq .status'

# Ver fila em tempo real
watch -n 5 'curl -s http://localhost:8001/admin/queue | jq .active_tasks'
```

### Cenário 4: Debug de Jobs
```bash
# Ver estatísticas gerais
curl http://localhost:8001/admin/stats

# Ver jobs específicos
curl http://localhost:8001/jobs

# Ver job específico
curl http://localhost:8001/jobs/abc123_invm

# Deletar job problemático
curl -X DELETE http://localhost:8001/jobs/abc123_invm
```

## 🔄 Comparação com video-download-service

| Feature | video-download | audio-normalization |
|---------|----------------|---------------------|
| POST /admin/cleanup | ✅ | ✅ |
| DELETE /admin/cache | ✅ | ✅ |
| GET /admin/stats | ✅ | ✅ |
| GET /admin/queue | ✅ | ✅ |
| GET /health | ✅ | ✅ |
| Estatísticas de arquivos | ✅ cache/ | ✅ processed/ + uploads/ |
| Celery monitoring | ✅ | ✅ |
| Redis health check | ✅ | ✅ |

**Diferenças**:
- video-download: Monitora pasta `./cache`
- audio-normalization: Monitora `./processed` + `./uploads`

## 📈 Dashboard Simples

Crie um script de monitoramento:

```bash
#!/bin/bash
# monitor.sh

echo "=== Audio Normalization Service ==="
echo ""

# Health
echo "Health:"
curl -s http://localhost:8001/health | jq '.status, .details'
echo ""

# Stats
echo "Statistics:"
curl -s http://localhost:8001/admin/stats | jq '{
  total_jobs,
  processed_mb: .processed_files.total_size_mb,
  uploads_mb: .upload_files.total_size_mb,
  active_tasks: .celery.active_tasks
}'
echo ""

# Queue
echo "Queue:"
curl -s http://localhost:8001/admin/queue | jq '{
  workers: .active_workers,
  running: .is_running
}'
```

Execute:
```bash
chmod +x monitor.sh
./monitor.sh
```

## 🚨 Alertas

### Disco Cheio
```bash
# Alerta se processed > 1GB
SIZE=$(curl -s http://localhost:8001/admin/stats | jq '.processed_files.total_size_mb')
if (( $(echo "$SIZE > 1000" | bc -l) )); then
  echo "⚠️ ALERTA: Cache muito grande ($SIZE MB)"
  curl -X POST http://localhost:8001/admin/cleanup
fi
```

### Workers Inativos
```bash
# Alerta se nenhum worker ativo
WORKERS=$(curl -s http://localhost:8001/admin/queue | jq '.active_workers')
if [ "$WORKERS" -eq 0 ]; then
  echo "⚠️ ALERTA: Nenhum worker ativo!"
  # docker-compose restart celery-worker
fi
```

### Jobs Falhando
```bash
# Alerta se > 10% de falhas
STATS=$(curl -s http://localhost:8001/admin/stats)
TOTAL=$(echo $STATS | jq '.total_jobs')
FAILED=$(echo $STATS | jq '.by_status.failed')
PERCENT=$(echo "scale=2; $FAILED / $TOTAL * 100" | bc)

if (( $(echo "$PERCENT > 10" | bc -l) )); then
  echo "⚠️ ALERTA: $PERCENT% de jobs falharam"
fi
```

## 🔐 Segurança

**⚠️ IMPORTANTE**: Endpoints administrativos devem ser protegidos em produção!

### Opção 1: Network Isolation
```yaml
# docker-compose.yml
audio-normalization-service:
  ports:
    - "127.0.0.1:8001:8001"  # Só acesso local
```

### Opção 2: Nginx com Auth
```nginx
location /admin/ {
    auth_basic "Admin Area";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://localhost:8001/admin/;
}
```

### Opção 3: API Key
```python
# Adicionar no main.py
from fastapi import Header

async def verify_admin_key(x_admin_key: str = Header(...)):
    if x_admin_key != os.getenv("ADMIN_KEY"):
        raise HTTPException(403, "Invalid admin key")

@app.post("/admin/cleanup", dependencies=[Depends(verify_admin_key)])
async def manual_cleanup():
    ...
```

## 📚 Documentação Automática

Acesse a documentação interativa:

```
http://localhost:8001/docs
```

Todos os endpoints administrativos estão documentados com exemplos interativos.

---

**Status**: ✅ Paridade completa com video-download-service  
**Novos endpoints**: 5 (cleanup, cache, stats, queue, health)  
**Monitoramento**: Completo (jobs, arquivos, workers, saúde)
