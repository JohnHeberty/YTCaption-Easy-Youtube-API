# Quickstart — SE10 Clothes Segmentation

**Tempo estimado:** 5 minutos

---

## 1. Setup

```bash
cd services/se10-clothes-segmentation
pip install -r requirements.txt
cp .env.example .env
```

`.env` mínimo:
```
APP_NAME=Clothes Segmentation Service
REDIS_URL=redis://localhost:6379/10
API_KEY=se10-test-key-2026
PORT=8010
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
curl http://localhost:8010/health

# Segmentar roupas
curl -X POST "http://localhost:8010/jobs" \
  -H "X-API-Key: se10-test-key-2026" \
  -F "file=@imagem.png" \
  -F "classes=shirt,pants,dress"

# Verificar status
curl "http://localhost:8010/jobs/seg_abc123" -H "X-API-Key: se10-test-key-2026"

# Download máscara
curl "http://localhost:8010/jobs/seg_abc123/download" -H "X-API-Key: se10-test-key-2026" -o mask.png
```

---

## 4. Endpoints Rápidos

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `GET` | `/health/deep` | Deep health |
| `GET` | `/ping` | Ping |
| `POST` | `/jobs` | Segmentar roupas |
| `GET` | `/jobs` | Listar jobs |
| `GET` | `/jobs/{id}` | Status do job |
| `DELETE` | `/jobs/{id}` | Deletar job |
| `GET` | `/admin/stats` | Estatísticas |
| `POST` | `/admin/cleanup` | Cleanup |
