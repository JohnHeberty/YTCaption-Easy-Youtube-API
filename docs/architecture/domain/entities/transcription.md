# Transcription Entity

Entidade principal que representa uma transcrição completa de vídeo.

---

## Visão Geral

`Transcription` é uma **Entity** do Domain-Driven Design (DDD), representando uma transcrição completa com:
- Identidade única (UUID)
- Estado mutável (pode adicionar segmentos)
- Ciclo de vida (criação → processamento → finalização)
- Regras de negócio encapsuladas

**Arquivo**: `src/domain/entities/transcription.py`

---

## Estrutura

```python
@dataclass
class Transcription:
    id: str                                    # UUID único
    youtube_url: Optional[YouTubeURL]          # URL do vídeo
    segments: List[TranscriptionSegment]       # Segmentos com timestamp
    language: Optional[str]                    # Idioma ("en", "pt", etc.)
    created_at: datetime                       # Data de criação
    processing_time: Optional[float]           # Tempo de processamento (segundos)
```

---

## Propriedades

### `duration` (readonly)
Retorna a duração total da transcrição em segundos.

```python
transcription.duration  # 125.5 (em segundos)
```

**Implementação**:
```python
@property
def duration(self) -> float:
    if not self.segments:
        return 0.0
    return max(segment.end for segment in self.segments)
```

### `is_complete` (readonly)
Verifica se a transcrição está completa (tem segmentos e idioma).

```python
transcription.is_complete  # True ou False
```

**Implementação**:
```python
@property
def is_complete(self) -> bool:
    return len(self.segments) > 0 and self.language is not None
```

---

## Métodos

### `add_segment(segment: TranscriptionSegment) -> None`
Adiciona um segmento de transcrição.

```python
segment = TranscriptionSegment(
    text="Hello, world!",
    start=0.0,
    end=2.5
)
transcription.add_segment(segment)
```

---

### `get_full_text() -> str`
Retorna o texto completo concatenando todos os segmentos.

```python
text = transcription.get_full_text()
# "Hello, world! This is a test. Goodbye!"
```

**Implementação**:
```python
def get_full_text(self) -> str:
    return " ".join(segment.text for segment in self.segments)
```

---

### `to_srt() -> str`
Converte transcrição para formato SRT (legendas).

**Exemplo de saída**:
```srt
1
00:00:00,000 --> 00:00:02,500
Hello, world!

2
00:00:02,500 --> 00:00:05,000
This is a test.
```

**Uso**:
```python
srt_content = transcription.to_srt()
with open("subtitles.srt", "w") as f:
    f.write(srt_content)
```

---

### `to_vtt() -> str`
Converte transcrição para formato WebVTT (legendas web).

**Exemplo de saída**:
```vtt
WEBVTT

00:00:00.000 --> 00:00:02.500
Hello, world!

00:00:02.500 --> 00:00:05.000
This is a test.
```

**Uso**:
```python
vtt_content = transcription.to_vtt()
with open("subtitles.vtt", "w") as f:
    f.write(vtt_content)
```

---

### `to_dict() -> dict`
Converte transcrição para dicionário (serialização).

**Saída**:
```python
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "video_id": "dQw4w9WgXcQ",
    "language": "en",
    "full_text": "Hello, world! This is a test.",
    "segments": [
        {
            "text": "Hello, world!",
            "start": 0.0,
            "end": 2.5,
            "duration": 2.5
        },
        {
            "text": "This is a test.",
            "start": 2.5,
            "end": 5.0,
            "duration": 2.5
        }
    ],
    "created_at": "2025-10-22T10:30:00",
    "processing_time": 12.5,
    "total_segments": 2
}
```

**Uso**:
```python
data = transcription.to_dict()
import json
json_str = json.dumps(data, indent=2)
```

---

## Criação

### Método 1: Construtor padrão
```python
from src.domain.entities import Transcription
from src.domain.value_objects import YouTubeURL

url = YouTubeURL.create("https://youtube.com/watch?v=dQw4w9WgXcQ")

transcription = Transcription(
    youtube_url=url,
    language="en"
)
# ID gerado automaticamente (UUID4)
# created_at definido automaticamente (agora)
# segments inicializado como lista vazia
```

### Método 2: Com ID específico (reconstrução)
```python
transcription = Transcription(
    id="550e8400-e29b-41d4-a716-446655440000",
    youtube_url=url,
    language="en"
)
```

---

## Exemplo Completo

