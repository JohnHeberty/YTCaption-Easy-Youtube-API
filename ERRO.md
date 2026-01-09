# Relatório de Análise de Erro - Circuit Breaker OPEN

**Data:** 09/01/2026  
**Serviço:** Orchestrator → Audio-Normalization  
**Erro:** `[audio-normalization] Failed to submit multipart: [audio-normalization] Circuit breaker is OPEN - service unavailable`

---

## 1. RESUMO EXECUTIVO

O orchestrator está falhando ao se comunicar com o serviço de audio-normalization devido ao circuit breaker estar no estado OPEN. Isso impede o envio de requisições multipart para normalização de áudio, bloqueando completamente o pipeline de processamento.

### Criticidade
- **Nível:** CRÍTICO 🔴
- **Impacto:** Pipeline completamente interrompido
- **Serviço Afetado:** audio-normalization
- **Status Atual:** Circuit Breaker OPEN (serviço indisponível para o orchestrator)

---

## 2. ANÁLISE DO CIRCUIT BREAKER

### 2.1 Configuração Atual

**Orchestrator (config.py):**
```python
"circuit_breaker_max_failures": 5,              # Abre após 5 falhas consecutivas
"circuit_breaker_recovery_timeout": 30,          # 30 segundos para tentar recovery
"circuit_breaker_half_open_max_requests": 2,     # 2 tentativas no estado HALF_OPEN
```

**Estados do Circuit Breaker:**
- `CLOSED`: Funcionamento normal, todas as requisições passam
- `HALF_OPEN`: Teste de recuperação, permite tentativas limitadas
- `OPEN`: Bloqueado, rejeita todas as requisições imediatamente

### 2.2 Comportamento Observado

1. **Falhas Acumuladas:** O orchestrator registrou 5 ou mais falhas consecutivas ao tentar comunicar com audio-normalization
2. **Circuit Breaker Acionado:** Após 5 falhas, o circuit breaker mudou para estado OPEN
3. **Bloqueio de Requisições:** Todas as novas tentativas são rejeitadas imediatamente com erro "Circuit breaker is OPEN"
4. **Recovery Timeout:** Após 30 segundos, tenta estado HALF_OPEN
5. **Falha no Half-Open:** Se as 2 tentativas no HALF_OPEN falharem, volta para OPEN

---

## 3. CAUSAS RAIZ IDENTIFICADAS

### 3.1 CAUSA PRINCIPAL: Desalinhamento de Endpoints

**Problema:** O orchestrator pode estar enviando requisições para endpoints incorretos ou com formato de payload incompatível.

**Evidências:**
```python
# Orchestrator espera (orchestrator.py:445):
POST /jobs com multipart/form-data:
- file: (filename, bytes, content-type)
- data: {
    "remove_noise": "true"/"false",
    "convert_to_mono": "true"/"false",
    "apply_highpass_filter": "true"/"false",
    "set_sample_rate_16k": "true"/"false"
  }

# Audio-normalization aceita (main.py:107):
POST /jobs com multipart/form-data:
- file: UploadFile
- remove_noise: Form("false")
- convert_to_mono: Form("false")
- apply_highpass_filter: Form("false")
- set_sample_rate_16k: Form("false")
- isolate_vocals: Form("false")  # ⚠️ PARÂMETRO EXTRA NÃO ENVIADO PELO ORCHESTRATOR
```

**Impacto:** O audio-normalization pode estar retornando 422 (validation error) porque o orchestrator não envia o parâmetro `isolate_vocals`.

### 3.2 CAUSA SECUNDÁRIA: Timeout Inadequado

**Problema:** Timeout de HTTP muito baixo para operações que envolvem processamento pesado.

**Evidências:**
```python
# Orchestrator (config.py:44):
"audio_normalization_timeout": 300,  # 5 minutos apenas para HTTP

# Audio-normalization pode levar:
- Celery task_time_limit: 1800s (30 minutos)
- Job timeout: 3600s (60 minutos)
```

**Impacto:** O orchestrator pode estar desistindo antes do audio-normalization começar a processar, causando timeouts consecutivos que abrem o circuit breaker.

### 3.3 CAUSA TERCIÁRIA: Health Check Agressivo

**Problema:** Health checks falhando podem estar contando como falhas no circuit breaker.

