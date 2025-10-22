# Whisper Module v2.0 - Parallel Transcription

Sistema de transcrição paralela com OpenAI Whisper.

---

## Visão Geral

O **Parallel Transcription System v2.0** oferece:
- **7-10x speedup** vs transcrição sequencial
- **Worker pool persistente** (sem overhead de inicialização)
- **Chunking inteligente** de áudio
- **Memory-efficient** processing
- **GPU/CPU automatic fallback**

---

## Arquitetura

```
Audio File (60min)
    ↓
ChunkPreparationService
    ↓ (split into 10x 6min chunks)
PersistentWorkerPool (4 workers)
    ↓ (parallel processing)
[Worker 1] [Worker 2] [Worker 3] [Worker 4]
    ↓ (merge results)
Final Transcription
```

**Benchmark**:
- Sequential: 60min audio = 45min processing
- Parallel (4 workers): 60min audio = 6min processing
- **Speedup**: 7.5x

---

## Componentes

### ParallelWhisperService
- Orquestra transcrição paralela
- Divide áudio em chunks
- Distribui para workers
- Merge de resultados

### PersistentWorkerPool
- Pool de N workers (configurável)
- Workers permanecem carregados (modelo em memória)
- Zero overhead entre transcrições
- Thread-safe task queue

### ChunkPreparationService
- Chunking inteligente em silêncios
- Evita cortar palavras
- Overlap de 0.5s entre chunks
- FFmpeg para splitting rápido

### ModelCache
- Cache de modelos Whisper carregados
- Lazy loading
- LRU eviction
- Reduz 10-15s de loading time

### TranscriptionFactory
- Factory para criar serviços
- Auto-detecta GPU/CPU
- Configura otimizações

---

## Modelos Suportados

| Modelo | Size | VRAM | Speed | Accuracy |
|--------|------|------|-------|----------|
| tiny   | 39M  | ~1GB | Fast  | Basic    |
| base   | 74M  | ~1GB | Fast  | Good     |
| small  | 244M | ~2GB | Medium| Better   |
| medium | 769M | ~5GB | Slow  | Great    |
| large  | 1.5G | ~10GB| V.Slow| Best     |
| turbo  | 809M | ~6GB | Fast  | Great    |

**Recomendado**: `base` (boa velocidade + qualidade)

---

## Exemplo de Uso

```python
from src.infrastructure.whisper import ParallelWhisperService

# Criar serviço paralelo
service = ParallelWhisperService(
    model="base",
    num_workers=4,
    device="cuda"  # ou "cpu"
)

# Transcrever
transcription = await service.transcribe(
    video_file,
    language="auto"
)

# Resultados
print(f"Segmentos: {len(transcription.segments)}")
print(f"Idioma: {transcription.language}")
print(f"Duração: {transcription.duration:.2f}s")
print(f"Tempo: {transcription.processing_time:.2f}s")
```

---

## Performance

**CPU (Intel i7)**:
- base model: ~1.5x realtime
- small model: ~0.8x realtime

**GPU (RTX 3090)**:
- base model: ~8x realtime  
- small model: ~5x realtime
- medium model: ~3x realtime

---

**Versão**: 2.0.0

[⬅️ Voltar](../README.md)
