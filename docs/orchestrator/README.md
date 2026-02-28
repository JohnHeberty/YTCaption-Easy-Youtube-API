# 🎭 Orchestrator - Gerenciador de Pipeline

O **Orchestrator** é o cérebro do sistema YTCaption, responsável por coordenar todo o pipeline de processamento de vídeos do YouTube através dos microserviços.

## 🎯 Função

Gerencia a sequência: **Download** → **Normalização** → **Transcrição**

- Submete jobs aos microserviços
- Faz polling de status com retry inteligente
- Transfere arquivos entre serviços
- Implementa circuit breaker para resiliência
- Fornece API unificada para clientes

## 🔧 Configuração

### Variáveis de Ambiente

```bash
# Servidor
HOST=0.0.0.0
PORT=8080
WORKERS=1

# Redis
REDIS_URL=redis://192.168.1.110:6379/0

# URLs dos Microserviços
VIDEO_DOWNLOADER_URL=http://192.168.1.132:8000
AUDIO_NORMALIZATION_URL=http://192.168.1.132:8001
AUDIO_TRANSCRIBER_URL=http://192.168.1.132:8004

# Timeouts (segundos)
VIDEO_DOWNLOADER_TIMEOUT=900        # 15 minutos
AUDIO_NORMALIZATION_TIMEOUT=600     # 10 minutos
AUDIO_TRANSCRIBER_TIMEOUT=1200      # 20 minutos

# Polling Adaptativo
POLL_INTERVAL_INITIAL=2             # Polling inicial rápido
POLL_INTERVAL_MAX=30                # Polling máximo
MAX_POLL_ATTEMPTS=600               # 30 min máximo

# Retry e Circuit Breaker
MICROSERVICE_MAX_RETRIES=5          # 5 tentativas por requisição
MICROSERVICE_RETRY_DELAY=3          # 3s base backoff exponencial
CIRCUIT_BREAKER_MAX_FAILURES=5      # Falhas antes de abrir circuito
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=300 # 5 min para recovery

# Recursos
MAX_FILE_SIZE_MB=500                # Limite de arquivo em memória

# Parâmetros Padrão
DEFAULT_LANGUAGE=auto
DEFAULT_REMOVE_NOISE=true
DEFAULT_CONVERT_MONO=true
DEFAULT_SAMPLE_RATE_16K=true
```

### Inicialização

```bash
cd orchestrator

# Instalar dependências
pip install -r requirements.txt

# Configurar ambiente
cp .env.example .env
# Edite .env com suas configurações

# Iniciar serviço
python main.py
```

## 📡 API Endpoints

### Pipeline Principal

#### `POST /process`
Inicia processamento completo de vídeo do YouTube.

