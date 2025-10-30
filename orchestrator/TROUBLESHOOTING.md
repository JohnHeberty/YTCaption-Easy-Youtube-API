# 🔧 Troubleshooting Guide - Orchestrator

## ⚠️ Problema: Job fica preso em `status: "queued"`

### Sintomas:
```json
{
  "job_id": "abc123",
  "status": "queued",
  "overall_progress": 0,
  "stages": {
    "download": {"status": "pending"},
    "normalization": {"status": "pending"},
    "transcription": {"status": "pending"}
  }
}
```

O job foi criado mas **nunca começou a executar**.

---

## 🔍 Diagnóstico

### 1. Verifique os logs do orchestrator
```bash
docker logs orchestrator-api --tail 100
```

**O que procurar:**
- ✅ `⚡ BACKGROUND TASK STARTED for job {job_id}` → Task foi iniciada
- ❌ Nenhuma mensagem → Background task não iniciou
- ❌ `Orchestrator not initialized` → Serviço não inicializou corretamente

### 2. Verifique saúde dos serviços
```bash
curl http://localhost:8000/health
```

**Resposta esperada:**
```json
{
  "status": "healthy",
  "microservices": {
    "video-downloader": "healthy",
    "audio-normalization": "healthy",
    "audio-transcriber": "healthy"
  }
}
```

### 3. Verifique Redis
```bash
docker ps | grep redis
docker logs orchestrator-redis
```

---

## ✅ Soluções

### Solução 1: Forçar execução manual do job

**Use o novo endpoint para forçar a execução:**

```bash
curl -X POST http://localhost:8000/jobs/{job_id}/execute
```

**Resposta:**
```json
{
  "job_id": "abc123",
  "status": "queued",
  "message": "Execução forçada agendada para job abc123. Use /jobs/abc123 para acompanhar.",
  "youtube_url": "https://www.youtube.com/watch?v=...",
  "overall_progress": 0
}
```

**Exemplo PowerShell:**
```powershell
$jobId = "bce28e256b844d1a"
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/jobs/$jobId/execute"
```

**Exemplo Python:**
```python
import requests

job_id = "bce28e256b844d1a"
response = requests.post(f"http://localhost:8000/jobs/{job_id}/execute")
print(response.json())
```

---

### Solução 2: Restart do orchestrator

Se forçar a execução não funcionar, faça restart:

```bash
cd orchestrator
docker-compose restart
```

Ou restart completo:

```bash
docker-compose down
docker-compose up -d
```

---

### Solução 3: Rebuild completo

Se o problema persistir:

```bash
cd orchestrator
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 🐛 Causas Comuns

### 1. Background Task não inicia
**Causa:** FastAPI background tasks podem falhar silenciosamente se:
- Exception durante inicialização do orchestrator
- Redis não está acessível
- Problemas de import/syntax

**Solução:** Verifique logs detalhados:
```bash
docker logs orchestrator-api --tail 200 | grep -i error
```

### 2. Orchestrator não inicializado
**Causa:** Falha no `lifespan` do FastAPI

**Verificar:**
```bash
docker logs orchestrator-api | grep "Orchestrator initialized"
```

**Deve aparecer:**
```
INFO - Orchestrator initialized successfully
```

**Se não aparecer:** Problema na inicialização. Verifique:
- Conexão com Redis
- Configuração de URLs dos microserviços

### 3. Redis inacessível
**Sintomas:**
- `Failed to connect to Redis`
- Job não é salvo corretamente

**Solução:**
```bash
# Verifica se Redis está rodando
docker ps | grep redis

# Testa conexão
docker exec orchestrator-redis redis-cli ping
# Deve retornar: PONG

# Verifica logs do Redis
docker logs orchestrator-redis --tail 50
```

---

## 📊 Checklist de Debug

Use este checklist para debug sistemático:

- [ ] **Docker Desktop rodando?**
  ```bash
  docker ps
  ```

- [ ] **Todos containers UP?**
  ```bash
  docker-compose ps
  ```

- [ ] **Redis acessível?**
  ```bash
  docker exec orchestrator-redis redis-cli ping
  ```

- [ ] **Orchestrator inicializado?**
  ```bash
  docker logs orchestrator-api | grep "Orchestrator initialized"
  ```

- [ ] **Background task agendada?**
  ```bash
  docker logs orchestrator-api | grep "Background task scheduled"
  ```

- [ ] **Background task iniciou?**
  ```bash
  docker logs orchestrator-api | grep "BACKGROUND TASK STARTED"
  ```

- [ ] **Microserviços healthy?**
  ```bash
  curl http://localhost:8000/health
  ```

- [ ] **Job existe no Redis?**
  ```bash
  curl http://localhost:8000/jobs/{job_id}
  ```

---

## 🚀 Workflow de Recuperação

### Cenário: Job criado mas não executou

```bash
# 1. Verifica se job existe
curl http://localhost:8000/jobs/bce28e256b844d1a

