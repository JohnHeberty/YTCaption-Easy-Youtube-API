# SE3 -- Audio Normalization

> Normalizacao de audio com noise reduction, vocal isolation e cache de 24h

## Quick Start

```bash
# Docker (CPU)
make up          # Sobe API + Celery worker
make health      # Health check
make logs        # Logs
make down        # Derruba

# Docker (GPU)
make up-gpu

# Desenvolvimento local
make install
make dev         # Porta 8003
```

A API fica disponivel em `http://localhost:8003`. Documentacao interativa em `/docs`.

## Key Endpoints

| Metodo | Rota | Descricao |
|---|---|---|
| POST | `/jobs` | Criar job de normalizacao (multipart: `file` + parametros) |
| GET | `/jobs/{job_id}` | Status do job |
| GET | `/jobs/{job_id}/download` | Baixar arquivo processado |
| GET | `/jobs` | Listar jobs recentes |
| POST | `/admin/cleanup` | Limpeza manual |
| GET | `/health` | Health check (Redis, disco, ffmpeg) |
| GET | `/metrics` | Metricas Prometheus |

### Parametros de processamento

Todos opcionais (true/false): `remove_noise`, `convert_to_mono`, `apply_highpass_filter`, `set_sample_rate_16k`, `isolate_vocals`.

### Exemplo

```bash
curl -X POST http://localhost:8003/jobs \
  -F "file=@audio.mp3" \
  -F "remove_noise=true" \
  -F "convert_to_mono=true"
```

## Architecture Notes

- **FastAPI** com BackgroundTasks e fallback para processamento direto se Celery estiver indisponivel.
- **Redis** armazena estado dos jobs como JSON com TTL de 24h.
- **Celery** executa processamento assincrono (`normalize_audio_task`, fila `audio_normalization_queue`), com retry (ate 3 tentativas, backoff exponencial), timeouts (25min soft / 30min hard) e heartbeat.
- **Pipeline**: extracao de audio de video (ffmpeg) > reducao de ruido (noisereduce) > isolamento vocal (librosa.hpss) > filtro high-pass > conversao mono/16kHz > exportacao webm/libopus.
- **GPU**: Dockerfile-GPU com CUDA 12.1 + PyTorch cu121 para aceleracao.
