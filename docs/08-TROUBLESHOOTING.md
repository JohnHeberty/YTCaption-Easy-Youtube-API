# 🔧 Troubleshooting

**Guia completo de solução de problemas - erros comuns e como resolver.**

---

## 📋 Índice

1. [Erros de Instalação](#erros-de-instalação)
2. [Erros de Docker](#erros-de-docker)
3. [Erros de Memória (OOM)](#erros-de-memória-oom)
4. [Erros de Download (YouTube)](#erros-de-download-youtube)
5. [Erros de Transcrição](#erros-de-transcrição)
6. [Erros de FFmpeg](#erros-de-ffmpeg)
7. [Erros de API](#erros-de-api)
8. [Performance Issues](#performance-issues)

---

## Erros de Instalação

### ❌ Docker não encontrado

**Erro**:
```
docker: command not found
```

**Causa**: Docker não está instalado.

**Solução**:
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Verificar
docker --version
```

---

### ❌ Docker Compose não encontrado

**Erro**:
```
docker-compose: command not found
```

**Solução**:
```bash
# Ubuntu/Debian
apt-get update
apt-get install -y docker-compose

# Verificar
docker-compose --version
```

---

### ❌ Permissão negada (Docker)

**Erro**:
```
permission denied while trying to connect to the Docker daemon socket
```

**Causa**: Usuário não está no grupo `docker`.

**Solução**:
```bash
sudo usermod -aG docker $USER
newgrp docker

# Ou use sudo
sudo docker-compose up -d
```

---

### ❌ Porta 8000 já em uso

**Erro**:
```
Error starting userland proxy: listen tcp 0.0.0.0:8000: bind: address already in use
```

**Causa**: Outra aplicação está usando a porta 8000.

**Solução 1 - Mudar porta**:
```bash
# Edite .env
PORT=8001

# Edite docker-compose.yml
ports:
  - "8001:8001"

# Restart
docker-compose down
docker-compose up -d
```

**Solução 2 - Matar processo na porta**:
```bash
# Linux
sudo lsof -i :8000
sudo kill -9 PID

# Windows
netstat -ano | findstr :8000
taskkill /PID PID /F
```

---

## Erros de Docker

### ❌ Container não inicia

**Erro**:
```
Container ytcaption exited with code 1
```

**Diagnóstico**:
```bash
docker-compose logs
```

**Soluções comuns**:

1. **Falta `.env`**:
```bash
cp .env.example .env
```

2. **Erro no `.env`**:
```bash
# Verifique sintaxe
cat .env
# Não deixe espaços: WHISPER_MODEL=base (correto)
# Errado: WHISPER_MODEL = base
```

3. **Rebuild**:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

### ❌ Container fica reiniciando

**Erro**:
```
Restarting (1) X seconds ago
```

**Causa**: Erro fatal na inicialização.

**Diagnóstico**:
```bash
docker-compose logs --tail=50
```

**Soluções**:

1. **Check RAM**:
```bash
free -h
# Se RAM < 4GB, use modelo menor
WHISPER_MODEL=tiny
```

2. **Check disk**:
```bash
df -h
# Se disco cheio, limpe temp
rm -rf ./temp/*
```

---

### ❌ Build falha

**Erro**:
```
ERROR [internal] load metadata for docker.io/library/python:3.11-slim
```

**Causa**: Problema de rede ou Docker Hub.

**Solução**:
```bash
# Limpar cache
docker system prune -a

# Rebuild
docker-compose build --no-cache
```

---

## Erros de Memória (OOM)

### ❌ Out of Memory (Transcrição)

**Erro**:
```
RuntimeError: Out of memory
Process killed by OOM killer
```

**Causa**: RAM insuficiente para o modelo/workers configurados.

**Soluções**:

#### 1. Use modelo menor
```bash
# .env
WHISPER_MODEL=tiny  # Era base ou small
```

#### 2. Reduza workers paralelos
```bash
# .env
PARALLEL_WORKERS=1  # Era 4
```

#### 3. Desabilite paralelo
```bash
# .env
ENABLE_PARALLEL_TRANSCRIPTION=false
```

#### 4. Reduza requisições simultâneas
```bash
# .env
MAX_CONCURRENT_REQUESTS=1  # Era 3
```

#### 5. Aumente swap (Linux)
```bash
# Criar swap de 4GB
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Permanente
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

### ❌ Docker Out of Memory

**Erro**:
```
docker: Error response from daemon: OCI runtime create failed
```

**Causa**: Container sem memória suficiente.

**Solução** (edite `docker-compose.yml`):
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          memory: 8G  # Era 4G
```

---

## Erros de Download (YouTube)

### ❌ Video not found

**Erro**:
```
HTTP 404: Video not found or unavailable
```

**Causas**:
- Vídeo privado
- Vídeo deletado
- Restrição geográfica
- Live stream (não suportado)

**Solução**:
- Use outro vídeo público
- Verifique URL (abra no navegador)

---

### ❌ Download timeout

**Erro**:
```
TimeoutError: Download exceeded timeout limit
```

**Causa**: Internet lenta ou vídeo muito grande.

**Solução**:
```bash
# .env
DOWNLOAD_TIMEOUT=1800  # Era 900 (15min → 30min)
```

---

### ❌ Video too long

**Erro**:
```
Video duration exceeds limit (max: 10800s)
```

**Causa**: Vídeo maior que `MAX_VIDEO_DURATION_SECONDS`.

**Solução**:
```bash
# .env
MAX_VIDEO_DURATION_SECONDS=21600  # Era 10800 (3h → 6h)
```

---

### ❌ Video too large

**Erro**:
```
Video size exceeds limit (max: 2500MB)
```

**Causa**: Vídeo maior que `MAX_VIDEO_SIZE_MB`.

**Solução**:
```bash
# .env
MAX_VIDEO_SIZE_MB=5000  # Era 2500 (2.5GB → 5GB)
```

---

### ❌ yt-dlp error

**Erro**:
```
ERROR: Unable to download webpage
ERROR: This video is not available
```

**Causas**:
- YouTube mudou API
- Versão antiga do yt-dlp

**Solução**:
```bash
# Rebuild com versão mais nova
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## Erros de Transcrição

### ❌ Transcription failed

**Erro**:
```
RuntimeError: Transcription failed after 3 retries
```

**Causas**:
- Áudio corrompido
- Formato não suportado
- Bug no Whisper

**Soluções**:

1. **Tente modelo menor**:
```bash
WHISPER_MODEL=base  # Era medium
```

2. **Desabilite paralelo**:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
```

3. **Check logs**:
```bash
docker-compose logs --tail=100
```

---

### ❌ Transcrição vazia

**Erro**:
```json
{
  "transcription": {
    "text": "",
    "segments": []
  }
}
```

**Causas**:
- Vídeo sem áudio
- Áudio muito baixo
- Idioma não detectado

**Soluções**:

1. **Especifique idioma**:
```bash
WHISPER_LANGUAGE=pt  # Era auto
```

2. **Use modelo maior**:
```bash
WHISPER_MODEL=small  # Era tiny
```

3. **Verifique áudio do vídeo** (abra no YouTube)

---

### ❌ Timestamps errados

**Erro**: Transcrição dessincronizada.

**Causas**:
- Bug no merge paralelo (raro)
- Áudio com pausas longas

**Solução**:
```bash
# Use single-core temporariamente
ENABLE_PARALLEL_TRANSCRIPTION=false
```

---

## Erros de FFmpeg

### ❌ FFmpeg not found

**Erro**:
```
FileNotFoundError: ffmpeg not found
```

**Causa**: FFmpeg não está instalado no container (bug no build).

**Solução**:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

### ❌ FFmpeg conversion failed

**Erro**:
```
FFmpegError: Conversion to WAV failed
```

**Causa**: Áudio corrompido ou formato inválido.

**Soluções**:

1. **Tente outro vídeo**
2. **Check logs**:
```bash
docker-compose logs --tail=100
```

3. **Manual test** (dentro do container):
```bash
docker exec -it ytcaption bash
ffmpeg -version
```

---

## Erros de API

### ❌ 400 Bad Request

**Erro**:
```json
{
  "detail": "Invalid YouTube URL format"
}
```

**Causa**: URL inválida.

**Solução**: Use formato correto:
- ✅ `https://www.youtube.com/watch?v=VIDEO_ID`
- ✅ `https://youtu.be/VIDEO_ID`
- ❌ `youtube.com/VIDEO_ID`

---

### ❌ 429 Too Many Requests

**Erro**:
```json
{
  "detail": "Too many concurrent requests"
}
```

**Causa**: Limite de `MAX_CONCURRENT_REQUESTS` atingido.

**Soluções**:

1. **Aguarde** (outra transcrição terminar)

2. **Aumente limite** (se tiver RAM):
```bash
MAX_CONCURRENT_REQUESTS=5  # Era 3
```

---

### ❌ 500 Internal Server Error

**Erro**:
```json
{
  "detail": "Internal server error"
}
```

**Diagnóstico**:
```bash
docker-compose logs --tail=100
```

**Soluções comuns**:
- Out of Memory → Reduza workers/modelo
- FFmpeg error → Rebuild container
- Bug → Check logs, reporte issue

---

### ❌ 503 Service Unavailable

**Erro**:
```json
{
  "detail": "Service temporarily unavailable"
}
```

**Causa**: Container não está rodando ou iniciando.

**Solução**:
```bash
docker-compose ps
docker-compose up -d
```

---

### ❌ Connection Refused

**Erro**:
```
curl: (7) Failed to connect to localhost port 8000: Connection refused
```

**Causa**: API não está rodando.

**Diagnóstico**:
```bash
docker-compose ps
```

**Solução**:
```bash
docker-compose up -d
```

---

## Performance Issues

### ⚠️ Transcrição muito lenta

**Sintomas**: 1 hora de áudio demora > 2 horas.

**Soluções**:

#### 1. Habilite paralelização
```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4
```

#### 2. Use modelo menor
```bash
WHISPER_MODEL=base  # Era small
```

#### 3. Use GPU (se disponível)
```bash
WHISPER_DEVICE=cuda
```

#### 4. Check CPU usage
```bash
htop
# Se CPU < 50%, aumente workers
PARALLEL_WORKERS=4  # Era 2
```

---

### ⚠️ CPU em 100%

**Sintomas**: Sistema travando, lag.

**Soluções**:

#### 1. Reduza workers
```bash
PARALLEL_WORKERS=2  # Era 8
```

#### 2. Limite recursos (docker-compose.yml)
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '4.0'  # Máximo 4 cores
```

---

### ⚠️ Disco cheio

**Erro**:
```
OSError: [Errno 28] No space left on device
```

**Soluções**:

#### 1. Limpe temp
```bash
rm -rf ./temp/*
```

#### 2. Limpe Docker
```bash
docker system prune -a
```

#### 3. Configure cleanup automático
```bash
# .env
CLEANUP_AFTER_PROCESSING=true
MAX_TEMP_AGE_HOURS=24
```

---

### ⚠️ RAM alta (sem OOM)

**Sintomas**: RAM em 90%+, mas não crashando.

**Soluções**:

#### 1. Reduza workers
```bash
PARALLEL_WORKERS=2  # Era 4
MAX_CONCURRENT_REQUESTS=2  # Era 4
```

#### 2. Use modelo menor
```bash
WHISPER_MODEL=base  # Era small
```

---

## Comandos de Diagnóstico

### Check Container Status
```bash
docker-compose ps
docker-compose logs --tail=100
```

### Check Resources
```bash
# CPU/RAM
docker stats ytcaption

# Disk
df -h

# RAM system
free -h
```

### Check API Health
```bash
curl http://localhost:8000/health | jq
```

### Check Logs em Tempo Real
```bash
docker-compose logs -f --tail=50
```

### Restart Completo
```bash
docker-compose down
docker-compose up -d
docker-compose logs -f
```

### Rebuild Completo
```bash
docker-compose down
docker system prune -a  # ⚠️ Remove TUDO
docker-compose build --no-cache
docker-compose up -d
```

---

## Logs Úteis

### Application Logs
```bash
docker exec -it ytcaption cat /app/logs/app.log
```

### Docker Logs
```bash
docker-compose logs --since 1h
```

### Nginx Logs (se usar)
```bash
tail -f /var/log/nginx/ytcaption-error.log
```

---

## Reportar Bug

Se nenhuma solução funcionou, reporte o bug:

**GitHub Issue**: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/issues

**Inclua**:
1. ✅ Versão da aplicação (`APP_VERSION`)
2. ✅ Configuração (`.env` sem dados sensíveis)
3. ✅ Logs completos (`docker-compose logs`)
4. ✅ Comando/requisição que falhou
5. ✅ Hardware (CPU cores, RAM, GPU)
6. ✅ Sistema operacional

**Exemplo**:
```markdown
## Bug: Out of Memory na transcrição

**Versão**: 1.3.3
**Sistema**: Ubuntu 22.04 LXC (Proxmox)
**Hardware**: 4 cores CPU, 8GB RAM

**Configuração**:
```
WHISPER_MODEL=base
PARALLEL_WORKERS=4
MAX_CONCURRENT_REQUESTS=3
```

**Erro**:
```
RuntimeError: Out of memory
```

**Logs**:
```
[Colar logs aqui]
```
```

---

## FAQ

### P: Qual modelo devo usar?
**R**: `base` para 90% dos casos. Ver [Whisper Models](./05-WHISPER-MODELS.md).

### P: Como melhorar velocidade?
**R**: Habilite paralelização ou use GPU. Ver [Parallel Transcription](./06-PARALLEL-TRANSCRIPTION.md).

### P: Preciso de GPU?
**R**: Não, mas GPU é 10-20x mais rápido.

### P: Quanto de RAM preciso?
**R**: Mínimo 4GB, recomendado 8GB+ para produção.

### P: Suporta Windows?
**R**: Sim, via WSL2 + Docker Desktop.

### P: Posso transcrever arquivos locais?
**R**: Não diretamente. Apenas URLs do YouTube (por design).

### P: Qual a precisão da transcrição?
**R**: 75-85% (`base`), 85-90% (`small`), 90-95% (`medium`).

---

**Próximo**: [Architecture](./09-ARCHITECTURE.md)

**Versão**: 1.3.3+  
**Última atualização**: 19/10/2025
