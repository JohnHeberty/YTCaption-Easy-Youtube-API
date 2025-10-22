# ITranscriptionService Interface

Interface (ABC) que define o contrato para serviços de transcrição.

---

## Visão Geral

`ITranscriptionService` é uma **Interface** que:
- Define o contrato para transcrição de áudio/vídeo
- Segue o **Dependency Inversion Principle** (SOLID)
- Permite múltiplas implementações (Whisper, OpenAI API, etc.)

**Arquivo**: `src/domain/interfaces/transcription_service.py`

---

## Métodos

### `transcribe(video_file, language="auto") -> Transcription`
Transcreve um arquivo de vídeo.

**Parâmetros**:
- `video_file: VideoFile` - Arquivo de vídeo para transcrever
- `language: str` - Idioma do vídeo (`"auto"` para detecção automática)

**Retorno**: `Transcription` - Entidade com a transcrição completa

**Exceções**: `TranscriptionError` - Erro na transcrição

```python
service: ITranscriptionService = WhisperService()
transcription = await service.transcribe(video_file, language="pt")
print(transcription.get_full_text())
```

### `detect_language(video_file) -> str`
Detecta o idioma do áudio.

**Parâmetros**:
- `video_file: VideoFile` - Arquivo de vídeo

**Retorno**: `str` - Código do idioma detectado (ISO 639-1)

**Exceções**: `TranscriptionError` - Erro na detecção

```python
language = await service.detect_language(video_file)
print(f"Idioma detectado: {language}")  # "pt"
```

---

## Implementações

### `WhisperTranscriptionService` (Infrastructure)
Implementação usando **OpenAI Whisper** (v2.0 com Parallel Processing).

**Localização**: `src/infrastructure/whisper/transcription_service.py`

**Características**:
- Modelos: tiny, base, small, medium, large
- Detecção automática de idioma
- Chunking inteligente de áudio
- GPU acceleration (CUDA/CPU fallback)

### `ParallelWhisperService` (v2.0+)
Implementação com **processamento paralelo**.

**Localização**: `src/infrastructure/whisper/parallel_transcription_service.py`

**Características**:
- Worker pool persistente
- Processamento de chunks paralelos
- 7-10x speedup (vs sequencial)
- Memory-efficient chunking

---

## Exemplo de Uso

```python
from src.domain.interfaces import ITranscriptionService
from src.infrastructure.whisper import ParallelWhisperService

async def transcribe_video(
    service: ITranscriptionService,
    video_file: VideoFile
):
    # Detectar idioma
    language = await service.detect_language(video_file)
    print(f"Idioma: {language}")
    
    # Transcrever
    transcription = await service.transcribe(video_file, language)
    
    # Exportar SRT
    srt_path = Path("output.srt")
    srt_path.write_text(transcription.to_srt())
    
    return transcription

# Injetar implementação
service = ParallelWhisperService(model="base", num_workers=4)
result = await transcribe_video(service, video_file)
```

---

## Dependency Inversion

```python
# ❌ ERRADO: Depender de implementação concreta
from src.infrastructure.whisper import WhisperTranscriptionService

class TranscribeUseCase:
    def __init__(self):
        self.service = WhisperTranscriptionService()  # Acoplamento

# ✅ CORRETO: Depender de abstração
from src.domain.interfaces import ITranscriptionService

class TranscribeUseCase:
    def __init__(self, service: ITranscriptionService):
        self.service = service  # Flexível
```

**Benefícios**:
- Testar com mock (sem carregar Whisper)
- Trocar implementação (Whisper → OpenAI API)
- Domínio desacoplado de infraestrutura

---

## Testes

```python
class MockTranscriptionService(ITranscriptionService):
    async def transcribe(self, video_file, language="auto"):
        return Transcription(
            youtube_url="https://youtu.be/123",
            segments=[
                TranscriptionSegment("Test", start=0, end=2)
            ],
            language="en"
        )
    
    async def detect_language(self, video_file):
        return "en"

# Usar mock nos testes
async def test_transcribe_use_case():
    mock_service = MockTranscriptionService()
    use_case = TranscribeUseCase(service=mock_service)
    
    result = await use_case.execute(video_file)
    assert result.language == "en"
```

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0