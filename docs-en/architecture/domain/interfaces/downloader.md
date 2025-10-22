# IVideoDownloader Interface

Interface (ABC) que define o contrato para downloaders de vídeo.

---

## Visão Geral

`IVideoDownloader` é uma **Interface** (Abstract Base Class) que:
- Define o contrato para download de vídeos do YouTube
- Segue o **Dependency Inversion Principle** (SOLID)
- Permite múltiplas implementações (yt-dlp, youtube-dl, etc.)

**Arquivo**: `src/domain/interfaces/video_downloader.py`

---

## Métodos

### `download(url, output_path) -> VideoFile`
Baixa um vídeo do YouTube.

**Parâmetros**:
- `url: YouTubeURL` - URL validada do vídeo
- `output_path: Path` - Caminho onde salvar o arquivo

**Retorno**: `VideoFile` - Entidade representando o arquivo baixado

**Exceções**: `VideoDownloadError` - Erro no download

```python
downloader: IVideoDownloader = YouTubeDownloader()
url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
video = await downloader.download(url, Path("temp/video.mp4"))
print(f"Baixado: {video.file_size_mb:.2f} MB")
```

### `get_video_info(url) -> dict`
Obtém informações sobre o vídeo sem baixá-lo.

**Parâmetros**:
- `url: YouTubeURL` - URL do vídeo

**Retorno**: `dict` - Informações do vídeo (título, duração, formato, etc.)

**Exceções**: `VideoDownloadError` - Erro ao obter informações

```python
info = await downloader.get_video_info(url)
print(f"Título: {info['title']}")
print(f"Duração: {info['duration']}s")
```

---

## Implementações

### `YouTubeDownloader` (Infrastructure)
Implementação usando **yt-dlp** (v3.0 com Resilience System).

**Localização**: `src/infrastructure/youtube/downloader.py`

**Características**:
- 7 estratégias de download (Standard → Tor)
- Rate limiting adaptativo
- User-agent rotation
- Proxy support
- Circuit breaker pattern

---

## Exemplo de Uso

```python
from src.domain.interfaces import IVideoDownloader
from src.domain.value_objects import YouTubeURL
from src.infrastructure.youtube import YouTubeDownloader

# Usar interface (não implementação direta)
async def download_video(downloader: IVideoDownloader, url_str: str):
    url = YouTubeURL.create(url_str)
    
    # Obter informações
    info = await downloader.get_video_info(url)
    print(f"Baixando: {info['title']}")
    
    # Fazer download
    video = await downloader.download(url, Path("temp/video.mp4"))
    print(f"Sucesso: {video.file_size_mb:.2f} MB")
    
    return video

# Injetar implementação
downloader = YouTubeDownloader()
video = await download_video(downloader, "https://youtu.be/dQw4w9WgXcQ")
```

---

## Dependency Inversion

```python
# ❌ ERRADO: Depender de implementação concreta
from src.infrastructure.youtube import YouTubeDownloader

class TranscribeVideoUseCase:
    def __init__(self):
        self.downloader = YouTubeDownloader()  # Acoplamento forte

# ✅ CORRETO: Depender de abstração
from src.domain.interfaces import IVideoDownloader

class TranscribeVideoUseCase:
    def __init__(self, downloader: IVideoDownloader):
        self.downloader = downloader  # Flexível
```

**Benefícios**:
- Testabilidade (mock da interface)
- Flexibilidade (trocar implementação)
- Desacoplamento (domínio não conhece infraestrutura)

---

## Testes

```python
from unittest.mock import AsyncMock

class MockVideoDownloader(IVideoDownloader):
    async def download(self, url, output_path):
        return VideoFile(file_path=output_path, file_size_bytes=1024)
    
    async def get_video_info(self, url):
        return {"title": "Test Video", "duration": 120}

# Usar mock nos testes
async def test_transcribe_use_case():
    mock_downloader = MockVideoDownloader()
    use_case = TranscribeVideoUseCase(downloader=mock_downloader)
    
    result = await use_case.execute("https://youtu.be/123")
    assert result.success
```

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0