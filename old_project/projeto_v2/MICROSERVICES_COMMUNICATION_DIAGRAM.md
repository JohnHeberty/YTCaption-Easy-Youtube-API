# 🔄 Diagrama de Comunicação - Micro-serviços YTCaption v3.0.0

## 📊 Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAMADA DE APRESENTAÇÃO                            │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Web UI     │  │  Mobile App  │  │   CLI Tool   │  │   3rd Party  │  │
│  │  (React)     │  │  (Flutter)   │  │  (Python)    │  │   Service    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓ HTTPS (REST)
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY (Kong/Nginx)                            │
│                               :8000                                          │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ • Authentication (JWT)                                              │   │
│  │ • Rate Limiting (5 req/min per endpoint)                            │   │
│  │ • Request Validation                                                │   │
│  │ • Load Balancing                                                    │   │
│  │ • Request/Response Transformation                                   │   │
│  │ • API Versioning (v1, v2...)                                        │   │
│  │ • CORS                                                              │   │
│  │ • Metrics Collection                                                │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
        ↓                       ↓                       ↓
    [gRPC]                 [gRPC]                 [gRPC]
        ↓                       ↓                       ↓
┌────────────────────┐ ┌────────────────────┐ ┌──────────────────┐
│   JOB MANAGER      │ │  ADMIN SERVICE     │ │  STORAGE SERVICE │
│    :8001 (in)      │ │    :8006 (in)      │ │   :8004 (in)     │
│                    │ │                    │ │                  │
│ • Create job       │ │ • Get metrics      │ │ • Get file       │
│ • Get status       │ │ • Get logs         │ │ • Upload file    │
│ • List jobs        │ │ • Health check     │ │ • Delete file    │
│ • Cancel job       │ │ • Service status   │ │ • List files     │
│ • Webhook config   │ │ • Alerts           │ │                  │
│                    │ │ • System info      │ │                  │
└────────────────────┘ └────────────────────┘ └──────────────────┘
```

---

## 🎯 Fluxo Principal (Happy Path)

```
SEQUÊNCIA COMPLETA DE UM JOB
═════════════════════════════════════════════════════════════════════════

1. CLIENTE SUBMETE JOB
━━━━━━━━━━━━━━━━━━━━━

    CLIENT
      │
      │ POST /api/v1/transcriptions
      │ {
      │   "youtube_url": "https://youtube.com/watch?v=xyz",
      │   "language": "auto",
      │   "priority": "normal"
      │ }
      ↓
    ┌─────────────────────┐
    │   API GATEWAY       │
    │   (Kong)            │
    │ • Autentica JWT     │
    │ • Rate limit check  │
    │ • Valida schema     │
    └─────────────────────┘
      │
      │ gRPC Call: CreateJob()
      ↓
    ┌──────────────────────────────────────┐
    │   JOB MANAGER SERVICE (:8001)       │
    │                                      │
    │  INSERT jobs (                       │
    │    id: uuid,                         │
    │    status: 'PENDING',                │
    │    youtube_url: 'https://...',       │
    │    created_at: now(),                │
    │    priority: 'normal'                │
    │  )                                   │
    └──────────────────────────────────────┘
      │
      │ Response gRPC: 
      │ {
      │   "job_id": "uuid",
      │   "status": "pending",
      │   "status_url": "/api/v1/transcriptions/uuid"
      │ }
      ↓
    ┌─────────────────────┐
    │   API GATEWAY       │
    ├─────────────────────┤
    │ 202 Accepted        │
    │ Location: /api/...  │
    └─────────────────────┘
      │
      │ HTTP Response 202
      ↓
    CLIENT (Aguardando, checa status depois)


2. JOB MANAGER PUBLICA EVENTO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    JOB MANAGER SERVICE
      │
      │ Publica no Message Broker:
      │ Event: "TranscriptionJobCreated"
      │ {
      │   "event_id": "uuid",
      │   "job_id": "uuid",
      │   "youtube_url": "https://...",
      │   "language": "auto",
      │   "priority": "normal",
      │   "timestamp": "2025-10-23T14:30:00Z"
      │ }
      ↓
    ┌──────────────────────────────────────┐
    │   MESSAGE BROKER                     │
    │   (RabbitMQ / Apache Kafka)          │
    │                                      │
    │   Topic: "transcription.jobs"        │
    │   Exchange: "transcription"          │
    │   Routing Key: "job.created"         │
    │                                      │
    │   TTL: 24 horas                      │
    │   Retention: Persistente             │
    └──────────────────────────────────────┘
      │
      │ Subscribers
      ├─────────────────────────────────────────┐
      │                                          │
      ↓                                          ↓
    [DOWNLOAD SERVICE]                   [JOB MANAGER SERVICE]
    (Consome)                            (Monitora status)


