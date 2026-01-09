# Sprints de Correção - Circuit Breaker & Comunicação

**Data:** 09/01/2026  
**Projeto:** YTCaption-Easy-Youtube-API  
**Objetivo:** Corrigir comunicação entre Orchestrator e Audio-Normalization

---

## RESUMO EXECUTIVO

Este documento detalha todas as sprints necessárias para corrigir o problema do circuit breaker que está bloqueando a comunicação entre orchestrator e audio-normalization.

**Prioridade:** CRÍTICA 🔴  
**Tempo Estimado Total:** 4-6 horas  
**Risco:** BAIXO (mudanças são backwards-compatible)

---

# SPRINT 1: CORREÇÃO CRÍTICA DE PAYLOAD (PRIORIDADE MÁXIMA)

**Objetivo:** Adicionar parâmetro `isolate_vocals` ao payload do orchestrator para compatibilidade total com audio-normalization.

**Tempo Estimado:** 30 minutos  
**Risco:** BAIXO  
**Impacto:** ALTO (resolve 80% do problema)

## Tarefas

### 1.1 Atualizar Modelo PipelineJob

**Arquivo:** `orchestrator/modules/models.py`

**Ação:** Adicionar campo `isolate_vocals` ao modelo

```python
# Adicionar no modelo PipelineJob:
isolate_vocals: Optional[bool] = False
```

**Validação:**
- ✅ Modelo aceita o novo campo
- ✅ Default é False (comportamento conservador)
- ✅ Compatível com jobs existentes

---

### 1.2 Atualizar Orchestrator - Envio de Payload

**Arquivo:** `orchestrator/modules/orchestrator.py`

**Ação:** Adicionar `isolate_vocals` no data enviado para audio-normalization

**Localização:** Função `_execute_normalization` (linha ~445)

```python
# ANTES:
data = {
    "remove_noise": _bool_to_str(...),
    "convert_to_mono": _bool_to_str(...),
    "apply_highpass_filter": _bool_to_str(...),
    "set_sample_rate_16k": _bool_to_str(...),
}

# DEPOIS:
data = {
    "remove_noise": _bool_to_str(...),
    "convert_to_mono": _bool_to_str(...),
    "apply_highpass_filter": _bool_to_str(...),
    "set_sample_rate_16k": _bool_to_str(...),
    "isolate_vocals": _bool_to_str(job.isolate_vocals if job.isolate_vocals is not None else defaults.get("isolate_vocals", False)),
}
```

**Validação:**
- ✅ Payload inclui todos os campos esperados
- ✅ Valores são strings "true"/"false"
- ✅ Default vem da configuração ou False

---

### 1.3 Atualizar Configuração - Default Parameters

**Arquivo:** `orchestrator/modules/config.py`

**Ação:** Adicionar `isolate_vocals` aos default params de audio-normalization

**Localização:** Função `get_microservice_config` (linha ~107)

```python
"audio-normalization": {
    # ...
    "default_params": {
        "remove_noise": settings["default_remove_noise"],
        "convert_to_mono": settings["default_convert_mono"],
        "set_sample_rate_16k": settings["default_sample_rate_16k"],
        "apply_highpass_filter": False,
        "isolate_vocals": False  # ADICIONAR ESTA LINHA
    }
}
```

**Validação:**
- ✅ Default configurável via variável de ambiente
- ✅ Valor padrão é False (operação rápida)

---

### 1.4 Adicionar Variável de Ambiente (Opcional)

**Arquivo:** `orchestrator/.env` ou docker-compose

**Ação:** Adicionar configuração para isolate_vocals

```bash
DEFAULT_ISOLATE_VOCALS=false
```

**Atualizar config.py:**

```python
"default_isolate_vocals": os.getenv("DEFAULT_ISOLATE_VOCALS", "false").lower() == "true",
```

**Validação:**
- ✅ Configurável sem alterar código
- ✅ Default seguro (False)

---

## Resultado Esperado Sprint 1

