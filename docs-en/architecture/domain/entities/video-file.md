# VideoFile Entity

Entidade que representa um arquivo de vídeo baixado.

---

## Visão Geral

`VideoFile` é uma **Entity** que encapsula informações sobre arquivos de vídeo:
- Identidade única (UUID)
- Caminho do arquivo
- Metadata (tamanho, formato, URL original)
- Operações (verificar existência, deletar)

**Arquivo**: `src/domain/entities/video_file.py`

---

## Estrutura

```python
@dataclass
class VideoFile:
    id: str                      # UUID único
    file_path: Path              # Caminho do arquivo
    original_url: Optional[str]  # URL original do vídeo
    file_size_bytes: int         # Tamanho em bytes
    format: Optional[str]        # Formato (mp4, webm, etc.)
    created_at: datetime         # Data de criação
```

---

## Propriedades

### `exists` (readonly)
Verifica se o arquivo existe no disco.

```python
video = VideoFile(file_path=Path("video.mp4"))
if video.exists:
    print("Arquivo encontrado!")
```

### `file_size_mb` (readonly)
Retorna o tamanho do arquivo em megabytes.

```python
print(f"Tamanho: {video.file_size_mb:.2f} MB")  # "Tamanho: 45.67 MB"
```

### `extension` (readonly)
Retorna a extensão do arquivo.

```python
print(video.extension)  # ".mp4"
```

---

## Métodos

### `delete() -> bool`
Remove o arquivo do disco.

**Retorno**: `True` se deletado com sucesso, `False` caso contrário.

```python
if video.delete():
    print("Arquivo removido!")
else:
    print("Falha ao remover")
```

### `to_dict() -> dict`
Serializa para dicionário.

```python
data = video.to_dict()
# {
#     "id": "550e8400-e29b-41d4-a716-446655440000",
#     "file_path": "/temp/video.mp4",
#     "original_url": "https://youtube.com/watch?v=123",
#     "file_size_mb": 45.67,
#     "format": "mp4",
#     "exists": true,
#     "created_at": "2025-10-22T10:30:00"
# }
```

---

## Exemplo Completo

```python
from pathlib import Path
from src.domain.entities import VideoFile

# Criar VideoFile
video = VideoFile(
    file_path=Path("temp/video_123.mp4"),
    original_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
    file_size_bytes=47841280,  # ~45.6 MB
    format="mp4"
)

# Verificar informações
print(f"ID: {video.id}")
print(f"Existe: {video.exists}")
print(f"Tamanho: {video.file_size_mb:.2f} MB")
print(f"Extensão: {video.extension}")

# Processar vídeo...
# (transcrição, etc.)

# Limpar após uso
if video.delete():
    print("Arquivo temporário removido")
```

---

## Regras de Negócio

1. **ID Único**: UUID4 gerado automaticamente
2. **Path Conversion**: Strings são convertidas para `Path` automaticamente
3. **Safe Delete**: `delete()` não lança exceção se arquivo não existe
4. **Size Calculation**: Tamanho em MB calculado a partir de bytes

---

## Testes

```python
def test_video_file_creation(tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_text("fake video")
    
    video = VideoFile(
        file_path=file_path,
        original_url="https://youtube.com/watch?v=123",
        file_size_bytes=1024,
        format="mp4"
    )
    
    assert video.id
    assert video.exists is True
    assert video.file_size_mb == 1024 / (1024 * 1024)
    assert video.extension == ".mp4"

def test_delete_video_file(tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_text("fake video")
    
    video = VideoFile(file_path=file_path)
    
    assert video.exists is True
    assert video.delete() is True
    assert video.exists is False
```

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0