3. DOWNLOAD SERVICE PROCESSA
━━━━━━━━━━━━━━━━━━━━━━━━━━

    DOWNLOAD SERVICE
      │
      │ Consome evento: TranscriptionJobCreated
      │
      ├─ UPDATE jobs SET status='DOWNLOADING'
      │
      ├─ Download YouTube Video
      │  ├─ Tenta com yt-dlp (retry 3x, backoff exponencial)
      │  ├─ Fallback: YouTube Transcript API (se falhar)
      │  ├─ Circuit Breaker (5 falhas = abrir)
      │  └─ Timeout: 15 minutos
      │
      ├─ Upload Arquivo para Storage
      │  └─ S3 / MinIO / GCS
      │
      ├─ Publica evento de sucesso
      │  Evento: "AudioDownloadedEvent"
      │  {
      │    "job_id": "uuid",
      │    "audio_url": "s3://bucket/audio/uuid.mp3",
      │    "duration_seconds": 300,
      │    "file_size_mb": 12.5
      │  }
      │
      └─ (Se erro) Publica evento de falha
         Evento: "TranscriptionFailedEvent"
         └─ Move para DLQ (Dead Letter Queue)
      
      ↓ Publica evento
      
    ┌──────────────────────────────────────┐
    │   MESSAGE BROKER                     │
    │   Topic: "transcription.audio_downloaded" │
    └──────────────────────────────────────┘
      │
      │ Subscribers
      ├─────────────────────────────────────────┐
      │                                          │
      ↓                                          ↓
  [TRANSCRIPTION SERVICE]              [JOB MANAGER SERVICE]
  (Aguarda para processar)            (Atualiza status)


4. TRANSCRIPTION SERVICE PROCESSA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    TRANSCRIPTION SERVICE
      │
      │ Consome evento: AudioDownloadedEvent
      │
      ├─ UPDATE jobs SET status='TRANSCRIBING'
      │
      ├─ Download áudio do S3
      │
      ├─ Carrega modelo Whisper (cache: 1 vez no startup)
      │
      ├─ Processa em paralelo (Worker Pool v2.0)
      │  ├─ Split audio em chunks (120s cada)
      │  ├─ Distribui chunks entre workers (CPU-bound)
      │  ├─ Cada worker: Whisper inference
      │  ├─ Mescla resultados
      │  └─ Publica: TranscriptionProgressEvent (a cada 10%)
      │
      ├─ Salva resultado no BD
      │  INSERT transcriptions (
      │    job_id, text, segments, language, ...
      │  )
      │
      ├─ Publica evento de sucesso
      │  Evento: "TranscriptionCompletedEvent"
      │  {
      │    "job_id": "uuid",
      │    "text": "Full transcription...",
      │    "segments": [
      │      {"start": 0, "end": 5, "text": "Hello..."},
      │      ...
      │    ],
      │    "language": "en",
      │    "processing_time_seconds": 120
      │  }
      │
      └─ (Se erro) Publica evento de falha
         └─ Retry automático ou DLQ
      
      ↓ Publica evento
      
    ┌──────────────────────────────────────┐
    │   MESSAGE BROKER                     │
    │   Topic: "transcription.completed"   │
    │   Topic: "transcription.progress"    │
    └──────────────────────────────────────┘
      │
      │ Subscribers (múltiplos consumidores)
      │
      ├─────────────────────────────────────────┬──────────────┬───────────┐
      │                                          │              │           │
      ↓                                          ↓              ↓           ↓
  [JOB MANAGER]                          [NOTIFICATION]    [ADMIN]    [ANALYTICS]
  • Atualiza status                      • Envia webhook   • Métricas • Registra
  • Marca como completo                  • Email           • Logs     • Eventos


