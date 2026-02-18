# SPRINT-02: Observabilidade e Fallbacks (P1/P2)

**Duração:** 2 semanas (10 dias úteis)  
**Prioridade:** P1/P2 (Observabilidade e Persistência)  
**Story Points:** 29  
**Impacto Esperado:** +200% velocidade de debug, -100% perda de jobs  
**Data de Criação:** 18/02/2026  
**Status:** 🟡 PENDENTE (aguarda Sprint-01)

---

## 📋 Objetivos da Sprint

Implementar **observabilidade completa** e **fallbacks de persistência** para:
- Diagnosticar problemas em produção rapidamente
- Não perder jobs em caso de falhas de infraestrutura
- Medir performance e identificar bottlenecks
- Proteger contra falhas de serviços externos

### Métricas de Sucesso
- ✅ Tempo médio de diagnóstico: 30min → 5min (-83%)
- ✅ Taxa de recuperação de jobs pós-Redis restart: 0% → 100%
- ✅ Visibilidade de latência P50/P95/P99 por etapa
- ✅ Logs JSON parseáveis em 100% das operações críticas
- ✅ Circuit breaker distribuído protegendo APIs externas

---

## 🎯 Riscos Corrigidos

Esta sprint corrige os seguintes riscos do Risk Register:

- **R-010:** Redis como Única Fonte de Estado
- **R-011:** Logging Não Estruturado em Partes Críticas
- **R-012:** Sem Métricas de Duração Por Etapa
- **R-014:** Validação de Entrada Insuficiente
- Circuit breaker distribuído (melhoria de R-002)

---

## 📝 Tasks Detalhadas

### Task 1: Dual-Store (Redis + SQLite) para Jobs (R-010)

**Story Points:** 8  
**Prioridade:** P1  
**Impacto:** -100% perda de jobs

#### Descrição
Implementar armazenamento dual (Redis primário + SQLite backup) para garantir persistência de jobs.

#### Sub-tasks

##### 1.1: Criar SQLite Job Store

**Arquivo:** `app/infrastructure/sqlite_job_store.py` (NOVO)

```python
"""
SQLite Job Store - Persistent backup for jobs

Provides durable storage for jobs with automatic recovery.
"""
import sqlite3
import json
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List
from datetime import datetime

from app.core.models import Job, JobStatus

logger = logging.getLogger(__name__)


class SQLiteJobStore:
    """Armazena jobs em SQLite para persistência"""
    
    def __init__(self, db_path: str = "data/jobs.db"):
        """
        Args:
            db_path: Path do banco SQLite
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Criar tabela se não existir
        self._init_db()
        
        logger.info(f"✅ SQLiteJobStore initialized: {db_path}")
    
    def _init_db(self):
        """Cria tabela de jobs"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    progress REAL DEFAULT 0.0,
                    data TEXT NOT NULL,  -- JSON serializado
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            
            # Índices para busca rápida
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status 
                ON jobs(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON jobs(created_at DESC)
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager para conexão SQLite"""
        conn = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    async def save_job(self, job: Job):
        """
        Salva job no SQLite
        
        Args:
            job: Job a salvar
        """
        data_json = json.dumps(job.dict())
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO jobs (
                    job_id, status, progress, data,
                    created_at, updated_at, completed_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id,
                job.status.value,
                job.progress,
                data_json,
                job.created_at,
                job.updated_at,
                job.completed_at,
                job.expires_at
            ))
            conn.commit()
        
        logger.debug(f"Job saved to SQLite: {job.job_id}")
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Recupera job do SQLite
        
        Args:
            job_id: ID do job
        
        Returns:
            Job ou None se não encontrado
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT data FROM jobs WHERE job_id = ?",
                (job_id,)
            ).fetchone()
        
        if not row:
            return None
        
        data = json.loads(row['data'])
        return Job(**data)
    
    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100
    ) -> List[Job]:
        """
        Lista jobs
        
        Args:
            status: Filtrar por status (opcional)
            limit: Máximo de resultados
        
        Returns:
            Lista de jobs
        """
        with self._get_connection() as conn:
            if status:
                rows = conn.execute("""
                    SELECT data FROM jobs 
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (status.value, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT data FROM jobs 
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,)).fetchall()
        
        jobs = []
        for row in rows:
            data = json.loads(row['data'])
            jobs.append(Job(**data))
        
        return jobs
    
    async def delete_job(self, job_id: str):
        """Remove job do SQLite"""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            conn.commit()
    
    async def cleanup_expired(self) -> int:
        """
        Remove jobs expirados
        
        Returns:
            Número de jobs removidos
        """
        now = datetime.utcnow()
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM jobs 
                WHERE expires_at IS NOT NULL 
                AND expires_at < ?
            """, (now,))
            deleted = cursor.rowcount
            conn.commit()
        
        if deleted > 0:
            logger.info(f"🧹 Cleaned {deleted} expired jobs from SQLite")
        
        return deleted
```

