# Guia de Deploy e Operação

## 🐳 Deploy com Docker

### Pré-requisitos

- Docker 20.10+
- Docker Compose 1.29+
- 4GB+ RAM disponível
- 10GB+ espaço em disco

### Deploy Rápido

```bash
# 1. Clonar repositório
git clone <repository-url>
cd whisper-transcription-api

# 2. Configurar ambiente
cp .env.example .env
nano .env  # Ajustar configurações

# 3. Build e executar
docker-compose up -d

# 4. Verificar status
docker-compose ps
docker-compose logs -f
```

### Verificar Instalação

```bash
# Health check
curl http://localhost:8000/health

# Teste de transcrição
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"}'
```

## 🖥️ Deploy no Proxmox

### 1. Preparar Container LXC

#### Criar Container Ubuntu

No console do Proxmox:

```bash
# Criar container com Ubuntu 22.04
pct create 100 local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.gz \
  --hostname whisper-api \
  --memory 4096 \
  --swap 2048 \
  --cores 4 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp,firewall=1 \
  --storage local-lvm \
  --rootfs local-lvm:20

# Iniciar container
pct start 100

# Entrar no container
pct enter 100
```

#### Instalar Docker no Container

```bash
# Atualizar sistema
apt update && apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Instalar Docker Compose
apt install -y docker-compose

# Verificar instalação
docker --version
docker-compose --version
```

### 2. Configurar Firewall

```bash
# Permitir porta 8000
ufw allow 8000/tcp
ufw enable
```

### 3. Deploy da Aplicação

```bash
# Criar diretório
mkdir -p /opt/whisper-api
cd /opt/whisper-api

# Transferir arquivos (do host)
# Opção 1: SCP
scp -r . root@<container-ip>:/opt/whisper-api/

# Opção 2: Git
git clone <repository-url> /opt/whisper-api/

# Configurar ambiente
cp .env.example .env
nano .env

# Ajustar variáveis importantes:
# - WHISPER_MODEL=base
# - WHISPER_DEVICE=cpu
# - LOG_LEVEL=INFO
# - TEMP_DIR=/opt/whisper-api/temp
```

### 4. Executar Container

```bash
cd /opt/whisper-api
docker-compose up -d

# Monitorar logs
docker-compose logs -f
```

### 5. Configurar como Serviço Systemd

```bash
# Criar service file
cat > /etc/systemd/system/whisper-api.service <<'EOF'
[Unit]
Description=Whisper Transcription API
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/whisper-api
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# Habilitar serviço
systemctl daemon-reload
systemctl enable whisper-api.service
systemctl start whisper-api.service

# Verificar status
systemctl status whisper-api.service
```

### 6. Configurar Nginx como Reverse Proxy (Opcional)

```bash
# Instalar Nginx
apt install -y nginx

# Configurar site
cat > /etc/nginx/sites-available/whisper-api <<'EOF'
server {
    listen 80;
    server_name whisper-api.local;

    client_max_body_size 100M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts para requisições longas
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
        send_timeout 600;
    }
}
EOF

# Ativar site
ln -s /etc/nginx/sites-available/whisper-api /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

## 📊 Monitoramento

### Logs

```bash
# Logs do Docker
docker-compose logs -f

# Logs específicos
docker-compose logs -f whisper-api

# Logs do sistema
tail -f /opt/whisper-api/logs/app.log
```

### Health Checks

```bash
# Verificar saúde
curl http://localhost:8000/health

# Resposta esperada:
{
  "status": "healthy",
  "version": "1.0.0",
  "whisper_model": "base",
  "storage_usage": {...},
  "uptime_seconds": 12345.67
}
```

### Métricas de Performance

```bash
# Uso de recursos do container
docker stats whisper-transcription-api

# Uso de storage
curl http://localhost:8000/health | jq '.storage_usage'
```

## 🔧 Manutenção

### Backup

```bash
# Backup de configurações
tar -czf backup-$(date +%Y%m%d).tar.gz \
  /opt/whisper-api/.env \
  /opt/whisper-api/docker-compose.yml

# Backup de logs (opcional)
tar -czf logs-backup-$(date +%Y%m%d).tar.gz \
  /opt/whisper-api/logs/
```

### Atualizações

```bash
cd /opt/whisper-api

# Parar serviço
docker-compose down

# Atualizar código
git pull origin main

# Rebuild imagem
docker-compose build --no-cache

# Reiniciar
docker-compose up -d

# Verificar
docker-compose logs -f
```

### Limpeza de Storage

```bash
# Limpar arquivos temporários antigos
# A API faz isso automaticamente, mas pode ser forçado:

