# Quickstart — SE2 Video Downloader

**Tempo estimado:** 5 minutos

---

## 1. Setup

```bash
cd services/se2-video-downloader
pip install -r requirements.txt
cp .env.example .env
```

`.env` mínimo:
```
APP_NAME=Video Downloader Service
REDIS_URL=redis://localhost:6379/2
API_KEY=your-api-key
PORT=8002
```

---

## 2. Iniciar Serviço

```bash
python run.py
```

---

## 3. Primeiro Teste

```bash
# Health check
curl http://localhost:8002/health

# Criar download
curl -X POST "http://localhost:8002/jobs" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "quality": "720p"}'

# Verificar status
curl "http://localhost:8002/jobs/vd_abc123" -H "X-API-Key: your-api-key"

# Download
curl "http://localhost:8002/jobs/vd_abc123/download" -H "X-API-Key: your-api-key" -o video.mp4
```

---

## 4. Endpoints Rápidos

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `POST` | `/jobs` | Criar download |
| `GET` | `/jobs` | Listar jobs |
| `GET` | `/jobs/{id}` | Status do job |
| `GET` | `/jobs/{id}/download` | Download vídeo |
| `DELETE` | `/jobs/{id}` | Deletar job |
| `GET` | `/jobs/orphaned` | Jobs órfãos |
| `POST` | `/jobs/orphaned/cleanup` | Limpar órfãos |
| `GET` | `/admin/stats` | Estatísticas |
| `POST` | `/admin/cleanup` | Cleanup |
| `POST` | `/admin/fix-stuck-jobs` | Fix stuck jobs |
| `GET` | `/metrics` | Prometheus |
| `GET` | `/user-agents/stats` | UA stats |
