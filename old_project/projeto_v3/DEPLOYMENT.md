# DEPLOYMENT & OPERAÇÃO

## 1. Local Development (Docker Compose)

### docker-compose.yml

```yaml
version: "3.9"

services:
  # Infrastructure
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ytcaption
      POSTGRES_PASSWORD: dev123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    environment:
      RABBITMQ_DEFAULT_USER: user
      RABBITMQ_DEFAULT_PASS: password
    ports:
      - "5672:5672"
      - "15672:15672"
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

  # Services
  api-gateway:
    build:
      context: ./services/api-gateway
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:dev123@postgres:5432/ytcaption
      RABBITMQ_URL: amqp://user:password@rabbitmq:5672/
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/live"]
      interval: 10s
      timeout: 3s
      retries: 3

  job-manager:
    build:
      context: ./services/job-manager
    ports:
      - "8001:8001"
    environment:
      DATABASE_URL: postgresql://postgres:dev123@postgres:5432/ytcaption
      RABBITMQ_URL: amqp://user:password@rabbitmq:5672/
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  downloader:
    build:
      context: ./services/downloader
    ports:
      - "8002:8002"
    environment:
      RABBITMQ_URL: amqp://user:password@rabbitmq:5672/
      MINIO_URL: http://minio:9000
    depends_on:
      rabbitmq:
        condition: service_healthy

  transcriber:
    build:
      context: ./services/transcriber
    ports:
      - "8003:8003"
    environment:
      RABBITMQ_URL: amqp://user:password@rabbitmq:5672/
    depends_on:
      rabbitmq:
        condition: service_healthy

  storage:
    build:
      context: ./services/storage
    ports:
      - "8004:8004"
    environment:
      MINIO_URL: http://minio:9000
      DATABASE_URL: postgresql://postgres:dev123@postgres:5432/ytcaption
    depends_on:
      postgres:
        condition: service_healthy

  notifier:
    build:
      context: ./services/notifier
    ports:
      - "8005:8005"
    environment:
      RABBITMQ_URL: amqp://user:password@rabbitmq:5672/
      SMTP_HOST: smtp.gmail.com
      SMTP_PORT: 587
    depends_on:
      rabbitmq:
        condition: service_healthy

  admin:
    build:
      context: ./services/admin
    ports:
      - "8006:8006"
    environment:
      DATABASE_URL: postgresql://postgres:dev123@postgres:5432/ytcaption
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  # Monitoring
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./infra/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  postgres_data:
  redis_data:
  minio_data:
  prometheus_data:
  grafana_data:
```

### Start

```bash
docker-compose up -d
docker-compose logs -f api-gateway

# Verify all services
curl http://localhost:8000/health/live
curl http://localhost:8001/health/live
curl http://localhost:8002/health/live
# ...
```

---

## 2. Production (Kubernetes)

### Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ytcaption
```

### PostgreSQL StatefulSet

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: ytcaption
spec:
  serviceName: postgres
  replicas: 2  # Primary + Replica
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
        - name: POSTGRES_DB
          value: ytcaption
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secrets
              key: password
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        livenessProbe:
          exec:
            command: ["pg_isready", "-U", "postgres"]
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "postgres"]
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 100Gi
```

### API Gateway Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: ytcaption
spec:
  replicas: 3  # Horizontal scaling
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      terminationGracePeriodSeconds: 30
      containers:
      - name: api-gateway
        image: ytcaption/api-gateway:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database_url
        - name: RABBITMQ_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: rabbitmq_url
        - name: LOG_LEVEL
          value: INFO
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 1
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 1
          failureThreshold: 2
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 5"]

  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: ytcaption
spec:
  type: LoadBalancer
  selector:
    app: api-gateway
  ports:
  - port: 80
    targetPort: 8000
    name: http
```

### HPA (Horizontal Pod Autoscaler)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: ytcaption
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
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
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
      - type: Pods
        value: 2
        periodSeconds: 60
      selectPolicy: Max
```

