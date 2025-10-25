# 🔧 REFERÊNCIA DE VARIÁVEIS DE AMBIENTE

Este documento lista todas as variáveis de ambiente disponíveis para cada microserviço.

---

## 🎵 AUDIO NORMALIZATION SERVICE (Porta 8001)

### Aplicação
```bash
APP_NAME=Audio Normalization Service
VERSION=2.0.0
ENVIRONMENT=development          # development, staging, production
DEBUG=false                      # true para debug mode
```

### Servidor
```bash
HOST=0.0.0.0                    # Interface de rede
PORT=8001                        # Porta do serviço
WORKERS=1                        # Número de workers Uvicorn
```

### Redis/Database
```bash
REDIS_URL=redis://localhost:6379/0
DATABASE__MIN_MEMORY_BYTES=52428800        # 50MB mínimo
DATABASE__MAX_CONNECTIONS=20
DATABASE__CONNECTION_TIMEOUT=5              # segundos
DATABASE__RETRY_ATTEMPTS=5
```

### Cache
```bash
CACHE__TTL_HOURS=24                        # 1-168 (7 dias max)
CACHE__CLEANUP_INTERVAL_MINUTES=30         # 5-1440
CACHE__MAX_CACHE_SIZE_MB=1024              # Tamanho máximo do cache
```

### Processamento
```bash
PROCESSING__MAX_FILE_SIZE_MB=100           # 1-500MB
PROCESSING__MAX_DURATION_MINUTES=30        # 1-120 minutos
PROCESSING__MAX_CONCURRENT_JOBS=3          # Jobs simultâneos
PROCESSING__JOB_TIMEOUT_MINUTES=30
PROCESSING__NOISE_REDUCTION_STRENGTH=0.8   # 0.1-1.0
PROCESSING__DEFAULT_SAMPLE_RATE=16000
PROCESSING__DEFAULT_BITRATE=64k
```

### Segurança
```bash
SECURITY__RATE_LIMIT_REQUESTS=100          # Requests por minuto
SECURITY__RATE_LIMIT_WINDOW=60             # Janela em segundos
SECURITY__ENABLE_FILE_CONTENT_VALIDATION=true
SECURITY__ENABLE_VIRUS_SCAN=false          # Requer ClamAV
SECURITY__MAX_UPLOAD_ATTEMPTS=3
SECURITY__VALIDATE_AUDIO_HEADERS=true
SECURITY__CHECK_FILE_ENTROPY=true
```

### Monitoramento
```bash
MONITORING__ENABLE_PROMETHEUS=true
MONITORING__METRICS_PORT=9090
MONITORING__ENABLE_TRACING=true
MONITORING__JAEGER_ENDPOINT=               # Opcional
MONITORING__LOG_CORRELATION_ID=true
MONITORING__STRUCTURED_LOGGING=true
```

### Diretórios
```bash
UPLOAD_DIR=./uploads
PROCESSED_DIR=./processed
TEMP_DIR=./temp
LOG_DIR=./logs
BACKUP_DIR=./backup
```

### Logging
```bash
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json                 # json ou text
LOG_ROTATION=1 day              # 1 hour, 1 day, 1 week
LOG_RETENTION=30 days
```

### Celery (Worker)
```bash
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_TASK_TIME_LIMIT=1800     # 30 minutos
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_WORKER_MAX_TASKS_PER_CHILD=50
```

---

## 🎤 AUDIO TRANSCRIBER SERVICE (Porta 8002)

### Aplicação
```bash
APP_NAME=Audio Transcriber Service
VERSION=2.0.0
ENVIRONMENT=development
DEBUG=false
```

### Servidor
```bash
HOST=0.0.0.0
PORT=8002
WORKERS=1
```

### Redis/Database
```bash
REDIS_URL=redis://localhost:6379/2
DATABASE__MIN_MEMORY_BYTES=52428800
DATABASE__MAX_CONNECTIONS=20
DATABASE__CONNECTION_TIMEOUT=5
DATABASE__RETRY_ATTEMPTS=5
```

### Cache
```bash
CACHE__TTL_HOURS=24
CACHE__CLEANUP_INTERVAL_MINUTES=30
CACHE__MAX_CACHE_SIZE_MB=2048
```

### Processamento
```bash
PROCESSING__MAX_FILE_SIZE_MB=200
PROCESSING__MAX_DURATION_MINUTES=60
PROCESSING__MAX_CONCURRENT_JOBS=2
PROCESSING__JOB_TIMEOUT_MINUTES=60
PROCESSING__WHISPER_MODEL=base              # tiny, base, small, medium, large
```

### Whisper Settings
```bash
WHISPER_OUTPUT_DIR=./transcriptions
WHISPER_MODEL_DIR=./models
WHISPER_DEVICE=cpu                          # cpu ou cuda
WHISPER_COMPUTE_TYPE=int8                   # int8, float16, float32
```

### Segurança
```bash
SECURITY__RATE_LIMIT_REQUESTS=50
SECURITY__RATE_LIMIT_WINDOW=60
SECURITY__ENABLE_FILE_CONTENT_VALIDATION=true
SECURITY__ENABLE_VIRUS_SCAN=false
SECURITY__MAX_UPLOAD_ATTEMPTS=3
```

### Monitoramento
```bash
MONITORING__ENABLE_PROMETHEUS=true
MONITORING__METRICS_PORT=9091
MONITORING__ENABLE_TRACING=true
MONITORING__LOG_CORRELATION_ID=true
MONITORING__STRUCTURED_LOGGING=true
```