**Código Atual (orchestrator.py:283-286):**
```python
def check_health(self) -> bool:
    # ...
    else:
        logger.warning(f"Health check for {self.service_name} returned status {r.status_code}")
    return healthy
except Exception as e:
    logger.error(f"Health check failed for {self.service_name}: {e}")
    self._record_failure()  # ⚠️ Health check conta como falha!
    return False
```

**Impacto:** Se o audio-normalization estiver temporariamente lento ou ocupado, health checks podem falhar e acumular contadores de falha rapidamente.

### 3.4 CAUSA QUATERNÁRIA: Falta de Retry Adequado

**Problema:** O circuit breaker está muito sensível a falhas temporárias.

**Configuração Atual:**
```python
"microservice_max_retries": 3,       # Apenas 3 tentativas
"microservice_retry_delay": 2,       # 2 segundos base
# Backoff exponencial: 2s, 4s, 8s = total ~14s
```

**Impacto:** Para serviços que estão processando e temporariamente lentos, 3 retries em 14 segundos não são suficientes. Se 2 requisições consecutivas falharem assim, o circuit breaker já acumula muitas falhas.

---

## 4. FLUXO DE FALHA DETALHADO

```
┌─────────────────────────────────────────────────────────────────┐
│ SEQUÊNCIA DE EVENTOS QUE LEVAM AO CIRCUIT BREAKER OPEN         │
└─────────────────────────────────────────────────────────────────┘

1. Orchestrator recebe job de pipeline
   └─> Inicia stage de normalização

2. Orchestrator tenta submit_multipart para audio-normalization
   └─> Envia POST /jobs com file + data
   
3. Audio-normalization valida payload
   └─> ⚠️ FALHA: Parâmetro "isolate_vocals" ausente → 422 Validation Error
   OR
   └─> ⚠️ FALHA: Timeout após 5 minutos → httpx.TimeoutException
   
4. Orchestrator registra falha
   └─> failure_count++ (agora = 1)
   └─> Faz retry com backoff exponencial
   
5. Retry #1 (após 2s)
   └─> ⚠️ FALHA novamente (mesmo problema)
   └─> failure_count++ (agora = 2)
   
6. Retry #2 (após 4s)
   └─> ⚠️ FALHA novamente
   └─> failure_count++ (agora = 3)
   
7. Retry #3 (após 8s)
   └─> ⚠️ FALHA novamente
   └─> failure_count++ (agora = 4)
   └─> Todas as tentativas esgotadas, raise RuntimeError
   
8. Pipeline tenta próximo job
   └─> Tenta submit_multipart novamente
   └─> ⚠️ FALHA imediatamente
   └─> failure_count++ (agora = 5)
   
9. ⚠️ CIRCUIT BREAKER ACIONADO
   └─> Circuit state: CLOSED → OPEN
   └─> last_failure_time = now()
   └─> Log: "Circuit breaker OPENED after 5 consecutive failures"
   
10. Próximas tentativas de qualquer job
    └─> _is_circuit_open() = True
    └─> Raise RuntimeError: "Circuit breaker is OPEN - service unavailable"
    └─> ❌ PIPELINE COMPLETAMENTE BLOQUEADO
```

---

## 5. ANÁLISE DE ENDPOINTS

### 5.1 Endpoint de Submissão

**Orchestrator envia:**
```python
POST http://192.168.18.132:8001/jobs
Content-Type: multipart/form-data

files = {
    "file": (audio_name, audio_bytes, "application/octet-stream")
}
data = {
    "remove_noise": "true",
    "convert_to_mono": "false",
    "apply_highpass_filter": "true",
    "set_sample_rate_16k": "false"
}
```

**Audio-normalization espera:**
```python
@app.post("/jobs", response_model=Job)
async def create_audio_job(
    file: UploadFile = File(...),
    remove_noise: str = Form("false"),
    convert_to_mono: str = Form("false"),
    apply_highpass_filter: str = Form("false"),
    set_sample_rate_16k: str = Form("false"),
    isolate_vocals: str = Form("false")  # ⚠️ FALTANDO NO ORCHESTRATOR
)
```

**🔴 PROBLEMA CRÍTICO:** O orchestrator NÃO envia `isolate_vocals`, mas o audio-normalization o define como campo obrigatório (mesmo com default). Dependendo da versão do FastAPI, isso pode causar 422.

### 5.2 Endpoint de Status

**Orchestrator consulta:**
```python
GET http://192.168.18.132:8001/jobs/{job_id}
```

