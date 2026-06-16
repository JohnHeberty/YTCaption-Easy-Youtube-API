# Image Generation Service (se8)

SDXL image generation service powered by Fooocus API. Runs on port 8008.

## Architecture

```
[Client :8008] --> [se8 API (proxy)] --> [Fooocus API :8888 (internal, GPU)]
                                              |
                                          [Fooocus Worker]
```

- **image-generation-api** (port 8008) — FastAPI proxy, no GPU needed
- **fooocus-api** (port 8888, internal) — Fooocus SDXL on GPU
- **celery-worker** — Async image generation via Redis DB=8

## Quick Start

```bash
# Build and start
make build
make up

# Check health
make health

# View logs
make logs

# Stop
make down
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/generation/text-to-image` | Text to image |
| POST | `/v1/generation/image-upscale-vary` | Upscale or vary image |
| POST | `/v1/generation/image-inpaint-outpaint` | Inpaint or outpaint |
| POST | `/v1/generation/image-prompt` | Image prompt |
| GET | `/v1/generation/{job_id}` | Query async job |
| DELETE | `/v1/generation/{job_id}` | Stop job |
| GET | `/health` | Health check |
| GET | `/health/deep` | Deep health check |

## Environment Variables

See `.env.example` for all configuration options.

## Local Development (no Docker)

```bash
make dev
```

## Production

```bash
cd docker && docker compose -f docker-compose.prod.yml up -d
```
