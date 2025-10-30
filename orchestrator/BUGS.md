# 🐛 BUGS E PROBLEMAS IDENTIFICADOS - YouTube Caption Orchestrator

## ⚠️ CRÍTICOS (P0) - RESOLVIDOS

### ✅ 1. Jobs ficando travados em "queued" (RESOLVIDO)
**Status:** CORRIGIDO ✅  
**Descrição:** Jobs ficavam permanentemente em status "queued" sem nunca executar.  
**Causa Raiz:** Orchestrator não salvava o job no Redis durante a execução do pipeline.  
**Sintomas:**
- Job criado com sucesso via POST /process
- Status retorna sempre "queued", progress 0%
- Logs mostram execução normal do pipeline
- Redis não refletia progresso em tempo real

**Solução Implementada:**
- Passou `redis_store` como parâmetro para `PipelineOrchestrator.__init__()`
- Adicionou 6 pontos de salvamento Redis:
  * Após status = DOWNLOADING
  * Após conclusão de download
  * Após status = NORMALIZING  
  * Após conclusão de normalização
  * Após status = TRANSCRIBING
  * Após conclusão de transcrição

**Arquivos Modificados:**
- `orchestrator/main.py` - linha 52: `orchestrator = PipelineOrchestrator(redis_store=redis_store)`
- `orchestrator/modules/orchestrator.py` - linhas 287, 303, 318, 348, 367, 408

**Teste de Validação:**
```powershell
# Status mudou de "queued" para "downloading" em 3s
POST /process → job_id
GET /jobs/{job_id} após 3s → status: "downloading" ✓
```

---

## 🔥 CRÍTICOS (P0) - PENDENTES

### ❌ 2. Factory Reset não limpa filas Redis nos microserviços
**Status:** NÃO CORRIGIDO ❌  
**Prioridade:** P0 (Crítico)  
**Descrição:** Endpoint `/admin/factory-reset` do orchestrator chama `/admin/cleanup?deep=true` nos microserviços, mas os serviços **não limpam as filas Celery do Redis**.

**Impacto:**
- Após factory reset, jobs antigos permanecem nas filas Celery
- Workers processam jobs fantasmas que não existem mais
- Logs ficam poluídos com erros de "job not found"
- Impossível ter um reset limpo do sistema

**Serviços Afetados:**
1. **video-downloader** (Redis DB 0)
   - Fila: `video_downloader_queue`
   - Cleanup remove apenas keys `video_job:*`
   - **FALTA:** Limpar fila Celery

2. **audio-normalization** (Redis DB 1)
   - Fila: `audio_normalization_queue`
   - Cleanup remove apenas keys `audio_job:*`
   - **FALTA:** Limpar fila Celery

3. **audio-transcriber** (Redis DB 2)
   - Fila: `audio_transcription_queue`
   - Cleanup remove apenas keys `transcription_job:*`
   - **FALTA:** Limpar fila Celery

**Código Atual (video-downloader/app/main.py:398):**
```python
async def _perform_total_cleanup():
    redis = Redis.from_url(redis_url, decode_responses=True)
    keys = redis.keys("video_job:*")  # ❌ Só remove jobs
    for key in keys:
        redis.delete(key)
    # ❌ FALTA: Limpar fila Celery!
```

**Solução Necessária:**
```python
async def _perform_total_cleanup():
    from celery import Celery
    from redis import Redis
    
    # 1. Limpar jobs do Redis
    redis = Redis.from_url(redis_url, decode_responses=True)
    keys = redis.keys("video_job:*")
    for key in keys:
        redis.delete(key)
    
    # 2. ✅ LIMPAR FILA CELERY
    celery_app = Celery()
    celery_app.config_from_object('app.celery_config')
    
    # Purge da fila
    celery_app.control.purge()
    
    # Ou limpar específico por fila
    from kombu import Connection
    with Connection(redis_url) as conn:
        conn.default_channel.queue_purge('video_downloader_queue')
    
    logger.warning("🔥 Fila Celery purgada!")
```

**Arquivos a Modificar:**
- `services/video-downloader/app/main.py` (linha ~398)
- `services/audio-normalization/app/main.py` (linha similar)
- `services/audio-transcriber/app/main.py` (linha similar)

