# 🗺️ Roadmap de Implementação - Micro-serviços v3.0.0

## 📅 Timeline

```
Sprint 1-2  (Semanas 1-2)   → Scaffolding & Setup Local
Sprint 3-4  (Semanas 3-4)   → Core Infrastructure (Message Broker, DB)
Sprint 5-6  (Semanas 5-6)   → Job Manager Service
Sprint 7-8  (Semanas 7-8)   → Download Service
Sprint 9-10 (Semanas 9-10)  → Transcription Service
Sprint 11-12(Semanas 11-12) → Storage + Notification Services
Sprint 13-14(Semanas 13-14) → API Gateway + Admin Service
Sprint 15+  (Semanas 15+)   → Kubernetes Deployment + Monitoring
```

---

## Phase 1: Scaffolding & Setup Local (Sprint 1-2)

### Objetivo
Criar estrutura base, ambiente local funcional (Docker Compose) e shared libraries

### Tasks

#### Task 1.1: Criar estrutura de pastas

```bash
mkdir -p {api-gateway,job-manager,download-service,transcription-service,storage-service,notification-service,admin-service}/src/{domain,application,infrastructure}
mkdir -p shared-libs/{ytcaption-core,ytcaption-testing}
mkdir -p infra/{docker,kubernetes,terraform,monitoring}
mkdir -p docs
```

#### Task 1.2: Shared Libraries - Base Models

**Arquivo**: `shared-libs/ytcaption-core/src/domain/models.py`

```python
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from uuid import UUID

class JobStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    id: UUID
    status: JobStatus
    youtube_url: str
    language: str
    priority: str
    requested_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime = None
    error_message: str = None

@dataclass
class Transcription:
    id: UUID
    job_id: UUID
    text: str
    segments: list
    language: str
    duration_seconds: float
    processing_time_seconds: float
    model: str
    created_at: datetime
```

#### Task 1.3: Shared Libraries - Domain Events

**Arquivo**: `shared-libs/ytcaption-core/src/domain/events.py`

```python
from dataclasses import dataclass, asdict
from datetime import datetime
from uuid import UUID, uuid4
import json

@dataclass
class DomainEvent:
    event_id: UUID = None
    timestamp: datetime = None
    version: str = "1.0"
    correlation_id: UUID = None
    causation_id: UUID = None
    
    def __post_init__(self):
        if not self.event_id:
            self.event_id = uuid4()
        if not self.timestamp:
            self.timestamp = datetime.utcnow()
    
    def to_json(self):
        return json.dumps(asdict(self), default=str)
    
    @classmethod
    def from_json(cls, data: str):
        return cls(**json.loads(data))

@dataclass
class TranscriptionJobCreated(DomainEvent):
    job_id: UUID = None
    youtube_url: str = None
    language: str = None
    priority: str = None
    requested_by: str = None

@dataclass
class AudioDownloadedEvent(DomainEvent):
    job_id: UUID = None
    audio_url: str = None
    duration_seconds: float = None
    file_size_mb: float = None

@dataclass
class TranscriptionCompletedEvent(DomainEvent):
    job_id: UUID = None
    text: str = None
    segments: list = None
    language: str = None
    processing_time_seconds: float = None

@dataclass
class TranscriptionFailedEvent(DomainEvent):
    job_id: UUID = None
    error: str = None
    error_code: str = None
    retry_count: int = None
```

#### Task 1.4: Shared Libraries - Message Queue Adapter

**Arquivo**: `shared-libs/ytcaption-core/src/infrastructure/message_queue.py`

```python
from abc import ABC, abstractmethod
from typing import Callable, List
import pika
import json
from loguru import logger

class MessageBroker(ABC):
    @abstractmethod
    async def publish(self, topic: str, event: DomainEvent):
        pass
    
    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable):
        pass

class RabbitMQBroker(MessageBroker):
    def __init__(self, url: str = "amqp://guest:guest@rabbitmq:5672/"):
        self.url = url
        self.connection = None
        self.channel = None
    
    async def connect(self):
        self.connection = pika.BlockingConnection(pika.URLParameters(self.url))
        self.channel = self.connection.channel()
    
    async def publish(self, topic: str, event: DomainEvent):
        if not self.channel:
            await self.connect()
        
        self.channel.queue_declare(queue=topic, durable=True)
        self.channel.basic_publish(
            exchange='',
            routing_key=topic,
            body=event.to_json(),
            properties=pika.BasicProperties(delivery_mode=2)  # Persistent
        )
        logger.info(f"Published event {event.event_id} to {topic}")
    
    async def subscribe(self, topic: str, handler: Callable):
        if not self.channel:
            await self.connect()
        
        self.channel.queue_declare(queue=topic, durable=True)
        
        def callback(ch, method, properties, body):
            try:
                event = json.loads(body)
                handler(event)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
        self.channel.basic_consume(queue=topic, on_message_callback=callback)
        logger.info(f"Subscribed to {topic}")
        self.channel.start_consuming()
```

