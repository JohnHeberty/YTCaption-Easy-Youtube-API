# SE7 -- Audio Generation

> Geracao de audio TTS com Chatterbox Multilingual PT-BR (voice cloning)

## Quick Start

- **Porta:** 8007
- **API Key:** `se7-test-key-2026`
- **Redis DB:** 7
- **GPU:** NVIDIA CUDA (recomendado)

```bash
# Docker (GPU)
cd services/se7-audio-generation
make up

# Docker (CPU)
make up-cpu

# Local
python run.py
```

## API Summary

| Metodo | Rota | Descricao |
|--------|------|-----------|
| GET | `/` | Info do servico |
| GET | `/health` | Health check (redis, modelo, disco) |
| POST | `/jobs` | Criar job TTS (form-data: text, voice_id) |
| GET | `/jobs` | Listar jobs |
| GET | `/jobs/{job_id}` | Consultar status |
| GET | `/jobs/{job_id}/download` | Download WAV |
| DELETE | `/jobs/{job_id}` | Deletar job |
| POST | `/voices` | Criar voice profile (upload audio) |
| GET | `/voices` | Listar voices |
| GET | `/voices/{voice_id}` | Detalhe voice |
| GET | `/voices/{voice_id}/sample` | Download sample WAV |
| DELETE | `/voices/{voice_id}` | Deletar voice |
| GET | `/admin/stats` | Estatisticas |
| POST | `/admin/cleanup` | Limpar jobs expirados |

## Configuracao (.env)

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `DEVICE` | `auto` | `auto`=GPU se disponivel, `cpu`, `cuda` |
| `DEFAULT_EXAGGERATION` | `0.5` | Expressividade (0.0-2.0) |
| `DEFAULT_CFG_WEIGHT` | `0.5` | Peso CFG (0.0-1.0) |
| `DEFAULT_TEMPERATURE` | `0.8` | Temperatura (0.0-2.0) |
| `CHUNK_SIZE` | `1000` | Max chars por chunk TTS |
| `MODEL_NAME` | `ResembleAI/Chatterbox-Multilingual-pt-br` | Modelo |

## Arquitetura

```
POST /jobs → Celery Worker → ChatterboxModelManager
  ├── text chunking (max 1000 chars)
  ├── model.generate(text, "pt", audio_prompt)
  └── WAV output (24kHz mono)
```

- Celery worker: concurrency=1, pool=solo (GPU-bound)
- Modelo carrega sob demanda no primeiro job
- Voice profiles: builtin_feminino.wav, builtin_masculino.wav
- Parametros identicos ao Chatterbox oficial (0.5/0.5/0.8)

## Docs

- [Architecture](./docs/ARCHITECTURE.md) — Arquitetura detalhada do Chatterbox
- [Guide](./docs/GUIDE.md) — Guia de uso e gravacao de voices

## Desenvolvimento

```bash
# Testes
make test

# Build Docker GPU
make build

# Build Docker CPU
make build-cpu

# Health check
curl http://localhost:8007/health
```

## Dependencias

- Redis (192.168.1.110:6379/7)
- NVIDIA GPU (recomendado) ou CPU
- HuggingFace (download do modelo na primeira execucao)
