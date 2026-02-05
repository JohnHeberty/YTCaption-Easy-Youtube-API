# Audio Transcriber Service - Enterprise Grade

Serviço de transcrição de áudio de alta resiliência usando Whisper AI com arquitetura empresarial completa.

## 🚀 Características Principais

### Core Features
- ✅ **Transcrição AI** - OpenAI Whisper com múltiplos modelos (tiny, base, small, medium, large)
- ✅ **Múltiplos Formatos** - WAV, MP3, M4A, FLAC, OGG com conversão automática
- ✅ **Saídas Flexíveis** - SRT, VTT, TXT, JSON com formatação precisa
- ✅ **Processamento Assíncrono** - Jobs em background com monitoramento em tempo real
- ✅ **Cache Inteligente** - Hash-based caching (arquivo + configurações)
- ✅ **Detecção Automática** - Idioma, formato, qualidade de áudio

### Enterprise Features  
- ✅ **Alta Resiliência** - Circuit breakers, retry automático, failover graceful
- ✅ **Observabilidade Completa** - Prometheus metrics, OpenTelemetry distributed tracing
- ✅ **Segurança Avançada** - Validação magic bytes, rate limiting, análise de entropia
- ✅ **Monitoramento Proativo** - Health checks, resource monitoring, alertas automáticos
- ✅ **Configuração Hierárquica** - Pydantic settings com validação de tipos
- ✅ **Logging Estruturado** - JSON logging com correlation IDs e performance metrics

### Performance & Scalability
- ✅ **Processamento Concorrente** - Multiple job processing com resource management
- ✅ **GPU Acceleration** - Auto-detecção CUDA com fallback para CPU
- ✅ **Resource Management** - Monitoramento CPU/GPU/memória com auto-scaling
- ✅ **Cleanup Automático** - Gestão de arquivos temporários e jobs expirados

## 🚀 Iniciar Serviços

### Docker Compose (RECOMENDADO)
```powershell
cd services/audio-normalization-service
docker-compose up -d
```

### Ver logs
```powershell
docker-compose logs -f
```

## 📊 Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/jobs` | Cria job de transcrição/tradução |
| GET | `/jobs/{job_id}` | Consulta status e progresso |
| GET | `/jobs/{job_id}/transcription` | Obtém resultado da transcrição |
| GET | `/jobs/{job_id}/download` | Download da transcrição em SRT |
| DELETE | `/jobs/{job_id}` | Cancela job em andamento |
| GET | `/jobs` | Lista jobs com filtros |
| GET | `/languages` | Lista idiomas suportados |

### 🆕 Gerenciamento de Modelo (v2.0+)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/model/unload` | 🔋 Descarrega modelo (economia de recursos) |
| POST | `/model/load` | 🚀 Carrega modelo explicitamente |
| GET | `/model/status` | 📊 Status atual do modelo |

**Ver documentação completa**: [MODEL-MANAGEMENT.md](./MODEL-MANAGEMENT.md)
| GET | `/health` | Health check completo |
| GET | `/metrics` | Prometheus metrics |
| GET | `/system/info` | Informações do sistema |

### 🔧 Endpoints Administrativos

| Método | Endpoint | Descrição |
|--------|----------|--------|
| POST | `/admin/cleanup` | Limpeza do sistema (básica ou profunda) |
| GET | `/admin/stats` | Estatísticas completas do sistema |
| POST | `/admin/cleanup-orphans` | Remove jobs e arquivos órfãos |
| GET | `/admin/queue` | Informações detalhadas da fila |
| GET | `/jobs/orphaned` | Lista jobs órfãos (stuck) |
| POST | `/jobs/orphaned/cleanup` | Cleanup granular de órfãos |

**Ver documentação completa**: [ADMIN_ENDPOINTS_STANDARDIZATION.md](../../docs/ADMIN_ENDPOINTS_STANDARDIZATION.md)

## 🧪 Testar

### Upload de áudio para transcrição
```bash
# Criar job de transcrição
curl -X POST http://localhost:8005/jobs \
  -F "file=@audio.mp3" \
  -F "language_in=pt" \
  -F "language_out=en"

# Verificar status (substitua JOB_ID)
curl http://localhost:8005/jobs/JOB_ID

# Obter transcrição
curl http://localhost:8005/jobs/JOB_ID/transcription

# Ver progresso
Invoke-RestMethod -Uri "http://localhost:8002/jobs/$jobId"

# Download do resultado
Invoke-WebRequest -Uri "http://localhost:8002/jobs/$jobId/download" -OutFile "audio_normalized.mp3"
```

### Testar Sistema de Cache
```powershell
# Executa script de teste automatizado
.\test_cache.ps1

# Resultado esperado:
# - Upload 1: Cria job novo
# - Upload 2 (mesmo arquivo): CACHE HIT (retorna job existente)
# - Upload 3 (operações diferentes): Cria job novo
```

## 🔑 Sistema de Cache

O serviço implementa cache inteligente baseado no **hash do arquivo + operações**:

### Como Funciona
1. **Upload** → Calcula SHA256 do arquivo
2. **Job ID** = `hash_operações` (ex: `a1b2c3_nvm`)
3. **Verifica Cache** → Se já existe, retorna job existente
4. **Economia** → Não reprocessa arquivos idênticos

### Códigos de Operação
- `n` = Noise reduction
- `v` = Volume normalize
- `m` = Mono conversion

**Exemplos de Job IDs:**
- `abc123_nvm` - Todas operações
- `abc123_n` - Apenas ruído
- `abc123_vm` - Volume + Mono

📖 **Documentação completa**: Ver [CACHE_SYSTEM.md](./CACHE_SYSTEM.md)

## 🔧 Configuração

### Variáveis de Ambiente
```env
REDIS_URL=redis://localhost:6379/0
```

## 📦 Dependências

- **FastAPI** - API REST
- **Celery + Redis** - Fila de jobs
- **pydub** - Manipulação de áudio
- **noisereduce** - Remoção de ruído
- **librosa** - Processamento de áudio
- **soundfile** - I/O de arquivos de áudio

## 🏗️ Arquitetura

```
┌─────────────┐
│   FastAPI   │ ─── Submete jobs ───┐
│   (8001)    │                      │
└─────────────┘                      ▼
                              ┌─────────────┐
                              │    Redis    │
                              │   (6380)    │
                              └─────────────┘
                                     ▲
┌─────────────┐                     │
│   Celery    │ ─── Processa audio ─┘
│   Worker    │
└─────────────┘
```

## 🎵 Processo de Normalização

1. **Upload** - Cliente envia arquivo de áudio
2. **Job Creation** - Cria job no Redis
3. **Queue** - Celery worker pega o job
4. **Processing**:
   - Remove ruído (noisereduce)
   - Normaliza volume (pydub)
   - Converte para mono
5. **Complete** - Arquivo disponível para download
6. **Expire** - Arquivo removido após 24h

## 📈 Performance

| Operação | Tempo Médio | Redução |
|----------|-------------|---------|
| Remove Ruído | 5-10s | N/A |
| Normaliza Volume | 1-2s | N/A |
| Converte Mono | 1s | ~50% tamanho |
| **Total (5min áudio)** | **7-13s** | **~50%** |

## 🔐 Portas

- **8001** - API REST
- **6380** - Redis (mapeado do 6379 interno)
