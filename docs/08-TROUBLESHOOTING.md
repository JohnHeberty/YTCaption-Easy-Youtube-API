# 🔧 Troubleshooting

**Guia completo de solução de problemas - erros comuns e como resolver.**

---

## 📋 Índice

1. [Erros de Instalação](#erros-de-instalação)
2. [Erros de Docker](#erros-de-docker)
3. [Erros de Memória (OOM)](#erros-de-memória-oom)
4. [Erros de Download (YouTube)](#erros-de-download-youtube)
   - [🆕 v3.0 - YouTube Resilience System](#v30---youtube-resilience-system)
5. [Erros de Transcrição](#erros-de-transcrição)
6. [Erros de FFmpeg](#erros-de-ffmpeg)
7. [Erros de API](#erros-de-api)
8. [Performance Issues](#performance-issues)
9. [🆕 Monitoramento (Prometheus/Grafana)](#monitoramento-prometheusgrafana)

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

### 🆕 v3.0 - YouTube Resilience System

**Desde v3.0, o sistema possui 5 camadas de resiliência para downloads. A maioria dos erros é tratada automaticamente.**

#### 📊 Diagnóstico Rápido

**Verifique métricas no Grafana**:
```
http://localhost:3001
Dashboard: YouTube Resilience v3.0
```

**Rode script diagnóstico**:
```bash
docker-compose exec app python -m scripts.youtube_diagnostic
```

---

### ❌ HTTP 403 Forbidden (MAIS COMUM v3.0)

**Erro**:
```json
{
  "error": "yt-dlp download failed",
  "details": "HTTP Error 403: Forbidden"
}
```

**Causa**: YouTube detectou bot/requisições automáticas.

**Soluções (em ordem de efetividade)**:

#### ✅ 1. Habilite Tor Proxy (RECOMENDADO)
```bash
# .env
ENABLE_TOR_PROXY=true
TOR_PROXY_URL=socks5h://torproxy:9050
```

**Verifique Tor**:
```bash
# Check se Tor está rodando
docker-compose ps torproxy

# Teste conexão
docker-compose exec app curl --socks5-hostname torproxy:9050 https://check.torproject.org
```

**Resultado esperado**: `"Congratulations. This browser is configured to use Tor."`

---

#### ✅ 2. Ajuste Rate Limiting
```bash
# .env - Reduz agressividade de requests
YOUTUBE_REQUESTS_PER_MINUTE=5   # Era 20
YOUTUBE_REQUESTS_PER_HOUR=50    # Era 100
YOUTUBE_COOLDOWN_ON_ERROR=30    # Espera 30s após erro
```

---

#### ✅ 3. Habilite User-Agent Rotation
```bash
# .env
ENABLE_USER_AGENT_ROTATION=true
```

**Verifica rotação** (logs):
```bash
docker-compose logs app | grep "User-Agent"
# Deve mostrar diferentes UAs: Chrome, Firefox, Safari, Edge
```

---

#### ✅ 4. Habilite Multi-Strategy
```bash
# .env
ENABLE_MULTI_STRATEGY=true
YOUTUBE_MAX_RETRIES=5
```

**O que faz**: Tenta 7 estratégias automaticamente:
1. Direct download (sem cookies)
2. Com cookies do navegador
3. Via mobile user-agent
4. Com referer header
5. Extract format (bypass age restriction)
6. Via embedded player
7. Fallback OAuth2

---

#### ✅ 5. Aumente Retry Delays
```bash
# .env - Exponential backoff agressivo
YOUTUBE_RETRY_DELAY_MIN=5      # Era 2
YOUTUBE_RETRY_DELAY_MAX=60     # Era 30
```

**Fórmula**: `delay = min(min_delay * 2^attempt, max_delay)`
- Tentativa 1: 5s
- Tentativa 2: 10s
- Tentativa 3: 20s
- Tentativa 4: 40s
- Tentativa 5: 60s (max)

---

#### ✅ 6. Circuit Breaker (último recurso)
```bash
# .env - Previne ban permanente
YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=10  # Para após 10 falhas
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=300   # Aguarda 5min antes de tentar novamente
```

**Status do circuit**:
```bash
# Grafana: Panel "Circuit Breaker Status"
# Logs:
docker-compose logs app | grep "Circuit breaker"
```

---

### ❌ Network unreachable

**Erro**:
```
[Errno 101] Network is unreachable
```

**Causas**:
- Tor proxy offline
- DNS misconfigured
- Firewall bloqueando

**Diagnóstico**:

#### 1. Check Tor
```bash
# Tor deve estar "Up"
docker-compose ps torproxy

# Restart se necessário
docker-compose restart torproxy

# Aguarde 30s para Tor estabelecer circuito
sleep 30
```

#### 2. Check DNS
```bash
# .env
# DNS configurado em docker-compose.yml:
dns:
  - 8.8.8.8
  - 8.8.4.4
  - 1.1.1.1

# Teste resolução
docker-compose exec app nslookup youtube.com
```

#### 3. Check Firewall (UFW)
```bash
# Proxmox Linux - libere portas
ufw allow 9050/tcp   # Tor SOCKS5
ufw allow 9051/tcp   # Tor Control
ufw reload
```

#### 4. Fallback: Desabilite Tor temporariamente
```bash
# .env
ENABLE_TOR_PROXY=false
ENABLE_MULTI_STRATEGY=true  # Mantenha outras camadas
```

---

### ❌ All strategies failed

**Erro**:
```json
{
  "error": "All download strategies failed",
  "details": "7 strategies attempted, all returned 403/503"
}
```

**Significa**: YouTube está bloqueando IP/sessão ativamente.

**Soluções DRÁSTICAS**:

#### 1. Tor + Nova Identidade
```bash
# Força Tor a trocar circuito (novo IP)
docker-compose exec torproxy pkill -HUP tor

# Aguarda novo circuito (30s)
sleep 30

# Tenta novamente
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://youtube.com/watch?v=VIDEO_ID"}'
```

#### 2. Aguarde Cooldown Completo
```bash
# .env - Aumenta muito o intervalo
YOUTUBE_COOLDOWN_ON_ERROR=300  # 5 minutos após erro
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=600  # 10 min
```

**Aguarde**: Circuit breaker vai abrir automaticamente após timeout.

#### 3. Última opção: Troque servidor
```bash
# Deploy em outra região/IP
# YouTube pode ter banido IP do servidor atual
```

---

### ❌ Rate limit exceeded

**Erro**:
```json
{
  "error": "Rate limit exceeded",
  "details": "20 requests in 1 minute (max: 20)"
}
```

**Causa**: Muitas requisições muito rápido.

**Soluções**:

#### 1. Aumente limites
```bash
# .env
YOUTUBE_REQUESTS_PER_MINUTE=30   # Era 20
YOUTUBE_REQUESTS_PER_HOUR=200    # Era 100
```

#### 2. Reduza carga paralela
```bash
# .env
MAX_CONCURRENT_REQUESTS=1  # Era 3
PARALLEL_WORKERS=2         # Era 4
```

#### 3. Check Grafana
```
Dashboard: YouTube Resilience v3.0
Panel: "Rate Limiting Status"
- Verde: OK
- Amarelo: Próximo do limite
- Vermelho: Limite atingido (espera cooldown)
```

---

### ❌ Tor circuit failed

**Erro**:
```
Tor SOCKS proxy connection failed
```

**Diagnóstico completo**:

```bash
# 1. Container Tor está rodando?
docker-compose ps torproxy
# Esperado: State=Up, Ports=9050/tcp, 9051/tcp

# 2. Tor estabeleceu circuito?
docker-compose logs torproxy | grep "Bootstrapped 100%"
# Esperado: "Bootstrapped 100% (done): Done"

# 3. Teste conexão SOCKS5
docker-compose exec app curl --socks5-hostname torproxy:9050 https://check.torproject.org
# Esperado: "Congratulations. This browser is configured to use Tor."

# 4. Teste download via Tor
docker-compose exec app python -c "
import requests
proxies = {'http': 'socks5h://torproxy:9050', 'https': 'socks5h://torproxy:9050'}
resp = requests.get('https://youtube.com', proxies=proxies, timeout=10)
print(f'Status: {resp.status_code}')
"
# Esperado: Status: 200
```

**Soluções**:

#### 1. Restart Tor (limpa circuito)
```bash
docker-compose restart torproxy
sleep 30  # Aguarda bootstrap
```

#### 2. Force nova identidade
```bash
docker-compose exec torproxy pkill -HUP tor
sleep 15
```

#### 3. Rebuild Tor (se persistir)
```bash
docker-compose down torproxy
docker-compose up -d torproxy
docker-compose logs -f torproxy  # Aguarda "Bootstrapped 100%"
```

#### 4. Fallback temporário
```bash
# .env
ENABLE_TOR_PROXY=false
ENABLE_MULTI_STRATEGY=true
ENABLE_USER_AGENT_ROTATION=true
```

---

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

---

## 🆕 Monitoramento (Prometheus/Grafana)

**Desde v3.0, métricas detalhadas estão disponíveis para diagnosticar problemas.**

### Acesse Dashboards

```bash
# Grafana (interface visual)
http://localhost:3001
# Login: admin / admin (troque na primeira vez)

# Prometheus (dados brutos)
http://localhost:9090
```

---

### Dashboard: YouTube Resilience v3.0

**Localização**: Grafana → Dashboards → YouTube Resilience v3.0

**Panels disponíveis**:

#### 1. **Download Success Rate**
- **Verde (>90%)**: Sistema saudável
- **Amarelo (70-90%)**: Problemas intermitentes
- **Vermelho (<70%)**: YouTube bloqueando

**Ação se vermelho**:
```bash
# .env
ENABLE_TOR_PROXY=true
YOUTUBE_REQUESTS_PER_MINUTE=10  # Reduz agressividade
```

---

#### 2. **Active Strategies**
Mostra quais das 7 estratégias estão funcionando.

**Exemplo de leitura**:
```
Strategy 1 (Direct): 45% success
Strategy 2 (Cookies): 30% success
Strategy 3 (Mobile): 15% success
Strategy 6 (Embedded): 10% success
Outras: 0% (não usadas)
```

**Ação**: Se todas < 20%, habilite Tor.

---

#### 3. **Rate Limiting Status**
- **Verde**: Dentro dos limites
- **Amarelo**: Próximo do limite (80%)
- **Vermelho**: Limite atingido (espera cooldown)

**Ação se frequentemente vermelho**:
```bash
# .env
YOUTUBE_REQUESTS_PER_MINUTE=30   # Aumenta limite
YOUTUBE_COOLDOWN_ON_ERROR=60     # Cooldown maior
```

---

#### 4. **Circuit Breaker Status**
- **Closed (verde)**: Requisições passando normalmente
- **Open (vermelho)**: Sistema pausado (muitas falhas)
- **Half-Open (amarelo)**: Testando recuperação

**Ação se "Open"**:
```bash
# Aguarde CIRCUIT_BREAKER_TIMEOUT (padrão: 60s)
# Sistema testa automaticamente e reabre se OK

# Se persistir > 5min:
docker-compose restart torproxy  # Novo IP Tor
sleep 30
```

---

#### 5. **User-Agent Distribution**
Mostra rotação de User-Agents (deve ter 4+ diferentes).

**Ação se apenas 1 UA**:
```bash
# .env
ENABLE_USER_AGENT_ROTATION=true
```

---

#### 6. **Average Retry Count**
- **<2**: Poucos problemas
- **2-4**: Alguns retries (normal)
- **>4**: Muitos problemas (YouTube bloqueando)

**Ação se >4**:
```bash
# .env
ENABLE_TOR_PROXY=true
YOUTUBE_RETRY_DELAY_MAX=120  # Delays maiores
```

---

#### 7. **403 Forbidden Errors (last 5min)**
Conta quantos HTTP 403 ocorreram.

- **0-2**: OK
- **3-5**: Atenção
- **>5**: Crítico (YouTube detectando bot)

**Ação se >5**:
```bash
# .env
ENABLE_TOR_PROXY=true
YOUTUBE_REQUESTS_PER_MINUTE=5   # Muito conservador
YOUTUBE_COOLDOWN_ON_ERROR=120   # 2min entre erros
```

---

#### 8. **Network Errors**
Erros de conexão (DNS, Tor offline, firewall).

**Ação se >0**:
```bash
# Check Tor
docker-compose ps torproxy
docker-compose logs torproxy | grep "Bootstrapped 100%"

# Check DNS
docker-compose exec app nslookup youtube.com

# Check Firewall
ufw status | grep "9050\|9051"
```

---

#### 9. **Cooldown Active**
Mostra se sistema está em cooldown (aguardando após erro).

- **false**: Sistema operando normalmente
- **true**: Aguardando COOLDOWN_ON_ERROR segundos

**Normal**: Aparecer após erros 403/503.

---

#### 10. **Request Duration (p95)**
Tempo de download no percentil 95.

- **<10s**: Ótimo
- **10-30s**: Normal (retries)
- **>30s**: Lento (muitos retries ou Tor lento)

**Ação se >30s frequentemente**:
```bash
# .env
YOUTUBE_MAX_RETRIES=3  # Era 5 (desiste mais cedo)

# Ou desabilite Tor se for a causa
ENABLE_TOR_PROXY=false
```

---

### Queries Prometheus Úteis

Acesse Prometheus (http://localhost:9090) e execute:

#### Download success rate (5 minutos)
```promql
rate(youtube_download_success_total[5m]) / 
(rate(youtube_download_success_total[5m]) + rate(youtube_download_failure_total[5m]))
```

#### Erro 403 por minuto
```promql
rate(youtube_403_forbidden_total[1m]) * 60
```

#### Retries médios
```promql
youtube_retries_before_success / youtube_download_success_total
```

#### Estratégias ativas
```promql
sum by (strategy) (youtube_strategy_success_total)
```

---

### Alertas Recomendados

Configure alertas no Grafana:

#### 1. **Alta taxa de erro 403**
```
Condition: youtube_403_forbidden_total > 10 in 5 minutes
Action: Habilitar Tor, reduzir rate limit
```

#### 2. **Circuit Breaker aberto > 5min**
```
Condition: youtube_circuit_breaker_open == 1 for 5 minutes
Action: Investigar logs, restart Tor
```

#### 3. **Success rate < 70%**
```
Condition: download_success_rate < 0.7 for 10 minutes
Action: Revisar configurações, checar YouTube status
```

---

### Logs Detalhados

**Download iniciado**:
```json
{
  "event": "youtube_download_start",
  "video_id": "ABC123",
  "attempt": 1,
  "strategy": "direct",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
}
```

**Download com retry**:
```json
{
  "event": "youtube_download_retry",
  "video_id": "ABC123",
  "attempt": 2,
  "strategy": "cookies",
  "previous_error": "HTTP 403 Forbidden",
  "retry_delay": 4.0,
  "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Firefox/121.0"
}
```

**Download sucesso**:
```json
{
  "event": "youtube_download_success",
  "video_id": "ABC123",
  "attempt": 3,
  "strategy": "mobile",
  "duration": 12.5,
  "file_size_mb": 45.2,
  "total_retries": 2
}
```

**Download falha (todas estratégias)**:
```json
{
  "event": "youtube_download_all_failed",
  "video_id": "ABC123",
  "total_attempts": 7,
  "strategies_tried": ["direct", "cookies", "mobile", "referer", "extract", "embedded", "oauth"],
  "errors": ["403", "403", "503", "403", "403", "403", "403"],
  "circuit_breaker_triggered": true
}
```

**View logs em tempo real**:
```bash
# Todos os eventos YouTube
docker-compose logs -f app | grep "youtube_download"

# Apenas erros
docker-compose logs -f app | grep "youtube_download.*error\|all_failed"

# Apenas sucessos
docker-compose logs -f app | grep "youtube_download_success"
```

---

### Troubleshooting com Métricas

#### Cenário 1: "Muitos erros 403"

**Diagnóstico**:
```bash
# Grafana: Panel "403 Forbidden Errors" mostra 15 erros em 5min
# Prometheus:
rate(youtube_403_forbidden_total[5m]) * 300
# Output: 15.0
```

**Solução**:
```bash
# .env
ENABLE_TOR_PROXY=true
YOUTUBE_REQUESTS_PER_MINUTE=5
docker-compose restart app
```

**Validação** (aguarde 5min):
```bash
# Grafana: "403 Forbidden Errors" deve cair para <3
# Success Rate deve subir para >85%
```

---

#### Cenário 2: "Transcrições parando"

**Diagnóstico**:
```bash
# Grafana: "Circuit Breaker Status" = OPEN (vermelho)
# Prometheus:
youtube_circuit_breaker_open
# Output: 1 (aberto)
```

**Solução**:
```bash
# Aguarde timeout (60s padrão)
# Ou force reset:
docker-compose restart torproxy
sleep 30
docker-compose restart app
```

**Validação**:
```bash
# Grafana: Circuit Breaker = CLOSED (verde) após 1min
```

---

#### Cenário 3: "Tor não está funcionando"

**Diagnóstico**:
```bash
# Grafana: "Active Strategies" mostra Strategy 1-6, mas nenhuma sucesso
# Logs:
docker-compose logs app | grep "Network unreachable"
# Output: [Errno 101] Network is unreachable
```

**Solução**:
```bash
# Check Tor
docker-compose logs torproxy | grep "Bootstrapped"
# Esperado: "Bootstrapped 100% (done): Done"

# Se não aparece, rebuild:
docker-compose down torproxy
docker-compose up -d torproxy
sleep 60  # Aguarda bootstrap completo
```

**Validação**:
```bash
# Test Tor connection
docker-compose exec app curl --socks5-hostname torproxy:9050 https://check.torproject.org
# Esperado: "Congratulations. This browser is configured to use Tor."
```

---

### Links Úteis

- **Grafana Docs**: https://grafana.com/docs/
- **Prometheus Queries**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **yt-dlp Status**: https://github.com/yt-dlp/yt-dlp/issues
- **Tor Project**: https://www.torproject.org/
- **YouTube API Status**: https://www.google.com/appsstatus/dashboard/

---

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
