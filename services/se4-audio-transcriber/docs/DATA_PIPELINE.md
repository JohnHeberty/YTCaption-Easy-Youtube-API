# 🔄 Data Pipeline - Fluxo de Dados

**Versão**: 1.0.0  
**Pipeline**: Raw → Transform → Validate → Approved

---

## 📋 Visão Geral

Pipeline completo de processamento de áudio para transcrição.

```
📥 Upload
   ↓
📦 data/raw/audio/          (Arquivo original)
   ↓
🔄 data/transform/audio/    (Normalização 16kHz mono)
   ↓
✅ data/validate/validated/ (Validação qualidade)
   ↓
🎯 Whisper Transcription
   ↓
✅ data/approved/transcriptions/ (TXT, SRT, VTT, JSON)
```

---

## 🔄 Estágios do Pipeline

### 1. Upload (`data/raw/`)

**Entrada**: Arquivo de áudio do usuário  
**Saída**: Arquivo salvo em `data/raw/audio/`

```python
def handle_upload(file):
    job_id = generate_job_id()
    filepath = f"data/raw/audio/{job_id}{ext}"
    
    # Validações iniciais
    validate_file_size(file, max_mb=500)
    validate_mime_type(file, allowed=['audio/*'])
    
    # Salvar
    file.save(filepath)
    
    return job_id, filepath
```

