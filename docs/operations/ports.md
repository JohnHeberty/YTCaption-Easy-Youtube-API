# Portas e Servicos

Este documento concentra a referencia estavel de portas e endpoints de health dos servicos principais.

## Servicos principais

| Servico | Porta principal | Health endpoint |
|---------|-----------------|-----------------|
| orchestrator | 8000/8080 | `/health` |
| youtube-search | 8001 | `/health` |
| video-downloader | 8002 | `/health` |
| audio-normalization | 8003 | `/health` |
| audio-transcriber | 8004 | `/health` |
| make-video | 8005 | `/health` |

## Observacoes

- Esta pagina registra apenas a referencia estavel de portas.
- Status runtime de containers e workers nao deve ser mantido aqui, porque envelhece rapido.
- Para verificacao operacional atual, use `make status`, `docker ps` ou os logs de servico.

## Comandos uteis

```bash
make status
make logs-youtube-search
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```