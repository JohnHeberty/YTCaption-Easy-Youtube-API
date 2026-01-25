# Make-Video Service

**Microserviço Orquestrador para Criação de Vídeos Dinâmicos**

## 📋 Visão Geral

Serviço que cria vídeos automaticamente usando:
- **YouTube Shorts** (concatenados aleatoriamente)
- **Áudio customizado** (substituindo áudio original)
- **Legendas automáticas** (sincronizadas)

### ⚠️ Princípio Fundamental: NÃO REINVENTAR A RODA

Este serviço é um **orquestrador puro** que:

✅ **USA** youtube-search (Port 8003) - Para buscar shorts  
✅ **USA** video-downloader (Port 8002) - Para baixar vídeos  
✅ **USA** audio-transcriber (Port 8005) - Para gerar legendas  

❌ **NÃO reimplementa** busca no YouTube  
❌ **NÃO reimplementa** download de vídeos  
❌ **NÃO reimplementa** transcrição de áudio  

**Responsabilidade exclusiva:** Orquestração + Montagem de vídeo (FFmpeg)

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────┐
│      MAKE-VIDEO SERVICE (Orquestrador)      │
│                                             │
│  FastAPI + Celery + Redis + FFmpeg         │
└──────────────┬──────────────────────────────┘
               │ HTTP
    ┌──────────┼──────────┬──────────────────┐
    ▼          ▼          ▼                  ▼
┌────────┐ ┌────────┐ ┌────────┐      ┌─────────┐
│ youtube│ │ video- │ │ audio- │      │ Storage │
│ search │ │downloader transcriber     │ System  │
│ :8003  │ │ :8002  │ │ :8005  │      └─────────┘
└────────┘ └────────┘ └────────┘
[EXISTENTE] [EXISTENTE] [EXISTENTE]
```

## 🚀 Features

- 🎬 **Aspect Ratio 9:16** (padrão vertical/Shorts)
- 🎲 **Montagem Aleatória** - Vídeos únicos a cada execução
- 💾 **Cache Local** - Reutilização de shorts já baixados
- 📝 **Legendas Automáticas** - Via audio-transcriber
- ⚡ **Processamento Assíncrono** - Celery para jobs longos
- 🔄 **Reutilização 100%** - Usa infraestrutura existente

## 📦 Instalação

### Requisitos

- Python 3.11+
- FFmpeg 6.0+
- Redis 7.0+
- Docker + docker-compose (recomendado)

### Configuração

```bash
# Copiar arquivo de ambiente
cp .env.example .env

# Editar configurações
nano .env
```

### Deploy com Docker

```bash
# Build e start
docker-compose up -d

# Verificar logs
docker-compose logs -f make-video

# Health check
curl http://localhost:8004/health
```

## 🎯 Uso

### Criar Vídeo

```bash
curl -X POST "http://localhost:8004/make-video" \
  -F "audio_file=@meu_audio.mp3" \
  -F "query=tech tips" \
  -F "max_shorts=100" \
  -F "aspect_ratio=9:16"
```

**Response:**
```json
{
  "job_id": "abc123",
  "status": "queued",
  "audio_duration": 180.5,
  "target_video_duration": 185.5,
  "estimated_completion": "2026-01-25T10:35:00Z"
}
```

### Verificar Status

```bash
curl "http://localhost:8004/jobs/abc123"
```

### Baixar Vídeo

```bash
curl "http://localhost:8004/download/abc123" -o video_final.mp4
```

## 🔧 Desenvolvimento

### Setup Local

```bash
# Criar virtualenv
python -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Rodar testes
pytest
```

## 📊 Status

**Versão:** 1.0.0  
**Status:** 🚧 Em desenvolvimento  

### Componentes Implementados

- ✅ Estrutura de diretórios
- ✅ Models (Job, CreateVideoRequest)
- ✅ Config
- ✅ Redis Store
- ✅ API Client (integração com microserviços)
- ✅ Video Builder (FFmpeg)
- ✅ Shorts Manager (cache)
- ✅ Subtitle Generator
- 🚧 Celery Tasks (em progresso)
- 🚧 FastAPI Main (em progresso)

## 📝 Licença

MIT License