**Audio-normalization responde:**
```python
{
    "id": "string",
    "status": "queued|processing|completed|failed",
    "progress": 0.0-100.0,
    "error_message": "string",
    ...
}
```

**Status:** ✅ COMPATÍVEL

### 5.3 Endpoint de Download

**Orchestrator baixa:**
```python
GET http://192.168.18.132:8001/jobs/{job_id}/download
```

**Audio-normalization retorna:**
```python
FileResponse com Content-Disposition
```

**Status:** ✅ COMPATÍVEL

---

## 6. ANÁLISE DE TIMEOUT

### 6.1 Timeouts Configurados

| Serviço | HTTP Timeout | Job Timeout | Celery Task Limit |
|---------|-------------|-------------|-------------------|
| Orchestrator → Audio-Norm | 300s (5min) | 3600s (60min) | N/A |
| Audio-Normalization | N/A | 3600s (60min) | 1800s (30min) |

### 6.2 Cenário de Timeout

```
T=0s    : Orchestrator envia POST /jobs
T=0.5s  : Audio-normalization recebe, valida, cria job, envia para Celery
T=1s    : Audio-normalization retorna 200 OK com job_id
T=1s    : Orchestrator recebe response, inicia polling
T=2-300s: Orchestrator faz polling GET /jobs/{id} a cada 1-20s
          Audio-normalization responde com status="processing", progress=10-90%
T=300s  : ⚠️ TIMEOUT! Orchestrator desiste do polling? NÃO!
          Polling continua até max_poll_attempts (720) ou job timeout (3600s)
```

**Análise:** O HTTP timeout de 300s é para a requisição HTTP inicial (POST /jobs), NÃO para o polling. O polling usa seu próprio timeout baseado em `max_poll_attempts` e `job_timeout`. Portanto, timeout não é a causa direta do circuit breaker.

**CORREÇÃO:** O timeout de 300s é adequado para a submissão inicial. O problema está em outro lugar.

---

## 7. ANÁLISE DE REDE E CONECTIVIDADE

### 7.1 Configuração de Rede

```python
# Orchestrator
"audio_normalization_url": "http://192.168.18.132:8001"

# Audio-normalization
"host": "0.0.0.0"
"port": 8001
```

### 7.2 Possíveis Problemas de Rede

1. **Firewall/Iptables:** Porta 8001 pode estar bloqueada
2. **Docker Network:** Se em containers, pode haver isolamento de rede
3. **DNS:** IP pode estar incorreto ou mudou
4. **Carga Alta:** Serviço pode estar rejeitando conexões (503)

**Diagnóstico Necessário:**
```bash
# Do container/host do orchestrator:
curl -v http://192.168.18.132:8001/health
curl -X POST http://192.168.18.132:8001/jobs \
  -F "file=@test.mp3" \
  -F "remove_noise=false" \
  -F "convert_to_mono=false" \
  -F "apply_highpass_filter=false" \
  -F "set_sample_rate_16k=false" \
  -F "isolate_vocals=false"
```

---

## 8. ESTADO ATUAL DO SERVIÇO

### 8.1 Possíveis Estados do Audio-Normalization

| Estado | Sintoma | Causa Provável |
|--------|---------|----------------|
| 🔴 Down | Health check falha, conexão recusada | Serviço não está rodando |
| 🟡 Overloaded | Health check OK, mas POST /jobs falha com 503/504 | Muitos jobs, CPU/memória saturada |
| 🟡 Partial | Health check OK, POST /jobs retorna 422 | Validação de payload falhando |
| 🟢 Healthy | Health check OK, POST /jobs retorna 200 | Funcionando normalmente |

### 8.2 Logs Esperados no Audio-Normalization

Se o serviço está recebendo requisições mas falhando:

```
ERROR: Validation error: Field required: isolate_vocals
OR
ERROR: Timeout reading request body
OR  
ERROR: Redis connection failed
OR
ERROR: Celery worker not available
```

---

## 9. DIAGNÓSTICO DE FALHA NO CIRCUIT BREAKER

### 9.1 Cenário 1: Validação de Payload (MAIS PROVÁVEL)

**Hipótese:** Audio-normalization rejeita payload porque `isolate_vocals` está ausente.

**Evidência:**
- Orchestrator não envia `isolate_vocals`
- FastAPI pode interpretar campo obrigatório mesmo com default

**Prova:**
```python
# Se FastAPI 0.100+, Form com default é opcional
# Se FastAPI 0.68-0.99, pode ser obrigatório
isolate_vocals: str = Form("false")  # Comportamento varia por versão
```

