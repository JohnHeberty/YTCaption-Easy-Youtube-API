# 🚀 Guia Rápido - Atualização e Teste GPU

## 📥 Atualizar no Servidor

```bash
cd ~/YTCaption-Easy-Youtube-API
git pull
chmod +x scripts/*.sh
```

## 🔍 1. Diagnosticar GPU (FEITO - resultado conhecido)

```bash
./scripts/gpu-diagnostic.sh
```

**Resultado esperado:** Driver/library version mismatch (módulos já recarregados ✅)

---

## 🐳 2. Instalar NVIDIA Docker

### Método Automático (RECOMENDADO):
```bash
sudo ./scripts/install-nvidia-docker.sh
```

### Método Manual:
```bash
# 1. Remover arquivo corrompido
sudo rm /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 2. Adicionar GPG key
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# 3. Criar repositório correto
sudo bash -c 'cat > /etc/apt/sources.list.d/nvidia-container-toolkit.list <<EOF
deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/\$(ARCH) /
EOF'

# 4. Instalar
sudo apt update
sudo apt install -y nvidia-container-toolkit

# 5. Configurar Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 6. Testar
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

---

## ✅ 3. Verificar Funcionamento

```bash
# GPU funciona no host?
nvidia-smi

# GPU funciona no Docker?
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

**Resultado esperado:** 
```
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 535.274.02             Driver Version: 535.274.02   CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
|   0  NVIDIA GeForce GTX 1050 Ti     Off | 00000000:06:10.0 Off |                  N/A |
+---------------------------------------------------------------------------------------+
```

---

## 🚀 4. Iniciar Aplicação com GPU

```bash
./scripts/start.sh --model base --memory 2048
```

**Resultado esperado:**
```
✓ NVIDIA GPU detected: GeForce GTX 1050 Ti
✓ CUDA detected: 12.2
Whisper Device:   cuda
GPU Available:    true
```

---

## � 5. Configurar YouTube Resilience (v3.0)

**Edite `.env` para produção:**
```bash
nano .env
```

**Configuração Recomendada (v3.0)**:
```bash
# YouTube Resilience (v3.0) - CRÍTICO
ENABLE_TOR_PROXY=true
TOR_PROXY_URL=socks5h://tor-proxy:9050

ENABLE_MULTI_STRATEGY=true
ENABLE_USER_AGENT_ROTATION=true

YOUTUBE_MAX_RETRIES=5
YOUTUBE_RETRY_DELAY_MIN=5
YOUTUBE_RETRY_DELAY_MAX=60

YOUTUBE_REQUESTS_PER_MINUTE=10
YOUTUBE_REQUESTS_PER_HOUR=200
YOUTUBE_COOLDOWN_ON_ERROR=30

YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=10
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=60
```

**Restart após mudanças**:
```bash
./scripts/stop.sh
./scripts/start.sh --model base --memory 2048
```

**Aguarde Tor (30-60s)**:
```bash
docker-compose logs tor-proxy | grep "Bootstrapped 100%"
# Esperado: "Bootstrapped 100% (done): Done"
```

**Teste download resiliente**:
```bash
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

**Verifique métricas**:
```bash
# Grafana (UI visual)
http://localhost:3000
# Login: admin / whisper2024

# Prometheus (dados brutos)
http://localhost:9090
```

---

## �🎯 Comandos Úteis

### Ver logs em tempo real:
```bash
docker-compose logs -f

# Apenas YouTube download events (v3.0)
docker-compose logs -f | grep "youtube_download"
```

### Ver uso GPU em tempo real:
```bash
watch -n 1 nvidia-smi
```

### Parar aplicação:
```bash
./scripts/stop.sh
```

### Status:
```bash
./scripts/status.sh
```

### Diagnóstico completo:
```bash
./scripts/gpu-diagnostic.sh
```

---

## 🐛 Problemas Comuns

### Erro: "could not select device driver with capabilities: [[gpu]]"
**Causa:** NVIDIA Docker não instalado  
**Solução:** 
```bash
sudo ./scripts/install-nvidia-docker.sh
```

### Erro: "Driver/library version mismatch"
**Causa:** Módulos kernel desatualizados  
**Solução:**
```bash
sudo rmmod nvidia_drm nvidia_modeset nvidia_uvm nvidia
sudo modprobe nvidia nvidia_uvm nvidia_modeset nvidia_drm
```

### Erro: "Permission denied"
**Causa:** Scripts não executáveis  
**Solução:**
```bash
chmod +x scripts/*.sh
```

---

## 📊 Hardware do Servidor

```
CPU:     3 cores
RAM:     9GB (configurado: 2GB)
GPU:     NVIDIA GeForce GTX 1050 Ti (4GB VRAM)
Driver:  535.274.02
CUDA:    12.2
```

---

## 📝 Notas

1. **Sempre execute os scripts da raiz do projeto:**
   ```bash
   cd ~/YTCaption-Easy-Youtube-API
   ./scripts/start.sh
   ```

2. **Scripts detectam automaticamente o projeto root**, então também funciona:
   ```bash
   cd ~/YTCaption-Easy-Youtube-API/scripts
   ./start.sh
   ```

3. **GPU é opcional**: Aplicação funciona em CPU se GPU não estiver disponível

4. **Modelo base recomendado** para GTX 1050 Ti (4GB VRAM)

---

## ✅ Checklist Final

- [x] Driver NVIDIA funcionando (`nvidia-smi`)
- [x] Módulos kernel recarregados
- [ ] NVIDIA Docker instalado
- [ ] GPU acessível no Docker (teste com container CUDA)
- [ ] Aplicação iniciada com GPU
- [ ] Logs confirmam uso GPU

---

**Próximo passo:** Executar `sudo ./scripts/install-nvidia-docker.sh` 🚀
