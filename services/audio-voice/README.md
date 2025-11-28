# 🎙️ Audio Voice Service

Microserviço de **dublagem de texto em áudio** e **clonagem de vozes** usando **XTTS v2** (Coqui TTS) + **RVC** (Retrieval-based Voice Conversion), integrado ao monorepo YTCaption-Easy-Youtube-API.

> ✅ Sistema 100% validado e aprovado para produção  
> 🎯 Motor TTS: **XTTS v2** (tts_models/multilingual/multi-dataset/xtts_v2)  
> 🔊 Clonagem: Zero-shot voice cloning com 3-30s de áudio  
> 🎭 Voice Conversion: **RVC** para conversão de voz de alta qualidade  
> 🧪 **236 testes** profissionais (TDD completo)

---

## 🚨 ALERTA IMPORTANTE: OTIMIZAÇÃO DE DISCO

> ⚠️ **ANTES DE FAZER BUILD** desta imagem, leia a documentação de otimização!  
> O Dockerfile anterior causava **estouro de disco** (22-25 GB durante build).  
> 
> **📚 DOCUMENTAÇÃO COMPLETA:**
> - 🚀 [INDEX.md](./INDEX.md) - Índice de toda documentação
> - 📋 [README_OPTIMIZATION.md](./README_OPTIMIZATION.md) - Quick start e visão geral
> - 🔧 [APPLY_OPTIMIZATION.md](./APPLY_OPTIMIZATION.md) - Guia passo a passo
> - 📊 [INCIDENT_REPORT.md](./INCIDENT_REPORT.md) - Relatório executivo do incidente
>
> **✅ VERSÃO OTIMIZADA:** Use `Dockerfile.optimized` (redução de 40% no uso de disco)
>
> ```bash
> # Aplicar otimizações automaticamente
> ./apply-all-optimizations.sh
> ```

---

## 🎯 Funcionalidades

### 1. Dublagem de Texto (Text-to-Speech)
- Converter texto em áudio dublado com XTTS v2
- Suporte a múltiplos idiomas (PT-BR, EN, ES, FR, etc.)
- Vozes genéricas pré-configuradas (female_generic, male_deep, etc.)
- Vozes personalizadas clonadas
- **Pipeline XTTS + RVC** para máxima qualidade

### 2. Clonagem de Voz (Voice Cloning)
- Criar perfis de voz a partir de amostras de áudio (3-30s)
- Armazenar e gerenciar perfis de voz
- Usar vozes clonadas na dublagem
- Cache inteligente (30 dias)

### 3. **RVC Voice Conversion (NOVO!)** 🎭
- Upload e gerenciamento de modelos RVC (.pth + .index)
- Conversão de voz em tempo real (RTF < 0.5)
- Ajuste de pitch (-12 a +12 semitons)
- Controle fino de parâmetros (index_rate, protect, filter_radius)
- Pipeline integrado: **Texto → XTTS → RVC → Áudio final**
- Fallback automático para XTTS-only em caso de erro
- Suporte a múltiplos modelos RVC simultâneos

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

### 2. Modelos XTTS (Download Automático)

Os modelos XTTS v2 (~2GB) são baixados automaticamente na primeira execução:
- Modelo: `tts_models/multilingual/multi-dataset/xtts_v2`
- Cache: `./models/xtts_v2/`
- Idiomas: 16 incluindo PT, PT-BR, EN, ES, FR, DE, IT, etc.

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
    "text": "Olá, teste do XTTS v2",
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
    "text": "Olá, este é um teste de dublagem com XTTS v2",
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

### Clonagem de Voz com XTTS v2

```bash
# 1. Clonar voz a partir de amostra (áudio 3-30s recomendado)
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
    "text": "Agora falando com minha própria voz clonada pelo XTTS v2!",
    "source_language": "pt",
    "voice_id": "voice_abc123def456"
  }' | jq .

# ⚠️ IMPORTANTE: Use "voice_id" (não "voice_profile_id")
```

