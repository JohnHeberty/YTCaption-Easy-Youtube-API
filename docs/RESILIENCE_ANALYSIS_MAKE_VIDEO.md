# 🔥 ANÁLISE DE RESILIÊNCIA - MAKE-VIDEO SERVICE

**Data**: 2026-02-28  
**Status**: 🚨 CRÍTICO - Sistema travado por loop infinito  
**Job Afetado**: GHKPgSBWpdBrtnySsa7gxR (travado há ~4 minutos)  
**Próximo na fila**: 4CBwM8mr7kBoeBGiuz4QTQ (aguardando desde 22:23:20)

---

## 🚨 PROBLEMA CRÍTICO IDENTIFICADO

### 1. **Loop Infinito no Retry de Legendas** (SEVERITY: CRITICAL)

**Arquivo**: `app/infrastructure/celery_tasks.py`  
**Linha**: 711-806

```python
# Etapa 6: Gerar legendas (RETRY INFINITO até conseguir)
logger.info(f"📝 [6/7] Generating subtitles...")
await update_job_status(job_id, JobStatus.GENERATING_SUBTITLES, progress=80.0)

segments = []
retry_attempt = 0
max_backoff = 300  # 5 minutos máximo entre tentativas

while not segments:  # ❌ LOOP INFINITO - SEM LIMITE DE TENTATIVAS!
    retry_attempt += 1
    
    try:
        if retry_attempt > 1:
            logger.info(f"🔄 Subtitle generation retry #{retry_attempt}")
        
        segments = await api_client.transcribe_audio(str(audio_path), job.subtitle_language)
        logger.info(f"✅ Subtitles generated: {len(segments)} segments (attempt #{retry_attempt})")
        
    except MicroserviceException as e:
        backoff_seconds = min(5 * (2 ** (retry_attempt - 1)), max_backoff)
        logger.warning(f"⚠️ Subtitle generation failed (attempt #{retry_attempt}): {e}")
        logger.info(f"🔄 Retrying in {backoff_seconds}s...")
        await asyncio.sleep(backoff_seconds)
        
    except Exception as e:
        backoff_seconds = min(5 * (2 ** (retry_attempt - 1)), max_backoff)
        logger.warning(f"⚠️ Unexpected error during subtitle generation (attempt #{retry_attempt}): {e}")
        await asyncio.sleep(backoff_seconds)
```

**Problema**:
- Loop `while not segments:` **nunca termina** se o audio-transcriber continua falhando
- Worker do Celery fica **100% ocupado** neste job
- **Nenhum outro job** pode ser processado (fila travada)
- Backoff exponencial eventualmente atinge 300s (5 minutos) entre tentativas
- Job GHKPgSBWpdBrtnySsa7gxR está travado fazendo tentativas 1, 2, 3, 4...∞

**Impacto**:
- 🔴 Sistema **INOPERANTE** - nenhum novo job é processado
- 🔴 Recursos desperdiçados (CPU, memória, conexões Redis/HTTP)
- 🔴 Jobs válidos ficam aguardando indefinidamente na fila
- 🔴 Usuários não recebem feedback de falha (job nunca falha, apenas tenta)

**Causa Raiz**:
O audio-transcriber está falhando com erro de import:
```
❌ Transcrição falhou: No module named 'app.services.models'
```

---

## 🐛 PROBLEMAS ADICIONAIS DE RESILIÊNCIA

### 2. **Ausência de Timeout no Task do Celery** (SEVERITY: HIGH)

**Arquivo**: `app/infrastructure/celery_tasks.py`  
**Linha**: 320

```python
@celery_app.task(bind=True, name='app.infrastructure.celery_tasks.process_make_video')
def process_make_video(self, job_id: str):
```

**Problemas**:
- ❌ Sem `time_limit` - task pode rodar indefinidamente
- ❌ Sem `soft_time_limit` - não há aviso antes do timeout
- ❌ Sem `acks_late` - task pode ser perdida se worker crashar