**Validações**:
- Tamanho máximo: 500 MB
- MIME type: audio/*
- Extensões: .mp3, .wav, .ogg, .m4a, .flac

**TTL**: 24 horas após job completed

---

### 2. Transform (`data/transform/`)

**Entrada**: Arquivo raw  
**Saída**: Áudio normalizado em `data/transform/audio/`

```python
def normalize_audio(input_path, job_id):
    output_path = f"data/transform/audio/{job_id}_normalized.wav"
    
    # FFmpeg: Converter para WAV 16kHz mono
    subprocess.run([
        'ffmpeg', '-i', input_path,
        '-ar', '16000',           # Sample rate 16kHz
        '-ac', '1',               # Mono
        '-c:a', 'pcm_s16le',      # PCM 16-bit
        '-af', 'loudnorm=I=-20:TP=-1.5:LRA=11',  # Normalização volume
        output_path
    ])
    
    return output_path
```

**Transformações**:
1. **Formato**: Qualquer → WAV PCM 16-bit
2. **Sample rate**: Qualquer → 16kHz
3. **Canais**: Stereo → Mono
4. **Volume**: Normalização -20dB LUFS
5. **Silêncio**: Trim start/end (>0.1s)

**Garantias**:
- Compatível com Whisper (todos engines)
- Máxima qualidade para transcrição
- Tamanho otimizado

**TTL**: Arquivos em `transform/temp/` limpos a cada 1 hora

---

### 3. Validate (`data/validate/`)

**Entrada**: Áudio normalizado  
**Saída**: Áudio validado em `data/validate/validated/`

```python
def validate_audio(audio_path, job_id):
    # Carregar metadados
    audio = AudioSegment.from_wav(audio_path)
    duration = len(audio) / 1000.0  # segundos
    
    # Validações
    if duration < 0.1:
        raise AudioTooShortError(f"Audio too short: {duration}s")
    
    if duration > 14400:  # 4 horas
        raise AudioTooLongError(f"Audio too long: {duration}s")
    
    if audio.dBFS < -60:
        raise AudioTooQuietError(f"Audio too quiet: {audio.dBFS} dBFS")
    
    if is_silent(audio):
        raise SilentAudioError("Audio is completely silent")
    
    # Salvar validado
    validated_path = f"data/validate/validated/{job_id}_validated.wav"
    audio.export(validated_path, format='wav')
    
    return validated_path
```

**Validações**:
- ✅ Duração: 0.1s < duration < 4 horas
- ✅ Volume: dBFS > -60
- ✅ Não silencioso (100%)
- ✅ Sample rate: 8kHz ≤ rate ≤ 48kHz
- ✅ Integridade: Checksum válido
- ✅ Decodificável: Sem corrupção

**Rejeições**:
- Áudios corrompidos
- 100% silenciosos
- Muito curtos (<0.1s)
- Muito longos (>4h)
- Volume muito baixo

---

### 4. Transcription (Whisper)

**Entrada**: Áudio validado  
**Saída**: Transcrição em múltiplos formatos

```python
def transcribe_audio(audio_path, engine, language, model_size, job_id):
    # Selecionar engine
    if engine == "faster-whisper":
        model = FasterWhisperModel(model_size)
    elif engine == "openai-whisper":
        model = OpenAIWhisperModel(model_size)
    elif engine == "whisperx":
        model = WhisperXModel(model_size)
    
    # Transcrever
    result = model.transcribe(
        audio_path,
        language=language,
        task="transcribe"
    )
    
    # Salvar em múltiplos formatos
    save_transcription(result, job_id)
    
    return result
```

**Engines**:
- `faster-whisper`: Rápido, GPU/CPU, CTranslate2
- `openai-whisper`: Original OpenAI, alta qualidade
- `whisperx`: Word-level timestamps, alignment

**Parâmetros**:
- `language`: pt, en, es, ... (None = auto-detect)
- `model_size`: tiny, base, small, medium, large
- `task`: transcribe (default) ou translate

---

### 5. Output (`data/approved/`)

**Entrada**: Resultado Whisper  
**Saída**: Múltiplos formatos em `data/approved/transcriptions/`

```python
def save_transcription(result, job_id):
    base_path = f"data/approved/transcriptions/{job_id}"
    
    # 1. TXT (texto puro)
    with open(f"{base_path}.txt", 'w') as f:
        f.write(result["text"])
    
    # 2. SRT (legendas)
    srt_content = generate_srt(result["segments"])
    with open(f"{base_path}.srt", 'w') as f:
        f.write(srt_content)
    
    # 3. VTT (WebVTT)
    vtt_content = generate_vtt(result["segments"])
    with open(f"{base_path}.vtt", 'w') as f:
        f.write(vtt_content)
    
    # 4. JSON (completo)
    with open(f"{base_path}.json", 'w') as f:
        json.dump(result, f, indent=2)
```

**Formatos gerados**:
- **TXT**: Texto puro (human-readable)
- **SRT**: Legendas SubRip (video players)
- **VTT**: WebVTT (web players)
- **JSON**: Completo com timestamps, words, metadata

**Estrutura JSON**:
```json
{
  "text": "Transcrição completa...",
  "language": "pt",
  "duration": 120.5,
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 5.2,
      "text": "Olá, bem-vindo ao vídeo.",
      "words": [
        {"word": "Olá", "start": 0.0, "end": 0.5, "probability": 0.99}
      ]
    }
  ]
}
```

**TTL**: 7 dias após completion

---

## 📊 Monitoramento do Pipeline

### Métricas por Estágio

```python
pipeline_metrics = {
    "upload": {
        "total": 1000,
        "success": 980,
        "failed": 20,
        "avg_duration_ms": 50
    },
    "transform": {
        "total": 980,
        "success": 970,
        "failed": 10,
        "avg_duration_ms": 2000
    },
    "validate": {
        "total": 970,
        "success": 960,
        "failed": 10,
        "rejection_reasons": {
            "too_short": 5,
            "silent": 3,
            "corrupted": 2
        }
    },
    "transcribe": {
        "total": 960,
        "success": 955,
        "failed": 5,
        "avg_duration_ms": 15000,
        "by_engine": {
            "faster-whisper": 700,
            "openai-whisper": 200,
            "whisperx": 55
        }
    }
}
```

### Logs Estruturados

```python
logger.info("Pipeline stage completed", extra={
    "job_id": "abc123",
    "stage": "transform",
    "duration_ms": 2000,
    "input_size_mb": 5.2,
    "output_size_mb": 3.1
})
```

---

## 🚨 Tratamento de Erros

### Por Estágio

| Estágio | Erro | Ação |
|---------|------|------|
| Upload | File too large | HTTP 413, rejeitar |
| Upload | Invalid MIME | HTTP 415, rejeitar |
| Transform | FFmpeg error | Retry 3x, falhar job |
| Validate | Audio too short | Rejeitar, retornar erro |
| Validate | Audio silent | Rejeitar, retornar erro |
| Transcribe | Out of memory | Usar modelo menor, retry |
| Transcribe | Model load fail | Circuit breaker, retry |
| Output | Disk full | Alertar, pausar pipeline |

### Retry Strategy

```python
retry_config = {
    "transform": {
        "max_retries": 3,
        "backoff": "exponential",  # 1s, 2s, 4s
        "exceptions": [FFmpegError]
    },
    "transcribe": {
        "max_retries": 2,
        "backoff": "exponential",
        "exceptions": [ModelLoadError, CUDAOutOfMemoryError]
    }
}
```

---

## 🔄 Paralelização

### Workers Celery

```python
# 3 tipos de workers especializados
celery -A app.celery_app worker -Q transform --concurrency=4
celery -A app.celery_app worker -Q validate --concurrency=8
celery -A app.celery_app worker -Q transcribe --concurrency=2 --pool=solo
```

**Filas**:
- `transform`: CPU-bound (4 workers)
- `validate`: I/O-bound (8 workers)
- `transcribe`: GPU-bound (2 workers, solo pool)

### Pipeline Paralelo

```
Job 1: Upload → Transform → Validate → Transcribe
Job 2:         Upload → Transform → Validate → Transcribe
Job 3:                 Upload → Transform → Validate → Transcribe
```

Cada estágio processa jobs em paralelo.

---

## 🧹 Limpeza Automática

### Cron Jobs

```bash
# Limpar raw/ (24h após completed)
0 */4 * * * python scripts/cleanup_old_audio.py

