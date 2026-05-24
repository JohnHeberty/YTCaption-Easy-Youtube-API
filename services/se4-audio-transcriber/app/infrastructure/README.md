# 🏗️ Infrastructure - Audio Transcriber Service

Componentes de infraestrutura para alta resiliência e disponibilidade.

Adaptados dos padrões de produção do **make-video service**.

---

## 📦 Componentes

### 1. Circuit Breaker

**Propósito**: Proteger serviços externos de falhas em cascata.

**Estados**:
- `CLOSED`: Normal, permite todas as chamadas
- `OPEN`: Bloqueado após threshold de falhas
- `HALF_OPEN`: Testando recuperação

**Use cases**:
- Download de models (HuggingFace)
- GPU operations (OOM protection)
- Audio file processing failures
- Whisper engine crashes

**Exemplo**:

```python
from app.infrastructure import get_circuit_breaker

cb = get_circuit_breaker()

# Proteger operação
try:
    result = cb.call(
        service="faster_whisper_load",
        func=model.load_model,
        model_size="base"
    )
except CircuitBreakerException:
    # Circuito aberto, serviço indisponível
    fallback_action()
```

**Configuração**:
```python
CircuitBreaker(
    failure_threshold=5,  # Abrir após 5 falhas
    timeout=60,  # Testar recuperação após 60s
    half_open_max_calls=3  # Permitir 3 chamadas em HALF_OPEN
)
```

---

### 2. Checkpoint Manager

**Propósito**: Recuperar transcrições longas interrompidas.

**Estágios**:
- `PREPROCESSING`: Normalização de áudio
- `MODEL_LOADING`: Carregando Whisper
- `TRANSCRIBING`: Transcrição em progresso
- `POSTPROCESSING`: Formatação
- `COMPLETED`: Finalizado

**Use cases**:
- Transcrições >30 minutos
- Modelos large-v3 (risco de GPU OOM)
- Workers Celery com crashes
- Network instável

**Exemplo**:

```python
from app.infrastructure import CheckpointManager, TranscriptionStage

manager = CheckpointManager(redis_store)

# Salvar checkpoint a cada 5 minutos
await manager.save_checkpoint(
    job_id="job_123",
    stage=TranscriptionStage.TRANSCRIBING,
    processed_seconds=300.0,
    total_seconds=1800.0,  # 30 minutos
    segments_completed=150,
    metadata={"text": "partial transcription..."}
)

# Recuperar após crash
checkpoint = await manager.resume_from_checkpoint("job_123")
if checkpoint:
    # Continuar de processed_seconds=300.0
    resume_transcription(checkpoint)
```

**Frequência**: Checkpoint a cada 300 segundos (5 minutos)

---

### 3. Distributed Rate Limiter

**Propósito**: Rate limiting distribuído para múltiplas instâncias.

**Algoritmo**: Sliding Window Counter (Redis ZSET)

**Use cases**:
- Limitar transcrições por cliente
- Prevenir abuse de API
- Proteger GPU de sobrecarga
- Rate limit por engine

**Exemplo**:

```python
from app.infrastructure import DistributedRateLimiter

limiter = DistributedRateLimiter(
    redis_client=redis_store.redis_client,
    max_requests=100,  # 100 requests
    window_seconds=60  # por minuto
)

# Verificar limite
if limiter.is_allowed(client_id="user_123"):
    process_transcription()
else:
    # Rate limited
    return 429_TOO_MANY_REQUESTS

# Obter uso atual
usage = limiter.get_usage("user_123")
# {'current': 45, 'limit': 100, 'remaining': 55, 'reset_at': 1234567890.0}
```

**Vantagens**:
- ✅ Funciona entre múltiplas instâncias (Redis)
- ✅ Sliding window (mais preciso que fixed)
- ✅ Degradação graceful se Redis cair

---

## 🧪 Testes

Todos os componentes têm cobertura de testes unitários:

```bash
# Circuit Breaker (14 testes)
pytest tests/unit/infrastructure/test_circuit_breaker.py -v

# Checkpoint Manager (14 testes)
pytest tests/unit/infrastructure/test_checkpoint_manager.py -v

# Todos juntos
pytest tests/unit/infrastructure/ -v
```

**Total**: 28 testes unitários ✅

---

## 📊 Comparação Make-Video vs Audio-Transcriber

| Componente | Make-Video | Audio-Transcriber | Status |
|------------|------------|-------------------|--------|
| Circuit Breaker | ✅ 334 linhas | ✅ 236 linhas | ✅ Implementado |
| Checkpoint Manager | ✅ 322 linhas | ✅ 229 linhas | ✅ Implementado |
| Rate Limiter | ✅ 319 linhas | ✅ 216 linhas | ✅ Implementado |
| Testes Unitários | ✅ 48 arquivos | ⚠️ 26 arquivos | 🔄 Em progresso |

---

## 📝 Próximas Implementações

### 1. Integrar Circuit Breaker nos Whisper Managers

```python
# app/faster_whisper_manager.py
from app.infrastructure import get_circuit_breaker

def load_model(self):
    cb = get_circuit_breaker()
    
    try:
        self.model = cb.call(
            service="faster_whisper_load",
            func=self._load_model_internal
        )
        cb.record_success("faster_whisper_load")
    except CircuitBreakerException:
        logger.error("Circuit breaker OPEN for faster-whisper")
        raise
```

### 2. Checkpoint durante Transcrição

```python
# app/processor.py
async def transcribe_with_checkpoints(self, job_id, audio_path):
    checkpoint_manager = CheckpointManager(self.redis_store)
    
    # Verificar checkpoint existente
    checkpoint = await checkpoint_manager.resume_from_checkpoint(job_id)
    if checkpoint:
        start_from = checkpoint.processed_seconds
    
    # Transcrever com checkpoints
    for segment in transcribe_audio(audio_path, start_from):
        if checkpoint_manager.should_save_checkpoint(...):
            await checkpoint_manager.save_checkpoint(...)
```

### 3. Rate Limiter na API

```python
# app/main.py
from app.infrastructure import DistributedRateLimiter

rate_limiter = DistributedRateLimiter(
    redis_client=job_store.redis_client,
    max_requests=50,  # 50 transcrições
    window_seconds=3600  # por hora
)

@app.post("/jobs")
async def create_job(request: Request):
    client_id = request.client.host
    
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(429, "Rate limit exceeded")
    
    # Processar job
    ...
```

---

## 🎯 Benefícios

1. **Circuit Breaker**:
   - ✅ Previne falhas em cascata
   - ✅ Auto-recuperação após timeout
   - ✅ Estados bem definidos (CLOSED/OPEN/HALF_OPEN)

2. **Checkpoint Manager**:
   - ✅ Recupera transcrições longas
   - ✅ Salva progresso incremental
   - ✅ Reduz desperdício de GPU time

3. **Rate Limiter**:
   - ✅ Protege contra abuse
   - ✅ Funciona com múltiplas instâncias
   - ✅ Sliding window (preciso)

---

## 📚 Referências

- Make-Video Service: `/root/YTCaption-Easy-Youtube-API/services/se5-make-video/`
- Circuit Breaker Pattern: [Martin Fowler](https://martinfowler.com/bliki/CircuitBreaker.html)
- Redis Rate Limiting: [Redis Labs](https://redis.io/docs/manual/patterns/rate-limiter/)
