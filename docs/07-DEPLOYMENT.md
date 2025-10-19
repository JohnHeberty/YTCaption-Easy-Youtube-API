# 🚀 Deployment

**Guia completo de deployment em produção - Docker, Proxmox, Nginx e SSL.**

---

## 📋 Índice

1. [Docker Compose (Recomendado)](#docker-compose-recomendado)
2. [Proxmox LXC Container](#proxmox-lxc-container)
3. [Nginx Reverse Proxy](#nginx-reverse-proxy)
4. [SSL/HTTPS com Certbot](#sslhttps-com-certbot)
5. [Monitoramento](#monitoramento)
6. [Backup](#backup)
7. [Segurança](#segurança)

---

## Docker Compose (Recomendado)

### 1. Preparação

**Clone o repositório**:
```bash
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
```

**Configure `.env`**:
```bash
cp .env.example .env
nano .env
```

**Configuração mínima**:
```bash
WHISPER_MODEL=base
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2
MAX_CONCURRENT_REQUESTS=3
```

---

### 2. Build e Start

**Método 1: Script Automático** ✅
```bash
chmod +x start.sh
./start.sh
```

**Método 2: Docker Compose Manual**
```bash
docker-compose build
docker-compose up -d
```

---

### 3. Verificação

**Check status**:
```bash
docker-compose ps
```

**Check logs**:
```bash
docker-compose logs -f
```

**Test API**:
```bash
curl http://localhost:8000/health
```

---

### 4. Comandos Úteis

**Restart**:
```bash
docker-compose restart
```

**Stop**:
```bash
docker-compose down
```

**Ver logs em tempo real**:
```bash
docker-compose logs -f --tail=100
```

**Rebuild após mudanças**:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## Proxmox LXC Container

### 1. Criar Container LXC

**Proxmox Web UI**:
1. Clique em "Create CT"
2. Configure:
   - **Template**: Ubuntu 22.04
   - **Disk**: 20 GB
   - **CPU**: 4 cores
   - **RAM**: 8192 MB
   - **Network**: Bridge (vmbr0)
   - **Start at boot**: ✅

---

### 2. Instalação Automática

**SSH no container**:
```bash
ssh root@IP_DO_CONTAINER
```

**Download e execute o script**:
```bash
wget https://raw.githubusercontent.com/JohnHeberty/YTCaption-Easy-Youtube-API/main/start.sh
chmod +x start.sh
./start.sh
```

O script irá:
- ✅ Detectar sistema operacional
- ✅ Instalar Docker e Docker Compose
- ✅ Clonar repositório
- ✅ Configurar `.env`
- ✅ Build e start da aplicação

---

### 3. Instalação Manual

**Instalar Docker**:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

**Instalar Docker Compose**:
```bash
apt-get update
apt-get install -y docker-compose
```

**Clonar repositório**:
```bash
cd /opt
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
```

**Configurar e iniciar**:
```bash
cp .env.example .env
nano .env  # Configure
docker-compose up -d
```

---

### 4. Configurar Autostart

**Systemd Service** (`/etc/systemd/system/ytcaption.service`):
```ini
[Unit]
Description=YTCaption API
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/YTCaption-Easy-Youtube-API
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

**Enable service**:
```bash
systemctl daemon-reload
systemctl enable ytcaption
systemctl start ytcaption
```

**Check status**:
```bash
systemctl status ytcaption
```

---

## Nginx Reverse Proxy

### 1. Instalar Nginx

**Ubuntu/Debian**:
```bash
apt-get update
apt-get install -y nginx
```

---

### 2. Configurar Virtual Host

**Criar arquivo** (`/etc/nginx/sites-available/ytcaption`):
```nginx
server {
    listen 80;
    server_name seu-dominio.com;

    # Logs
    access_log /var/log/nginx/ytcaption-access.log;
    error_log /var/log/nginx/ytcaption-error.log;

    # Timeouts para transcrições longas
    proxy_connect_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_read_timeout 3600s;

    # Max upload size (para áudios grandes)
    client_max_body_size 500M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (se necessário)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Enable site**:
```bash
ln -s /etc/nginx/sites-available/ytcaption /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

---

### 3. Configurar Firewall

```bash
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## SSL/HTTPS com Certbot

### 1. Instalar Certbot

```bash
apt-get update
apt-get install -y certbot python3-certbot-nginx
```

---

### 2. Obter Certificado

```bash
certbot --nginx -d seu-dominio.com
```

**Responda**:
- Email: seu-email@exemplo.com
- Termos: A (Agree)
- Redirect HTTP → HTTPS: 2 (Yes)

---

### 3. Renovação Automática

**Certbot já cria cron job automaticamente**. Verifique:
```bash
systemctl status certbot.timer
```

**Testar renovação**:
```bash
certbot renew --dry-run
```

---

### 4. Configuração Final (após SSL)

O Certbot modifica automaticamente o Nginx. Resultado (`/etc/nginx/sites-available/ytcaption`):

```nginx
server {
    server_name seu-dominio.com;

    # Timeouts
    proxy_connect_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_read_timeout 3600s;
    client_max_body_size 500M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/seu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seu-dominio.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    if ($host = seu-dominio.com) {
        return 301 https://$host$request_uri;
    }

    listen 80;
    server_name seu-dominio.com;
    return 404;
}
```

---

## Monitoramento

### 1. Logs

**Docker logs**:
```bash
docker-compose logs -f --tail=100
```

**Nginx logs**:
```bash
tail -f /var/log/nginx/ytcaption-access.log
tail -f /var/log/nginx/ytcaption-error.log
```

**Application logs** (dentro do container):
```bash
docker exec -it ytcaption tail -f /app/logs/app.log
```

---

### 2. Health Check Automático

**Script de monitoramento** (`/opt/monitor-ytcaption.sh`):
```bash
#!/bin/bash

API_URL="http://localhost:8000/health"
WEBHOOK_URL="https://seu-webhook.com/alert"  # Discord, Slack, etc.

response=$(curl -s -o /dev/null -w "%{http_code}" $API_URL)

if [ "$response" != "200" ]; then
    echo "API DOWN! Status: $response"
    
    # Enviar alerta
    curl -X POST $WEBHOOK_URL \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"🚨 YTCaption API está DOWN! (Status: $response)\"}"
    
    # Tentar restart
    cd /opt/YTCaption-Easy-Youtube-API
    docker-compose restart
fi
```

**Cron job** (executa a cada 5 minutos):
```bash
chmod +x /opt/monitor-ytcaption.sh
crontab -e
```

Adicione:
```
*/5 * * * * /opt/monitor-ytcaption.sh
```

---

### 3. Recursos do Sistema

**Script de monitoramento de recursos** (`/opt/monitor-resources.sh`):
```bash
#!/bin/bash

echo "=== YTCaption Resources ==="
echo "Date: $(date)"
echo ""

# CPU
echo "CPU Usage:"
docker stats ytcaption --no-stream --format "{{.CPUPerc}}"
echo ""

# RAM
echo "Memory Usage:"
docker stats ytcaption --no-stream --format "{{.MemUsage}}"
echo ""

# Disk
echo "Disk Usage:"
df -h /opt/YTCaption-Easy-Youtube-API
echo ""

# Container status
echo "Container Status:"
docker-compose ps
```

**Cron job diário**:
```bash
0 9 * * * /opt/monitor-resources.sh >> /var/log/ytcaption-resources.log
```

---

## Backup

### 1. Backup de Configuração

**Script de backup** (`/opt/backup-ytcaption.sh`):
```bash
#!/bin/bash

BACKUP_DIR="/backup/ytcaption"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup .env
cp /opt/YTCaption-Easy-Youtube-API/.env \
   $BACKUP_DIR/.env-$DATE

# Backup docker-compose.yml
cp /opt/YTCaption-Easy-Youtube-API/docker-compose.yml \
   $BACKUP_DIR/docker-compose-$DATE.yml

# Backup logs (últimos 7 dias)
find /opt/YTCaption-Easy-Youtube-API/logs -name "*.log" -mtime -7 \
     -exec cp {} $BACKUP_DIR/ \;

# Manter apenas últimos 30 dias
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup concluído: $DATE"
```

**Cron job diário**:
```bash
0 2 * * * /opt/backup-ytcaption.sh
```

---

### 2. Backup Offsite (Opcional)

**Para S3/Backblaze B2**:
```bash
apt-get install rclone

# Configure rclone
rclone config

# Adicione ao script de backup
rclone sync /backup/ytcaption remote:ytcaption-backup
```

---

## Segurança

### 1. Autenticação Básica (Nginx)

**Criar arquivo de senha**:
```bash
apt-get install apache2-utils
htpasswd -c /etc/nginx/.htpasswd admin
```

**Adicione ao Nginx config**:
```nginx
location / {
    auth_basic "YTCaption API";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    proxy_pass http://localhost:8000;
    # ... resto da config
}
```

**Reload Nginx**:
```bash
systemctl reload nginx
```

---

### 2. Rate Limiting (Nginx)

**Adicione ao início do arquivo Nginx**:
```nginx
# Rate limiting zone
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/m;

server {
    # ... server config
    
    location /api/ {
        limit_req zone=api_limit burst=5;
        
        proxy_pass http://localhost:8000;
        # ... proxy config
    }
}
```

**Isso limita**: 10 requisições/minuto por IP (burst de 5).

---

### 3. Firewall (UFW)

```bash
# Permitir apenas SSH, HTTP, HTTPS
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

### 4. Fail2Ban (Proteção contra Brute Force)

**Instalar**:
```bash
apt-get install fail2ban
```

**Configurar** (`/etc/fail2ban/jail.local`):
```ini
[nginx-req-limit]
enabled = true
filter = nginx-req-limit
action = iptables-multiport[name=ReqLimit, port="http,https", protocol=tcp]
logpath = /var/log/nginx/ytcaption-error.log
findtime = 600
maxretry = 10
bantime = 3600
```

**Restart**:
```bash
systemctl restart fail2ban
```

---

## Update em Produção

### 1. Backup Primeiro

```bash
/opt/backup-ytcaption.sh
```

---

### 2. Atualizar Código

```bash
cd /opt/YTCaption-Easy-Youtube-API
git pull origin main
```

---

### 3. Rebuild e Restart

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

### 4. Verificar

```bash
docker-compose logs -f --tail=50
curl https://seu-dominio.com/health
```

---

## Troubleshooting em Produção

### Container não inicia

**Check logs**:
```bash
docker-compose logs
```

**Check resources**:
```bash
free -h
df -h
```

**Restart Docker**:
```bash
systemctl restart docker
docker-compose up -d
```

---

### API lenta

**Check CPU/RAM**:
```bash
docker stats ytcaption
```

**Reduza workers**:
```bash
# Edite .env
PARALLEL_WORKERS=2  # Era 4
MAX_CONCURRENT_REQUESTS=2  # Era 4

docker-compose restart
```

---

### SSL não renova

**Check certbot timer**:
```bash
systemctl status certbot.timer
```

**Renovar manualmente**:
```bash
certbot renew
systemctl reload nginx
```

---

## Checklist de Produção

- [ ] **Servidor**: 8GB+ RAM, 4+ cores CPU
- [ ] **Docker**: Instalado e rodando
- [ ] **Configuração**: `.env` otimizado
- [ ] **Nginx**: Reverse proxy configurado
- [ ] **SSL**: Certificado válido (Let's Encrypt)
- [ ] **Firewall**: UFW ou iptables configurado
- [ ] **Monitoramento**: Health check ativo
- [ ] **Backup**: Cron job diário configurado
- [ ] **Logs**: Rotação configurada
- [ ] **Autostart**: Systemd service habilitado
- [ ] **Segurança**: Autenticação ou rate limiting
- [ ] **Teste**: API respondendo corretamente

---

**Próximo**: [Troubleshooting](./08-TROUBLESHOOTING.md)

**Versão**: 1.3.3+  
**Última atualização**: 19/10/2025
