# Orchestrator API

API orquestradora que coordena o pipeline completo de processamento de vídeos do YouTube.

## Visão Geral

O Orchestrator é o ponto de entrada do sistema. Ele:

1. Recebe requests dos clientes
2. Cria e gerencia jobs no Redis
3. Coordena os 3 microserviços (download → normalize → transcribe)
4. Implementa retry automático e polling resiliente
5. Retorna resultados consolidados

## Endpoints

### POST `/pipeline`

Inicia processamento de um vídeo.

**Request**:
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "auto",
  "language_out": null,
  "remove_noise": true,
  "convert_to_mono": true,
  "apply_highpass_filter": false,
  "set_sample_rate_16k": true,
  "isolate_vocals": false
}
```

**Response**:
```json
{
  "job_id": "a1b2c3d4e5f6g7h8",
  "status": "queued",
  "message": "Pipeline iniciado com sucesso",
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "overall_progress": 0.0
}
```

### GET `/jobs/{job_id}`

Consulta status detalhado do job.

**Response**:
```json
{
  "job_id": "a1b2c3d4e5f6g7h8",
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "status": "completed",
  "overall_progress": 100.0,
  "created_at": "2025-10-29T10:00:00",
  "updated_at": "2025-10-29T10:05:30",
  "completed_at": "2025-10-29T10:05:30",
  "stages": {
    "download": {
      "status": "completed",
      "job_id": "FtnKP8fSSdc_audio",
      "progress": 100.0,
      "started_at": "2025-10-29T10:00:05",
      "completed_at": "2025-10-29T10:01:15"
    },
    "normalization": {
      "status": "completed",
      "job_id": "norm_a1b2c3d4",
      "progress": 100.0,
      "started_at": "2025-10-29T10:01:20",
      "completed_at": "2025-10-29T10:02:45"
    },
    "transcription": {
      "status": "completed",
      "job_id": "trans_x9y8z7w6",
      "progress": 100.0,
      "started_at": "2025-10-29T10:02:50",
      "completed_at": "2025-10-29T10:05:30"
    }
  },
  "transcription_text": "Este é o texto completo da transcrição...",
  "transcription_segments": [
    {
      "text": "Este é o primeiro segmento",
      "start": 0.0,
      "end": 2.5,
      "duration": 2.5
    },
    {
      "text": "Este é o segundo segmento",
      "start": 2.5,
      "end": 5.0,
      "duration": 2.5
    }
  ],
  "transcription_file": "transcription.srt",
  "audio_file": "audio_normalized.webm"
}
```

### GET `/jobs`

Lista jobs recentes.

**Query Params**:
- `limit` (opcional): Número máximo de jobs (padrão: 50)

**Response**:
```json
{
  "total": 10,
  "jobs": [
    {
      "job_id": "a1b2c3d4",
      "youtube_url": "https://...",
      "status": "completed",
      "progress": 100.0,
      "created_at": "2025-10-29T10:00:00",
      "updated_at": "2025-10-29T10:05:00"
    }
  ]
}
```

### GET `/health`

Health check do orchestrator + microserviços.

**Response**:
```json
{
  "status": "healthy",
  "service": "ytcaption-orchestrator",
  "version": "1.0.0",
  "timestamp": "2025-10-29T10:00:00",
  "microservices": {
    "video-downloader": "healthy",
    "audio-normalization": "healthy",
    "audio-transcriber": "healthy"
  }
}
```

### GET `/admin/stats`

Estatísticas do orchestrator.

**Response**:
```json
{
  "orchestrator": {
    "version": "1.0.0",
    "environment": "production"
  },
  "redis": {
    "total_jobs": 150,
    "active_jobs": 5,
    "completed_jobs": 145,
    "memory_usage": "12.5MB"
  },
  "settings": {
    "cache_ttl_hours": 24,
    "job_timeout_minutes": 60,
    "poll_interval": 3,
    "max_poll_attempts": 600
  }
}
```

### POST `/admin/cleanup`

Remove jobs antigos do cache.

**Query Params**:
- `max_age_hours` (opcional): Idade máxima dos jobs em horas (padrão: 24)
- `deep` (opcional): Se true, remove também logs (padrão: false)

**Response**:
```json
{
  "message": "Cleanup executado com sucesso",
  "jobs_removed": 15,
  "logs_cleaned": false
}
```

### POST `/admin/factory-reset`

⚠️ **CUIDADO**: Remove TUDO de TODOS os serviços!

**Response**:
```json
{
  "message": "Factory reset executado em todos os serviços",
  "orchestrator": {
    "jobs_removed": 150,
    "logs_cleaned": true
  },
  "microservices": {
    "video-downloader": {
      "status": "success",
      "data": {"files_removed": 50, "tasks_purged": 25}
    },
    "audio-normalization": {
      "status": "success",
      "data": {"files_removed": 45, "tasks_purged": 20}
    },
    "audio-transcriber": {
      "status": "success",
      "data": {"files_removed": 55, "tasks_purged": 30}
    }
  },
  "warning": "Todos os dados foram removidos de todos os serviços"
}
```

## Arquitetura Interna

### Fluxo do Pipeline

```python
async def execute_pipeline(job):
    # 1. Download (video-downloader)
    audio_bytes, filename = await _execute_download(job)
    
    # 2. Normalization (audio-normalization)
    normalized_bytes, norm_filename = await _execute_normalization(job, audio_bytes, filename)
    
    # 3. Transcription (audio-transcriber)
    transcription = await _execute_transcription(job, normalized_bytes, norm_filename)
    
    # 4. Consolidação
    job.transcription_text = transcription["text"]
    job.transcription_segments = transcription["segments"]
    job.mark_as_completed()
    
    return job
