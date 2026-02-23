# YTCaption Common Library

Biblioteca compartilhada de utilitários para todos os microserviços do sistema YTCaption.

## Componentes

### 📦 Models (`common.models`)
- `BaseJob`: Modelo base para todos os jobs
- `JobStatus`: Enum padronizado de status
- `HealthStatus`: Enum de health check

### 📝 Logging (`common.logging`)
- `setup_structured_logging()`: Configura logging estruturado
- `get_logger()`: Obtém logger configurado
- `JSONFormatter`: Formatter JSON para logs
- `set_correlation_id()`: Define correlation ID
- `get_correlation_id()`: Obtém correlation ID

### 🔴 Redis (`common.redis`)
- `ResilientRedisStore`: Redis com circuit breaker e pooling
- `RedisCircuitBreaker`: Circuit breaker standalone

### ⚠️ Exceptions (`common.exceptions`)
- `BaseServiceException`: Exceção base
- `ValidationException`: Erro de validação (400)
- `ResourceNotFoundException`: Recurso não encontrado (404)
- `ProcessingException`: Erro de processamento (500)
- `ServiceUnavailableException`: Serviço indisponível (503)
- `setup_exception_handlers()`: Configura handlers globais

### ⚙️ Config (`common.config`)
- `BaseServiceSettings`: Configuração base com validação
- `RedisSettings`: Configurações Redis
- `CelerySettings`: Configurações Celery
- `LoggingSettings`: Configurações de logging

## Instalação

Adicione ao `requirements.txt` do seu serviço:

```txt
-e ../common
```

## Uso Rápido

```python
from fastapi import FastAPI
from common.logging import setup_structured_logging, get_logger
from common.redis import ResilientRedisStore
from common.exceptions import setup_exception_handlers
from common.config import BaseServiceSettings

# Setup
setup_structured_logging("my-service", "INFO")
logger = get_logger(__name__)

# Config
settings = BaseServiceSettings()

# Redis
redis_store = ResilientRedisStore(settings.redis_url)

# FastAPI
app = FastAPI()
setup_exception_handlers(app, debug=settings.debug)

# Uso
logger.info("Service started")
redis_store.set("key", "value")
```

## Benefícios

- ✅ Padronização entre serviços
- ✅ Reutilização de código
- ✅ Menos bugs por duplicação
- ✅ Manutenção centralizada
- ✅ Observabilidade melhorada

## Versão

1.0.0