**Solução:** Adicionar `isolate_vocals` no orchestrator.

### 9.2 Cenário 2: Serviço Indisponível

**Hipótese:** Audio-normalization não está rodando ou não está acessível.

**Evidência:**
- Health checks falhando consecutivamente
- ConnectError ou ConnectionRefused

**Prova:**
```bash
curl http://192.168.18.132:8001/health
# Se retornar erro de conexão = serviço down
```

**Solução:** Reiniciar serviço, verificar logs, verificar rede.

### 9.3 Cenário 3: Overload

**Hipótese:** Audio-normalization está sobrecarregado e rejeitando conexões.

**Evidência:**
- Health check OK mas POST /jobs falha com 503
- Muitos jobs em processamento simultâneo

**Prova:**
```bash
curl http://192.168.18.132:8001/health
# Verificar "checks.celery" e "checks.disk_space"
```

**Solução:** Escalar workers, aumentar recursos, limpar jobs órfãos.

---

## 10. ANÁLISE DE CÓDIGO CRÍTICO

### 10.1 Trecho Problemático do Orchestrator

```python
# orchestrator/modules/orchestrator.py:445-456
async def _execute_normalization(self, job: PipelineJob, audio_bytes: bytes, audio_name: str):
    files = {
        "file": (audio_name, audio_bytes, "application/octet-stream")
    }
    data = {
        "remove_noise": _bool_to_str(...),
        "convert_to_mono": _bool_to_str(...),
        "apply_highpass_filter": _bool_to_str(...),
        "set_sample_rate_16k": _bool_to_str(...),
        # ⚠️ FALTA: "isolate_vocals": "false"
    }
    resp = await self.audio_client.submit_multipart(files=files, data=data)
```

### 10.2 Trecho do Audio-Normalization

```python
# services/audio-normalization/app/main.py:107-117
@app.post("/jobs", response_model=Job)
async def create_audio_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    remove_noise: str = Form("false"),
    convert_to_mono: str = Form("false"),
    apply_highpass_filter: str = Form("false"),
    set_sample_rate_16k: str = Form("false"),
    isolate_vocals: str = Form("false")  # ⚠️ Este campo não é enviado
) -> Job:
```

---

## 11. IMPACTO NO SISTEMA

### 11.1 Efeitos Imediatos

- ❌ **Pipeline Bloqueado:** Nenhum job consegue processar áudio
- ❌ **Acúmulo de Jobs:** Jobs ficam em estado QUEUED no orchestrator
- ❌ **Timeout de Usuários:** Requisições de usuários ficam pendentes
- ⚠️ **Cascata de Falhas:** Se outros serviços dependem de normalization, também falham

### 11.2 Efeitos de Longo Prazo

- 📈 **Crescimento de Fila:** Redis acumula jobs pending
- 💾 **Uso de Disco:** Arquivos temporários não são limpos
- 🔥 **Sobrecarga de Memória:** Jobs órfãos ocupam memória
- 🚨 **Indisponibilidade Total:** Sistema inutilizável

---

## 12. CONCLUSÕES

### 12.1 Causa Raiz PRINCIPAL

**INCOMPATIBILIDADE DE PAYLOAD:** O orchestrator não está enviando o parâmetro `isolate_vocals` que o audio-normalization espera (ou que FastAPI interpreta como obrigatório).

### 12.2 Causas Raiz SECUNDÁRIAS

1. **Circuit Breaker Muito Sensível:** 5 falhas é muito pouco para ambientes com latência de rede
2. **Health Checks Afetando Circuit Breaker:** Health checks não deveriam contar como falhas operacionais
3. **Falta de Logging Detalhado:** Não há logs claros sobre qual exatamente é o erro 4xx retornado

### 12.3 Recomendações CRÍTICAS

1. ✅ **Adicionar `isolate_vocals` no payload do orchestrator**
2. ✅ **Aumentar `circuit_breaker_max_failures` de 5 para 10-15**
3. ✅ **Remover health checks do contador de falhas do circuit breaker**
4. ✅ **Adicionar logging detalhado de erros 4xx no orchestrator**
5. ✅ **Implementar fallback quando circuit breaker abre (notificar admin, retry manual)**

---

## 13. PRÓXIMOS PASSOS

Ver documento **SPRINTS.md** para plano de ação detalhado.

---

**Fim do Relatório**
