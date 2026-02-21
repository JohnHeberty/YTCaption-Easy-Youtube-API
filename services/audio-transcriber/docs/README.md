# 📝 Audio Transcriber - README

**Versão**: 1.0.0  
**Serviço**: Transcrição de áudio usando Whisper

---

## 📋 Visão Geral

Serviço de transcrição de áudio com **alta resiliência** usando 3 engines Whisper:

- **faster-whisper**: Rápido, GPU/CPU (CTranslate2)
- **openai-whisper**: Original OpenAI, alta qualidade
- **whisperx**: Word-level timestamps, alignment

### Características

✅ **3 Engines Whisper** com seleção via API  
✅ **Alta Resiliência** (Circuit Breaker, Checkpoints, Rate Limiting)  
✅ **Pipeline Estruturado** (Raw → Transform → Validate → Approved)  
✅ **Múltiplos Formatos** (TXT, SRT, VTT, JSON)  
✅ **GPU/CPU Support** com fallback automático  
✅ **Async Processing** via Celery  
✅ **Production-Ready** com monitoramento completo

---

## 🚀 Quick Start

```bash
# 1. Setup
cd services/audio-transcriber
pip install -r requirements.txt

# 2. Configure
cp .env.example .env

# 3. Start Redis
docker-compose up -d redis

# 4. Start API
python run.py

# 5. Start Worker (outro terminal)
celery -A app.celery_app worker --loglevel=info

# 6. Test
curl -X POST "http://localhost:8002/transcribe" \
  -F "file=@audio.mp3" \
  -F "engine=faster-whisper"
```

Ver [QUICKSTART.md](docs/QUICKSTART.md) para mais detalhes.

---

## 📂 Estrutura

```
audio-transcriber/
├── app/
│   ├── main.py                    # API Flask
│   ├── celery_app.py              # Celery worker
│   ├── config.py                  # Configuração
│   ├── infrastructure/            # Resiliência
│   │   ├── circuit_breaker.py
│   │   ├── checkpoint_manager.py
│   │   └── distributed_rate_limiter.py
│   ├── services/                  # Engines Whisper
│   │   ├── faster_whisper_manager.py
│   │   ├── openai_whisper_manager.py
│   │   └── whisperx_manager.py
│   └── processor.py               # Orquestração
├── data/                          # Dados (pipeline)
│   ├── raw/                       # Uploads originais
│   ├── transform/                 # Normalizados
│   ├── validate/                  # Validados
│   ├── approved/                  # Transcrições finais
│   └── logs/                      # Logs
├── docs/                          # Documentação
│   ├── QUICKSTART.md
│   ├── API_REFERENCE.md
│   ├── ENGINES.md
│   ├── RESILIENCE.md
│   ├── DATA_PIPELINE.md
│   └── DEPLOYMENT.md
├── tests/                         # Testes (sem Mocks!)
│   ├── unit/
│   │   ├── infrastructure/        # 28 testes passing
│   │   └── test_engine_selection.py
│   └── integration/
└── requirements.txt
```

---

## 🎯 Engines Whisper

| Engine | Velocidade | Qualidade | GPU | Uso |
|--------|-----------|-----------|-----|-----|
| **faster-whisper** | ⚡⚡⚡ | ⭐⭐⭐ | Sim | Produção (default) |
| **openai-whisper** | ⚡ | ⭐⭐⭐⭐ | Sim | Máxima qualidade |
| **whisperx** | ⚡⚡ | ⭐⭐⭐⭐ | Sim | Word timestamps |

### Seleção via API

```bash
# faster-whisper (default)
curl -F "file=@audio.mp3" -F "engine=faster-whisper" /transcribe

# openai-whisper
curl -F "file=@audio.mp3" -F "engine=openai-whisper" /transcribe

# whisperx
curl -F "file=@audio.mp3" -F "engine=whisperx" /transcribe
```

Ver [ENGINES.md](docs/ENGINES.md) para comparação detalhada.

---

## 🛡️ Alta Resiliência

### 1. Circuit Breaker

Protege contra falhas em cascata:

```
CLOSED → OPEN → HALF_OPEN → CLOSED
```

### 2. Checkpoint Manager

Salva progresso granular para recuperação:

```
[████──────] 40% ❌ Falha
↓
[████──────] 40% ✅ Recupera do checkpoint
```

### 3. Distributed Rate Limiter