**Dicas de Clonagem**:
- ✅ Áudio limpo, sem ruído de fundo
- ✅ Duração: 3-30 segundos (ideal: 6-10s)
- ✅ Fala clara e natural
- ✅ Formatos: MP3, WAV, M4A, OGG
- ❌ Evitar música, eco, múltiplas vozes
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

### **RVC (Voice Conversion)** 🎭

- `POST /rvc-models` - Upload modelo RVC (.pth + .index)
- `GET /rvc-models` - Listar modelos RVC
- `GET /rvc-models/{model_id}` - Detalhes do modelo
- `DELETE /rvc-models/{model_id}` - Remover modelo RVC
- `GET /rvc-models/stats` - Estatísticas de uso

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

# XTTS (Motor de síntese Coqui TTS)
XTTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
XTTS_DEVICE=cuda              # cuda ou cpu (GPU recomendado)
XTTS_FALLBACK_CPU=true        # Fallback automático para CPU
XTTS_TEMPERATURE=0.75         # Variação de emoção (0.1-1.0)
XTTS_REPETITION_PENALTY=1.5   # Controle de repetição
XTTS_SPEED=1.0                # Velocidade de fala

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
│   ├── xtts_client.py       # XTTS v2 client (Coqui TTS)
│   ├── validators.py        # Validação de entrada
│   ├── resilience.py        # Retry, circuit breaker, timeout
│   ├── redis_store.py       # Store Redis
│   ├── celery_tasks.py      # Tasks assíncronas
│   └── ...
├── Dockerfile
├── docker-compose.yml
```

## 🎭 Uso Avançado: RVC (Voice Conversion)

### O que é RVC?

RVC (Retrieval-based Voice Conversion) permite transformar o áudio XTTS para soar como uma voz específica.

**Pipeline:** Texto → XTTS → RVC → Áudio Final

### Upload de Modelo RVC

```bash
curl -X POST "http://localhost:8005/rvc-models" \
  -F "name=Voz_Profissional" \
  -F "model_file=@modelo.pth" \
  -F "index_file=@modelo.index" \
  -F "description=Voz grave profissional" | jq .
```

### Dublagem com TTS + RVC

```bash
curl -X POST "http://localhost:8005/jobs" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "text=Teste de síntese com RVC" \
  -d "source_language=pt" \
  -d "mode=dubbing" \
  -d "voice_preset=female_warm" \
  -d "enable_rvc=true" \
  -d "rvc_model_id=rvc_abc123" \
  -d "rvc_pitch=0" \
  -d "rvc_index_rate=0.75" | jq .
