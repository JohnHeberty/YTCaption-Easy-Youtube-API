# Quickstart — SE1 Orchestrator

**Tempo estimado:** 5 minutos

---

## 1. Setup

```bash
cd services/se1-orchestrator
pip install -r requirements.txt
cp .env.example .env
```

`.env` mínimo:
```
APP_NAME=youtube-caption-orchestrator
REDIS_URL=redis://localhost:6379/1
API_KEY=your-api-key
VIDEO_DOWNLOADER_URL=http://localhost:8002
AUDIO_NORMALIZATION_URL=http://localhost:8003
AUDIO_TRANSCRIBER_URL=http://localhost:8004
```

---

## 2. Iniciar Dependências

```bash
# Redis
docker-compose up -d redis

# SE2 (Video Downloader)
cd ../se2-video-downloader && python run.py &

# SE3 (Audio Normalization)
cd ../se3-audio-normalization && python run.py &

# SE4 (Audio Transcriber)
cd ../se4-audio-transcriber && python run.py &
```

---

## 3. Iniciar Orchestrator

```bash
cd services/se1-orchestrator
python run.py
```

---

## 4. Primeiro Teste

```bash
# Health check
curl http://localhost:8001/health

# Iniciar pipeline
curl -X POST "http://localhost:8001/process" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# Verificar status
curl "http://localhost:8001/jobs/{job_id}" -H "X-API-Key: your-api-key"
```

---

## 5. Endpoints Rápidos

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `POST` | `/process` | Iniciar pipeline |
| `GET` | `/jobs` | Listar jobs |
| `GET` | `/jobs/{id}` | Status do job |
| `GET` | `/jobs/{id}/wait` | Aguardar conclusão |
| `GET` | `/jobs/{id}/stream` | SSE progresso |
| `GET` | `/admin/stats` | Estatísticas |
| `POST` | `/admin/cleanup` | Cleanup |
| `POST` | `/admin/factory-reset` | Factory reset |
