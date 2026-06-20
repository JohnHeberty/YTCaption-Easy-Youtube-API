# SE9 -- Make Video IMG

> Geracao de video a partir de imagens geradas (SE8) + narração (SE7) com efeito Ken Burns

## Quick Start

- **Porta:** 8009
- **API Key:** `se9-test-key-2026`
- **Redis DB:** 9

```bash
# Docker
cd services/se9-make-video-img
docker compose -f docker/docker-compose.yml --env-file .env up -d --build

# Local
python run.py
```

## API Summary

| Metodo | Rota | Descricao |
|--------|------|-----------|
| GET | `/` | Info do servico |
| GET | `/health` | Health check (SE7, SE8, disco, ffmpeg) |
| GET | `/ping` | Ping simples |
| POST | `/jobs` | Criar job de video |
| GET | `/jobs` | Listar jobs |
| GET | `/jobs/{job_id}` | Consultar status do job |
| DELETE | `/jobs/{job_id}` | Deletar job e arquivos |
| GET | `/download/{job_id}` | Download do video MP4 |
| GET | `/admin/stats` | Estatisticas do sistema |
| POST | `/admin/cleanup` | Limpar jobs falhos |

## Configuracao (.env)

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `SE7_URL` | `http://localhost:8007` | URL do SE7 (audio) |
| `SE8_URL` | `http://localhost:8008` | URL do SE8 (imagens) |
| `DEFAULT_VOICE_ID` | `builtin_feminino` | Voz padrao |
| `DEFAULT_ASPECT_RATIO` | `9:16` | Proporcao do video |
| `DEFAULT_ZOOM_SPEED` | `0.004` | Velocidade do Ken Burns |
| `DEFAULT_CROSSFADE_DURATION` | `0.3` | Duracao do crossfade |
| `TTS_EXAGGERATION` | `0.5` | Exaggeration Chatterbox |
| `TTS_CFG_WEIGHT` | `0.5` | CFG weight Chatterbox |
| `TTS_TEMPERATURE` | `0.8` | Temperature Chatterbox |

## Arquitetura

```
n8n → POST /jobs → SE9 (orquestra)
  ├── SE7 (audio)   → narração WAV
  ├── SE8 (imagens) → cenas PNG
  └── FFmpeg         → video final MP4 (Ken Burns + crossfade)
```

- Worker in-memory (thread, NAO Celery) — processa 1 job por vez
- Ken Burns: 2 estilos (zoom_in, zoom_out), velocidade automatica por cena
- Crossfade: xfade para <=8 segmentos, concat_batched para >8
- Titulo: card escuro de 0.5s com fade-in
- Audio: detecta SR/channels antes de gerar silencio

## Docs

- [Architecture](./docs/ARCHITECTURE.md) — Arquitetura detalhada, decisoes, pipeline completo
- [API Reference](./docs/API_REFERENCE.md) — Todas as rotas com request/response

## Desenvolvimento

```bash
# Testes unitarios
python -m pytest tests/unit/ -v

# Teste E2E (requer SE7+SE8 online)
python -m pytest tests/e2e/ -v -s

# Build Docker
docker compose -f docker/docker-compose.yml --env-file .env up -d --build
```

## Dependencias

- SE7 (porta 8007) — Audio Generation (Chatterbox TTS)
- SE8 (porta 8008) — Image Generation (Stable Diffusion)
- Redis (192.168.1.110:6379/9)
- FFmpeg
