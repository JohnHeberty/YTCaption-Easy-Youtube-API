# 📦 Deployment Guide

Complete guide for deploying YTCaption to production environments.

---

## 📋 Table of Contents

1. [Deployment Methods](#deployment-methods)
2. [Docker Compose Deployment](#docker-compose-deployment)
3. [Production Deployment with Nginx](#production-deployment-with-nginx)
4. [SSL/TLS Configuration](#ssltls-configuration)
5. [Environment Configuration](#environment-configuration)
6. [Health Checks & Monitoring](#health-checks--monitoring)
7. [Blue-Green Deployment](#blue-green-deployment)
8. [Backup & Rollback](#backup--rollback)
9. [Security Hardening](#security-hardening)
10. [Update & Maintenance](#update--maintenance)

---

## Deployment Methods

### Quick Comparison

| Method | Best For | Complexity | Downtime |
|--------|----------|------------|----------|
| **Docker Compose** | Development, staging, small production | Low | Yes (30-60s) |
| **Docker Compose + Nginx** | Production (single server) | Medium | Minimal (<5s) |
| **Blue-Green** | High-availability production | High | Zero |

### Recommended Approach

- **Small projects** (1-50 users): Docker Compose only
- **Production** (50+ users): Docker Compose + Nginx + SSL
- **Mission-critical** (high availability): Blue-Green deployment

---

## Docker Compose Deployment

### Prerequisites

**Server Requirements**:
- **OS**: Ubuntu 22.04+ / Debian 11+ / RHEL 8+
- **CPU**: 4+ cores (8+ recommended)
- **RAM**: 8GB minimum (16GB+ for medium/large models)
- **Disk**: 20GB free space
- **Network**: Public IP or domain name (for SSL)

**Software Requirements**:
```bash
# Check versions
docker --version        # 20.10+
docker compose version  # 2.0+
```

See [Installation Guide](./02-installation.md) if Docker is not installed.

---

### Quick Deployment (start.sh)

**Step 1**: Clone repository
```bash
cd /opt
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
```

**Step 2**: Run automated script
```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

**What the script does**:
1. ✅ Detects CPU cores and RAM (auto-configuration)
2. ✅ Detects GPU availability (NVIDIA CUDA)
3. ✅ Recommends optimal Whisper model
4. ✅ Configures `.env` with detected resources
5. ✅ Updates `docker-compose.yml` resource limits
6. ✅ Builds and starts containers
7. ✅ Waits for health check (max 20s)

**Example output**:
```
==================================
   YTCaption Startup Script
==================================
✓ Detected: 8 cores / 16 threads
✓ Using 100% of CPU cores: 8
✓ Detected: 16GB RAM (16384MB)
✓ Using 100% of RAM: 16GB
✓ NVIDIA GPU detected on host: NVIDIA RTX 3090
✓ Docker GPU access: OK
✓ Recommended: medium (with GPU)
✓ Docker installed: 24.0.7
✓ Docker Compose installed: 2.21.0

==================================
  Configuration Summary
==================================
CPU Cores:        8 (100% allocated)
Docker CPUs:      8
Uvicorn Workers:  1 (default, optimal)
Parallel Transc:  ENABLED (auto-detect 8 cores)
Total RAM:        16GB (16384MB available)
Docker Memory:    16G (16384MB, 100% allocated)
Whisper Device:   cuda
Whisper Model:    medium
GPU Available:    true
==================================

Start YTCaption with this configuration? (Y/n): y

✓ YTCaption started successfully!
✓ Service is ready!

==================================
  YTCaption is running!
==================================
API URL:        http://localhost:8000
Documentation:  http://localhost:8000/docs
Health Check:   http://localhost:8000/health
```

---

### Custom Configuration (start.sh options)

**Available flags**:
```bash
./scripts/start.sh --help

Options:
  --force-rebuild       Force rebuild Docker images
  --no-gpu             Disable GPU even if available
  --no-parallel        Disable parallel transcription
  --model MODEL        Set Whisper model (tiny|base|small|medium|large)
  --workers NUM        Set Uvicorn workers (default: 1)
  --parallel-workers N Set parallel transcription workers (default: auto)
  --memory MB          Set Docker memory limit in MB
```

**Examples**:

**1. Custom memory limit** (e.g., 8GB on 16GB server):
```bash
./scripts/start.sh --memory 8192
```

**2. Force CPU mode** (no GPU):
```bash
./scripts/start.sh --no-gpu --model base
```

**3. High-volume production** (4 parallel workers):
```bash
./scripts/start.sh --model medium --parallel-workers 4 --memory 12288
```

**4. Rebuild after code update**:
```bash
./scripts/start.sh --force-rebuild
```

---

### Manual Deployment (docker-compose)

**Step 1**: Configure environment
```bash
cp .env.example .env
nano .env
```

**Recommended production settings** (v3.0):
```bash
# App & Server
WHISPER_MODEL=base  # or medium with GPU
WORKERS=1
REQUEST_TIMEOUT=3600
MAX_CONCURRENT_REQUESTS=5

# Parallel Transcription (v2.0)
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4
PARALLEL_CHUNK_DURATION=120

# YouTube Resilience (v3.0) - CRITICAL
YOUTUBE_MAX_RETRIES=5
YOUTUBE_RETRY_DELAY_MIN=10
YOUTUBE_RETRY_DELAY_MAX=120
YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=8
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=180
YOUTUBE_REQUESTS_PER_MINUTE=10
YOUTUBE_REQUESTS_PER_HOUR=200
YOUTUBE_COOLDOWN_ON_ERROR=60

# Multi-Strategy Download (v3.0)
ENABLE_MULTI_STRATEGY=true
ENABLE_USER_AGENT_ROTATION=true

# Limits
MAX_VIDEO_SIZE_MB=2500
MAX_VIDEO_DURATION_SECONDS=10800
DOWNLOAD_TIMEOUT=900

# Cleanup & Logs
CLEANUP_ON_STARTUP=true
LOG_LEVEL=INFO
```

See [Configuration Guide](./03-configuration.md) for all variables.

**Step 2**: Build and start
```bash
docker compose build
docker compose up -d
```

**Step 3**: Verify deployment
```bash
# Check container status
docker compose ps

# Expected output:
# whisper-transcription-api   Up (healthy)
# whisper-prometheus          Up
# whisper-grafana             Up
# whisper-tor-proxy           Up

# Check logs
docker compose logs -f --tail=50

# Test API
curl http://localhost:8000/health
# {"status":"healthy"}

curl http://localhost:8000/health/ready
# {"status":"ready","checks":{"whisper":true,"youtube":true,...}}
```

---

### Container Management

**View logs**:
```bash
docker compose logs -f                # All containers
docker compose logs -f whisper-api    # API only
docker compose logs --tail=100        # Last 100 lines
```

**Restart containers**:
```bash
docker compose restart              # All
docker compose restart whisper-api  # API only
```

**Stop containers**:
```bash
docker compose down      # Stop and remove
docker compose stop      # Stop only (keep containers)
```

**Check resource usage**:
```bash
docker stats whisper-transcription-api

# Output:
# CONTAINER                   CPU %   MEM USAGE / LIMIT   NET I/O
# whisper-transcription-api   45%     4.2GB / 16GB        1.2GB / 800MB
```

---

## Production Deployment with Nginx

### Architecture

```
Internet → Nginx (443/SSL) → Docker (8000) → YTCaption API
          ↓ (reverse proxy)
          - SSL termination
          - Rate limiting
          - Load balancing
          - Caching (optional)
```

### Prerequisites

**Install Nginx**:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y nginx

# RHEL/CentOS
sudo yum install -y nginx
```

**Check installation**:
```bash
nginx -v
# nginx version: nginx/1.24.0
```

---

### Nginx Configuration

**Step 1**: Create virtual host

Create `/etc/nginx/sites-available/ytcaption`:
```nginx
# Upstream backend
upstream ytcaption_backend {
    server localhost:8000;
    keepalive 64;
}

# Redirect HTTP → HTTPS (will be configured by Certbot)
server {
    listen 80;
    server_name api.yourdomain.com;
    
    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS configuration
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    
    # SSL certificates (will be configured by Certbot)
    # ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;
    
    # SSL configuration (modern, secure)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Logs
    access_log /var/log/nginx/ytcaption-access.log;
    error_log /var/log/nginx/ytcaption-error.log;
    
    # Client limits
    client_max_body_size 500M;         # Max upload size (audio files)
    client_body_timeout 300s;          # 5 minutes
    
    # Proxy timeouts (for long transcriptions)
    proxy_connect_timeout 3600s;       # 1 hour
    proxy_send_timeout 3600s;
    proxy_read_timeout 3600s;
    send_timeout 3600s;
    
    # Proxy headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    proxy_http_version 1.1;
    
    # Main location
    location / {
        proxy_pass http://ytcaption_backend;
    }
    
    # Health check endpoint (no rate limit)
    location = /health {
        access_log off;
        proxy_pass http://ytcaption_backend;
    }
    
    # API endpoints (with rate limiting)
    location ~ ^/api/v1/(transcribe|video/info) {
        # Rate limit: 10 req/min per IP
        limit_req zone=api_limit burst=5 nodelay;
        limit_req_status 429;
        
        proxy_pass http://ytcaption_backend;
    }
}

# Rate limiting zone (10 requests/minute per IP)
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/m;
```

**Step 2**: Enable site
```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/ytcaption /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Expected output:
# nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
# nginx: configuration file /etc/nginx/nginx.conf test is successful

# Reload Nginx
sudo systemctl reload nginx
```

---

### Firewall Configuration

**UFW (Ubuntu/Debian)**:
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Check status
sudo ufw status
```

**Firewalld (RHEL/CentOS)**:
```bash
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# Check status
sudo firewall-cmd --list-all
```

---

## SSL/TLS Configuration

### Certbot (Let's Encrypt)

**Step 1**: Install Certbot
```bash
# Ubuntu/Debian
sudo apt install -y certbot python3-certbot-nginx

# RHEL/CentOS
sudo yum install -y certbot python3-certbot-nginx
```

**Step 2**: Obtain certificate
```bash
sudo certbot --nginx -d api.yourdomain.com
```

**Follow prompts**:
```
Enter email address: your-email@example.com
(A)gree to terms: A
Receive newsletter: Y or N
```

**Certbot automatically**:
- ✅ Obtains SSL certificate from Let's Encrypt
- ✅ Configures Nginx with SSL settings
- ✅ Sets up auto-renewal via cron job

**Step 3**: Verify auto-renewal
```bash
# Check renewal timer
sudo systemctl status certbot.timer

# Test renewal (dry run)
sudo certbot renew --dry-run
```

**Step 4**: Check certificate
```bash
sudo certbot certificates

# Output:
# Certificate Name: api.yourdomain.com
#   Domains: api.yourdomain.com
#   Expiry Date: 2025-01-20 12:00:00+00:00 (VALID: 89 days)
#   Certificate Path: /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem
#   Private Key Path: /etc/letsencrypt/live/api.yourdomain.com/privkey.pem
```

---

### Manual SSL Configuration

If using custom SSL certificates (not Let's Encrypt):

**Step 1**: Copy certificates
```bash
sudo mkdir -p /etc/nginx/ssl
sudo cp your_cert.crt /etc/nginx/ssl/ytcaption.crt
sudo cp your_key.key /etc/nginx/ssl/ytcaption.key
sudo chmod 600 /etc/nginx/ssl/ytcaption.key
```

**Step 2**: Update Nginx config
```nginx
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    
    # Custom SSL certificates
    ssl_certificate /etc/nginx/ssl/ytcaption.crt;
    ssl_certificate_key /etc/nginx/ssl/ytcaption.key;
    
    # ... rest of configuration
}
```

**Step 3**: Reload Nginx
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## Environment Configuration

### Production-Optimized Settings

**Scenario 1**: High-volume production (100+ requests/day)
```bash
# Aggressive with protections
WHISPER_MODEL=medium          # Good quality
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=6            # More workers

YOUTUBE_REQUESTS_PER_MINUTE=15
YOUTUBE_REQUESTS_PER_HOUR=300
YOUTUBE_MAX_RETRIES=7
YOUTUBE_COOLDOWN_ON_ERROR=20
MAX_CONCURRENT_REQUESTS=8
```

**Scenario 2**: Medium-volume production (20-100 requests/day)
```bash
# Balanced (recommended)
WHISPER_MODEL=base            # Balanced speed/quality
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4

YOUTUBE_REQUESTS_PER_MINUTE=10
YOUTUBE_REQUESTS_PER_HOUR=200
YOUTUBE_MAX_RETRIES=5
YOUTUBE_COOLDOWN_ON_ERROR=30
MAX_CONCURRENT_REQUESTS=5
```

**Scenario 3**: Low-volume production (<20 requests/day)
```bash
# Conservative
WHISPER_MODEL=base
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2

YOUTUBE_REQUESTS_PER_MINUTE=5
YOUTUBE_REQUESTS_PER_HOUR=100
YOUTUBE_MAX_RETRIES=3
YOUTUBE_COOLDOWN_ON_ERROR=60
MAX_CONCURRENT_REQUESTS=3
```

**Scenario 4**: YouTube blocking aggressively
```bash
# Maximum protection
WHISPER_MODEL=base
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4

# Very conservative rate limits
YOUTUBE_REQUESTS_PER_MINUTE=3
YOUTUBE_REQUESTS_PER_HOUR=50
YOUTUBE_MAX_RETRIES=7
YOUTUBE_COOLDOWN_ON_ERROR=120
YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=5
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=300
YOUTUBE_RETRY_DELAY_MIN=10
YOUTUBE_RETRY_DELAY_MAX=180
```

See [Configuration Guide](./03-configuration.md) for detailed explanations.

---

### Applying Configuration Changes

**Step 1**: Edit `.env`
```bash
nano .env
# Make changes
```

**Step 2**: Restart containers
```bash
docker compose restart
```

**Step 3**: Verify
```bash
# Check logs
docker compose logs -f --tail=50

# Test API
curl https://api.yourdomain.com/health
```

**Note**: Most configuration changes require container restart. Only DNS and some network settings can be hot-reloaded.

---

## Health Checks & Monitoring

### Built-in Health Endpoints

**1. Basic health check** (`/health`):
```bash
curl https://api.yourdomain.com/health

# Response:
{
  "status": "healthy",
  "timestamp": "2025-10-22T15:30:45.123Z"
}
```

**2. Readiness probe** (`/health/ready`):
```bash
curl https://api.yourdomain.com/health/ready

# Response:
{
  "status": "ready",
  "timestamp": "2025-10-22T15:30:45.123Z",
  "checks": {
    "whisper": true,           # Model loaded
    "youtube": true,           # yt-dlp available
    "ffmpeg": true,            # FFmpeg available
    "disk_space": true,        # >1GB free
    "temp_dir": true,          # Writable
    "cache": true,             # Cache initialized
    "worker_pool": true        # Workers ready (if parallel enabled)
  }
}
```

**3. Metrics endpoint** (`/metrics`):
```bash
curl https://api.yourdomain.com/metrics

# Prometheus metrics (excerpt):
# transcription_requests_total 1234
# transcription_duration_seconds_sum 5678.9
# youtube_download_errors_total{strategy="default"} 12
# circuit_breaker_state{name="youtube"} 0
# ...
```

---

### Automated Health Monitoring

**Script** (`/opt/monitor-ytcaption.sh`):
```bash
#!/bin/bash

API_URL="https://api.yourdomain.com/health/ready"
WEBHOOK_URL="https://your-webhook.com/alert"  # Discord, Slack, etc.

response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL")

if [ "$response" != "200" ]; then
    echo "[$(date)] API UNHEALTHY! Status: $response"
    
    # Send alert (Discord webhook example)
    curl -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "{\"content\": \"🚨 YTCaption API is DOWN! (Status: $response)\"}"
    
    # Attempt restart
    cd /opt/YTCaption-Easy-Youtube-API
    docker compose restart whisper-api
    
    # Wait and recheck
    sleep 30
    response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL")
    if [ "$response" = "200" ]; then
        curl -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"content\": \"✅ YTCaption API recovered after restart\"}"
    fi
fi
```

**Setup cron job** (runs every 5 minutes):
```bash
chmod +x /opt/monitor-ytcaption.sh
crontab -e

# Add:
*/5 * * * * /opt/monitor-ytcaption.sh >> /var/log/ytcaption-monitor.log 2>&1
```

---

### Prometheus & Grafana

**Access Grafana**:
```
URL: http://your-server-ip:3000
User: admin
Pass: whisper2024  (change in docker-compose.yml)
```

**Pre-configured dashboards**:
1. **System Overview**: CPU, RAM, disk, network
2. **API Performance**: Request rate, latency, errors
3. **YouTube Resilience v3.0**: Download success rate, strategy usage, circuit breaker state, rate limits
4. **Transcription Stats**: Duration, queue size, parallel workers

See [Monitoring Guide](./07-monitoring.md) for detailed setup.

---

## Blue-Green Deployment

Zero-downtime deployment strategy using two identical environments.

### Architecture

```
         Nginx (reverse proxy)
              ↓
      ┌───────┴────────┐
      ↓                ↓
   GREEN (8000)    BLUE (8001)
   (active)        (standby)
```

**Deployment flow**:
1. Green is active (serving traffic)
2. Deploy new version to Blue
3. Test Blue thoroughly
4. Switch Nginx to Blue
5. Green becomes standby (for rollback)

---

### Setup

**Step 1**: Create two docker-compose files

**`docker-compose.green.yml`**:
```yaml
services:
  whisper-api:
    container_name: whisper-api-green
    ports:
      - "8000:8000"
    # ... rest of configuration
```

**`docker-compose.blue.yml`**:
```yaml
services:
  whisper-api:
    container_name: whisper-api-blue
    ports:
      - "8001:8000"  # Different port
    # ... rest of configuration
```

**Step 2**: Configure Nginx with upstream switching

**`/etc/nginx/sites-available/ytcaption`**:
```nginx
upstream ytcaption_green {
    server localhost:8000;
}

upstream ytcaption_blue {
    server localhost:8001;
}

# Active upstream (switch here for deployment)
upstream ytcaption_active {
    server localhost:8000;  # GREEN is active
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    
    # ... SSL and other config
    
    location / {
        proxy_pass http://ytcaption_active;
        # ... proxy config
    }
}
```

---

### Deployment Process

**Deploy to Blue (standby)**:
```bash
cd /opt/YTCaption-Easy-Youtube-API

# Pull latest code
git pull origin main

# Build and start Blue
docker compose -f docker-compose.blue.yml build --no-cache
docker compose -f docker-compose.blue.yml up -d

# Wait for Blue to be ready
for i in {1..30}; do
    if curl -sf http://localhost:8001/health/ready > /dev/null; then
        echo "Blue is ready!"
        break
    fi
    sleep 2
done
```

**Test Blue**:
```bash
# Smoke tests
curl http://localhost:8001/health
curl http://localhost:8001/health/ready

# Full test (transcribe short video)
curl -X POST http://localhost:8001/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

**Switch traffic to Blue**:
```bash
# Edit Nginx config
sudo nano /etc/nginx/sites-available/ytcaption

# Change upstream:
# upstream ytcaption_active {
#     server localhost:8001;  # BLUE is now active
# }

# Reload Nginx (zero downtime)
sudo nginx -t
sudo systemctl reload nginx
```

**Verify**:
```bash
# Check public API (should hit Blue)
curl https://api.yourdomain.com/health

# Monitor logs
docker compose -f docker-compose.blue.yml logs -f
```

**Cleanup old version** (after confirming Blue is stable):
```bash
docker compose -f docker-compose.green.yml down
```

---

### Rollback

If Blue has issues, switch back to Green:

```bash
# Edit Nginx config
sudo nano /etc/nginx/sites-available/ytcaption

# Change upstream back:
# upstream ytcaption_active {
#     server localhost:8000;  # GREEN is active again
# }

# Reload Nginx
sudo nginx -t
sudo systemctl reload nginx
```

**Result**: Instant rollback (< 1 second), no data loss.

---

## Backup & Rollback

### Configuration Backup

**Automated daily backup** (`/opt/backup-ytcaption.sh`):
```bash
#!/bin/bash

BACKUP_DIR="/backup/ytcaption"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup .env
cp /opt/YTCaption-Easy-Youtube-API/.env \
   "$BACKUP_DIR/.env-$DATE"

# Backup docker-compose.yml
cp /opt/YTCaption-Easy-Youtube-API/docker-compose.yml \
   "$BACKUP_DIR/docker-compose-$DATE.yml"

# Backup Nginx config
cp /etc/nginx/sites-available/ytcaption \
   "$BACKUP_DIR/nginx-ytcaption-$DATE"

# Backup Prometheus data (metadata only, not TSDB)
tar -czf "$BACKUP_DIR/prometheus-config-$DATE.tar.gz" \
    /opt/YTCaption-Easy-Youtube-API/monitoring/prometheus.yml

# Backup Grafana dashboards
tar -czf "$BACKUP_DIR/grafana-dashboards-$DATE.tar.gz" \
    /opt/YTCaption-Easy-Youtube-API/monitoring/grafana/dashboards/

# Clean old backups (keep 30 days)
find "$BACKUP_DIR" -type f -mtime +30 -delete

echo "[$(date)] Backup completed: $DATE"
```

**Setup cron job**:
```bash
chmod +x /opt/backup-ytcaption.sh
crontab -e

# Daily backup at 2 AM
0 2 * * * /opt/backup-ytcaption.sh >> /var/log/ytcaption-backup.log 2>&1
```

---

### Offsite Backup (Recommended)

**Using rclone** (S3, Backblaze B2, Google Drive, etc.):

**Install rclone**:
```bash
curl https://rclone.org/install.sh | sudo bash
```

**Configure remote** (example: Backblaze B2):
```bash
rclone config

# Follow prompts:
# n) New remote
# name: b2-backup
# storage: b2
# account: <your-account-id>
# key: <your-application-key>
```

**Add to backup script**:
```bash
# At end of /opt/backup-ytcaption.sh:
rclone sync /backup/ytcaption b2-backup:ytcaption-backup \
    --log-file=/var/log/ytcaption-rclone.log
```

---

### Restore from Backup

**Step 1**: Stop application
```bash
cd /opt/YTCaption-Easy-Youtube-API
docker compose down
```

**Step 2**: Restore files
```bash
# Restore .env
cp /backup/ytcaption/.env-20251020_120000 .env

# Restore docker-compose.yml
cp /backup/ytcaption/docker-compose-20251020_120000.yml docker-compose.yml

# Restore Nginx config
sudo cp /backup/ytcaption/nginx-ytcaption-20251020_120000 \
        /etc/nginx/sites-available/ytcaption
sudo nginx -t
sudo systemctl reload nginx
```

**Step 3**: Rebuild and start
```bash
docker compose build --no-cache
docker compose up -d
```

**Step 4**: Verify
```bash
docker compose logs -f --tail=50
curl https://api.yourdomain.com/health/ready
```

---

## Security Hardening

### 1. Basic Authentication (Nginx)

**Create password file**:
```bash
sudo apt install -y apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd admin
# Enter password when prompted
```

**Update Nginx config**:
```nginx
location /api/ {
    # Basic auth
    auth_basic "YTCaption API";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    # Rate limiting
    limit_req zone=api_limit burst=5 nodelay;
    
    proxy_pass http://ytcaption_backend;
    # ... rest of config
}
```

**Reload Nginx**:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

**Test**:
```bash
# Without auth (401 Unauthorized)
curl https://api.yourdomain.com/api/v1/transcribe

# With auth (works)
curl -u admin:yourpassword https://api.yourdomain.com/api/v1/transcribe
```

---

### 2. API Key Authentication

**Generate API key**:
```bash
openssl rand -hex 32
# Output: a7f8d3c9b2e1f4a6... (64 characters)
```

**Update Nginx config**:
```nginx
# Check API key in header
map $http_x_api_key $api_key_valid {
    default 0;
    "a7f8d3c9b2e1f4a6..." 1;  # Your API key
    "b8g9e4d0c3f2a5b7..." 1;  # Second API key (if needed)
}

location /api/ {
    # Validate API key
    if ($api_key_valid = 0) {
        return 401 "Invalid API Key";
    }
    
    proxy_pass http://ytcaption_backend;
    # ... rest of config
}
```

**Test**:
```bash
# Without key (401 Unauthorized)
curl https://api.yourdomain.com/api/v1/transcribe

# With key (works)
curl -H "X-API-Key: a7f8d3c9b2e1f4a6..." \
     https://api.yourdomain.com/api/v1/transcribe
```

---

### 3. Rate Limiting (Advanced)

**Per-IP and per-API-key limits**:
```nginx
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=ip_limit:10m rate=10r/m;
limit_req_zone $http_x_api_key zone=key_limit:10m rate=100r/m;

location /api/v1/transcribe {
    # IP limit: 10 req/min
    limit_req zone=ip_limit burst=5 nodelay;
    
    # API key limit: 100 req/min (if key provided)
    if ($http_x_api_key != "") {
        limit_req zone=key_limit burst=20 nodelay;
    }
    
    proxy_pass http://ytcaption_backend;
}
```

---

### 4. Fail2Ban (Brute-force Protection)

**Install Fail2Ban**:
```bash
sudo apt install -y fail2ban
```

**Create filter** (`/etc/fail2ban/filter.d/nginx-ytcaption.conf`):
```ini
[Definition]
failregex = ^<HOST> .* "(GET|POST) /api/.*" (401|403|429) .*$
ignoreregex =
```

**Create jail** (`/etc/fail2ban/jail.d/nginx-ytcaption.conf`):
```ini
[nginx-ytcaption]
enabled = true
port = http,https
filter = nginx-ytcaption
logpath = /var/log/nginx/ytcaption-access.log
maxretry = 10
findtime = 600
bantime = 3600
```

**Restart Fail2Ban**:
```bash
sudo systemctl restart fail2ban

# Check status
sudo fail2ban-client status nginx-ytcaption
```

---

### 5. Firewall (UFW)

**Strict rules** (allow only SSH, HTTP, HTTPS):
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (redirect to HTTPS)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Check status
sudo ufw status verbose
```

---

### 6. Docker Security

**Run as non-root** (already configured in Dockerfile):
```dockerfile
# Dockerfile (excerpt)
RUN useradd -m -u 1000 appuser
USER appuser
```

**Read-only filesystem** (optional, in docker-compose.yml):
```yaml
services:
  whisper-api:
    read_only: true
    tmpfs:
      - /app/temp:noexec,nosuid,size=10g
      - /tmp:noexec,nosuid,size=1g
```

**Drop capabilities**:
```yaml
services:
  whisper-api:
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

---

## Update & Maintenance

### Updating YTCaption

**Standard update** (with downtime):
```bash
cd /opt/YTCaption-Easy-Youtube-API

# Backup first
/opt/backup-ytcaption.sh

# Pull latest code
git pull origin main

# Rebuild and restart
docker compose down
docker compose build --no-cache
docker compose up -d

# Verify
docker compose logs -f --tail=50
curl https://api.yourdomain.com/health/ready
```

**Zero-downtime update** (blue-green):
See [Blue-Green Deployment](#blue-green-deployment) section above.

---

### Updating Dependencies

**Update Docker images** (monthly recommended):
```bash
cd /opt/YTCaption-Easy-Youtube-API

# Pull latest base images
docker compose pull

# Rebuild
docker compose build --no-cache

# Restart
docker compose down
docker compose up -d
```

**Update Python packages** (after pip freeze changes):
```bash
# Already done automatically during `docker compose build`
# (Dockerfile installs from requirements.txt)
```

---

### Log Rotation

**Configure logrotate** (`/etc/logrotate.d/ytcaption`):
```
/var/log/nginx/ytcaption-*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    sharedscripts
    postrotate
        systemctl reload nginx > /dev/null
    endscript
}

/var/log/ytcaption-*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
}
```

**Test**:
```bash
sudo logrotate -f /etc/logrotate.d/ytcaption
```

---

### Disk Cleanup

**Manual cleanup**:
```bash
# Remove old Docker images
docker image prune -a -f

# Remove unused volumes
docker volume prune -f

# Clean temp files
docker compose exec whisper-api rm -rf /app/temp/*

# Clean Prometheus old data (keeps 15 days by default)
# Already configured in docker-compose.yml:
# --storage.tsdb.retention.time=15d
```

**Automated cleanup** (cron job):
```bash
crontab -e

# Weekly cleanup at 3 AM Sunday
0 3 * * 0 docker image prune -a -f >> /var/log/docker-cleanup.log 2>&1
```

---

## Troubleshooting

### Container Won't Start

**Check logs**:
```bash
docker compose logs whisper-api --tail=100
```

**Check resources**:
```bash
free -h     # RAM available
df -h       # Disk space
```

**Solution**:
```bash
# Restart Docker daemon
sudo systemctl restart docker

# Rebuild containers
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

### API Slow/Unresponsive

**Check resource usage**:
```bash
docker stats whisper-transcription-api

# High CPU/RAM? Reduce workers:
nano .env
# Change: PARALLEL_WORKERS=2 (was 4)
docker compose restart
```

---

### SSL Certificate Issues

**Check expiry**:
```bash
sudo certbot certificates

# If expired, renew:
sudo certbot renew
sudo systemctl reload nginx
```

---

### YouTube Download Failures

See [Troubleshooting Guide](./05-troubleshooting.md) - YouTube section for v3.0 resilience strategies.

**Quick check**:
```bash
# Check circuit breaker state
curl https://api.yourdomain.com/metrics | grep circuit_breaker_state

# circuit_breaker_state{name="youtube"} 0  (0=closed, 1=open)
```

---

## Deployment Checklist

- [ ] **Server**: 8GB+ RAM, 4+ cores, 20GB+ disk
- [ ] **Docker**: Installed and running (20.10+)
- [ ] **Nginx**: Installed and configured (reverse proxy)
- [ ] **SSL**: Valid certificate (Let's Encrypt or custom)
- [ ] **Firewall**: UFW/firewalld configured (ports 22, 80, 443)
- [ ] **Configuration**: `.env` optimized for production
- [ ] **Health checks**: Automated monitoring script (cron)
- [ ] **Backups**: Daily cron job + offsite backup
- [ ] **Logs**: Rotation configured (logrotate)
- [ ] **Security**: Rate limiting, auth (basic/API key), Fail2Ban
- [ ] **Monitoring**: Prometheus + Grafana accessible
- [ ] **Documentation**: Runbook for common issues
- [ ] **Testing**: Full smoke test (transcribe video, check metrics)

---

## Next Steps

- [Monitoring Guide](./07-monitoring.md) - Prometheus, Grafana, alerting
- [Troubleshooting Guide](./05-troubleshooting.md) - Common issues & solutions
- [API Usage Guide](./04-api-usage.md) - Endpoint reference

---

**Version**: 3.0.0  
**Last Updated**: October 22, 2025  
**Contributors**: YTCaption Team
