# YouTubeURL Value Object

Value Object que representa URLs validadas do YouTube.

---

## Visão Geral

`YouTubeURL` é um **Value Object** imutável que encapsula:
- URL validada do YouTube
- Video ID extraído
- Validação automática via regex

**Arquivo**: `src/domain/value_objects/youtube_url.py`

---

## Estrutura

```python
@dataclass(frozen=True)  # Imutável
class YouTubeURL:
    url: str       # URL completa
    video_id: str  # ID do vídeo (ex: "dQw4w9WgXcQ")
```

---

## Criação

### `create(url: str) -> YouTubeURL`
Factory method para criar instâncias validadas.

```python
from src.domain.value_objects import YouTubeURL

# URLs válidas
url1 = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
url2 = YouTubeURL.create("https://youtu.be/dQw4w9WgXcQ")
url3 = YouTubeURL.create("https://m.youtube.com/watch?v=dQw4w9WgXcQ")

print(url1.video_id)  # "dQw4w9WgXcQ"

# URL inválida lança exceção
try:
    invalid = YouTubeURL.create("https://vimeo.com/123456")
except ValueError as e:
    print(e)  # "URL inválida do YouTube"
```

---

## Formatos Suportados

| Formato | Exemplo |
|---------|---------|
| Standard | `https://www.youtube.com/watch?v=VIDEO_ID` |
| Short | `https://youtu.be/VIDEO_ID` |
| Mobile | `https://m.youtube.com/watch?v=VIDEO_ID` |
| Embed | `https://www.youtube.com/embed/VIDEO_ID` |

---

## Validação

Regex usado:
```python
_YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.|m\.)?'
    r'(youtube\.com|youtu\.be)/'
    r'(watch\?v=|embed/)?([a-zA-Z0-9_-]{11})'
)
```

**Regras**:
- Protocol: http ou https (opcional)
- Domain: youtube.com, youtu.be, m.youtube.com
- Video ID: 11 caracteres alfanuméricos + `-_`

---

## Exemplo Completo

```python
from src.domain.value_objects import YouTubeURL

# Criar URL validada
url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# Acessar propriedades (readonly)
print(f"URL: {url.url}")
print(f"Video ID: {url.video_id}")

# Passar para serviços
downloader.download(url)
transcriber.transcribe(url)

# Comparação (value equality)
url1 = YouTubeURL.create("https://youtu.be/dQw4w9WgXcQ")
url2 = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(url1.video_id == url2.video_id)  # True (mesmo vídeo)
```

---

## Regras de Negócio

1. **Imutabilidade**: `frozen=True` impede modificações
2. **Validação**: Lança `ValueError` para URLs inválidas
3. **Video ID**: Sempre 11 caracteres
4. **Factory Pattern**: Use `create()`, não construtor direto

---

## Testes

```python
def test_youtube_url_valid():
    url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert url.video_id == "dQw4w9WgXcQ"

def test_youtube_url_short_format():
    url = YouTubeURL.create("https://youtu.be/dQw4w9WgXcQ")
    assert url.video_id == "dQw4w9WgXcQ"

def test_youtube_url_invalid():
    with pytest.raises(ValueError):
        YouTubeURL.create("https://vimeo.com/123456")

def test_youtube_url_immutable():
    url = YouTubeURL.create("https://youtu.be/123")
    with pytest.raises(FrozenInstanceError):
        url.video_id = "456"
```

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0