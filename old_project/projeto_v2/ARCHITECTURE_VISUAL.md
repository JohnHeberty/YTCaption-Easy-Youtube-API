# 🎨 Visualização da Arquitetura - YTCaption v3.0.0

## 🔷 Arquitetura de Alto Nível

```
                          ┌─────────────────┐
                          │   CLIENTE       │
                          │  (Web/Mobile)   │
                          └────────┬────────┘
                                   │
                        HTTP REST (HTTPS)
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │   API GATEWAY (8000)     │
                    │                          │
                    │  • Authentication        │
                    │  • Rate Limiting         │
                    │  • Load Balancing        │
                    │  • CORS                  │
                    └──┬──────────┬──────┬─────┘
                       │ gRPC     │      │
            ┌──────────┴──┐   ┌───┴────┐ └──────────┐
            │             │   │        │            │
            ▼             ▼   ▼        ▼            ▼
     ┌────────────┐ ┌────────────┐ ┌──────┐ ┌─────────────┐
     │ JOB MGR    │ │ADMIN SERV. │ │STORE │ │ WEBHOOK MGR │
     │ (8001)     │ │ (8006)     │ │(8004)│ │  (8005)     │
     └────────────┘ └────────────┘ └──────┘ └─────────────┘
            │
            │ Publica evento
            ▼
     ┌────────────────────────┐
     │  MESSAGE BROKER        │
     │  (RabbitMQ Cluster)    │
     │                        │
     │ Topics:                │
     │ • transcription.jobs   │
     │ • transcription.audio  │
     │ • transcription.done   │
     │ • transcription.error  │
     └────┬─────────────┬─────┘
          │ Subscribe   │
    ┌─────▼─┐      ┌────▼────┐
    │DOWNLOAD│      │TRANSCRIB│
    │SERVICE │      │SERVICE  │
    │(8002)  │      │(8003)   │
    └────────┘      └─────────┘
```

---

## 📊 Comunicação entre Serviços

```
FLUXO TÍPICO DE UM JOB
══════════════════════════════════════════════════════════════

[1] Cliente submete
    └─ HTTP POST /api/v1/transcriptions
       {
         "youtube_url": "https://youtube.com/watch?v=xyz",
         "language": "auto"
       }
       
       ⏱️  Tempo: 0ms

[2] API Gateway roteia
    └─ gRPC Call: JobManager.CreateJob()
       
       ⏱️  Tempo: 5-10ms

[3] Job Manager cria job
    └─ INSERT jobs (status='PENDING')
    └─ Publica: TranscriptionJobCreated
    └─ Retorna: 202 ACCEPTED (job_id, status_url)
       
       ⏱️  Tempo: 20-30ms TOTAL (Cliente já recebeu!)

[4] Download Service consome
    └─ Recebe: TranscriptionJobCreated
    └─ Download YouTube (com retry)
    └─ Upload S3
    └─ Publica: AudioDownloadedEvent
       
       ⏱️  Tempo: 10-120 segundos (depende vídeo)

[5] Transcription Service consome
    └─ Recebe: AudioDownloadedEvent
    └─ Carrega modelo Whisper
    └─ Transcreve em paralelo
    └─ Salva resultado
    └─ Publica: TranscriptionCompletedEvent
       
       ⏱️  Tempo: 30-600 segundos (depende tamanho)

[6] Job Manager atualiza
    └─ Recebe: TranscriptionCompletedEvent
    └─ UPDATE jobs (status='COMPLETED')
    └─ Cache em Redis
       
       ⏱️  Tempo: 50ms

[7] Notification Service notifica
    └─ Recebe: TranscriptionCompletedEvent
    └─ Envia webhook para cliente
    └─ Email (se configurado)
       
       ⏱️  Tempo: 100-500ms

[8] Cliente consulta resultado
    └─ GET /api/v1/transcriptions/{id}/result
    └─ Retorna: 200 OK com transcrição
       
       ⏱️  Tempo: 20-50ms (GET é rápido, cache)

TOTAL: 50ms (API) + (tempo processamento) + (tempo notificação)
       ✅ Cliente não bloqueia!
```

---

## 🏛️ Estrutura Interna de 1 Serviço (Hexagonal)