5. JOB MANAGER ATUALIZA STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    JOB MANAGER SERVICE
      │
      │ Consome evento: TranscriptionCompletedEvent
      │
      ├─ UPDATE jobs SET 
      │    status='COMPLETED',
      │    completed_at=now(),
      │    result_url='/api/v1/transcriptions/{id}/result'
      │
      ├─ Cache resultado em Redis (TTL: 24h)
      │
      └─ Pronto para cliente consultar


6. NOTIFICATION SERVICE NOTIFICA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    NOTIFICATION SERVICE
      │
      │ Consome evento: TranscriptionCompletedEvent
      │
      ├─ Se webhook configurado:
      │  └─ POST https://client.com/webhooks/transcription
      │     {
      │       "job_id": "uuid",
      │       "status": "completed",
      │       "result_url": "/api/v1/transcriptions/uuid/result"
      │     }
      │
      ├─ Se email configurado:
      │  └─ Envia email com link para resultado
      │
      ├─ Se WebSocket conectado:
      │  └─ Push notificação real-time para browser
      │
      └─ Log de notificação enviada


7. CLIENTE RECUPERA RESULTADO
━━━━━━━━━━━━━━━━━━━━━━━━━

    CLIENT
      │
      │ GET /api/v1/transcriptions/{job_id}
      ↓
    ┌─────────────────────┐
    │   API GATEWAY       │
    └─────────────────────┘
      │
      │ gRPC: GetJobStatus(job_id)
      ↓
    ┌──────────────────────────────────────┐
    │   JOB MANAGER SERVICE                │
    │                                      │
    │   SELECT from jobs WHERE id=job_id   │
    │   └─ Check cache Redis primeiro      │
    └──────────────────────────────────────┘
      │
      │ Response:
      │ {
      │   "job_id": "uuid",
      │   "status": "completed",
      │   "progress": 100,
      │   "result_url": "/api/v1/transcriptions/uuid/result",
      │   "created_at": "2025-10-23T14:30:00Z",
      │   "completed_at": "2025-10-23T14:32:00Z"
      │ }
      ↓
    ┌─────────────────────┐
    │   API GATEWAY       │
    └─────────────────────┘
      │
      │ HTTP 200
      ↓
    CLIENT


8. CLIENTE RECUPERA RESULTADO COMPLETO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    CLIENT
      │
      │ GET /api/v1/transcriptions/{job_id}/result
      ↓
    ┌─────────────────────┐
    │   API GATEWAY       │
    └─────────────────────┘
      │
      │ gRPC: GetTranscriptionResult(job_id)
      ↓
    ┌──────────────────────────────────────┐
    │   JOB MANAGER SERVICE                │
    │                                      │
    │   • Check cache Redis                │
    │   • Se não em cache, query BD        │
    │   • Serializa resultado              │
    └──────────────────────────────────────┘
      │
      │ gRPC Response (buscado do BD)
      ↓
    ┌─────────────────────┐
    │   API GATEWAY       │
    └─────────────────────┘
      │
      │ HTTP 200 JSON
      │ {
      │   "job_id": "uuid",
      │   "youtube_url": "https://youtube.com/watch?v=xyz",
      │   "text": "Full transcription...",
      │   "segments": [
      │     {
      │       "start": 0.0,
      │       "end": 5.3,
      │       "text": "Hello world"
      │     },
      │     ...
      │   ],
      │   "language": "en",
      │   "duration_seconds": 300,
      │   "processing_time_seconds": 120,
      │   "model": "base",
      │   "completed_at": "2025-10-23T14:32:00Z"
      │ }
      ↓
    CLIENT
```

---

## ⚠️ Fluxo de Erro (Error Path)

```
CENÁRIOS DE FALHA E RECUPERAÇÃO
═══════════════════════════════════════════════════════════════════════