- ✅ Orchestrator envia payload completo
- ✅ Audio-normalization aceita requisições sem erro 422
- ✅ Circuit breaker começa a recuperar
- ⚠️ Ainda pode haver falhas se serviço estiver down/overloaded

---

# SPRINT 2: AJUSTE DE CIRCUIT BREAKER (ALTA PRIORIDADE)

**Objetivo:** Tornar circuit breaker menos sensível a falhas temporárias e melhorar resiliência.

**Tempo Estimado:** 45 minutos  
**Risco:** BAIXO  
**Impacto:** MÉDIO (previne bloqueios futuros)

## Tarefas

### 2.1 Separar Health Checks do Circuit Breaker

**Arquivo:** `orchestrator/modules/orchestrator.py`

**Problema Atual:** Health checks contam como falhas, o que é incorreto.

**Localização:** Método `check_health` (linha ~270-286)

```python
# ANTES:
async def check_health(self) -> bool:
    # ...
    except Exception as e:
        logger.error(f"Health check failed for {self.service_name}: {e}")
        self._record_failure()  # ❌ ERRADO: conta como falha operacional
        return False

# DEPOIS:
async def check_health(self) -> bool:
    # ...
    except Exception as e:
        logger.error(f"Health check failed for {self.service_name}: {e}")
        # ✅ CORRETO: health check não afeta circuit breaker
        # Apenas retorna status sem registrar falha
        return False
```

**Validação:**
- ✅ Health checks não disparam circuit breaker
- ✅ Circuit breaker só abre em falhas operacionais reais
- ✅ Logs ainda registram health check failures

---

### 2.2 Aumentar Threshold de Falhas

**Arquivo:** `orchestrator/modules/config.py`

**Ação:** Aumentar tolerância a falhas temporárias

```python
# ANTES:
"circuit_breaker_max_failures": 5,              # Muito sensível

# DEPOIS:
"circuit_breaker_max_failures": 10,             # Mais tolerante
```

**Justificativa:**
- Ambientes com latência de rede podem ter falhas ocasionais
- 5 falhas = ~15 segundos de problema já abre o circuit
- 10 falhas = ~30 segundos, mais razoável

**Validação:**
- ✅ Sistema tolera mais falhas temporárias
- ✅ Ainda protege contra falhas sistêmicas
- ⚠️ Aumenta tempo para detectar serviço realmente down

---

### 2.3 Ajustar Recovery Timeout

**Arquivo:** `orchestrator/modules/config.py`

**Ação:** Reduzir tempo de recovery para permitir tentativas mais rápidas

```python
# ANTES:
"circuit_breaker_recovery_timeout": 30,         # 30 segundos

# DEPOIS:
"circuit_breaker_recovery_timeout": 20,         # 20 segundos
```

**Justificativa:**
- Serviços podem recuperar rapidamente (restart, deploy)
- 20s é suficiente para evitar spam mas permite recovery rápido

**Validação:**
- ✅ Recovery mais ágil
- ✅ Não sobrecarrega serviço com tentativas
- ✅ Balance entre resiliência e performance

---

### 2.4 Aumentar Half-Open Requests

**Arquivo:** `orchestrator/modules/config.py`

**Ação:** Permitir mais tentativas no estado HALF_OPEN

```python
# ANTES:
"circuit_breaker_half_open_max_requests": 2,    # Apenas 2 tentativas

# DEPOIS:
"circuit_breaker_half_open_max_requests": 5,    # 5 tentativas para confirmar recovery
```

**Justificativa:**
- 2 tentativas podem falhar por acaso (latência)
- 5 tentativas dão mais confiança de que serviço recuperou

**Validação:**
- ✅ Recovery mais confiável
- ✅ Menos false positives (volta para OPEN prematuramente)

---

### 2.5 Adicionar Logging Detalhado de Circuit Breaker

**Arquivo:** `orchestrator/modules/orchestrator.py`

**Ação:** Melhorar visibilidade de transições de estado

**Localização:** Método `_is_circuit_open` (linha ~68)

