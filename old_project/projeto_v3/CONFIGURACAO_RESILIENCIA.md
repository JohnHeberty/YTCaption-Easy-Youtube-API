# CONFIGURAÇÃO DE RESILIÊNCIA

## 1. Circuit Breaker

### Implementação

```python
# Dependência: pybreaker (Python)

from pybreaker import CircuitBreaker

# Por serviço
youtube_cb = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listeners=[prometheus_listener],  # Metrics
    exclude_exceptions=[ValueError],  # Don't trip on validation
    expect_exception=(HTTPError, TimeoutError)
)

# Uso
@youtube_cb
def download_video(url):
    response = requests.get(url, timeout=30)
    return response.content
```

### Estados

```
CLOSED (Normal)
  ├─ Chamadas passam normalmente
  ├─ Conta falhas
  └─ Se fail_max atingido → OPEN

OPEN (Falha)
  ├─ Bloqueia todas chamadas (fail-fast)
  └─ Espera reset_timeout → HALF_OPEN

HALF_OPEN (Testando)
  ├─ Permite 1 chamada teste
  ├─ Se sucesso → CLOSED
  └─ Se falhar → OPEN
```

### Configuração por Serviço

```
Serviço            Fail Max  Reset(s)  Retryable  Timeout(s)
─────────────────────────────────────────────────────────────
YouTube API        5         60        SIM        30
PostgreSQL         10        30        SIM        10
Redis              3         20        SIM        5
RabbitMQ           7         45        SIM        5
Email SMTP         5         60        NÃO        10
```

### Métricas

```
circuit_breaker_calls_total{service, state}
circuit_breaker_state{service}  # 0=CLOSED, 1=OPEN, 2=HALF_OPEN
circuit_breaker_failures_total{service}
```

---

## 2. Retry Strategy

### Algoritmo

```python
from random import random
from asyncio import sleep

async def retry_with_backoff(func, *args, **kwargs):
    base_delay = 1
    max_delay = 32
    max_attempts = 5
    
    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if not should_retry(e):  # 400, 401, 403, 404, 409
                raise
            
            if attempt == max_attempts:
                raise
            
            # Exponential backoff + jitter
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = random() * delay
            await sleep(delay + jitter)

def should_retry(error):
    # Retryable: 408, 429, 5xx, Connection, Timeout
    # Non-retryable: 4xx client errors
    if isinstance(error, TimeoutError):
        return True
    if isinstance(error, ConnectionError):
        return True
    if hasattr(error, 'status_code'):
        return error.status_code in (408, 429) or error.status_code >= 500
    return False
```

### Delays

```
Attempt 1: ~1s        (1 + random 0-1)
Attempt 2: ~2-3s      (2 + random 0-2)
Attempt 3: ~4-6s      (4 + random 0-4)
Attempt 4: ~8-14s     (8 + random 0-8)
Attempt 5: ~16-30s    (16 + random 0-16)
─────────────────────────────────────
Total max: ~60s
```

### Retry Policies por Endpoint

```
Download YouTube
  - Retryable: Timeout, 429, 5xx
  - Max attempts: 3
  - Total time: ~12s

Database queries
  - Retryable: Connection, Timeout
  - Max attempts: 5
  - Total time: ~60s

RabbitMQ publish
  - Retryable: Connection, timeout
  - Max attempts: 5
  - Total time: ~60s
```

---

## 3. Timeout

### Hierarquia

```
HTTP Client Request
  ├─ Timeout total: 30s
  └─ Por tentativa: 5s
  
Database Query
  ├─ Timeout: 10s
  └─ Connection pool: 2s
  
RabbitMQ
  ├─ Connect: 5s
  ├─ Publish: 10s
  └─ Consume: 30s
  
Downstream service (gRPC)
  ├─ Timeout: 5s
  └─ Half-open state: 1s
```

### Implementação

```python
import asyncio

async def call_with_timeout(func, *args, timeout=5, **kwargs):
    try:
        return await asyncio.wait_for(
            func(*args, **kwargs),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout after {timeout}s")
        raise TimeoutError(f"Operation exceeded {timeout}s")
```

---

## 4. Graceful Shutdown

### Timeline (30 segundos)

```
t=0s      SIGTERM recebido
t=0-2s    Log shutdown ("Starting graceful shutdown...")
t=2s      Health checks retornam 503
          └─ Kubernetes remove da LB (max 5s)

t=2-5s    Stop accepting NEW requests
          └─ /health/ready = UNREADY
          └─ Drain em-flight requests

t=5-20s   Close long connections
          ├─ Database: Close pool + drain queries
          ├─ RabbitMQ: Close connection (requeue messages)
          └─ gRPC: Close listeners

t=20-30s  Cleanup
          ├─ Close files
          ├─ Flush logs
          └─ Wait remaining operations

t=30s     SIGKILL (Kubernetes força)
```

### Código

```python
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI

class GracefulShutdown:
    def __init__(self):
        self.is_shutting_down = False
    
    async def shutdown_event(self):
        self.is_shutting_down = True
        
        # t=0-2s
        logger.info("Starting graceful shutdown...")
        await asyncio.sleep(2)
        
        # t=2-5s: Drain requests
        logger.info("Draining in-flight requests...")
        while active_requests > 0 and time.time() - start < 3:
            await asyncio.sleep(0.1)
        
        # t=5-20s: Close connections
        logger.info("Closing connections...")
        await db_pool.close()
        await rabbitmq.close()
        
        logger.info("Graceful shutdown complete")

# FastAPI lifespan
shutdown = GracefulShutdown()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await shutdown.shutdown_event()

app = FastAPI(lifespan=lifespan)

# Health check
@app.get("/health/ready")
async def health_ready():
    if shutdown.is_shutting_down:
        return {"status": "UNREADY"}, 503
    return {"status": "READY"}, 200
```