CENÁRIO 1: Download falha (YouTube indisponível)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    DOWNLOAD SERVICE
      │
      ├─ Tenta baixar (falha 1)
      ├─ Retry com 2s delay
      ├─ Tenta baixar (falha 2)
      ├─ Retry com 4s delay
      ├─ Tenta baixar (falha 3)
      ├─ Retry com 8s delay → FALHA FINAL
      │
      └─ Publica evento:
         "TranscriptionFailedEvent"
         {
           "job_id": "uuid",
           "error": "YouTube video not available",
           "error_code": "YOUTUBE_ERROR",
           "retry_count": 3,
           "timestamp": "..."
         }
         
      ↓
    MESSAGE BROKER
    Topic: "transcription.failed"
      │
      ├─ Subscribers:
      ├─ JOB MANAGER: UPDATE jobs SET status='FAILED'
      ├─ NOTIFICATION: Notifica cliente do erro
      └─ ANALYTICS: Registra falha para análise
      
      ↓
    DLQ (Dead Letter Queue) - Mensagens que falharam
    • Armazenada por 30 dias para debugging
    • Admin pode revisar e reprocessar manualmente


CENÁRIO 2: Service crash durante processamento
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    TRANSCRIPTION SERVICE (em execução)
      │
      ├─ Processando chunk 3 de 10
      ├─ Memory leak causando OOM
      ├─ Processo é killado pelo Kubernetes
      │
      └─ [Pod é reiniciado automaticamente]
      
      ↓
    Kubernetes Liveness/Readiness Probe
      │
      ├─ Liveness: Detecta pod morto
      ├─ Termina pod
      ├─ Cria novo pod
      └─ New pod carrega modelo Whisper novamente
      
      ↓
    Message Broker (RabbitMQ/Kafka)
      │
      ├─ Mensagem não foi processada (pod morreu antes de ack)
      ├─ Mensagem volta para fila (redelivery)
      ├─ Outro worker (ou novo pod) pega mensagem
      └─ Reprocessa job (idempotent: pode processar 2x)
      
      ↓
    Resultado: Job é completado corretamente! ✓


CENÁRIO 3: Database connection fails
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    JOB MANAGER SERVICE
      │
      ├─ Tenta INSERT job no BD
      ├─ Connection timeout (DB está down)
      ├─ Retry com backoff: 1s, 2s, 4s
      ├─ Após 3 falhas: gRPC status_code = UNAVAILABLE
      │
      └─ API GATEWAY recebe UNAVAILABLE
         │
         ├─ Retorna HTTP 503 Service Unavailable
         ├─ Client recebe erro e pode tentar depois
         │
         └─ Admin notificado via alertas


CENÁRIO 4: Circuit Breaker (YouTube bloqueando requests)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    DOWNLOAD SERVICE
      │
      ├─ 5 falhas consecutivas
      ├─ Circuit Breaker OPENS
      │
      ├─ Próximas requisições:
      │  └─ Rejeitadas imediatamente (fail-fast)
      │     └─ Não desperdiça tempo tentando
      │
      ├─ Espera timeout (60s)
      ├─ Tenta 1 request (HALF-OPEN)
      │
      ├─ Se sucesso: Circuit fecha → Volta ao normal
      ├─ Se falha: Circuit reabre → Continua aberto
      │
      └─ No meio-tempo:
         • Job fica em fila esperando
         • Webhook notifica cliente (tentar depois)
         • Alertas enviados para Admin


CENÁRIO 5: Storage falha durante save
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    TRANSCRIPTION SERVICE
      │
      ├─ Transcrição completa ✓
      ├─ Tenta salvar no BD
      ├─ Falha: Disk full on S3
      │
      └─ Publica: "TranscriptionFailedEvent"
         │
         ├─ Resultado não foi salvo
         ├─ Job vai para DLQ
         ├─ Admin recebe alerta
         ├─ Admin: Aumenta storage
         ├─ Admin: Move job da DLQ para fila principal
         ├─ Serviço reprocessa (idempotent)
         └─ Sucesso na segunda tentativa ✓


CENÁRIO 6: Message Broker está down
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    TRANSCRIPTION SERVICE
      │
      ├─ Quer publicar evento
      ├─ Tenta conectar ao RabbitMQ
      ├─ Connection refused (RabbitMQ down)
      │
      └─ Opções:
         ├─ Buffer em disco local (event store)
         ├─ Retry conectar periodicamente
         │
         ├─ Quando RabbitMQ volta online:
         │  └─ Flush eventos locais → RabbitMQ
         │
         └─ Resultado: Nenhuma mensagem perdida ✓
```

---

## 🔐 Padrão de Resiliência

```
┌───────────────────────────────────────────────────────────┐
│         PADRÕES DE TOLERÂNCIA A FALHAS                    │
└───────────────────────────────────────────────────────────┘

