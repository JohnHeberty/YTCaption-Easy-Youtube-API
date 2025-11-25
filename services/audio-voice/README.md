# 🎙️ Audio Voice Service

Microserviço de **dublagem de texto em áudio** e **clonagem de vozes** usando OpenVoice, integrado ao monorepo YTCaption-Easy-Youtube-API.

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
- OpenVoice (instalação veja abaixo)

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

### 2. Instalar OpenVoice

```bash
# Opção 1: Via pip (se disponível)
pip install git+https://github.com/myshell-ai/OpenVoice.git

# Opção 2: Clone e instale localmente
git clone https://github.com/myshell-ai/OpenVoice.git
cd OpenVoice
pip install -e .
```

### 3. Baixar Modelos OpenVoice

```bash
# Crie diretório de modelos
mkdir -p models/checkpoints

# Baixe modelos pré-treinados do OpenVoice
# Siga instruções em: https://github.com/myshell-ai/OpenVoice#download-checkpoints
```

### 4. Iniciar Serviço

```bash
# Opção 1: Local (desenvolvimento)
# Terminal 1: Redis
redis-server

# Terminal 2: FastAPI
python run.py

# Terminal 3: Celery Worker
celery -A app.celery_tasks worker --loglevel=info -Q audio_voice_queue

# Opção 2: Docker Compose (produção)
docker-compose up --build
```

### 5. Testar

```bash
# Health check
curl http://localhost:8004/health

# Listar vozes genéricas disponíveis
curl http://localhost:8004/presets

# Listar idiomas suportados
curl http://localhost:8004/languages
```

## 📖 Uso

### Dublagem com Voz Genérica

```bash
curl -X POST "http://localhost:8004/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "dubbing",
    "text": "Olá, este é um teste de dublagem",
    "source_language": "pt-BR",
    "voice_preset": "female_generic"
  }'

# Response
{
  "id": "job_abc123",
  "status": "queued",
  "progress": 0.0,
  "audio_url": "/jobs/job_abc123/download",
  ...
}

# Verificar status
curl http://localhost:8004/jobs/job_abc123

# Download quando completo
curl http://localhost:8004/jobs/job_abc123/download -O
```

### Clonagem de Voz

```bash
# 1. Clonar voz a partir de amostra
curl -X POST "http://localhost:8004/voices/clone" \
  -F "file=@minha_voz.wav" \
  -F "name=João Silva" \
  -F "language=pt-BR" \
  -F "description=Voz masculina brasileira"

# Response
{
  "id": "voice_xyz789",
  "name": "João Silva",
  "language": "pt-BR",
  ...
}

# 2. Listar vozes clonadas
curl http://localhost:8004/voices

# 3. Usar voz clonada na dublagem
curl -X POST "http://localhost:8004/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "dubbing_with_clone",
    "text": "Agora falando com minha própria voz clonada!",
    "source_language": "pt-BR",
    "voice_id": "voice_xyz789"
  }'
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

- `GET /presets` - Vozes genéricas disponíveis
- `GET /languages` - Idiomas suportados
- `GET /health` - Health check profundo
- `GET /admin/stats` - Estatísticas
- `POST /admin/cleanup` - Limpeza de sistema

Documentação completa da API: http://localhost:8004/docs

## ⚙️ Configuração

Principais variáveis de ambiente (`.env`):

```bash
# Application
PORT=8004
LOG_LEVEL=INFO

# Redis
REDIS_URL=redis://localhost:6379/4

# Limits
MAX_FILE_SIZE_MB=100
MAX_TEXT_LENGTH=10000
MAX_DURATION_MINUTES=10

# OpenVoice
OPENVOICE_DEVICE=cpu  # ou cuda
OPENVOICE_PRELOAD_MODELS=false
OPENVOICE_MIN_CLONE_DURATION_SEC=5
OPENVOICE_MAX_CLONE_DURATION_SEC=60

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
│   ├── openvoice_client.py  # Adapter OpenVoice
│   ├── redis_store.py       # Store Redis
│   ├── celery_tasks.py      # Tasks assíncronas
│   └── ...
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

Fluxo de processamento:
1. Cliente → POST /jobs (dublagem) ou POST /voices/clone (clonagem)
2. FastAPI cria Job → Salva Redis
3. Celery Worker processa job
4. OpenVoice gera áudio/clona voz
5. Áudio salvo em ./processed
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

### OpenVoice não carrega modelos

**Problema:** `OpenVoice models failed to load`

**Solução:**
1. Verifique se modelos foram baixados em `./models/checkpoints/`
2. Verifique permissões de diretório
3. Verifique memória disponível (min 2GB RAM)

### Jobs ficam em "processing" eternamente

**Problema:** Jobs não completam

**Solução:**
1. Verifique se Celery worker está rodando: `celery -A app.celery_tasks inspect active`
2. Verifique logs: `tail -f logs/audio-voice.log`
3. Execute cleanup: `curl -X POST http://localhost:8004/admin/cleanup?deep=true`

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
    "openvoice": {"status": "ok", "models_loaded": true}
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
    "queued": 2,
    "processing": 3,
    "completed": 140,
    "failed": 5
  },
  "voice_profiles": {
    "total": 12,
    "active": 10,
    "expired": 2
  }
}
```

## 🔐 Segurança

- Validação de tamanho de arquivo (max 100MB padrão)
- Validação de duração de áudio (max 10min)
- Validação de tamanho de texto (max 10.000 chars)
- User não-root no Docker
- Rate limiting (via reverse proxy recomendado)

## 📝 Notas de Implementação

### OpenVoice Adapter

O arquivo `openvoice_client.py` contém um **ADAPTER/MOCK** para desenvolvimento. Para produção:

1. Instale OpenVoice real: `pip install git+https://github.com/myshell-ai/OpenVoice.git`
2. Substitua imports mockados por imports reais
3. Ajuste chamadas conforme API OpenVoice
4. Teste com modelos baixados

Veja comentários no código marcados com `===== PRODUÇÃO =====`.

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
