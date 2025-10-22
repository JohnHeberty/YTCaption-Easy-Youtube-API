# Domain Exceptions

Hierarquia de exceções customizadas do domínio.

---

## Visão Geral

O domínio define uma hierarquia de exceções para representar erros de negócio:
- **Granularidade**: Exceções específicas para debugging preciso
- **Herança**: Todas derivam de `DomainException`
- **Context**: Exceções carregam informações relevantes (arquivo, timeout, etc.)

**Arquivo**: `src/domain/exceptions.py`

---

## Hierarquia

```
DomainException (base)
├── VideoDownloadError
│   └── NetworkError
├── TranscriptionError
│   ├── AudioTooLongError
│   ├── AudioCorruptedError
│   ├── ModelLoadError
│   ├── WorkerPoolError
│   └── FFmpegError
├── StorageError
├── ValidationError
│   ├── AudioTooLongError
│   └── AudioCorruptedError
├── ResourceNotFoundError
├── ServiceUnavailableError
├── OperationTimeoutError
├── QuotaExceededError
└── CacheError
```

---

## Exceções Base

### `DomainException`
Exceção raiz para todos os erros de domínio.

```python
try:
    await service.transcribe(video)
except DomainException as e:
    # Captura QUALQUER erro de domínio
    log.error(f"Erro de domínio: {e}")
```

### `VideoDownloadError`
Erro ao baixar vídeo do YouTube.

```python
try:
    video = await downloader.download(url, path)
except VideoDownloadError as e:
    print(f"Falha no download: {e}")
```

### `TranscriptionError`
Erro ao transcrever áudio.

```python
try:
    transcription = await service.transcribe(video)
except TranscriptionError as e:
    print(f"Falha na transcrição: {e}")
```

---

## Exceções Granulares (v2.1)

### `AudioTooLongError`
Áudio excede duração máxima permitida.

```python
try:
    validate_audio_duration(video, max_duration=3600)
except AudioTooLongError as e:
    print(f"Áudio muito longo: {e.duration}s (máx: {e.max_duration}s)")
```

**Atributos**:
- `duration: float` - Duração real do áudio
- `max_duration: float` - Duração máxima permitida

### `AudioCorruptedError`
Arquivo de áudio corrompido ou ilegível.

```python
try:
    await service.transcribe(video)
except AudioCorruptedError as e:
    print(f"Arquivo corrompido: {e.file_path}")
    print(f"Razão: {e.reason}")
```

**Atributos**:
- `file_path: str` - Caminho do arquivo
- `reason: str` - Motivo da corrupção

### `ModelLoadError`
Erro ao carregar modelo Whisper.

```python
try:
    service = WhisperService(model="large")
except ModelLoadError as e:
    print(f"Falha ao carregar '{e.model_name}': {e.reason}")
```

**Atributos**:
- `model_name: str` - Nome do modelo (tiny, base, etc.)
- `reason: str` - Motivo do erro

### `WorkerPoolError`
Erro no pool de workers de transcrição.

```python
try:
    result = await parallel_service.transcribe(video)
except WorkerPoolError as e:
    print(f"Worker {e.worker_id} falhou: {e.reason}")
```

**Atributos**:
- `worker_id: int` - ID do worker (opcional)
- `reason: str` - Motivo do erro

### `FFmpegError`
Erro ao executar FFmpeg.

```python
try:
    await ffmpeg_optimizer.optimize(audio_path)
except FFmpegError as e:
    print(f"Comando: {e.command}")
    print(f"Erro: {e.stderr[:200]}")
```

**Atributos**:
- `command: str` - Comando FFmpeg executado
- `stderr: str` - Saída de erro (stderr)

### `OperationTimeoutError`
Operação excedeu tempo limite.

```python
try:
    video = await downloader.download(url, timeout=300)
except OperationTimeoutError as e:
    print(f"Operação '{e.operation}' timeout após {e.timeout}s")
```

**Atributos**:
- `operation: str` - Nome da operação
- `timeout: float` - Tempo limite em segundos

### `QuotaExceededError`
Quota/limite de uso excedido.

```python
try:
    await rate_limiter.acquire()
except QuotaExceededError as e:
    print(f"Quota excedida: {e.current}/{e.limit} {e.resource}")
```

**Atributos**:
- `resource: str` - Recurso limitado
- `limit: int` - Limite máximo
- `current: int` - Uso atual

---

## Exemplo de Uso

```python
from src.domain.exceptions import (
    DomainException,
    TranscriptionError,
    AudioTooLongError,
    ModelLoadError
)

async def transcribe_video(video: VideoFile):
    try:
        # Validar duração
        if video.duration > 3600:
            raise AudioTooLongError(
                duration=video.duration,
                max_duration=3600
            )
        
        # Carregar modelo
        try:
            service = WhisperService(model="large")
        except Exception as e:
            raise ModelLoadError(
                model_name="large",
                reason=str(e)
            )
        
        # Transcrever
        return await service.transcribe(video)
    
    except AudioTooLongError as e:
        log.warning(f"Áudio muito longo: {e.duration}s")
        raise
    
    except ModelLoadError as e:
        log.error(f"Erro ao carregar modelo: {e.reason}")
        # Fallback para modelo menor
        service = WhisperService(model="base")
        return await service.transcribe(video)
    
    except TranscriptionError as e:
        log.error(f"Erro na transcrição: {e}")
        raise
    
    except DomainException as e:
        log.error(f"Erro de domínio: {e}")
        raise
```

---

## Testes

```python
def test_audio_too_long_error():
    error = AudioTooLongError(duration=7200, max_duration=3600)
    assert error.duration == 7200
    assert error.max_duration == 3600
    assert "7200" in str(error)
    assert "3600" in str(error)

def test_model_load_error():
    error = ModelLoadError(model_name="large", reason="CUDA out of memory")
    assert error.model_name == "large"
    assert "CUDA" in error.reason

def test_ffmpeg_error():
    error = FFmpegError(
        command="ffmpeg -i input.mp4",
        stderr="Invalid codec"
    )
    assert error.command == "ffmpeg -i input.mp4"
    assert "Invalid" in error.stderr
```

---

[⬅️ Voltar](README.md)

**Versão**: 3.0.0