```python
# Adicionar logs em todas as transições:

if self._circuit_state == "OPEN":
    if self.last_failure_time and datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
        logger.warning(f"[{self.service_name}] Circuit breaker transitioning OPEN → HALF_OPEN (recovery attempt after {self.recovery_timeout}s)")
        self._circuit_state = "HALF_OPEN"
        # ...

if self._circuit_state == "HALF_OPEN":
    if self._half_open_attempts >= self.half_open_max_requests:
        logger.error(f"[{self.service_name}] Circuit breaker HALF_OPEN → OPEN (recovery failed after {self._half_open_attempts} attempts)")
        # ...
```

**Validação:**
- ✅ Logs claros de todas as transições
- ✅ Timestamps para análise de timeline
- ✅ Facilita debug futuro

---

## Resultado Esperado Sprint 2

- ✅ Circuit breaker mais resiliente
- ✅ Menos false positives
- ✅ Recovery mais rápido e confiável
- ✅ Melhor observabilidade

---

# SPRINT 3: MELHORIA DE ERROR HANDLING (MÉDIA PRIORIDADE)

**Objetivo:** Capturar e logar erros detalhados para facilitar debug futuro.

**Tempo Estimado:** 1 hora  
**Risco:** MUITO BAIXO  
**Impacto:** MÉDIO (não resolve problema mas facilita diagnóstico)

## Tarefas

### 3.1 Adicionar Logging de Response Body em Erros

**Arquivo:** `orchestrator/modules/orchestrator.py`

**Ação:** Logar corpo da resposta em erros 4xx/5xx

**Localização:** Método `submit_multipart` (linha ~200-225)

```python
# ANTES:
except httpx.HTTPStatusError as e:
    if e.response.status_code == 400:
        raise RuntimeError(f"[{self.service_name}] Bad request - check file format or parameters: {e}")

# DEPOIS:
except httpx.HTTPStatusError as e:
    error_body = ""
    try:
        error_body = e.response.text
    except:
        pass
    
    if e.response.status_code == 400:
        logger.error(f"[{self.service_name}] Bad request (400): {error_body}")
        raise RuntimeError(f"[{self.service_name}] Bad request - check file format or parameters: {error_body[:200]}")
    elif e.response.status_code == 422:
        logger.error(f"[{self.service_name}] Validation error (422): {error_body}")
        raise RuntimeError(f"[{self.service_name}] Validation error - check payload: {error_body[:200]}")
```

**Validação:**
- ✅ Logs mostram exatamente qual campo falhou
- ✅ Easier to debug payload issues
- ✅ Não expõe informações sensíveis (trunca em 200 chars)

---

### 3.2 Adicionar Métricas de Circuit Breaker

**Arquivo:** `orchestrator/modules/orchestrator.py`

**Ação:** Expor métricas para monitoramento

```python
# Adicionar método para obter estado:
def get_circuit_breaker_state(self) -> Dict[str, Any]:
    """Retorna estado atual do circuit breaker para monitoramento"""
    return {
        "service": self.service_name,
        "state": self._circuit_state,
        "failure_count": self.failure_count,
        "max_failures": self.max_failures,
        "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
        "half_open_attempts": self._half_open_attempts if self._circuit_state == "HALF_OPEN" else 0,
        "recovery_timeout_sec": self.recovery_timeout
    }
```

**Uso:** Adicionar endpoint de métricas no orchestrator

```python
@app.get("/metrics/circuit-breaker")
async def get_circuit_breaker_metrics():
    return {
        "video-downloader": orchestrator.video_client.get_circuit_breaker_state(),
        "audio-normalization": orchestrator.audio_client.get_circuit_breaker_state(),
        "audio-transcriber": orchestrator.transcription_client.get_circuit_breaker_state()
    }
```

**Validação:**
- ✅ Visibilidade de estado de todos os services
- ✅ Pode ser monitorado por ferramentas externas
- ✅ Alertas podem ser configurados

---

### 3.3 Adicionar Retry com Jitter

**Arquivo:** `orchestrator/modules/orchestrator.py`

**Ação:** Adicionar jitter ao backoff para evitar thundering herd

**Localização:** Método `_retry_with_backoff` (linha ~145)

