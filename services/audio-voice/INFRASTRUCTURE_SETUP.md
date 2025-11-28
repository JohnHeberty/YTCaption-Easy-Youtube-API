# 🔧 Configuração de Infraestrutura para Produção

Este documento contém configurações essenciais para evitar o problema de estouro de disco que você enfrentou.

---

## 📦 1. CONFIGURAÇÃO DO DOCKER DAEMON

### 1.1 Arquivo daemon.json

Copie o arquivo `daemon.json.example` para `/etc/docker/daemon.json`:

```bash
sudo cp daemon.json.example /etc/docker/daemon.json
sudo systemctl restart docker
```

### 1.2 Explicação das Configurações

```json
{
  // Logs limitados a 10 MB por container, máximo 3 arquivos rotacionados
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3",
    "compress": "true"  // Comprime logs antigos
  },
  
  // Overlay2 é o storage driver mais eficiente
  "storage-driver": "overlay2",
  
  // Limita downloads/uploads paralelos (reduz picos de I/O)
  "max-concurrent-downloads": 3,
  "max-concurrent-uploads": 3,
  
  // Permite Docker continuar rodando se daemon reiniciar
  "live-restore": true,
  
  // Runtime NVIDIA para GPU
  "default-runtime": "nvidia"
}
```

### 1.3 Verificar Configuração

```bash
# Verifica se Docker reiniciou corretamente
sudo systemctl status docker

# Verifica configurações aplicadas
docker info | grep -E "Storage Driver|Logging Driver"
```

---

## 🗂️ 2. PARTICIONAMENTO LVM

### 2.1 Esquema Recomendado

Para uma VM de 100 GB total, sugiro:

```
/dev/ubuntu-vg/ubuntu-lv  (raiz)      -> 30 GB
/dev/ubuntu-vg/docker-lv  (docker)    -> 60 GB
/dev/ubuntu-vg/home-lv    (home)      -> 10 GB
```

### 2.2 Comandos de Criação

⚠️ **ATENÇÃO:** Execute APENAS em VM nova ou após backup!

```bash
# Redimensiona partição raiz para 30 GB (se maior)
sudo lvresize -L 30G /dev/ubuntu-vg/ubuntu-lv
sudo resize2fs /dev/ubuntu-vg/ubuntu-lv

# Cria partição Docker de 60 GB
sudo lvcreate -L 60G -n docker-lv ubuntu-vg
sudo mkfs.ext4 /dev/ubuntu-vg/docker-lv

# Para Docker e move dados
sudo systemctl stop docker
sudo mv /var/lib/docker /var/lib/docker.backup
sudo mkdir -p /var/lib/docker

# Monta nova partição
sudo mount /dev/ubuntu-vg/docker-lv /var/lib/docker

# Adiciona ao fstab para montar no boot
echo '/dev/ubuntu-vg/docker-lv /var/lib/docker ext4 defaults 0 2' | sudo tee -a /etc/fstab

# Restaura dados (se necessário)
sudo rsync -avh /var/lib/docker.backup/ /var/lib/docker/
sudo systemctl start docker

# Verifica
df -h | grep docker
```

### 2.3 Expandir Partição Docker (Se Necessário)

```bash
# Adiciona 20 GB à partição Docker
sudo lvextend -L +20G /dev/ubuntu-vg/docker-lv
sudo resize2fs /dev/ubuntu-vg/docker-lv

# Verifica
df -h | grep docker
```

---

## 📊 3. MONITORAMENTO AUTOMÁTICO

### 3.1 Script de Monitoramento

Já incluído em `scripts/check-disk.sh`.

### 3.2 Configurar Alertas por Email

```bash
# Instala mailutils (se necessário)
sudo apt-get install -y mailutils

# Configura email de alerta
export ALERT_EMAIL="seu-email@example.com"

# Testa envio
echo "Teste de alerta" | mail -s "Teste" $ALERT_EMAIL
```

### 3.3 Integração com Prometheus/Grafana (Avançado)

```yaml
# docker-compose.yml (adicionar ao stack)
services:
  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    restart: unless-stopped
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    ports:
      - "9100:9100"

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    restart: unless-stopped
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

volumes:
  prometheus_data:
```

### 3.4 Alertas Slack/Discord (Webhook)

```bash
#!/bin/bash
# /usr/local/bin/disk-alert-webhook.sh

WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')

if [ "$USAGE" -gt 80 ]; then
  curl -X POST $WEBHOOK_URL \
    -H 'Content-Type: application/json' \
    -d "{\"text\":\"🔴 ALERTA: Disco raiz em ${USAGE}% de uso!\"}"
fi
```

---

## 🧹 4. LIMPEZA AUTOMÁTICA

### 4.1 Cron Jobs Recomendados

```bash
# Edita crontab
crontab -e

# Adiciona:
# Monitoramento de disco a cada 15 minutos
*/15 * * * * /usr/local/bin/check-disk.sh 80

# Limpeza Docker diária às 3h (remove imagens/containers com +48h)
0 3 * * * docker system prune -af --volumes --filter "until=48h"

# Limpeza de logs do sistema semanalmente (domingo às 4h)
0 4 * * 0 journalctl --vacuum-time=14d

# Limpeza de cache apt mensalmente (dia 1 às 5h)
0 5 1 * * apt-get clean && apt-get autoclean
```