##### 1.2: Criar Dual Store Facade

**Arquivo:** `app/infrastructure/dual_job_store.py` (NOVO)

```python
"""
Dual Job Store - Redis (fast) + SQLite (durable)

Stores jobs in both Redis and SQLite for best of both worlds:
- Redis: Fast access, low latency
- SQLite: Durable, survives restarts
"""
import logging
from typing import Optional, List

from app.core.models import Job, JobStatus
from app.infrastructure.redis_store import RedisJobStore
from app.infrastructure.sqlite_job_store import SQLiteJobStore

logger = logging.getLogger(__name__)


class DualJobStore:
    """Armazena jobs em Redis (primário) + SQLite (backup)"""
    
    def __init__(self, redis_url: str, sqlite_path: str = "data/jobs.db"):
        """
        Args:
            redis_url: URL de conexão Redis
            sqlite_path: Path do banco SQLite
        """
        self.redis = RedisJobStore(redis_url=redis_url)
        self.sqlite = SQLiteJobStore(db_path=sqlite_path)
        
        logger.info("✅ DualJobStore initialized (Redis + SQLite)")
    
    async def save_job(self, job: Job):
        """
        Salva job em AMBOS os stores
        
        Strategy: Fire-and-forget no SQLite. Se SQLite falhar, apenas loga warning.
        """
        # 1. Salvar no Redis (primário)
        await self.redis.save_job(job)
        
        # 2. Salvar no SQLite (backup) - best effort
        try:
            await self.sqlite.save_job(job)
        except Exception as e:
            logger.warning(
                f"Failed to save job to SQLite backup: {job.job_id}",
                extra={"error": str(e)},
                exc_info=True
            )
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Busca job com fallback: Redis → SQLite
        
        Returns:
            Job ou None
        """
        # 1. Tentar Redis primeiro (mais rápido)
        job = await self.redis.get_job(job_id)
        
        if job:
            return job
        
        # 2. Fallback para SQLite
        logger.info(f"Job {job_id} not found in Redis, trying SQLite...")
        
        job = await self.sqlite.get_job(job_id)
        
        if job:
            logger.info(f"✅ Job {job_id} recovered from SQLite backup")
            
            # Repopular Redis
            try:
                await self.redis.save_job(job)
                logger.debug(f"Job {job_id} restored to Redis")
            except Exception as e:
                logger.warning(f"Failed to restore job to Redis: {e}")
        
        return job
    
    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100
    ) -> List[Job]:
        """
        Lista jobs do Redis (se disponível) senão SQLite
        """
        try:
            return await self.redis.list_jobs(status=status, limit=limit)
        except Exception as e:
            logger.warning(f"Failed to list from Redis, using SQLite: {e}")
            return await self.sqlite.list_jobs(status=status, limit=limit)
    
    async def delete_job(self, job_id: str):
        """Remove de AMBOS os stores"""
        await self.redis.delete_job(job_id)
        
        try:
            await self.sqlite.delete_job(job_id)
        except Exception as e:
            logger.warning(f"Failed to delete from SQLite: {e}")
    
    async def sync_redis_to_sqlite(self, limit: int = 1000) -> int:
        """
        Sincroniza jobs do Redis para SQLite (backup em massa)
        
        Útil para rodar periodicamente via cron.
        
        Returns:
            Número de jobs sincronizados
        """
        logger.info("🔄 Starting Redis → SQLite sync...")
        
        try:
            redis_jobs = await self.redis.list_jobs(limit=limit)
            
            synced = 0
            for job in redis_jobs:
                try:
                    await self.sqlite.save_job(job)
                    synced += 1
                except Exception as e:
                    logger.warning(f"Failed to sync job {job.job_id}: {e}")
            
            logger.info(f"✅ Synced {synced}/{len(redis_jobs)} jobs to SQLite")
            return synced
        
        except Exception as e:
            logger.error(f"❌ Sync failed: {e}", exc_info=True)
            return 0
```