```python
import random

# ANTES:
delay = self.retry_delay * (2 ** attempt)

# DEPOIS:
base_delay = self.retry_delay * (2 ** attempt)
jitter = random.uniform(0, base_delay * 0.1)  # 10% jitter
delay = base_delay + jitter

logger.warning(f"[{self.service_name}] Attempt {attempt + 1}/{self.max_retries} failed with {status}, retrying in {delay:.1f}s...")
```

**Justificativa:**
- Evita que múltiplos orchestrators retentem ao mesmo tempo
- Distribui carga de retry

**Validação:**
- ✅ Retries distribuídos no tempo
- ✅ Menos chance de overload no recovery

---

## Resultado Esperado Sprint 3

- ✅ Logs muito mais informativos
- ✅ Debug facilitado
- ✅ Monitoramento do circuit breaker
- ✅ Retry mais inteligente

---

# SPRINT 4: VALIDAÇÃO E TESTES (ALTA PRIORIDADE)

**Objetivo:** Garantir que as mudanças funcionam e não quebram funcionalidade existente.

**Tempo Estimado:** 1.5 horas  
**Risco:** BAIXO  
**Impacto:** CRÍTICO (valida todas as mudanças)

## Tarefas

### 4.1 Teste Manual - Payload Completo

**Ação:** Testar envio de job com novo payload

```bash
# Do orchestrator, fazer request direto ao audio-normalization:
curl -X POST http://192.168.18.132:8001/jobs \
  -F "file=@test_audio.mp3" \
  -F "remove_noise=true" \
  -F "convert_to_mono=false" \
  -F "apply_highpass_filter=true" \
  -F "set_sample_rate_16k=false" \
  -F "isolate_vocals=false"
```

**Resultado Esperado:**
```json
{
  "id": "abc123",
  "status": "queued",
  "progress": 0.0,
  ...
}
```

**Validação:**
- ✅ Retorna 200 OK
- ✅ Job é criado e processado
- ⚠️ Se falhar, verificar logs do audio-normalization

---

### 4.2 Teste de Circuit Breaker - Recovery

**Ação:** Simular falha e verificar recovery

**Cenário:**
1. Parar audio-normalization
2. Tentar enviar job (deve falhar)
3. Verificar que circuit breaker abre após X falhas
4. Iniciar audio-normalization
5. Aguardar recovery_timeout
6. Verificar que circuit breaker tenta HALF_OPEN
7. Verificar que circuit breaker fecha após sucessos

**Validação:**
- ✅ Circuit breaker abre após falhas
- ✅ Circuit breaker tenta recovery automaticamente
- ✅ Circuit breaker fecha após recovery confirmado
- ✅ Logs mostram todas as transições

---

### 4.3 Teste de Pipeline Completo

**Ação:** Executar pipeline end-to-end

```python
# Via API do orchestrator:
POST /pipeline
{
  "youtube_url": "https://www.youtube.com/watch?v=test",
  "remove_noise": true,
  "convert_to_mono": true,
  "apply_highpass_filter": true,
  "set_sample_rate_16k": true,
  "isolate_vocals": false
}
```

**Resultado Esperado:**
- ✅ Download completa
- ✅ Normalization completa COM isolate_vocals=false
- ✅ Transcription completa
- ✅ Resultado final OK

**Validação:**
- ✅ Pipeline não quebra em nenhum stage
- ✅ Todos os parâmetros são passados corretamente
- ✅ Tempos de processamento razoáveis

---

### 4.4 Teste de Carga - Multiple Jobs

**Ação:** Enviar múltiplos jobs simultaneamente

```bash
for i in {1..10}; do
  curl -X POST http://orchestrator:8080/pipeline \
    -H "Content-Type: application/json" \
    -d '{"youtube_url": "https://youtube.com/watch?v=test'$i'"}' &
done
wait
```

**Validação:**
- ✅ Todos os jobs são processados
- ✅ Circuit breaker não abre indevidamente
- ✅ Sem deadlocks ou race conditions
- ⚠️ Monitorar uso de CPU/memória

---

