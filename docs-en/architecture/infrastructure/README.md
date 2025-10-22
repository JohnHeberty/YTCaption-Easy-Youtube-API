# Infrastructure Layer

Camada de infraestrutura - Implementações concretas dos serviços.

---

## Visão Geral

A **Infrastructure Layer** implementa as interfaces definidas no domínio:
- **Storage**: Gerenciamento de arquivos temporários
- **Cache**: Cache LRU para transcrições
- **Validators**: Validação de áudio/vídeo
- **Utils**: Utilitários (FFmpeg optimizer)
- **YouTube**: Download resiliente de vídeos (v3.0)
- **Whisper**: Transcrição paralela (v2.0)

---

## Módulos Principais

### Storage (`infrastructure/storage/`)
- **LocalStorageService**: Armazenamento local com limpeza automática
- **FileCleanupManager**: Context managers, cleanup periódico, TTL configurável

### Cache (`infrastructure/cache/`)
- **TranscriptionCache**: Cache LRU com hash de arquivos, TTL 24h, redução de 40-60% carga GPU

### Validators (`infrastructure/validators/`)
- **AudioValidator**: Validação com FFprobe, detecção de corrupção, estimativa de tempo

### Utils (`infrastructure/utils/`)
- **FFmpegOptimizer**: Hardware acceleration (CUDA/NVENC), flags otimizadas, 2-3x speedup

### YouTube (`infrastructure/youtube/`)
- **YouTubeDownloader** (v3.0): 7 estratégias de download, rate limiting, proxy support, Tor
- **TranscriptService**: Extração de legendas nativas do YouTube

### Whisper (`infrastructure/whisper/`)
- **WhisperTranscriptionService**: Transcrição sequencial com Whisper
- **ParallelWhisperService** (v2.0): Worker pool persistente, processamento paralelo, 7-10x speedup
- **ModelCache**: Cache de modelos Whisper carregados
- **ChunkPreparationService**: Chunking inteligente de áudio

---

## Características

**Storage**:
- Diretórios temporários com timestamp único
- Cleanup automático de arquivos antigos (>24h)
- Thread-safe com asyncio

**Cache**:
- Hash MD5/SHA256 de arquivos
- LRU eviction quando cache cheio
- Expiração por TTL
- Thread-safe

**Validator**:
- FFprobe para metadados rápidos
- Suporta 10+ codecs de áudio
- Estimativa de tempo de processamento
- Detecção de corrupção

**FFmpeg Optimizer**:
- Detecção automática de hardware (CUDA, VAAPI, VideoToolbox)
- Flags de otimização adaptativas
- Conversão 2-3x mais rápida

---

## Exemplo de Uso

```python
from src.infrastructure.storage import LocalStorageService
from src.infrastructure.cache import TranscriptionCache
from src.infrastructure.validators import AudioValidator

# Storage
storage = LocalStorageService(base_temp_dir="./temp")
temp_dir = await storage.create_temp_directory()
removed = await storage.cleanup_old_files(max_age_hours=24)

# Cache
cache = TranscriptionCache(max_size=100, ttl_hours=24)
file_hash = cache.compute_file_hash(Path("video.mp4"))
cached = cache.get(file_hash, model_name="base", language="en")

# Validator
validator = AudioValidator()
metadata = validator.validate_file(Path("video.mp4"))
if metadata.is_valid:
    min_time, max_time = validator.estimate_processing_time(
        metadata, model_name="base", device="cuda"
    )
```

---

**Versão**: 3.0.0

[⬅️ Voltar](../README.md)