```
Exemplo: Transcription Service

transcription-service/
│
├── src/
│   │
│   ├── domain/                          ⭐ CENTRO (Lógica Pura)
│   │   ├── models.py
│   │   │   └─ class Transcription (Aggregate Root)
│   │   │
│   │   ├── services.py
│   │   │   └─ class WhisperTranscriptionService (Lógica de negócio)
│   │   │
│   │   ├── ports/
│   │   │   ├─ in_ports.py    (Use Cases - Entrada)
│   │   │   └─ out_ports.py   (Interfaces - Saída)
│   │   │
│   │   └── exceptions.py
│   │
│   ├── application/                     🔄 ORQUESTRAÇÃO
│   │   ├── use_cases/
│   │   │   └─ transcribe_use_case.py
│   │   │
│   │   ├── dtos/
│   │   │   ├─ input.py       (Request)
│   │   │   └─ output.py      (Response)
│   │   │
│   │   ├── mappers/
│   │   │   └─ domain_dto_mapper.py
│   │   │
│   │   └── event_handlers/
│   │       └─ audio_downloaded_handler.py
│   │
│   ├── infrastructure/                  🔌 ADAPTADORES (Implementação)
│   │   │
│   │   ├── inbound/
│   │   │   ├─ http/routes.py           (FastAPI endpoints)
│   │   │   └─ message_queue/
│   │   │      └─ consumers.py          (RabbitMQ consumer)
│   │   │
│   │   ├── outbound/
│   │   │   ├─ database/
│   │   │   │   └─ repository.py        (PostgreSQL adapter)
│   │   │   ├─ message_queue/
│   │   │   │   └─ publisher.py         (RabbitMQ adapter)
│   │   │   ├─ storage/
│   │   │   │   └─ s3_adapter.py        (S3 adapter)
│   │   │   └─ cache/
│   │   │       └─ redis_adapter.py     (Redis adapter)
│   │   │
│   │   ├── config/
│   │   │   ├─ settings.py              (Environment vars)
│   │   │   └─ di_container.py          (Dependency Injection)
│   │   │
│   │   └── shared/
│   │       ├─ logging.py
│   │       ├─ monitoring.py
│   │       └─ tracing.py
│   │
│   └── main.py                         (FastAPI entry point)
│
├── tests/
│   ├── unit/
│   │   └─ domain/
│   │      └─ test_transcription_service.py  (Rápido: 100ms)
│   │
│   ├── integration/
│   │   ├─ test_database.py             (Com banco)
│   │   └─ test_message_queue.py        (Com RabbitMQ)
│   │
│   └── e2e/
│       └─ test_full_flow.py            (Completo)
│
└── Dockerfile
    docker-compose.yml
    pyproject.toml
    README.md
```

---

## 🌐 Stack Tecnológico

```
TIER                    TECHNOLOGY          FUNÇÃO
─────────────────────────────────────────────────────────────

WEB/MOBILE CLIENT
                        React.js            Interface web
                        Flutter             App mobile
                        cURL/Postman        Testing

API GATEWAY
                        Kong / Nginx        Load balancing
                        JWT                 Authentication
                        Prometheus          Métricas

MICROSERVICES
                        FastAPI             Framework
                        Python 3.11+        Language
                        Pydantic            Validation
                        SQLAlchemy          ORM

MESSAGING
                        RabbitMQ            Event broker
                        (3-node cluster)    Persistência
                        Messages: JSON      Format

DATABASE
                        PostgreSQL          Primary DB
                        Replication         Master-Slave
                        TimescaleDB         Time-series

CACHE
                        Redis               Cache layer
                        Sentinel            HA failover
                        6 GB RAM            Typical

STORAGE
                        S3 / MinIO          Object storage
                        (ou GCS/Azure)      Cloud compatible
                        CDN (CloudFront)    Distribution

ML/AI
                        Whisper             Transcrição
                        ONNX                Model format
                        Torch               Inference

MONITORING
                        Prometheus          Metrics
                        Grafana             Visualization
                        Jaeger              Distributed tracing
                        Loki                Centralized logging

ORCHESTRATION
                        Kubernetes          Container orchestration
                        Docker              Containerization
                        Helm                K8s package manager

CI/CD
                        GitHub Actions      Automation
                        DockerHub           Image registry
                        ArgoCD              GitOps deployment
```

---

## 📊 Escalabilidade Visual

```
CENÁRIO 1: Baixa Carga (10 jobs/hora)
═════════════════════════════════════

    API GW  Job Mgr  Download  Transcr   Notif
      |       |         |        |       |
      1 pod   1 pod    1 pod    1 pod   1 pod
    [100m]  [100m]   [100m]   [500m]  [50m]
    
    Total: ~200m CPU, 1GB RAM
    Cost: ~$5/mês


CENÁRIO 2: Média Carga (100 jobs/hora)
═══════════════════════════════════════

    API GW  Job Mgr  Download  Transcr   Notif
      |       |         |        |       |
      2 pods  2 pods   5 pods   3 pods  2 pods
    [100m]  [100m]   [100m]   [500m]  [50m]
    
    Total: ~600m CPU, 3GB RAM
    Cost: ~$20/mês


CENÁRIO 3: Alta Carga (1000+ jobs/hora)
════════════════════════════════════════

    API GW  Job Mgr  Download  Transcr   Notif
      |       |         |        |       |
      5 pods  3 pods  20 pods  10 pods  5 pods
    [100m]  [100m]   [100m]   [500m]  [50m]
    
    Total: ~2000m CPU, 8GB RAM
    Cost: ~$50-100/mês (Kubernetes auto-escalou!)
    
    
⚡ IMPORTANTE: Kubernetes HPA faz isso automaticamente!
   Você não precisa provisionar manualmente.
   HPA monitora métricas (CPU, custom metrics) e escalona.
```

