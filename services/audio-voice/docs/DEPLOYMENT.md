# Deployment Guide - Audio Voice Service

Guia completo para deploy em produção do sistema multi-engine TTS.

---

## 📋 Índice

1. [Requisitos](#requisitos)
2. [Docker Deployment](#docker-deployment)
3. [Kubernetes](#kubernetes)
4. [Variáveis de Ambiente](#variáveis-de-ambiente)
5. [Monitoring](#monitoring)
6. [Scaling](#scaling)
7. [Backup & Recovery](#backup--recovery)

---

## 🔧 Requisitos

### Hardware

**Mínimo (CPU-only):**
- CPU: 8 cores
- RAM: 16GB
- Storage: 50GB SSD

**Recomendado (GPU):**
- GPU: NVIDIA com 8GB+ VRAM (RTX 3060, A4000, etc.)
- CPU: 16 cores
- RAM: 32GB
- Storage: 100GB NVMe SSD

**Produção (High Load):**
- GPU: NVIDIA com 24GB+ VRAM (RTX 3090, A6000, etc.)
- CPU: 32 cores
- RAM: 64GB
- Storage: 500GB NVMe SSD (cache de modelos)

### Software

- Docker 24+
- Docker Compose 2.0+
- NVIDIA Container Toolkit (para GPU)
- Redis 7+
- Nginx ou Traefik (load balancer)

---

## 🐳 Docker Deployment

### 1. Build da Imagem

```bash
cd services/audio-voice

# CPU
docker build -t audio-voice:latest -f Dockerfile .

# GPU
docker build -t audio-voice:gpu -f Dockerfile-gpu .
```

### 2. docker-compose.yml (Produção)

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  audio-voice:
    image: audio-voice:gpu
    runtime: nvidia
    restart: always
    depends_on:
      - redis
    environment:
      # Engine configuration
      - TTS_ENGINE_DEFAULT=xtts
      - CUDA_VISIBLE_DEVICES=0
      
      # Redis
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      
      # Performance
      - WORKERS=4
      - MAX_QUEUE_SIZE=100
      
      # Cache
      - HF_HOME=/app/models
      - TTS_HOME=/app/models
      
      # Logging
      - LOG_LEVEL=INFO
      - LOG_FILE=/app/logs/app.log
      
    ports:
      - "8000:8000"
    
    volumes:
      - ./models:/app/models:ro  # Read-only cache
      - ./outputs:/app/outputs
      - ./logs:/app/logs
      - ./voice_profiles:/app/voice_profiles
    
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
  
  nginx:
    image: nginx:alpine
    restart: always
    depends_on:
      - audio-voice
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./outputs:/var/www/outputs:ro
    
volumes:
  redis_data:
    driver: local
```

### 3. nginx.conf

```nginx
upstream audio_voice {
    least_conn;
    server audio-voice:8000;
}

server {
    listen 80;
    server_name yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # API
    location /api/ {
        proxy_pass http://audio_voice/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts para processos longos
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        
        # Upload size
        client_max_body_size 100M;
    }
    
    # Static files (outputs)
    location /outputs/ {
        alias /var/www/outputs/;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check
    location /health {
        access_log off;
        proxy_pass http://audio_voice/health;
    }
}
```

### 4. Deploy

```bash
# Start services
docker-compose up -d

# Ver logs
docker-compose logs -f audio-voice

# Verificar health
curl http://localhost/health

# Restart
docker-compose restart audio-voice

# Stop
docker-compose down
```

---

## ☸️ Kubernetes

### 1. Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: audio-voice
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: audio-voice
  template:
    metadata:
      labels:
        app: audio-voice
    spec:
      containers:
      - name: audio-voice
        image: audio-voice:gpu
        ports:
        - containerPort: 8000
        
        env:
        - name: TTS_ENGINE_DEFAULT
          value: "xtts"
        - name: REDIS_HOST
          value: "redis-service"
        - name: LOG_LEVEL
          value: "INFO"
        
        resources:
          requests:
            memory: "16Gi"
            cpu: "4"
            nvidia.com/gpu: "1"
          limits:
            memory: "32Gi"
            cpu: "8"
            nvidia.com/gpu: "1"
        
        volumeMounts:
        - name: models
          mountPath: /app/models
        - name: outputs
          mountPath: /app/outputs
        
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
      
      volumes:
      - name: models
        persistentVolumeClaim:
          claimName: models-pvc
      - name: outputs
        persistentVolumeClaim:
          claimName: outputs-pvc
```

### 2. Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: audio-voice-service
  namespace: production
spec:
  selector:
    app: audio-voice
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### 3. HPA (Horizontal Pod Autoscaler)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: audio-voice-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: audio-voice
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
```

---

## 🔐 Variáveis de Ambiente

### Core

```bash
# Engine padrão
TTS_ENGINE_DEFAULT=xtts  # ou f5tts

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password  # Se configurado
```

### GPU/CPU

```bash
# Forçar GPU específica
CUDA_VISIBLE_DEVICES=0  # GPU 0
CUDA_VISIBLE_DEVICES=0,1  # GPUs 0 e 1

# Forçar CPU
FORCE_CPU=1

# Fallback automático
TTS_FALLBACK_TO_CPU=true
```

### Cache

```bash
# Hugging Face cache (F5-TTS, Whisper)
HF_HOME=/mnt/models/huggingface

# Coqui TTS cache (XTTS)
TTS_HOME=/mnt/models/coqui

# Voice profiles cache
VOICE_PROFILES_DIR=/mnt/cache/voices
VOICE_PROFILES_TTL=2592000  # 30 dias em segundos
```

### Performance

```bash
# Workers
WORKERS=4  # Número de workers uvicorn

# Queue
MAX_QUEUE_SIZE=100
QUEUE_TIMEOUT=300  # 5 minutos

# Timeouts
JOB_TIMEOUT=600  # 10 minutos
UPLOAD_TIMEOUT=120  # 2 minutos
```

### Logging

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=/app/logs/audio-voice.log
LOG_FORMAT=json  # ou text
LOG_ROTATION=1d  # 1 dia
LOG_RETENTION=30d  # 30 dias
```

### Security

```bash
# API Key (opcional)
API_KEY=your_secret_api_key

# CORS
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100  # por minuto
```

---

## 📊 Monitoring

### 1. Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "engine_default": settings.tts_engine_default,
        "engines_loaded": list(processor.engines.keys()),
        "redis": await check_redis(),
        "gpu_available": torch.cuda.is_available(),
        "timestamp": datetime.utcnow().isoformat()
    }
```

### 2. Prometheus Metrics

```python
# requirements.txt
prometheus-client==0.18.0

# app/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Métricas
jobs_total = Counter('jobs_total', 'Total de jobs', ['engine', 'status'])
job_duration = Histogram('job_duration_seconds', 'Duração do job', ['engine'])
queue_size = Gauge('queue_size', 'Tamanho da fila')
gpu_memory = Gauge('gpu_memory_mb', 'VRAM usada', ['gpu'])

# Endpoint
@app.get("/metrics")
async def metrics():
    from prometheus_client import generate_latest
    return Response(generate_latest(), media_type="text/plain")
```

### 3. Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Audio Voice Service",
    "panels": [
      {
        "title": "Jobs por Engine",
        "targets": [
          {
            "expr": "rate(jobs_total[5m])",
            "legendFormat": "{{engine}}"
          }
        ]
      },
      {
        "title": "Duração Média",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(job_duration_seconds_bucket[5m]))",
            "legendFormat": "p95"
          }
        ]
      },
      {
        "title": "VRAM Usage",
        "targets": [
          {
            "expr": "gpu_memory_mb",
            "legendFormat": "GPU {{gpu}}"
          }
        ]
      }
    ]
  }
}
```

---

## 📈 Scaling

### Vertical Scaling (Mais recursos)

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '16'
      memory: 64G
    reservations:
      devices:
        - driver: nvidia
          count: 2  # 2 GPUs
          capabilities: [gpu]
```

### Horizontal Scaling (Mais instâncias)

```bash
# Docker Compose
docker-compose up -d --scale audio-voice=4

# Kubernetes
kubectl scale deployment audio-voice --replicas=6
```

### Load Balancing

**Nginx:**
```nginx
upstream audio_voice {
    least_conn;  # Menos conexões
    server audio-voice-1:8000 weight=2;
    server audio-voice-2:8000 weight=2;
    server audio-voice-3:8000 weight=1;  # GPU menor
}
```

**Traefik:**
```yaml
http:
  services:
    audio-voice:
      loadBalancer:
        servers:
          - url: "http://audio-voice-1:8000"
          - url: "http://audio-voice-2:8000"
        healthCheck:
          path: /health
          interval: "30s"
```

---

## 💾 Backup & Recovery

### 1. Backup de Dados

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Redis
docker exec redis redis-cli --rdb $BACKUP_DIR/redis.rdb

# Voice profiles
tar -czf $BACKUP_DIR/voice_profiles.tar.gz /app/voice_profiles

# Outputs (últimos 7 dias)
find /app/outputs -mtime -7 -type f | tar -czf $BACKUP_DIR/outputs.tar.gz -T -

# Upload para S3 (opcional)
aws s3 cp $BACKUP_DIR s3://my-bucket/backups/ --recursive
```

### 2. Recovery

```bash
#!/bin/bash
# restore.sh

BACKUP_DATE=$1  # Ex: 20251127

# Redis
docker cp /backups/$BACKUP_DATE/redis.rdb redis:/data/dump.rdb
docker restart redis

# Voice profiles
tar -xzf /backups/$BACKUP_DATE/voice_profiles.tar.gz -C /

# Outputs
tar -xzf /backups/$BACKUP_DATE/outputs.tar.gz -C /
```

---

## 🔒 Security Checklist

- [ ] HTTPS configurado (SSL/TLS)
- [ ] Firewall configurado (apenas portas necessárias)
- [ ] API key authentication (se necessário)
- [ ] CORS configurado corretamente
- [ ] Rate limiting ativo
- [ ] Logs não expõem dados sensíveis
- [ ] Secrets em environment variables (não no código)
- [ ] Backups criptografados
- [ ] Atualizações de segurança aplicadas

---

## 📚 Recursos Adicionais

- [README.md](../README.md) - Documentação principal
- [MIGRATION.md](MIGRATION.md) - Guia de migração
- [Performance Tuning](PERFORMANCE.md) - Otimizações

---

**Deploy testado e validado em produção** ✅