**Recomendação**:
```python
@celery_app.task(
    bind=True,
    name='app.infrastructure.celery_tasks.process_make_video',
    time_limit=3600,        # 1 hora hard limit
    soft_time_limit=3300,   # 55 minutos warning
    acks_late=True,         # ACK após completar (não antes)
    reject_on_worker_lost=True
)
```

---

### 3. **Falta de Circuit Breaker** (SEVERITY: MEDIUM)

**Problema**:
- Quando audio-transcriber está falhando **consistentemente**, o sistema continua tentando
- Não há detecção de "serviço em modo de falha"
- Deveria falhar rápido após detectar padrão de falhas

**Recomendação**:
Implementar circuit breaker pattern:
- Após N falhas consecutivas → abrir circuito
- Enquanto circuito aberto → falhar fast sem tentar
- Após timeout → tentar uma request (half-open)
- Se sucesso → fechar circuito

---

### 4. **Falta de Dead Letter Queue** (SEVERITY: MEDIUM)

**Problema**:
- Jobs que falharam múltiplas vezes não têm tratamento especial
- Deveria haver uma fila separada para jobs "mortos"
- Permite análise posterior sem bloquear processamento

**Recomendação**:
```python
# No celery_config.py
task_routes = {
    'app.infrastructure.celery_tasks.process_make_video': {
        'queue': 'make_video_queue',
        'routing_key': 'make_video',
        'priority': 5
    },
    'dead_letter_tasks': {
        'queue': 'dead_letter_queue',
        'routing_key': 'dead_letter'
    }
}
```

---

### 5. **Polling Infinito no Audio Transcriber** (SEVERITY: MEDIUM)

**Arquivo**: `app/api/api_client.py`  
**Linhas**: 356-445

```python
# Poll transcription status
max_polls = 10
poll_interval = 30  # seconds

for attempt in range(1, max_polls + 1):
    try:
        response = await self.client.get(f"{self.audio_transcriber_url}/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        
        status = job.get("status", "unknown")
        
        if status == "completed":
            # Buscar resultado...
            return segments
        
        elif status == "failed":
            error_msg = job.get("error_message", "Unknown error")
            logger.error(f"❌ Transcrição falhou: {error_msg}")
            raise TranscriberUnavailableException(...)
        
    except httpx.HTTPError as e:
        logger.warning(f"⚠️ Polling error (attempt {attempt}/{max_polls}): {e}")
        if attempt >= max_polls:
            raise
    
    # Aguardar próximo poll
    if attempt < max_polls:
        await asyncio.sleep(poll_interval)

# Timeout após max_polls
raise TranscriptionTimeoutException(...)
```

**Problema**:
- Esse polling tem limite (`max_polls=10`), **MAS**...
- É chamado dentro do loop infinito `while not segments:`
- Então mesmo com timeout aqui, **o loop externo continua tentando**

---

### 6. **Falta de Monitoramento de Health do Worker** (SEVERITY: LOW)

**Problema**:
- Não há probes para detectar worker travado
- Kubernetes/Docker Compose não sabe que worker está inoperante
- Deveria haver liveness/readiness checks

**Recomendação**:
```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD-SHELL", "celery -A app.infrastructure.celery_config inspect ping"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

### 7. **Exceções Genéricas Capturadas** (SEVERITY: LOW)

**Arquivo**: `app/infrastructure/celery_tasks.py`  
**Múltiplas linhas**

```python
except Exception as e:
    # Captura QUALQUER exceção, incluindo KeyboardInterrupt, SystemExit, etc.
    ...
```

**Problema**:
- Não deveria capturar `BaseException` subclasses
- Pode ocultar sinais de shutdown graceful
- Dificulta debugging

**Recomendação**:
```python
except (MicroserviceException, AudioProcessingException) as e:
    # Capturar apenas exceções esperadas
    ...
except Exception as e:
    # Log e re-raise exceções inesperadas
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

---

