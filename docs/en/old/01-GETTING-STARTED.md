# 🚀 Getting Started

**Guia de início rápido - da instalação à primeira transcrição em 5 minutos.**

---

## ⚡ Quick Start (Docker)

### 1. Clone o repositório
```bash
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
```

### 2. Configure o ambiente
```bash
cp .env.example .env
```

### 3. Inicie com Docker
```bash
docker-compose up -d
```

### 4. Verifique se está funcionando
```bash
curl http://localhost:8000/health
```

**Resposta esperada:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-19T15:30:00"
}
```

---

## 🎯 Primeira Transcrição

### Método 1: YouTube Transcript (Legendas Nativas)

**Mais rápido** - usa legendas existentes (1-2 segundos)

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "use_youtube_transcript": true
  }'
```

### Método 2: Whisper AI (Transcrição Real)

**Mais preciso** - transcreve o áudio com IA (minutos)

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "use_youtube_transcript": false,
    "language": "auto"
  }'
```

---

## 📚 Resposta da API

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration": 213.0,
  "language": "en",
  "method": "youtube_transcript",
  "processing_time": 1.2,
  "segments": [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "We're no strangers to love"
    }
  ],
  "full_text": "We're no strangers to love..."
}
```

---

## 🌐 Interface Web

Acesse a documentação interativa:

**Swagger UI**: http://localhost:8000/docs

---

## 🎬 Exemplos Práticos

### Transcrever vídeo em Português
```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "language": "pt"
  }'
```

### Obter apenas informações do vídeo
```bash
curl "http://localhost:8000/api/v1/video-info?url=https://www.youtube.com/watch?v=VIDEO_ID"
```

---

## ⏱️ Tempo de Processamento

| Método | Vídeo 5min | Vídeo 30min | Vídeo 1h |
|--------|------------|-------------|----------|
| **YouTube Transcript** | 1-2s | 1-2s | 2-3s |
| **Whisper (CPU)** | 2-3min | 10-15min | 30-40min |
| **Whisper (GPU)** | 30s | 3-5min | 8-12min |
| **Whisper Paralelo (4 cores)** | 1min | 4-6min | 12-18min |

---

## 🛠️ Próximos Passos

1. **[Configuração Completa](./03-CONFIGURATION.md)** - Ajuste todas as opções do `.env`
2. **[Modelos Whisper](./05-WHISPER-MODELS.md)** - Escolha o modelo ideal
3. **[Transcrição Paralela](./06-PARALLEL-TRANSCRIPTION.md)** - Acelere para vídeos longos
4. **[Deploy](./07-DEPLOYMENT.md)** - Coloque em produção

---

## 🆘 Problemas?

Veja **[Troubleshooting](./08-TROUBLESHOOTING.md)** para soluções rápidas.

---

## 🆕 YouTube Resilience v3.0

**Desde outubro/2024, o sistema possui proteção avançada contra bloqueios do YouTube.**

### Problemas Comuns e Soluções Rápidas

#### ❌ HTTP 403 Forbidden

**Erro mais comum** - YouTube detectou requisições automáticas.

**Solução Rápida**:
```bash
# 1. Edite .env
ENABLE_TOR_PROXY=true
TOR_PROXY_URL=socks5h://torproxy:9050

# 2. Restart
docker-compose restart app

# 3. Aguarde 30s (Tor estabelecendo circuito)
sleep 30

# 4. Tente novamente
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID"}'
```

---

#### ❌ Network Unreachable

**Tor offline ou DNS misconfigured**.

**Solução**:
```bash
# Check Tor
docker-compose ps torproxy

# Restart se necessário
docker-compose restart torproxy
sleep 30
```

---

#### ❌ All Strategies Failed

**YouTube bloqueando IP/sessão ativamente**.

**Solução**:
```bash
# Force Tor a trocar IP
docker-compose exec torproxy pkill -HUP tor
sleep 30

# Tente novamente
```

---

### Configurações Recomendadas (Produção)

```bash
# .env - Configuração robusta v3.0
ENABLE_TOR_PROXY=true
TOR_PROXY_URL=socks5h://torproxy:9050

ENABLE_MULTI_STRATEGY=true
ENABLE_USER_AGENT_ROTATION=true

YOUTUBE_MAX_RETRIES=5
YOUTUBE_RETRY_DELAY_MIN=5
YOUTUBE_RETRY_DELAY_MAX=60

YOUTUBE_REQUESTS_PER_MINUTE=10
YOUTUBE_REQUESTS_PER_HOUR=100
YOUTUBE_COOLDOWN_ON_ERROR=30

YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=10
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=60
```

**Resultado esperado**: Taxa de sucesso >95% (antes era ~60%).

---

### Monitoramento

**Grafana Dashboard**: http://localhost:3001  
**Prometheus Metrics**: http://localhost:9090

**Principais métricas**:
- Download Success Rate (>90% = saudável)
- 403 Forbidden Count (deve ser baixo)
- Circuit Breaker Status (deve estar "Closed")
- Active Strategies (quantas das 7 estratégias funcionam)

---

### Documentação Completa v3.0

- **[Configuração Resilience](./03-CONFIGURATION.md#youtube-resilience-settings-v30)** - 12 env vars explicadas
- **[Troubleshooting v3.0](./08-TROUBLESHOOTING.md#v30---youtube-resilience-system)** - Todos os erros possíveis
- **[CHANGELOG v3.0.0](./CHANGELOG.md#v300---20241019)** - O que mudou

---

**Versão**: 3.0.0+  
**Última atualização**: 19/10/2025
