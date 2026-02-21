# 📦 DATA - Estrutura de Dados do Audio Transcriber

**Versão**: 1.0.0  
**Data**: 21/02/2026

---

## 📋 Visão Geral

Pasta centralizada contendo **TODOS os dados** do serviço de transcrição, organizados em um **pipeline claro**.

## 🔄 PIPELINE DE DADOS

```
┌─────────────────────────────────────────────────────────┐
│         PIPELINE COMPLETO DE TRANSCRIÇÃO                 │
└─────────────────────────────────────────────────────────┘

  📥 data/raw/          Dados brutos (uploads)
      ├── audio/        Áudios originais recebidos
      ├── uploads/      Uploads temporários
      └── cache/        Cache de processamento
             ↓
             
  🔄 data/transform/    Transformação e normalização
      ├── audio/        Áudios normalizados (16kHz mono)
      └── temp/         Temporários (limpeza automática)
             ↓
             
  ✅ data/validate/     Validação de áudio
      ├── in_progress/  Áudios validando agora
      └── validated/    Áudios validados prontos
             ↓
             
  ✅ data/approved/     Transcrições aprovadas
      ├── transcriptions/ Arquivos .txt, .srt, .vtt
      └── output/       Saídas formatadas
             ↓
             
  📊 data/logs/         Logs e debug
      ├── app/          Logs operacionais
      └── debug/        Debug artifacts
      
  💾 data/database/     Dados persistentes
      └── redis-dump/   Backups do Redis
```

---

## 📂 Estrutura Detalhada

### 📥 `data/raw/` - Dados Brutos

**Arquivos originais** antes de qualquer processamento.

```
raw/
├── audio/               # Áudios recebidos (formato original)
│   ├── {job_id}.mp3
│   ├── {job_id}.wav
│   ├── {job_id}.ogg
│   └── {job_id}.m4a
├── uploads/             # Uploads temporários (antes de validation)
│   └── {temp_id}.tmp
└── cache/               # Cache de processamento
    └── metadata.json    # Metadados de cache
```

**Características**:
- Arquivos **não modificados** (como recebidos)
- Podem ter **formatos variados** (MP3, WAV, OGG, M4A, etc)
- **Temporários** até processamento
- **TTL**: 24 horas após processamento

**Limpeza automática**:
```python
# Arquivos >24h após job completed
cleanup_interval: 1 dia
```

---

### 🔄 `data/transform/` - Transformação

**Normalização** de áudios para formato padrão Whisper.

```
transform/
├── audio/               # Áudios normalizados
│   └── {job_id}_normalized.wav
└── temp/                # Arquivos temporários
    └── (limpo a cada 1h)
```

**Processamentos**:
1. **Conversão formato**: MP3/OGG/M4A → WAV
2. **Resample**: Qualquer → 16kHz
3. **Mono**: Stereo → 1 canal
4. **Normalização volume**: -20dB LUFS
5. **Remoção silêncio**: Trim start/end

**Garantias**:
- Saída: WAV PCM 16kHz mono 16-bit
- Compatível: Todos os engines Whisper
- Metadados corretos
- Volume normalizado

**Comando FFmpeg**:
```bash
ffmpeg -i input.mp3 \
  -ar 16000 \
  -ac 1 \
  -c:a pcm_s16le \
  -af "loudnorm=I=-20:TP=-1.5:LRA=11" \
  output.wav
```

---

### ✅ `data/validate/` - Validação

**Validação de qualidade** do áudio antes de transcrição.

```
validate/
├── in_progress/         # Validando agora
│   └── {job_id}.wav
└── validated/           # Validados ✅
    └── {job_id}_validated.wav
```

**Validações realizadas**:
1. **Duração**: 0.1s < duration < 4 horas
2. **Sample rate**: 8kHz ≤ rate ≤ 48kHz
3. **Canais**: 1 ou 2 (convertido para mono)
4. **Codec**: Válido e decodificável
5. **Corrupção**: Checksum e integridade
6. **Silêncio**: Não 100% silencioso

**Rejeitados**:
- Áudios corrompidos
- Sem áudio (silêncio total)
- Duração inválida
- Formato não suportado

---

### ✅ `data/approved/` - Transcrições Aprovadas

**Saídas finais** de transcrição prontas para entrega.

```
approved/
├── transcriptions/      # Transcrições em múltiplos formatos
│   ├── {job_id}.txt     # Texto puro
│   ├── {job_id}.srt     # Legendas SRT
│   ├── {job_id}.vtt     # Legendas WebVTT
│   └── {job_id}.json    # JSON com timestamps
└── output/              # Saídas especiais
    ├── {job_id}_segments.json  # Segmentos detalhados
    └── {job_id}_words.json     # Word-level timestamps
```

**Formatos de saída**:

#### 1. TXT (Texto Puro)
```
Olá, este é um teste de transcrição.
A qualidade do áudio está boa.
```

#### 2. SRT (Legendas)
```srt
1
00:00:00,000 --> 00:00:02,500
Olá, este é um teste de transcrição.

2
00:00:02,500 --> 00:00:05,000
A qualidade do áudio está boa.
```