### 4.5 Teste de Erros - Validation Errors

**Ação:** Tentar enviar payloads inválidos

```bash
# Teste 1: Sem file
curl -X POST http://192.168.18.132:8001/jobs \
  -F "remove_noise=true"

# Teste 2: Arquivo muito grande (> max_file_size_mb)
curl -X POST http://192.168.18.132:8001/jobs \
  -F "file=@huge_file.mp3" \
  -F "remove_noise=false" \
  -F "convert_to_mono=false" \
  -F "apply_highpass_filter=false" \
  -F "set_sample_rate_16k=false" \
  -F "isolate_vocals=false"

# Teste 3: Parâmetro inválido
curl -X POST http://192.168.18.132:8001/jobs \
  -F "file=@test.mp3" \
  -F "remove_noise=INVALID" \
  -F "convert_to_mono=false" \
  -F "apply_highpass_filter=false" \
  -F "set_sample_rate_16k=false" \
  -F "isolate_vocals=false"
```

**Resultado Esperado:**
- ✅ Retorna 400/422 com mensagem clara
- ✅ Circuit breaker NÃO abre (erros 4xx não contam)
- ✅ Logs mostram erro detalhado

**Validação:**
- ✅ Error handling funciona corretamente
- ✅ Não afeta circuit breaker
- ✅ Mensagens de erro são úteis

---

## Resultado Esperado Sprint 4

- ✅ Todas as mudanças validadas
- ✅ Nenhuma regressão
- ✅ Sistema resiliente a falhas
- ✅ Pronto para produção

---

# SPRINT 5: AUDIO-NORMALIZATION - MELHORIAS (BAIXA PRIORIDADE)

**Objetivo:** Melhorar robustez do audio-normalization para prevenir problemas futuros.

**Tempo Estimado:** 1 hora  
**Risco:** BAIXO  
**Impacto:** BAIXO (preventivo)

## Tarefas

### 5.1 Tornar isolate_vocals Opcional Explicitamente

**Arquivo:** `services/audio-normalization/app/main.py`

**Ação:** Garantir que campo é verdadeiramente opcional

```python
# ATUAL:
isolate_vocals: str = Form("false")

# MELHOR:
isolate_vocals: Optional[str] = Form(default="false")
```

**Justificativa:**
- Garante compatibilidade com todas as versões de FastAPI
- Explicitamente opcional

**Validação:**
- ✅ Endpoint aceita requests com ou sem isolate_vocals
- ✅ Default é "false" quando omitido
- ✅ FastAPI não gera erro de validação

---

### 5.2 Adicionar Validação de Parâmetros Booleanos

**Arquivo:** `services/audio-normalization/app/main.py`

**Ação:** Validar que strings são booleanos válidos

```python
def validate_bool_param(value: str, param_name: str) -> bool:
    """Valida e converte parâmetro string para bool"""
    if not isinstance(value, str):
        raise ValueError(f"{param_name} must be a string")
    
    value_lower = value.lower().strip()
    if value_lower in ('true', '1', 'yes', 'on'):
        return True
    elif value_lower in ('false', '0', 'no', 'off', ''):
        return False
    else:
        raise ValueError(f"{param_name} must be 'true' or 'false', got: {value}")

# Usar na função create_audio_job:
try:
    remove_noise_bool = validate_bool_param(remove_noise, "remove_noise")
    # ... (resto dos parâmetros)
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

**Validação:**
- ✅ Rejeita valores inválidos com erro claro
- ✅ Aceita formatos comuns (true, 1, yes, etc)
- ✅ Logs mostram qual parâmetro falhou

---

### 5.3 Adicionar Health Check para Celery

**Arquivo:** `services/audio-normalization/app/main.py`

**Ação:** Verificar se Celery workers estão disponíveis

```python
# No endpoint /health, adicionar:

# 4. Verifica Celery workers
try:
    from .celery_config import celery_app
    inspect = celery_app.control.inspect()
    active_workers = inspect.active()
    
    if active_workers and len(active_workers) > 0:
        health_status["checks"]["celery"] = {
            "status": "ok",
            "workers": len(active_workers),
            "worker_names": list(active_workers.keys())
        }
    else:
        health_status["checks"]["celery"] = {
            "status": "warning",
            "message": "No active workers found"
        }
        # Não marca como unhealthy, apenas warning
