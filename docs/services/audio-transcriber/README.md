# 📝 Audio Transcriber - Transcrição e Tradução

O **Audio Transcriber** é responsável por converter áudio em texto usando modelos de speech-to-text (Whisper) e realizar traduções quando necessário.

## 🎯 Função

- Transcrição de áudio para texto usando OpenAI Whisper
- Detecção automática de idioma
- Tradução entre idiomas
- Geração de timestamps precisos
- Segmentação inteligente do texto
- Múltiplos formatos de saída (SRT, VTT, TXT, JSON)

---

## 🏗️ Arquitetura Modular

> **⭐ ATUALIZADO**: Estrutura reorganizada em Fevereiro 2026 seguindo **Clean Architecture**

### Estrutura de Diretórios

```
services/se4-audio-transcriber/
├── app/
│   ├── api/                    # 🌐 Camada de Apresentação
│   │   └── router.py           # (Futuro) Rotas FastAPI separadas
│   │
│   ├── core/                   # ⚙️ Configurações
│   │   ├── config.py           # Settings (env vars, constantes)
│   │   └── logging_config.py   # Logging estruturado
│   │
│   ├── domain/                 # 🎯 Regras de Negócio
│   │   ├── models.py           # Job, Segment, Word (Pydantic)
│   │   ├── exceptions.py       # TranscriptionError, ValidationError
│   │   └── interfaces.py       # Contratos (ABC): IJobStore, IProcessor
│   │
│   ├── services/               # 💼 Casos de Uso
│   │   ├── processor.py        # TranscriptionProcessor (orquestração)
│   │   ├── faster_whisper_manager.py  # Gerencia faster-whisper
│   │   ├── model_manager.py    # (Opcional) openai-whisper
│   │   └── device_manager.py   # (Opcional) GPU/CPU detection
│   │
│   ├── infrastructure/         # 🔧 Detalhes Técnicos
│   │   ├── redis_store.py      # RedisJobStore (persistência)
│   │   ├── storage.py          # FileStorage (filesystem)
│   │   └── circuit_breaker.py  # Resiliência (fallback)
│   │
│   ├── workers/                # ⚡ Background Processing
│   │   ├── celery_config.py    # Configuração Celery
│   │   └── celery_tasks.py     # process_transcription_task
│   │
│   ├── shared/                 # 🛠️ Utilitários
│   │   ├── health_checker.py   # Health checks (Redis, FFmpeg, Model)
│   │   ├── progress_tracker.py # Tracking de progresso
│   │   └── orphan_cleaner.py   # Limpeza de jobs órfãos
│   │
│   └── main.py                 # 🚀 FastAPI app (entry point)
│
├── common/                     # 📚 Biblioteca compartilhada (symlink)
│   ├── config_utils/
│   ├── log_utils/
│   ├── redis_utils/
│   └── models/
│
├── tests/                      # 🧪 Testes (estruturado)
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt            # faster-whisper >=1.1.1
├── Makefile                    # Automação (install, test, build, up)
└── README.md                   # Este arquivo
```

### Fluxo de Dados (Clean Architecture)

```
Client Request (HTTP)
    ↓
main.py (FastAPI app)
    ↓
services/processor.py (TranscriptionProcessor)
    ↓
services/faster_whisper_manager.py (FasterWhisperManager)
    ↓
domain/models.py (Job, Segment, Word)
    ↓
infrastructure/redis_store.py (RedisJobStore)
    ↓
workers/celery_tasks.py (process_transcription_task)
    ↓
infrastructure/storage.py (FileStorage - save files)
```

### Benefícios da Arquitetura Modular

1. **Testabilidade**: Cada módulo pode ser testado isoladamente
2. **Manutenibilidade**: Código organizado por responsabilidade
3. **Escalabilidade**: Fácil adicionar novos engines (whisperx, openai-whisper)
4. **Independência de Framework**: Lógica de negócio separada de FastAPI/Celery
5. **Reutilização**: Módulos `shared/` e `infrastructure/` reutilizáveis

### Padrões Implementados

- **Repository Pattern**: `redis_store.py` abstrai persistência
- **Strategy Pattern**: Múltiplos engines (faster-whisper, whisperx)
- **Circuit Breaker**: Resiliência em `infrastructure/circuit_breaker.py`
- **Dependency Injection**: Through interfaces (`domain/interfaces.py`)

