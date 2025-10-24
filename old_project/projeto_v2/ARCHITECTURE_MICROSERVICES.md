# 🏗️ Arquitetura de Micro-serviços - YTCaption v3.0.0

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Princípios de Design](#princípios-de-design)
3. [Arquitetura Hexagonal](#arquitetura-hexagonal)
4. [Componentes Principais](#componentes-principais)
5. [Comunicação entre Micro-serviços](#comunicação-entre-micro-serviços)
6. [Fluxo de Processamento](#fluxo-de-processamento)
7. [Estrutura de Pastas](#estrutura-de-pastas)
8. [Escalabilidade e Resiliência](#escalabilidade-e-resiliência)
9. [Deploy e Orquestração](#deploy-e-orquestração)

---

## 🎯 Visão Geral

A refatoração migra de uma **arquitetura monolítica** para uma **arquitetura de micro-serviços com fila de processamento distribuído**, implementando princípios de **Arquitetura Hexagonal (Ports & Adapters)**.

### Objetivos

- ✅ **Escalabilidade Horizontal**: Cada serviço pode escalar independentemente
- ✅ **Resiliência**: Falha em um serviço não derruba toda a aplicação
- ✅ **Processamento Assíncrono**: API não bloqueia cliente, fila gerencia jobs
- ✅ **Separação de Responsabilidades**: Cada serviço tem uma única responsabilidade
- ✅ **Desenvolvimento Ágil**: Equipes trabalham independentemente por serviço
- ✅ **Observabilidade**: Logging distribuído, tracing e métricas centralizadas

### Versão Atual

| Aspecto | Antes (v1.x-v2.x) | Depois (v3.0.0) |
|---------|------------------|-----------------|
| **Arquitetura** | Monolítica com Clean Architecture | Micro-serviços com Hexagonal |
| **Processamento** | Síncrono/Paralelo Single Box | Assíncrono com Fila |
| **Escalabilidade** | Vertical (recursos do servidor) | Horizontal (adicionar workers) |
| **Resiliência** | Circuit Breaker local | Circuit Breaker + Health Checks |
| **Comunicação** | In-process | RabbitMQ/Redis + gRPC |
| **Estado** | Arquivo local + cache | PostgreSQL + Redis |

---

## 🏛️ Princípios de Design

### 1. Arquitetura Hexagonal (Ports & Adapters)

Cada micro-serviço segue o padrão hexagonal:

```
┌─────────────────────────────────────────────────────┐
│                                                       │
│              DOMAIN LAYER                            │
│         (Regras de Negócio - Centro)                │
│                                                       │
│  ┌────────────────────────────────────────────┐    │
│  │  Entities, Value Objects, Domain Services │    │
│  │  ❌ ZERO dependências externas             │    │
│  └────────────────────────────────────────────┘    │
│                                                       │
└─────────────────────────────────────────────────────┘
         ▲              ▲              ▲
         │              │              │
         │ PORTS (Interfaces)         │
         │              │              │
    ┌────┴─┐      ┌─────┴─┐      ┌───┴──┐
    │      │      │       │      │      │
    ▼      ▼      ▼       ▼      ▼      ▼
 [In]   [Out]  [In]   [Out]   [In]  [Out]
 HTTP  Message  DB  Event   Cache  Log
 Adapter Adapter Adapter Adapter Adapter Adapter
```

### 2. Domain-Driven Design (DDD)

- **Bounded Contexts**: Cada serviço é um contexto delimitado
- **Ubiquitous Language**: Linguagem comum entre domínios
- **Anti-Corruption Layer**: Traduz entre domínios diferentes

### 3. SOLID em Nível de Serviço

| Princípio | Aplicação |
|-----------|-----------|
| **S**ingle Responsibility | Um serviço = Uma responsabilidade |
| **O**pen/Closed | Aberto para extensão via eventos |
| **L**iskov Substitution | Serviços substituíveis (mesma interface) |
| **I**nterface Segregation | Ports específicas (não mega-interfaces) |
| **D**ependency Inversion | Depende de abstrações (interfaces) |

### 4. Resiliência (The 12 Factors + Cloud Native)

- ❌ Acoplamento forte entre serviços
- ✅ Fila de processamento (desacoplamento)
- ✅ Retry com backoff exponencial
- ✅ Circuit breaker
- ✅ Health checks (liveness + readiness)
- ✅ Timeouts
- ✅ Graceful shutdown

---

## 🔷 Arquitetura Hexagonal Detalhada

### Para cada Micro-serviço:

```
microservice/
├── src/
│   ├── domain/                          # ⭐ Centro (Regras de Negócio)
│   │   ├── models/
│   │   │   ├── aggregates.py           # Agregados (entidades principais)
│   │   │   ├── value_objects.py        # Objetos de valor
│   │   │   └── events.py               # Domain Events
│   │   ├── services/
│   │   │   └── business_logic.py       # Lógica de negócio pura
│   │   └── ports/
│   │       ├── in_ports.py             # Use cases (entrada)
│   │       └── out_ports.py            # Adaptadores (saída)
│   │
│   ├── application/                     # Orquestração de casos de uso
│   │   ├── use_cases/
│   │   │   └── *.py
│   │   ├── dtos/
│   │   │   ├── input_dtos.py          # Request DTOs
│   │   │   └── output_dtos.py         # Response DTOs
│   │   ├── mappers/
│   │   │   └── dto_to_domain.py       # Conversão DTO ↔ Domain
│   │   └── event_handlers/
│   │       └── *.py                   # Handle domain events
│   │
│   ├── infrastructure/                  # Implementação técnica (Adapters)
│   │   ├── outbound/
│   │   │   ├── database/
│   │   │   │   └── repositories.py    # DB Adapter (OUT)
│   │   │   ├── message_queue/
│   │   │   │   └── publishers.py      # Message Adapter (OUT)
│   │   │   ├── external_services/
│   │   │   │   └── youtube_client.py  # HTTP Adapter (OUT)
│   │   │   └── cache/
│   │   │       └── redis_adapter.py   # Cache Adapter (OUT)
│   │   │
│   │   ├── inbound/
│   │   │   ├── http/
│   │   │   │   └── routes.py          # HTTP Adapter (IN)
│   │   │   └── message_queue/
│   │   │       └── consumers.py       # Queue Adapter (IN)
│   │   │
│   │   ├── config/
│   │   │   ├── settings.py            # Configuração (env vars)
│   │   │   └── dependency_injection.py # IoC Container
│   │   │
│   │   └── shared/
│   │       ├── logging.py
│   │       ├── monitoring.py
│   │       └── tracing.py
│   │
│   └── __init__.py
│
├── tests/
│   ├── unit/
│   │   └── domain/                    # Testes de lógica pura (mais rápido)
│   ├── integration/
│   │   └── infrastructure/            # Testes com BD, Fila, etc
│   └── e2e/
│       └── scenarios.py               # Testes de fluxo completo
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

### Ports (Interfaces)

```python
# src/domain/ports/in_ports.py
from abc import ABC, abstractmethod

class TranscriptionUseCaseIn(ABC):
    """Porta de entrada (INPUT): O que este serviço oferece"""
    
    @abstractmethod
    async def transcribe_video(self, video_url: str, language: str) -> TranscriptionResult:
        """Transcrever vídeo"""
        pass


# src/domain/ports/out_ports.py
from abc import ABC, abstractmethod

class VideoDownloadPort(ABC):
    """Porta de saída (OUTPUT): Dependências externas"""
    
    @abstractmethod
    async def download_audio(self, video_url: str) -> bytes:
        """Baixar áudio do YouTube"""
        pass

class TranscriptionRepositoryPort(ABC):
    """Porta de saída: Persistência"""
    
    @abstractmethod
    async def save_transcription(self, transcription: Transcription) -> str:
        """Salvar transcrição no BD"""
        pass

class TranscriptionEventPublisherPort(ABC):
    """Porta de saída: Publicar eventos"""
    
    @abstractmethod
    async def publish_transcription_completed(self, event: TranscriptionCompletedEvent):
        """Publicar evento de conclusão"""
        pass
```

---

## 🎬 Componentes Principais (Micro-serviços)

### 1️⃣ **API Gateway** (porta 8000)
**Responsabilidade**: Roteamento, autenticação, rate limiting

```
Cliente HTTP
     ↓
[API Gateway]
   ├─ Autentica (JWT)
   ├─ Rate limit
   ├─ Valida schema
   └─ Roteia para serviço apropriado
     ├─ → Client Service
     ├─ → Transcription Service
     ├─ → Job Status Service
     └─ → Admin Service
```

**Tech Stack**:
- FastAPI com Kong/Nginx (load balancing)
- JWT para autenticação
- Swagger auto-gerado

**Endpoints**:
```http
POST   /api/v1/transcriptions          → Cria job
GET    /api/v1/transcriptions/{id}     → Status do job
GET    /api/v1/transcriptions/{id}/result → Resultado
DELETE /api/v1/transcriptions/{id}     → Cancela job
```

---

### 2️⃣ **Transcription Service** (porta 8001)
**Responsabilidade**: Transcrever áudio usando Whisper

```
[Transcription Service]
├─ Receive: TranscriptionJobStarted event
├─ Download áudio (já feito pelo Download Service)
├─ Processa com Whisper (paralelo com worker pool)
├─ Salva resultado no BD
└─ Publish: TranscriptionCompleted event
```

**Tech Stack**:
- FastAPI
- Pydantic para validação
- SQLAlchemy para BD
- Whisper (OpenAI) para transcrição
- Redis para cache

**Features**:
- Carrega modelo Whisper uma vez (persistent worker pool v2.0)
- Processa chunks em paralelo
- Suporta 6 modelos (tiny→large)
- Detecção automática de idioma

---

### 3️⃣ **Download Service** (porta 8002)
**Responsabilidade**: Baixar áudio do YouTube

```
[Download Service]
├─ Receive: TranscriptionJobCreated event
├─ Valida URL do YouTube
├─ Download com retry + backoff exponencial
├─ Salva arquivo temporário
├─ Upload para armazenamento distribuído (S3/MinIO)
└─ Publish: AudioDownloadedEvent
```

**Tech Stack**:
- FastAPI
- yt-dlp para download YouTube
- Boto3 para S3
- Circuit breaker para resiliência

**Features**:
- Retry com backoff exponencial
- Multiple user-agent rotation
- Circuit breaker (falhas contínuas)
- Streaming para arquivos grandes

---

### 4️⃣ **Job Manager Service** (porta 8003)
**Responsabilidade**: Orquestrar workflow de jobs

```
[Job Manager Service]
├─ Recebe requisição do API Gateway
├─ Cria registro de job (status: PENDING)
├─ Publica: TranscriptionJobCreated
├─ Monitora eventos
│  ├─ AudioDownloadedEvent → status: DOWNLOADING
│  ├─ TranscriptionStartedEvent → status: TRANSCRIBING
│  ├─ TranscriptionCompletedEvent → status: COMPLETED
│  └─ ErrorEvent → status: FAILED
└─ Retorna status para cliente
```

**Tech Stack**:
- FastAPI
- PostgreSQL para persistência
- Redis para estado (cache)
- Message broker (RabbitMQ/Kafka)

**Features**:
- State machine (PENDING → DOWNLOADING → TRANSCRIBING → COMPLETED)
- Timeout para jobs (ex: 1 hora max)
- Retry automático para falhas transientes
- Dead letter queue para falhas permanentes

---

### 5️⃣ **Storage Service** (porta 8004)
**Responsabilidade**: Gerenciar armazenamento distribuído

```
[Storage Service]
├─ Adapters:
│  ├─ Local Filesystem
│  ├─ AWS S3
│  ├─ MinIO (self-hosted S3)
│  └─ Google Cloud Storage
├─ Funções:
│  ├─ Upload arquivo
│  ├─ Download arquivo
│  ├─ Listar arquivos
│  └─ Deletar arquivo (com retenção)
└─ Features:
   ├─ Multi-cloud (select via env)
   ├─ Versioning
   ├─ Cleanup automático
   └─ Encrypted at rest
```

**Tech Stack**:
- FastAPI
- Boto3 (AWS S3)
- MinIO Python client
- Cryptography para encryption

---

### 6️⃣ **Notification Service** (porta 8005)
**Responsabilidade**: Notificar cliente sobre progressão

```
[Notification Service]
├─ Ingesta eventos:
│  ├─ TranscriptionStarted
│  ├─ TranscriptionProgress (cada 10% processado)
│  ├─ TranscriptionCompleted
│  └─ TranscriptionFailed
├─ Canais:
│  ├─ Webhook (POST para URL do cliente)
│  ├─ Email
│  ├─ WebSocket (real-time)
│  └─ SMS (opcional)
└─ Features:
   ├─ Retry exponencial (3 tentativas)
   ├─ Template de mensagens
   └─ Rate limiting por cliente
```

**Tech Stack**:
- FastAPI com WebSockets
- SendGrid para email
- Twilio para SMS
- HTTPX para webhooks

---

### 7️⃣ **Admin Service** (porta 8006)
**Responsabilidade**: Operações administrativas

```
[Admin Service]
├─ Endpoints:
│  ├─ GET /metrics → Métricas globais
│  ├─ GET /health → Status de todos serviços
│  ├─ POST /cleanup → Cleanup manual
│  ├─ GET /jobs → Listar jobs
│  ├─ POST /jobs/{id}/cancel → Cancelar job
│  └─ GET /logs → Logs centralizados
├─ Features:
│  ├─ Dashboard (Grafana)
│  ├─ Alertas (Prometheus + Alertmanager)
│  └─ Tracing distribuído (Jaeger)
└─ Segurança:
   ├─ RBAC (Role-Based Access Control)
   └─ Auditoria de ações
```

**Tech Stack**:
- FastAPI
- Prometheus para métricas
- Grafana para dashboard
- Jaeger para distributed tracing

---

## 🔄 Comunicação entre Micro-serviços

### Padrão 1: Fila de Mensagens (Assíncrono - Desacoplado)

```
                    ┌─────────────────────────────┐
                    │   Message Broker            │
                    │  (RabbitMQ / Apache Kafka)  │
                    └─────────────────────────────┘
                          ▲         ▲         ▲
            ┌─────────────┼─────────┼─────────┤
            │             │         │         │
            │ Publica    │ Consome │ Consome │ Consome
            │             │         │         │
     ┌──────▼────┐  ┌─────▼────┐ ┌─▼──────┐ ┌─▼──────┐
     │Job Manager│  │ Download │ │Transcr.│ │Notif.  │
     │ Service   │  │ Service  │ │Service │ │Service │
     └───────────┘  └──────────┘ └────────┘ └────────┘
         (Producer)   (Consumer)  (Consumer) (Consumer)
```

### Topics/Queues

```yaml
transcription.jobs:
  - Message: TranscriptionJobCreated
  - Producer: API Gateway (via Job Manager)
  - Consumers: Download Service, Job Manager Service
  - TTL: 24 horas

transcription.audio_downloaded:
  - Message: AudioDownloadedEvent
  - Producer: Download Service
  - Consumers: Transcription Service, Job Manager Service
  - TTL: 24 horas

transcription.completed:
  - Message: TranscriptionCompletedEvent
  - Producer: Transcription Service
  - Consumers: Job Manager Service, Notification Service, Admin Service
  - TTL: 30 dias (auditoria)

transcription.failed:
  - Message: TranscriptionFailedEvent
  - Producer: Any Service
  - Consumers: Job Manager Service, Notification Service, Admin Service
  - TTL: 30 dias (debugging)
```

### Message Format (Avro/JSON Schema)

```json
{
  "event_id": "uuid",
  "event_type": "TranscriptionJobCreated",
  "timestamp": "2025-10-23T14:30:00Z",
  "version": "1.0",
  "correlation_id": "uuid",  // Trace relacionado
  "causation_id": "uuid",     // Causa raiz
  "data": {
    "job_id": "uuid",
    "youtube_url": "https://youtube.com/watch?v=xyz",
    "language": "auto",
    "requested_by": "user@example.com",
    "priority": "normal",  // normal, high, low
    "metadata": {
      "user_agent": "...",
      "ip_address": "...",
      "request_id": "..."
    }
  }
}
```

---

### Padrão 2: Chamadas Síncronas (gRPC - Acoplado mas Rápido)

Para operações críticas que precisam de resposta imediata:

```
┌──────────────────────────────────────────────────────┐
│                 gRPC (HTTP/2 + Protobuf)             │
│                                                       │
│  API Gateway ────┬────→ Job Manager Service         │
│                  ├────→ Storage Service              │
│                  └────→ Admin Service                │
│                                                       │
│  Vantagens:                                           │
│  ✅ Tipo-safe (Protobuf)                             │
│  ✅ Rápido (HTTP/2 + binário)                        │
│  ✅ Suporta streaming bidirecional                   │
│                                                       │
│  Desvantagens:                                        │
│  ❌ Acoplamento (cliente espera resposta)            │
│  ❌ Timeout se serviço cair                          │
└──────────────────────────────────────────────────────┘
```

**Quando usar gRPC**:
- ✅ Status em tempo real (cliente quer saber agora)
- ✅ Operações críticas (erro deve ser visto imediatamente)
- ✅ Alta volume de dados (protobuf é compacto)

**Quando NÃO usar gRPC**:
- ❌ Operações longas (use fila)
- ❌ Pode falhar/retentar (use fila)

---

### Padrão 3: Event Sourcing (Histórico Completo)

```
Event Store (PostgreSQL):
┌─────────────────────────────────────────────────────┐
│ id │ event_type │ aggregate_id │ data │ timestamp  │
├─────────────────────────────────────────────────────┤
│ 1  │ Created    │ job-123      │ {...} │ 14:30:00  │
│ 2  │ Started    │ job-123      │ {...} │ 14:30:05  │
│ 3  │ Progress   │ job-123      │ {...} │ 14:30:10  │
│ 4  │ Completed  │ job-123      │ {...} │ 14:31:00  │
└─────────────────────────────────────────────────────┘

Benefícios:
✅ Auditoria completa (saber o que aconteceu)
✅ Replay (reconstruir estado)
✅ Time travel (debugging histórico)
✅ CQRS (separar leitura de escrita)
```

---

### Padrão 4: Saga (Orquestração de Transações Distribuídas)

```
Cliente solicita transcrição:

1. API Gateway
   └─ Chama: Job Manager (cria job)
        ↓
2. Job Manager
   ├─ Salva job com status: CREATED
   └─ Publica: TranscriptionJobCreated
        ↓
3. Download Service (consome evento)
   ├─ Download áudio
   ├─ Publica: AudioDownloadedEvent
   └─ (Se falhar) Publica: TranscriptionFailedEvent → Volta ao passo 2
        ↓
4. Transcription Service (consome evento)
   ├─ Transcreve
   ├─ Publica: TranscriptionCompletedEvent
   └─ (Se falhar) Publica: TranscriptionFailedEvent → Volta ao passo 2
        ↓
5. Notification Service (consome evento)
   └─ Notifica cliente: "Pronto!"

Compensating Transactions (Rollback):
├─ Se falha no passo 3: Cancela job, notifica cliente
├─ Se falha no passo 4: Recoloca na fila com retry
└─ DLQ (Dead Letter Queue): Jobs que não conseguem ser processados
```

---

## 🔁 Fluxo de Processamento Completo

### 1. Cliente solicita transcrição

```http
POST /api/v1/transcriptions HTTP/1.1
Content-Type: application/json

{
  "youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "auto",
  "priority": "normal",
  "webhook_url": "https://client.com/webhooks/transcription"  # Opcional
}
```

### 2. API Gateway valida e roteia

```
[API Gateway]
├─ ✓ Valida URL
├─ ✓ Rate limit por IP (5 req/min)
├─ ✓ Autentica (JWT)
└─ Roteia para: Job Manager Service
```

### 3. Job Manager cria job

```
[Job Manager Service]
├─ INSERT INTO jobs (status=PENDING)
├─ ✓ Retorna: 202 Accepted
│         {
│           "job_id": "uuid",
│           "status": "pending",
│           "status_url": "/api/v1/transcriptions/uuid",
│           "result_url": "/api/v1/transcriptions/uuid/result"
│         }
└─ Publica: TranscriptionJobCreated → Fila
```

### 4. Download Service consome evento

```
[Download Service] (Consumer)
├─ Recebe: TranscriptionJobCreated
├─ Download áudio do YouTube (com retry)
│  ├─ Tenta 3 vezes com backoff exponencial
│  ├─ Usa user-agent rotation
│  └─ (Fallback) Tenta YouTube Transcript API
├─ Upload para S3/MinIO
├─ UPDATE job (status=DOWNLOADING)
├─ Publica: AudioDownloadedEvent
└─ (Se falha) Publica: TranscriptionFailedEvent
```

### 5. Transcription Service consome evento

```
[Transcription Service] (Consumer)
├─ Recebe: AudioDownloadedEvent
├─ Download áudio do S3
├─ Carrega modelo Whisper (cached)
├─ Transcreve em paralelo (worker pool)
│  ├─ Split áudio em chunks (120s cada)
│  ├─ Processa chunks em paralelo
│  ├─ Mescla resultados
│  └─ Publica: TranscriptionProgress a cada 10%
├─ Salva resultado no BD
├─ UPDATE job (status=TRANSCRIBING → COMPLETED)
├─ Publica: TranscriptionCompletedEvent
└─ (Se falha) Publica: TranscriptionFailedEvent
   └─ Job Manager move para DLQ ou recoloca na fila
```

### 6. Notification Service notifica cliente

```
[Notification Service] (Consumer)
├─ Recebe: TranscriptionCompletedEvent
├─ Envia webhook (se configurado)
├─ Envia email (se configurado)
├─ Atualiza cache com resultado
└─ Publica: NotificationSentEvent
```

### 7. Cliente verifica resultado

```http
# Polling (simples, não ideal)
GET /api/v1/transcriptions/{job_id} HTTP/1.1

# Resposta
{
  "job_id": "uuid",
  "status": "completed",
  "progress": 100,
  "result": {
    "text": "Full transcription...",
    "segments": [...],
    "language": "en",
    "processing_time": 120
  },
  "created_at": "2025-10-23T14:30:00Z",
  "completed_at": "2025-10-23T14:32:00Z"
}
```

---

## 📁 Estrutura de Pastas

```
.
├── api-gateway/                    # Porta 8000
│   ├── src/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
│
├── job-manager-service/            # Porta 8001
│   ├── src/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
│
├── download-service/               # Porta 8002
│   ├── src/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
│
├── transcription-service/          # Porta 8003
│   ├── src/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
│
├── storage-service/                # Porta 8004
│   ├── src/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
│
├── notification-service/           # Porta 8005
│   ├── src/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
│
├── admin-service/                  # Porta 8006
│   ├── src/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
│
├── shared-libs/                    # Código compartilhado
│   ├── ytcaption-core/
│   │   ├── domain/
│   │   │   ├── models.py          # Entidades compartilhadas
│   │   │   ├── events.py          # Domain events
│   │   │   └── exceptions.py      # Exceções customizadas
│   │   ├── infrastructure/
│   │   │   ├── message_queue/     # Adaptador RabbitMQ/Kafka
│   │   │   ├── database/          # DB client compartilhado
│   │   │   └── monitoring/        # Logging, tracing, métricas
│   │   └── pyproject.toml
│   │
│   └── ytcaption-testing/         # Helpers de teste
│       ├── fixtures.py
│       ├── mocks.py
│       └── pyproject.toml
│
├── infra/                          # Infraestrutura
│   ├── docker-compose.yml          # Ambiente local
│   ├── docker-compose.prod.yml     # Produção (Kubernetes YAML)
│   ├── kubernetes/
│   │   ├── namespaces.yaml
│   │   ├── services.yaml           # K8s Services
│   │   ├── deployments.yaml        # K8s Deployments
│   │   ├── hpa.yaml               # Horizontal Pod Autoscaler
│   │   ├── ingress.yaml           # Kong/Nginx Ingress
│   │   └── monitoring/
│   │       ├── prometheus.yaml
│   │       ├── alertmanager.yaml
│   │       └── grafana.yaml
│   │
│   ├── terraform/                  # IaC (Infrastructure as Code)
│   │   ├── aws/
│   │   ├── gcp/
│   │   └── azure/
│   │
│   └── monitoring/
│       ├── prometheus.yml
│       ├── grafana-dashboards/
│       │   ├── jobs.json
│       │   ├── services.json
│       │   └── infrastructure.json
│       ├── jaeger-config.yaml
│       └── loki-config.yaml
│
├── docs/
│   ├── ARCHITECTURE_MICROSERVICES.md     # Este arquivo
│   ├── API_SPECIFICATION.md              # OpenAPI
│   ├── MESSAGE_SCHEMA.md                 # Event schema
│   ├── DEPLOYMENT_GUIDE.md               # Como fazer deploy
│   ├── TROUBLESHOOTING.md                # Debugging
│   ├── CONTRIBUTING.md                   # Como contribuir
│   └── tutorials/
│       ├── local-setup.md
│       ├── kubernetes-deploy.md
│       └── scaling-guide.md
│
├── old/                            # Código antigo (monolítico v1-v2)
│   └── ...
│
├── docker-compose.yml              # Ambiente local completo
├── docker-compose.prod.yml         # Ambiente produção
├── Makefile                        # Comandos úteis
├── .env.example                    # Variáveis de ambiente
└── README.md                       # README principal
```

---

## 📈 Escalabilidade e Resiliência

### Horizontal Scaling (Adicionar mais servidores)

```yaml
# Kubernetes HPA (Horizontal Pod Autoscaler)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: transcription-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: transcription-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    - type: Pods
      pods:
        metric:
          name: queue_depth  # Métrica customizada
        target:
          type: AverageValue
          averageValue: "30"  # Se fila > 30, adiciona pod
```

### Load Balancing

```
┌─────────────────────────────────────────────────────┐
│           Kong API Gateway / Nginx                   │
│           (Load Balancer)                            │
│                                                       │
│  Round Robin / Least Connections / IP Hash          │
└─────────────────────────────────────────────────────┘
    ▼           ▼           ▼           ▼
 [Pod 1]    [Pod 2]    [Pod 3]    [Pod 4]
 Service    Service    Service    Service
```

### Resiliência - Padrões de Fault Tolerance

```yaml
# Circuit Breaker Pattern
┌─────────────────┐
│ Closed (Normal) │ ──(Error rate > 50%)──→ [Open (Failing)]
└─────────────────┘ ←─(Cooldown timeout)─── [Half-Open]
                         ↓
                   (Teste 1 request)
                    ├─ Sucesso → Closed
                    └─ Falha → Open

# Implementation
from pybreaker import CircuitBreaker

youtube_breaker = CircuitBreaker(
    fail_max=5,           # Falhar 5x
    reset_timeout=60,     # Wait 60s
    exclude=[BadURL]      # Não conta BadURL como falha
)

try:
    video = youtube_breaker.call(download_video, url)
except CircuitBreaker:
    # Fallback: YouTube Transcript API
    video = get_transcript_fallback(url)
```

### Retry Strategy

```python
# Exponential Backoff with Jitter
import asyncio
import random

async def retry_with_backoff(
    func,
    max_attempts=3,
    base_delay=1,
    max_delay=60,
    jitter=True
):
    for attempt in range(max_attempts):
        try:
            return await func()
        except TransientError as e:
            if attempt == max_attempts - 1:
                raise
            
            delay = base_delay * (2 ** attempt)  # Exponential
            if jitter:
                delay += random.uniform(0, delay * 0.1)
            delay = min(delay, max_delay)  # Cap at max_delay
            
            logger.warning(f"Attempt {attempt+1} failed, retrying in {delay}s")
            await asyncio.sleep(delay)
```

### Timeouts

```python
# Request timeout
@app.post("/transcribe")
async def transcribe(request: TranscribeRequest):
    try:
        result = await asyncio.wait_for(
            transcription_service.transcribe(request),
            timeout=3600  # 1 hora
        )
        return result
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Processing timeout")
```

### Health Checks

```yaml
# Liveness Probe (Is service alive?)
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

# Readiness Probe (Ready to accept traffic?)
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5

# Endpoints
GET /health/live → 200 if app is running
GET /health/ready → 200 if all dependencies (DB, Cache, Queue) OK
```

### Graceful Shutdown

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting service...")
    # Initialize connections...
    yield
    # Shutdown
    logger.info("Shutting down gracefully...")
    # Stop accepting new requests
    # Wait for in-flight requests to complete (timeout: 30s)
    # Close connections
    await asyncio.sleep(30)
    logger.info("Shutdown complete")
```

---

## 🚀 Deploy e Orquestração

### Ambiente Local (Development)

```bash
# Clonar repositório
git clone https://github.com/yourorg/ytcaption-microservices
cd ytcaption-microservices

# Build e start
docker-compose up -d

# Verificar status
docker-compose ps

# Logs
docker-compose logs -f api-gateway
```

### Ambiente Produção (Kubernetes)

```bash
# Criar namespace
kubectl create namespace ytcaption

# Deploy services
kubectl apply -f infra/kubernetes/

# Verificar deployments
kubectl get deployments -n ytcaption
kubectl get pods -n ytcaption
kubectl get svc -n ytcaption

# Scale manualmente
kubectl scale deployment transcription-service --replicas=5 -n ytcaption

# View logs
kubectl logs -f deployment/transcription-service -n ytcaption
```

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy Microservices

on:
  push:
    branches: [main]
    paths:
      - 'transcription-service/**'  # Só deploy se mudar este serviço
      - 'infra/**'

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: |
          docker build -t transcription-service:${{ github.sha }} ./transcription-service
      
      - name: Run tests
        run: |
          docker run --rm transcription-service:${{ github.sha }} pytest
      
      - name: Push to registry
        run: |
          docker push registry.example.com/transcription-service:${{ github.sha }}
  
  deploy:
    needs: build-and-test
    runs-on: ubuntu-latest
    steps:
      - name: Update Kubernetes
        run: |
          kubectl set image deployment/transcription-service \
            transcription-service=registry.example.com/transcription-service:${{ github.sha }} \
            -n ytcaption
```

---

## 📊 Monitoramento e Observabilidade

### Métricas (Prometheus + Grafana)

```
┌──────────────────────────────────────────────────────┐
│              Application Metrics                      │
├──────────────────────────────────────────────────────┤
│ • Requests/second (por endpoint)                     │
│ • Latency (p50, p95, p99)                            │
│ • Error rate (por tipo de erro)                      │
│ • Queue depth (número de jobs pendentes)             │
│ • Model cache hit rate                               │
│ • Worker pool utilization                            │
│ • Audio download success rate                        │
│ • Storage usage (GB)                                 │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│           Infrastructure Metrics                      │
├──────────────────────────────────────────────────────┤
│ • CPU/Memory/Disk por pod                            │
│ • Network I/O (RabbitMQ, Database)                   │
│ • Database connections (active/idle)                 │
│ • Redis memory usage                                 │
│ • K8s pod restarts                                   │
└──────────────────────────────────────────────────────┘
```

### Logging Centralizado (ELK / Loki)

```
┌──────────────────────────────────────────────────────┐
│   Each Service                                        │
│   logger.info("Job started", extra={                 │
│       "job_id": "uuid",                              │
│       "trace_id": "uuid",                            │
│       "correlation_id": "uuid"                       │
│   })                                                  │
└──────────────────────────────────────────────────────┘
    ↓ (LogStash / Vector)
┌──────────────────────────────────────────────────────┐
│   Centralized Log Storage (Elasticsearch/Loki)       │
│   • Indexed by service, trace_id, correlation_id     │
│   • Retention: 30 dias                               │
└──────────────────────────────────────────────────────┘
    ↓ (Kibana / Grafana)
┌──────────────────────────────────────────────────────┐
│   Search & Visualization                             │
│   • Find job by ID                                   │
│   • Trace error root cause                           │
│   • Correlate with other services                    │
└──────────────────────────────────────────────────────┘
```

### Tracing Distribuído (Jaeger)

```
Cliente Request:
  ├─ trace_id: a1b2c3d4
  └─ span_id: 1
        ↓
[API Gateway]
  └─ span_id: 2 (parent: 1)
        ↓
[Job Manager]
  └─ span_id: 3 (parent: 2)
        ├─ DB query (span 4)
        └─ Message publish (span 5)
        ↓
[Download Service]
  └─ span_id: 6 (parent: 2) [async]
        ├─ Network call YouTube (span 7)
        └─ S3 upload (span 8)
        ↓
[Transcription Service]
  └─ span_id: 9 (parent: 2) [async]
        ├─ Whisper inference (span 10-15, paralelo)
        └─ DB save (span 16)

Visualization em Jaeger:
┌─────────────────────────────────────────────────┐
│ Trace: a1b2c3d4 (Total: 1200ms)                │
├─────────────────────────────────────────────────┤
│ [API Gateway] ──────────── 50ms ──────┐        │
│   [Job Manager] ────── 30ms ──┐       │        │
│     [DB] ──– 10ms            │       │        │
│     [Queue] ─ 5ms            │       │        │
│   [Download] ────────── 800ms ─┼─────┤        │
│     [YouTube] ── 700ms       │       │        │
│     [S3] ─────── 100ms       │       │        │
│   [Transcription] ──── 700ms ─┘       │        │
│     [Whisper 1-4] ── 680ms  (paralelo)        │
│     [DB] ──– 20ms                    │        │
└─────────────────────────────────────────────────┘
```

---

## ⚡ Resumo Executivo

### Benefícios da Refatoração

| Aspecto | Monolítico (v1-v2) | Micro-serviços (v3) |
|---------|------------------|------------------|
| **Escalabilidade** | ❌ Vertical (limites de hardware) | ✅ Horizontal (add Pods) |
| **Deployment** | 🟡 Redeploy tudo | ✅ Deploy serviço isolado |
| **Resiliência** | ❌ 1 falha = sistema cai | ✅ Isolamento de falhas |
| **Performance** | 🟡 Timeout -> Cliente espera | ✅ Fila -> Job status |
| **Desenvolvimento** | 🟡 Codebase grande, acoplo | ✅ Equipes independentes |
| **Custo** | ✅ Instância única | 🟡 Múltiplas instâncias |
| **Observabilidade** | 🟡 Logs locais | ✅ Distributed tracing |

### Trade-offs

| Vantagem | Desvantagem |
|----------|-----------|
| ✅ Escalabilidade | ❌ Complexidade operacional |
| ✅ Independência | ❌ Consistência eventual |
| ✅ Resiliência | ❌ Debugging distribuído |
| ✅ Performance | ❌ Mais recursos (custo) |
| ✅ DevOps rápido | ❌ Network latency |

### Próximos Passos

1. **Fase 1 (Sprint 1-2)**: Scaffolding dos serviços + Docker Compose
2. **Fase 2 (Sprint 3-4)**: Implementar Job Manager + Message Queue
3. **Fase 3 (Sprint 5-6)**: Implementar Download Service
4. **Fase 4 (Sprint 7-8)**: Refatorar Transcription Service
5. **Fase 5 (Sprint 9-10)**: Implementar Storage + Notification Services
6. **Fase 6 (Sprint 11+)**: Kubernetes deployment + Monitoring
7. **Fase 7 (Ongoing)**: Otimizações de performance + custo

---

## 📚 Referências

- [Domain-Driven Design - Eric Evans](https://www.domainlanguage.com/ddd/)
- [Clean Architecture - Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Microservices Patterns - Sam Newman](https://samnewman.io/books/building_microservices/)
- [RabbitMQ Best Practices](https://www.rabbitmq.com/bestpractices.html)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [OpenTelemetry - Distributed Tracing](https://opentelemetry.io/)

---

**Documento versão**: 1.0.0  
**Data**: 2025-10-23  
**Status**: Em Planejamento