##### 1.3: Migrar Código para Usar DualStore

**Arquivo:** `app/main.py`

```python
# ANTES:
from app.infrastructure.redis_store import RedisJobStore
redis_store = RedisJobStore(redis_url=settings['redis_url'])

# DEPOIS:
from app.infrastructure.dual_job_store import DualJobStore
redis_store = DualJobStore(
    redis_url=settings['redis_url'],
    sqlite_path="data/jobs.db"
)
```

##### 1.4: Cronjob de Sync e Cleanup

**Arquivo:** `app/infrastructure/celery_config.py`

```python
from celery.schedules import crontab

celery_app.conf.beat_schedule.update({
    'sync-redis-to-sqlite': {
        'task': 'app.infrastructure.celery_tasks.sync_jobs_to_sqlite',
        'schedule': crontab(minute='*/15'),  # A cada 15 minutos
    },
    'cleanup-expired-jobs': {
        'task': 'app.infrastructure.celery_tasks.cleanup_expired_jobs',
        'schedule': crontab(hour='3', minute='0'),  # 3 AM diariamente
    },
})


@celery_app.task
async def sync_jobs_to_sqlite():
    """Sincroniza jobs do Redis para SQLite"""
    from app.core.config import get_settings
    from app.infrastructure.dual_job_store import DualJobStore
    
    settings = get_settings()
    store = DualJobStore(
        redis_url=settings['redis_url'],
        sqlite_path="data/jobs.db"
    )
    
    synced = await store.sync_redis_to_sqlite(limit=1000)
    logger.info(f"🔄 Synced {synced} jobs to SQLite")
    return synced


@celery_app.task
async def cleanup_expired_jobs():
    """Remove jobs expirados"""
    from app.infrastructure.sqlite_job_store import SQLiteJobStore
    
    store = SQLiteJobStore()
    deleted = await store.cleanup_expired()
    logger.info(f"🧹 Cleaned {deleted} expired jobs")
    return deleted
```

**Critério de Aceite:**
- ✅ Jobs salvos em Redis E SQLite
- ✅ Recuperação automática do SQLite se Redis falhar
- ✅ Sync periódico a cada 15min
- ✅ Teste: restart Redis → jobs recuperados do SQLite

---

### Task 2: Logging Estruturado (JSON) (R-011)

**Story Points:** 8  
**Prioridade:** P2  
**Impacto:** +200% velocidade de debug

#### Descrição
Implementar logging estruturado (JSON) em todas as operações críticas com correlation ID.

#### Sub-tasks

##### 2.1: Configurar Logging Estruturado

**Arquivo:** `app/infrastructure/structured_logging.py` (NOVO)

