# 🚀 Guia Rápido - YouTube Caption Orchestrator

## ⚡ Iniciar em 5 Minutos

### Pré-requisitos
- ✅ Docker e Docker Compose
- ✅ Redis rodando em `192.168.18.110:6379` (ou configure outro)
- ✅ Microserviços rodando:
  - video-downloader em `http://localhost:8001`
  - audio-normalization em `http://localhost:8002`
  - audio-transcriber em `http://localhost:8003`

### Passo 1: Configure

```bash
cd orchestrator
cp .env.example .env
```

Edite `.env` se necessário:
```bash
VIDEO_DOWNLOADER_URL=http://192.168.18.110:8001
AUDIO_NORMALIZATION_URL=http://192.168.18.110:8002
AUDIO_TRANSCRIBER_URL=http://192.168.18.110:8003
REDIS_URL=redis://192.168.18.110:6379/0
```

### Passo 2: Inicie

**Opção A: Docker (Recomendado)**
```bash
docker-compose up -d
docker-compose logs -f  # Ver logs
```

**Opção B: Local**
```bash
pip install -r requirements.txt
python run.py
```

### Passo 3: Teste

```bash
# Health check
curl http://localhost:8000/health

# Processa vídeo
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "pt"
  }'

# Retorna: {"job_id": "abc123def456", ...}

# Acompanha progresso
curl http://localhost:8000/jobs/abc123def456
```

---

## 📖 Exemplos de Uso

### Python

```python
import requests
import time

# Inicia pipeline
response = requests.post("http://localhost:8000/process", json={
    "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "language": "pt",
    "remove_noise": True,
    "convert_to_mono": True,
    "sample_rate_16k": True
})

job_id = response.json()["job_id"]
print(f"Job criado: {job_id}")

# Polling
while True:
    status = requests.get(f"http://localhost:8000/jobs/{job_id}").json()
    
    print(f"Status: {status['status']} | Progress: {status['overall_progress']}%")
    
    if status['status'] in ['completed', 'failed']:
        break
    
    time.sleep(5)

# Resultado
if status['status'] == 'completed':
    print(f"Transcrição: {status['transcription_text']}")
else:
    print(f"Erro: {status['error_message']}")
```

### JavaScript

```javascript
// Inicia pipeline
const response = await fetch('http://localhost:8000/process', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    youtube_url: 'https://www.youtube.com/watch?v=VIDEO_ID',
    language: 'pt'
  })
});

const { job_id } = await response.json();
console.log('Job criado:', job_id);

// Polling
async function checkStatus() {
  const res = await fetch(`http://localhost:8000/jobs/${job_id}`);
  const data = await res.json();
  
  console.log(`Status: ${data.status} | Progress: ${data.overall_progress}%`);
  
  if (data.status === 'completed') {
    console.log('Transcrição:', data.transcription_text);
    return true;
  } else if (data.status === 'failed') {
    console.error('Erro:', data.error_message);
    return true;
  }
  
  return false;
}

const interval = setInterval(async () => {
  const done = await checkStatus();
  if (done) clearInterval(interval);
}, 5000);
```

---

## 🔍 Monitoramento

### Logs

```bash
# Docker
docker-compose logs -f orchestrator

# Local
tail -f logs/orchestrator.log
```

### Endpoints Úteis

```bash
# Health de todos os serviços
curl http://localhost:8000/health | jq

# Lista jobs recentes
curl http://localhost:8000/jobs?limit=10 | jq

# Estatísticas
curl http://localhost:8000/admin/stats | jq

# Cleanup de jobs antigos
curl -X POST http://localhost:8000/admin/cleanup
```

---

## ❓ Troubleshooting

### Problema: Microserviço não responde

```bash
# Verifique health
curl http://localhost:8000/health | jq .microservices

# Teste microserviço diretamente
curl http://localhost:8001/health  # video-downloader
curl http://localhost:8002/health  # audio-normalization
curl http://localhost:8003/health  # audio-transcriber
```

### Problema: Job travado

```bash
# Veja status detalhado
curl http://localhost:8000/jobs/{job_id} | jq