except Exception as e:
    health_status["checks"]["celery"] = {
        "status": "error",
        "message": str(e)
    }
    is_healthy = False
```

**Validação:**
- ✅ Health check detecta Celery down
- ✅ Orchestrator pode tomar decisões baseadas nisso
- ✅ Monitoramento mais preciso

---

### 5.4 Implementar Graceful Degradation

**Arquivo:** `services/audio-normalization/app/main.py`

**Ação:** Se Celery falhar, processar diretamente (já implementado parcialmente)

**Melhorar fallback existente:**

```python
def submit_processing_task(job: Job):
    """Submete job para processamento em background via Celery"""
    try:
        from .celery_config import celery_app
        from .celery_tasks import normalize_audio_task
        
        task_result = normalize_audio_task.apply_async(
            args=[job.model_dump()], 
            task_id=job.id
        )
        logger.info(f"📤 Job {job.id} enviado para Celery worker: {task_result.id}")
        return "celery"
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar job {job.id} para Celery: {e}")
        logger.warning(f"⚠️ Fallback ativo: processando job {job.id} diretamente (sem Celery)")
        
        # Fallback: processar diretamente em background task
        import asyncio
        asyncio.create_task(_process_job_direct(job))
        return "direct"

async def _process_job_direct(job: Job):
    """Processa job diretamente sem Celery (fallback)"""
    try:
        await processor.process_audio_job(job)
    except Exception as e:
        logger.error(f"Falha no processamento direto do job {job.id}: {e}")
        job.status = JobStatus.FAILED
        job.error_message = f"Direct processing failed: {str(e)}"
        job_store.update_job(job)
```

**Validação:**
- ✅ Serviço continua funcionando mesmo sem Celery
- ✅ Logs indicam modo de processamento (celery/direct)
- ⚠️ Performance pode ser reduzida no modo direct

---

## Resultado Esperado Sprint 5

- ✅ Audio-normalization mais robusto
- ✅ Melhor compatibilidade com orchestrator
- ✅ Graceful degradation funcional
- ✅ Health checks mais informativos

---

# SPRINT 6: DOCUMENTAÇÃO E MONITORAMENTO (BAIXA PRIORIDADE)

**Objetivo:** Documentar mudanças e configurar monitoramento.

**Tempo Estimado:** 45 minutos  
**Risco:** ZERO  
**Impacto:** BAIXO (qualidade de vida)

## Tarefas

### 6.1 Atualizar README do Orchestrator

**Arquivo:** `orchestrator/README.md`

**Ação:** Documentar configurações de circuit breaker

```markdown
## Circuit Breaker Configuration

O orchestrator implementa circuit breaker para proteger microserviços de sobrecarga:

### Variáveis de Ambiente

- `CIRCUIT_BREAKER_MAX_FAILURES` (default: 10): Número de falhas antes de abrir
- `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` (default: 20): Segundos antes de tentar recovery
- `CIRCUIT_BREAKER_HALF_OPEN_MAX_REQUESTS` (default: 5): Tentativas no estado HALF_OPEN

### Estados

- **CLOSED**: Normal operation
- **HALF_OPEN**: Testing recovery (limited requests)
- **OPEN**: Service unavailable (all requests rejected)

### Monitoramento

Check circuit breaker status:
```
GET /metrics/circuit-breaker
```

Returns status for all microservices.
```

---

### 6.2 Adicionar Alertas para Circuit Breaker

**Arquivo:** `orchestrator/modules/orchestrator.py`

**Ação:** Logar alertas críticos quando circuit breaker abre

```python
def _record_failure(self):
    """Registra falha - pode abrir circuit breaker"""
    self.last_failure_time = datetime.now()
    
    # ... código existente ...
    
    if self._circuit_state == "CLOSED":
        self.failure_count += 1
        if self.failure_count >= self.max_failures:
            self._circuit_state = "OPEN"
            # ADICIONAR: Alert crítico
            logger.critical(f"🚨 ALERT: Circuit breaker OPENED for {self.service_name} after {self.failure_count} failures")
            logger.critical(f"🚨 Service {self.service_name} is now UNAVAILABLE. Will retry in {self.recovery_timeout}s")
            # TODO: Enviar para sistema de alertas (Slack, PagerDuty, etc)
