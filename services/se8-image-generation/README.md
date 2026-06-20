# SE8 -- Image Generation

> Geracao de imagens com Stable Diffusion XL (Fooocus-based)

## Quick Start

- **Porta:** 8008
- **API Key:** `se8-test-key-2026`
- **Redis DB:** 8
- **GPU:** NVIDIA (obrigatorio)

```bash
# Docker (GPU)
cd services/se8-image-generation
make up

# Local
python run.py
```

## API Summary

| Metodo | Rota | Descricao |
|--------|------|-----------|
| GET | `/` | Info do servico |
| GET | `/health` | Health check |
| GET | `/health/deep` | Health check profundo |
| GET | `/ping` | Ping |
| POST | `/v1/generation/text-to-image` | Gerar imagem (sync) |
| GET | `/v1/generation/query-job` | Consultar job de geracao |
| GET | `/v1/generation/job-queue` | Fila de jobs |
| GET | `/v1/engines/all-models` | Listar modelos |
| GET | `/v1/engines/styles` | Estilos disponiveis |
| GET | `/v1/engines/cleanup` | Limpar VRAM |
| GET | `/files/{date}/{filename}` | Download de arquivo |
| GET | `/admin/stats` | Estatisticas |
| POST | `/admin/cleanup` | Limpar jobs |

## Configuracao (.env)

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `GPU_MODE` | `lazy` | `lazy`=carrega sob demanda, `eager`=carrega no startup |
| `DEFAULT_WIDTH` | `1024` | Largura da imagem |
| `DEFAULT_HEIGHT` | `1024` | Altura da imagem |
| `DEFAULT_STEPS` | `30` | Passos de inferencia |
| `DEFAULT_PERFORMANCE` | `Quality` | `Speed` ou `Quality` |

## Arquitetura

```
POST /v1/generation/text-to-image → SDXL inference (GPU)
  ├── Fooocus-based pipeline
  ├── LoRA, ControlNet, IP-Adapter
  └── Output: PNG file
```

- Modo sincrono (resposta direta, sem polling)
- GPU-bound: 1 inference por vez
- Modelo padrao: juggernautXL_v8Rundiffusion

## Docs

- [Architecture](./docs/ARCHITECTURE.md) — Arquitetura detalhada
- [Validacao](./VALID.md) — Relatorio de validacao E2E

## Desenvolvimento

```bash
# Health check
curl http://localhost:8008/health

# Gerar imagem
curl -X POST http://localhost:8008/v1/generation/text-to-image \
  -H "X-API-Key: se8-test-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a sunset over mountains", "width": 1024, "height": 1024}'
```

## Dependencias

- Redis (192.168.1.110:6379/8)
- NVIDIA GPU (obrigatorio)