```python
"""
Structured JSON Logging

All logs output as JSON with structured fields for easy parsing/aggregation.
"""
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
import contextvars

# Context var para correlation ID
correlation_id = contextvars.ContextVar('correlation_id', default=None)


class JSONFormatter(logging.Formatter):
    """Formata logs como JSON"""
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Converte LogRecord para JSON
        
        Output format:
        {
            "timestamp": "2026-02-18T10:30:45.123Z",
            "level": "INFO",
            "logger": "app.services.video_builder",
            "message": "Video concatenation started",
            "correlation_id": "abc-123-def",
            "job_id": "xyz",
            "video_count": 5,
            ...extra fields...
        }
        """
        # Campos base
        log_obj = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Adicionar correlation ID
        cid = correlation_id.get()
        if cid:
            log_obj["correlation_id"] = cid
        
        # Adicionar campos extras (passados via extra={})
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'created', 'filename', 
                              'funcName', 'levelname', 'lineno', 'module',
                              'msecs', 'message', 'pathname', 'process',
                              'processName', 'relativeCreated', 'thread',
                              'threadName', 'exc_info', 'exc_text', 'stack_info']:
                    log_obj[key] = value
        
        # Adicionar exception info se presente
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, 'stack_info') and record.stack_info:
            log_obj["stack_info"] = record.stack_info
        
        return json.dumps(log_obj, default=str)


def setup_structured_logging(
    level: str = "INFO",
    output_file: str = None
):
    """
    Configura logging estruturado para toda a aplicação
    
    Args:
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        output_file: Path de arquivo para logs (None = stdout)
    """
    # Criar handler
    if output_file:
        handler = logging.FileHandler(output_file)
    else:
        handler = logging.StreamHandler(sys.stdout)
    
    # Aplicar formatter JSON
    handler.setFormatter(JSONFormatter())
    
    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(handler)
    
    # Fazer logs de bibliotecas externas menos verbosos  
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    logging.info(
        "Structured logging initialized",
        extra={
            "log_level": level,
            "output": output_file or "stdout",
            "format": "json"
        }
    )
```

##### 2.2: Middleware de Correlation ID

**Arquivo:** `app/main.py`

```python
from app.infrastructure.structured_logging import correlation_id
import shortuuid

@app.middleware("http")
async def add_correlation_id_middleware(request, call_next):
    """
    Adiciona correlation ID a cada request
    
    Ordem de prioridade:
    1. Header X-Correlation-ID (se presente)
    2. Gerar novo UUID
    """
    cid = request.headers.get("X-Correlation-ID", shortuuid.uuid())
    
    # Definir no context
    correlation_id.set(cid)
    
    # Processar request
    response = await call_next(request)
    
    # Adicionar ao response header
    response.headers["X-Correlation-ID"] = cid
    
    return response
```

##### 2.3: Refatorar Logs Críticos

Substituir todos os logs críticos por versão estruturada:

```python
# ANTES:
logger.info(f"🎬 Concatenating {len(video_files)} videos")

# DEPOIS:
logger.info(
    "Video concatenation started",
    extra={
        "job_id": job_id,
        "video_count": len(video_files),
        "aspect_ratio": aspect_ratio,
        "crop_position": crop_position,
        "stage": "concatenation",
        "operation": "video_concat_start"
    }
)
```

**Locais para refatorar:**
- `celery_tasks.py` - Todas as etapas do pipeline
- `video_builder.py` - Operações FFmpeg
- `api_client.py` - Chamadas externas
- `video_validator.py` - Validação OCR

**Critério de Aceite:**
- ✅ 100% dos logs críticos em JSON
- ✅ Correlation ID em todos os logs de um request
- ✅ Logs parseáveis com `jq` ou ELK

---

### Task 3: Métricas Prometheus por Etapa (R-012)

**Story Points:** 5  
**Prioridade:** P2  
**Impacto:** +100% visibilidade de bottlenecks

#### Descrição
Instrumentar código com métricas Prometheus para medir latência de cada etapa.

#### Sub-tasks

##### 3.1: Definir Métricas Completas

**Arquivo:** `app/infrastructure/metrics.py`

