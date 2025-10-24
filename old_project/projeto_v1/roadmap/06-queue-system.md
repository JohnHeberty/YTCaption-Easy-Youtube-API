# Phase 6: Queue System (Celery + Redis)

**Status**: ⏳ PENDENTE  
**Prioridade**: 🔴 HIGH  
**Esforço Estimado**: 8 horas (1 dia)  
**Impacto**: Alto  
**ROI**: ⭐⭐⭐⭐⭐

---

## 📋 Objetivo

Implementar sistema de filas assíncronas robusto usando Celery + Redis para desacoplar processamento pesado da API, permitindo escalabilidade horizontal e melhor resiliência.

---

## 🎯 Motivação

**Problemas atuais**:
- ❌ Transcrições longas bloqueiam workers HTTP
- ❌ Timeout de 3600s (1h) é muito agressivo
- ❌ Difícil escalar processamento independentemente da API
- ❌ Sem retry automático de falhas
- ❌ Impossível priorizar requisições

**Benefícios esperados**:
- ✅ API sempre responsiva (aceita job e retorna imediatamente)
- ✅ Escala workers independentemente da API
- ✅ Retry automático com exponential backoff
- ✅ Priorização de jobs (express lanes para PRO users)
- ✅ Monitoramento em tempo real de filas
- ✅ Melhor gestão de recursos

---

## 🏗️ Arquitetura Proposta

### Fluxo de Trabalho

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI    │────▶│    Redis    │────▶│   Celery    │
│  (HTTP)     │◀────│   (API)     │◀────│   (Broker)  │◀────│  (Workers)  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                    │                    │                    │
      │                    │                    │                    │
   Request              Accept Job          Queue Job          Process Job
   (sync)              (immediate)         (persistent)        (async)
      │                    │                    │                    │
      │              Return job_id              │              Store result
      │                    │                    │                    │
   Poll /status/{id}  ────▶ Check Redis ───────▶ Get status ───────┘
      │                    │
   Get result          Return status
```

### Componentes

1. **Redis**: Message broker + result backend
2. **Celery**: Task queue e workers
3. **FastAPI**: API gateway que enfileira jobs
4. **Flower** (opcional): UI para monitoramento

---

## 🛠️ Implementação Técnica

### 1. Dependências

```txt
# requirements.txt
celery[redis]==5.3.4
redis==5.0.1
flower==2.0.1  # Dashboard de monitoramento
```

### 2. Celery Configuration

```python
# src/infrastructure/celery/celery_app.py
from celery import Celery
from celery.schedules import crontab
from src.config import settings

# Criar instância Celery
celery_app = Celery(
    'ytcaption_worker',
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['src.infrastructure.celery.tasks']
)

# Configuração
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Result backend
    result_backend=settings.redis_url,
    result_expires=86400,  # 24 horas
    result_persistent=True,
    
    # Broker settings
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Disable prefetching
    worker_max_tasks_per_child=50,  # Restart worker after N tasks
    
    # Task routing (prioridades)
    task_routes={
        'transcribe_video_express': {'queue': 'express'},
        'transcribe_video_standard': {'queue': 'standard'},
        'transcribe_video_batch': {'queue': 'batch'},
    },
    
    # Retry policy
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Beat schedule (tarefas periódicas)
    beat_schedule={
        'cleanup-old-results': {
            'task': 'cleanup_old_results',
            'schedule': crontab(hour=2, minute=0),  # 2AM diariamente
        },
        'reset-monthly-quotas': {
            'task': 'reset_monthly_quotas',
            'schedule': crontab(day_of_month=1, hour=0, minute=0),  # 1º dia do mês
        },
    },
)

# Task base class com retry automático
class BaseTask(celery_app.Task):
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutos
    retry_jitter = True
```

### 3. Tasks Definition

```python
# src/infrastructure/celery/tasks.py
from celery import Task
from celery.utils.log import get_task_logger
from src.infrastructure.celery.celery_app import celery_app, BaseTask
from src.application.use_cases import TranscribeYouTubeVideoUseCase
from src.application.dtos import TranscribeRequestDTO

logger = get_task_logger(__name__)

