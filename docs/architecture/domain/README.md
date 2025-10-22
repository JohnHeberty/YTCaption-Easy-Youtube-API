# Domain Layer - Camada de Domínio

Documentação completa da camada Domain (regras de negócio puras).

---

## 📋 Índice

### Entities (Entidades)
- [Transcription](./entities/transcription.md) - Entidade principal de transcrição
- [VideoFile](./entities/video-file.md) - Entidade de arquivo de vídeo

### Value Objects (Objetos de Valor)
- [YouTubeURL](./value-objects/youtube-url.md) - URL validada do YouTube
- [TranscriptionSegment](./value-objects/transcription-segment.md) - Segmento de transcrição com timestamp

### Interfaces (Contratos)
- [IVideoDownloader](./interfaces/downloader.md) - Interface para download de vídeos
- [ITranscriptionService](./interfaces/transcription-service.md) - Interface para serviço de transcrição
- [IStorageService](./interfaces/storage-service.md) - Interface para gerenciamento de armazenamento

### Exceptions
- [Domain Exceptions](./exceptions.md) - Exceções específicas do domínio

---

## Visão Geral

A **Domain Layer** é o coração da aplicação, contendo toda a lógica de negócio pura, sem dependências externas.

### Princípios

1. **Zero Dependências Externas**
   - Sem frameworks (FastAPI, Whisper, yt-dlp)
   - Sem I/O (file system, network, database)
   - Apenas Python puro

2. **Imutabilidade**
   - Value Objects são imutáveis (`frozen=True`)
   - Entities têm estado mutável controlado

3. **Validação no Construtor**
   - Objetos sempre válidos após criação
   - Exceções levantadas em `__post_init__`

4. **Rich Domain Model**
   - Métodos de negócio nas entidades
   - Comportamento encapsulado

---

## Estrutura

```
src/domain/
├── entities/               # Objetos com identidade
│   ├── transcription.py    # Transcrição completa com ID
│   └── video_file.py       # Arquivo de vídeo com ID
│
├── value_objects/          # Objetos imutáveis
│   ├── youtube_url.py      # URL validada (frozen)
│   └── transcription_segment.py  # Segmento (frozen)
│
├── interfaces/             # Contratos (ABCs)
│   ├── video_downloader.py
│   ├── transcription_service.py
│   └── storage_service.py
│
└── exceptions.py           # Exceções de domínio
```

---

## Diferença: Entity vs Value Object

### Entity (Entidade)

**Características**:
- Tem identidade única (ID)
- Mutável (estado pode mudar)
- Comparação por ID
- Tem ciclo de vida

**Exemplo**: `Transcription`
```python
transcription1 = Transcription(id="123")
transcription2 = Transcription(id="123")
transcription1 == transcription2  # True (mesmo ID)

transcription1.add_segment(segment)  # Mutável
```

### Value Object (Objeto de Valor)

**Características**:
- Sem identidade (sem ID)
- Imutável (`frozen=True`)
- Comparação por valor
- Sem ciclo de vida

**Exemplo**: `YouTubeURL`
```python
url1 = YouTubeURL("https://youtube.com/watch?v=123")
url2 = YouTubeURL("https://youtube.com/watch?v=123")
url1 == url2  # True (mesmo valor)

url1.url = "outro"  # ERRO! Imutável
```

---

## Regras de Negócio

### YouTubeURL
- ✅ Aceita: `youtube.com`, `youtu.be`, `m.youtube.com`
- ✅ Extrai video ID automaticamente
- ❌ Rejeita: URLs de outros sites

### TranscriptionSegment
- ✅ `start >= 0` (não negativo)
- ✅ `end >= start` (fim após início)
- ✅ `text` não vazio
- ✅ Duração calculada: `end - start`

### Transcription
- ✅ Gera ID único (UUID4)
- ✅ Agregar segmentos (`add_segment`)
- ✅ Exportar formatos: SRT, VTT, dict
- ✅ Calcular duração total
- ✅ Validar completude

