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

**Versão**: 1.3.3+  
**Última atualização**: 19/10/2025