### 4.2 Logrotate para Logs da Aplicação

```bash
# /etc/logrotate.d/audio-voice
/path/to/services/audio-voice/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    create 0644 appuser appuser
    postrotate
        docker-compose -f /path/to/docker-compose.yml restart audio-voice
    endscript
}
```

---

## 🚨 5. LIMITES E QUOTAS

### 5.1 Limites de Disco para Containers

```yaml
# docker-compose.yml
services:
  audio-voice:
    image: audio-voice:3.0.0
    storage_opt:
      size: '20G'  # Limita container a 20 GB
```

⚠️ Requer Docker com `overlay2` ou `devicemapper` configurado.

### 5.2 Limites de Recursos (CPU/Memória)

```yaml
services:
  audio-voice:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 16G
        reservations:
          cpus: '2.0'
          memory: 8G
```

---

## 📈 6. MONITORAMENTO DE BUILD

### 6.1 Script de Build com Monitoramento

```bash
#!/bin/bash
# build-with-monitoring.sh

LOG_FILE="build-$(date +%Y%m%d-%H%M%S).log"

# Verifica espaço ANTES
echo "Espaço ANTES do build:"
df -h | grep -E "Filesystem|/dev/mapper" | tee -a $LOG_FILE

# Monitora em background
(
  while true; do
    df -h / | tail -1 | awk '{print strftime("%H:%M:%S"), $5}' >> $LOG_FILE
    sleep 10
  done
) &
MONITOR_PID=$!

# Build
DOCKER_BUILDKIT=1 docker build \
  --target runtime \
  --progress=plain \
  -t audio-voice:latest \
  . 2>&1 | tee -a $LOG_FILE

BUILD_STATUS=$?

# Para monitoramento
kill $MONITOR_PID 2>/dev/null

# Verifica espaço DEPOIS
echo "Espaço DEPOIS do build:"
df -h | grep -E "Filesystem|/dev/mapper" | tee -a $LOG_FILE

# Mostra gráfico de uso
echo "Evolução do uso de disco durante build:"
grep -E "[0-9]+%" $LOG_FILE | tail -20

exit $BUILD_STATUS
```

---

## 🛡️ 7. BACKUP E RECUPERAÇÃO

### 7.1 Snapshot LVM Antes de Build

```bash
#!/bin/bash
# pre-build-snapshot.sh

# Cria snapshot de 10 GB
sudo lvcreate -L 10G -s -n docker-snapshot /dev/ubuntu-vg/docker-lv

echo "Snapshot criado: /dev/ubuntu-vg/docker-snapshot"
echo "Para reverter: sudo lvconvert --merge /dev/ubuntu-vg/docker-snapshot"
```

### 7.2 Reverter Snapshot (Em Caso de Erro)

```bash
# Para Docker
sudo systemctl stop docker

# Reverte snapshot
sudo lvconvert --merge /dev/ubuntu-vg/docker-snapshot

# Reinicia
sudo reboot
```

---

## 📋 CHECKLIST DE PRODUÇÃO

Antes de fazer deploy em produção:

### Infraestrutura
- [ ] Partição `/var/lib/docker` separada (60+ GB)
- [ ] `daemon.json` configurado com limites
- [ ] Monitoramento de disco ativo (cron)
- [ ] Limpeza automática configurada (prune diário)
- [ ] Alertas configurados (email/webhook)

### Docker
- [ ] BuildKit ativado
- [ ] `.dockerignore` completo
- [ ] Multi-stage build implementado
- [ ] Logs com limite de tamanho
- [ ] Healthchecks configurados

### Backup
- [ ] Snapshot LVM antes de builds
- [ ] Backup da VM (weekly)
- [ ] Volumes persistentes documentados

### Monitoramento
- [ ] Script `check-disk.sh` funcionando
- [ ] Alertas testados
- [ ] Logs centralizados (opcional)
- [ ] Prometheus/Grafana (opcional)

---

## 🆘 PLANO DE RECUPERAÇÃO DE DESASTRE

### Cenário 1: Disco Cheio Durante Build

```bash
# 1. Cancela build (Ctrl+C)
# 2. Remove containers parados
docker container prune -f
# 3. Remove imagens não usadas
docker image prune -af
# 4. Verifica espaço
df -h
# 5. Se OK, tenta build novamente
```

### Cenário 2: Filesystem Corrompido (Como Aconteceu com Você)

```bash
# 1. Boot em modo recovery/rescue

# 2. NÃO montar partição ainda

# 3. Libera espaço deletando Docker (se possível)
mkdir /mnt/temp
mount /dev/ubuntu-vg/ubuntu-lv /mnt/temp
rm -rf /mnt/temp/var/lib/docker/*
umount /mnt/temp

# 4. Roda fsck
fsck.ext4 -yfv /dev/ubuntu-vg/ubuntu-lv

# 5. Reboot
reboot

# 6. Reinstala Docker e restaura backup
```

---

**Última atualização:** 28/11/2025  
**Autor:** Guia de Infraestrutura - Audio Voice Service