---

## Exemplos de Uso

### Criando Transcrição

```python
from src.domain.entities import Transcription
from src.domain.value_objects import TranscriptionSegment, YouTubeURL

# 1. Criar URL validada
url = YouTubeURL.create("https://youtube.com/watch?v=dQw4w9WgXcQ")

# 2. Criar transcrição
transcription = Transcription(
    youtube_url=url,
    language="en"
)

# 3. Adicionar segmentos
segment1 = TranscriptionSegment(
    text="Hello, world!",
    start=0.0,
    end=2.5
)
transcription.add_segment(segment1)

# 4. Obter texto completo
full_text = transcription.get_full_text()  # "Hello, world!"

# 5. Exportar para SRT
srt_content = transcription.to_srt()
```

### Validação Automática

```python
# ❌ URL inválida
try:
    url = YouTubeURL.create("https://vimeo.com/123")
except ValueError as e:
    print(e)  # "Invalid YouTube URL"

# ❌ Segmento inválido
try:
    segment = TranscriptionSegment(
        text="",  # Vazio!
        start=0.0,
        end=2.0
    )
except ValueError as e:
    print(e)  # "Text cannot be empty"

# ❌ Tempo inválido
try:
    segment = TranscriptionSegment(
        text="Hello",
        start=5.0,
        end=2.0  # Fim antes do início!
    )
except ValueError as e:
    print(e)  # "End time must be greater than or equal to start time"
```

---

## Interfaces (Contratos)

Interfaces definem **contratos** que a Infrastructure Layer deve implementar.

### Por que Interfaces?

**Dependency Inversion Principle (SOLID)**:
- Domain depende de **abstrações** (interfaces)
- Infrastructure implementa as interfaces
- Fácil de mockar em testes
- Fácil de trocar implementações

**Exemplo**:
```python
# Domain define a interface
class ITranscriptionService(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> Transcription:
        ...

# Infrastructure implementa
class WhisperTranscriptionService(ITranscriptionService):
    def transcribe(self, audio_path: Path) -> Transcription:
        # Implementação real com Whisper
        pass

# Application usa a interface
class TranscribeVideoUseCase:
    def __init__(self, transcriber: ITranscriptionService):
        self._transcriber = transcriber  # Depende da interface!
```

---

## Exceções de Domínio

Exceções específicas para erros de negócio:

```python
# src/domain/exceptions.py
class DomainException(Exception):
    """Base exception for domain layer"""
    pass

class InvalidYouTubeURLError(DomainException):
    """Invalid YouTube URL format"""
    pass

class InvalidTranscriptionSegmentError(DomainException):
    """Invalid transcription segment"""
    pass
```

**Uso**:
```python
if not self._is_valid_youtube_url(url):
    raise InvalidYouTubeURLError(f"Invalid URL: {url}")
```

---

## Testes de Domain Layer

Domain Layer é **100% testável** sem mocks:

```python
# tests/unit/domain/test_youtube_url.py
def test_valid_youtube_url():
    url = YouTubeURL.create("https://youtube.com/watch?v=123")
    assert url.video_id == "123"

def test_invalid_youtube_url():
    with pytest.raises(ValueError):
        YouTubeURL.create("https://vimeo.com/123")

def test_transcription_segment_duration():
    segment = TranscriptionSegment(
        text="Hello",
        start=0.0,
        end=2.5
    )
    assert segment.duration == 2.5
```

**Vantagens**:
- Testes rápidos (<1ms)
- Sem dependências externas
- Sem mocks necessários
- Alta cobertura (>90%)

---

## Próximos Passos

- [Transcription Entity](./entities/transcription.md) - Entidade principal
- [YouTubeURL Value Object](./value-objects/youtube-url.md) - URL validada
- [Application Layer](../application/README.md) - Casos de uso

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0  
**Última Atualização**: 22 de outubro de 2025  
**Mantido por**: YTCaption Team