#### 3. VTT (WebVTT)
```vtt
WEBVTT

00:00:00.000 --> 00:00:02.500
Olá, este é um teste de transcrição.

00:00:02.500 --> 00:00:05.000
A qualidade do áudio está boa.
```

#### 4. JSON (Detalhado)
```json
{
  "text": "Olá, este é um teste...",
  "language": "pt",
  "duration": 5.0,
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 2.5,
      "text": "Olá, este é um teste de transcrição.",
      "words": [
        {"word": "Olá", "start": 0.0, "end": 0.5},
        {"word": "este", "start": 0.6, "end": 0.9}
      ]
    }
  ]
}
```

**TTL**: 7 dias após completed

---

### 📊 `data/logs/` - Logs e Debug

**Logs operacionais** e artefatos de debug.

```
logs/
├── app/                 # Logs da aplicação
│   ├── audio-transcriber-{date}.log
│   ├── celery-worker-{date}.log
│   └── error-{date}.log
└── debug/               # Debug artifacts
    ├── failed_audio/    # Áudios que falharam
    ├── waveforms/       # Waveforms para debug
    └── metrics.json     # Métricas de performance
```

**Retenção**:
- Logs app: 30 dias
- Debug artifacts: 7 dias

---

### 💾 `data/database/` - Dados Persistentes

**Dados persistentes** do sistema.

```
database/
├── redis-dump/          # Backups do Redis
│   ├── dump-{timestamp}.rdb
│   └── checkpoint-{timestamp}.rdb
└── job_history.db       # SQLite com histórico de jobs
```

**Backups Redis**:
- Frequência: 1x por dia
- Retenção: 7 dias
- Compressão: gzip

---

## 🧹 Política de Limpeza

### Automática

| Diretório | TTL | Script |
|-----------|-----|--------|
| `raw/audio/` | 24h após completed | `cleanup_old_audio.py` |
| `raw/uploads/` | 1h | `cleanup_temp.py` |
| `transform/temp/` | 1h | `cleanup_temp.py` |
| `validate/in_progress/` | 2h | `cleanup_stalled.py` |
| `approved/transcriptions/` | 7 dias | `cleanup_old_transcriptions.py` |
| `logs/debug/` | 7 dias | `cleanup_logs.py` |

### Manual

```bash
# Limpar tudo exceto database
make clean-data

# Limpar apenas temporários
make clean-temp

# Limpar logs antigos
make clean-logs
```

---

## 📏 Limites e Quotas

### Por Job

| Recurso | Limite |
|---------|--------|
| Audio size | 500 MB |
| Audio duration | 4 horas |
| Transcription size | 10 MB |
| Processing time | 30 min |

### Globais

| Recurso | Limite |
|---------|--------|
| Total raw/ | 50 GB |
| Total approved/ | 100 GB |
| Concurrent jobs | 10 (CPU) / 5 (GPU) |
| Jobs per day | 10,000 |

---

## 🔒 Segurança

### Permissões

```bash
# Estrutura de permissões
data/
├── raw/         (rwx------)  750
├── transform/   (rwx------)  750
├── validate/    (rwx------)  750
├── approved/    (rwxr-xr-x)  755  # Leitura pública
├── logs/        (rwx------)  750
└── database/    (rwx------)  700  # Mais restrito
```

### Sanitização

Todos os arquivos recebidos passam por:
1. **Validação MIME type**
2. **Checksum verification**
3. **Malware scan** (ClamAV)
4. **Content validation**

---

## 📊 Monitoramento

### Métricas

```python
# data/logs/debug/metrics.json
{
  "storage": {
    "raw_usage_gb": 12.5,
    "approved_usage_gb": 45.3,
    "total_usage_gb": 67.8
  },
  "performance": {
    "avg_processing_time_s": 15.3,
    "jobs_completed_24h": 245,
    "jobs_failed_24h": 3
  },
  "cleanup": {
    "last_cleanup": "2026-02-21T10:00:00Z",
    "files_cleaned": 123,
    "space_freed_gb": 5.2
  }
}
```

### Alertas

```yaml
alerts:
  - storage > 80GB: "Storage almost full"
  - failed_jobs_24h > 10: "High failure rate"
  - processing_time > 300s: "Slow processing"
```

---

## 🚀 Performance

### Otimizações

1. **Parallel processing**:
   - Multiple workers processando diferentes estágios
   - Pipeline assíncrono

2. **Caching**:
   - Áudios normalizados em cache (1h)
   - Modelos Whisper em memória

3. **Cleanup incremental**:
   - Não bloqueia processamento
   - Rodando em background

### Benchmarks

| Operação | Tempo (CPU) | Tempo (GPU) |
|----------|-------------|-------------|
| Audio normalization (1 min) | 2s | 1s |
| Transcription small model | 15s | 5s |
| Transcription large model | 45s | 15s |
| Total pipeline (1 min áudio) | 20s | 8s |

---

## 📚 Referências

- **Make-Video data structure**: `/services/make-video/data/`
- **Redis persistence**: [Redis RDB](https://redis.io/docs/manual/persistence/)
- **FFmpeg audio processing**: [FFmpeg Filters](https://ffmpeg.org/ffmpeg-filters.html)
- **Whisper audio requirements**: [OpenAI Whisper Docs](https://github.com/openai/whisper)