```

**Validação:**
- ✅ Logs CRITICAL são fáceis de detectar
- ✅ Pode ser integrado com sistemas de alerta
- 📧 Considerar envio de email/webhook

---

### 6.3 Criar Script de Diagnóstico

**Arquivo:** `scripts/diagnose_circuit_breaker.py`

**Ação:** Script para diagnosticar problemas de circuit breaker

```python
#!/usr/bin/env python3
"""
Script de diagnóstico de circuit breaker
Verifica conectividade e estado dos microserviços
"""

import requests
import sys

ORCHESTRATOR_URL = "http://localhost:8080"
SERVICES = {
    "audio-normalization": "http://192.168.18.132:8001",
    "video-downloader": "http://192.168.18.132:8000",
    "audio-transcriber": "http://192.168.18.132:8002"
}

def check_service(name, url):
    print(f"\n🔍 Checking {name}...")
    try:
        r = requests.get(f"{url}/health", timeout=5)
        if r.status_code == 200:
            print(f"✅ {name}: HEALTHY")
            return True
        else:
            print(f"⚠️ {name}: UNHEALTHY (status {r.status_code})")
            return False
    except Exception as e:
        print(f"❌ {name}: DOWN ({type(e).__name__})")
        return False

def check_circuit_breaker():
    print(f"\n🔍 Checking circuit breaker status...")
    try:
        r = requests.get(f"{ORCHESTRATOR_URL}/metrics/circuit-breaker", timeout=5)
        if r.status_code == 200:
            data = r.json()
            for service, state in data.items():
                status = state.get("state", "UNKNOWN")
                failures = state.get("failure_count", 0)
                print(f"  {service}: {status} (failures: {failures})")
        else:
            print(f"⚠️ Circuit breaker endpoint returned {r.status_code}")
    except Exception as e:
        print(f"❌ Cannot reach orchestrator: {e}")

def main():
    print("=" * 60)
    print("Circuit Breaker Diagnostic Tool")
    print("=" * 60)
    
    # Check all services
    results = {}
    for name, url in SERVICES.items():
        results[name] = check_service(name, url)
    
    # Check circuit breaker
    check_circuit_breaker()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    healthy_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"Services healthy: {healthy_count}/{total_count}")
    
    if healthy_count == total_count:
        print("✅ All services are healthy")
        sys.exit(0)
    else:
        print("❌ Some services are unhealthy")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Uso:**
```bash
chmod +x scripts/diagnose_circuit_breaker.py
./scripts/diagnose_circuit_breaker.py
```

**Validação:**
- ✅ Detecta serviços down
- ✅ Mostra estado do circuit breaker
- ✅ Exit code indica status (0=ok, 1=problem)

---

## Resultado Esperado Sprint 6

- ✅ Documentação atualizada
- ✅ Alertas configurados
- ✅ Ferramentas de diagnóstico disponíveis
- ✅ Manutenção facilitada

---

# CHECKLIST DE IMPLEMENTAÇÃO

## Pré-Implementação
- [ ] Fazer backup do código atual
- [ ] Criar branch de desenvolvimento
- [ ] Revisar ERRO.md para entender o problema
- [ ] Verificar que audio-normalization está rodando

## Sprint 1 - Payload (CRÍTICO)
- [ ] Adicionar `isolate_vocals` ao modelo PipelineJob
- [ ] Adicionar `isolate_vocals` ao payload em orchestrator.py
- [ ] Adicionar `isolate_vocals` aos default_params em config.py
- [ ] Adicionar variável de ambiente DEFAULT_ISOLATE_VOCALS
- [ ] Testar envio de payload manualmente

