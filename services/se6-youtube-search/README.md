# YouTube Search Service

Microserviço para operações de busca no YouTube usando arquitetura hexagonal com FastAPI, Celery e Redis.

## 🎯 Características

- **Arquitetura Hexagonal**: Separação clara de responsabilidades
- **Cache Inteligente**: Redis com TTL de 24h por padrão
- **Processamento Assíncrono**: Celery para jobs em background
- **Alta Performance**: FastAPI com workers configuráveis
- **Containerizado**: Docker e Docker Compose prontos
- **Health Checks**: Monitoramento de saúde do serviço
- **Logs Estruturados**: Sistema de logging por níveis

## 🚀 Funcionalidades

### Endpoints Disponíveis

1. **Video Info** - `POST /search/video-info`
   - Obter informações detalhadas de um vídeo

2. **Channel Info** - `POST /search/channel-info`
   - Obter informações de um canal
   - Opcionalmente incluir vídeos do canal

3. **Playlist Info** - `POST /search/playlist-info`
   - Obter informações de uma playlist

4. **Video Search** - `POST /search/videos`
   - Buscar vídeos por query

5. **Related Videos** - `POST /search/related-videos`
   - Obter vídeos relacionados a um vídeo específico

6. **Job Status** - `GET /jobs/{job_id}`
   - Consultar status e resultado de um job

7. **List Jobs** - `GET /jobs`
   - Listar todos os jobs

8. **Delete Job** - `DELETE /jobs/{job_id}`
   - Remover job e cache

9. **Admin Stats** - `GET /admin/stats`
   - Estatísticas completas do sistema

10. **Admin Queue** - `GET /admin/queue`
    - Estatísticas da fila Celery

11. **Admin Cleanup** - `POST /admin/cleanup`
    - Limpeza manual do sistema

12. **Health Check** - `GET /health`
    - Verificar saúde do serviço

## 📋 Requisitos

- Docker e Docker Compose
- Redis (compartilhado ou dedicado)
- Python 3.11+ (para desenvolvimento local)

## 🔧 Instalação e Configuração

### 1. Configurar Variáveis de Ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env` conforme necessário:

```env
# Application
APP_NAME=YouTube Search Service
PORT=8003

# Redis
REDIS_URL=redis://redis:6379/0

# Cache
CACHE_TTL_HOURS=24

# YouTube API
YOUTUBE_DEFAULT_TIMEOUT=10
YOUTUBE_MAX_RESULTS=50
```

### 2. Iniciar com Docker Compose

```bash
# Build e start
docker-compose up -d --build

# Ver logs
docker-compose logs -f

# Parar serviços
docker-compose down
```

### 3. Desenvolvimento Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Iniciar API
python run.py

# Iniciar Celery Worker (em outro terminal)
celery -A app.celery_config.celery_app worker --loglevel=info -Q youtube_search_queue

# Iniciar Celery Beat (em outro terminal)
celery -A app.celery_config.celery_app beat --loglevel=info
```

## 🧪 Testes

### Executar Testes

```bash
# Instalar dependências de teste
pip install -r tests/requirements-test.txt

# Executar todos os testes
python tests/run_tests.py

# Executar testes específicos
pytest tests/test_models.py -v
pytest tests/test_integration.py -v
pytest tests/test_config.py -v

# Executar com coverage
pytest tests/ --cov=app --cov-report=html
```

### Estrutura de Testes

```
tests/
├── conftest.py              # Configuração pytest
├── test_models.py           # Testes de modelos
├── test_config.py           # Testes de configuração
├── test_integration.py      # Testes de integração API
├── requirements-test.txt    # Dependências de teste
└── run_tests.py            # Runner de testes
```

## 📖 Uso

### Exemplo: Buscar informações de vídeo

```bash
curl -X POST "http://localhost:8003/search/video-info?video_id=dQw4w9WgXcQ" \
  -H "Content-Type: application/json"
```

Resposta:
```json
{
  "id": "abc123def456",
  "search_type": "video_info",
  "video_id": "dQw4w9WgXcQ",
  "status": "queued",
  "progress": 0.0,
  "created_at": "2025-12-10T10:00:00",
  "expires_at": "2025-12-11T10:00:00"
}
```

### Consultar resultado do job

```bash
curl "http://localhost:8003/jobs/abc123def456"
```

Resposta quando completo:
```json
{
  "id": "abc123def456",
  "status": "completed",
  "progress": 100.0,
  "result": {
    "video_id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "duration": "3:33",
    "views_count": 1500000000,
    ...
  }
}
```

## 🏗️ Arquitetura

```
youtube-search/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI endpoints
│   ├── models.py            # Pydantic models
│   ├── config.py            # Configurações
│   ├── processor.py         # Lógica de processamento
│   ├── celery_config.py     # Configuração Celery
│   ├── celery_tasks.py      # Tasks Celery
│   ├── redis_store.py       # Store Redis
│   ├── logging_config.py    # Configuração de logs
│   ├── exceptions.py        # Exceções customizadas
│   └── ytbpy/              # Biblioteca YouTube
│       ├── video.py
│       ├── channel.py
│       ├── playlist.py
│       ├── search.py
│       └── utils.py
├── tests/                   # Testes
├── logs/                    # Logs do serviço
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── run.py
└── README.md
```

### Fluxo de Dados

1. **Request** → API FastAPI recebe requisição
2. **Job Creation** → Cria job com ID único baseado em parâmetros
3. **Cache Check** → Verifica se job já existe (cache hit)
4. **Celery Queue** → Envia job para fila Celery
5. **Worker Processing** → Worker processa job assincronamente
6. **Result Storage** → Resultado armazenado no Redis
7. **Response** → Cliente consulta resultado via job_id

## 🔌 Integração com Orchestrator

Este serviço foi projetado para integrar com o orchestrator principal:

```python
# No orchestrator
## 📊 Monitoramento