### Diretórios
```bash
UPLOAD_DIR=./uploads
TRANSCRIPTION_DIR=./transcriptions
MODELS_DIR=./models
TEMP_DIR=./temp
LOG_DIR=./logs
BACKUP_DIR=./backup
```

### Logging
```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_ROTATION=1 day
LOG_RETENTION=30 days
```

### Celery (Worker)
```bash
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_TASK_TIME_LIMIT=3600     # 60 minutos (transcrição pode demorar)
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_WORKER_MAX_TASKS_PER_CHILD=50
```

---

## 🎬 VIDEO DOWNLOADER SERVICE (Porta 8000)

### Aplicação
```bash
APP_NAME=Video Downloader Service
VERSION=2.0.0
ENVIRONMENT=development
DEBUG=false
```

### Servidor
```bash
HOST=0.0.0.0
PORT=8000
WORKERS=1
```

### Redis/Database
```bash
REDIS_URL=redis://localhost:6379/0
DATABASE__MIN_MEMORY_BYTES=52428800
DATABASE__MAX_CONNECTIONS=20
DATABASE__CONNECTION_TIMEOUT=5
DATABASE__RETRY_ATTEMPTS=5
```

### Cache
```bash
CACHE__TTL_HOURS=24
CACHE__CLEANUP_INTERVAL_MINUTES=30
CACHE__MAX_CACHE_SIZE_GB=10
CACHE_DIR=./cache
```

### Processamento
```bash
PROCESSING__MAX_CONCURRENT_DOWNLOADS=2
PROCESSING__JOB_TIMEOUT_MINUTES=30
PROCESSING__DEFAULT_QUALITY=best            # best, 720p, 480p, 360p, audio
PROCESSING__MAX_FILE_SIZE_GB=5
PROCESSING__MAX_DURATION_MINUTES=120
```

### User Agent Management
```bash
UA_QUARANTINE_HOURS=48
UA_MAX_ERRORS=3
UA_ROTATION_ENABLED=true
UA_UPDATE_INTERVAL_HOURS=24
```

### Segurança
```bash
SECURITY__RATE_LIMIT_REQUESTS=100
SECURITY__RATE_LIMIT_WINDOW=60
SECURITY__ENABLE_URL_VALIDATION=true
SECURITY__BLOCKED_DOMAINS=localhost,127.0.0.1,0.0.0.0
SECURITY__MAX_REDIRECTS=5
```

### Monitoramento
```bash
MONITORING__ENABLE_PROMETHEUS=true
MONITORING__METRICS_PORT=9092
MONITORING__ENABLE_TRACING=false
MONITORING__LOG_CORRELATION_ID=true
MONITORING__STRUCTURED_LOGGING=true
```

### Diretórios
```bash
CACHE_DIR=./cache
LOG_DIR=./logs
BACKUP_DIR=./backup
```

### Logging
```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_ROTATION=1 day
LOG_RETENTION=30 days
```

### Download Settings
```bash
DEFAULT_QUALITY=best
MAX_CONCURRENT_DOWNLOADS=2
DOWNLOAD_TIMEOUT=300            # segundos
RETRY_ATTEMPTS=3
RETRY_DELAY=5                   # segundos
```

### Celery (Worker)
```bash
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_TASK_TIME_LIMIT=1800     # 30 minutos
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_WORKER_MAX_TASKS_PER_CHILD=50
```

---

## 📊 CONFIGURAÇÕES POR AMBIENTE

### Development (Local)
```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
REDIS_URL=redis://localhost:6379/0
WORKERS=1
```

### Staging (Testes)
```bash
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
REDIS_URL=redis://redis-staging:6379/0
WORKERS=2
```

### Production (Proxmox)
```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
REDIS_URL=redis://192.168.18.110:6379/0
WORKERS=4
MONITORING__ENABLE_PROMETHEUS=true
MONITORING__ENABLE_TRACING=true
```

---

## 🔐 VALORES SENSÍVEIS

⚠️ **NUNCA commite o arquivo .env no Git!**

Valores que devem ser mantidos em segredo:
- `REDIS_URL` (se contém senha)
- Tokens de API
- Chaves de criptografia
- Senhas de banco de dados

Sempre use `.env.example` como template e crie `.env` localmente.

---

## 🎯 VALORES RECOMENDADOS POR PERFIL

### Servidor Pequeno (2 CPU, 4GB RAM)
```bash
WORKERS=1
PROCESSING__MAX_CONCURRENT_JOBS=1
CACHE__MAX_CACHE_SIZE_MB=512
PROCESSING__MAX_FILE_SIZE_MB=50
```

### Servidor Médio (4 CPU, 8GB RAM)
```bash
WORKERS=2
PROCESSING__MAX_CONCURRENT_JOBS=3
CACHE__MAX_CACHE_SIZE_MB=2048
PROCESSING__MAX_FILE_SIZE_MB=200
```

### Servidor Grande (8+ CPU, 16GB+ RAM)
```bash
WORKERS=4
PROCESSING__MAX_CONCURRENT_JOBS=5
CACHE__MAX_CACHE_SIZE_MB=4096
PROCESSING__MAX_FILE_SIZE_MB=500
```

---

## 📝 NOTAS IMPORTANTES

1. **REDIS_URL**: Certifique-se de usar databases diferentes (0, 1, 2) para cada serviço
2. **Portas**: Verifique se as portas não estão em uso antes de iniciar
3. **Cache**: Monitore o uso de disco para evitar enchimento
4. **Logs**: Configure rotação adequada para não encher o disco
5. **Timeout**: Ajuste conforme o tamanho médio dos arquivos processados

---

**Última Atualização:** 25/10/2025
