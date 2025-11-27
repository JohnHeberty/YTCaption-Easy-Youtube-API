# 🚀 Deployment Guide - Audio Voice Service

Guia completo de implantação do Audio Voice Service (XTTS v2 + RVC) em produção.

**Última atualização:** 27 de Novembro de 2025

---

## 📑 Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Deployment Local](#deployment-local)
3. [Deployment Docker](#deployment-docker)
4. [Deployment Kubernetes](#deployment-kubernetes)
5. [Deployment Cloud (AWS/GCP/Azure)](#deployment-cloud)
6. [Configuração de Produção](#configuração-de-produção)
7. [Monitoramento](#monitoramento)
8. [Backup e Recovery](#backup-e-recovery)
9. [Scaling](#scaling)
10. [Security](#security)

---

## 📋 Pré-requisitos

### Hardware Mínimo

**Desenvolvimento (CPU):**
- CPU: 4 cores
- RAM: 8GB
- Disco: 20GB livre
- GPU: Opcional

**Produção (GPU Recomendado):**
- CPU: 8+ cores
- RAM: 16GB+
- Disco: 50GB+ SSD
- GPU: NVIDIA com 4GB+ VRAM (RTX 3060, T4, etc.)
- CUDA: 11.8+

### Software

- Docker 24.0+
- Docker Compose 2.20+
- Git
- NVIDIA Container Toolkit (se GPU)
- Redis 7+
- Linux (Ubuntu 22.04 LTS recomendado)

---

## 💻 Deployment Local

### 1. Clone e Setup

```bash
# Clone o repositório
git clone https://github.com/YourOrg/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API/services/audio-voice

# Criar ambiente virtual
python3.10 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou .\venv\Scripts\activate (Windows)

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt -c constraints.txt
```

### 2. Configurar Variáveis de Ambiente

```bash
# Copiar exemplo
cp .env.example .env

# Editar .env
nano .env
```

**.env básico:**
```bash
# Application
PORT=8005
LOG_LEVEL=INFO
ENVIRONMENT=development

# Redis
REDIS_URL=redis://localhost:6379/4

# XTTS
XTTS_DEVICE=cpu  # ou cuda
XTTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
XTTS_TEMPERATURE=0.75
XTTS_FALLBACK_CPU=true

# Limits
MAX_FILE_SIZE_MB=100
MAX_TEXT_LENGTH=10000
MAX_DURATION_MINUTES=10

# Cache
CACHE_TTL_HOURS=24
VOICE_PROFILE_TTL_DAYS=30
```

### 3. Iniciar Serviços

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: FastAPI
python run.py

# Terminal 3: Celery Worker
celery -A app.celery_config worker \
  --loglevel=info \
  --concurrency=1 \
  --pool=solo \
  -Q audio_voice_queue
```

### 4. Verificar

```bash
# Health check
curl http://localhost:8005/health | jq .

# Swagger docs
open http://localhost:8005/docs
```

---

## 🐳 Deployment Docker

### 1. Build da Imagem

```bash
# Build
docker build -t audio-voice:latest .

# Ou com GPU
docker build -f Dockerfile-gpu -t audio-voice:latest-gpu .
```

### 2. Docker Compose (Recomendado)

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: audio-voice-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  audio-voice-service:
    image: audio-voice:latest
    container_name: audio-voice-api
    ports:
      - "8005:8005"
    environment:
      - REDIS_URL=redis://redis:6379/4
      - XTTS_DEVICE=cuda
      - LOG_LEVEL=INFO
    volumes:
      - ./models:/app/models
      - ./processed:/app/processed
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    depends_on:
      - redis
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8005/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-worker:
    image: audio-voice:latest
    container_name: audio-voice-celery
    command: celery -A app.celery_config worker --loglevel=info --concurrency=2 -Q audio_voice_queue
    environment:
      - REDIS_URL=redis://redis:6379/4
      - XTTS_DEVICE=cuda
    volumes:
      - ./models:/app/models
      - ./processed:/app/processed
      - ./uploads:/app/uploads
      - ./temp:/app/temp
    depends_on:
      - redis
      - audio-voice-service
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  redis_data:
```

### 3. Iniciar Stack

```bash
# Subir todos os serviços
docker compose up -d

# Ver logs
docker compose logs -f

# Ver status
docker compose ps

# Verificar saúde
docker compose exec audio-voice-service curl http://localhost:8005/health
```

### 4. Gerenciamento

```bash
# Parar
docker compose stop

# Reiniciar
docker compose restart

# Atualizar imagem
docker compose pull
docker compose up -d

# Remover tudo
docker compose down -v  # CUIDADO: remove volumes!
```

---

## ☸️ Deployment Kubernetes

### 1. Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: audio-voice
```

### 2. ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: audio-voice-config
  namespace: audio-voice
data:
  XTTS_DEVICE: "cuda"
  XTTS_MODEL: "tts_models/multilingual/multi-dataset/xtts_v2"
  LOG_LEVEL: "INFO"
  MAX_FILE_SIZE_MB: "100"
  CACHE_TTL_HOURS: "24"
```

### 3. Secret

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: audio-voice-secret
  namespace: audio-voice
type: Opaque
stringData:
  REDIS_URL: "redis://redis-service:6379/4"
```

### 4. Redis Deployment

```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: audio-voice
spec:
  replicas: 1
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
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: audio-voice
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

### 5. Audio Voice Deployment

```yaml
# audio-voice-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: audio-voice
  namespace: audio-voice
spec:
  replicas: 2
  selector:
    matchLabels:
      app: audio-voice
  template:
    metadata:
      labels:
        app: audio-voice
    spec:
      containers:
      - name: audio-voice-api
        image: your-registry/audio-voice:latest
        ports:
        - containerPort: 8005
        envFrom:
        - configMapRef:
            name: audio-voice-config
        - secretRef:
            name: audio-voice-secret
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
            nvidia.com/gpu: "1"
          limits:
            memory: "8Gi"
            cpu: "4"
            nvidia.com/gpu: "1"
        livenessProbe:
          httpGet:
            path: /health
            port: 8005
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8005
          initialDelaySeconds: 30
          periodSeconds: 10
        volumeMounts:
        - name: models
          mountPath: /app/models
        - name: processed
          mountPath: /app/processed
      volumes:
      - name: models
        persistentVolumeClaim:
          claimName: models-pvc
      - name: processed
        persistentVolumeClaim:
          claimName: processed-pvc
      nodeSelector:
        accelerator: nvidia-tesla-t4  # ou seu tipo de GPU
---
apiVersion: v1
kind: Service
metadata:
  name: audio-voice-service
  namespace: audio-voice
spec:
  type: LoadBalancer
  selector:
    app: audio-voice
  ports:
  - port: 80
    targetPort: 8005
```

### 6. Persistent Volume Claims

```yaml
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: models-pvc
  namespace: audio-voice
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: processed-pvc
  namespace: audio-voice
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 50Gi
```

### 7. Deploy

```bash
# Aplicar manifests
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f pvc.yaml
kubectl apply -f redis-deployment.yaml
kubectl apply -f audio-voice-deployment.yaml

# Verificar pods
kubectl get pods -n audio-voice

# Ver logs
kubectl logs -f deployment/audio-voice -n audio-voice

# Get service endpoint
kubectl get svc -n audio-voice
```

---

## ☁️ Deployment Cloud

### AWS (ECS + Fargate)

#### 1. Push para ECR

```bash
# Login ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

# Build e tag
docker build -t audio-voice:latest .
docker tag audio-voice:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/audio-voice:latest

# Push
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/audio-voice:latest
```

#### 2. Task Definition

```json
{
  "family": "audio-voice",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "4096",
  "memory": "16384",
  "containerDefinitions": [
    {
      "name": "audio-voice",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/audio-voice:latest",
      "portMappings": [
        {
          "containerPort": 8005,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "XTTS_DEVICE", "value": "cpu"},
        {"name": "REDIS_URL", "value": "redis://redis.cache.amazonaws.com:6379/4"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/audio-voice",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### 3. ECS Service

```bash
# Criar serviço
aws ecs create-service \
  --cluster production \
  --service-name audio-voice \
  --task-definition audio-voice:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### GCP (Cloud Run)

```bash
# Build e deploy
gcloud builds submit --tag gcr.io/PROJECT_ID/audio-voice

# Deploy
gcloud run deploy audio-voice \
  --image gcr.io/PROJECT_ID/audio-voice \
  --platform managed \
  --region us-central1 \
  --memory 16Gi \
  --cpu 4 \
  --timeout 300 \
  --set-env-vars XTTS_DEVICE=cpu,REDIS_URL=redis://10.0.0.1:6379/4
```

### Azure (Container Instances)

```bash
# Login
az login
az acr login --name myregistry

# Build e push
docker build -t myregistry.azurecr.io/audio-voice:latest .
docker push myregistry.azurecr.io/audio-voice:latest

# Deploy
az container create \
  --resource-group production \
  --name audio-voice \
  --image myregistry.azurecr.io/audio-voice:latest \
  --cpu 4 \
  --memory 16 \
  --registry-login-server myregistry.azurecr.io \
  --registry-username <username> \
  --registry-password <password> \
  --dns-name-label audio-voice-api \
  --ports 8005 \
  --environment-variables XTTS_DEVICE=cpu REDIS_URL=redis://10.0.0.1:6379/4
```

---

## ⚙️ Configuração de Produção

### .env Produção

```bash
# Application
PORT=8005
LOG_LEVEL=INFO
ENVIRONMENT=production

# Redis
REDIS_URL=redis://redis-cluster:6379/4
REDIS_PASSWORD=your_secure_password

# XTTS
XTTS_DEVICE=cuda
XTTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
XTTS_TEMPERATURE=0.75
XTTS_REPETITION_PENALTY=1.5
XTTS_SPEED=1.0
XTTS_FALLBACK_CPU=false  # Produção: GPU obrigatória

# Security
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
API_KEY_REQUIRED=true
API_KEYS=key1,key2,key3

# Limits (produção)
MAX_FILE_SIZE_MB=100
MAX_TEXT_LENGTH=10000
MAX_DURATION_MINUTES=10
MAX_CONCURRENT_JOBS=10

# Cache (otimizado)
CACHE_TTL_HOURS=24
VOICE_PROFILE_TTL_DAYS=30
CLEANUP_INTERVAL_HOURS=6

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
```

### Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/audio-voice
upstream audio_voice {
    least_conn;
    server 127.0.0.1:8005 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8006 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Timeouts
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

    # Max body size
    client_max_body_size 100M;

    location / {
        proxy_pass http://audio_voice;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (se necessário)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Health check endpoint (bypass auth)
    location /health {
        proxy_pass http://audio_voice/health;
        access_log off;
    }
}
```

---

## 📊 Monitoramento

### Prometheus

**prometheus.yml:**
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'audio-voice'
    static_configs:
      - targets: ['localhost:9090']
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Audio Voice Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [{"expr": "rate(http_requests_total[5m])"}]
      },
      {
        "title": "Response Time",
        "targets": [{"expr": "histogram_quantile(0.95, http_request_duration_seconds)"}]
      },
      {
        "title": "Error Rate",
        "targets": [{"expr": "rate(http_requests_total{status=~\"5..\"}[5m])"}]
      },
      {
        "title": "GPU Memory",
        "targets": [{"expr": "nvidia_gpu_memory_used_bytes"}]
      }
    ]
  }
}
```

### Health Checks

```bash
# Script de monitoramento
#!/bin/bash
# /usr/local/bin/monitor-audio-voice.sh

URL="http://localhost:8005/health"
EXPECTED_STATUS="healthy"

response=$(curl -s $URL | jq -r '.status')

if [ "$response" != "$EXPECTED_STATUS" ]; then
    echo "ALERT: Audio Voice unhealthy - Status: $response"
    # Enviar alerta (Slack, PagerDuty, etc.)
    curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
      -H 'Content-Type: application/json' \
      -d "{\"text\":\"Audio Voice UNHEALTHY: $response\"}"
fi
```

---

## 💾 Backup e Recovery

### Backup de Modelos RVC

```bash
#!/bin/bash
# backup-rvc-models.sh

BACKUP_DIR="/backups/audio-voice"
DATE=$(date +%Y%m%d-%H%M%S)

# Backup modelos RVC
docker exec audio-voice-api tar czf - /app/models/rvc > \
  $BACKUP_DIR/rvc-models-$DATE.tar.gz

# Backup metadata
docker exec audio-voice-redis redis-cli --rdb /data/dump.rdb
docker cp audio-voice-redis:/data/dump.rdb $BACKUP_DIR/redis-$DATE.rdb

# Limpeza de backups antigos (>30 dias)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.rdb" -mtime +30 -delete
```

### Restore

```bash
#!/bin/bash
# restore-rvc-models.sh

BACKUP_FILE=$1

# Restore modelos
docker cp $BACKUP_FILE audio-voice-api:/tmp/backup.tar.gz
docker exec audio-voice-api tar xzf /tmp/backup.tar.gz -C /app/models/

# Restart
docker compose restart audio-voice-service
```

---

## 📈 Scaling

### Horizontal Scaling (Docker Compose)

```bash
# Escalar workers Celery
docker compose up -d --scale celery-worker=4

# Escalar API (com load balancer)
docker compose up -d --scale audio-voice-service=3
```

### Auto-scaling (Kubernetes)

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: audio-voice-hpa
  namespace: audio-voice
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

## 🔒 Security

### 1. API Key Authentication

```python
# app/middleware.py
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
```

### 2. Rate Limiting

```python
# app/middleware.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/jobs")
@limiter.limit("10/minute")
async def list_jobs():
    ...
```

### 3. HTTPS Only

```bash
# Force HTTPS redirect no nginx
if ($scheme != "https") {
    return 301 https://$server_name$request_uri;
}
```

### 4. Firewall

```bash
# UFW rules
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP (redirect)
sudo ufw allow 443/tcp  # HTTPS
sudo ufw deny 8005/tcp  # Bloquear acesso direto à API
sudo ufw enable
```

---

## ✅ Deployment Checklist

- [ ] Hardware provisionado (CPU/GPU/RAM/Disco)
- [ ] Docker e Docker Compose instalados
- [ ] NVIDIA drivers instalados (se GPU)
- [ ] Redis configurado e rodando
- [ ] Variáveis de ambiente configuradas (.env)
- [ ] Modelos XTTS baixados (~2GB)
- [ ] SSL/TLS certificado instalado
- [ ] Reverse proxy configurado (Nginx/Caddy)
- [ ] Firewall configurado
- [ ] Monitoramento configurado (Prometheus/Grafana)
- [ ] Logs centralizados (ELK/Loki)
- [ ] Backup automático configurado
- [ ] Health checks configurados
- [ ] Auto-scaling configurado (se K8s)
- [ ] Testes de carga realizados
- [ ] Documentação de runbooks criada
- [ ] Plano de disaster recovery documentado

---

## 📚 Recursos Adicionais

- [README.md](README.md) - Visão geral do serviço
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Resolução de problemas
- [AUDIO-QUALITY-TESTS.md](docs/AUDIO-QUALITY-TESTS.md) - Testes de qualidade

---

**Última atualização:** 27 de Novembro de 2025  
**Serviço:** Audio Voice v1.0.0  
**Stack:** XTTS v2 + RVC + FastAPI + Redis + Celery + Docker
