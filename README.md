# YTCaption - API de Transcrição do YouTube

🎙️ **API REST para transcrição de vídeos do YouTube usando Whisper e legendas nativas**

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com/)
[![Whisper](https://img.shields.io/badge/OpenAI-Whisper-orange)](https://github.com/openai/whisper)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)

## 📋 Recursos

- 🎥 Download automático do YouTube (menor qualidade)
- 🎙️ Transcrição Whisper ou legendas nativas
- ⚡ **100x mais rápido** com YouTube Transcript
- 🌍 Detecção automática de idioma (10 línguas)
- 🏗️ Clean Architecture + SOLID
-  Docker pronto para Proxmox
- 📚 Documentação completa

## 🚀 Quick Start

### Docker (Recomendado)

```bash
cp .env.example .env
docker-compose up -d
curl http://localhost:8000/health
```

### Local

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac | .\\venv\\Scripts\\activate (Windows)
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn src.presentation.api.main:app --reload
```

## 📖 Documentação

- **[docs/README.md](docs/README.md)** - Documentação completa
- **[docs/EXAMPLES.md](docs/EXAMPLES.md)** - Exemplos práticos
- **[docs/CHANGELOG.md](docs/CHANGELOG.md)** - Versões e melhorias
- **Swagger UI**: http://localhost:8000/docs

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
```

## 🐳 Deploy Proxmox

Scripts automáticos disponíveis em `docs/STARTUP_SCRIPTS.md`

```bash
chmod +x start.sh
./start.sh  # Detecta hardware e configura automaticamente
```

## 📊 Performance

| Método | Vídeo 3min | Vídeo 1h |
|--------|------------|----------|
| **YouTube Transcript** | 1-2s | 2-5s |
| **Whisper Tiny** | 42s | 15min |
| **Whisper Base** | 106s | 30min |

## 🎓 Novidades v1.1.0

- ✅ YouTube Transcript (100x mais rápido)
- ✅ Detecção de idioma automática
- ✅ yt-dlp 2025.10.14 (bugs corrigidos)
- ✅ Lista de legendas disponíveis
- ✅ Recomendações de modelo Whisper

Veja [CHANGELOG.md](docs/CHANGELOG.md) para detalhes completos.

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