@celery_app.task(
    name='transcribe_video_express',
    base=BaseTask,
    bind=True,
    priority=9  # Alta prioridade
)
def transcribe_video_express(
    self: Task,
    youtube_url: str,
    language: str = 'auto',
    model: str = 'base',
    user_id: str = None
):
    """
    Transcrição expressa (para PRO users).
    Alta prioridade, fila dedicada.
    """
    logger.info(f"Starting express transcription: {youtube_url}")
    
    # Atualizar estado
    self.update_state(state='STARTED', meta={'progress': 0})
    
    try:
        # Executar transcrição
        use_case = TranscribeYouTubeVideoUseCase()  # Injetado via DI
        request_dto = TranscribeRequestDTO(
            youtube_url=youtube_url,
            language=language,
            model=model
        )
        
        result = use_case.execute(request_dto)
        
        logger.info(f"Transcription completed: {result.transcription_id}")
        
        return {
            'status': 'success',
            'transcription_id': result.transcription_id,
            'processing_time': result.processing_time,
            'total_segments': result.total_segments
        }
        
    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}", exc_info=True)
        
        # Atualizar estado de erro
        self.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'error_type': type(e).__name__
            }
        )
        raise

@celery_app.task(
    name='transcribe_video_standard',
    base=BaseTask,
    bind=True,
    priority=5  # Prioridade média
)
def transcribe_video_standard(
    self: Task,
    youtube_url: str,
    language: str = 'auto',
    model: str = 'base',
    user_id: str = None
):
    """Transcrição padrão (FREE users)."""
    logger.info(f"Starting standard transcription: {youtube_url}")
    
    # Implementação similar ao express
    # ...

@celery_app.task(
    name='transcribe_video_batch',
    base=BaseTask,
    bind=True,
    priority=1  # Baixa prioridade
)
def transcribe_video_batch(
    self: Task,
    videos: list,
    user_id: str
):
    """Processamento batch de múltiplos vídeos."""
    logger.info(f"Starting batch transcription: {len(videos)} videos")
    
    results = []
    for i, video in enumerate(videos):
        try:
            result = transcribe_video_standard(
                youtube_url=video['youtube_url'],
                language=video.get('language', 'auto'),
                model=video.get('model', 'base'),
                user_id=user_id
            )
            results.append({'video_index': i, 'status': 'success', 'result': result})
        except Exception as e:
            results.append({'video_index': i, 'status': 'failed', 'error': str(e)})
        
        # Atualizar progresso
        progress = (i + 1) / len(videos) * 100
        self.update_state(state='PROGRESS', meta={'progress': progress})
    
    return {'results': results}

@celery_app.task(name='cleanup_old_results')
def cleanup_old_results():
    """Remove resultados antigos do Redis."""
    logger.info("Starting cleanup of old results")
    # Implementação de cleanup
    ...

@celery_app.task(name='reset_monthly_quotas')
def reset_monthly_quotas():
    """Reseta quotas mensais dos usuários."""
    logger.info("Resetting monthly quotas")
    # Implementação de reset
    ...
```

### 4. API Integration

```python
# src/presentation/api/routes/async_transcription.py
from fastapi import APIRouter, Depends, HTTPException
from celery.result import AsyncResult
from src.infrastructure.celery.tasks import (
    transcribe_video_express,
    transcribe_video_standard
)

router = APIRouter(prefix="/api/v1/transcribe/async", tags=["Async Transcription"])

@router.post("/submit")
async def submit_transcription(
    request_dto: TranscribeRequestDTO,
    current_user: User = Depends(get_current_user)
):
    """
    Submete uma transcrição para processamento assíncrono.
    Retorna job_id para acompanhar progresso.
    """
    # Verificar quota
    if current_user.monthly_usage >= current_user.monthly_quota:
        raise HTTPException(429, "Monthly quota exceeded")
    
    # Escolher fila baseado no tier do usuário
    if current_user.tier in ['pro', 'enterprise']:
        task = transcribe_video_express.apply_async(
            kwargs={
                'youtube_url': request_dto.youtube_url,
                'language': request_dto.language,
                'model': request_dto.model,
                'user_id': current_user.id
            },
            queue='express'
        )
    else:
        task = transcribe_video_standard.apply_async(
            kwargs={
                'youtube_url': request_dto.youtube_url,
                'language': request_dto.language,
                'model': request_dto.model,
                'user_id': current_user.id
            },
            queue='standard'
        )
    
    return {
        'job_id': task.id,
        'status': 'accepted',
        'message': 'Transcription job submitted successfully',
        'status_url': f'/api/v1/transcribe/async/status/{task.id}'
    }

