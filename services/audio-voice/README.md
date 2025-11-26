# 🎙️ Audio Voice Service

Microserviço de **dublagem de texto em áudio** e **clonagem de vozes** usando **F5-TTS** (produção), integrado ao monorepo YTCaption-Easy-Youtube-API.

> ✅ Sistema 100% validado e aprovado para produção  
> 🎯 Motor TTS: **F5-TTS v1 Base** (SWivid/F5-TTS)  
> 🔊 Clonagem: Automática via Whisper + referência de áudio

## 🎯 Funcionalidades

### 1. Dublagem de Texto (Text-to-Speech)
- Converter texto em áudio dublado
- Suporte a múltiplos idiomas
- Vozes genéricas pré-configuradas (female_generic, male_deep, etc.)
- Vozes personalizadas clonadas

### 2. Clonagem de Voz (Voice Cloning)
- Criar perfis de voz a partir de amostras de áudio
- Armazenar e gerenciar perfis de voz
- Usar vozes clonadas na dublagem
- Cache inteligente (30 dias)

## 📋 Pré-requisitos

- Python 3.10+
- Redis 7+
- FFmpeg
- Docker e Docker Compose (opcional)
- GPU NVIDIA (opcional, recomendado para produção)

## 🚀 Quick Start

### 1. Instalação

```bash
# Clone o projeto (se ainda não tiver)
cd services/audio-voice

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt -c constraints.txt

# Configure variáveis de ambiente
cp .env.example .env
# Edite .env conforme necessário
```

### 2. Modelos F5-TTS (Download Automático)

Os modelos F5-TTS (~500MB) são baixados automaticamente na primeira execução:
- Modelo: `F5TTS_v1_Base` 
- Cache: `./models/f5tts/`
- Whisper (transcrição): `openai/whisper-base` (~140MB)

**Não é necessário download manual!**

### 3. Iniciar Serviço

```bash
# Opção 1: Docker Compose (RECOMENDADO)
docker-compose up -d

# Verificar status
docker-compose ps

# Ver logs
docker logs audio-voice-api -f

# Opção 2: Local (desenvolvimento)
# Terminal 1: Redis
redis-server

# Terminal 2: FastAPI
python run.py

# Terminal 3: Celery Worker
celery -A app.celery_config worker --loglevel=info --concurrency=1 --pool=solo -Q audio_voice_queue
```

### 4. Criar Presets de Voz (Primeira Vez)

```bash
# Cria 4 vozes base (female_generic, male_deep, female_pt, male_pt)
docker exec audio-voice-api python /app/scripts/create_voice_presets.py

# Ou localmente:
python scripts/create_voice_presets.py
```

### 5. Testar

```bash
# Health check
curl http://localhost:8005/

# Síntese básica
curl -X POST "http://localhost:8005/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Olá, teste do F5-TTS",
    "source_language": "pt"
  }' | jq .

# Verificar job
curl http://localhost:8005/jobs/{JOB_ID} | jq .

# Download áudio
curl http://localhost:8005/jobs/{JOB_ID}/download -o output.wav
```

## 📖 Uso

### Dublagem com Voz Preset

```bash
curl -X POST "http://localhost:8005/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Olá, este é um teste de dublagem com F5-TTS",
    "source_language": "pt",
    "voice_preset": "female_pt"
  }' | jq .

# Response
{
  "id": "job_abc123",
  "status": "queued",
  "voice_preset": "female_pt",
  "audio_url": null,
  ...
}

# Verificar status (polling a cada 5s)
curl http://localhost:8005/jobs/job_abc123 | jq '{id, status, duration, output_file}'

# Download quando status="completed"
curl http://localhost:8005/jobs/job_abc123/download -o meu_audio.wav
```

**Presets disponíveis**: `female_generic`, `male_deep`, `female_pt`, `male_pt`, `female_es`, `male_es`
### Clonagem de Voz com F5-TTS

```bash
# 1. Clonar voz a partir de amostra (áudio 2-10s recomendado)
curl -X POST "http://localhost:8005/voices/clone" \
  -F "file=@minha_voz.mp3" \
  -F "name=Minha_Voz" \
  -F "language=pt" \
  -F "description=Voz clonada do João" | jq .

# Response
{
  "message": "Voice cloning job queued",
  "job_id": "job_xyz789",
  "status": "queued",
  "poll_url": "/jobs/job_xyz789"
}

# 2. Aguardar clonagem completar (~15-30s)
curl http://localhost:8005/jobs/job_xyz789 | jq '{status, voice_id, voice_name}'

# Response quando completo
{
  "status": "completed",
  "voice_id": "voice_abc123def456",
  "voice_name": "Minha_Voz"
}

# 3. Listar vozes clonadas
curl http://localhost:8005/voices | jq '.voices[] | {id, name, language}'

# 4. Ver detalhes da voz (inclui reference_text transcrito)
curl http://localhost:8005/voices/voice_abc123def456 | jq .

# 5. Usar voz clonada na dublagem
curl -X POST "http://localhost:8005/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Agora falando com minha própria voz clonada pelo F5-TTS!",
    "source_language": "pt",
    "voice_id": "voice_abc123def456"
  }' | jq .

# ⚠️ IMPORTANTE: Use "voice_id" (não "voice_profile_id")
```