# Veja qual estágio falhou
curl http://localhost:8000/jobs/{job_id} | jq .stages

# Logs do orchestrator
docker-compose logs orchestrator | grep {job_id}
```

### Problema: Redis desconectado

```bash
# Teste conexão
redis-cli -h 192.168.18.110 -p 6379 ping

# Veja configuração
cat .env | grep REDIS
```

---

## 📊 Dashboard Swagger

Abra no navegador:
```
http://localhost:8000/docs
```

Interface interativa para testar todos os endpoints.

---

## 🎯 Fluxo Típico

```
1. Cliente POST /process → job_id (< 500ms)
2. Background: Download vídeo (1-5 min)
3. Background: Normaliza áudio (30s-2 min)
4. Background: Transcreve (5-15 min dependendo do tamanho)
5. Cliente GET /jobs/{id} → Resultado final
```

**Progresso:**
- 0-33%: Download
- 34-66%: Normalização
- 67-100%: Transcrição

---

## 📝 Parâmetros Disponíveis

### POST /process

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `youtube_url` | string | **required** | URL do YouTube |
| `language` | string | `"auto"` | Idioma ISO 639-1 ou "auto" |
| `remove_noise` | boolean | `true` | Remove ruído de fundo |
| `convert_to_mono` | boolean | `true` | Converte para mono |
| `sample_rate_16k` | boolean | `true` | Sample rate 16kHz |

### Idiomas Suportados

`pt`, `en`, `es`, `fr`, `de`, `it`, `ja`, `ko`, `zh`, `ru`, `ar`, `hi`, ou `auto` (detecção automática)

---

## 🔧 Configuração Avançada

### Timeouts

Edite `.env`:
```bash
VIDEO_DOWNLOADER_TIMEOUT=300      # 5 minutos
AUDIO_NORMALIZATION_TIMEOUT=180   # 3 minutos
AUDIO_TRANSCRIBER_TIMEOUT=600     # 10 minutos
```

### Polling

```bash
POLL_INTERVAL=2          # Intervalo entre consultas (segundos)
MAX_POLL_ATTEMPTS=300    # Máximo de tentativas (10 minutos)
```

### Cache

```bash
CACHE_TTL_HOURS=24       # Jobs expiram em 24h
JOB_TIMEOUT_MINUTES=60   # Job timeout
```

### Workers

```bash
WORKERS=4                # Número de workers (produção)
DEBUG=false              # Debug mode
```

---

## 📦 Deployment Produção

### Docker Swarm

```bash
docker stack deploy -c docker-compose.yml ytcaption
```

### Kubernetes

```yaml
# Criar ConfigMap com .env
kubectl create configmap orchestrator-config --from-env-file=.env

# Deployment
kubectl apply -f k8s/orchestrator-deployment.yaml
```

### Nginx Reverse Proxy

```nginx
upstream orchestrator {
    server localhost:8000;
}

server {
    listen 80;
    server_name api.ytcaption.com;

    location / {
        proxy_pass http://orchestrator;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 🎓 Recursos

- 📖 [README Completo](README.md)
- 📓 [Notebook de Teste](test_orchestrator.ipynb)
- 📄 [Resumo de Melhorias](../RESUMO_MELHORIAS.md)
- 🔍 [Swagger Docs](http://localhost:8000/docs)

---

## ✅ Checklist de Validação

Antes de usar em produção:

- [ ] Redis acessível e com espaço
- [ ] Todos 3 microserviços rodando e saudáveis
- [ ] Timeouts configurados apropriadamente
- [ ] Logs sendo coletados
- [ ] Health checks monitorados
- [ ] Cleanup automático agendado
- [ ] Backup do Redis configurado
- [ ] CORS ajustado para domínios permitidos
- [ ] Rate limiting configurado (se necessário)
- [ ] Alertas configurados para falhas

---

**Pronto para usar! 🚀**

Em caso de dúvidas, consulte o [README completo](README.md) ou abra uma issue.

---

*Guia Rápido - YouTube Caption Orchestrator v1.0.0*