```python
"""
Prometheus Metrics for Make-Video Service
"""
from prometheus_client import Counter, Histogram, Gauge, Info, Summary

# HTTP Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Pipeline Stage Metrics
pipeline_stage_duration_seconds = Histogram(
    'pipeline_stage_duration_seconds',
    'Duration of each pipeline stage',
    ['stage', 'job_id'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
)

pipeline_stage_errors_total = Counter(
    'pipeline_stage_errors_total',
    'Total errors per pipeline stage',
    ['stage', 'error_type', 'error_code']
)

pipeline_jobs_total = Counter(
    'pipeline_jobs_total',
    'Total jobs processed',
    ['status']  # completed, failed, cancelled
)

pipeline_jobs_active = Gauge(
    'pipeline_jobs_active',
    'Number of currently active jobs'
)

# Video Processing Metrics
video_processing_duration_seconds = Histogram(
    'video_processing_duration_seconds',
    'Duration of video processing operations',
    ['operation'],  # concat, crop, trim, overlay
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

video_processing_input_duration_seconds = Histogram(
    'video_processing_input_duration_seconds',
    'Duration of input videos',
    buckets=[5, 10, 30, 60, 120, 300, 600]
)

video_processing_shorts_count = Histogram(
    'video_processing_shorts_count',
    'Number of shorts used per job',
    buckets=[1, 5, 10, 20, 50, 100]
)

# External API Metrics
external_api_calls_total = Counter(
    'external_api_calls_total',
    'Total external API calls',
    ['service', 'endpoint', 'status']
)

external_api_duration_seconds = Histogram(
    'external_api_duration_seconds',
    'External API call duration',
    ['service', 'endpoint'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

external_api_retries_total = Counter(
    'external_api_retries_total',
    'Total retry attempts for external APIs',
    ['service', 'endpoint']
)

# Circuit Breaker Metrics
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['service']
)

circuit_breaker_transitions_total = Counter(
    'circuit_breaker_transitions_total',
    'Circuit breaker state transitions',
    ['service', 'from_state', 'to_state']
)

# OCR/Validation Metrics
ocr_frames_processed_total = Counter(
    'ocr_frames_processed_total',
    'Total frames processed by OCR'
)

ocr_processing_duration_seconds = Histogram(
    'ocr_processing_duration_seconds',
    'OCR processing duration per video',
    buckets=[1, 5, 10, 30, 60, 120]
)

ocr_confidence_score = Histogram(
    'ocr_confidence_score',
    'OCR confidence scores',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

validation_results_total = Counter(
    'validation_results_total',
    'Video validation results',
    ['result']  # approved, rejected
)

# Resource Metrics
resource_disk_usage_bytes = Gauge(
    'resource_disk_usage_bytes',
    'Disk usage in bytes',
    ['directory']  # temp, output, cache, approved
)

resource_memory_usage_bytes = Gauge(
    'resource_memory_usage_bytes',
    'Memory usage by component',
    ['component']  # ocr, ffmpeg, redis, total
)

resource_ffmpeg_processes = Gauge(
    'resource_ffmpeg_processes',
    'Current number of FFmpeg processes'
)

resource_temp_files_count = Gauge(
    'resource_temp_files_count',
    'Number of temporary files'
)

# Subtitle Metrics
subtitle_segments_count = Histogram(
    'subtitle_segments_count',
    'Number of subtitle segments per video',
    buckets=[10, 20, 50, 100, 200, 500, 1000]
)

subtitle_sync_drift_seconds = Histogram(
    'subtitle_sync_drift_seconds',
    'Audio-video sync drift',
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
)


# Context Manager para instrumentar funções
from contextlib import contextmanager
import time

@contextmanager
def measure_duration(metric: Histogram, labels: dict = None):
    """
    Context manager para medir duração
    
    Uso:
        with measure_duration(pipeline_stage_duration_seconds, {'stage': 'concat'}):
            await concatenate_videos(...)
    """
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        if labels:
            metric.labels(**labels).observe(duration)
        else:
            metric.observe(duration)
```