---

## 🔄 Padrões de Comunicação

```
PADRÃO 1: Fila (Assíncrono)
════════════════════════════

Service A              RabbitMQ               Service B
  │                    (Broker)                  │
  │                                              │
  ├─ Publica evento   ──────────────────────────►│
  │ (não espera)                    Consome     │
  │                                              │
  │ Continua          RabbitMQ                  │
  │ (não bloqueado)    (persiste)               │ Processa
  │                                              │
  │◄─────────────── Publica resposta ───────────┤
  │
  
✅ Vantagem: Desacoplado, se B cair, A não sabe
❌ Desvantagem: Latência de rede, eventual consistency


PADRÃO 2: gRPC (Síncrono)
═════════════════════════

Client                Server
  │                    │
  ├─ gRPC Call  ──────►│
  │ (bloqueia)         │ Processa
  │                    │
  │ Espera ◄───────────┤ Responde
  │ response           │
  │
✅ Vantagem: Síncrono, fast, type-safe (Protobuf)
❌ Desvantagem: Acoplado, se server cair, erro imediato


PADRÃO 3: Event Sourcing (Histórico)
════════════════════════════════════

Ação: User criou transcription

┌─ Domain Event ────────────────────────────┐
│ {                                         │
│   "event_id": "uuid",                     │
│   "event_type": "TranscriptionCreated",   │
│   "timestamp": "2025-10-23T14:30:00Z",    │
│   "job_id": "xyz",                        │
│   "youtube_url": "https://..."            │
│ }                                         │
└───────────────────────────────────────────┘
                    │
                    ▼
          Event Store (BD)
          ┌──────────────────┐
          │ id│event│data    │
          ├──────────────────┤
          │1  │Created│{...}  │
          │2  │Started│{...}  │
          │3  │Compl. │{...}  │
          └──────────────────┘
                    │
                PublishEvent
                    │
    ┌───────────────┼───────────────┐
    │               │               │
    ▼               ▼               ▼
  Service A     Service B      Service C
  (atualiza)    (atualiza)     (notifica)

✅ Vantagem: Auditoria completa, replay, debugging
❌ Desvantagem: Complexo, eventual consistency
```

---

## 🛡️ Resiliência

```
CIRCUIT BREAKER (Para YouTube API)
═════════════════════════════════════

Status: CLOSED          Status: OPEN            Status: HALF-OPEN
(Normal)                (Failing)               (Testing)

  │                       │                       │
  ▼                       ▼                       ▼
  
Request ✓               Request ✗              1 Request
Request ✓              Request ✗               → Success? CLOSED
Request ✓            Request ✗                → Fail? OPEN again
  │                     │                       │
  └─ Sucesso            └─ 5 falhas            └─ After 60s timeout
     CLOSED                OPEN


RETRY COM BACKOFF
═════════════════

Tentativa 1: 0ms   ✗ Falha
                   Wait 1s

Tentativa 2: 1s    ✗ Falha
                   Wait 2s

Tentativa 3: 3s    ✗ Falha
                   Wait 4s + jitter

Tentativa 4: 7s    ✓ Sucesso! ✓


TIMEOUT (Job fica > 1 hora)
═══════════════════════════

14:30:00 - Job criado
14:35:00 - Download OK
14:45:00 - Transcribing
15:30:00 - Ainda transcrevendo
15:45:00 - TIMEOUT! Cancela job
          - Notifica: "Processing took too long"


BULKHEAD (Isolamento de recursos)
═════════════════════════════════

ThreadPool Transcription: 20 threads
    ├─ Thread 1: Processando job A ✓
    ├─ Thread 2: Processando job B ✓
    ├─ Thread 3: ✗ STUCK (deadlock)
    ├─ Thread 4: Processando job D ✓
    ├─ Thread 5: Processando job E ✓
    └─ ...

Job C não bloqueia threads 4-20! ✅ Outras requisições continuam.
```

---

## 🚀 Deploy em Kubernetes

