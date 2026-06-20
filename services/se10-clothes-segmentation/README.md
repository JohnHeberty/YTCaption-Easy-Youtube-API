# SE10 -- Clothes Segmentation

> Segmentacao e deteccao de roupas com GroundingDINO + SAM-2

## Quick Start

- **Porta:** 8010
- **API Key:** `se10-test-key-2026`
- **GPU:** NVIDIA (recomendado, funciona em CPU degraded mode)

```bash
# Docker
cd services/se10-clothes-segmentation
make up

# Local
python run.py
```

## API Summary

| Metodo | Rota | Descricao |
|--------|------|-----------|
| GET | `/` | Info do servico |
| GET | `/health` | Health check |
| GET | `/health/deep` | Health check profundo (checkpoints) |
| GET | `/ping` | Ping |
| POST | `/v1/segment` | Segmentar roupas em imagem |
| GET | `/jobs` | Listar jobs |
| GET | `/jobs/stats` | Estatisticas |
| GET | `/jobs/{job_id}` | Status do job |
| DELETE | `/jobs/{job_id}` | Deletar job |

## Configuracao (.env)

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `SE10_API_KEY` | `se10-test-key-2026` | API key |
| `CHECKPOINT_DIR` | `./checkpoints` | Diretorio dos checkpoints |
| `WORKER_THREADS` | `2` | Threads para processamento |

## Arquitetura

```
POST /v1/segment (imagem) → GroundingDINO (deteccao) → SAM-2 (segmentacao)
  ├── Detecta: hat, shirt, pants, dress, shoes, etc.
  ├── Output: mascara binaria + bounding box + scores
  └── 15 classes de roupas suportadas
```

- GroundingDINO: deteccao zero-shot por texto
- SAM-2: segmentacao pixel-level
- Checkpoints: groundingdino_swint_ogc.pth + sam2_hiera_tiny.pt
- Funciona em degraded mode sem checkpoints (API disponivel, segmentacao desabilitada)

## Docs

- [API Reference](./docs/API_REFERENCE.md) — Todas as rotas com request/response

## Desenvolvimento

```bash
# Testes
make test

# Health check
curl http://localhost:8010/health
```

## Dependencias

- Redis (192.168.1.110:6379/10)
- NVIDIA GPU (recomendado)
- Checkpoints: groundingdino_swint_ogc.pth, sam2_hiera_tiny.pt