---

## 🔧 Configuração

### Variáveis de Ambiente Principais

```bash
# Servidor
HOST=0.0.0.0
PORT=8004

# Redis
REDIS_URL=redis://localhost:6379/2

# Whisper/OpenAI
OPENAI_API_KEY=sk-...                    # Chave da OpenAI (opcional)
WHISPER_MODEL=base                       # tiny, base, small, medium, large
USE_LOCAL_WHISPER=true                   # Usar Whisper local vs API

# Processamento
MAX_FILE_SIZE_MB=100
TRANSCRIPTION_TIMEOUT_SECONDS=600
TEMP_DIR=./temp
TRANSCRIPTIONS_DIR=./transcriptions

# Cache
CACHE_TTL_HOURS=24
```

### Inicialização

```bash
cd services/se4-audio-transcriber

# Instalar dependências
pip install -r requirements.txt

# Download do modelo Whisper (primeira execução)
python -c "import whisper; whisper.load_model('base')"

# Iniciar serviço
python run.py
```

## 📡 API Endpoints

### Jobs Principais

#### `POST /jobs`
Cria job de transcrição.

**Request** (multipart/form-data):
```
file: [arquivo_audio.wav]           # Arquivo de áudio normalizado
language_in: "auto"                 # Idioma de entrada ("auto", "pt", "en", etc.)
language_out: "en"                  # Idioma de saída (opcional, para tradução)
```

**Response:**
```json
{
  "id": "trans_xyz789abc123",
  "status": "queued",
  "progress": 0.0,
  "created_at": "2025-10-29T10:10:00Z",
  "original_filename": "normalized_abc123def456.wav",
  "file_size": 16234567,
  "language_in": "auto",
  "language_out": "en",
  "detected_language": null,
  "model_used": "base"
}
```

#### `GET /jobs/{job_id}`
Consulta status do job de transcrição.

**Response:**
```json
{
  "id": "trans_xyz789abc123",
  "status": "completed",
  "progress": 100.0,
  "created_at": "2025-10-29T10:10:00Z",
  "updated_at": "2025-10-29T10:15:30Z",
  "completed_at": "2025-10-29T10:15:30Z",
  "original_filename": "normalized_abc123def456.wav",
  "transcription_filename": "transcription_xyz789abc123.srt",
  "file_size": 16234567,
  "duration": 180.5,
  "processing_time": 330.2,
  "language_in": "auto",
  "language_out": "en",
  "detected_language": "pt",
  "model_used": "base",
  "word_count": 425,
  "segment_count": 18,
  "confidence_avg": 0.92,
  "audio_info": {
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav",
    "duration": 180.5
  }
}
```

#### `GET /jobs/{job_id}/download`
Download do arquivo de transcrição (SRT padrão).

**Response**: Arquivo SRT com headers:
```
Content-Type: text/plain; charset=utf-8
Content-Disposition: attachment; filename="transcription_xyz789abc123.srt"
```

#### `GET /jobs/{job_id}/text`
Obtém apenas o texto da transcrição.

**Response:**
```json
{
  "text": "Olá, bem-vindos ao meu canal. Hoje vamos falar sobre inteligência artificial e como ela está mudando o mundo. Primeiro, vamos entender o que é machine learning..."
}
```

#### `GET /jobs/{job_id}/transcription`
Obtém transcrição completa com segments e timestamps.

**Response:**
```json
{
  "job_id": "trans_xyz789abc123",
  "detected_language": "pt",
  "translated_to": "en",
  "full_text": "Hello, welcome to my channel. Today we're going to talk about artificial intelligence...",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.2,
      "duration": 3.2,
      "text": "Hello, welcome to my channel.",
      "words": [
        {
          "word": "Hello",
          "start": 0.0,
          "end": 0.5,
          "confidence": 0.95
        },
        {
          "word": "welcome",
          "start": 0.8,
          "end": 1.2,
          "confidence": 0.92
        }
      ],
      "avg_confidence": 0.94,
      "no_speech_prob": 0.02
    }
  ],
  "statistics": {
    "total_segments": 18,
    "total_words": 425,
    "total_duration": 180.5,
    "avg_confidence": 0.92,
    "speech_percentage": 0.85
  }
}
```

### Idiomas e Modelos

#### `GET /languages`
Lista idiomas suportados.