@router.get("/status/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """Obtém status de um job assíncrono."""
    result = AsyncResult(job_id)
    
    if result.state == 'PENDING':
        response = {
            'job_id': job_id,
            'status': 'pending',
            'message': 'Job is queued and waiting for processing'
        }
    elif result.state == 'STARTED':
        response = {
            'job_id': job_id,
            'status': 'processing',
            'progress': result.info.get('progress', 0)
        }
    elif result.state == 'SUCCESS':
        response = {
            'job_id': job_id,
            'status': 'completed',
            'result': result.result
        }
    elif result.state == 'FAILURE':
        response = {
            'job_id': job_id,
            'status': 'failed',
            'error': str(result.info)
        }
    else:
        response = {
            'job_id': job_id,
            'status': result.state.lower()
        }
    
    return response

@router.delete("/cancel/{job_id}")
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """Cancela um job em andamento."""
    result = AsyncResult(job_id)
    result.revoke(terminate=True)
    
    return {
        'job_id': job_id,
        'status': 'cancelled',
        'message': 'Job cancelled successfully'
    }
```

### 5. Docker Compose Integration

```yaml
# docker-compose.yml
services:
  # Redis (broker + backend)
  redis:
    image: redis:7.2-alpine
    container_name: whisper-redis
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - whisper-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  # Celery Worker - Express Queue (PRO users)
  celery-worker-express:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: whisper-celery-express
    command: celery -A src.infrastructure.celery.celery_app worker -Q express -l info -n express@%h
    environment:
      - REDIS_URL=redis://redis:6379/0
      - WHISPER_MODEL=base
    volumes:
      - ./temp:/app/temp
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - whisper-network

  # Celery Worker - Standard Queue (FREE users)
  celery-worker-standard:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: whisper-celery-standard
    command: celery -A src.infrastructure.celery.celery_app worker -Q standard -l info -n standard@%h --concurrency=2
    environment:
      - REDIS_URL=redis://redis:6379/0
      - WHISPER_MODEL=base
    volumes:
      - ./temp:/app/temp
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - whisper-network
    deploy:
      replicas: 2  # 2 workers para standard queue

  # Celery Beat (tarefas periódicas)
  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: whisper-celery-beat
    command: celery -A src.infrastructure.celery.celery_app beat -l info
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - whisper-network

  # Flower (monitoramento)
  flower:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: whisper-flower
    command: celery -A src.infrastructure.celery.celery_app flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - FLOWER_BASIC_AUTH=admin:whisper2024
    depends_on:
      - redis
      - celery-worker-express
      - celery-worker-standard
    restart: unless-stopped
    networks:
      - whisper-network

volumes:
  redis_data:
```

---

## 📊 Métricas

```python
# Novas métricas Prometheus
celery_tasks_submitted = Counter('celery_tasks_submitted_total', ['queue', 'task_name'])
celery_tasks_completed = Counter('celery_tasks_completed_total', ['queue', 'status'])
celery_task_duration = Histogram('celery_task_duration_seconds', ['task_name'])
celery_queue_length = Gauge('celery_queue_length', ['queue'])
celery_active_workers = Gauge('celery_active_workers', ['queue'])
```

---

## 🧪 Testing

```python
# tests/integration/test_async_transcription.py
async def test_async_transcription_flow():
    # Submit job
    response = await client.post("/api/v1/transcribe/async/submit", json={
        "youtube_url": "https://youtube.com/watch?v=test",
        "language": "en"
    })
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    
    # Poll status até completar
    max_retries = 60
    for _ in range(max_retries):
        status_response = await client.get(f"/api/v1/transcribe/async/status/{job_id}")
        status = status_response.json()["status"]
        
        if status == "completed":
            assert status_response.json()["result"]["transcription_id"]
            break
        elif status == "failed":
            pytest.fail(f"Job failed: {status_response.json()}")
        
        await asyncio.sleep(1)
    else:
        pytest.fail("Job timeout")
```

---

## 🚀 Deployment

### Scaling Strategy

```bash
# Escalar workers express (PRO)
docker-compose up -d --scale celery-worker-express=5

# Escalar workers standard (FREE)
docker-compose up -d --scale celery-worker-standard=10

# Monitorar filas
docker exec whisper-celery-express celery -A src.infrastructure.celery.celery_app inspect active
```

### Monitoring

- **Flower Dashboard**: http://localhost:5555
- **Redis CLI**: `redis-cli LLEN celery` (queue length)
- **Celery Events**: `celery -A src.infrastructure.celery.celery_app events`

---

**Próxima Phase**: [Phase 7: WebSocket Progress Updates](./07-websocket-progress.md)