Controle de carga via Redis Sliding Window:

```
100 requests / hora por endpoint
```

Ver [RESILIENCE.md](docs/RESILIENCE.md) para detalhes.

---

## 📊 API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/transcribe` | Transcrever áudio |
| GET | `/status/{job_id}` | Consultar status |
| GET | `/result/{job_id}` | Baixar resultado |
| DELETE | `/job/{job_id}` | Cancelar job |
| GET | `/health` | Health check |

### Exemplo Completo

```python
import requests
import time

# 1. Upload
files = {'file': open('audio.mp3', 'rb')}
data = {'engine': 'faster-whisper', 'language': 'pt'}
response = requests.post('http://localhost:8002/transcribe', 
                        files=files, data=data)
job = response.json()

# 2. Aguardar
while True:
    status = requests.get(f"http://localhost:8002/status/{job['job_id']}").json()
    if status['status'] == 'completed':
        break
    time.sleep(2)

# 3. Resultado
txt = requests.get(f"http://localhost:8002/result/{job['job_id']}?format=txt").text
print(txt)
```

Ver [API_REFERENCE.md](docs/API_REFERENCE.md) para documentação completa.

---

## 🔄 Data Pipeline

```
📥 Upload (raw/)
   ↓
🔄 Transform (normalize 16kHz)
   ↓
✅ Validate (quality checks)
   ↓
🎯 Whisper Transcription
   ↓
✅ Output (TXT, SRT, VTT, JSON)
```

Ver [DATA_PIPELINE.md](docs/DATA_PIPELINE.md) para fluxo detalhado.

---

## 🧪 Testes

```bash
# Todos os testes
pytest

# Apenas infraestrutura (28 testes)
pytest tests/unit/infrastructure/ -v

# Com coverage
pytest --cov=app tests/
```

### Status Atual

✅ **28/28** testes de infraestrutura passing  
✅ **Sem Mocks** (Stubs apenas)  
✅ Circuit Breaker: 14 testes  
✅ Checkpoint Manager: 14 testes  

---

## ⚙️ Configuração

### .env

```bash
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Whisper
DEFAULT_ENGINE=faster-whisper
WHISPER_MODEL_SIZE=base  # tiny, base, small, medium, large
DEVICE=cuda  # cuda ou cpu
COMPUTE_TYPE=float16  # float16 (GPU) ou int8 (CPU)

# Limites
MAX_FILE_SIZE_MB=500
MAX_AUDIO_DURATION_HOURS=4
MAX_CONCURRENT_JOBS=10

# Rate Limiting
RATE_LIMIT_TRANSCRIBE=100  # req/hora
RATE_LIMIT_STATUS=1000
RATE_LIMIT_RESULT=500
```

---

## 🐳 Docker

```bash
# Build
docker-compose build

# Start
docker-compose up -d

# Logs
docker-compose logs -f audio-transcriber

# Stop
docker-compose down
```

Ver [DEPLOYMENT.md](docs/DEPLOYMENT.md) para produção.

---

## 📈 Monitoramento

### Métricas

- Prometheus: `/metrics`
- Health: `/health`
- Logs: `data/logs/app/`

### Alertas

```yaml
alerts:
  - circuit_breaker_open: "Circuit breaker opened"
  - high_error_rate: "Error rate > 5%"
  - slow_processing: "Processing time > 60s"
  - storage_full: "Storage > 80%"
```

---

## 📚 Documentação

| Documento | Descrição |
|-----------|-----------|
| [QUICKSTART.md](docs/QUICKSTART.md) | Início rápido (10 min) |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | API completa |
| [ENGINES.md](docs/ENGINES.md) | Comparação engines |
| [RESILIENCE.md](docs/RESILIENCE.md) | Circuit Breaker, Checkpoints |
| [DATA_PIPELINE.md](docs/DATA_PIPELINE.md) | Fluxo de dados |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Deploy produção |
| [TESTING.md](docs/TESTING.md) | Guia de testes |

---

## 🤝 Contribuindo

1. Fork o repo
2. Crie branch (`git checkout -b feature/amazing`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Abra Pull Request

---

## 📄 Licença

MIT License - ver LICENSE file

---

## 🆘 Suporte

- **Issues**: GitHub Issues
- **Logs**: `data/logs/app/audio-transcriber-{date}.log`
- **Debug**: `data/logs/debug/`
- **Docs**: `/docs/` folder