**Teste de Validação:**
```bash
# 1. Criar jobs
POST /process → job1, job2, job3

# 2. Factory reset
POST /admin/factory-reset

# 3. Verificar Redis
redis-cli -n 0 KEYS "video_job:*"  # Deve retornar vazio
redis-cli -n 0 LLEN video_downloader_queue  # Deve retornar 0

# 4. Verificar logs dos workers
# NÃO deve ter "job not found" após reset
```

---

### ❌ 3. Jobs ficando parados sem logs de erro
**Status:** INVESTIGAÇÃO EM ANDAMENTO 🔍  
**Prioridade:** P0 (Crítico)  
**Descrição:** Jobs permanecem em estado "downloading" indefinidamente sem logs de erro no orchestrator ou microserviços.

**Sintomas:**
- Job fica em "downloading" por >5 minutos
- Overall progress = 0%
- Download stage: status="pending", progress=0%
- **Sem logs de erro** no orchestrator
- **Sem logs de erro** no video-downloader
- Health checks todos OK

**Hipóteses (em ordem de probabilidade):**

#### **H1: Job submetido mas não recebido pelo worker Celery** (75%)
**Evidência:**
- Orchestrator logs mostram: `"Submitting JSON to video-downloader: http://ytcaption-video-downloader:8000/jobs"`
- Video-downloader recebe POST mas não enfileira no Celery
- Worker Celery não processa porque não há task na fila

**Como Verificar:**
```bash
# Verificar se há tasks na fila
docker exec ytcaption-video-downloader-celery celery -A app.celery_config inspect active
docker exec ytcaption-video-downloader-celery celery -A app.celery_config inspect reserved

# Verificar se worker está ouvindo a fila correta
docker logs ytcaption-video-downloader-celery | grep "video_downloader_queue"
```

**Possível Causa:**
- Worker não está registrado na fila
- Celery não está conectado ao Redis
- Task não foi enfileirada corretamente

**Código Suspeito (video-downloader/app/main.py):**
```python
@app.post("/jobs")
async def create_download_job(request: DownloadRequest, background_tasks: BackgroundTasks):
    job = VideoJob(...)
    redis_store.save_job(job)  # ✓ Salva no Redis
    
    # ❌ SUSPEITA: Task Celery pode não estar sendo enfileirada
    background_tasks.add_task(...)  # Usa FastAPI background, não Celery?
    
    return {"job_id": job.id}
```

**Se usar FastAPI background_tasks ao invés de Celery:**
- Task roda no processo do uvicorn
- Se uvicorn reiniciar, task é perdida
- Não há persistência da tarefa

**Correção Necessária:**
```python
from app.celery_tasks import process_download_task

@app.post("/jobs")
async def create_download_job(request: DownloadRequest):
    job = VideoJob(...)
    redis_store.save_job(job)
    
    # ✅ Usar Celery para persistência
    process_download_task.apply_async(
        args=[job.id],
        queue='video_downloader_queue'
    )
    
    return {"job_id": job.id}
```

#### **H2: Polling travado sem atualizar progress** (15%)
**Evidência:**
- `_wait_until_done()` faz polling mas não atualiza `stage.progress`
- Orchestrator pode estar travado no loop de polling

**Como Verificar:**
```python
# Adicionar logs detalhados no polling
async def _wait_until_done(self, client, job_id, stage):
    attempts = 0
    while attempts < self.max_attempts:
        logger.info(f"[POLL] Attempt {attempts}: job={job_id}, stage={stage.name}")  # ← ADD
        status = await client.get_job_status(job_id)
        logger.info(f"[POLL] Response: {status}")  # ← ADD
        # ...
```

#### **H3: Network timeout entre containers** (5%)
**Evidência:**
- Container orchestrator não consegue conectar ao video-downloader
- Mas health check funciona (inconsistência)

**Como Verificar:**
```bash
# Testar conectividade entre containers
docker exec ytcaption-orchestrator ping ytcaption-video-downloader
docker exec ytcaption-orchestrator curl http://ytcaption-video-downloader:8000/health
```

#### **H4: Race condition no Redis** (5%)
**Evidência:**
- Job salvo mas imediatamente sobrescrito
- Orchestrator lê versão desatualizada

