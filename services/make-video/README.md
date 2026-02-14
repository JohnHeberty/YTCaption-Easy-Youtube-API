# Make-Video Service 🎬

**Versão:** 2.0.0 (Força Bruta)  
**Status:** ✅ Produção  
**Arquitetura:** Microserviço Orquestrador

> ## 🚀 **NOVA ARQUITETURA IMPLEMENTADA** (Fevereiro 2026)
> 
> **Detecção de Legendas: 97.73% de Acurácia** ✅
> 
> Substituímos todas as abordagens antigas (Sprints 00-07) por **FORÇA BRUTA**:
> - ✅ Processa TODOS os frames (sem sampling)
> - ✅ Frame COMPLETO (sem ROI)
> - ✅ Sem otimizações complexas
> - ✅ Resultado: 97.73% acurácia (vs 24.44% anterior)
> 
> **Documentação**:
> - [Nova Arquitetura (Força Bruta)](docs/NEW_ARCHITECTURE_BRUTE_FORCE.md)
> - [Sprints Antigas (Descontinuadas)](docs/SPRINTS_DEPRECATED.md)

Serviço de orquestração para criação automatizada de vídeos a partir de áudio fornecido pelo usuário, shorts do YouTube e legendas sincronizadas com detecção de fala (Voice Activity Detection).

---

## 📋 Índice

