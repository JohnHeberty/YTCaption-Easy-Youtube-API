# 📥 Video Downloader - Serviço de Download

O **Video Downloader** é responsável por baixar vídeos do YouTube e extrair áudio para processamento posterior no pipeline.

## 🎯 Função

- Download de vídeos do YouTube em várias qualidades
- Extração de áudio dos vídeos
- Cache inteligente de 24h para evitar downloads repetidos
- Sistema rotatório de User-Agents para evitar bloqueios
- Background processing com Celery + Redis

## 🔧 Configuração

### Variáveis de Ambiente Principais

```bash
# Servidor
HOST=0.0.0.0
PORT=8000

# Redis (compartilhado com Celery)
REDIS_URL=redis://localhost:6379/0

# Cache
CACHE_TTL_HOURS=24
CLEANUP_INTERVAL_HOURS=6

# User Agents
MAX_QUARANTINE_HOURS=24
```

### Inicialização

```bash
cd services/video-downloader

# Instalar dependências
pip install -r requirements.txt

# Iniciar worker Celery (terminal separado)
celery -A app.celery_config worker --loglevel=info

# Iniciar API
python run.py
```

## 📡 API Endpoints

### Jobs Principais

#### `POST /jobs`
Cria novo job de download.

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "quality": "audio"
}
```

Campos aceitos no request:
- `url` (obrigatório)
- `quality` (opcional): `best`, `worst`, `720p`, `480p`, `360p`, `audio`

Campos internos que não devem ser enviados no `POST /jobs`:
- `id`, `status`, `progress`, timestamps
- `filename`, `file_path`, `file_size`, `error_message`, `retry_count`

**Response:**
```json
{
  "id": "vd_0167f6c083f8f343",
  "status": "queued",
  "url": "https://www.youtube.com/watch?v=FtnKP8fSSdc",
  "quality": "audio",
  "progress": 0.0,
  "created_at": "2025-10-29T10:00:00-03:00",
  "expires_at": "2025-10-30T10:00:00-03:00"
}
```

Para campos detalhados de execução (erro, arquivo, timestamps adicionais, etc.), use `GET /jobs/{job_id}`.

#### `GET /jobs/{job_id}`
Consulta status de job específico.

**Response:**
```json
{
  "id": "vd_0167f6c083f8f343",
  "url": "https://www.youtube.com/watch?v=FtnKP8fSSdc",
  "quality": "audio",
  "status": "completed",
  "progress": 100.0,
  "created_at": "2025-10-29T10:00:00-03:00",
  "completed_at": "2025-10-29T10:02:30-03:00",
  "filename": "audio_FtnKP8fSSdc.webm",
  "file_path": "./cache/audio_FtnKP8fSSdc.webm",
  "file_size": 15720450,
  "error_message": null
}
```

#### `GET /jobs/{job_id}/download`
Download do arquivo processado.

**Response**: Arquivo binário com headers:
```
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="audio_FtnKP8fSSdc.webm"
Content-Length: 15720450
```

### Gerenciamento

#### `GET /jobs`
Lista jobs recentes (máximo 20).

#### `DELETE /jobs/{job_id}`
Remove job e arquivo associado.

**Response:**
```json
{
  "message": "Job removido com sucesso",
  "job_id": "FtnKP8fSSdc_audio",
  "files_deleted": 1
}
```

### Administração

#### `GET /admin/stats`
Estatísticas do sistema.

**Response:**
```json
{
  "jobs": {
    "total": 45,
    "completed": 42,
    "failed": 2,
    "processing": 1
  },
  "cache": {
    "files_count": 35,
    "total_size_mb": 1250.5
  },
  "celery": {
    "active_workers": 1,
    "active_tasks": 1,
    "broker": "redis",
    "backend": "redis"
  }
}
```

#### `GET /admin/queue`
Status da fila Celery.

#### `POST /admin/cleanup`
Limpeza do sistema.

**Request:**
```json
{
  "deep": false  // true para limpeza completa (factory reset)
}
```

**Response:**
```json
{
  "message": "Limpeza básica iniciada em background",
  "cleanup_id": "cleanup_básica_20251029_143000",
  "status": "processing",
  "deep": false,
  "warning": "Jobs expirados serão removidos"
}
```

### User-Agents

#### `GET /user-agents/stats`
Estatísticas do sistema de User-Agents.

**Response:**
```json
{
  "total_uas": 1000,
  "quarantined_uas": 5,
  "available_uas": 995,
  "quarantine_errors": {
    "403": 3,
    "429": 2
  }
}
```

#### `POST /user-agents/reset/{user_agent_id}`
Reset manual de User-Agent problemático.

### Health Check

#### `GET /health`
Verifica saúde do serviço.

**Response:**
```json
{
  "status": "healthy",
  "service": "video-download-service",
  "version": "3.0.0",
  "celery": {
    "healthy": true,
    "workers_active": 1,
    "broker": "redis"
  },
  "details": {
    "celery_workers": "✅ Ativo",
    "redis_broker": "✅ Ativo", 
    "job_store": "✅ Ativo",
    "cache_cleanup": "✅ Ativo"
  }
}
```

## 🔄 Estados de Job

1. **queued** - Job criado, aguardando processamento
2. **downloading** - Download em andamento
3. **completed** - Download concluído com sucesso
4. **failed** - Falha no download

## 🎬 Qualidades Suportadas

- **audio** - Apenas áudio (formato webm/m4a)
- **best** - Melhor qualidade disponível
- **720p** - HD 720p
- **480p** - SD 480p  
- **360p** - Baixa 360p

## 🔄 Cache Inteligente

### Funcionamento
- **TTL**: 24 horas por padrão
- **Key**: `{video_id}_{quality}` (ex: `FtnKP8fSSdc_audio`)
- **Storage**: Redis para metadados + filesystem para arquivos
- **Cleanup**: Automático a cada 6 horas

### Benefícios
- Evita downloads repetidos
- Resposta instantânea para jobs existentes
- Economia de largura de banda
- Redução de carga no YouTube

## 🤖 Sistema de User-Agents

### Funcionalidades  
- **Pool**: 1000+ User-Agents reais
- **Rotação**: Automática para cada requisição
- **Quarentena**: UAs problemáticos ficam isolados 24h
- **Recovery**: Reset automático após período de quarentena

### Estados
- **Ativo**: UA funcionando normalmente
- **Quarentenado**: UA com erros 403/429, isolado temporariamente
- **Erro**: UA com falhas críticas

## ⚡ Background Processing

### Celery Workers
- **Broker**: Redis
- **Backend**: Redis  
- **Tasks**: `download_video_task`
- **Concurrent**: Configurável via workers

### Monitoramento
```bash
# Status dos workers
celery -A app.celery_config inspect active

