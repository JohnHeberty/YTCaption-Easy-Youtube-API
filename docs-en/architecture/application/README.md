# Application Layer

Camada de aplicação - Orquestração de casos de uso (Use Cases).

---

## Índice

**Use Cases**:
- [Transcribe Video](use-cases/transcribe-video.md) - Orquestra download + transcrição
- [Cleanup Files](use-cases/cleanup-files.md) - Remove arquivos temporários antigos

**DTOs** (Data Transfer Objects):
- [Transcription DTOs](dtos/transcription-dtos.md) - Request/Response DTOs

---

## Visão Geral

A **Application Layer** é responsável por:
- Orquestrar fluxos de negócio (Use Cases)
- Coordenar múltiplos serviços de domínio
- Transformar dados entre camadas (DTOs)
- Gerenciar transações e rollbacks

**Princípios**:
- ✅ **Single Responsibility**: Cada Use Case tem uma responsabilidade específica
- ✅ **Dependency Inversion**: Depende de interfaces do domínio, não implementações
- ✅ **Separation of Concerns**: Lógica de orquestração separada de lógica de negócio
- ✅ **Testabilidade**: Fácil de testar com mocks das interfaces

---

## Estrutura

```
src/application/
├── use_cases/              # Casos de uso
│   ├── transcribe_video.py   # Use Case principal
│   └── cleanup_files.py       # Limpeza de arquivos
└── dtos/                   # Data Transfer Objects
    └── transcription_dtos.py  # DTOs de transcrição
```

---

## Use Cases

### TranscribeYouTubeVideoUseCase
**Responsabilidade**: Orquestrar o processo completo de transcrição.

**Fluxo**:
1. Validar URL do YouTube
2. Verificar cache (v2.2.1)
3. Criar diretório temporário
4. Baixar vídeo
5. Validar áudio (v2.0)
6. Transcrever com Whisper (com timeout v2.1)
7. Salvar no cache
8. Limpar arquivos temporários
9. Retornar resposta

**Exceções Tratadas**:
- `ValidationError` - URL inválida ou áudio corrompido
- `VideoDownloadError` - Falha no download
- `TranscriptionError` - Falha na transcrição
- `OperationTimeoutError` - Timeout na transcrição (v2.1)

### CleanupOldFilesUseCase
**Responsabilidade**: Remover arquivos temporários antigos.

**Fluxo**:
1. Obter uso de armazenamento (antes)
2. Remover arquivos com idade > max_age_hours
3. Obter uso de armazenamento (depois)
4. Retornar estatísticas

---

## DTOs (Data Transfer Objects)

DTOs são objetos imutáveis que transferem dados entre camadas:

### Request DTOs
- `TranscribeRequestDTO` - Requisição de transcrição
- `ExportCaptionsRequestDTO` - Exportação de legendas

### Response DTOs
- `TranscribeResponseDTO` - Resposta com transcrição completa
- `VideoInfoResponseDTO` - Informações do vídeo
- `HealthCheckDTO` - Status da API
- `ErrorResponseDTO` - Resposta de erro padronizada

### Auxiliary DTOs
- `TranscriptionSegmentDTO` - Segmento individual
- `SubtitlesInfoDTO` - Informações de legendas
- `WhisperRecommendationDTO` - Recomendação Whisper vs YouTube

**Validação**: DTOs usam Pydantic para validação automática de dados.

---

## Exemplo de Uso

```python
from src.application.use_cases import TranscribeYouTubeVideoUseCase
from src.application.dtos import TranscribeRequestDTO

# Criar Use Case (injetar dependências)
use_case = TranscribeYouTubeVideoUseCase(
    video_downloader=downloader,
    transcription_service=whisper_service,
    storage_service=storage,
    cleanup_after_processing=True,
    max_video_duration=10800  # 3 horas
)

# Criar requisição
request = TranscribeRequestDTO(
    youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    language="auto"
)

# Executar Use Case
try:
    response = await use_case.execute(request)
    print(f"Transcrição ID: {response.transcription_id}")
    print(f"Idioma: {response.language}")
    print(f"Tempo: {response.processing_time:.2f}s")
    print(f"Texto: {response.full_text}")
except ValidationError as e:
    print(f"Dados inválidos: {e}")
except TranscriptionError as e:
    print(f"Erro na transcrição: {e}")
```

---

## Dependency Injection

Use Cases recebem **interfaces** como dependências:

```python
class TranscribeYouTubeVideoUseCase:
    def __init__(
        self,
        video_downloader: IVideoDownloader,      # Interface
        transcription_service: ITranscriptionService,  # Interface
        storage_service: IStorageService,        # Interface
        # ...
    ):
        self.video_downloader = video_downloader
        self.transcription_service = transcription_service
        self.storage_service = storage_service
```

**Benefícios**:
- Testabilidade (usar mocks)
- Flexibilidade (trocar implementações)
- Desacoplamento (Application não conhece Infrastructure)

---

## Testes

```python
async def test_transcribe_use_case_success():
    # Criar mocks
    mock_downloader = AsyncMock(spec=IVideoDownloader)
    mock_downloader.download.return_value = VideoFile(
        file_path=Path("video.mp4"),
        file_size_bytes=1024
    )
    
    mock_transcription = AsyncMock(spec=ITranscriptionService)
    mock_transcription.transcribe.return_value = Transcription(
        segments=[TranscriptionSegment("Hello", 0, 2)],
        language="en"
    )
    
    mock_storage = AsyncMock(spec=IStorageService)
    
    # Criar Use Case com mocks
    use_case = TranscribeYouTubeVideoUseCase(
        video_downloader=mock_downloader,
        transcription_service=mock_transcription,
        storage_service=mock_storage
    )
    
    # Executar
    request = TranscribeRequestDTO(youtube_url="https://youtu.be/123")
    response = await use_case.execute(request)
    
    # Assertions
    assert response.language == "en"
    assert response.total_segments == 1
    mock_downloader.download.assert_called_once()
    mock_transcription.transcribe.assert_called_once()
```

---

**Versão**: 3.0.0

[⬅️ Voltar](../README.md)