### Kubernetes Integration

```yaml
spec:
  terminationGracePeriodSeconds: 30  # Match app timeout
  lifecycle:
    preStop:
      exec:
        command: ["/bin/sh", "-c", "sleep 5"]  # Give app time to register shutdown
```

---

## 5. Bulkhead Pattern

### Isolamento de Recursos

```
API Gateway
  ├─ HTTP threads: 50 max (Uvicorn workers)
  ├─ Connection pool DB: 10 max
  └─ RabbitMQ channel: 1 per thread

Downloader
  ├─ Parallel downloads: 10 max
  ├─ Retry workers: 5 threads
  └─ Storage upload: 5 parallel

Transcriber
  ├─ Workers: 4 (CPU-bound)
  ├─ Model memory: 1 copy (shared)
  └─ Queue: In-memory (100 max)

Notifier
  ├─ Email workers: 20 threads
  ├─ Webhook workers: 20 threads
  └─ DB connection: 5 max
```

### Implementação

```python
from concurrent.futures import ThreadPoolExecutor
from asyncio import Semaphore

# Limite parallelismo
transcriber_semaphore = Semaphore(4)  # 4 concurrent

async def transcribe_audio(file_path):
    async with transcriber_semaphore:
        # Only 4 at a time, rest wait
        return await _do_transcribe(file_path)

# Thread pool (bounded)
download_executor = ThreadPoolExecutor(max_workers=10)

def download_parallel(urls):
    futures = [
        download_executor.submit(download_url, url)
        for url in urls
    ]
    return [f.result() for f in futures]
```

### Metrics

```
transcriber_workers_active{service}
transcriber_queue_depth{service}
db_connection_pool_available{service}
http_threads_active{service}
```

---

## 6. Idempotency

### Key Generation

```python
import hashlib

def generate_idempotency_key(user_id: str, request_id: str, endpoint: str) -> str:
    data = f"{user_id}:{request_id}:{endpoint}"
    return hashlib.sha256(data.encode()).hexdigest()

# Cache (Redis)
class IdempotencyCache:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 86400  # 24 hours
    
    def get(self, key: str):
        return self.redis.get(f"idempotency:{key}")
    
    def set(self, key: str, response: dict):
        self.redis.setex(
            f"idempotency:{key}",
            self.ttl,
            json.dumps(response)
        )
```

### Implementação

```python
@app.post("/api/v1/jobs")
async def create_job(request: JobRequest):
    idempotency_key = generate_idempotency_key(
        user_id=request.user_id,
        request_id=request.request_id,
        endpoint="/api/v1/jobs"
    )
    
    # Check cache first
    cached = cache.get(idempotency_key)
    if cached:
        return json.loads(cached), 200
    
    # Process
    job = await job_manager.create(request)
    response = {"job_id": job.id, "status": "queued"}
    
    # Cache response
    cache.set(idempotency_key, response)
    
    return response, 202
```

---

## 7. Rate Limiting

### Token Bucket Algorithm

```python
from time import time
from threading import Lock

class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity  # Max tokens
        self.tokens = capacity
        self.refill_rate = refill_rate  # Tokens per second
        self.last_refill = time()
        self.lock = Lock()
    
    def allow(self, tokens_required: int = 1) -> bool:
        with self.lock:
            # Refill based on time passed
            now = time()
            elapsed = now - self.last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.refill_rate
            )
            self.last_refill = now
            
            if self.tokens >= tokens_required:
                self.tokens -= tokens_required
                return True
            return False
```

### Limites

```
Global:          10k req/min  (capacity: 167, refill: 2.77/s)
Per-user:        100 req/min  (capacity: 2, refill: 1.67/s)
Per-IP:          1k req/min   (capacity: 17, refill: 16.67/s)

Response 429:
{
  "error": "Too many requests",
  "retry_after": 5
}
```

---

## 8. Health Checks

### Liveness Probe

```
GET /health/live

Timeout: 1s
Failure threshold: 3 consecutive
Action: Kubernetes restarts pod

Response 200: {"status": "alive", "timestamp": "..."}
```

**Verifica**:
- Process is running
- Minimal dependencies

### Readiness Probe

```
GET /health/ready

Timeout: 1s
Failure threshold: 2 consecutive
Action: Kubernetes removes from LB

Verifica:
- Database connection OK
- RabbitMQ connection OK
- Redis cache OK (if required)
- Model loaded (transcriber only)
```

**Response 200**: `{"status": "ready"}`  
**Response 503**: Service degraded, don't send traffic

### Implementação

```python
@app.get("/health/live")
async def health_live():
    return {"status": "alive", "timestamp": datetime.now().isoformat()}

@app.get("/health/ready")
async def health_ready():
    checks = {
        "database": await check_db(),
        "rabbitmq": await check_rabbitmq(),
        "redis": await check_redis(),
    }
    
    if all(checks.values()):
        return {"status": "ready", "checks": checks}, 200
    
    return {"status": "degraded", "checks": checks}, 503

async def check_db():
    try:
        async with db.execute("SELECT 1"):
            return True
    except:
        return False
```

---

**Próximo**: Leia `DEPLOYMENT.md`