**Response:**
```json
{
  "supported_languages": {
    "auto": "Detecção Automática",
    "pt": "Português",
    "en": "English", 
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "ja": "日本語",
    "ko": "한국어",
    "zh": "中文",
    "ru": "Русский",
    "ar": "العربية"
  },
  "translation_pairs": [
    "pt->en", "en->pt", "es->en", "fr->en", 
    "de->en", "it->en", "ja->en", "ko->en",
    "zh->en", "ru->en", "ar->en"
  ],
  "models_available": [
    "tiny", "base", "small", "medium", "large"
  ]
}
```

### Gerenciamento

#### `GET /jobs`
Lista jobs recentes de transcrição.

#### `DELETE /jobs/{job_id}`
Remove job e arquivos associados.

### Administração  

#### `GET /admin/stats`
Estatísticas do serviço.

**Response:**
```json
{
  "jobs": {
    "total": 85,
    "completed": 80,
    "failed": 3,
    "processing": 2
  },
  "transcription": {
    "total_hours_processed": 45.8,
    "avg_processing_time": 215.5,
    "avg_confidence": 0.89,
    "languages_detected": {
      "pt": 35,
      "en": 30,
      "es": 15,
      "fr": 5
    }
  },
  "models": {
    "current_model": "base",
    "model_performance": {
      "tiny": { "speed": "5x", "accuracy": "80%" },
      "base": { "speed": "3x", "accuracy": "85%" },
      "small": { "speed": "2x", "accuracy": "90%" }
    }
  },
  "disk_usage": {
    "temp_dir_mb": 250.5,
    "transcriptions_dir_mb": 45.2,
    "models_dir_gb": 2.8
  }
}
```

#### `POST /admin/cleanup`
Limpeza de arquivos temporários.

### Health Check

#### `GET /health`
Verifica saúde do serviço.

**Response:**
```json
{
  "status": "healthy",
  "service": "audio-transcriber-service",
  "version": "2.0.0",
  "dependencies": {
    "whisper": "✅ Modelo 'base' carregado",
    "torch": "✅ CUDA disponível",
    "redis": "✅ Conectado",
    "disk_space": "✅ 12.5GB livres"
  },
  "performance": {
    "model_loaded": "base",
    "gpu_available": true,
    "avg_processing_speed": "2.1x realtime",
    "concurrent_jobs": 1,
    "max_concurrent": 2
  }
}
```

## 🔄 Estados de Job

1. **queued** - Job criado, aguardando processamento
2. **loading_model** - Carregando modelo Whisper
3. **transcribing** - Transcrição em andamento
4. **translating** - Tradução em andamento (se aplicável)
5. **completed** - Processamento concluído
6. **failed** - Falha no processamento

## 🗣️ Modelos Whisper

### Modelos Disponíveis

| Modelo | Tamanho | Velocidade | Precisão | Uso Recomendado |
|--------|---------|------------|----------|-----------------|
| `tiny` | 39 MB | ~5x realtime | ~80% | Desenvolvimento/testes |
| `base` | 74 MB | ~3x realtime | ~85% | **Padrão recomendado** |
| `small` | 244 MB | ~2x realtime | ~90% | Alta qualidade |
| `medium` | 769 MB | ~1.5x realtime | ~93% | Produção crítica |
| `large` | 1550 MB | ~1x realtime | ~95% | Máxima precisão |

### Configuração de Modelo
```python
# Mudança de modelo (requer reinicialização)
WHISPER_MODEL=small

# Parâmetros de processamento
WHISPER_TEMPERATURE=0.0        # Determinístico
WHISPER_BEST_OF=5             # Múltiplas tentativas
WHISPER_BEAM_SIZE=5           # Beam search
```

## 🌍 Suporte a Idiomas

### Detecção Automática
- **99 idiomas** suportados pelo Whisper
- **Detecção automática** com confiança > 90%
- **Fallback**: Inglês se detecção falhar

### Idiomas Principais
- **Português** (pt) - Excelente
- **Inglês** (en) - Excelente  
- **Espanhol** (es) - Excelente
- **Francês** (fr) - Muito bom
- **Alemão** (de) - Muito bom
- **Italiano** (it) - Bom
- **Japonês** (ja) - Bom
- **Chinês** (zh) - Bom
- **Russo** (ru) - Bom
- **Árabe** (ar) - Regular