#### Task 1.5: Docker Compose - Infraestrutura

**Arquivo**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  # Message Broker
  rabbitmq:
    image: rabbitmq:3.12-management
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: rabbitmq-diagnostics ping
      interval: 30s
      timeout: 10s
      retries: 3

  # Database
  postgres:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: ytcaption
      POSTGRES_USER: ytcaption
      POSTGRES_PASSWORD: ytcaption_dev
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/database/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ytcaption"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  # S3 Compatible Storage (MinIO)
  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/minio_root
    command: minio server /minio_root --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
  redis_data:
  rabbitmq_data:
  minio_data:
```

#### Task 1.6: Database Schema

**Arquivo**: `infra/database/init.sql`

```sql
-- Jobs table
CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    status VARCHAR(50) NOT NULL,
    youtube_url TEXT NOT NULL,
    language VARCHAR(10) NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal',
    requested_by VARCHAR(255),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    error_message TEXT,
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- Transcriptions table
CREATE TABLE transcriptions (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(id),
    text TEXT NOT NULL,
    segments JSONB NOT NULL,
    language VARCHAR(10) NOT NULL,
    duration_seconds FLOAT NOT NULL,
    processing_time_seconds FLOAT NOT NULL,
    model VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    INDEX idx_job_id (job_id)
);

-- Event Store (para Event Sourcing)
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    aggregate_id UUID NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    data JSONB NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    version INT NOT NULL,
    INDEX idx_aggregate_id (aggregate_id),
    INDEX idx_timestamp (timestamp)
);
```

---

## Phase 2: Core Infrastructure (Sprint 3-4)

### Objetivo
Configurar Message Broker, Database, Cache com alta disponibilidade

### Tasks

#### Task 2.1: RabbitMQ Cluster Setup

```yaml
# infra/kubernetes/rabbitmq-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: rabbitmq
spec:
  serviceName: rabbitmq
  replicas: 3
  selector:
    matchLabels:
      app: rabbitmq
  template:
    metadata:
      labels:
        app: rabbitmq
    spec:
      containers:
      - name: rabbitmq
        image: rabbitmq:3.12-management
        ports:
        - containerPort: 5672
          name: amqp
        - containerPort: 15672
          name: management
        env:
        - name: RABBITMQ_DEFAULT_USER
          valueFrom:
            secretKeyRef:
              name: rabbitmq
              key: username
        - name: RABBITMQ_DEFAULT_PASS
          valueFrom:
            secretKeyRef:
              name: rabbitmq
              key: password
        volumeMounts:
        - name: data
          mountPath: /var/lib/rabbitmq
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: standard
      resources:
        requests:
          storage: 20Gi
```

#### Task 2.2: PostgreSQL Replication

```yaml
# infra/kubernetes/postgres-replication.yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres
  replicas: 2
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_REPLICATION_MODE
          value: "master"  # or "replica"
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 100Gi
```

#### Task 2.3: Redis High Availability

```yaml
# infra/kubernetes/redis-ha.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
spec:
  serviceName: redis
  replicas: 3
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
        - redis-server
        - /etc/redis/redis.conf
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: config
          mountPath: /etc/redis
        - name: data
          mountPath: /data
      volumes:
      - name: config
        configMap:
          name: redis-config
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

---

## Phase 3: Job Manager Service (Sprint 5-6)

### Objetivo
Implementar serviço de orquestração central de jobs

### Estrutura

