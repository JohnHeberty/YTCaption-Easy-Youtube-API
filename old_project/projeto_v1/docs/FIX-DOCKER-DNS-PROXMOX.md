# Fix Docker DNS Issues on Proxmox

## Problema Identificado

No Proxmox, o container Docker não consegue acessar a internet:
- ✅ **Windows local**: 5/7 estratégias funcionam perfeitamente
- ❌ **Proxmox**: Todas estratégias falham com 403 Forbidden
- ❌ **DNS**: `nslookup youtube.com` timeout
- ❌ **Ping**: 100% packet loss para 8.8.8.8

## Diagnóstico

```bash
# Executar no Proxmox:
cd /path/to/YTCaption-Easy-Youtube-API
chmod +x scripts/fix-docker-network.sh
./scripts/fix-docker-network.sh
```

## Soluções (em ordem de preferência)

### Solução 1: Configurar DNS no Docker Daemon (RECOMENDADO)

```bash
# No host Proxmox:
sudo nano /etc/docker/daemon.json
```

Adicione:
```json
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "dns-opts": ["ndots:0"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Reinicie o Docker:
```bash
sudo systemctl restart docker

# Verificar status
sudo systemctl status docker

# Testar DNS
docker run --rm alpine nslookup youtube.com
```

### Solução 2: Verificar Firewall do Proxmox

```bash
# Verificar regras iptables
sudo iptables -L -n | grep -i docker
sudo iptables -t nat -L -n | grep -i docker

# Se tiver bloqueios, permitir:
sudo iptables -I FORWARD -j ACCEPT
sudo iptables -I INPUT -j ACCEPT
sudo iptables -I OUTPUT -j ACCEPT

# Salvar regras (Debian/Ubuntu):
sudo apt-get install iptables-persistent
sudo netfilter-persistent save
```

### Solução 3: Configurar Bridge do Docker

```bash
# Verificar bridge
docker network inspect bridge

# Recriar bridge se necessário
docker network rm bridge
docker network create --driver bridge bridge

# Verificar configuração
ip addr show docker0
```

### Solução 4: Usar Rede Host (temporário para teste)

Edite `docker-compose.yml`:
```yaml
services:
  whisper-api:
    network_mode: "host"
    # Remova ports: se usar host mode
```

**⚠️ Atenção**: Menos seguro, use apenas para diagnóstico.

### Solução 5: Configurar DNS no /etc/resolv.conf do Container

Edite `.env` ou `docker-compose.yml`:
```yaml
services:
  whisper-api:
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
    dns_search: []
    dns_opts:
      - ndots:0
```

### Solução 6: Verificar MTU da Interface

```bash
# Verificar MTU atual
ip link show docker0

# Se MTU for muito alto, diminuir:
sudo ip link set dev docker0 mtu 1450

# Configurar permanentemente em /etc/docker/daemon.json:
{
  "mtu": 1450
}
```

## Após Aplicar Qualquer Solução

```bash
# 1. Parar containers
docker compose down

# 2. Limpar caches
docker system prune -af

# 3. Reconstruir
docker compose build --no-cache

# 4. Iniciar
docker compose up -d

# 5. Verificar logs
docker logs whisper-transcription-api --follow

# 6. Testar DNS dentro do container
docker exec whisper-transcription-api nslookup youtube.com
docker exec whisper-transcription-api ping -c 3 8.8.8.8
docker exec whisper-transcription-api curl -I https://www.youtube.com

# 7. Testar download real
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"}'
```

## Verificação de Sucesso

✅ Deve ver nos logs:
```
INFO: Video info retrieved: jNQXAC9IVRw | Duration: 206 seconds
INFO: 🎯 Trying strategy: android_client (priority 1)
INFO: ✅ Strategy succeeded: android_client
INFO: ✅ Audio downloaded successfully
```

❌ NÃO deve ver:
```
ERROR: unable to download video data: HTTP Error 403: Forbidden
ERROR: [youtube] jNQXAC9IVRw: No video formats found!
```

## Comandos de Diagnóstico Úteis

```bash
# Ver DNS do host
cat /etc/resolv.conf

# Ver DNS do container
docker exec whisper-transcription-api cat /etc/resolv.conf

# Testar conectividade
docker exec whisper-transcription-api ping -c 3 google.com
docker exec whisper-transcription-api wget -q --spider https://youtube.com && echo "OK" || echo "FALHOU"

# Ver rotas
docker exec whisper-transcription-api ip route

# Verificar processos DNS
docker exec whisper-transcription-api ps aux | grep dns

# Capturar tráfego (debug avançado)
sudo tcpdump -i docker0 -n port 53
```

## Problemas Específicos do Proxmox

### Problema: VirtIO Network pode causar MTU issues
```bash
# No host Proxmox, verificar MTU da interface:
ip link show

# Ajustar MTU do Docker para corresponder:
sudo nano /etc/docker/daemon.json
{
  "mtu": 1450  # ou 1400 se ainda tiver problemas
}
```

### Problema: IPv6 pode causar conflicts
```bash
# Desabilitar IPv6 no Docker daemon.json:
{
  "ipv6": false
}
```

### Problema: Firewall do Proxmox bloqueando
```bash
# Verificar firewall do Proxmox:
pve-firewall status

# Se ativo, adicionar regras:
# Via GUI: Datacenter → Firewall → Add Rule
# Permitir: Docker subnet (172.17.0.0/16)
```

## Teste Rápido

```bash
# Script de teste rápido:
echo "Testando DNS..."
docker run --rm alpine nslookup youtube.com && echo "✅ DNS OK" || echo "❌ DNS FALHOU"

echo "Testando conectividade..."
docker run --rm alpine ping -c 2 8.8.8.8 && echo "✅ PING OK" || echo "❌ PING FALHOU"

echo "Testando HTTPS..."
docker run --rm alpine wget -q --spider https://youtube.com && echo "✅ HTTPS OK" || echo "❌ HTTPS FALHOU"
```

## Referências

- [Docker DNS Configuration](https://docs.docker.com/config/containers/container-networking/#dns-services)
- [Proxmox Network Configuration](https://pve.proxmox.com/wiki/Network_Configuration)
- [Docker Network Troubleshooting](https://docs.docker.com/network/troubleshoot/)
