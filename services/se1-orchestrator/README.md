# se1-orchestrator

Orquestrador central do pipeline de transcricao de videos do YouTube. Recebe requisicoes de processamento, coordena a execucao em tres estagios (download de audio, normalizacao, transcricao) delegando a microservicos dedicados (se2-video-downloader, se3-audio-normalization, se4-audio-transcriber) e persiste o progresso dos jobs no Redis. Expoe endpoints REST para iniciar pipelines, consultar status, acompanhar progresso em tempo real via SSE e administrar o servico (cleanup, factory reset).

## Quick Start

```bash
# Subir com Docker (requer .env configurado e rede externa ytcaption-network)
make up

# Ou manualmente:
docker compose up -d

# Verificar saude
make health

# Acompanhar logs
make logs

# Parar
make down
```

A API fica disponivel em `http://localhost:8005` (porta configurvel via `HOST_PORT` no `.env`).

## Endpoints

| Metodo | Caminho                     | Descricao                                                    |
|--------|-----------------------------|--------------------------------------------------------------|
| GET    | `/`                         | Informacoes do servico e lista de endpoints                  |
| POST   | `/process`                  | Inicia pipeline completo (download + normalizacao + transcricao) |
| GET    | `/health`                   | Health check do orquestrador e microservicos dependentes     |
| GET    | `/jobs`                     | Lista jobs recentes com status e progresso                   |
| GET    | `/jobs/{job_id}`            | Status detalhado de um job (inclui estagios e artefatos)     |
| GET    | `/jobs/{job_id}/wait`       | Aguarda (long-polling) ate o job concluir ou falhar          |
| GET    | `/jobs/{job_id}/stream`     | SSE stream com eventos em tempo real                         |
| GET    | `/admin/stats`              | Estatisticas do orquestrador, Redis e configuracoes          |
| POST   | `/admin/cleanup`            | Remove jobs antigos do Redis                                 |
| POST   | `/admin/factory-reset`      | Reset destrutivo: FLUSHDB Redis + limpa logs                 |

### Exemplo: iniciar pipeline

```bash
curl -X POST http://localhost:8005/process \
  -H "Content-Type: application/json" \
  -d '{"youtube_url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","language":"pt"}'
```

Retorna `{ "job_id": "...", "status": "queued", ... }`.

## Architecture Notes

- **FastAPI** com lifespan async que inicializa Redis, orquestrador e valida configuracao na inicializacao
- **Redis** como store unico de estado (jobs salvos como JSON com TTL de 24h)
- **Circuit breaker** em cada MicroserviceClient (estados CLOSED / OPEN / HALF_OPEN) para evitar falhas em cascata
- **Polling adaptativo**: intervalo inicial de 2s, cresce ate 30s, maximo de 300 tentativas
- **SSE streaming** no endpoint `/jobs/{job_id}/stream` para atualizacoes em tempo real via `text/event-stream`
- **Dependency injection** centralizada em `infrastructure/dependency_injection.py`
- Rede Docker externa `ytcaption-network` para comunicacao entre os servicos