##### 3.2: Instrumentar Código

**Exemplo em celery_tasks.py:**

```python
from app.infrastructure.metrics import (
    measure_duration,
    pipeline_stage_duration_seconds,
    pipeline_jobs_total,
    pipeline_jobs_active,
    video_processing_shorts_count
)

async def process_make_video(job_id: str):
    """Task com métricas completas"""
    
    # Incrementar gauge de jobs ativos
    pipeline_jobs_active.inc()
    
    try:
        # Etapa 1: Analyzing Audio
        with measure_duration(
            pipeline_stage_duration_seconds,
            {'stage': 'analyzing_audio', 'job_id': job_id}
        ):
            audio_duration = await analyze_audio(audio_path)
        
        # Etapa 2: Fetching Shorts
        with measure_duration(
            pipeline_stage_duration_seconds,
            {'stage': 'fetching_shorts', 'job_id': job_id}
        ):
            shorts = await fetch_shorts(query, max_results)
        
        # ... todas as etapas ...
        
        # Success
        pipeline_jobs_total.labels(status='completed').inc()
        
    except Exception as e:
        pipeline_jobs_total.labels(status='failed').inc()
        raise
    
    finally:
        pipeline_jobs_active.dec()
```

**Critério de Aceite:**
- ✅ Métricas em todas as etapas do pipeline
- ✅ Dashboard Grafana mostrando P50/P95/P99
- ✅ Alertas baseados em SLOs

---

### Task 4: Circuit Breaker Distribuído (Redis-based)

**Story Points:** 5  
**Prioridade:** P1  
**Impacto:** Proteção multi-worker

#### Descrição
Migrar circuit breaker in-memory para Redis para funcionar com múltiplos workers.

#### Sub-tasks

##### 4.1: Implementar Circuit Breaker Distribuído

**Arquivo:** `app/infrastructure/distributed_circuit_breaker.py` (NOVO)