1. RETRY COM EXPONENTIAL BACKOFF + JITTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Tentativa 1: ├─ (falha)
    Tentativa 2: ├────────── 1s ──────────┤ (falha)
    Tentativa 3: ├────────────────── 2-4s ──────────┤ (falha)
    Tentativa 4: ├──────────────────────── 4-8s ──────────┤ (sucesso)
    
    Fórmula: delay = min(base * (2^attempt) + random(0, jitter), max_delay)
    Exemplo: 1 * (2^0) + rand = 1 + 0.1 = 1.1s


2. CIRCUIT BREAKER
━━━━━━━━━━━━━━━━

                    ┌─────────────┐
                    │  CLOSED     │ ← Normal operation
                    │ (OK)        │
                    └──────┬──────┘
                        fail_rate > 50%
                           ↓
                    ┌─────────────┐
                    │   OPEN      │ ← Reject all requests
                    │ (FAIL FAST) │
                    └──────┬──────┘
                        timeout (60s)
                           ↓
                    ┌─────────────┐
                    │ HALF-OPEN   │ ← Test 1 request
                    │ (TESTING)   │
                    └──────┬──────┘
                        success/fail
                      ↙          ↘
                  CLOSED      OPEN


3. BULKHEAD PATTERN (Isolamento de recursos)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Video Worker Pool:
    ┌─────────────────────────────────────┐
    │ Max threads: 10                     │
    │ Current: 8 de 10 (80%)              │
    │ Queue: 15 jobs aguardando           │
    └─────────────────────────────────────┘
    
    Se 1 job ficar stuck (deadlock), outros 7 continuam:
    
    ✓ Thread 1: Processando job A
    ✓ Thread 2: Processando job B
    ✗ Thread 3: STUCK em job C
    ✓ Thread 4-10: Processando jobs D-J
    
    Job C não bloqueia threads 4-10


4. TIMEOUT
━━━━━━━━━━

    YouTubeClient.download(video_url, timeout=15m)
    └─ Se > 15 minutos → Cancela
    
    TranscriptionService.transcribe(audio, timeout=1h)
    └─ Se > 1 hora → Cancela e marca como FAILED


5. FALLBACK
━━━━━━━━━

    try:
        audio = youtube_api.download(url)
    except YouTubeAPIError:
        audio = youtube_transcript_api.get_transcript(url)
        └─ Rápido (1-2s) vs Whisper (1-10min)
        └─ Se ambas falham → FAILED
```

---

## 📈 Escalabilidade

```
COMO ESCALAR CADA SERVIÇO
═══════════════════════════════════════════════════════════════════════

TRANSCRIPTION SERVICE (CPU-bound)
━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Métrica de Trigger: Queue Depth > 30 jobs
    
    ┌─ Pod 1 (worker A)
    ├─ Pod 2 (worker B)
    ├─ Pod 3 (worker C)      ← Kubernetes HPA adiciona novo
    ├─ Pod 4 (worker D)        quando fila > 30
    └─ Pod 5 (worker E)
    
    CPU per pod: 2 cores (Whisper model)
    Memory per pod: 1.5GB (model cache)
    
    Max scale: 10 pods (20 cores total)


DOWNLOAD SERVICE (I/O-bound)
━━━━━━━━━━━━━━━━━━━━━━

    Métrica de Trigger: Network Saturation > 70%
    
    ┌─ Pod 1
    ├─ Pod 2
    ├─ Pod 3      ← HPA adiciona quando banda > 70%
    ├─ Pod 4
    └─ ...
    
    Cada pod: 1 core, 512MB RAM (baixa CPU)
    
    Max scale: 20 pods (I/O é paralelizável)


JOB MANAGER SERVICE (I/O-bound)
━━━━━━━━━━━━━━━━━━━━━

    Métrica de Trigger: DB Connection Pool > 80%
    
    ┌─ Pod 1
    ├─ Pod 2
    ├─ Pod 3      ← HPA adiciona quando conexões > 80%
    └─ Pod 4
    
    Cada pod: 1 core, 256MB RAM
    DB: 50 conexões (5-10 por pod)
    
    Max scale: 10 pods