# Estatísticas
celery -A app.celery_config inspect stats
```

## 🚨 Troubleshooting

### Job Stuck em "queued"
**Causa**: Worker Celery não rodando
**Solução**: `celery -A app.celery_config worker --loglevel=info`

### Erro 403/429 do YouTube
**Causa**: User-Agent bloqueado ou rate limit
**Solução**: Sistema rotativo resolve automaticamente

### Cache Cheio
**Causa**: Muitos arquivos acumulados
**Solução**: `POST /admin/cleanup` ou aumentar limpeza automática

### Job "failed" com network error
**Causa**: Problema de conectividade
**Solução**: Verificar internet, DNS e firewall

### Arquivo Corrompido
**Causa**: Download interrompido
**Solução**: Deletar job e tentar novamente

## 📊 Monitoramento

### Logs Estruturados
```
INFO - Job FtnKP8fSSdc_audio criado para download
INFO - Download iniciado: https://www.youtube.com/watch?v=FtnKP8fSSdc
INFO - Download concluído: 15.0MB em 45s
INFO - Cache hit para job FtnKP8fSSdc_audio (TTL: 23h)
```

### Métricas Importantes
- Jobs por status
- Tamanho total do cache
- Workers Celery ativos
- User-Agents disponíveis vs quarentenados
- Tempo médio de download

## 🔧 Configuração Avançada

### Celery Settings
```python
# app/celery_config.py
broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'UTC'
```

### Download Settings
```python
# Timeout para downloads
DOWNLOAD_TIMEOUT = 300  # 5 minutos

# Retry automático
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos
```

## 📁 Estrutura de Arquivos

```
services/video-downloader/
├── app/
│   ├── main.py           # API endpoints
│   ├── downloader.py     # Lógica de download
│   ├── celery_tasks.py   # Tasks Celery
│   ├── celery_config.py  # Configuração Celery
│   ├── models.py         # Modelos de dados
│   ├── redis_store.py    # Interface Redis
│   └── config.py         # Configurações
├── cache/                # Arquivos baixados
├── logs/                 # Logs do serviço
├── user-agents.txt       # Pool de User-Agents
└── requirements.txt      # Dependências
```

---

**Porta**: 8000 | **Versão**: 3.0.0 | **Tech**: FastAPI + Celery + Redis