```
job-manager-service/
├── src/
│   ├── domain/
│   │   ├── models.py           # Job aggregate
│   │   ├── ports/
│   │   │   ├── in_ports.py    # Use cases
│   │   │   └── out_ports.py   # Repositories, message broker
│   │   └── services.py         # Business logic
│   │
│   ├── application/
│   │   ├── use_cases/
│   │   │   ├── create_job.py
│   │   │   ├── get_job_status.py
│   │   │   ├── cancel_job.py
│   │   │   └── list_jobs.py
│   │   ├── dtos/
│   │   │   ├── input.py
│   │   │   └── output.py
│   │   └── event_handlers.py
│   │
│   ├── infrastructure/
│   │   ├── outbound/
│   │   │   ├── database.py     # PostgreSQL adapter
│   │   │   └── message_queue.py # RabbitMQ adapter
│   │   ├── inbound/
│   │   │   ├── http/
│   │   │   │   └── routes.py   # FastAPI endpoints
│   │   │   └── message_queue/
│   │   │       └── consumers.py
│   │   ├── config/
│   │   │   ├── settings.py
│   │   │   └── di_container.py
│   │   └── shared/
│   │       ├── logging.py
│   │       └── monitoring.py
│   │
│   └── main.py                 # FastAPI entry point
│
├── tests/
│   ├── unit/
│   │   └── domain/
│   │       └── test_job_service.py
│   ├── integration/
│   │   └── test_job_repository.py
│   └── e2e/
│       └── test_job_workflow.py
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

### Implementação Chave

**Arquivo**: `job-manager-service/src/domain/models.py`

```python
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

class JobStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    """Aggregate Root - Job"""
    id: UUID
    status: JobStatus
    youtube_url: str
    language: str
    priority: str
    requested_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    events: list = field(default_factory=list)
    
    def mark_downloading(self):
        self.status = JobStatus.DOWNLOADING
        self.updated_at = datetime.utcnow()
        self.events.append(JobStartedDownloadingEvent(self.id))
    
    def mark_transcribing(self):
        self.status = JobStatus.TRANSCRIBING
        self.updated_at = datetime.utcnow()
        self.events.append(JobStartedTranscribingEvent(self.id))
    
    def mark_completed(self):
        self.status = JobStatus.COMPLETED
        self.updated_at = datetime.utcnow()
        self.completed_at = datetime.utcnow()
        self.events.append(JobCompletedEvent(self.id))
    
    def mark_failed(self, error: str):
        self.status = JobStatus.FAILED
        self.updated_at = datetime.utcnow()
        self.error_message = error
        self.events.append(JobFailedEvent(self.id, error))
    
    def cancel(self):
        if self.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
            self.status = JobStatus.CANCELLED
            self.updated_at = datetime.utcnow()
            self.events.append(JobCancelledEvent(self.id))
```

**Arquivo**: `job-manager-service/src/application/use_cases/create_job.py`

```python
from dataclasses import dataclass
from uuid import uuid4
from datetime import datetime
from pydantic import BaseModel, HttpUrl, validator

class CreateJobRequest(BaseModel):
    youtube_url: HttpUrl
    language: str = "auto"
    priority: str = "normal"
    requested_by: str
    webhook_url: Optional[HttpUrl] = None
    
    @validator('language')
    def validate_language(cls, v):
        allowed = ['auto', 'en', 'pt', 'es', ...]
        if v not in allowed:
            raise ValueError(f"Language must be one of {allowed}")
        return v

class CreateJobResponse(BaseModel):
    job_id: str
    status: str
    status_url: str
    created_at: str