### Pod Disruption Budget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway-pdb
  namespace: ytcaption
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api-gateway
```

### Resource Quotas

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: ytcaption-quota
  namespace: ytcaption
spec:
  hard:
    requests.cpu: "10"
    requests.memory: "20Gi"
    limits.cpu: "20"
    limits.memory: "40Gi"
    pods: "50"
    services: "20"
```

### Secrets

```bash
kubectl create secret generic app-secrets \
  --from-literal=database_url='postgresql://...' \
  --from-literal=rabbitmq_url='amqp://...' \
  -n ytcaption

kubectl create secret generic db-secrets \
  --from-literal=password='securepwd123' \
  -n ytcaption
```

---

## 3. CI/CD Pipeline

### GitHub Actions

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_PASSWORD: test123
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=.

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: docker/setup-buildx-action@v2
      - uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      - uses: docker/build-push-action@v4
        with:
          push: true
          tags: ytcaption/api-gateway:${{ github.sha }}

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: azure/setup-kubectl@v3
      - run: |
          kubectl set image deployment/api-gateway \
            api-gateway=ytcaption/api-gateway:${{ github.sha }} \
            -n ytcaption

  deploy-prod:
    needs: deploy-staging
    runs-on: ubuntu-latest
    if: github.event.ref == 'refs/heads/main'
    environment: production
    steps:
      - uses: actions/checkout@v3
      - uses: azure/setup-kubectl@v3
      - run: |
          kubectl set image deployment/api-gateway \
            api-gateway=ytcaption/api-gateway:${{ github.sha }} \
            -n ytcaption --record
```

---

## 4. Backup & Recovery

### Automated Backup

```bash
#!/bin/bash
# backup-postgres.sh

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="$BACKUP_DIR/ytcaption-$DATE.sql.gz"

mkdir -p $BACKUP_DIR

# Full backup
pg_dump -h $DB_HOST -U postgres ytcaption | gzip > $BACKUP_FILE

# Upload to S3
aws s3 cp $BACKUP_FILE s3://ytcaption-backups/

# Cleanup local (keep 7 days)
find $BACKUP_DIR -mtime +7 -delete

echo "Backup complete: $BACKUP_FILE"
```

**Cron**: `0 2 * * * /usr/local/bin/backup-postgres.sh` (Daily 2am)

### Recovery Test (Monthly)

```bash
#!/bin/bash
# test-restore.sh

BACKUP_FILE="$1"  # Latest backup

# Create test database
createdb ytcaption_test

# Restore
gunzip -c $BACKUP_FILE | psql ytcaption_test

# Verify (count tables, records)
psql ytcaption_test -c "SELECT count(*) FROM jobs;"

# Cleanup
dropdb ytcaption_test

echo "Recovery test passed"
```

---

## 5. Monitoring & Alerting

### Prometheus Config

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'api-gateway'
    static_configs:
      - targets: ['api-gateway:8000']
    metrics_path: '/metrics'

  - job_name: 'job-manager'
    static_configs:
      - targets: ['job-manager:8001']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'rabbitmq'
    static_configs:
      - targets: ['rabbitmq:15692']
```

### Alert Rules

```yaml
groups:
- name: ytcaption
  rules:
  - alert: HighErrorRate
    expr: rate(http_errors_total[5m]) > 0.01
    for: 5m
    annotations:
      summary: "High error rate"

  - alert: HighLatency
    expr: histogram_quantile(0.95, http_request_duration_seconds) > 0.5
    for: 5m
    annotations:
      summary: "P95 latency > 500ms"

  - alert: PodDown
    expr: kube_pod_status_phase{namespace="ytcaption"} == 0
    for: 1m
    annotations:
      summary: "Pod down in ytcaption"
```

---

**Próximo**: Leia `MONITORAMENTO.md`