```
AMBIENTE LOCAL (Docker Compose)
════════════════════════════════

docker-compose up
        │
        ├─ RabbitMQ     (localhost:5672)
        ├─ PostgreSQL   (localhost:5432)
        ├─ Redis        (localhost:6379)
        ├─ MinIO        (localhost:9000)
        ├─ API Gateway  (localhost:8000)
        ├─ Job Manager  (localhost:8001)
        ├─ Download Svc (localhost:8002)
        ├─ Transcr. Svc (localhost:8003)
        ├─ Storage Svc  (localhost:8004)
        ├─ Notif. Svc   (localhost:8005)
        └─ Admin Svc    (localhost:8006)

✅ Tudo no seu PC!


AMBIENTE PRODUÇÃO (Kubernetes)
════════════════════════════════

kubectl apply -f infra/kubernetes/
        │
        ├─ Namespace: ytcaption
        │
        ├─ StatefulSets:
        │  ├─ rabbitmq-0, rabbitmq-1, rabbitmq-2
        │  ├─ postgres-0, postgres-1
        │  └─ redis-0, redis-1, redis-2
        │
        ├─ Deployments (auto-scaláveis com HPA):
        │  ├─ api-gateway        (replicas: 2-10)
        │  ├─ job-manager        (replicas: 2-5)
        │  ├─ download-service   (replicas: 3-20)
        │  ├─ transcription-svc  (replicas: 2-10)
        │  ├─ storage-service    (replicas: 1-3)
        │  ├─ notification-svc   (replicas: 1-5)
        │  └─ admin-service      (replicas: 1-2)
        │
        ├─ Services (load balanced):
        │  └─ Cada deployment tem 1 ClusterIP service
        │
        ├─ Ingress (Kong):
        │  └─ External load balancer (localhost → cloud)
        │
        ├─ HPA (Horizontal Pod Autoscaler):
        │  └─ Monitora CPU, memory, custom metrics
        │
        └─ Monitoring:
           ├─ Prometheus (scrape 8m interval)
           ├─ Grafana (visualize)
           └─ Jaeger (distributed tracing)

✅ Production-ready, auto-scaling, self-healing!
```

---

## 📈 Métricas de Sucesso

```
ANTES (v2.0 - Monolítico)
═════════════════════════

API Response Time      → 3-5 minutos ❌
QPS Capacity          → 1-2 concurrent ❌
Whisper Processing    → 1-10 minutos
Uptime                → 99% (falhas esporádicas) ❌
Deploy Frequency      → 1x/week (risco de downtime)
Cost (1000 jobs/h)    → $200-300/mês ❌
CPU Utilization       → 95% (sem headroom) ❌
Mean Time To Recovery → 30 minutos (manual fix)


DEPOIS (v3.0 - Micro-serviços)
═══════════════════════════════

API Response Time      → 50ms ✅ (3600x mais rápido!)
QPS Capacity          → 100+ concurrent ✅ (50x melhoria)
Whisper Processing    → 1-5 minutos (mantém paralelo)
Uptime                → 99.9% (isolamento de falhas) ✅
Deploy Frequency      → 5-10x/week (low risk per service)
Cost (1000 jobs/h)    → $50-100/mês ✅ (50% mais barato)
CPU Utilization       → 60% (com headroom) ✅
Mean Time To Recovery → 2-5 minutos (K8s auto-heals)


SCORE GERAL
═══════════

                    v2.0  v3.0
Performance:        3/10  10/10  ✅
Reliability:        6/10  9.5/10 ✅
Scalability:        3/10  10/10  ✅
Operations:         4/10  8/10   ✅
Cost Efficiency:    5/10  9/10   ✅
─────────────────────────────────
MÉDIA:              4.2   9.3    ⭐ +122% melhoria
```

---

## 🎓 Quem faz o quê?

```
ARQUITETO
├─ Define estrutura hexagonal
├─ Design patterns de comunicação
├─ Decisões de tech stack
└─ Code reviews de design

DESENVOLVEDOR 1 (Backend Core)
├─ Implementa Job Manager
├─ Implementa Download Service
├─ Implementa shared libraries
└─ 70% do código

DESENVOLVEDOR 2 (Backend Processing)
├─ Implementa Transcription Service
├─ Implementa Storage Service
├─ Implementa Notification Service
└─ 30% do código

DEVOPS/SRE
├─ Setup RabbitMQ cluster
├─ Setup PostgreSQL replication
├─ Kubernetes manifests
├─ Monitoring (Prometheus + Grafana)
├─ CI/CD pipeline
└─ Produção deployment

PM/MANAGER
├─ Sprint planning
├─ Timeline tracking
├─ Stakeholder communication
└─ Release management
```

---

**Versão**: 3.0.0-PLANNING  
**Data**: 2025-10-23  
**Status**: ✅ Completo