## 📊 EVIDÊNCIAS DOS LOGS

### Logs do make-video-celery (travado):

```
[2026-02-28 22:21:55,010: ERROR/MainProcess] ❌ Transcrição falhou: No module named 'app.services.models'
[2026-02-28 22:21:55,010: WARNING/MainProcess] ⚠️ Subtitle generation failed (attempt #1): ...
[2026-02-28 22:21:55,010: INFO/MainProcess] 🔄 Retrying in 5s...

[2026-02-28 22:22:52,363: ERROR/MainProcess] ❌ Transcrição falhou: No module named 'app.services.models'
[2026-02-28 22:22:52,363: WARNING/MainProcess] ⚠️ Subtitle generation failed (attempt #2): ...
[2026-02-28 22:22:52,363: INFO/MainProcess] 🔄 Retrying in 10s...

[2026-02-28 22:23:46,530: ERROR/MainProcess] ❌ Transcrição falhou: No module named 'app.services.models'
[2026-02-28 22:23:46,530: WARNING/MainProcess] ⚠️ Subtitle generation failed (attempt #3): ...
[2026-02-28 22:23:46,530: INFO/MainProcess] 🔄 Retrying in 20s...

[2026-02-28 22:25:56,759: ERROR/MainProcess] ❌ Transcrição falhou: No module named 'app.services.models'

[2026-02-28 22:27:15,266: ERROR/MainProcess] ❌ Transcrição falhou: No module named 'app.services.models'
```

**Padrão observado**:
- Tentativas continuam indefinidamente
- Backoff: 5s → 10s → 20s → 40s → 80s → 160s → 300s (max) → 300s → ...
- Job GHKPgSBWpdBrtnySsa7gxR monopolizando o worker

### Job na fila (starving):

```json
{
  "id": null,
  "video_id": null,
  "status": "queued",
  "created_at": "2026-02-28T22:23:20.287850-03:00",
  "updated_at": "2026-02-28T22:23:20.287950-03:00",
  "error": null
}
```

Job `4CBwM8mr7kBoeBGiuz4QTQ` aguardando há **~4 minutos** sem ser processado.

---

## ✅ CORREÇÕES NECESSÁRIAS

### PRIORIDADE 1 - URGENTE (Sistema travado)

1. **Adicionar limite máximo de retries no loop de legendas**
   ```python
   MAX_SUBTITLE_RETRIES = 5  # Limite razoável
   retry_attempt = 0
   
   while not segments and retry_attempt < MAX_SUBTITLE_RETRIES:
       retry_attempt += 1
       ...
   
   if not segments:
       raise SubtitleGenerationException(
           reason=f"Failed to generate subtitles after {MAX_SUBTITLE_RETRIES} attempts",
           ...
       )
   ```

2. **Adicionar timeout no task do Celery**

3. **Restart do worker travado** (imediato)
   ```bash
   docker compose restart ytcaption-make-video-celery
   ```

### PRIORIDADE 2 - IMPORTANTE (Prevenção)

4. **Implementar circuit breaker para audio-transcriber**
5. **Adicionar health checks nos workers**
6. **Configurar dead letter queue**

### PRIORIDADE 3 - MELHORIA (Qualidade)

7. **Refinar captura de exceções**
8. **Adicionar métricas de resiliência** (Prometheus)
9. **Implementar graceful degradation**

---

## 🔧 SOLUÇÃO IMEDIATA PARA DESTRAVAR

```bash
# 1. Matar o worker travado
docker compose -f services/make-video/docker-compose.yml restart ytcaption-make-video-celery

# 2. Ver fila de jobs pendentes  
curl -s http://localhost:8005/jobs | jq '.jobs[] | select(.status == "queued") | {id, created_at}'

# 3. Monitorar processamento
docker logs -f ytcaption-make-video-celery
```

---

**Autor**: Sistema de Análise de Resiliência  
**Próxima ação**: Implementar correções PRIORIDADE 1