```python
"""
Distributed Circuit Breaker using Redis

Shares circuit breaker state across multiple workers.
"""
import logging
import time
from enum import Enum
from typing import Optional
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class DistributedCircuitBreaker:
    """Circuit breaker com estado no Redis"""
    
    def __init__(
        self,
        redis_client: aioredis.Redis,
        service_name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3
    ):
        self.redis = redis_client
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.timeout = timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        
        # Redis keys
        self.state_key = f"cb:{service_name}:state"
        self.failures_key = f"cb:{service_name}:failures"
        self.last_failure_key = f"cb:{service_name}:last_failure"
        self.half_open_calls_key = f"cb:{service_name}:half_open_calls"
    
    async def is_open(self) -> bool:
        """Verifica se circuit está aberto"""
        state = await self._get_state()
        
        if state == CircuitState.CLOSED:
            return False
        
        if state == CircuitState.OPEN:
            # Verificar se deve transicionar para HALF_OPEN
            last_failure = await self.redis.get(self.last_failure_key)
            if last_failure:
                elapsed = time.time() - float(last_failure)
                if elapsed >= self.timeout:
                    await self._transition_to_half_open()
                    return False
            return True
        
        if state == CircuitState.HALF_OPEN:
            # Permitir chamadas limitadas
            calls = await self.redis.get(self.half_open_calls_key)
            calls = int(calls) if calls else 0
            
            if calls < self.half_open_max_calls:
                await self.redis.incr(self.half_open_calls_key)
                return False
            return True
        
        return False
    
    async def record_success(self):
        """Registra sucesso"""
        state = await self._get_state()
        
        if state == CircuitState.HALF_OPEN:
            # Transição HALF_OPEN → CLOSED
            await self._transition_to_closed()
            logger.info(f"✅ Circuit breaker CLOSED: {self.service_name}")
        
        # Reset failures
        await self.redis.delete(self.failures_key)
    
    async def record_failure(self):
        """Registra falha"""
        failures = await self.redis.incr(self.failures_key)
        await self.redis.set(self.last_failure_key, time.time())
        
        state = await self._get_state()
        
        if state == CircuitState.HALF_OPEN:
            # Falha em HALF_OPEN → volta para OPEN
            await self._transition_to_open()
            logger.warning(f"⚠️ Circuit breaker OPEN (half-open failed): {self.service_name}")
        
        elif failures >= self.failure_threshold:
            # Threshold atingido → OPEN
            await self._transition_to_open()
            logger.warning(
                f"⚠️ Circuit breaker OPEN: {self.service_name} "
                f"({failures} failures)"
            )
    
    async def _get_state(self) -> CircuitState:
        """Obter estado atual"""
        state = await self.redis.get(self.state_key)
        return CircuitState(state.decode()) if state else CircuitState.CLOSED
    
    async def _transition_to_closed(self):
        """Transição para CLOSED"""
        await self.redis.set(self.state_key, CircuitState.CLOSED.value)
        await self.redis.delete(self.failures_key)
        await self.redis.delete(self.half_open_calls_key)
        
        from app.infrastructure.metrics import circuit_breaker_state
        circuit_breaker_state.labels(service=self.service_name).set(0)
    
    async def _transition_to_open(self):
        """Transição para OPEN"""
        await self.redis.set(self.state_key, CircuitState.OPEN.value)
        
        from app.infrastructure.metrics import circuit_breaker_state
        circuit_breaker_state.labels(service=self.service_name).set(1)
    
    async def _transition_to_half_open(self):
        """Transição para HALF_OPEN"""
        await self.redis.set(self.state_key, CircuitState.HALF_OPEN.value)
        await self.redis.set(self.half_open_calls_key, 0)
        
        from app.infrastructure.metrics import circuit_breaker_state
        circuit_breaker_state.labels(service=self.service_name).set(2)
        
        logger.info(f"🔄 Circuit breaker HALF_OPEN: {self.service_name}")
```

##### 4.2: Integrar em APIs Externas

**Arquivo:** `app/api/api_client.py`

```python
from app.infrastructure.distributed_circuit_breaker import DistributedCircuitBreaker

class MicroservicesClient:
    def __init__(self, ...):
        # ...
        
        # Circuit breakers distribuídos
        self.breakers = {
            'youtube-search': DistributedCircuitBreaker(
                redis_client=redis_client,
                service_name='youtube-search',
                failure_threshold=5,
                timeout_seconds=60
            ),
            'video-downloader': DistributedCircuitBreaker(
                redis_client=redis_client,
                service_name='video-downloader',
                failure_threshold=5,
                timeout_seconds=60
            ),
            'audio-transcriber': DistributedCircuitBreaker(
                redis_client=redis_client,
                service_name='audio-transcriber',
                failure_threshold=5,
                timeout_seconds=120  # Transcrição demora mais
            ),
        }
    
    async def search_shorts(self, query, max_results):
        """Busca com circuit breaker"""
        breaker = self.breakers['youtube-search']
        
        # Verificar circuit
        if await breaker.is_open():
            raise MicroserviceException(
                "Circuit breaker is OPEN for youtube-search",
                ErrorCode.API_UNAVAILABLE,
                "youtube-search"
            )
        
        try:
            result = await self._search_shorts_internal(query, max_results)
            await breaker.record_success()
            return result
        
        except Exception as e:
            await breaker.record_failure()
            raise
```

**Critério de Aceite:**
- ✅ Circuit breaker compartilhado entre workers
- ✅ Estado persiste no Redis
- ✅ Métricas de transições de estado

---

### Task 5: Validação de Entrada (R-014)

**Story Points:** 3  
**Prioridade:** P2  
**Impacto:** -20% erros tardios

#### Descrição
Adicionar validação de tamanho/formato/duração no upload de áudio.

#### Sub-tasks

