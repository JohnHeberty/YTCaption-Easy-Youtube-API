# IStorageService Interface

Interface (ABC) que define o contrato para gerenciamento de armazenamento.

---

## Visão Geral

`IStorageService` é uma **Interface** que:
- Define o contrato para gerenciamento de arquivos temporários
- Segue o **Dependency Inversion Principle** (SOLID)
- Permite múltiplas implementações (local, cloud, etc.)

**Arquivo**: `src/domain/interfaces/storage_service.py`

---

## Métodos

### `create_temp_directory() -> Path`
Cria um diretório temporário.

**Retorno**: `Path` - Caminho do diretório criado

```python
storage: IStorageService = LocalStorageService()
temp_dir = await storage.create_temp_directory()
print(f"Diretório: {temp_dir}")  # "temp/session_abc123"
```

### `cleanup_old_files(max_age_hours=24) -> int`
Remove arquivos antigos do armazenamento temporário.

**Parâmetros**:
- `max_age_hours: int` - Idade máxima dos arquivos em horas (padrão: 24h)

**Retorno**: `int` - Número de arquivos removidos

```python
removed = await storage.cleanup_old_files(max_age_hours=12)
print(f"Removidos: {removed} arquivos")
```

### `cleanup_directory(directory) -> bool`
Remove um diretório e todo seu conteúdo.

**Parâmetros**:
- `directory: Path` - Diretório a ser removido

**Retorno**: `bool` - `True` se removido com sucesso

```python
success = await storage.cleanup_directory(temp_dir)
if success:
    print("Diretório limpo!")
```

### `get_temp_files() -> List[Path]`
Lista todos os arquivos temporários.

**Retorno**: `List[Path]` - Lista de caminhos dos arquivos

```python
files = await storage.get_temp_files()
for file in files:
    print(f"- {file} ({file.stat().st_size} bytes)")
```

### `get_storage_usage() -> dict`
Obtém informações sobre uso de armazenamento.

**Retorno**: `dict` - Informações de uso (total, usado, livre)

```python
usage = await storage.get_storage_usage()
print(f"Total: {usage['total_gb']:.2f} GB")
print(f"Usado: {usage['used_gb']:.2f} GB")
print(f"Livre: {usage['free_gb']:.2f} GB")
```

---

## Implementações

### `LocalStorageService` (Infrastructure)
Implementação para armazenamento local.

**Localização**: `src/infrastructure/storage/local_storage.py`

**Características**:
- Gerencia diretório `temp/` na raiz do projeto
- Cleanup automático de arquivos antigos
- Thread-safe (async locks)
- Tratamento robusto de erros

---

## Exemplo de Uso

```python
from src.domain.interfaces import IStorageService
from src.infrastructure.storage import LocalStorageService

async def process_video(storage: IStorageService, video_url: str):
    # Criar diretório temporário
    temp_dir = await storage.create_temp_directory()
    
    try:
        # Baixar vídeo
        video_path = temp_dir / "video.mp4"
        await downloader.download(video_url, video_path)
        
        # Processar...
        transcription = await transcribe(video_path)
        
        return transcription
    
    finally:
        # Limpar diretório
        await storage.cleanup_directory(temp_dir)

# Injetar implementação
storage = LocalStorageService(base_dir=Path("temp"))
result = await process_video(storage, "https://youtu.be/123")
```

---

## Dependency Inversion

```python
# ❌ ERRADO: Depender de implementação concreta
from src.infrastructure.storage import LocalStorageService

class TranscribeUseCase:
    def __init__(self):
        self.storage = LocalStorageService()  # Acoplamento

# ✅ CORRETO: Depender de abstração
from src.domain.interfaces import IStorageService

class TranscribeUseCase:
    def __init__(self, storage: IStorageService):
        self.storage = storage  # Flexível
```

**Benefícios**:
- Testar com mock (sem I/O)
- Trocar implementação (local → S3)
- Domínio desacoplado de infraestrutura

---

## Testes

```python
class MockStorageService(IStorageService):
    async def create_temp_directory(self):
        return Path("/tmp/test")
    
    async def cleanup_old_files(self, max_age_hours=24):
        return 0
    
    async def cleanup_directory(self, directory):
        return True
    
    async def get_temp_files(self):
        return []
    
    async def get_storage_usage(self):
        return {"total_gb": 100, "used_gb": 50, "free_gb": 50}

# Usar mock nos testes
async def test_transcribe_use_case():
    mock_storage = MockStorageService()
    use_case = TranscribeUseCase(storage=mock_storage)
    
    result = await use_case.execute("https://youtu.be/123")
    assert result.success
```

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0