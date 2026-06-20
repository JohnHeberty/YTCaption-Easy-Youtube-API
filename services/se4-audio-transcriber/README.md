# SE4 -- Audio Transcriber

> Transcricao de audio com Whisper (faster-whisper), suporte a GPU CUDA e multiplos engines

## Quick Start

```bash
# Docker
make up          # Sobe API + Celery worker + Celery beat
make logs        # Logs dos 3 containers
make api-health  # Health check

# Desenvolvimento local
make venv install
make dev         # Porta 8004
```

### Variaveis essenciais

| Variavel | Default | Descricao |
|---|---|---|
| `PORT` | `8004` | Porta da API |
| `REDIS_URL` | `redis://localhost:6379/4` | Conexao Redis |
| `WHISPER_MODEL` | `small` | Modelo (tiny/base/small/medium/large) |
| `WHISPER_DEVICE` | `cpu` | Dispositivo (cpu/cuda) |
| `CACHE_TTL_HOURS` | `24` | TTL dos jobs |
| `ENABLE_CHUNKING` | `false` | Chunking para audios longos |

## Key Endpoints

| Metodo | Caminho | Descricao |
|---|---|---|
| POST | `/jobs` | Criar job (multipart upload) |
| GET | `/jobs` | Listar jobs |
| GET | `/jobs/{id}` | Status e resultado |
| GET | `/jobs/{id}/text` | Texto puro |
| GET | `/jobs/{id}/transcription` | Transcricao completa com segments |
| GET | `/jobs/{id}/download` | Download SRT |
| POST | `/model/load` | Pre-carregar modelo Whisper |
| POST | `/model/unload` | Liberar modelo da memoria |
| GET | `/health` | Health check |
| GET | `/metrics` | Metricas Prometheus |

### Exemplo

```bash
curl -X POST http://localhost:8004/jobs \
  -F "file=@audio.mp3" \
  -F "language=pt"
```

## Architecture Notes

- **Entry point**: `run.py` inicia uvicorn na porta 8004. FastAPI app registra 4 routers: jobs, admin, model, health.
- **Domain**: `AudioTranscriptionJob` extends `StandardJob` com `language`, `engine`, `segments`. Tres engines: faster-whisper (padrao, 4x mais rapido), openai-whisper, whisperx.
- **Processing flow**: `POST /jobs` salva arquivo, cria job no Redis, submete task Celery (`transcribe_audio_task`). O `TranscriptionProcessor` valida, converte para WAV 16kHz mono via ffmpeg, transcreve com engine selecionado, gera SRT, atualiza Redis.
- **Infraestrutura**: 3 containers Docker — API (FastAPI + uvicorn), Celery worker (pool solo), Celery beat (cleanup periodico). Todos compartilham volumes para uploads, transcricoes, modelos, temp e logs.
- **Model management**: `FasterWhisperModelManager` gerencia lazy loading, deteccao GPU com fallback CPU em OOM, circuit breaker e word-level timestamps. Modelos cacheados em `./data/models/`.
