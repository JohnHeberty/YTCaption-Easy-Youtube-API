# Quickstart — SE6 YouTube Search

**Tempo estimado:** 5 minutos

---

## 1. Setup

```bash
cd services/se6-youtube-search
pip install -r requirements.txt
cp .env.example .env
```

`.env` mínimo:
```
APP_NAME=YouTube Search Service
REDIS_URL=redis://localhost:6379/6
API_KEY=your-api-key
PORT=8006
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
curl http://localhost:8006/health

# Buscar vídeos
curl -X POST "http://localhost:8006/search/videos?query=python+tutorial" \
  -H "X-API-Key: your-api-key"

# Aguardar conclusão
curl "http://localhost:8006/jobs/ys_abc123/wait?timeout=120" \
  -H "X-API-Key: your-api-key"

# Download resultados
curl "http://localhost:8006/jobs/ys_abc123/download" \
  -H "X-API-Key: your-api-key" -o results.json
```

---

## 4. Endpoints Rápidos

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `POST` | `/search/video-info` | Info vídeo |
| `POST` | `/search/channel-info` | Info canal |
| `POST` | `/search/playlist-info` | Info playlist |
| `POST` | `/search/videos` | Buscar vídeos |
| `POST` | `/search/related-videos` | Relacionados |
| `POST` | `/search/shorts` | Buscar Shorts |
| `GET` | `/jobs/{id}` | Status do job |
| `GET` | `/jobs/` | Listar jobs |
| `DELETE` | `/jobs/{id}` | Deletar job |
| `GET` | `/jobs/{id}/download` | Download JSON |
| `GET` | `/jobs/{id}/wait` | Long-poll |
| `POST` | `/admin/cleanup` | Cleanup |
| `GET` | `/admin/stats` | Estatísticas |
| `GET` | `/admin/queue` | Fila |
| `GET` | `/admin/metrics` | Prometheus |