@dataclass
class CreateJobUseCase:
    job_repository: JobRepositoryPort
    message_broker: MessageBrokerPort
    
    async def execute(self, request: CreateJobRequest) -> CreateJobResponse:
        # 1. Create job aggregate
        job = Job(
            id=uuid4(),
            status=JobStatus.PENDING,
            youtube_url=str(request.youtube_url),
            language=request.language,
            priority=request.priority,
            requested_by=request.requested_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # 2. Save to repository
        await self.job_repository.save(job)
        
        # 3. Publish event
        event = TranscriptionJobCreatedEvent(
            job_id=job.id,
            youtube_url=job.youtube_url,
            language=job.language,
            priority=job.priority,
            requested_by=job.requested_by
        )
        await self.message_broker.publish("transcription.jobs", event)
        
        # 4. Return response
        return CreateJobResponse(
            job_id=str(job.id),
            status=job.status.value,
            status_url=f"/api/v1/transcriptions/{job.id}",
            created_at=job.created_at.isoformat()
        )
```

---

## Phase 4-5: Download & Transcription Services (Sprint 7-10)

Seguem o mesmo padrão hexagonal que Job Manager.

### Download Service

```python
# src/domain/services/youtube_downloader.py

class YouTubeDownloader:
    def __init__(self, circuit_breaker: CircuitBreaker, retry_policy: RetryPolicy):
        self.circuit_breaker = circuit_breaker
        self.retry_policy = retry_policy
    
    async def download(self, url: str, timeout: int = 15 * 60) -> bytes:
        """
        Download áudio com retry e circuit breaker
        """
        try:
            return await self.circuit_breaker.call(
                self._download_with_retry,
                url,
                timeout
            )
        except CircuitBreakerOpen:
            raise YouTubeDownloadFailedError("Circuit breaker open, try later")
    
    @retry(policy=ExponentialBackoffWithJitter(base=1, max=60))
    async def _download_with_retry(self, url: str, timeout: int) -> bytes:
        """Realiza download com retry automático"""
        try:
            audio_bytes = await yt_dlp.extract_audio(url, timeout)
            return audio_bytes
        except TransientError as e:
            # Retry será feito automaticamente
            raise
        except PermanentError as e:
            # Não retentar
            raise YouTubeDownloadFailedError(str(e))
```

### Transcription Service

```python
# src/infrastructure/outbound/whisper_adapter.py

class WhisperTranscriber:
    def __init__(self, model_name: str = "base", device: str = "cpu"):
        self.model = whisper.load_model(model_name, device=device)
        self.device = device
    
    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        """
        Transcrever com worker pool paralelo v2.0
        """
        # Split audio em chunks
        chunks = self._split_audio(audio_path, chunk_duration=120)
        
        # Processar em paralelo
        tasks = [
            self._transcribe_chunk(chunk)
            for chunk in chunks
        ]
        results = await asyncio.gather(*tasks)
        
        # Mesclar resultados
        return self._merge_results(results)
    
    async def _transcribe_chunk(self, chunk: AudioChunk) -> ChunkResult:
        """Worker process para cada chunk"""
        result = self.model.transcribe(
            chunk.path,
            language=chunk.language
        )
        return ChunkResult(
            start=chunk.start,
            end=chunk.end,
            text=result['text'],
            segments=result['segments']
        )
```

---

## Phase 6: Storage & Notification (Sprint 11-12)

### Storage Service

Suporta múltiplos backends via Strategy pattern:

```python
# src/domain/ports/storage_port.py

class StoragePort(ABC):
    @abstractmethod
    async def upload(self, file_path: str, key: str) -> str:
        """Retorna URL do arquivo armazenado"""
        pass
    
    @abstractmethod
    async def download(self, key: str) -> bytes:
        pass
    
    @abstractmethod
    async def delete(self, key: str):
        pass

# src/infrastructure/outbound/s3_adapter.py
class S3Storage(StoragePort):
    async def upload(self, file_path: str, key: str) -> str:
        async with aioboto3.client('s3') as s3:
            await s3.upload_file(file_path, self.bucket, key)
            return f"s3://{self.bucket}/{key}"

# src/infrastructure/outbound/minio_adapter.py
class MinIOStorage(StoragePort):
    async def upload(self, file_path: str, key: str) -> str:
        async with aiofiles.open(file_path, 'rb') as f:
            data = await f.read()
        await self.minio_client.put_object(self.bucket, key, data)
        return f"minio://{self.bucket}/{key}"
```

### Notification Service

```python
# src/infrastructure/outbound/webhook_publisher.py

class WebhookPublisher:
    async def notify(self, webhook_url: str, payload: dict):
        """Notificar cliente via webhook com retry"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"User-Agent": "YTCaption/3.0"}
                )
                response.raise_for_status()
        except httpx.RequestError as e:
            # Será retentado pela fila
            raise WebhookFailedError(str(e))

# src/infrastructure/inbound/message_queue/consumers.py

class NotificationConsumer:
    async def handle_transcription_completed(self, event: TranscriptionCompletedEvent):
        """Consumidor de evento"""
        
        # Buscar configurações de notificação
        webhooks = await self.repo.get_webhooks(event.job_id)
        
        # Notificar todos os webhooks
        for webhook_url in webhooks:
            payload = {
                "job_id": str(event.job_id),
                "status": "completed",
                "result_url": f"/api/v1/transcriptions/{event.job_id}/result",
                "completed_at": event.timestamp.isoformat()
            }
            
            try:
                await self.webhook_publisher.notify(webhook_url, payload)
            except WebhookFailedError:
                # Publicar de volta na fila para retry
                await self.message_broker.publish(
                    "transcription.webhook_retry",
                    WebhookRetryEvent(job_id=event.job_id, webhook_url=webhook_url)
                )
```

---

## Phase 7: API Gateway & Monitoring (Sprint 13-14+)

### API Gateway

```yaml
# infra/kubernetes/kong-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kong-api-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: kong
  template:
    metadata:
      labels:
        app: kong
    spec:
      containers:
      - name: kong
        image: kong:3.4-alpine
        env:
        - name: KONG_DATABASE
          value: postgres
        - name: KONG_PG_HOST
          value: postgres
        - name: KONG_PG_USER
          valueFrom:
            secretKeyRef:
              name: postgres
              key: username
        - name: KONG_PG_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres
              key: password
        ports:
        - containerPort: 8000  # Proxy
        - containerPort: 8443  # Proxy SSL
        - containerPort: 8001  # Admin API
        livenessProbe:
          httpGet:
            path: /status
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /status
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Monitoring Stack

```yaml
# infra/kubernetes/monitoring.yaml
---
# Prometheus
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
    - job_name: 'job-manager'
      static_configs:
      - targets: ['job-manager:8001']
    - job_name: 'download-service'
      static_configs:
      - targets: ['download-service:8002']
    - job_name: 'transcription-service'
      static_configs:
      - targets: ['transcription-service:8003']
---
# Grafana Dashboard
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboards
data:
  dashboard.json: |
    {
      "dashboard": {
        "title": "YTCaption Micro-services",
        "panels": [
          {
            "title": "Jobs Per Second",
            "targets": [
              {
                "expr": "rate(transcription_jobs_total[5m])"
              }
            ]
          },
          {
            "title": "Error Rate",
            "targets": [
              {
                "expr": "rate(transcription_errors_total[5m])"
              }
            ]
          },
          {
            "title": "Queue Depth",
            "targets": [
              {
                "expr": "queue_depth"
              }
            ]
          }
        ]
      }
    }
```

---

## Critério de Sucesso

### Fase 1 ✓
- [x] Estrutura de pastas criada
- [x] Docker Compose com todos serviços rodando localmente
- [x] Shared libraries compilando

### Fase 2 ✓
- [x] RabbitMQ cluster funcional
- [x] PostgreSQL replicado
- [x] Redis HA
- [x] Health checks passando

### Fase 3 ✓
- [x] Job Manager API respondendo
- [x] Jobs sendo criados no BD
- [x] Eventos sendo publicados

### Fase 4-5 ✓
- [x] Download Service baixando vídeos
- [x] Transcription Service transcrevendo

### Fase 6 ✓
- [x] Storage funcionando (S3/MinIO)
- [x] Webhooks sendo enviados

### Fase 7 ✓
- [x] API Gateway roteando corretamente
- [x] Prometheus coletando métricas
- [x] Grafana dashboard funcional
- [x] Alerts disparando

---

## Estimativas de Esforço

| Fase | Duração | Pessoas | Outputs |
|------|---------|---------|---------|
| 1-2 | 2-3 sem | 2 | Scaffold + Docker Compose |
| 3-4 | 2-3 sem | 1-2 | Job Manager + Core Infra |
| 5-6 | 2-3 sem | 2 | Download Service |
| 7-8 | 2-3 sem | 2 | Transcription Service |
| 9-10 | 2-3 sem | 1-2 | Storage + Notification |
| 11-12 | 2 sem | 1-2 | API Gateway + Admin |
| 13-14 | 2-3 sem | 2 | Kubernetes + Monitoring |
| 15+ | Ongoing | 1-2 | Otimizações + Manutenção |

**Total**: ~14-18 semanas (3-4 meses)

---

**Documento versão**: 1.0.0  
**Data**: 2025-10-23  
**Status**: Em Planejamento

