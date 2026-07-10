# Quickstart — SE7 Audio Generation (TTS)

**Tempo estimado:** 5 minutos

---

## 1. Setup

```bash
cd services/se7-audio-generation
pip install -r requirements.txt
cp .env.example .env
```

`.env` mínimo:
```
APP_NAME=Audio Generation Service
REDIS_URL=redis://localhost:6379/7
API_KEY=your-api-key
PORT=8007
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
curl http://localhost:8007/health

# Gerar áudio
curl -X POST "http://localhost:8007/jobs" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Olá, isso é um teste de geração de áudio.", "voice_id": "default"}'

# Verificar status
curl "http://localhost:8007/jobs/ag_abc123" -H "X-API-Key: your-api-key"

# Download
curl "http://localhost:8007/jobs/ag_abc123/download" -H "X-API-Key: your-api-key" -o audio.wav
```

---

## 4. Endpoints Rápidos

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `POST` | `/jobs` | Gerar áudio (TTS) |
| `GET` | `/jobs` | Listar jobs |
| `GET` | `/jobs/{id}` | Status do job |
| `GET` | `/jobs/{id}/download` | Download áudio |
| `DELETE` | `/jobs/{id}` | Deletar job |
| `GET` | `/voices` | Listar vozes disponíveis |
| `POST` | `/voices` | Criar voice profile |
| `GET` | `/voices/{id}` | Info da voice |
| `DELETE` | `/voices/{id}` | Deletar voice |
| `GET` | `/admin/stats` | Estatísticas |
| `POST` | `/admin/cleanup` | Cleanup |
| `GET` | `/admin/models/status` | Status do modelo |