# Entrar no container
docker-compose exec whisper-api /bin/bash

# Limpar manualmente
rm -rf /app/temp/*

# Ou usar endpoint da API (se implementado)
curl -X POST http://localhost:8000/api/v1/cleanup
```

### Limpeza de Docker

```bash
# Remover imagens não usadas
docker image prune -a

# Remover volumes não usados
docker volume prune

# Limpeza completa
docker system prune -a --volumes
```

## 🔒 Segurança

### Firewall

```bash
# Permitir apenas porta necessária
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 8000/tcp
ufw enable
```

### Usuário Não-Root

O container já executa como usuário não-root (`appuser`).

### HTTPS com Certbot (Produção)

```bash
# Instalar Certbot
apt install -y certbot python3-certbot-nginx

# Obter certificado
certbot --nginx -d whisper-api.yourdomain.com

# Renovação automática
certbot renew --dry-run
```

### Limitação de Taxa (Rate Limiting)

Adicionar no Nginx:

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/m;

location / {
    limit_req zone=api_limit burst=5;
    # ... resto da configuração
}
```

## ⚡ Otimização de Performance

### Recursos do Container

Ajustar `docker-compose.yml`:

```yaml
services:
  whisper-api:
    deploy:
      resources:
        limits:
          cpus: '4'      # Aumentar para mais performance
          memory: 8G     # Aumentar se usar modelo maior
        reservations:
          cpus: '2'
          memory: 4G
```

### Cache de Modelos Whisper

```yaml
volumes:
  - whisper-cache:/home/appuser/.cache/whisper
```

Modelos são baixados apenas uma vez!

### Múltiplos Workers

Para alta demanda, considerar múltiplas instâncias:

```yaml
services:
  whisper-api-1:
    # ... configuração
    ports:
      - "8001:8000"
  
  whisper-api-2:
    # ... configuração
    ports:
      - "8002:8000"
```

Load balancer no Nginx:

```nginx
upstream whisper_backend {
    server localhost:8001;
    server localhost:8002;
}

server {
    location / {
        proxy_pass http://whisper_backend;
    }
}
```

## 🐛 Troubleshooting

### Container não inicia

```bash
# Ver logs de erro
docker-compose logs

# Verificar recursos
free -h
df -h

# Verificar portas
netstat -tulpn | grep 8000
```

### Erro de Memória

```bash
# Aumentar memória do container
# Em docker-compose.yml:
mem_limit: 8g

# Ou usar modelo menor
# Em .env:
WHISPER_MODEL=tiny
```

### Transcrição muito lenta

```python
# Opções:
# 1. Usar modelo menor (tiny/base)
# 2. Adicionar GPU support
# 3. Aumentar CPU cores
# 4. Limitar tamanho máximo de vídeo
```

### Disco cheio

```bash
# Verificar uso
df -h
docker system df

# Limpar
docker system prune -a --volumes
rm -rf /opt/whisper-api/temp/*
```

### API não responde

```bash
# Verificar processo
docker-compose ps

# Reiniciar
docker-compose restart

# Logs
docker-compose logs -f

# Health check
curl http://localhost:8000/health
```

## 📈 Escalabilidade

### Horizontal Scaling

Para escalar horizontalmente:

1. **Load Balancer**: Nginx/HAProxy
2. **Múltiplas Instâncias**: Docker Swarm ou Kubernetes
3. **Queue System**: Redis + Celery para processamento assíncrono
4. **Shared Storage**: NFS ou S3 para arquivos temporários

### Vertical Scaling

Para melhorar performance de uma instância:

1. **Mais CPU**: Aumentar cores
2. **Mais RAM**: Para modelos maiores
3. **GPU**: NVIDIA GPU para acelerar transcrição
4. **SSD**: Storage mais rápido

## 🎯 Checklist de Deploy

### Antes do Deploy

- [ ] Revisar configurações em `.env`
- [ ] Testar em ambiente de desenvolvimento
- [ ] Verificar recursos disponíveis
- [ ] Configurar backups
- [ ] Documentar credenciais

### Durante o Deploy

- [ ] Executar `docker-compose up -d`
- [ ] Verificar logs: `docker-compose logs -f`
- [ ] Testar health check: `curl /health`
- [ ] Testar endpoint de transcrição
- [ ] Configurar monitoramento

### Após o Deploy

- [ ] Monitorar recursos (CPU, RAM, Disk)
- [ ] Configurar alertas
- [ ] Documentar URL de acesso
- [ ] Treinar equipe
- [ ] Planejar manutenções

---

**Com este guia, você tem tudo que precisa para deploy e operação bem-sucedidos da API!**