**Request:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "auto",              // Opcional: idioma para transcrição
  "language_out": "en",           // Opcional: idioma de saída (tradução)
  "remove_noise": true,           // Opcional: remover ruído
  "convert_to_mono": true,        // Opcional: converter para mono
  "apply_highpass_filter": false, // Opcional: filtro high-pass
  "set_sample_rate_16k": true     // Opcional: sample rate 16kHz
}
```

**Response:**
```json
{
  "job_id": "abc123def456",
  "status": "queued",
  "message": "Pipeline iniciado com sucesso. Use /jobs/{job_id} para acompanhar o progresso.",
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "overall_progress": 0.0
}
```

#### `GET /jobs/{job_id}`
Consulta status detalhado de um job.

**Response:**
```json
{
  "job_id": "abc123def456",
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "status": "transcribing",
  "overall_progress": 75.5,
  "created_at": "2025-10-29T10:00:00Z",
  "updated_at": "2025-10-29T10:05:30Z",
  "stages": {
    "download": {
      "status": "completed",
      "job_id": "video_job_123",
      "progress": 100.0,
      "started_at": "2025-10-29T10:00:05Z",
      "completed_at": "2025-10-29T10:02:30Z"
    },
    "normalization": {
      "status": "completed", 
      "job_id": "audio_job_456",
      "progress": 100.0,
      "started_at": "2025-10-29T10:02:35Z",
      "completed_at": "2025-10-29T10:04:10Z"
    },
    "transcription": {
      "status": "processing",
      "job_id": "transcr_job_789",
      "progress": 65.0,
      "started_at": "2025-10-29T10:04:15Z"
    }
  },
  "transcription_text": "Olá, bem-vindos ao meu canal...",
  "transcription_segments": [
    {
      "text": "Olá, bem-vindos ao meu canal",
      "start": 0.0,
      "end": 2.5,
      "duration": 2.5
    }
  ],
  "transcription_file": "transcription_abc123.srt",
  "audio_file": "normalized_audio.wav"
}
```

### Gerenciamento

#### `GET /jobs`
Lista jobs recentes.

**Response:**
```json
{
  "total": 10,
  "jobs": [
    {
      "job_id": "abc123",
      "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
      "status": "completed",
      "progress": 100.0,
      "created_at": "2025-10-29T10:00:00Z",
      "updated_at": "2025-10-29T10:10:00Z"
    }
  ]
}
```

#### `GET /health`
Verifica saúde do orquestrador e microserviços.

**Response:**
```json
{
  "status": "healthy",
  "service": "orchestrator",
  "version": "2.0.0",
  "timestamp": "2025-10-29T15:30:00Z",
  "microservices": {
    "video-downloader": "healthy",
    "audio-normalization": "healthy", 
    "audio-transcriber": "healthy"
  }
}
```

### Administração

#### `GET /admin/stats`
Estatísticas do sistema.

#### `POST /admin/cleanup`
Limpeza de jobs antigos.

#### `POST /admin/factory-reset`
⚠️ **CUIDADO** - Remove todos os dados de todos os serviços.

## 🛡️ Resiliência Implementada

### Circuit Breaker
- **Abre após**: 5 falhas consecutivas
- **Recovery**: 5 minutos automático
- **Proteção**: Evita spam em serviços com problema

### Retry Inteligente
- **Tentativas**: 5 por requisição
- **Backoff**: Exponencial (3s → 6s → 12s → 24s → 48s)
- **Diferenciação**: Não retry em erros 4xx (cliente)

### Polling Adaptativo
- **Inicial**: 2s para jobs rápidos
- **Progressivo**: 4s após 10 tentativas
- **Máximo**: 30s para jobs longos
- **Timeout**: 30 minutos máximo

### Tratamento de Erros Específico
- **404 inicial**: Normal (job sendo criado)
- **404 tardio**: Job foi deletado/expirado
- **4xx**: Erro de cliente - não retry
- **5xx**: Erro de servidor - retry com backoff
- **Network**: Timeout/conexão - retry com backoff

## 📊 Monitoramento

### Logs Estruturados
```
[PIPELINE:abc123] Starting DOWNLOAD stage for URL: https://...
[PIPELINE:abc123] DOWNLOAD completed: audio.webm (45.2MB)
[video-downloader] Circuit breaker OPENED after 5 failures
[PIPELINE:abc123] NORMALIZATION completed: normalized.wav (47.8MB)
```

### Métricas
- Progress por stage (0-100%)
- Tamanhos de arquivo transferidos
- Tempos de execução por etapa
- Status de circuit breakers
- Uso de recursos

## 🚨 Troubleshooting

### Erro 404 "Job not found"
**Causa**: URLs incorretas dos microserviços ou timing inadequado
**Solução**: Verificar URLs no .env e aguardar processamento

### Circuit Breaker Aberto
**Logs**: `[service] Circuit breaker OPENED after 5 failures`
**Causa**: Microserviço com problema
**Solução**: Verificar saúde do microserviço, aguardar 5min para recovery

### Timeout de Job
**Causa**: Job muito longo ou microserviço lento
**Solução**: Aumentar timeouts específicos no .env

### Arquivo Muito Grande
**Logs**: `File too large: XXXmb > 500MB limit`
**Solução**: Aumentar MAX_FILE_SIZE_MB ou usar vídeo menor

### Falhas de Conexão
**Logs**: `Network error submitting - service may be down`
**Solução**: Verificar se microserviços estão rodando e acessíveis

## 🔄 Estados do Pipeline

1. **queued** - Pipeline criado, aguardando início
2. **downloading** - Download do vídeo em andamento
3. **normalizing** - Processamento de áudio em andamento  
4. **transcribing** - Transcrição em andamento
5. **completed** - Pipeline completo com sucesso
6. **failed** - Falha em algum estágio

## 📈 Performance

- **Jobs simultâneos**: Limitado por recursos dos microserviços
- **Cache**: Redis para jobs e metadados
- **Memória**: Arquivos carregados em memória (limite 500MB)
- **Network**: Retry automático para falhas temporárias

---

**Porta**: 8080 | **Versão**: 2.0.0 | **Atualizado**: Outubro 2025