```

### Parâmetros RVC

| Parâmetro | Range | Default | Descrição |
|-----------|-------|---------|-----------|
| `rvc_pitch` | -12 a +12 | 0 | Ajuste de pitch (semitons) |
| `rvc_index_rate` | 0.0-1.0 | 0.75 | Influência do index |
| `rvc_filter_radius` | 0-7 | 3 | Filtro de mediana |
| `rvc_protect` | 0.0-0.5 | 0.33 | Proteção de consoantes |

**Docs completas:** Ver [AUDIO-QUALITY-TESTS.md](docs/AUDIO-QUALITY-TESTS.md)

## 🐛 Troubleshooting

### XTTS: CUDA Out of Memory

**Problema:** `CUDA out of memory` em GPU <4GB

**Solução:**
1. Use CPU: `XTTS_DEVICE=cpu` no `.env`
2. Ou libere GPU: pare outros processos (Ollama, etc.)
3. Restart containers: `docker-compose restart`

### Modelos não baixam automaticamente

**Problema:** Erro no download do XTTS v2

**Solução:**
1. Verifique conexão internet
2. Verifique espaço em disco (min 5GB livre)
3. Limpe cache HuggingFace: `rm -rf ~/.cache/tts`
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

**Problema:** `Voice cloning failed` ou qualidade ruim

**Solução:**
1. **Duração ideal**: 3-30s (XTTS funciona melhor com 6-10s)
2. **Qualidade**: Áudio limpo, sem ruído/eco
3. **Formatos**: WAV, MP3, M4A, OGG (prefira WAV 24kHz+)
4. **Idioma correto**: `pt`, `en`, `es` (não `pt-BR`)
5. **Teste com diferentes samples**: XTTS é sensível à qualidade

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
    "xtts": {"status": "ok", "device": "cuda", "model": "xtts_v2"}
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

### XTTS v2 Engine

✅ **Motor de produção validado**: XTTS v2 (Coqui TTS)

**Características**:
- **Síntese**: Fala humana natural de alta qualidade
- **Clonagem**: Zero-shot voice cloning (3-30s de áudio)
- **Idiomas**: 16 idiomas suportados incluindo PT-BR
- **Performance GPU**: 10-30s para áudio de 3-7s
- **Performance CPU**: 60-180s (3-6x mais lento, viável para dev)
- **GPU Fallback**: Automático em caso de CUDA OOM
- **Sample Rate**: 24kHz (alta qualidade)

**Documentação técnica**:
- `IMPLEMENTATION_SUMMARY.md` - Resumo completo da implementação
- `TTS_RESEARCH_PTBR.md` - Pesquisa de modelos TTS para PT-BR

**Qualidade validada**:
- ✅ Naturalidade excelente com quality profiles
- ✅ Clonagem zero-shot funcional
- ✅ GPU-first com fallback CPU robusto
- ✅ Retry automático e resiliência integrada

## 🧪 Testes e Qualidade

### Cobertura de Testes

**Total: 236 testes profissionais**

| Categoria | Testes | Arquivo | Descrição |
|-----------|--------|---------|-----------|
| **Infrastructure** | 22 | `test_docker_gpu.py` | Docker + CUDA validation |
| **Dependencies** | 17 | `test_rvc_dependencies.py` | RVC libs installation |
| **RVC Client** | 27 | `test_rvc_client.py` | Voice conversion core |
| **XTTS+RVC Integration** | 15 | `test_xtts_rvc_integration.py` | Pipeline integration |
| **Unit Tests** | 53 | `test_rvc_unit.py` | Component isolation |
| **Model Management** | 25 | `test_rvc_model_manager.py` | Model CRUD + cache |
| **API Endpoints** | 22 | `test_api_rvc_endpoints.py` | REST API validation |
| **E2E Tests** | 16 | `test_e2e_rvc_pipeline.py` | Full workflows |
| **Performance** | 16 | `test_rvc_performance.py` | RTF benchmarks |
| **Audio Quality** | 23 | `test_audio_quality.py` | Audio validation |

### Executar Testes

```bash
# Todos os testes
pytest tests/ -v

# Testes de performance
pytest tests/test_rvc_performance.py -v -m performance

# Testes de qualidade de áudio
pytest tests/test_audio_quality.py -v

# Com coverage
pytest --cov=app --cov-report=html
```

### Métricas de Performance

**Targets validados:**
- RTF (Real-Time Factor): <0.5 (2x mais rápido que tempo real)
- RVC init: <100ms
- Memory baseline: <500MB
- API response: <100ms (GET), <200ms (POST)
- Model loading: <2s
- Cached access: <10ms

### Qualidade de Áudio

**Padrões garantidos:**
- Formato: WAV, 24kHz, Mono, 16-bit
- Duração: ±50ms precisão
- Silêncio: <200ms inicial, <500ms final
- Clipping: <0.1%
- Peak: -6dB a -1dB
- RMS: -20dB ±2dB
- LUFS: -16 ±2 (broadcast standard)
- SNR: >20dB
- RVC similaridade: >0.7

**Docs:** Ver [AUDIO-QUALITY-TESTS.md](docs/AUDIO-QUALITY-TESTS.md)

## 🔐 Segurança

- Validação de tamanho de arquivo (max 100MB padrão)
- Validação de duração de áudio (max 10min)
- Validação de tamanho de texto (max 10.000 chars)
- Sanitização de entrada via `validators.py`
- User não-root no Docker
- Rate limiting (via reverse proxy recomendado)

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

**Status:** ✅ Implementado e pronto para produção  
**Compatibilidade:** Orchestrator v2.0+  
**Testes:** 236 testes profissionais (TDD completo)  
**Qualidade:** Broadcast standard (LUFS -16, RTF <0.5)  
**Última atualização:** 27 de Novembro de 2025