- [⚡ Início Rápido (Makefile)](#-início-rápido-makefile)
- [Stack Tecnológico](#-stack-tecnológico)
- [Funcionalidades](#-funcionalidades)
- [Arquitetura do Sistema](#-arquitetura-do-sistema)
- [Pipeline Operacional](#-pipeline-operacional)
- [Fluxo de Dados](#-fluxo-de-dados)
- [Componentes Principais](#-componentes-principais)
- [Instalação e Configuração](#-instalação-e-configuração)
- [Uso da API](#-uso-da-api)
- [Estrutura de Diretórios](#-estrutura-de-diretórios)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Desenvolvimento](#-desenvolvimento)
- [Testes](#-testes)
- [Monitoramento](#-monitoramento)

---

## ⚡ Início Rápido (Makefile)

Este serviço possui um **Makefile completo** para padronizar todos os comandos.

```bash
# Ver todos os comandos disponíveis
make help

# Setup inicial
make dev-setup              # Instala deps + valida estrutura
make build                  # Build Docker
make up                     # Iniciar serviços

# Desenvolvimento
make dev                    # Modo desenvolvimento
make test-quick             # Testes rápidos
make logs                   # Ver logs

# Calibração OCR
make calibrate-quick        # Calibração rápida (3-4h)
make calibrate              # Calibração completa (60-80h)
make calibrate-status       # Status da calibração

# Manutenção
make restart                # Reiniciar serviços
make validate               # Validar configuração
make health                 # Health check
```

📖 **Guia completo:** [MAKEFILE_GUIDE.md](MAKEFILE_GUIDE.md)

---

## 🛠 Stack Tecnológico

### Linguagem e Runtime
- **Python 3.11+** - Linguagem principal
- **Asyncio** - Processamento assíncrono

### Web Framework
- **FastAPI 0.104.1** - Framework web assíncrono de alta performance
- **Uvicorn 0.24.0** - Servidor ASGI
- **python-multipart 0.0.6** - Suporte para upload de arquivos

### Cliente HTTP Assíncrono
- **httpx 0.25.2** - Cliente HTTP async/await
- **aiofiles 23.2.1** - Operações de I/O assíncronas

### Fila de Tarefas e Cache
- **Celery 5.3.4** - Processamento distribuído de tarefas
- **Redis 5.0.1** - Message broker e cache
- **fakeredis 2.20.0** - Mock de Redis para testes

### Validação e Configuração
- **Pydantic 2.5.2** - Validação de dados e serialização
- **pydantic-settings 2.1.0** - Gerenciamento de configurações
- **python-dotenv 1.0.0** - Carregamento de variáveis de ambiente

### Processamento de Vídeo e Áudio
- **ffmpeg-python 0.2.0** - Wrapper Python para FFmpeg
- **pydub 0.25.1** - Manipulação de áudio
- **Pillow 10.1.0** - Processamento de imagens

### OCR e Visão Computacional
- **pytesseract 0.3.10** - Engine de OCR (Tesseract wrapper)
- **opencv-python 4.8.1.78** - Biblioteca de visão computacional
- **Tesseract 5.x** - Engine OCR nativo (requer instalação do sistema)

### Detecção de Fala (VAD)
- **torch 2.1.1** - Framework de deep learning
- **torchaudio 2.1.1** - Processamento de áudio com PyTorch
- **webrtcvad 2.0.10** - Voice Activity Detection baseado em WebRTC

### Processamento de Legendas
- **pysrt 1.1.2** - Leitura e escrita de arquivos SRT

### Observabilidade
- **prometheus-client 0.19.0** - Métricas para monitoramento

### Utilitários
- **shortuuid 1.0.11** - Geração de IDs únicos curtos

### Testes
- **pytest 7.4.3** - Framework de testes
- **pytest-asyncio 0.21.1** - Suporte async para pytest
- **pytest-cov 4.1.0** - Cobertura de código

### Banco de Dados
- **SQLite 3.x** - Armazenamento de blacklist de vídeos
  - WAL mode para concorrência
  - Transações ACID
  - TTL automático

---

## ✨ Funcionalidades

### 1. Criação Automatizada de Vídeos
- **Upload de Áudio**: Aceita múltiplos formatos (MP3, WAV, M4A, OGG, AAC)
- **Busca Inteligente de Shorts**: Integração com YouTube Search API
- **Composição Automática**: Montagem de vídeo com shorts + áudio + legendas
- **Multi-formato**: Suporta diversos aspect ratios (9:16, 16:9, 1:1, 4:5)

### 2. Processamento de Legendas Avançado
- **Transcrição Automática**: Via microserviço audio-transcriber
- **Speech-Gated Subtitles**: Legendas sincronizadas com detecção de fala (VAD)
- **Word-by-Word**: Sincronização palavra por palavra
- **Estilos Customizáveis**: Static, dynamic, minimal
- **Multi-idioma**: Suporte para PT, EN, ES

### 3. Validação e Filtragem Inteligente
- **OCR Detection**: Detecta vídeos com legendas embutidas
- **Blacklist Automática**: Sistema SQLite para banir vídeos inadequados
- **Validação de Integridade**: Verifica qualidade e decodificabilidade de vídeos
- **Confidence Score**: Sistema de pontuação para decisões automáticas

### 4. Gerenciamento de Jobs
- **Processamento Assíncrono**: Jobs em background via Celery
- **Tracking em Tempo Real**: Acompanhamento de progresso por etapa
- **Status Granular**: 11 estados diferentes de processamento
- **Persistência**: Armazenamento de jobs no Redis com TTL

### 5. Cache e Performance
- **Shorts Cache**: Reutilização de vídeos baixados
- **TTL Configurável**: Expiração automática de cache
- **Cleanup Automático**: Limpeza periódica de arquivos temporários
- **Limite de Tamanho**: Controle de uso de disco

### 6. Otimizações Implementadas ✅ (11/02/2026)

**Performance e Estabilidade:**
- **P0 - Frame Limit Reduction**: 240→30 frames (87.5% ↓ memória)
- **P1 - Singleton OCRDetector**: Thread-safe (~450MB economia/worker)
- **P1 - Garbage Collection**: Agressivo em finally blocks
- **P1 - AV1→H.264 Conversion**: 20x mais rápido (40min→2min)
- **P2 - Cache Validation**: Redis com TTL 7 dias

**Impacto Total:**
- 💾 Redução de memória: ~90% por worker
- ⚡ Performance: 3-8x melhoria geral
- 🎯 AV1/VP9: 20x mais rápido após conversão

**Documentação:** Ver [UNION_OPTIMIZE.md](UNION_OPTIMIZE.md) para detalhes completos.

### 7. Observabilidade
- **Health Check**: Endpoint para validação de dependências
- **Métricas Prometheus**: Exposição de métricas de performance
- **Logging Estruturado**: JSON logs para análise
- **Estatísticas de Cache**: Monitoramento de uso de recursos

---

## 🏗 Arquitetura do Sistema

### Padrão Arquitetural: Orquestrador de Microserviços

O Make-Video Service atua como **orquestrador central** que coordena três microserviços especializados:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Make-Video Service (Orchestrator)            │
│                         Port 8004 - FastAPI                      │
└──────────────┬──────────────┬──────────────┬────────────────────┘
               │              │              │
               │              │              │
       ┌───────▼──────┐  ┌────▼──────┐  ┌───▼────────────┐
       │YouTube-Search│  │Video-Down │  │Audio-Transcriber│
       │  Port 8003   │  │Port 8002  │  │   Port 8001     │
       └──────────────┘  └───────────┘  └─────────────────┘
```

### Componentes Internos

```
┌────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  API Routes  │  │ Redis Store  │  │ Shorts Cache │            │
│  │  /make-video │  │  Job State   │  │   Video DB   │            │
│  │  /jobs/{id}  │  │  Management  │  │              │            │
│  │  /download   │  │              │  │              │            │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘            │
│         │                  │                  │                    │
└─────────┼──────────────────┼──────────────────┼────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                        Celery Worker Pool                          │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                  celery_tasks.py                             │ │
│  │  • process_make_video() - Pipeline principal                │ │
│  │  • download_with_retry() - Download com validação           │ │
│  │  • select_shorts() - Seleção inteligente                    │ │
│  │  • generate_subtitles() - Transcrição + VAD                 │ │
│  │  • compose_final_video() - Montagem FFmpeg                  │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │VideoValidator│  │ Blacklist    │  │VideoBuilder  │           │
│  │  OCR + Check │  │  SQLite DB   │  │ FFmpeg Comp  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────────────────┐
│                          Redis (Message Broker)                    │
│  • Celery Queue: task distribution                                │
│  • Job State: JSON serialization                                  │
│  • Cache: TTL-based expiration                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Banco de Dados

```
┌────────────────────────────────────────────────────────────────────┐
│                    SQLite Database (blacklist.db)                  │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ Table: blacklist                                             │ │
│  │  - video_id (PK)                                             │ │
│  │  - reason (TEXT) - Motivo do ban                            │ │
│  │  - confidence (REAL) - Score OCR (0-1)                      │ │
│  │  - added_at (TIMESTAMP)                                      │ │
│  │  - expires_at (TIMESTAMP) - TTL 90 dias                     │ │
│  │  - metadata (JSON) - Dados extras                           │ │
│  └──────────────────────────────────────────────────────────────┘ │
│  • WAL Mode: Concorrência sem locks                               │
│  • ACID Transactions: Integridade garantida                       │
│  • Auto-cleanup: Expiração automática via expires_at             │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Pipeline Operacional

### Fluxo Completo de Criação de Vídeo

```
┌─────────────────┐
│  1. UPLOAD      │  Cliente faz POST /make-video
│  Audio File     │  • Valida formato (mp3, wav, m4a, ogg, aac)
│  + Query        │  • Valida tamanho (max 100MB)
│                 │  • Salva em /audio_uploads/{job_id}/
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. JOB QUEUED  │  Cria Job no Redis
│  Redis Store    │  • Status: QUEUED
│                 │  • Job ID: shortuuid gerado
│                 │  • Dispara Celery task
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. ANALYZING    │  Analisa duração do áudio
│    AUDIO        │  • pydub: AudioSegment
│                 │  • Calcula target_duration (audio + 5s)
│                 │  • Atualiza job: audio_duration
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. FETCHING     │  Busca shorts via youtube-search
│    SHORTS       │  • POST /search com query
│                 │  • Recebe lista de video_ids
│                 │  • max_shorts: 10-500 (configurável)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. DOWNLOADING  │  Download + Validação (3-tier)
│    SHORTS       │  ┌──────────────────────────────┐
│                 │  │ CHECK 1: Blacklist           │
│                 │  │ • is_blacklisted(video_id)   │
│                 │  │ • Skip se banido             │
│                 │  ├──────────────────────────────┤
│                 │  │ CHECK 2: Integrity           │
│                 │  │ • validate_video_integrity() │
│                 │  │ • FFprobe + frame decode     │
│                 │  ├──────────────────────────────┤
│                 │  │ CHECK 3: OCR Detection       │
│                 │  │ • has_embedded_subtitles()   │
│                 │  │ • 6 frames OCR analysis      │
│                 │  │ • Confidence threshold: 0.40 │
│                 │  │ • Se detectado → blacklist   │
│                 │  └──────────────────────────────┘
│                 │  • Retry: 3x com backoff
│                 │  • Timeout: 120s por vídeo
│                 │  • Cache: /shorts_cache/*.mp4
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 6. SELECTING    │  Seleção inteligente de shorts
│    SHORTS       │  • Ordena por duração (prefer longer)
│                 │  • Algoritmo greedy: preencher target
│                 │  • Evita shorts muito curtos (<5s)
│                 │  • Cria timeline: [short1, short2, ...]
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 7. GENERATING   │  Transcrição + VAD
│    SUBTITLES    │  ┌──────────────────────────────┐
│                 │  │ A. Transcribe Audio          │
│                 │  │ • POST audio-transcriber     │
│                 │  │ • Retorna segments + words   │
│                 │  ├──────────────────────────────┤
│                 │  │ B. Apply VAD                 │
│                 │  │ • process_subtitles_with_vad │
│                 │  │ • Torch/WebRTC VAD models    │
│                 │  │ • Filtra non-speech          │
│                 │  ├──────────────────────────────┤
│                 │  │ C. Generate SRT              │
│                 │  │ • Word-by-word timestamps    │
│                 │  │ • Format: SubRip (.srt)      │
│                 │  │ • Style: ASS parameters      │
│                 │  └──────────────────────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 8. ASSEMBLING   │  Preparação de assets
│    VIDEO        │  • Concatena shorts em ordem
│                 │  • Ajusta aspect ratio/crop
│                 │  • Prepara overlay de áudio
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 9. FINAL        │  Composição FFmpeg
│    COMPOSITION  │  ┌──────────────────────────────┐
│                 │  │ VideoBuilder.build_video()   │
│                 │  │ • Input: shorts timeline     │
│                 │  │ • Audio overlay: fade in/out │
│                 │  │ • Subtitle burn-in: ASS/SRT  │
│                 │  │ • Output: MP4 H.264          │
│                 │  │ • Quality: fast/medium/high  │
│                 │  └──────────────────────────────┘
│                 │  • Arquivo final: /output/{job_id}.mp4
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 10. COMPLETED   │  Job finalizado
│     SUCCESS     │  • Status: COMPLETED
│                 │  • result.video_url disponível
│                 │  • GET /download/{job_id}
└─────────────────┘

         OU

┌─────────────────┐
│ 11. FAILED      │  Tratamento de erro
│     ERROR       │  • Status: FAILED
│                 │  • error.message + details
│                 │  • Cleanup de arquivos temp
└─────────────────┘
```

---

## 📊 Fluxo de Dados

### Estrutura de Job

```json
{
  "job_id": "eJ6ufSDUtJwD25KvRAyiH4",
  "status": "downloading_shorts",
  "progress": 25.0,
  
  "query": "technology innovation",
  "audio_duration": 29.76,
  "target_video_duration": 34.76,
  "max_shorts": 10,
  "subtitle_language": "pt",
  "subtitle_style": "static",
  "aspect_ratio": "9:16",
  "crop_position": "center",
  
  "stages": {
    "analyzing_audio": {
      "status": "completed",
      "progress": 100.0,
      "duration": 0.5,
      "metadata": {}
    },
    "downloading_shorts": {
      "status": "in_progress",
      "progress": 60.0,
      "metadata": {
        "downloaded": 6,
        "total": 10
      }
    }
  },
  
  "result": null,
  "error": null,
  
  "created_at": "2026-02-05T00:00:02Z",
  "updated_at": "2026-02-05T00:00:07Z",
  "completed_at": null,
  "expires_at": null
}
```

### Estados do Job

| Status | Descrição | Progress |
|--------|-----------|----------|
| `queued` | Job na fila, aguardando processamento | 0% |
| `analyzing_audio` | Analisando duração do áudio | 5% |
| `fetching_shorts` | Buscando shorts no YouTube | 10% |
| `downloading_shorts` | Baixando e validando shorts | 25% |
| `selecting_shorts` | Selecionando melhores shorts | 50% |
| `generating_subtitles` | Transcrevendo + aplicando VAD | 60% |
| `assembling_video` | Preparando assets para composição | 75% |
| `final_composition` | Renderizando vídeo final (FFmpeg) | 85% |
| `completed` | Job concluído com sucesso | 100% |
| `failed` | Erro durante processamento | - |
| `cancelled` | Job cancelado pelo usuário | - |

---

## 🧩 Componentes Principais

### 1. API Routes (`app/main.py`)

**Endpoints Principais:**
- `POST /make-video` - Criar novo job de vídeo
- `GET /jobs/{job_id}` - Consultar status do job
- `GET /download/{job_id}` - Baixar vídeo finalizado
- `GET /jobs` - Listar jobs (com filtros)
- `DELETE /jobs/{job_id}` - Cancelar/deletar job
- `GET /health` - Health check + dependências
- `GET /cache/stats` - Estatísticas de cache
- `POST /cache/cleanup` - Limpar cache manualmente
- `POST /test-speech-gating` - Testar VAD em áudio

### 2. Celery Tasks (`app/celery_tasks.py`)

**Tarefas Assíncronas:**
- `process_make_video(job_id)` - Pipeline principal
- `download_with_retry(video_id, max_retries=3)` - Download resiliente
- Integra com microserviços via `MicroservicesClient`

### 3. Video Validator (`app/video_validator.py`)

**Responsabilidades:**
- **Validação de Integridade**: FFprobe + decode de frames
- **OCR Detection**: Extração de 6 frames + Tesseract OCR
- **Confidence Scoring**: 4 features (length, alphanumeric, spaces, position)
- **Threshold**: 0.40 para classificação binária

**Método Principal:**
```python
def has_embedded_subtitles(video_path: str) -> Tuple[bool, float, str]:
    """
    Returns:
        - bool: True se tem legendas embutidas
        - float: Confidence score (0-1)
        - str: Texto detectado (sample)
    """
```

### 4. Blacklist Manager (`app/sqlite_blacklist.py`)

**Funcionalidades:**
- **CRUD**: add, is_blacklisted, get_entry, remove
- **WAL Mode**: Concorrência nativa do SQLite
- **Permanente**: Entradas não expiram (blacklist para sempre)
- **Factory Pattern**: `get_blacklist()` singleton

**Schema SQLite:**
```sql
CREATE TABLE blacklist (
    video_id TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    confidence REAL CHECK(confidence >= 0 AND confidence <= 1),
    added_at TIMESTAMP DEFAULT (datetime('now')),
    metadata JSON
);
```

### 5. Video Builder (`app/video_builder.py`)

**Responsabilidades:**
- Montagem de vídeos com FFmpeg
- Overlay de áudio com fade
- Burn-in de legendas (ASS/SRT)
- Crop e aspect ratio adjustment

### 6. Subtitle Generator (`app/subtitle_generator.py`)

**Funcionalidades:**
- Word-by-word SRT generation
- ASS format support
- Customização de estilo (font, color, outline)
- Integração com VAD

### 7. VAD Processor (`app/vad.py` + `app/vad_utils.py`)

**Modelos:**
- **WebRTC VAD**: Leve e rápido
- **Torch Silero VAD**: Alta precisão

**Processo:**
```python
def process_subtitles_with_vad(
    audio_path: str,
    segments: List[Dict],
    vad_threshold: float = 0.5
) -> List[Dict]:
    """
    Filtra segmentos sem fala detectada
    Returns: Filtered segments apenas com speech
    """
```

### 8. Shorts Cache (`app/shorts_manager.py`)

**Funcionalidades:**
- Cache em disco de vídeos baixados
- TTL configurável
- Cleanup automático
- Estatísticas de uso

### 9. Redis Store (`app/redis_store.py`)

**Operações:**
- `save_job(job)` - Persistir job
- `get_job(job_id)` - Recuperar job
- `update_job_status(job_id, status)` - Atualizar estado
- `list_jobs(filters)` - Listar com filtros
- `cleanup_expired()` - Remover jobs antigos

---

## 🚀 Instalação e Configuração

### Pré-requisitos

**Software Necessário:**
```bash
# Python 3.11+
python3 --version

# Redis Server
redis-server --version

# FFmpeg (com libx264, libfdk-aac)
ffmpeg -version

# Tesseract OCR
tesseract --version
```

**Instalação de Dependências do Sistema (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y \
    python3.11 python3.11-dev python3-pip \
    redis-server \
    ffmpeg \
    tesseract-ocr tesseract-ocr-por tesseract-ocr-eng \
    libsm6 libxext6 libxrender-dev libgomp1
```

### Instalação do Serviço

1. **Clone o repositório:**
```bash
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API/services/make-video
```

2. **Crie ambiente virtual:**
```bash
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. **Instale dependências Python:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Configure variáveis de ambiente:**
```bash
cp .env.example .env
nano .env  # Edite conforme seu ambiente
```

5. **Crie estrutura de diretórios:**
```bash
mkdir -p storage/{audio_uploads,shorts_cache,temp,output_videos}
mkdir -p logs
```

6. **Inicialize banco de dados:**
```bash
python3 -c "from app.sqlite_blacklist import SQLiteBlacklist; SQLiteBlacklist('./storage/shorts_cache/blacklist.db')"
```

### Iniciar Serviços

**Modo Desenvolvimento:**
```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery Worker
celery -A app.celery_config worker --loglevel=info

# Terminal 3: Celery Beat (opcional, para tarefas periódicas)
celery -A app.celery_config beat --loglevel=info

# Terminal 4: FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8004
```

**Modo Produção (Docker Compose):**
```bash
docker-compose up -d
```

---

## 📡 Uso da API

### Criar Vídeo

**Request:**
```bash
curl -X POST http://localhost:8004/make-video \
  -F "audio_file=@audio.mp3" \
  -F "query=technology innovation" \
  -F "max_shorts=10" \
  -F "subtitle_language=pt" \
  -F "subtitle_style=static" \
  -F "aspect_ratio=9:16" \
  -F "crop_position=center"
```

**Response:**
```json
{
  "job_id": "eJ6ufSDUtJwD25KvRAyiH4",
  "status": "queued",
  "message": "Video creation job queued successfully"
}
```

### Consultar Status

**Request:**
```bash
curl http://localhost:8004/jobs/eJ6ufSDUtJwD25KvRAyiH4
```

**Response:**
```json
{
  "job_id": "eJ6ufSDUtJwD25KvRAyiH4",
  "status": "downloading_shorts",
  "progress": 25.0,
  "query": "technology innovation",
  "audio_duration": 29.76,
  "target_video_duration": 34.76,
  "stages": {
    "analyzing_audio": {"status": "completed", "progress": 100.0},
    "downloading_shorts": {"status": "in_progress", "progress": 60.0}
  }
}
```

### Download Vídeo

**Request:**
```bash
curl -O http://localhost:8004/download/eJ6ufSDUtJwD25KvRAyiH4
```

### Listar Jobs

**Request:**
```bash
curl "http://localhost:8004/jobs?status=completed&limit=10"
```

### Health Check

**Request:**
```bash
curl http://localhost:8004/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "make-video",
  "version": "1.0.0",
  "redis": "connected",
  "services": {
    "youtube-search": "healthy",
    "video-downloader": "healthy",
    "audio-transcriber": "healthy"
  }
}
```

---

## 📁 Estrutura de Diretórios

```
make-video/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Configurações (Pydantic Settings)
│   ├── models.py                  # Data models (Job, JobStatus, etc)
│   ├── celery_config.py           # Configuração Celery
│   ├── celery_tasks.py            # Tarefas assíncronas (pipeline)
│   ├── redis_store.py             # Camada de persistência Redis
│   ├── api_client.py              # Cliente para microserviços
│   ├── video_validator.py         # OCR + validação de vídeos
│   ├── sqlite_blacklist.py        # Blacklist SQLite (WAL mode)
│   ├── blacklist_factory.py       # Factory pattern para blacklist
│   ├── shorts_blacklist.py        # Legacy JSON blacklist
│   ├── blacklist_manager.py       # Redis-based blacklist (legacy)
│   ├── shorts_manager.py          # Cache de shorts
│   ├── video_builder.py           # Montagem FFmpeg
│   ├── video_processor.py         # Processamento de vídeo
│   ├── subtitle_generator.py     # Geração de legendas (SRT/ASS)
│   ├── subtitle_postprocessor.py # Pós-processamento de legendas
│   ├── ass_generator.py           # Geração ASS avançada
│   ├── audio_utils.py             # Utilitários de áudio
│   ├── vad.py                     # Voice Activity Detection
│   ├── vad_utils.py               # VAD helpers
│   ├── ocr_detector.py            # OCR detection core
│   ├── exceptions.py              # Exceções customizadas
│   ├── log_utils.py               # Logging helpers
│   ├── logging_config.py          # Setup de logging
│   ├── metrics.py                 # Métricas Prometheus
│   └── timeout_utils.py           # Timeout decorators
├── tests/
│   ├── unit/                      # Testes unitários
│   │   ├── test_sqlite_blacklist.py
│   │   ├── test_video_validator.py
│   │   ├── test_ocr_detector.py
│   │   └── ...
│   ├── integration/               # Testes de integração
│   └── conftest.py                # Fixtures pytest
├── scripts/
│   ├── migrate_blacklist.py       # Migração JSON → SQLite
│   ├── test_integration.py        # Testes de integração manuais
│   └── validate_environment.py    # Validação de ambiente
├── storage/
│   ├── audio_uploads/             # Áudios enviados (por job_id)
│   ├── shorts_cache/              # Cache de vídeos baixados
│   │   ├── blacklist.db           # Banco SQLite
│   │   ├── blacklist.json         # JSON legacy (backup)
│   │   └── *.mp4                  # Vídeos cacheados
│   ├── temp/                      # Arquivos temporários
│   └── output_videos/             # Vídeos finalizados
├── logs/                          # JSON logs estruturados
├── common/                        # Código compartilhado (symlink)
├── .env                           # Variáveis de ambiente (NÃO commitar)
├── .env.example                   # Template de variáveis
├── requirements.txt               # Dependências Python
├── requirements-docker.txt        # Dependências Docker
├── Dockerfile                     # Build do container
├── docker-compose.yml             # Orquestração de containers
├── pytest.ini                     # Configuração pytest
├── conftest.py                    # Fixtures globais
├── run.py                         # Script de inicialização
├── README.md                      # Esta documentação
├── QUICKSTART.md                  # Guia rápido
├── RELATORIO_MIGRACAO_SQLITE.md   # Relatório de migração
└── PLANO_MIGRACAO_SQLITE.md       # Plano de migração
```

---

## 🔐 Variáveis de Ambiente

### Configuração de Servidor

| Variável | Tipo | Padrão | Descrição |
|----------|------|--------|-----------|
| `PORT` | int | `8004` | Porta do servidor FastAPI |
| `DEBUG` | bool | `False` | Modo debug (verbose logging) |
| `LOG_LEVEL` | str | `INFO` | Nível de log (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | str | `json` | Formato de log (json ou text) |
| `LOG_DIR` | str | `./logs` | Diretório de logs |

### Redis (Celery Message Broker)

| Variável | Tipo | Padrão | Descrição |
|----------|------|--------|-----------|
| `REDIS_URL` | str | `redis://localhost:6379/0` | URL de conexão Redis (apenas Celery) |
| `CACHE_TTL_HOURS` | int | `24` | TTL do cache de jobs no Redis (horas) |
| `MAX_CACHE_SIZE_GB` | int | `50` | Tamanho máximo do cache em disco (GB) |

> 🔧 **Nota**: Redis é usado APENAS para Celery (message broker + result backend). A blacklist usa SQLite.

### URLs de Microserviços

| Variável | Tipo | Padrão | Descrição |
|----------|------|--------|-----------|
| `YOUTUBE_SEARCH_URL` | str | `https://ytsearch.loadstask.com` | URL do serviço youtube-search (porta 8003) |
| `VIDEO_DOWNLOADER_URL` | str | `https://ytdownloader.loadstask.com` | URL do serviço video-downloader (porta 8002) |
| `AUDIO_TRANSCRIBER_URL` | str | `https://yttranscriber.loadstask.com` | URL do serviço audio-transcriber (porta 8001) |

### Diretórios de Armazenamento

| Variável | Tipo | Padrão | Descrição |
|----------|------|--------|-----------|
| `AUDIO_UPLOAD_DIR` | str | `./storage/audio_uploads` | Diretório para áudios enviados |
| `SHORTS_CACHE_DIR` | str | `./storage/shorts_cache` | Cache de shorts baixados |
| `TEMP_DIR` | str | `./storage/temp` | Arquivos temporários |
| `OUTPUT_DIR` | str | `./storage/output_videos` | Vídeos finalizados |

### Processamento de Vídeo

| Variável | Tipo | Padrão | Descrição |
|----------|------|--------|-----------|
| `DEFAULT_ASPECT_RATIO` | str | `9:16` | Aspect ratio padrão (9:16, 16:9, 1:1, 4:5) |
| `DEFAULT_CROP_POSITION` | str | `center` | Posição do crop (center, top, bottom) |
| `DEFAULT_VIDEO_QUALITY` | str | `fast` | Qualidade FFmpeg (fast, medium, high) |

### Blacklist (SQLite Permanente)

| Variável | Tipo | Padrão | Descrição |
|----------|------|--------|-----------|
| `SQLITE_DB_PATH` | str | `./storage/shorts_cache/blacklist.db` | Caminho do banco SQLite (permanente) |

> ⚠️ **Nota**: A blacklist é permanente. Vídeos com legendas embutidas ficam banidos indefinidamente. Use `blacklist.remove(video_id)` para desbanir manualmente.

### Legendas (Subtitles)

| Variável | Tipo | Padrão | Descrição |
|----------|------|--------|-----------|
| `SUBTITLE_FONT_SIZE` | int | `22` | Tamanho da fonte (pixels) |
| `SUBTITLE_FONT_NAME` | str | `Arial Black` | Nome da fonte (deve estar instalada) |
| `SUBTITLE_COLOR` | str | `&H00FFFF&` | Cor da fonte (formato ASS hexadecimal) |
| `SUBTITLE_OUTLINE_COLOR` | str | `&H000000&` | Cor do outline (formato ASS) |
| `SUBTITLE_OUTLINE` | int | `2` | Espessura do outline (pixels) |
| `SUBTITLE_ALIGNMENT` | int | `10` | Alinhamento ASS (10=center-bottom) |
| `SUBTITLE_MARGIN_V` | int | `280` | Margem vertical inferior (pixels) |
| `WORDS_PER_CAPTION` | int | `2` | Palavras por legenda (word-by-word) |

### Timeouts e Retries

| Variável | Tipo | Padrão | Descrição |
|----------|------|--------|-----------|
| `API_TIMEOUT` | int | `120` | Timeout geral de APIs (segundos) |
| `DOWNLOAD_POLL_INTERVAL` | int | `3` | Intervalo entre polls de download (segundos) |
| `DOWNLOAD_MAX_POLLS` | int | `40` | Máximo de polls para download (120s total) |
| `TRANSCRIBE_POLL_INTERVAL` | int | `5` | Intervalo entre polls de transcrição (segundos) |
| `TRANSCRIBE_MAX_POLLS` | int | `240` | Máximo de polls para transcrição (1200s = 20min) |

### Cleanup Automático

| Variável | Tipo | Padrão | Descrição |
|----------|------|--------|-----------|
| `CLEANUP_TEMP_AFTER_HOURS` | int | `1` | Limpar /temp após X horas |
| `CLEANUP_OUTPUT_AFTER_HOURS` | int | `24` | Limpar /output após X horas |
| `CLEANUP_SHORTS_CACHE_AFTER_DAYS` | int | `30` | Limpar /shorts_cache após X dias |

---

## 💻 Desenvolvimento

### Ambiente de Desenvolvimento

**Pré-commit hooks (opcional):**
```bash
pip install pre-commit
pre-commit install
```

**Linting:**
```bash
# Black (formatação)
black app/ tests/

# Flake8 (linting)
flake8 app/ tests/ --max-line-length=120

# MyPy (type checking)
mypy app/
```

### Debug com VSCode

**`.vscode/launch.json`:**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8004"
      ],
      "jinja": true,
      "justMyCode": false
    },
    {
      "name": "Celery Worker",
      "type": "python",
      "request": "launch",
      "module": "celery",
      "args": [
        "-A", "app.celery_config",
        "worker",
        "--loglevel=debug",
        "--concurrency=1"
      ]
    }
  ]
}
```

---

## 🧪 Testes

### Executar Testes

**Todos os testes:**
```bash
pytest
```

**Com cobertura:**
```bash
pytest --cov=app --cov-report=html --cov-report=term-missing
```

**Testes específicos:**
```bash
# Testes unitários do SQLite
pytest tests/unit/test_sqlite_blacklist.py -v

# Testes de vídeo validator
pytest tests/unit/test_video_validator.py -v

# Testes de OCR
pytest tests/unit/test_ocr_detector.py -v
```

**Testes de integração:**
```bash
python3 scripts/test_integration.py
```

### Cobertura de Código

**Gerar relatório:**
```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

**Meta de cobertura:** 75%+

### Testes Manuais

**Criar vídeo de teste:**
```bash
curl -X POST http://localhost:8004/make-video \
  -F "audio_file=@TEST.ogg" \
  -F "query=programming tutorial" \
  -F "max_shorts=10"
```

**Monitorar logs:**
```bash
tail -f logs/make-video.log | jq '.'
```

---

## 📊 Monitoramento

### Métricas Prometheus

**Endpoint:**
```
http://localhost:8004/metrics
```

**Métricas Expostas:**
- `http_requests_total` - Total de requisições HTTP
- `http_request_duration_seconds` - Latência de requisições
- `celery_tasks_total` - Total de tarefas Celery
- `celery_task_duration_seconds` - Duração de tarefas
- `blacklist_queries_total` - Consultas à blacklist
- `ocr_detections_total` - Detecções OCR

### Logs Estruturados

**Formato JSON:**
```json
{
  "timestamp": "2026-02-05T00:00:02.531Z",
  "level": "INFO",
  "logger": "app.celery_tasks",
  "message": "Job eJ6ufSDUtJwD25KvRAyiH4 created and queued",
  "job_id": "eJ6ufSDUtJwD25KvRAyiH4",
  "status": "queued"
}
```

**Análise com jq:**
```bash
# Filtrar erros
cat logs/make-video.log | jq 'select(.level == "ERROR")'

# Jobs completados
cat logs/make-video.log | jq 'select(.status == "completed")'

# Duração média de jobs
cat logs/make-video.log | jq -s '[.[] | select(.processing_time)] | add / length'
```

### Health Check

**Monitoramento automático:**
```bash
# Uptime monitoring (exemplo com curl)
while true; do
  curl -s http://localhost:8004/health | jq '.status'
  sleep 30
done
```

**Integração com Prometheus Alertmanager:**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'make-video'
    static_configs:
      - targets: ['localhost:8004']
    metrics_path: '/metrics'
```

---

## 🐛 Troubleshooting

### Problemas Comuns

**1. Tesseract não encontrado:**
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-por tesseract-ocr-eng

# Verificar instalação
tesseract --version
which tesseract
```

**2. FFmpeg erro de codec:**
```bash
# Verificar codecs disponíveis
ffmpeg -codecs | grep -i h264
ffmpeg -codecs | grep -i aac

# Reinstalar com libx264
sudo apt-get install ffmpeg libavcodec-extra
```

**3. Redis connection refused:**
```bash
# Verificar se Redis está rodando
sudo systemctl status redis-server

# Iniciar Redis
sudo systemctl start redis-server

# Testar conexão
redis-cli ping
```

**4. Celery worker não processa jobs:**
```bash
# Verificar fila
celery -A app.celery_config inspect active

# Ver workers registrados
celery -A app.celery_config inspect registered

# Purgar fila (CUIDADO!)
celery -A app.celery_config purge
```

**5. OCR não detecta legendas:**
```bash
# Verificar idiomas instalados
tesseract --list-langs

# Ajustar threshold em config
SUBTITLE_CONFIDENCE_THRESHOLD=0.30  # Mais sensível
```

---

## 📝 Licença

Este projeto faz parte do **YTCaption-Easy-Youtube-API** desenvolvido por **JohnHeberty**.

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

---

## 📞 Suporte

- **Documentação:** [QUICKSTART.md](QUICKSTART.md)
- **Issues:** [GitHub Issues](https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/issues)
- **Relatórios:** [RELATORIO_MIGRACAO_SQLITE.md](RELATORIO_MIGRACAO_SQLITE.md)

---

**Última atualização:** 04 de Fevereiro de 2026  
**Versão:** 1.0.0  
**Status:** ✅ Produção