**Como Verificar:**
```bash
# Monitorar operações Redis em tempo real
docker exec orchestrator-redis redis-cli MONITOR | grep "video_job"
```

**Ações Imediatas:**
1. ✅ Adicionar logs verbosos no polling (`_wait_until_done`)
2. ✅ Adicionar logs no endpoint `/jobs` dos microserviços
3. ✅ Verificar se Celery workers estão processando
4. ✅ Verificar filas Celery com `celery inspect`
5. ✅ Adicionar timeout explícito no polling (já existe: `max_poll_attempts`)

**Teste de Reprodução:**
```bash
# 1. Limpar tudo
POST /admin/factory-reset

# 2. Criar job
POST /process → job_id

# 3. Monitorar em paralelo:
# Terminal 1: Logs orchestrator
docker logs -f ytcaption-orchestrator

# Terminal 2: Logs video-downloader
docker logs -f ytcaption-video-downloader

# Terminal 3: Logs Celery worker
docker logs -f ytcaption-video-downloader-celery

# Terminal 4: Filas Redis
watch -n 1 'redis-cli -n 0 LLEN video_downloader_queue'

# Terminal 5: Polling status
watch -n 2 'curl -s http://localhost:8004/jobs/{job_id} | jq .status'
```

---

## ⚠️ ALTOS (P1)

### 4. Circuit Breaker pode bloquear serviços saudáveis temporariamente
**Status:** DESIGN ISSUE 🟡  
**Prioridade:** P1 (Alto)  
**Descrição:** Circuit breaker abre após 3 falhas consecutivas e bloqueia requisições por 60s, mesmo que o serviço se recupere rapidamente.

**Cenários Problemáticos:**
- Microserviço reinicia (downtime de 5s)
- Circuit breaker detecta 3 falhas e abre
- Serviço fica bloqueado por 60s mesmo estando saudável

**Configuração Atual:**
```python
# orchestrator/modules/config.py
"circuit_breaker_max_failures": 3,
"circuit_breaker_recovery_timeout": 60  # segundos
```

**Impacto:**
- Pipeline falha desnecessariamente
- Latência adicional de até 60s

**Solução Proposta:**
1. Reduzir recovery_timeout para 15s
2. Implementar half-open state (permite 1 requisição teste)
3. Adicionar exponential backoff no recovery

```python
class MicroserviceClient:
    def _is_circuit_open(self) -> bool:
        if not self._circuit_open:
            return False
        
        # Half-open: Permite 1 teste após timeout
        if datetime.now() - self.last_failure_time > timedelta(seconds=15):
            logger.info(f"[{self.service_name}] Circuit breaker HALF-OPEN - testing")
            return False  # Permite 1 requisição
        
        return True
```

---

### 5. Logs de erro HTTP não incluem response body
**Status:** MELHORIA 🟡  
**Prioridade:** P1 (Alto)  
**Descrição:** Quando microserviços retornam erro 4xx/5xx, apenas o status code é logado, não o corpo da resposta com detalhes do erro.

**Código Atual:**
```python
except httpx.HTTPStatusError as e:
    raise RuntimeError(f"[{self.service_name}] HTTP error: {e}")  # ❌ Sem detalhes
```

**Solução:**
```python
except httpx.HTTPStatusError as e:
    error_body = e.response.text if e.response else "No response body"
    logger.error(f"[{self.service_name}] HTTP {e.response.status_code}: {error_body}")
    raise RuntimeError(f"[{self.service_name}] HTTP {e.response.status_code}: {error_body}")
```

---

### 6. Max file size não configurável por microserviço
**Status:** LIMITAÇÃO 🟡  
**Prioridade:** P1 (Alto)  
**Descrição:** Limite de tamanho de arquivo (`max_file_size_mb`) é global para todos os serviços, mas cada serviço tem necessidades diferentes.

**Problema:**
- Video-downloader pode gerar arquivos grandes (500MB+)
- Audio-normalization recebe/gera arquivos menores (100MB típico)
- Transcriber precisa apenas do áudio (50MB típico)

**Solução:**
```python
# config.py
"video-downloader": {
    "max_file_size_mb": 500,  # Vídeos grandes
    ...
},
"audio-normalization": {
    "max_file_size_mb": 200,  # Áudio normalizado
    ...
},
"audio-transcriber": {
    "max_file_size_mb": 100,  # Áudio final
    ...
}
```