##### 5.1: Criar Validador de Upload

**Arquivo:** `app/shared/validation.py`

```python
"""
Input validation for API requests
"""
import os
import magic
from pathlib import Path
from fastapi import UploadFile, HTTPException


class AudioFileValidator:
    """Valida arquivos de áudio no upload"""
    
    MAX_SIZE_MB = 50
    MAX_DURATION_SEC = 600  # 10 minutos
    
    ALLOWED_FORMATS = {
        'audio/mpeg',  # MP3
        'audio/wav',
        'audio/x-wav',
        'audio/mp4',
        'audio/m4a',
        'audio/ogg'
    }
    
    @staticmethod
    async def validate(
        audio_file: UploadFile,
        max_size_mb: int = MAX_SIZE_MB,
        max_duration_sec: int = MAX_DURATION_SEC
    ):
        """
        Valida arquivo de áudio
        
        Raises:
            HTTPException: Se validação falhar
        """
        # 1. Validar tamanho
        audio_file.file.seek(0, os.SEEK_END)
        size_bytes = audio_file.file.tell()
        audio_file.file.seek(0)
        
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > max_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"Audio file too large: {size_mb:.1f}MB (max: {max_size_mb}MB)"
            )
        
        # 2. Validar formato (magic bytes)
        header = audio_file.file.read(2048)
        audio_file.file.seek(0)
        
        mime_type = magic.from_buffer(header, mime=True)
        
        if mime_type not in AudioFileValidator.ALLOWED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid audio format: {mime_type}. Allowed: {', '.join(AudioFileValidator.ALLOWED_FORMATS)}"
            )
        
        # 3. Validar duração (após salvar temp)
        # (implementado após salvar arquivo temporário em /create endpoint)
```

##### 5.2: Aplicar no Endpoint

**Arquivo:** `app/main.py`

```python
from app.shared.validation import AudioFileValidator

@app.post("/create")
async def create_video(
    audio_file: UploadFile = File(...),
    ...
):
    # Validar ANTES de processar
    await AudioFileValidator.validate(
        audio_file,
        max_size_mb=50,
        max_duration_sec=600
    )
    
    # ... resto do código ...
```

**Critério de Aceite:**
- ✅ Upload >50MB rejeitado com 400
- ✅ Formato não-áudio rejeitado com 400
- ✅ Validação rápida (<100ms)

---

## 🧪 Plano de Testes

### Testes Unitários
```bash
pytest tests/test_dual_job_store.py -v
pytest tests/test_structured_logging.py -v
pytest tests/test_distributed_circuit_breaker.py -v
pytest tests/test_audio_validation.py -v
```

### Testes de Integração
```bash
# Redis failure recovery
pytest tests/integration/test_redis_failover.py

# Métricas
pytest tests/integration/test_metrics_collection.py

# Circuit breaker multi-worker
pytest tests/integration/test_circuit_breaker_distributed.py
```

### Testes de Chaos
```bash
# Restart Redis mid-job
pytest tests/chaos/test_redis_restart.py

# Simulate API failures
pytest tests/chaos/test_api_circuit_breaker.py
```

---

## 📊 Métricas de Validação

### Antes da Sprint
- Tempo de debug: 30-60min
- Jobs perdidos por restart Redis: 100%
- Visibilidade de bottlenecks: 0%

### Após Sprint
- Tempo de debug: <5min (-90%)
- Jobs perdidos: 0% (-100%)
- Latência por etapa visível: 100%

---

## ✅ Definition of Done

- [ ] 5 tasks implementadas
- [ ] Dual-store funcional (Redis + SQLite)
- [ ] 100% logs críticos em JSON
- [ ] Métricas Prometheus completas
- [ ] Circuit breaker distribuído ativo
- [ ] Dashboard Grafana atualizado
- [ ] Testes 100% passando
- [ ] Deployed e validado

---

**Próxima Sprint:** SPRINT-RESILIENCE-03.md (Estrutural)
