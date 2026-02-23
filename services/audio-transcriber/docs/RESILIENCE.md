# 🛡️ Resilience - Sistema de Alta Resiliência

**Versão**: 1.0.0  
**Padrões**: Circuit Breaker, Checkpoints, Rate Limiting

---

## 📋 Visão Geral

O Audio Transcriber implementa **3 camadas de resiliência** para garantir alta disponibilidade:

1. **Circuit Breaker**: Protege contra falhas em cascata
2. **Checkpoint Manager**: Recuperação de falhas parciais
3. **Distributed Rate Limiter**: Controle de carga distribuído

---

## 🔴 Circuit Breaker

Protege o sistema contra falhas em cascata interrompendo chamadas a serviços que estão falhando.

### Estados

```
CLOSED → OPEN → HALF_OPEN → CLOSED
  ↑                           ↓
  └───────────────────────────┘
```

| Estado | Descrição | Comportamento |
|--------|-----------|---------------|
| **CLOSED** | Normal | Todas as requisições passam |
| **OPEN** | Falhando | Rejeita todas as requisições (fast-fail) |
| **HALF_OPEN** | Testando | Permite algumas requisições para testar |

### Configuração

```python
from app.infrastructure.circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,        # Falhas antes de abrir
    success_threshold=2,        # Sucessos para fechar
    timeout=60,                 # Segundos em OPEN
    half_open_max_calls=3       # Testes em HALF_OPEN
)
```

### Uso

```python
# Decorador
@breaker.call
def transcribe_audio(audio_path):
    return whisper_model.transcribe(audio_path)

# Context manager
with breaker:
    result = transcribe_audio("audio.mp3")

# Manual
if breaker.can_execute():
    try:
        result = transcribe_audio("audio.mp3")
        breaker.record_success()
    except Exception as e:
        breaker.record_failure()
        raise
```

### Métricas

```python
metrics = breaker.get_metrics()
# {
#   "state": "CLOSED",
#   "failure_count": 2,
#   "success_count": 150,
#   "total_calls": 152,
#   "error_rate": 0.013,
#   "last_failure_time": "2026-02-21T10:00:00Z"
# }
```

### Eventos

```python
# Callbacks
breaker.on_open = lambda: logger.warning("Circuit opened!")
breaker.on_close = lambda: logger.info("Circuit closed!")
breaker.on_half_open = lambda: logger.info("Circuit half-open")
```

---

## 💾 Checkpoint Manager

Salva progresso granular para recuperação de falhas.

### Conceito

```
Job: Transcrever áudio de 10 minutos

Sem Checkpoints:
[──────────────────] ❌ Falha aos 9 min → Recomeça do zero

Com Checkpoints:
[████──────────────] ✅ Checkpoint aos 4 min
                    ❌ Falha aos 6 min → Recomeça do checkpoint (4 min)
```

### Estrutura

```python
checkpoint = {
    "job_id": "abc123",
    "stage": "transcribing",          # normalize, validate, transcribe
    "progress": 0.45,                 # 0.0 - 1.0
    "segment_index": 15,              # Último segmento processado
    "partial_data": {
        "segments": [...],            # Segmentos já transcritos
        "metadata": {...}
    },
    "timestamp": "2026-02-21T10:05:00Z"
}
```

### Configuração

```python
from app.infrastructure.checkpoint_manager import CheckpointManager

checkpoint_mgr = CheckpointManager(
    redis_client=redis_client,
    checkpoint_interval=30,     # Salva a cada 30s
    ttl=86400,                  # TTL 24 horas
    max_checkpoints=10          # Mantém últimos 10
)
```

### Uso

```python
# Criar checkpoint
checkpoint_mgr.save_checkpoint(
    job_id="abc123",
    stage="transcribing",
    progress=0.45,
    data={"segments": [...]}
)

# Recuperar último checkpoint
checkpoint = checkpoint_mgr.get_latest_checkpoint("abc123")

if checkpoint:
    # Retomar do checkpoint
    segment_index = checkpoint["segment_index"]
    partial_segments = checkpoint["partial_data"]["segments"]
    
    # Continuar de onde parou
    continue_transcription(segment_index, partial_segments)
else:
    # Começar do zero
    start_transcription()

# Listar todos os checkpoints
checkpoints = checkpoint_mgr.list_checkpoints("abc123")
# [checkpoint3, checkpoint2, checkpoint1, ...]

# Limpar checkpoints antigos
checkpoint_mgr.cleanup_old_checkpoints("abc123")
```

### Granularidade

Checkpoints podem ser salvos em diferentes estágios:

```python
stages = {
    "upload": 0.10,       # 10% - Upload completo
    "normalize": 0.25,    # 25% - Normalização completa
    "validate": 0.35,     # 35% - Validação completa
    "transcribe_0.5": 0.60,  # 60% - 50% da transcrição
    "transcribe_1.0": 0.85,  # 85% - Transcrição completa
    "format": 1.0         # 100% - Formatação completa
}
```

### Recovery Automático

```python
def transcribe_with_recovery(job_id, audio_path):
    # Tentar recuperar checkpoint
    checkpoint = checkpoint_mgr.get_latest_checkpoint(job_id)
    
    if checkpoint:
        logger.info(f"Recovering from checkpoint at {checkpoint['progress']*100}%")
        start_index = checkpoint["segment_index"]
        partial_data = checkpoint["partial_data"]
    else:
        start_index = 0
        partial_data = None
    
    # Processar com checkpoints
    for i, segment in enumerate(audio_segments[start_index:], start=start_index):
        result = transcribe_segment(segment)
        
        # Salvar checkpoint a cada N segmentos
        if i % 5 == 0:
            checkpoint_mgr.save_checkpoint(
                job_id=job_id,
                stage="transcribing",
                progress=i / len(audio_segments),
                data={"segment_index": i, "segments": results}
            )
```

---

## ⏱️ Distributed Rate Limiter

Controla a taxa de requisições usando Redis e Sliding Window.

### Algoritmo

Sliding Window com Redis ZSET:

```
Janela de 1 hora:
[────────────────────────────────────] Max: 100 req/hora
 ^                                   ^
 t-1h                                t

Requests (sorted by timestamp):
ZSET: [req1:t1, req2:t2, ..., req100:t100]

Nova request:
1. Remove req com timestamp < (t - 1h)
2. Conta requests na janela
3. Se count < 100: ALLOW
4. Se count >= 100: DENY (retry after X seconds)
```

### Configuração

```python
from app.infrastructure.distributed_rate_limiter import DistributedRateLimiter

rate_limiter = DistributedRateLimiter(
    redis_client=redis_client,
    max_requests=100,          # Máximo de requests
    window_seconds=3600,       # Janela de 1 hora
    identifier="user:123"      # Identificador (user, IP, API key)
)
```

### Uso

```python
# Verificar e consumir
if rate_limiter.is_allowed():
    # Processar requisição
    result = process_transcription()
else:
    # Rejeitar
    retry_after = rate_limiter.get_retry_after()
    raise RateLimitError(f"Retry after {retry_after}s")

# Informações
info = rate_limiter.get_limit_info()
# {
#   "limit": 100,
#   "remaining": 45,
#   "reset_at": 1645432800,
#   "retry_after": 0
# }
```

### Rate Limits por Endpoint

```python
RATE_LIMITS = {
    "/transcribe": {
        "hourly": 100,
        "daily": 1000
    },
    "/status": {
        "hourly": 1000,
        "daily": 10000
    },
    "/result": {
        "hourly": 500,
        "daily": 5000
    }
}
```

### Middleware Flask

```python
from functools import wraps

def rate_limit(max_requests, window_seconds):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            identifier = get_client_identifier()  # IP, user_id, API key
            
            limiter = DistributedRateLimiter(
                redis_client=redis,
                max_requests=max_requests,
                window_seconds=window_seconds,
                identifier=identifier
            )
            
            if not limiter.is_allowed():
                info = limiter.get_limit_info()
                return jsonify({
                    "error": "Rate limit exceeded",
                    "limit": info["limit"],
                    "retry_after": info["retry_after"]
                }), 429
            
            return f(*args, **kwargs)
        return decorated
    return decorator

# Uso
@app.route('/transcribe', methods=['POST'])
@rate_limit(max_requests=100, window_seconds=3600)
def transcribe():
    ...
```

---

## 🔄 Integração Completa

Combinando todas as camadas de resiliência:

```python
from app.infrastructure import CircuitBreaker, CheckpointManager, DistributedRateLimiter

class ResilientTranscriptionService:
    def __init__(self, redis_client):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60
        )
        
        self.checkpoint_mgr = CheckpointManager(
            redis_client=redis_client,
            checkpoint_interval=30
        )
        
        self.rate_limiter = DistributedRateLimiter(
            redis_client=redis_client,
            max_requests=100,
            window_seconds=3600
        )
    
    def transcribe(self, job_id, audio_path, user_id):
        # 1. Rate Limiting
        if not self.rate_limiter.is_allowed(identifier=user_id):
            raise RateLimitError("Too many requests")
        
        # 2. Circuit Breaker
        if not self.circuit_breaker.can_execute():
            raise CircuitOpenError("Service temporarily unavailable")
        
        try:
            # 3. Checkpoint Recovery
            checkpoint = self.checkpoint_mgr.get_latest_checkpoint(job_id)
            
            if checkpoint:
                # Recuperar do checkpoint
                result = self._resume_from_checkpoint(job_id, checkpoint)
            else:
                # Começar do zero
                result = self._transcribe_from_start(job_id, audio_path)
            
            # Sucesso
            self.circuit_breaker.record_success()
            return result
            
        except Exception as e:
            # Falha
            self.circuit_breaker.record_failure()
            raise
    
    def _transcribe_from_start(self, job_id, audio_path):
        segments = load_audio_segments(audio_path)
        results = []
        
        for i, segment in enumerate(segments):
            # Processar segmento
            result = self.whisper_model.transcribe(segment)
            results.append(result)
            
            # Checkpoint a cada 5 segmentos
            if i % 5 == 0:
                self.checkpoint_mgr.save_checkpoint(
                    job_id=job_id,
                    stage="transcribing",
                    progress=i / len(segments),
                    data={"segment_index": i, "results": results}
                )
        
        return results
    
    def _resume_from_checkpoint(self, job_id, checkpoint):
        start_index = checkpoint["segment_index"]
        partial_results = checkpoint["partial_data"]["results"]
        
        # Continuar de onde parou
        segments = load_audio_segments(audio_path)
        
        for i, segment in enumerate(segments[start_index:], start=start_index):
            result = self.whisper_model.transcribe(segment)
            partial_results.append(result)
            
            if i % 5 == 0:
                self.checkpoint_mgr.save_checkpoint(
                    job_id=job_id,
                    stage="transcribing",
                    progress=i / len(segments),
                    data={"segment_index": i, "results": partial_results}
                )
        
        return partial_results
```

---

## 📊 Monitoramento

### Métricas Prometheus

```python
from prometheus_client import Counter, Gauge, Histogram

# Circuit Breaker
circuit_breaker_state = Gauge('circuit_breaker_state', 'Current state', ['service'])
circuit_breaker_failures = Counter('circuit_breaker_failures', 'Total failures', ['service'])

# Checkpoints
checkpoint_saves = Counter('checkpoint_saves', 'Total checkpoints saved')
checkpoint_recoveries = Counter('checkpoint_recoveries', 'Total recoveries from checkpoint')

# Rate Limiting
rate_limit_hits = Counter('rate_limit_hits', 'Total rate limit hits', ['endpoint'])
rate_limit_remaining = Gauge('rate_limit_remaining', 'Remaining requests', ['identifier'])
```

### Logs Estruturados

```python
logger.info("Circuit breaker opened", extra={
    "service": "whisper_transcription",
    "failure_count": 5,
    "error_rate": 0.15
})

logger.info("Checkpoint saved", extra={
    "job_id": "abc123",
    "stage": "transcribing",
    "progress": 0.45,
    "checkpoint_id": "ckpt_15"
})

logger.warning("Rate limit exceeded", extra={
    "identifier": "user:123",
    "limit": 100,
    "remaining": 0,
    "retry_after": 300
})
```

---

## 🧪 Testes de Resiliência

### Teste Circuit Breaker

```python
def test_circuit_breaker_opens_after_failures():
    breaker = CircuitBreaker(failure_threshold=3)
    
    # Simular 3 falhas
    for _ in range(3):
        with pytest.raises(Exception):
            with breaker:
                raise Exception("fail")
    
    # Circuit deve estar OPEN
    assert breaker.state == CircuitBreakerState.OPEN
    
    # Novas chamadas devem falhar imediatamente
    with pytest.raises(CircuitBreakerOpenError):
        with breaker:
            pass
```

### Teste Checkpoint Recovery

```python
def test_checkpoint_recovery():
    mgr = CheckpointManager(redis_client)
    
    # Simular job parando aos 50%
    mgr.save_checkpoint(
        job_id="job1",
        stage="transcribing",
        progress=0.5,
        data={"segments": [1, 2, 3, 4, 5]}
    )
    
    # Recuperar
    checkpoint = mgr.get_latest_checkpoint("job1")
    
    assert checkpoint["progress"] == 0.5
    assert len(checkpoint["partial_data"]["segments"]) == 5
```

### Teste Rate Limiting

```python
def test_rate_limit():
    limiter = DistributedRateLimiter(
        redis_client=redis,
        max_requests=5,
        window_seconds=60
    )
    
    # Fazer 5 requests (OK)
    for _ in range(5):
        assert limiter.is_allowed()
    
    # 6a request deve falhar
    assert not limiter.is_allowed()
    
    # Verificar retry_after
    assert limiter.get_retry_after() > 0
```

---

## 📚 Links Relacionados

- **[Infrastructure README](../app/infrastructure/README.md)** - Implementação completa
- **[Quickstart](QUICKSTART.md)** - Início rápido
- **[Testing Guide](TESTING.md)** - Testes de resiliência