# 2. Força execução
curl -X POST http://localhost:8000/jobs/bce28e256b844d1a/execute

# 3. Monitora progresso (aguarda até 10min)
curl "http://localhost:8000/jobs/bce28e256b844d1a/sleep?timeout=600"

# OU monitora em tempo real via SSE (abra no navegador)
# http://localhost:8000/jobs/bce28e256b844d1a/stream
```

### Cenário: Múltiplos jobs presos

```bash
# 1. Lista todos os jobs
curl http://localhost:8000/jobs?limit=100

# 2. Identifica jobs em 'queued'
# Use jq para filtrar (se disponível):
curl http://localhost:8000/jobs | jq '.jobs[] | select(.status=="queued") | .job_id'

# 3. Força execução de cada um
for job_id in $(curl -s http://localhost:8000/jobs | jq -r '.jobs[] | select(.status=="queued") | .job_id'); do
    echo "Forcing execution for $job_id"
    curl -X POST http://localhost:8000/jobs/$job_id/execute
    sleep 2
done
```

---

## 📝 Logs Importantes

### Log de sucesso completo:
```
INFO - Pipeline job abc123 created and saved to Redis
INFO - Background task scheduled for job abc123
INFO - ⚡ BACKGROUND TASK STARTED for job abc123
INFO - Starting background pipeline for job abc123
INFO - ✅ Job abc123 retrieved from Redis, status: queued
INFO - 🚀 Executing pipeline for job abc123...
INFO - [PIPELINE:abc123] Starting DOWNLOAD stage for URL: https://...
INFO - Video job submitted: fcQ0oqsQvxE_audio
INFO - Job fcQ0oqsQvxE_audio completed successfully
INFO - [PIPELINE:abc123] DOWNLOAD completed: fcQ0oqsQvxE_audio.webm (31.5MB)
INFO - [PIPELINE:abc123] Starting NORMALIZATION stage
...
INFO - Pipeline for job abc123 finished with status: completed
```

### Log de problema:
```
INFO - Pipeline job abc123 created and saved to Redis
INFO - Background task scheduled for job abc123
[NENHUMA MENSAGEM DEPOIS]
```
→ **Background task não iniciou!** Use `/jobs/{id}/execute`

---

## 🔄 Prevenção

Para evitar que jobs fiquem presos:

1. **Monitore saúde:**
   ```bash
   watch -n 10 'curl -s http://localhost:8000/health | jq'
   ```

2. **Use SSE para novos jobs:**
   - Detecta problemas em tempo real
   - Client recebe notificação se falhar

3. **Configure timeout adequado:**
   - Vídeos longos precisam de mais tempo
   - Ajuste `timeout` nos endpoints `/sleep` e `/stream`

4. **Logs centralizados:**
   ```bash
   # Todos os logs em um lugar
   docker-compose logs -f
   ```

---

## 📞 Suporte

Se o problema persistir após todas as soluções:

1. **Colete informações:**
   ```bash
   # Logs completos
   docker logs orchestrator-api > orchestrator.log
   
   # Estado dos containers
   docker-compose ps > containers.txt
   
   # Health check
   curl http://localhost:8000/health > health.json
   
   # Job específico
   curl http://localhost:8000/jobs/{job_id} > job.json
   ```

2. **Verifique versões:**
   ```bash
   docker --version
   docker-compose --version
   ```

3. **Abra issue com:**
   - Logs coletados
   - Descrição do problema
   - Passos para reproduzir
   - Ambiente (Windows/Linux/Mac)

---

## 🎯 Quick Fix (TL;DR)

**Job preso em 'queued'?**

```bash
# PowerShell
$jobId = "SEU_JOB_ID_AQUI"
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/jobs/$jobId/execute"

# Bash
curl -X POST http://localhost:8000/jobs/SEU_JOB_ID_AQUI/execute
```

**Ainda não funciona?**

```bash
cd orchestrator
docker-compose restart
```

**AINDA não funciona?**

```bash
cd orchestrator
docker-compose down
docker-compose build
docker-compose up -d
```

✅ **Problema resolvido!**
