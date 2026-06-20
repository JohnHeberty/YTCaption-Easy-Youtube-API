# SE2 -- Video Downloader

> Download assincrono de videos do YouTube com yt-dlp, rotacao de user-agent e retry resiliente

## Quick Start

### Docker Compose

```bash
# Build e sobe API + Celery worker
make up

# Health check
make health

# Logs
make logs
```

### Desenvolvimento local

```bash
make venv
make install
make dev   # Porta 8002
```

### Variaveis de Ambiente

| Variavel | Default | Descricao |
|---|---|---|
| `PORT` | `8002` | Porta HTTP |
| `REDIS_URL` | `redis://localhost:6379/0` | Conexao Redis |
| `CACHE_TTL_HOURS` | `24` | Duracao do cache |
| `DEFAULT_QUALITY` | `best` | Qualidade padrao |
| `LOG_LEVEL` | `INFO` | Verbosidade de log |

## Key Endpoints

| Metodo | Caminho | Descricao |
|---|---|---|
| POST | `/jobs` | Criar job de download (body: `url`, `quality` opcional) |
| GET | `/jobs` | Listar jobs recentes |
| GET | `/jobs/{job_id}` | Status detalhado do job |
| GET | `/jobs/{job_id}/download` | Baixar arquivo processado |
| GET | `/jobs/orphaned` | Jobs stuck em processing |
| POST | `/jobs/orphaned/cleanup` | Limpeza de jobs orfaos |
| GET | `/admin/stats` | Estatisticas do servico |
| GET | `/admin/queue` | Detalhes da fila Celery |
| POST | `/admin/cleanup` | Limpeza de jobs expirados |
| GET | `/health` | Health check (Redis, worker, disco) |
| GET | `/metrics` | Metricas Prometheus |

### Exemplo

```bash
curl -X POST http://localhost:8002/jobs \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

## Architecture Notes

- **Job model** (`VideoDownloadJob`): estende `StandardJob` com `url`, `quality`, `filename`, `file_path`, `file_size`, `current_user_agent`
- **Download engine**: yt-dlp com retry progressivo. Cada job tenta ate 3 user-agents, cada um testado ate 3 vezes (9 tentativas totais), com backoff exponencial ate 60s. User-agents problematicos sao colocados em quarentena por 48h.
- **Pipeline**: `POST /jobs` cria job e enfileira task Celery (`download_video_task`). A task executa sincronamente no worker, atualiza progresso no Redis, e expoe o arquivo via `GET /jobs/{job_id}/download`.
- **Docker Compose**: dois containers — `video-downloader-api` (FastAPI + uvicorn) e `video-downloader-celery` (Celery worker, pool solo, fila `video_downloader_queue`).
