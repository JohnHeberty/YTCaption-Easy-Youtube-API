# Quickstart — SE8 Image Generation

**Tempo estimado:** 5 minutos

---

## 1. Setup

```bash
cd services/se8-image-generation
pip install -r requirements.txt
cp .env.example .env
```

`.env` mínimo:
```
APP_NAME=Image Generation Service
REDIS_URL=redis://localhost:6379/8
API_KEY=se8-test-key-2026
PORT=8008
```

**⚠️ Requer GPU NVIDIA** para geração de imagens (SDXL/Fooocus).

---

## 2. Iniciar Serviço

```bash
python run.py
```

---

## 3. Primeiro Teste

```bash
# Health check
curl http://localhost:8008/health

# Gerar imagem (sync)
curl -X POST "http://localhost:8008/v1/generations" \
  -H "X-API-Key: se8-test-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a beautiful sunset over mountains", "style": "realistic"}'

# Gerar imagem (async)
curl -X POST "http://localhost:8008/v1/generations/async" \
  -H "X-API-Key: se8-test-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a beautiful sunset", "style": "realistic"}'

# Verificar status
curl "http://localhost:8008/v1/jobs/img_abc123" -H "X-API-Key: se8-test-key-2026"
```

---

## 4. Endpoints Rápidos

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `GET` | `/health/deep` | Deep health (GPU) |
| `GET` | `/ping` | Ping |
| `POST` | `/v1/generations` | Gerar imagem (sync) |
| `POST` | `/v1/generations/async` | Gerar imagem (async) |
| `GET` | `/v1/jobs/{id}` | Status do job async |
| `GET` | `/v1/engines/styles` | Estilos disponíveis |
| `POST` | `/v1/images/upscale` | Upscale imagem |
| `POST` | `/v1/images/inpaint` | Inpaint imagem |
| `POST` | `/v1/images/face-swap` | Face swap |
| `GET` | `/v1/models` | Modelos disponíveis |
| `GET` | `/v1/outputs/{filename}` | Servir arquivo output |
| `GET` | `/admin/stats` | Estatísticas |
| `POST` | `/admin/cleanup` | Cleanup |
| `GET` | `/admin/vram` | Status VRAM |
| `POST` | `/admin/process/restart` | Reiniciar processo |