---

## 📋 MÉDIOS (P2)

### 7. Polling interval fixo pode desperdiçar recursos
**Status:** OTIMIZAÇÃO 🟢  
**Prioridade:** P2 (Médio)  
**Descrição:** Polling usa intervalo fixo de 2s independente do tipo de job (vídeo curto vs longo).

**Impacto:**
- Jobs rápidos (<1min): polling a cada 2s é bom
- Jobs longos (>10min): polling a cada 2s desperdiça requisições

**Solução Implementada (Parcial):**
```python
# Polling adaptativo já existe!
if attempts < 10:
    poll_delay = self.poll_interval_initial  # 2s
elif attempts < 50:
    poll_delay = min(self.poll_interval_initial * 2, self.poll_interval_max)  # 4s
else:
    poll_delay = self.poll_interval_max  # 5s
```

**Melhoria Adicional:**
- Usar WebSocket/SSE do microserviço para push de atualizações
- Implementar long-polling no microserviço

---

### 8. Falta tratamento de disco cheio
**Status:** EDGE CASE 🟢  
**Prioridade:** P2 (Médio)  
**Descrição:** Se disco ficar cheio durante download/processamento, erro não é tratado graciosamente.

**Solução:**
```python
import shutil

def check_disk_space(path="/app/cache", required_mb=100):
    """Verifica espaço em disco antes de processar"""
    stat = shutil.disk_usage(path)
    free_mb = stat.free / (1024 * 1024)
    if free_mb < required_mb:
        raise RuntimeError(f"Insufficient disk space: {free_mb:.0f}MB < {required_mb}MB required")
    return free_mb
```

---

### 9. Retry exponential backoff pode ser muito lento
**Status:** CONFIGURAÇÃO 🟢  
**Prioridade:** P2 (Médio)  
**Descrição:** Backoff exponencial `2^attempt` pode resultar em delays muito longos (2s, 4s, 8s, 16s, 32s...).

**Cálculo Atual (5 attempts):**
- Attempt 1: delay 2s
- Attempt 2: delay 4s  
- Attempt 3: delay 8s
- Attempt 4: delay 16s
- Total: ~30s até falhar

**Solução:**
```python
delay = min(self.retry_delay * (2 ** attempt), 10)  # Cap em 10s
```

---

## 🔍 OBSERVAÇÕES

### Pontos Positivos do Código Atual:
✅ Circuit breaker implementado  
✅ Retry com exponential backoff  
✅ Health checks  
✅ Polling adaptativo  
✅ Validação de tamanho de arquivo  
✅ Logs estruturados  
✅ Timeouts configuráveis  
✅ Separação de concerns (client, orchestrator, models)

### Pontos de Atenção:
⚠️ Falta monitoramento de métricas (Prometheus/Grafana)  
⚠️ Falta tracing distribuído (OpenTelemetry)  
⚠️ Falta rate limiting  
⚠️ Falta autenticação entre serviços  
⚠️ Redis single point of failure (sem replicação)

---

## 📊 RESUMO POR PRIORIDADE

| Prioridade | Total | Resolvidos | Pendentes |
|------------|-------|------------|-----------|
| **P0 (Crítico)** | 3 | 1 ✅ | 2 ❌ |
| **P1 (Alto)** | 3 | 0 | 3 🟡 |
| **P2 (Médio)** | 3 | 0 | 3 🟢 |
| **TOTAL** | **9** | **1** | **8** |

---

## 🎯 PRÓXIMOS PASSOS (Prioridade)

1. ❌ **URGENTE:** Corrigir factory reset para limpar filas Celery (#2)
2. ❌ **URGENTE:** Investigar e resolver jobs parados (#3)
   - Adicionar logs verbosos no polling
   - Verificar integração FastAPI/Celery
   - Monitorar filas Redis em tempo real
3. 🟡 Melhorar circuit breaker com half-open state (#4)
4. 🟡 Adicionar response body nos logs de erro HTTP (#5)
5. 🟡 Configurar max file size por serviço (#6)

---

**Última Atualização:** 2025-10-30 02:00 BRT  
**Responsável:** GitHub Copilot + John Freitas  
**Versão:** 1.0