NOTIFICATION SERVICE (I/O-bound)
━━━━━━━━━━━━━━━━━━━━━━

    Métrica: Webhook queue > 50 eventos
    
    ┌─ Pod 1
    ├─ Pod 2
    └─ Pod 3      ← HPA
    
    Max scale: 5 pods (baixa carga)


STORAGE SERVICE (Gerenciado)
━━━━━━━━━━━━━━━

    Usar S3 / GCS / Azure Blob (managed)
    ├─ Auto-scaling ilimitado
    ├─ Replicação automática
    ├─ CDN (CloudFront) para downloads rápidos
    └─ Versioning + Lifecycle policies


MESSAGE BROKER (RabbitMQ Cluster)
━━━━━━━━━━━━━━━━━━━━━━━━━━

    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ RabbitMQ 1   │  │ RabbitMQ 2   │  │ RabbitMQ 3   │
    │ (Master)     │  │ (Mirror)     │  │ (Mirror)     │
    └──────────────┘  └──────────────┘  └──────────────┘
           │                 │                 │
           └─────────────────┴─────────────────┘
             (Replication + HA)
    
    ├─ Queue replicada em 3 nós
    ├─ Se 1 nó cai, outros 2 continuam
    ├─ Persistência em disco
    └─ Max throughput: 50k msg/s


DATABASE (PostgreSQL)
━━━━━━━━━━━━━

    ┌──────────────┐                ┌──────────────┐
    │ PostgreSQL   │                │  Replica     │
    │ (Primary)    │ ◄─────────────► │  (Standby)   │
    └──────────────┘ Streaming      └──────────────┘
         
    ├─ Replicação contínua
    ├─ Failover automático (se Primary cai)
    ├─ Read replicas para queries pesadas
    └─ Backup diário


CACHE (Redis)
━━━━━━━

    ┌──────────────┐  Replication  ┌──────────────┐
    │  Redis 1     │ ◄────────────► │  Redis 2     │
    │  (Master)    │                │  (Replica)   │
    └──────────────┘                └──────────────┘
         
    ├─ Cache de resultados (TTL: 24h)
    ├─ Session store
    ├─ Rate limit counter
    └─ Auto-failover se Master cai
```

---

## 🔍 Monitoramento e Alertas

```
PROMETHEUS METRICS (coletadas de cada serviço)
═════════════════════════════════════════════════════════════════════

[Application Metrics]

transcription_jobs_total{status="completed"}
transcription_jobs_total{status="failed"}
transcription_jobs_total{status="pending"}

transcription_duration_seconds
  (p50: 120s, p95: 300s, p99: 600s)

transcription_errors_total{error_type="youtube_error"}
transcription_errors_total{error_type="whisper_error"}
transcription_errors_total{error_type="storage_error"}

whisper_model_load_time_seconds
whisper_inference_duration_seconds
whisper_model_cache_hit_ratio (ex: 0.95)

queue_depth{queue="transcription.jobs"}
queue_depth{queue="transcription.completed"}

http_requests_total{endpoint="/api/v1/transcriptions"}
http_request_duration_seconds{endpoint="/api/v1/transcriptions"}
http_request_status{status="200"}
http_request_status{status="400"}
http_request_status{status="429"}


[Infrastructure Metrics]

container_cpu_usage_seconds_total
container_memory_usage_bytes
container_network_receive_bytes_total
container_network_transmit_bytes_total

postgres_connections_active
postgres_connections_idle
postgres_query_duration_seconds

rabbitmq_queue_messages_ready
rabbitmq_messages_published_total
rabbitmq_messages_delivered_total

redis_used_memory_bytes
redis_connected_clients


[Alertas]

Rule: high_error_rate
  alert if: rate(transcription_errors_total[5m]) > 0.05
  for: 5m
  severity: critical

Rule: queue_backup
  alert if: queue_depth > 100
  for: 10m
  severity: warning

Rule: database_connection_pool_exhausted
  alert if: postgres_connections_active >= 48
  for: 5m
  severity: critical

Rule: pod_memory_oom_risk
  alert if: container_memory_usage_bytes > 90% of limit
  for: 5m
  severity: warning

Rule: service_unavailable
  alert if: up{job="transcription-service"} == 0
  for: 1m
  severity: critical