**Dicas de Clonagem**:
- ✅ Áudio limpo, sem ruído de fundo
- ✅ Duração: 2-10 segundos (ideal: 3-5s)
- ✅ Fala clara e natural
- ✅ Formatos: MP3, WAV, M4A, OGG
- ❌ Evitar música, eco, múltiplas vozes'
```

## 🔌 Integração com Orchestrator

O serviço é compatível com o orchestrator do monorepo. Configuração em `orchestrator/modules/config.py`:

```python
MICROSERVICES = {
    # ... outros serviços
    "audio-voice": {
        "url": "http://audio-voice:8004",
        "timeout": 120,
        "max_retries": 3,
        "endpoints": {
            "health": "/health",
            "submit": "/jobs",
            "status": "/jobs/{job_id}",
            "download": "/jobs/{job_id}/download"
        },
        "default_params": {
            "voice_preset": "female_generic",
            "speed": 1.0,
            "pitch": 1.0
        }
    }
}
```

## 📚 API Endpoints

### Jobs de Dublagem

- `POST /jobs` - Criar job de dublagem
- `GET /jobs/{job_id}` - Status do job
- `GET /jobs/{job_id}/download` - Download do áudio
- `GET /jobs` - Listar jobs
- `DELETE /jobs/{job_id}` - Remover job

### Clonagem de Voz

- `POST /voices/clone` - Clonar voz
- `GET /voices` - Listar vozes clonadas
- `GET /voices/{voice_id}` - Detalhes de voz
- `DELETE /voices/{voice_id}` - Remover voz

### Informações
# Limits
MAX_FILE_SIZE_MB=100
MAX_TEXT_LENGTH=10000
MAX_DURATION_MINUTES=10

# Application
PORT=8004
LOG_LEVEL=INFO

# Redis
REDIS_URL=redis://localhost:6379/4

# Limits
MAX_FILE_SIZE_MB=100
MAX_TEXT_LENGTH=10000
MAX_DURATION_MINUTES=10

# F5-TTS (Motor de síntese)
F5TTS_MODEL=F5-TTS            # F5-TTS ou E2-TTS
F5TTS_DEVICE=cuda             # cuda ou cpu (GPU recomendado)
F5TTS_CACHE=/app/models/f5tts # Cache de modelos (~500MB)
F5TTS_NFE_STEP=32             # Quality (16=fast, 32=balanced, 64=high)
F5TTS_TARGET_RMS=0.1          # Volume normalizado

# Cache
CACHE_TTL_HOURS=24
VOICE_PROFILE_TTL_DAYS=30
```

## 🏗️ Arquitetura