### Health Check

```bash
curl http://localhost:8003/health
```

Resposta:
```json
{
  "status": "healthy",
  "service": "youtube-search",
  "version": "1.0.0",
  "timestamp": "2025-12-10T10:00:00",
  "checks": {
    "redis": {
      "status": "ok",
      "message": "Connected",
      "jobs": {
        "total_jobs": 150,
        "queued": 5,
        "processing": 2,
        "completed": 140,
        "failed": 3
      }
    },
    "disk_space": {
      "status": "ok",
      "free_gb": 50.5,
      "total_gb": 100.0,
      "percent_free": 50.5
    },
    "celery_workers": {
      "status": "ok",
      "workers": 2,
      "active_tasks": 3
    },
    "ytbpy": {
      "status": "ok",
      "message": "Library loaded"
    }
  }
}
```

### Estatísticas do Sistema

```bash
curl http://localhost:8003/admin/stats
```

Resposta:
```json
{
  "total_jobs": 150,
  "queued": 5,
  "processing": 2,
  "completed": 140,
  "failed": 3,
  "celery": {
    "active_workers": 2,
    "active_tasks": 3,
    "broker": "redis",
    "backend": "redis",
    "queue": "youtube_search_queue"
  }
}
```

### Estatísticas da Fila Celery

```bash
curl http://localhost:8003/admin/queue
```

### Limpeza do Sistema

#### Limpeza Básica (Remove jobs expirados)

```bash
curl -X POST "http://localhost:8003/admin/cleanup?deep=false"
```

#### Limpeza Total (⚠️ FACTORY RESET - Remove TUDO)

```bash
# Apenas Redis
curl -X POST "http://localhost:8003/admin/cleanup?deep=true&purge_celery_queue=false"

# Redis + Fila Celery
curl -X POST "http://localhost:8003/admin/cleanup?deep=true&purge_celery_queue=true"
```

### Deletar Job Específico

```bash
curl -X DELETE "http://localhost:8003/jobs/abc123def456"
```json
{
  "status": "healthy",
  "redis": "connected",
  "stats": {
    "total_jobs": 150,
    "queued": 5,
    "processing": 2,
    "completed": 140,
    "failed": 3
  }
}
```

## 🔧 Configurações Avançadas

### Cache TTL

Configurar tempo de vida do cache (padrão 24h):

```env
CACHE_TTL_HOURS=48
```

### Worker Concurrency

Ajustar número de workers Celery:

```bash
celery -A app.celery_config.celery_app worker --concurrency=4
```

### Rate Limiting

Habilitar/desabilitar rate limiting:

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
```

## 🐛 Troubleshooting

### Serviço não inicia

1. Verificar se Redis está rodando:
   ```bash
   docker ps | grep redis
   ```

2. Verificar logs:
   ```bash
   docker-compose logs youtube-search-service
   ```

### Jobs ficam travados em "processing"

1. Verificar se Celery worker está rodando:
   ```bash
   docker-compose logs celery-worker
   ```

2. Reiniciar worker:
   ```bash
   docker-compose restart celery-worker
   ```

### Erro de conexão com Redis

Verificar URL do Redis no `.env`:
```env
REDIS_URL=redis://redis:6379/0
```

## 📝 Logs

Logs são salvos em:
- `logs/error.log` - Erros
- `logs/warning.log` - Avisos
- `logs/info.log` - Informações gerais
- `logs/debug.log` - Debug detalhado

## 🤝 Contribuindo

Este serviço segue o padrão dos outros microserviços do projeto:
- Arquitetura hexagonal
- FastAPI + Celery + Redis
- Cache inteligente de 24h
- Health checks e logging estruturado

## 📚 Documentação Adicional

- **[CACHE.md](CACHE.md)** - Documentação completa sobre cache distribuído com Redis
  - Arquitetura de cache
  - Estratégias de invalidação
  - Monitoramento e troubleshooting
  - Redis Cluster para produção

## 📄 Licença

Parte do projeto YTCaption-Easy-Youtube-API

## 🔗 Links Úteis

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/documentation)
- [ytbpy Library](https://github.com/YOUR_REPO/ytbpy)
