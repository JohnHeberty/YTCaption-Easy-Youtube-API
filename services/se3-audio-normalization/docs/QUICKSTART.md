# Quickstart — SE3 Audio Normalization

**Tempo estimado:** 5 minutos

---

## 1. Setup

```bash
cd services/se3-audio-normalization
pip install -r requirements.txt
cp .env.example .env
```

`.env` mínimo:
```
APP_NAME=Audio Normalization Service
REDIS_URL=redis://localhost:6379/3
API_KEY=your-api-key
PORT=8003
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
curl http://localhost:8003/health

# Normalizar áudio
curl -X POST "http://localhost:8003/jobs" \
  -H "X-API-Key: your-api-key" \
  -F "file=@audio.mp3" \
  -F "remove_noise=true" \
  -F "convert_to_mono=true"

# Verificar status
curl "http://localhost:8003/jobs/an_abc123" -H "X-API-Key: your-api-key"

# Download
curl "http://localhost:8003/jobs/an_abc123/download" -H "X-API-Key: your-api-key" -o normalized.webm
```

---

## 4. Endpoints Rápidos

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `POST` | `/jobs` | Criar job |
| `GET` | `/jobs` | Listar jobs |
| `GET` | `/jobs/{id}` | Status do job |
| `GET` | `/jobs/{id}/download` | Download áudio |
| `DELETE` | `/jobs/{id}` | Deletar job |
| `POST` | `/jobs/{id}/heartbeat` | Heartbeat |
| `GET` | `/admin/stats` | Estatísticas |
| `GET` | `/admin/queue` | Fila |
| `POST` | `/admin/cleanup` | Cleanup |
| `GET` | `/metrics` | Prometheus |