```

### Resiliência

**1. Retry com Exponential Backoff**

```python
async def _retry_with_backoff(func):
    for attempt in range(max_retries):
        try:
            return await func()
        except HTTPStatusError as e:
            # Não retenta erros 4xx
            if 400 <= e.response.status_code < 500:
                raise
            
            # Retenta erros 5xx com backoff
            delay = retry_delay * (2 ** attempt)  # 2s, 4s, 8s
            await asyncio.sleep(delay)
```

**2. Polling Resiliente**

```python
async def _wait_until_done(client, job_id, stage):
    for attempt in range(max_poll_attempts):  # 600 tentativas
        status = await client.get_status(job_id)
        
        if status["status"] == "completed":
            return status
        
        if status["status"] == "failed":
            raise RuntimeError(status["error"])
        
        # Atualiza progresso
        stage.progress = status.get("progress", 0)
        
        await asyncio.sleep(poll_interval)  # 3 segundos
```

**3. Health Checks**

```python
async def check_services_health():
    for service in [video, audio, transcription]:
        ok = await service.check_health()
        if not ok:
            logger.warning(f"{service} unhealthy, but proceeding")
```

## Configuração

### Variáveis de Ambiente

```bash
# Redis
REDIS_URL=redis://localhost:6379/0

# Servidor
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Polling
POLL_INTERVAL=3              # Segundos entre cada poll
MAX_POLL_ATTEMPTS=600        # 30min total (600 × 3s)

# Retry
HTTP_MAX_RETRIES=3
RETRY_BACKOFF_BASE_SECONDS=1.5

# Cache
CACHE_TTL_HOURS=24
JOB_TIMEOUT_MINUTES=60

# Microserviços
VIDEO_DOWNLOADER_URL=http://localhost:8001
AUDIO_NORMALIZATION_URL=http://localhost:8002
AUDIO_TRANSCRIBER_URL=http://localhost:8003

# Timeouts (segundos)
VIDEO_DOWNLOADER_TIMEOUT=300
AUDIO_NORMALIZATION_TIMEOUT=180
AUDIO_TRANSCRIBER_TIMEOUT=600

# Defaults
DEFAULT_LANGUAGE=auto
DEFAULT_REMOVE_NOISE=true
DEFAULT_CONVERT_MONO=true
DEFAULT_SAMPLE_RATE_16K=true
```

## Logs

Estrutura de logs:

```
orchestrator/
└── logs/
    ├── orchestrator.log           # Log principal
    └── orchestrator.log.1         # Rotacionado
```

Formato:
```
2025-10-29 10:00:00,123 - modules.orchestrator - INFO - Starting pipeline for job a1b2c3d4
2025-10-29 10:00:05,456 - modules.orchestrator - INFO - Video job submitted: FtnKP8fSSdc_audio
2025-10-29 10:01:15,789 - modules.orchestrator - INFO - Transcription text retrieved: 1234 chars
```

## Debugging

### Ver logs em tempo real

```bash
docker-compose logs -f orchestrator
```

### Inspecionar job no Redis

```bash
docker exec -it ytcaption-redis redis-cli
GET orchestrator:job:JOB_ID
```

### Testar pipeline manualmente

```python
import httpx
import json

# 1. Submeter job
response = httpx.post("http://localhost:8000/pipeline", json={
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "auto"
})
job_data = response.json()
job_id = job_data["job_id"]

# 2. Polling manual
import time
while True:
    status = httpx.get(f"http://localhost:8000/jobs/{job_id}")
    data = status.json()
    print(f"Status: {data['status']}, Progress: {data['overall_progress']}%")
    
    if data["status"] in ["completed", "failed"]:
        break
    
    time.sleep(5)

# 3. Ver resultado
if data["status"] == "completed":
    print("Texto:", data["transcription_text"][:200])
    print("Segments:", len(data["transcription_segments"]))
```

## Performance

### Métricas Típicas

| Etapa | Tempo Médio | Varia com |
|-------|-------------|-----------|
| Download | 10-30s | Tamanho do vídeo, qualidade da internet |
| Normalização | 5-15s | Duração do áudio, filtros aplicados |
| Transcrição | 30s-5min | Duração do áudio, modelo Whisper |

**Total**: 1-6 minutos para vídeo de 10 minutos.

### Otimizações

1. **Cache Redis**: Evita reprocessamento (24h TTL)
2. **Streaming**: Arquivos não são salvos em disco (exceto cache)
3. **Parallelização**: Workers Celery processamjobs em paralelo
4. **Retry inteligente**: Não retenta erros 4xx (economiza recursos)

## Troubleshooting

### Job fica em "queued"

```bash
# Verifica se microserviços estão rodando
curl http://localhost:8000/health

# Verifica logs
docker-compose logs -f orchestrator
```

### Job fica em "downloading" por muito tempo

```bash
# Verifica worker do video-downloader
docker-compose logs -f video-downloader-celery

# Verifica job no Redis
docker exec ytcaption-redis redis-cli GET celery-task-meta-TASK_ID
```

### Erro "Connection refused"

```bash
# Verifica URLs no .env
cat orchestrator/.env | grep _URL

# Testa conexão direta
curl http://192.168.18.132:8001/health
```

### Timeout no polling

```bash
# Aumenta timeout no .env
MAX_POLL_ATTEMPTS=1200  # 60min (1200 × 3s)
AUDIO_TRANSCRIBER_TIMEOUT=1200  # 20min

# Reinicia orchestrator
docker-compose restart orchestrator
```