### Tradução
- **Destino**: Sempre inglês (limitação Whisper)
- **Qualidade**: Varia por idioma origem
- **Uso**: Especificar `language_out: "en"`

## 📄 Formatos de Saída

### SRT (SubRip)
```srt
1
00:00:00,000 --> 00:00:03,200
Hello, welcome to my channel.

2
00:00:03,500 --> 00:00:08,100
Today we're going to talk about artificial intelligence.
```

### VTT (WebVTT)
```vtt
WEBVTT

00:00:00.000 --> 00:00:03.200
Hello, welcome to my channel.

00:00:03.500 --> 00:00:08.100
Today we're going to talk about artificial intelligence.
```

### JSON (Completo)
```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 3.2,
      "text": "Hello, welcome to my channel.",
      "confidence": 0.94
    }
  ]
}
```

## 🎯 Qualidade e Precisão

### Métricas de Confiança
- **Por palavra**: 0.0 - 1.0
- **Por segmento**: Média das palavras
- **Geral**: Média ponderada por duração

### Fatores que Afetam Qualidade
- **Qualidade do áudio**: Ruído, distorção
- **Velocidade da fala**: Muito rápido/lento
- **Sotaque/dialeto**: Variações regionais
- **Múltiplos falantes**: Sobreposição
- **Música de fundo**: Interfere na transcrição

### Otimizações
- **Normalização prévia**: Audio Normalization service
- **Sample rate**: 16kHz otimizado
- **Formato**: WAV PCM preferido
- **Duração**: Segmentos 5-30 minutos ideais

## 🚨 Troubleshooting

### Job Stuck em "loading_model"
**Causa**: Modelo Whisper não encontrado
**Solução**: `python -c "import whisper; whisper.load_model('base')"`

### Baixa Precisão na Transcrição
**Causa**: Áudio de baixa qualidade ou idioma não suportado
**Solução**: Melhorar normalização ou verificar idioma

### "CUDA Out of Memory"
**Causa**: Modelo muito grande para GPU disponível
**Solução**: Usar modelo menor ou CPU

### Timeout no Processamento
**Causa**: Arquivo muito longo ou modelo lento
**Solução**: Aumentar timeout ou usar modelo mais rápido

### Tradução de Baixa Qualidade  
**Causa**: Limitações do modelo para o par de idiomas
**Solução**: Usar serviço de tradução especializado

## ⚡ Performance

### Otimizações GPU
```python
# CUDA settings
TORCH_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
WHISPER_DEVICE = "cuda"
WHISPER_FP16 = True  # Half precision para economia de VRAM
```

### Otimizações CPU
```python
# Threading
TORCH_THREADS = 4
OMP_NUM_THREADS = 4

# Memory management
WHISPER_CHUNK_LENGTH = 30  # Processar em chunks de 30s
```

## 📊 Monitoramento

### Logs Estruturados
```
INFO - Job trans_xyz789 iniciado: pt -> en (180.5s audio)
INFO - Modelo 'base' carregado (GPU: Tesla T4)
INFO - Detecção de idioma: pt (confiança: 0.98)
INFO - Transcrição completada: 425 palavras, confiança média: 0.92
INFO - Tradução completada: pt -> en
INFO - Job trans_xyz789 finalizado em 330.2s
```

### Métricas Importantes
- Tempo de processamento vs duração do áudio
- Confiança média por job
- Distribuição de idiomas detectados
- Taxa de uso GPU vs CPU
- Cache hit rate

## 📁 Estrutura de Arquivos

```
services/se4-audio-transcriber/
├── app/
│   ├── main.py           # API endpoints
│   ├── processor.py      # Lógica de transcrição
│   ├── models.py         # Modelos de dados  
│   ├── whisper_client.py # Interface Whisper
│   ├── redis_store.py    # Interface Redis
│   └── config.py         # Configurações
├── temp/                 # Arquivos temporários
├── transcriptions/       # Transcrições geradas
├── models/               # Modelos Whisper baixados
├── logs/                 # Logs do serviço
└── requirements.txt      # Dependências
```

---

**Porta**: 8004 | **Versão**: 2.0.0 | **Tech**: FastAPI + faster-whisper + PyTorch  
**Arquitetura**: ⭐ Clean Architecture (Modular) | [Ver detalhes completos](../../ARCHITECTURE.md)