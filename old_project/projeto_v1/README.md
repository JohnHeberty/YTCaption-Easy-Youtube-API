# YTCaption - API de Transcrição do YouTube

🎙️ **API REST para transcrição de vídeos do YouTube usando Whisper com Clean Architecture**

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com/)
[![Whisper](https://img.shields.io/badge/OpenAI-Whisper-orange)](https://github.com/openai/whisper)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)

## ✨ Features

- 🎥 Download automático de áudio do YouTube
- 🎙️ Transcrição com OpenAI Whisper (6 modelos disponíveis)
- ⚡ **Transcrição paralela** (3-4x mais rápido em multi-core)
- 🧠 **Seleção inteligente** de modo (single-core vs paralelo)
- 🌍 Suporte a 99 idiomas com detecção automática
- 🏗️ **Clean Architecture + SOLID Principles**
- 🐳 Docker pronto para produção (Proxmox/LXC)
- � Múltiplos formatos de saída (JSON, SRT, VTT, TXT)
- 🔧 Altamente configurável (52 variáveis de ambiente)

## 🚀 Quick Start (5 minutos)

**Script automático** (detecta sistema e instala tudo):
```bash
wget https://raw.githubusercontent.com/JohnHeberty/YTCaption-Easy-Youtube-API/main/start.sh
chmod +x start.sh
./start.sh
```

Acesse: **http://localhost:8000**

## 📚 Documentação Completa

**Documentação organizada com Single Responsibility Principle**:

| Documento | Descrição |
|-----------|-----------|
| **[01-GETTING-STARTED](docs/01-GETTING-STARTED.md)** | 🚀 Início rápido em 5 minutos |
| **[02-INSTALLATION](docs/02-INSTALLATION.md)** | 📦 Instalação (Docker, Local, Proxmox) |
| **[03-CONFIGURATION](docs/03-CONFIGURATION.md)** | ⚙️ Todas as 52 variáveis `.env` explicadas |
| **[04-API-USAGE](docs/04-API-USAGE.md)** | � Endpoints, requests e responses |
| **[05-WHISPER-MODELS](docs/05-WHISPER-MODELS.md)** | 🎯 Escolher modelo ideal (tiny→large) |
| **[06-PARALLEL-TRANSCRIPTION](docs/06-PARALLEL-TRANSCRIPTION.md)** | ⚡ Processamento paralelo otimizado |
| **[07-DEPLOYMENT](docs/07-DEPLOYMENT.md)** | 🚀 Produção (Nginx, SSL, Monitoramento) |
| **[08-TROUBLESHOOTING](docs/08-TROUBLESHOOTING.md)** | 🔧 Solução de problemas comuns |
| **[09-ARCHITECTURE](docs/09-ARCHITECTURE.md)** | 🏛️ Clean Architecture + SOLID (para devs) |
| **[10-PARALLEL-ARCHITECTURE](docs/10-PARALLEL-ARCHITECTURE.md)** | 🚀 Persistent Worker Pool (v2.0.0) |
| **[CHANGELOG](docs/CHANGELOG.md)** | 📝 Histórico de versões |

**Documentação interativa**: http://localhost:8000/docs (Swagger UI)

## 🔥 Exemplo Rápido

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \\
  -H "Content-Type: application/json" \\
  -d '{
    "youtube_url": "https://youtube.com/watch?v=exemplo",
    "use_youtube_transcript": true
  }'
```

## 🎯 Quando Usar Cada Método

**YouTube Transcript** (1-2s):
- ✅ Vídeo com legendas
- ✅ Vídeos longos (1h+)
- ✅ Resultado rápido

**Whisper** (mais lento):
- ✅ Sem legendas
- ✅ Máxima precisão
- ✅ Áudio complexo

## ⚙️ Configuração Principal

```env
WHISPER_MODEL=base          # tiny|base|small|medium|large
WHISPER_DEVICE=cpu          # cpu|cuda
MAX_VIDEO_SIZE_MB=2500
PORT=8000

# Transcrição Paralela (Persistent Worker Pool - v2.0.0)
ENABLE_PARALLEL_TRANSCRIPTION=true   # true=paralelo (todos áudios), false=single-core
PARALLEL_WORKERS=2                   # Número de workers (0 = auto-detect)
PARALLEL_CHUNK_DURATION=120          # Duração dos chunks em segundos
```

### 🚀 Transcrição Paralela (v2.0.0 - Otimizada!)

Para áudios longos, use transcrição paralela com **persistent worker pool**:

```env
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2
```

**Benefícios:**
- ⚡ **7-10x mais rápido** vs versão anterior (v1.2.0)
- 🚀 **3-5x mais rápido** vs single-core
- 🧠 Workers carregam modelo **UMA VEZ** no startup
- 📦 Chunks pré-criados em disco via FFmpeg
- 🔒 Sessões isoladas para requisições concorrentes
- 🎯 Ideal para vídeos de 10+ minutos

**Exemplo Real (Proxmox LXC, 4 cores, modelo base):**
- Vídeo 45min: **~22 minutos** (v1.2.0) → **~2-3 minutos** (v2.0.0) 🚀

**Requisitos:**
- ⚠️ RAM: `(workers × tamanho_modelo)` - Ex: 2 workers × 800MB = ~2GB
- ⚠️ Requer FFmpeg instalado
- 💡 Recomendado: 4GB+ RAM, 2-4 workers

Veja [docs/10-PARALLEL-ARCHITECTURE.md](docs/10-PARALLEL-ARCHITECTURE.md) para arquitetura completa.

## 🐳 Deploy Proxmox

Scripts automáticos disponíveis em `docs/STARTUP_SCRIPTS.md`

```bash
chmod +x start.sh
./start.sh  # Detecta hardware e configura automaticamente
```

## 📊 Performance

| Método | Vídeo 3min | Vídeo 45min |
|--------|------------|-------------|
| **YouTube Transcript** | 1-2s | 2-5s |
| **Whisper Tiny** | 42s | 15min |
| **Whisper Base (Single-core)** | 106s | ~6min |
| **Whisper Base (Paralelo v2.0)** | ~35s | **~2-3min** 🚀 |

*Transcrição paralela v2.0: speedup de 7-10x vs v1.2.0, 3-5x vs single-core*

## � Versão Atual: v2.0.0

### 🚀 Novidades v2.0.0 (Breaking Changes)

- � **Persistent Worker Pool**: Workers carregam modelo 1x no startup
- ⚡ **Performance**: 7-10x mais rápido vs v1.2.0 paralelo
- 🧠 **Session Isolation**: Pastas isoladas para requisições concorrentes
- 📦 **Chunk Preparation**: Pré-criação de chunks via FFmpeg
- 🗑️ **V1 Descontinuada**: Versão antiga (ProcessPoolExecutor) removida
- � **Documentação**: Arquitetura completa e guia de migração

**Breaking Changes:**
- Remoção da implementação paralela V1 (lenta)
- Modo de operação simplificado (sem auto-switch baseado em duração)
- Workers iniciados no startup da aplicação (não por request)

Veja [docs/CHANGELOG.md](docs/CHANGELOG.md) para detalhes completos.

## 🏗️ Arquitetura

```
src/
├── domain/         # Regras de negócio
├── application/    # Casos de uso
├── infrastructure/ # YouTube, Whisper, Storage
└── presentation/   # FastAPI routes
```

Clean Architecture + Dependency Injection + SOLID

## 🤝 Contribuindo

1. Fork o projeto
2. Crie branch (`git checkout -b feature/nova`)
3. Commit (`git commit -m 'feat: adiciona X'`)
4. Push (`git push origin feature/nova`)
5. Pull Request

## 📝 Licença

MIT License - veja [LICENSE](LICENSE)

---

**Desenvolvido com ❤️ usando Clean Architecture**