```

---

## 🎛️ API Gateway Routing

```
┌──────────────────────────────────────────────────────────────┐
│             KONG / NGINX API Gateway                         │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Route: /api/v1/transcriptions                              │
│  ├─ Method: POST                                             │
│  ├─ Service: job-manager-service:8001                        │
│  ├─ Rate Limit: 5/min per IP                                 │
│  ├─ Timeout: 30s                                             │
│  ├─ Retry: 3 (on 5xx)                                        │
│  └─ Cache: none (POST)                                       │
│                                                               │
│  Route: /api/v1/transcriptions/{id}                          │
│  ├─ Method: GET                                              │
│  ├─ Service: job-manager-service:8001                        │
│  ├─ Rate Limit: 10/min per IP                                │
│  ├─ Timeout: 10s                                             │
│  ├─ Retry: 3 (on 5xx)                                        │
│  └─ Cache: 5s (GET)                                          │
│                                                               │
│  Route: /api/v1/transcriptions/{id}/result                   │
│  ├─ Method: GET                                              │
│  ├─ Service: job-manager-service:8001                        │
│  ├─ Rate Limit: 10/min per IP                                │
│  ├─ Timeout: 10s                                             │
│  ├─ Retry: 3                                                 │
│  └─ Cache: 3600s (1 hora)                                    │
│                                                               │
│  Route: /api/v1/transcriptions/{id}/cancel                   │
│  ├─ Method: DELETE                                           │
│  ├─ Service: job-manager-service:8001                        │
│  ├─ Rate Limit: 1/min per IP                                 │
│  ├─ Timeout: 10s                                             │
│  └─ Retry: none (state change)                               │
│                                                               │
│  Route: /admin/*                                             │
│  ├─ Auth: JWT + RBAC (admin role)                            │
│  ├─ Service: admin-service:8006                              │
│  ├─ Rate Limit: unlimited (internal use)                     │
│  └─ Timeout: 30s                                             │
│                                                               │
│  Route: /health                                              │
│  ├─ Method: GET                                              │
│  ├─ Service: all services (aggregated)                       │
│  ├─ Rate Limit: 30/min                                       │
│  └─ Timeout: 5s                                              │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔐 Event Schema (Avro / JSON Schema)

```json
// Base event schema
{
  "event_id": "string (uuid)",
  "event_type": "string enum (TranscriptionJobCreated|...)",
  "timestamp": "ISO8601 datetime",
  "version": "string (1.0)",
  "correlation_id": "uuid (for tracing related events)",
  "causation_id": "uuid (event that caused this)",
  "data": { "object (event-specific payload)" }
}

// TranscriptionJobCreated
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "TranscriptionJobCreated",
  "timestamp": "2025-10-23T14:30:00Z",
  "version": "1.0",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440001",
  "causation_id": "550e8400-e29b-41d4-a716-446655440002",
  "data": {
    "job_id": "job-123-uuid",
    "youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "auto",
    "priority": "normal",
    "requested_by": "user@example.com",
    "webhook_url": "https://client.com/webhooks/transcription"
  }
}

// AudioDownloadedEvent
{
  "event_type": "AudioDownloadedEvent",
  "data": {
    "job_id": "job-123-uuid",
    "audio_url": "s3://bucket/audio/job-123-uuid.mp3",
    "duration_seconds": 300,
    "file_size_mb": 12.5,
    "download_time_seconds": 45
  }
}

// TranscriptionCompletedEvent
{
  "event_type": "TranscriptionCompletedEvent",
  "data": {
    "job_id": "job-123-uuid",
    "text": "Full transcription...",
    "segments": [
      {"start": 0.0, "end": 5.3, "text": "Hello"},
      {"start": 5.4, "end": 10.2, "text": "world"}
    ],
    "language": "en",
    "duration_seconds": 300,
    "processing_time_seconds": 120,
    "model": "base",
    "confidence": 0.95
  }
}

// TranscriptionFailedEvent
{
  "event_type": "TranscriptionFailedEvent",
  "data": {
    "job_id": "job-123-uuid",
    "error": "YouTube video not found",
    "error_code": "YOUTUBE_NOT_FOUND",
    "error_details": "Video removed or private",
    "retry_count": 3,
    "can_retry": false,
    "timestamp": "2025-10-23T14:35:00Z"
  }
}
```

---

**Documento versão**: 1.0.0  
**Data**: 2025-10-23  
**Status**: Em Planejamento