## Sprint 2 - Circuit Breaker (ALTO)
- [ ] Remover `_record_failure()` do método check_health
- [ ] Aumentar `circuit_breaker_max_failures` para 10
- [ ] Ajustar `circuit_breaker_recovery_timeout` para 20
- [ ] Aumentar `circuit_breaker_half_open_max_requests` para 5
- [ ] Adicionar logs detalhados de transições de estado
- [ ] Testar recovery após falha simulada

## Sprint 3 - Error Handling (MÉDIO)
- [ ] Adicionar logging de response body em erros
- [ ] Implementar método get_circuit_breaker_state
- [ ] Adicionar endpoint /metrics/circuit-breaker
- [ ] Adicionar jitter ao retry backoff
- [ ] Testar logging de erros

## Sprint 4 - Testes (CRÍTICO)
- [ ] Teste manual de payload completo
- [ ] Teste de circuit breaker recovery
- [ ] Teste de pipeline end-to-end
- [ ] Teste de carga com múltiplos jobs
- [ ] Teste de erros de validação

## Sprint 5 - Audio-Normalization (BAIXO)
- [ ] Tornar isolate_vocals Optional[str] explicitamente
- [ ] Adicionar validação de parâmetros booleanos
- [ ] Adicionar check de Celery no /health
- [ ] Melhorar fallback para processamento direto
- [ ] Testar graceful degradation

## Sprint 6 - Documentação (BAIXO)
- [ ] Atualizar README do orchestrator
- [ ] Adicionar alertas críticos no código
- [ ] Criar script de diagnóstico
- [ ] Testar script de diagnóstico

## Pós-Implementação
- [ ] Executar todos os testes da Sprint 4
- [ ] Revisar todos os logs em busca de warnings
- [ ] Fazer commit das mudanças
- [ ] Fazer push para repositório
- [ ] Monitorar logs por 24h
- [ ] Atualizar documentação de troubleshooting

---

# TIMELINE ESTIMADO

```
Dia 1 (4 horas):
├─ Sprint 1: Correção de Payload (30min) ✅ CRÍTICO
├─ Sprint 2: Circuit Breaker (45min) ✅ ALTO  
├─ Sprint 3: Error Handling (1h)
└─ Sprint 4: Testes (1.5h) ✅ CRÍTICO

Dia 2 (2 horas) - Opcional:
├─ Sprint 5: Audio-Normalization (1h)
└─ Sprint 6: Documentação (45min)
```

---

# RISCOS E MITIGAÇÕES

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Breaking changes em API | BAIXO | ALTO | Manter backwards compatibility, adicionar campos opcionais |
| Circuit breaker muito permissivo | MÉDIO | MÉDIO | Monitorar métricas, ajustar thresholds conforme necessário |
| Performance degradada | BAIXO | BAIXO | Jitter e retry são otimizações, não devem impactar negativamente |
| Celery fallback sobrecarregar | MÉDIO | BAIXO | Limitar jobs simultâneos em modo direct |

---

# CRITÉRIOS DE SUCESSO

## Must Have (Obrigatório)
- ✅ Circuit breaker não abre indevidamente
- ✅ Payload completo é enviado para audio-normalization
- ✅ Pipeline completo funciona sem erros
- ✅ Logs mostram transições de circuit breaker claramente

## Should Have (Desejável)
- ✅ Circuit breaker recupera automaticamente
- ✅ Erros 4xx não afetam circuit breaker
- ✅ Retry com jitter funciona
- ✅ Métricas de circuit breaker disponíveis

## Could Have (Opcional)
- ⚪ Alertas automáticos para circuit breaker OPEN
- ⚪ Script de diagnóstico funcional
- ⚪ Documentação atualizada
- ⚪ Graceful degradation no audio-normalization

---

**FIM DO DOCUMENTO**

Próximos passos:
1. Revisar e aprovar sprints
2. Fazer backup e criar branch
3. Implementar Sprint 1 (CRÍTICO)
4. Implementar Sprint 2 (ALTO)
5. Testar tudo (Sprint 4)