```
audio-voice/
├── app/
│   ├── main.py              # FastAPI endpoints
│   ├── models.py            # Pydantic models
│   ├── config.py            # Configurações
│   ├── processor.py         # Lógica de processamento
│   ├── f5tts_client.py      # F5-TTS adapter (GPU-first with CPU fallback)
│   ├── redis_store.py       # Store Redis
│   ├── celery_tasks.py      # Tasks assíncronas
│   └── ...
├── Dockerfile
├── docker-compose.yml
## 🐛 Troubleshooting

### F5-TTS: CUDA Out of Memory

**Problema:** `CUDA out of memory` em GPU <4GB

**Solução:**
1. Use CPU: `F5TTS_DEVICE=cpu` no `.env`
2. Ou libere GPU: pare outros processos (Ollama, etc.)
3. Restart containers: `docker-compose restart`

### Modelos não baixam automaticamente

**Problema:** Erro no download do F5-TTS/Whisper

**Solução:**
1. Verifique conexão internet
2. Verifique espaço em disco (min 2GB livre)
3. Limpe cache HuggingFace: `rm -rf models/f5tts/*`
4. Restart container com logs: `docker logs audio-voice-api -f`
6. Cliente → GET /jobs/{id}/download

## 🧪 Testes

```bash
# Testes unitários
pytest tests/unit/

# Testes de integração
pytest tests/integration/

# Todos os testes
pytest

# Com cobertura
pytest --cov=app --cov-report=html
```

## 🐛 Troubleshooting

### Clonagem de voz falha

**Problema:** `Voice cloning failed` ou transcrição errada

**Solução:**
1. **Duração ideal**: 2-10s (Whisper funciona melhor)
2. **Qualidade**: Áudio limpo, sem ruído/eco
3. **Formatos**: WAV, MP3, M4A, OGG (prefira WAV 16kHz+)
4. **Idioma correto**: `pt`, `en`, `es` (não `pt-BR`)
5. **Verifique transcrição**: `GET /voices/{voice_id}` → `reference_text`

### Síntese não usa voz clonada

**Problema:** Síntese usa preset em vez da voz clonada

**Solução:**
1. ✅ Use `"voice_id": "voice_XXXX"` (não `voice_profile_id`)
2. Verifique logs: `docker logs audio-voice-celery | grep "Using.*voice"`
3. Confirme voice_id existe: `curl http://localhost:8005/voices | jq .`

### Jobs ficam em "processing" eternamente

**Problema:** Jobs não completam

  "checks": {
    "redis": {"status": "ok"},
    "disk_space": {"status": "ok", "free_gb": 50.2},
    "f5tts": {"status": "ok", "device": "cpu", "model": "F5TTS_v1_Base"}
  }
### Clonagem de voz falha

**Problema:** `Voice cloning failed`

**Solução:**
1. Verifique qualidade da amostra (min 5s, 16kHz)
2. Formatos suportados: WAV, MP3, M4A, OGG
3. Verifique se idioma está correto

## 📊 Monitoramento

### Health Check

```bash
curl http://localhost:8004/health
```

Response:
```json
{
  "status": "healthy",
  "service": "audio-voice",
  "version": "1.0.0",
  "checks": {
    "redis": {"status": "ok"},
    "disk_space": {"status": "ok", "free_gb": 50.2},
    "f5tts": {"status": "ok", "device": "cuda", "model": "F5-TTS"}
  }
}
```

### Estatísticas

```bash
curl http://localhost:8004/admin/stats
```

Response:
```json
{
  "jobs": {
    "total": 150,
## 📝 Notas de Implementação

### F5-TTS Engine

✅ **Motor de produção validado**: F5-TTS v1 Base (SWivid/F5-TTS)

**Características**:
- **Síntese**: Fala humana natural de alta qualidade
- **Clonagem**: Automática via Whisper (transcrição) + áudio de referência
- **Performance GPU**: 10-30s para áudio de 3-7s
- **Performance CPU**: 86-850s (10-30x mais lento, viável para dev/teste)
- **GPU Fallback**: Automático em caso de CUDA OOM

**Documentação técnica**:
- `CONTEXT.md` - Contexto completo do sistema
- `SPRINT5-RESULTS.md` - Benchmarks GPU vs CPU

**Qualidade validada**:
- ✅ Pitch variation: 90-114 Hz (fala natural)
- ✅ Zero artefatos sintéticos
- ✅ Clonagem automática funcional
- ✅ GPU-first com fallback CPU robusto

## 🔐 Segurança

- Validação de tamanho de arquivo (max 100MB padrão)
- Validação de duração de áudio (max 10min)
- Validação de tamanho de texto (max 10.000 chars)
- User não-root no Docker
- Rate limiting (via reverse proxy recomendado)

## 📝 Notas de Implementação

### Performance & GPU Support

**GPU (Recomendado para produção)**:
- Device: `F5TTS_DEVICE=cuda`
- Performance: 10-30s para síntese de 3-7s
- VRAM: Mínimo 4GB (GTX 1050 Ti ou superior)
- Fallback automático para CPU em caso de OOM

**CPU (Dev/teste)**:
- Device: `F5TTS_DEVICE=cpu`
- Performance: 86-850s (10-30x mais lento)
- RAM: 4-8GB recomendado

**Celery GPU/CPU Split**:
- API container: GPU (`F5TTS_DEVICE=cuda`)
- Celery worker: CPU (`F5TTS_DEVICE_CELERY=cpu`) - evita conflito de GPU

Ver `SPRINT5-RESULTS.md` para benchmarks detalhados.

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'Adiciona nova funcionalidade'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Abra um Pull Request

## 📄 Licença

Same as parent project: YTCaption-Easy-Youtube-API

## 📞 Suporte

- Issues: GitHub Issues
- Docs: `/docs` endpoint (Swagger UI)
- Architecture: `ARCHITECTURE.md`

---

**Status:** ✅ Implementado e pronto para integração  
**Compatibilidade:** Orchestrator v2.0+  
**Última atualização:** 2024-11-24
