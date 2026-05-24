# 🎯 Audio Transcriber - Quickstart

**Versão**: 1.0.0  
**Tempo estimado**: 10 minutos

---

## 🚀 Start Rápido

### 1. Setup Inicial

```bash
# Clone e entre no diretório
cd services/se4-audio-transcriber

# Instale dependências
pip install -r requirements.txt

# Configure .env
cp .env.example .env
nano .env  # Ajuste as variáveis
```

### 2. Inicie Redis

```bash
# Docker
docker-compose up -d redis

# Ou local
redis-server
```

### 3. Inicie o Serviço

```bash
# API Server
python run.py

# Em outro terminal, Celery Worker
celery -A app.celery_app worker --loglevel=info
```

### 4. Primeiro Teste

```bash
# Upload um áudio
curl -X POST "http://localhost:8004/transcribe" \
  -F "file=@test_audio.mp3" \
  -F "engine=faster-whisper" \
  -F "language=pt"

# Resposta
{
  "job_id": "abc123",
  "status": "processing",
  "engine": "faster-whisper"
}

# Consulte status
curl "http://localhost:8004/status/abc123"

# Download resultado
curl "http://localhost:8004/result/abc123" > transcription.txt
```

---

## ⚙️ Engines Disponíveis

| Engine | Velocidade | Qualidade | GPU | Uso |
|--------|-----------|-----------|-----|-----|
| **faster-whisper** | ⚡⚡⚡ | ⭐⭐⭐ | Sim | Produção |
| **openai-whisper** | ⚡ | ⭐⭐⭐⭐ | Sim | Alta qualidade |
| **whisperx** | ⚡⚡ | ⭐⭐⭐⭐ | Sim | Word alignment |

**Recomendação**: `faster-whisper` (default) para balanceamento.

---

## 📊 Exemplos de Uso

### Upload Básico

```python
import requests

files = {'file': open('audio.mp3', 'rb')}
data = {'engine': 'faster-whisper', 'language': 'pt'}

response = requests.post('http://localhost:8004/transcribe', 
                        files=files, data=data)
job = response.json()
print(f"Job ID: {job['job_id']}")
```

### Monitorar Progresso

```python
import requests
import time

job_id = "abc123"

while True:
    status = requests.get(f'http://localhost:8004/status/{job_id}').json()
    
    if status['status'] == 'completed':
        print("✅ Completed!")
        break
    elif status['status'] == 'failed':
        print(f"❌ Failed: {status['error']}")
        break
    
    print(f"⏳ Processing... {status.get('progress', 0)}%")
    time.sleep(2)
```

### Download Resultados

```python
import requests

job_id = "abc123"

# Texto puro
txt = requests.get(f'http://localhost:8004/result/{job_id}?format=txt').text

# SRT (legendas)
srt = requests.get(f'http://localhost:8004/result/{job_id}?format=srt').text

# JSON (detalhado)
json_data = requests.get(f'http://localhost:8004/result/{job_id}?format=json').json()
```

---

## 🔧 Configuração

### Variáveis de Ambiente

```bash
# .env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Engine padrão
DEFAULT_ENGINE=faster-whisper

# Modelos (tamanho)
WHISPER_MODEL_SIZE=base  # tiny, base, small, medium, large

# GPU
DEVICE=cuda  # cuda ou cpu
COMPUTE_TYPE=float16  # float16 (GPU) ou int8 (CPU)

# Limites
MAX_FILE_SIZE_MB=500
MAX_AUDIO_DURATION_HOURS=4
MAX_CONCURRENT_JOBS=10
```

### GPU Setup

```bash
# Verifique GPU
nvidia-smi

# Para GPU, use float16
export COMPUTE_TYPE=float16
export DEVICE=cuda

# Para CPU, use int8
export COMPUTE_TYPE=int8
export DEVICE=cpu
```

---

## 🧪 Testes

```bash
# Todos os testes
pytest

# Apenas unitários
pytest tests/unit/

# Apenas infraestrutura
pytest tests/unit/infrastructure/ -v

# Com coverage
pytest --cov=app tests/
```

---

## 📚 Próximos Passos

1. **[API Reference](API_REFERENCE.md)** - Documentação completa da API
2. **[Engines Guide](ENGINES.md)** - Comparação detalhada dos engines
3. **[Resilience](RESILIENCE.md)** - Circuit Breaker e Checkpoints
4. **[Data Pipeline](DATA_PIPELINE.md)** - Fluxo de dados
5. **[Deployment](DEPLOYMENT.md)** - Deploy em produção

---

## ❓ Troubleshooting

### Erro: "CUDA out of memory"

```bash
# Use modelo menor
export WHISPER_MODEL_SIZE=base

# Ou force CPU
export DEVICE=cpu
export COMPUTE_TYPE=int8
```

### Erro: "Redis connection refused"

```bash
# Verifique Redis rodando
redis-cli ping

# Se não rodando
docker-compose up -d redis
# Ou
redis-server
```

### Erro: "No module named 'faster_whisper'"

```bash
# Reinstale dependências
pip install -r requirements.txt

# Ou instale manualmente
pip install faster-whisper
```

---

## 🆘 Suporte

- **Logs**: `data/logs/app/audio-transcriber-{date}.log`
- **Debug**: `data/logs/debug/`
- **Issues**: GitHub Issues
- **Docs**: `/docs/` folder