# Limpar temp/ (1h)
0 * * * * python scripts/cleanup_temp.py

# Limpar approved/ (7 dias após completed)
0 2 * * * python scripts/cleanup_old_transcriptions.py
```

### Script de Limpeza

```python
def cleanup_old_audio():
    cutoff = datetime.now() - timedelta(hours=24)
    
    for filepath in glob("data/raw/audio/*"):
        job_id = extract_job_id(filepath)
        
        # Verificar se job completou há >24h
        job_status = redis.get(f"job:{job_id}:status")
        completed_at = redis.get(f"job:{job_id}:completed_at")
        
        if job_status == "completed" and completed_at < cutoff:
            os.remove(filepath)
            logger.info(f"Cleaned old audio: {filepath}")
```

---

## 📈 Performance

### Benchmarks

| Áudio | Duração | Transform | Validate | Transcribe (GPU) | Total |
|-------|---------|-----------|----------|------------------|-------|
| 1 min | 60s | 2s | 0.5s | 5s | 7.5s |
| 5 min | 300s | 8s | 1s | 20s | 29s |
| 30 min | 1800s | 45s | 3s | 120s | 168s |
| 2h | 7200s | 180s | 10s | 480s | 670s |

### Otimizações

1. **FFmpeg**: Hardware acceleration (NVENC/VAAPI)
2. **Whisper**: Batch processing, model caching
3. **I/O**: Async file operations
4. **Parallel**: Multiple workers por estágio

---

## 📚 Links Relacionados

- **[Data Structure](../data/README.md)** - Estrutura de diretórios
- **[API Reference](API_REFERENCE.md)** - Endpoints da API
- **[Resilience](RESILIENCE.md)** - Circuit Breaker e Checkpoints
- **[Testing](TESTING.md)** - Testes do pipeline
