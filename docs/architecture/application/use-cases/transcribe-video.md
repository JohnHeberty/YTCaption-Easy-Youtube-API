# TranscribeYouTubeVideoUseCase

Use Case principal que orquestra o processo de transcrição de vídeos do YouTube.

---

## Responsabilidade

Coordenar download de vídeo + transcrição + cache + cleanup.

**Arquivo**: `src/application/use_cases/transcribe_video.py`

---

## Fluxo de Execução

```
1. Validar URL do YouTube
2. Verificar se deve usar YouTube Transcript
   ├── SIM → Obter legendas do YouTube (rápido)
   └── NÃO → Continuar com Whisper
3. Criar diretório temporário
4. Baixar vídeo
5. [v2.2.1] Verificar cache usando file_hash
   ├── HIT → Retornar resultado em cache
   └── MISS → Continuar processamento
6. [v2.0] Validar áudio (duração, integridade)
7. [v2.1] Transcrever com Whisper + timeout global
8. [v2.2.1] Salvar no cache
9. Limpar arquivos temporários
10. Retornar resposta
```

---

## Parâmetros do Construtor

```python
def __init__(
    self,
    video_downloader: IVideoDownloader,
    transcription_service: ITranscriptionService,
    storage_service: IStorageService,
    cleanup_after_processing: bool = True,
    max_video_duration: int = 10800,  # 3h
    audio_validator=None,  # v2.0
    transcription_cache=None  # v2.0
)
```

---

## Método Principal

### `execute(request: TranscribeRequestDTO) -> TranscribeResponseDTO`

**Entrada**: `TranscribeRequestDTO`
- `youtube_url` - URL do YouTube
- `language` - Idioma ("auto" para detecção automática)
- `use_youtube_transcript` - Usar legendas do YouTube (v2.0)
- `prefer_manual_subtitles` - Preferir legendas manuais (v2.0)

**Saída**: `TranscribeResponseDTO`
- `transcription_id` - UUID único
- `youtube_url` - URL do vídeo
- `video_id` - ID do vídeo
- `language` - Idioma detectado
- `full_text` - Texto completo
- `segments` - Lista de segmentos com timestamps
- `total_segments` - Número de segmentos
- `duration` - Duração total (segundos)
- `processing_time` - Tempo de processamento (segundos)
- `source` - "whisper" ou "youtube_transcript"

**Exceções**:
- `ValidationError` - URL inválida, áudio corrompido
- `VideoDownloadError` - Falha no download
- `TranscriptionError` - Falha na transcrição
- `OperationTimeoutError` - Timeout na transcrição (v2.1)

---

## Exemplo Completo

```python
from src.application.use_cases import TranscribeYouTubeVideoUseCase
from src.application.dtos import TranscribeRequestDTO

# Criar Use Case
use_case = TranscribeYouTubeVideoUseCase(
    video_downloader=downloader,
    transcription_service=whisper_service,
    storage_service=storage,
    cleanup_after_processing=True,
    max_video_duration=10800,
    audio_validator=validator,  # v2.0
    transcription_cache=cache    # v2.0
)

# Exemplo 1: Transcrição com Whisper
request1 = TranscribeRequestDTO(
    youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    language="auto"
)
response1 = await use_case.execute(request1)

# Exemplo 2: Usar legendas do YouTube (rápido)
request2 = TranscribeRequestDTO(
    youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    use_youtube_transcript=True,
    prefer_manual_subtitles=True
)
response2 = await use_case.execute(request2)

# Processar resposta
print(f"ID: {response1.transcription_id}")
print(f"Idioma: {response1.language}")
print(f"Segmentos: {response1.total_segments}")
print(f"Duração: {response1.duration:.1f}s")
print(f"Processamento: {response1.processing_time:.2f}s")
print(f"Fonte: {response1.source}")
print(f"\nTexto completo:\n{response1.full_text}")
```

---

## Novidades por Versão

### v2.0
- ✅ Cache de transcrições
- ✅ Validação de áudio antes de processar
- ✅ Suporte a YouTube Transcript (rápido)
- ✅ Estimativa de tempo de processamento

### v2.1
- ✅ Timeout global na transcrição
- ✅ Exceções granulares (`AudioTooLongError`, `OperationTimeoutError`)
- ✅ Logging melhorado

### v2.2.1
- ✅ Cache reimplementado com `file_hash` (após download)
- ✅ Cache mais confiável (não depende de URL, usa hash do arquivo)

---

## Timeout Dinâmico (v2.1)

O Use Case calcula timeout dinamicamente baseado em:
- Duração do áudio
- Modelo Whisper usado
- Fatores de processamento (realtime factor)

```python
# Fatores por modelo
tiny:   2.0x realtime  # ~2x mais rápido que duração
base:   1.5x realtime
small:  0.8x realtime
medium: 0.4x realtime
large:  0.2x realtime

# Exemplo: áudio de 60s com modelo "base"
base_time = 60 / 1.5 = 40s
overhead = 40 * 0.2 = 8s
safety = 40 * 0.5 = 20s
timeout = 40 + 8 + 20 = 68s
```

---

## Cache (v2.2.1)

**Chave do Cache**: `file_hash + model_name + language`

```python
# Hash calculado APÓS download
file_hash = compute_file_hash(video_file.file_path)

# Verificar cache
cached = cache.get(
    file_hash=file_hash,
    model_name="base",
    language="en"
)

if cached:
    return cached  # Cache HIT
else:
    # Cache MISS → processar
    result = await transcribe(video_file)
    
    # Salvar no cache
    cache.put(
        file_hash=file_hash,
        transcription_data=result,
        model_name="base",
        language="en"
    )
```

**Benefícios**:
- Mesmo vídeo processado uma única vez
- Cache funciona mesmo com URLs diferentes
- Baseado no conteúdo real do arquivo (hash SHA256)

---

## Testes

```python
async def test_transcribe_success():
    use_case = TranscribeYouTubeVideoUseCase(
        video_downloader=mock_downloader,
        transcription_service=mock_transcription,
        storage_service=mock_storage
    )
    
    request = TranscribeRequestDTO(
        youtube_url="https://youtu.be/dQw4w9WgXcQ",
        language="en"
    )
    
    response = await use_case.execute(request)
    
    assert response.language == "en"
    assert response.total_segments > 0
    assert response.source == "whisper"

async def test_transcribe_with_cache():
    cache = TranscriptionCache()
    use_case = TranscribeYouTubeVideoUseCase(
        transcription_cache=cache,
        # ...
    )
    
    # Primeira execução (cache MISS)
    response1 = await use_case.execute(request)
    
    # Segunda execução (cache HIT)
    response2 = await use_case.execute(request)
    
    assert response1.transcription_id == response2.transcription_id
    assert response2.processing_time < response1.processing_time

async def test_transcribe_timeout():
    # Simular transcrição lenta
    async def slow_transcribe(*args, **kwargs):
        await asyncio.sleep(100)
    
    mock_service = AsyncMock()
    mock_service.transcribe = slow_transcribe
    
    use_case = TranscribeYouTubeVideoUseCase(
        transcription_service=mock_service,
        # ...
    )
    
    with pytest.raises(OperationTimeoutError):
        await use_case.execute(request)
```

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0