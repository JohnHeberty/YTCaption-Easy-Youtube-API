# Quickstart — SE9 Make Video (Image-to-Video)

**Tempo estimado:** 5 minutos

---

## 1. Setup

```bash
cd services/se9-make-video-img
pip install -r requirements.txt
cp .env.example .env
```

`.env` mínimo:
```
APP_NAME=Make Video Image Service
REDIS_URL=redis://localhost:6379/9
API_KEY=your-api-key
PORT=8009
SE7_URL=http://localhost:8007
SE8_URL=http://localhost:8008
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
curl http://localhost:8009/health

# Criar vídeo
curl -X POST "http://localhost:8009/jobs" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "hook": "Era uma vez...",
    "scenes": [
      {"image_url": "https://example.com/img1.png", "duration": 5},
      {"image_url": "https://example.com/img2.png", "duration": 5}
    ],
    "narration": [{"text": "Era uma vez uma história incrível."}]
  }'

# Verificar status
curl "http://localhost:8009/jobs/vid_abc123" -H "X-API-Key: your-api-key"

# Download
curl "http://localhost:8009/jobs/vid_abc123/download" -H "X-API-Key: your-api-key" -o video.mp4
```

---

## 4. Endpoints Rápidos

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `POST` | `/jobs` | Criar vídeo |
| `GET` | `/jobs` | Listar jobs |
| `GET` | `/jobs/{id}` | Status do job |
| `GET` | `/jobs/{id}/download` | Download vídeo |
| `DELETE` | `/jobs/{id}` | Deletar job |
| `GET` | `/config` | Configuração atual |
| `GET` | `/transitions` | Transições disponíveis |
| `GET` | `/camera-movements` | Movimentos de câmera |
| `GET` | `/voices` | Vozes disponíveis (SE7) |
| `GET` | `/admin/stats` | Estatísticas |
| `POST` | `/admin/cleanup` | Cleanup |