```python
from src.domain.entities import Transcription
from src.domain.value_objects import TranscriptionSegment, YouTubeURL

# 1. Criar transcrição
url = YouTubeURL.create("https://youtube.com/watch?v=dQw4w9WgXcQ")
transcription = Transcription(
    youtube_url=url,
    language="en"
)

# 2. Adicionar segmentos
segments_data = [
    {"text": "Never gonna give you up", "start": 0.0, "end": 2.5},
    {"text": "Never gonna let you down", "start": 2.5, "end": 5.0},
    {"text": "Never gonna run around", "start": 5.0, "end": 7.5},
]

for seg_data in segments_data:
    segment = TranscriptionSegment(**seg_data)
    transcription.add_segment(segment)

# 3. Verificar estado
print(f"Complete: {transcription.is_complete}")      # True
print(f"Duration: {transcription.duration}s")        # 7.5
print(f"Segments: {len(transcription.segments)}")    # 3

# 4. Obter texto completo
full_text = transcription.get_full_text()
print(full_text)
# "Never gonna give you up Never gonna let you down Never gonna run around"

# 5. Exportar para SRT
srt_content = transcription.to_srt()
with open("rickroll.srt", "w", encoding="utf-8") as f:
    f.write(srt_content)

# 6. Serializar para JSON
import json
data = transcription.to_dict()
with open("transcription.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
```

---

## Regras de Negócio

1. **ID Único**: Sempre gerado como UUID4 se não especificado
2. **Segmentos Ordenados**: Segmentos devem ser adicionados em ordem cronológica
3. **Completude**: Transcrição completa = tem segmentos + tem idioma
4. **Duração**: Calculada a partir do último segmento (`max(segment.end)`)
5. **Idioma**: Código ISO 639-1 (2 letras: "en", "pt", "es", etc.)

---

## Testes

```python
# tests/unit/domain/entities/test_transcription.py
import pytest
from src.domain.entities import Transcription
from src.domain.value_objects import TranscriptionSegment, YouTubeURL

def test_create_transcription():
    url = YouTubeURL.create("https://youtube.com/watch?v=123")
    transcription = Transcription(youtube_url=url, language="en")
    
    assert transcription.id  # UUID gerado
    assert transcription.youtube_url == url
    assert transcription.language == "en"
    assert len(transcription.segments) == 0

def test_add_segment():
    transcription = Transcription(language="en")
    segment = TranscriptionSegment(text="Hello", start=0.0, end=2.0)
    
    transcription.add_segment(segment)
    
    assert len(transcription.segments) == 1
    assert transcription.segments[0] == segment

def test_get_full_text():
    transcription = Transcription(language="en")
    transcription.add_segment(TranscriptionSegment(text="Hello", start=0.0, end=1.0))
    transcription.add_segment(TranscriptionSegment(text="World", start=1.0, end=2.0))
    
    assert transcription.get_full_text() == "Hello World"

def test_duration():
    transcription = Transcription(language="en")
    transcription.add_segment(TranscriptionSegment(text="A", start=0.0, end=2.5))
    transcription.add_segment(TranscriptionSegment(text="B", start=2.5, end=7.5))
    
    assert transcription.duration == 7.5

def test_is_complete():
    transcription = Transcription()
    assert not transcription.is_complete  # Sem segmentos, sem idioma
    
    transcription.language = "en"
    assert not transcription.is_complete  # Tem idioma, mas sem segmentos
    
    transcription.add_segment(TranscriptionSegment(text="A", start=0.0, end=1.0))
    assert transcription.is_complete  # Tem ambos!

def test_to_srt():
    transcription = Transcription(language="en")
    transcription.add_segment(TranscriptionSegment(text="Hello", start=0.0, end=2.5))
    
    srt = transcription.to_srt()
    
    assert "1\n" in srt
    assert "00:00:00,000 --> 00:00:02,500" in srt
    assert "Hello" in srt

def test_to_vtt():
    transcription = Transcription(language="en")
    transcription.add_segment(TranscriptionSegment(text="Hello", start=0.0, end=2.5))
    
    vtt = transcription.to_vtt()
    
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:02.500" in vtt
    assert "Hello" in vtt

def test_to_dict():
    url = YouTubeURL.create("https://youtube.com/watch?v=123")
    transcription = Transcription(youtube_url=url, language="en")
    transcription.add_segment(TranscriptionSegment(text="Hi", start=0.0, end=1.0))
    
    data = transcription.to_dict()
    
    assert data["id"]
    assert data["youtube_url"] == str(url)
    assert data["video_id"] == "123"
    assert data["language"] == "en"
    assert data["full_text"] == "Hi"
    assert len(data["segments"]) == 1
    assert data["total_segments"] == 1
```

---

## Próximos Passos

- [VideoFile Entity](./video-file.md) - Entidade de arquivo de vídeo
- [TranscriptionSegment Value Object](../value-objects/transcription-segment.md) - Segmento de transcrição
- [YouTubeURL Value Object](../value-objects/youtube-url.md) - URL validada

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0  
**Última Atualização**: 22 de outubro de 2025