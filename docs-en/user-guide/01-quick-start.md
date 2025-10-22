# ⚡ Quick Start

**Da instalação à primeira transcrição em 5 minutos**

---

## 🎯 Objetivo

Ao final deste guia você terá:
- ✅ YTCaption rodando localmente
- ✅ Primeira transcrição completa
- ✅ Acesso aos dashboards de monitoramento

**Tempo estimado**: 5 minutos

---

## 🚀 Passo 1: Clone e Configure

```bash
# 1. Clone o repositório
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API

# 2. Copie o arquivo de configuração
cp .env.example .env

# 3. (Opcional) Edite configurações
nano .env
```

**Configuração mínima** (já vem no `.env.example`):
```bash
WHISPER_MODEL=base
ENABLE_TOR_PROXY=false  # Mude para true se YouTube bloquear
```

---

## 🐳 Passo 2: Inicie com Docker

```bash
docker-compose up -d
```

**Aguarde** ~30 segundos para containers iniciarem.

### Verifique se está rodando

```bash
docker-compose ps
```

**Esperado**:
```
NAME                        STATUS
whisper-transcription-api   Up (healthy)
whisper-prometheus          Up
whisper-grafana             Up
whisper-tor-proxy           Up
```

---

## 🧪 Passo 3: Teste a API

### Health Check

```bash
curl http://localhost:8000/health
```

**Esperado**:
```json
{
  "status": "healthy",
  "whisper_model": "base",
  "timestamp": "2025-10-22T10:30:00"
}
```

---

## 🎬 Passo 4: Primeira Transcrição

### Opção 1: Legendas Nativas (RÁPIDO - 1-2s)

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "use_youtube_transcript": true
  }'
```

### Opção 2: Whisper AI (PRECISO - 30s-2min)

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "use_youtube_transcript": false,
    "language": "en"
  }'
```

### Resposta Esperada

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration": 213.0,
  "language": "en",
  "method": "whisper",
  "processing_time": 45.2,
  "transcription": {
    "text": "We're no strangers to love. You know the rules and so do I...",
    "segments": [
      {
        "start": 0.0,
        "end": 3.5,
        "text": "We're no strangers to love"
      },
      {
        "start": 3.5,
        "end": 6.8,
        "text": "You know the rules and so do I"
      }
    ]
  }
}
```

---

## 📊 Passo 5: Acesse os Dashboards

### Swagger UI (Documentação Interativa)
```
http://localhost:8000/docs
```

### Grafana (Monitoramento)
```
http://localhost:3000
Login: admin / whisper2024
```

**Dashboards disponíveis**:
- YouTube Resilience v3.0 (download metrics)
- System Performance (API, Whisper, resources)

### Prometheus (Métricas Brutes)
```
http://localhost:9090
```

---

## ❌ Problemas Comuns

### Erro: "Connection refused"

**Causa**: Containers não iniciaram

**Solução**:
```bash
docker-compose logs -f

# Se necessário, rebuild:
docker-compose down
docker-compose build
docker-compose up -d
```

---

### Erro: "HTTP 403 Forbidden" (YouTube)

**Causa**: YouTube detectou requisições automáticas

**Solução Rápida**:
```bash
# 1. Edite .env
nano .env

# 2. Habilite Tor
ENABLE_TOR_PROXY=true

# 3. Restart
docker-compose restart whisper-api

# 4. Aguarde Tor (30s)
docker-compose logs tor-proxy | grep "Bootstrapped 100%"

# 5. Tente novamente
```

📖 [Troubleshooting completo](./05-troubleshooting.md#http-403-forbidden)

---

### Erro: "Out of Memory"

**Causa**: Modelo Whisper muito grande para RAM disponível

**Solução**:
```bash
# .env - Use modelo menor
WHISPER_MODEL=tiny  # Era base

docker-compose restart whisper-api
```

---

## 🎓 Próximos Passos

Agora que você tem o YTCaption rodando:

1. **Configure para suas necessidades**  
   → [Configuration Guide](./03-configuration.md)

2. **Entenda todos os endpoints da API**  
   → [API Usage](./04-api-usage.md)

3. **Prepare para produção**  
   → [Deployment Guide](./06-deployment.md)

4. **Configure YouTube Resilience v3.0**  
   → [Configuration - YouTube Resilience](./03-configuration.md#youtube-resilience-v30)

---

## 🆘 Precisa de Ajuda?

- **Problemas técnicos**: [Troubleshooting](./05-troubleshooting.md)
- **Dúvidas sobre configuração**: [Configuration](./03-configuration.md)
- **Issue no GitHub**: [Abrir issue](https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/issues)

---

## ✅ Checklist de Sucesso

- [ ] Docker Compose rodando (`docker-compose ps` mostra 4 containers Up)
- [ ] Health check retorna `"status": "healthy"`
- [ ] Primeira transcrição completa (Whisper ou YouTube Transcript)
- [ ] Grafana acessível em http://localhost:3000
- [ ] Swagger UI acessível em http://localhost:8000/docs

**Tudo funcionando?** 🎉 Parabéns! Você está pronto para usar o YTCaption!

---

**[← Voltar para User Guide](./README.md)** | **[Próximo: Installation →](./02-installation.md)**
