# 🏛️ Architecture

**Documentação técnica da arquitetura - Clean Architecture, SOLID e estrutura do projeto.**

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Clean Architecture](#clean-architecture)
3. [SOLID Principles](#solid-principles)
4. [Estrutura de Pastas](#estrutura-de-pastas)
5. [Fluxo de Dados](#fluxo-de-dados)
6. [Camadas](#camadas)
7. [Dependency Injection](#dependency-injection)
8. [Para Desenvolvedores](#para-desenvolvedores)

---

## Visão Geral

Este projeto segue **Clean Architecture** com **princípios SOLID**, garantindo:

- ✅ **Separação de responsabilidades**
- ✅ **Testabilidade**
- ✅ **Manutenibilidade**
- ✅ **Independência de frameworks**
- ✅ **Escalabilidade**

---

## Clean Architecture

### Camadas (de dentro para fora)

```
┌─────────────────────────────────────────┐
│           Infrastructure                │  ← Frameworks, Drivers
│  (FastAPI, Whisper, YouTube, FFmpeg)    │
├─────────────────────────────────────────┤
│         Interface Adapters              │  ← Controllers, Presenters
│      (Routes, DTOs, Serializers)        │
├─────────────────────────────────────────┤
│          Use Cases                      │  ← Application Logic
│  (Transcribe, Download, Process)        │
├─────────────────────────────────────────┤
│       Domain (Entities)                 │  ← Business Rules
│  (ValueObjects, Interfaces, Exceptions) │
└─────────────────────────────────────────┘
```

### Regra de Dependência

**Dependências sempre apontam para dentro**:
- ✅ Infrastructure → Use Cases → Domain
- ❌ Domain NÃO conhece Infrastructure
- ❌ Use Cases NÃO conhecem FastAPI

---

## SOLID Principles

### S - Single Responsibility Principle

**Cada classe tem UMA responsabilidade.**

✅ **Exemplo**:
```python
# src/infrastructure/youtube/downloader.py
class YouTubeDownloader:
    """Responsabilidade: Baixar áudio do YouTube"""
    def download(self, url: str) -> str:
        pass

# src/infrastructure/whisper/transcription_service.py
class TranscriptionService:
    """Responsabilidade: Transcrever áudio"""
    def transcribe(self, audio_path: str) -> dict:
        pass
```

❌ **Anti-padrão** (evitado):
```python
class YouTubeTranscriber:
    """Faz TUDO: download + transcrição + cleanup"""
    def download_and_transcribe(self, url: str):
        # Muitas responsabilidades!
        pass
```

---

### O - Open/Closed Principle

**Aberto para extensão, fechado para modificação.**

✅ **Exemplo**:
```python
# src/domain/interfaces/transcription_service.py
class ITranscriptionService(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> dict:
        ...

# Podemos adicionar nova implementação sem modificar código existente
class WhisperService(ITranscriptionService):
    def transcribe(self, audio_path: str) -> dict:
        # Whisper implementation
        pass

class GoogleSpeechService(ITranscriptionService):
    def transcribe(self, audio_path: str) -> dict:
        # Google Speech implementation (futuro)
        pass
```

---

### L - Liskov Substitution Principle

**Subclasses devem ser substituíveis por suas classes base.**

✅ **Exemplo**:
```python
# Qualquer ITranscriptionService pode ser usado
def process_audio(service: ITranscriptionService, audio: str):
    return service.transcribe(audio)

# Funciona com qualquer implementação
process_audio(WhisperService(), "audio.wav")
process_audio(GoogleSpeechService(), "audio.wav")
```

---

### I - Interface Segregation Principle

**Interfaces específicas são melhores que uma interface geral.**

✅ **Exemplo**:
```python
# src/domain/interfaces/
# Interfaces separadas por responsabilidade

class IDownloader(ABC):
    @abstractmethod
    def download(self, url: str) -> str:
        ...

class ITranscriptionService(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> dict:
        ...

class IStorageService(ABC):
    @abstractmethod
    def cleanup(self, path: str) -> None:
        ...
```

❌ **Anti-padrão** (evitado):
```python
class IVideoProcessor(ABC):
    """Interface muito geral"""
    def download(self, url: str): ...
    def transcribe(self, audio: str): ...
    def cleanup(self, path: str): ...
    # Cliente forçado a implementar TUDO
```

---

### D - Dependency Inversion Principle

**Dependa de abstrações, não de implementações.**

✅ **Exemplo**:
```python
# Use Case depende da INTERFACE, não da implementação
class TranscribeVideoUseCase:
    def __init__(
        self,
        downloader: IDownloader,  # Abstração
        transcriber: ITranscriptionService,  # Abstração
        storage: IStorageService  # Abstração
    ):
        self._downloader = downloader
        self._transcriber = transcriber
        self._storage = storage
    
    def execute(self, url: str):
        audio = self._downloader.download(url)
        result = self._transcriber.transcribe(audio)
        self._storage.cleanup(audio)
        return result
```

❌ **Anti-padrão** (evitado):
```python
class TranscribeVideoUseCase:
    def __init__(self):
        # Dependência direta de implementações concretas
        self._downloader = YouTubeDownloader()
        self._transcriber = WhisperService()
```

---

## Estrutura de Pastas

```
src/
├── domain/                          # Camada de Domínio (núcleo)
│   ├── entities/                    # Entidades de negócio
│   │   └── transcription_result.py
│   ├── exceptions/                  # Exceções de domínio
│   │   └── domain_exceptions.py
│   ├── interfaces/                  # Interfaces (contratos)
│   │   ├── downloader.py
│   │   ├── storage_service.py
│   │   └── transcription_service.py
│   └── value_objects/               # Objetos de valor
│       └── transcription_segment.py
│
├── application/                     # Camada de Aplicação (Use Cases)
│   └── use_cases/
│       └── transcribe_video_use_case.py
│
├── infrastructure/                  # Camada de Infraestrutura
│   ├── whisper/                     # Implementação Whisper
│   │   ├── transcription_service.py
│   │   └── parallel_transcription_service.py
│   ├── youtube/                     # Implementação YouTube (v3.0 ↓)
│   │   ├── downloader.py            # ← Core download logic
│   │   ├── download_config.py       # 🆕 v3.0 - Configurações centralizadas
│   │   ├── download_strategies.py   # 🆕 v3.0 - 7 estratégias de download
│   │   ├── rate_limiter.py          # 🆕 v3.0 - Rate limiting inteligente
│   │   ├── user_agent_rotator.py    # 🆕 v3.0 - Rotação de User-Agents
│   │   ├── proxy_manager.py         # 🆕 v3.0 - Gerenciamento Tor proxy
│   │   └── metrics.py               # 🆕 v3.0 - Métricas Prometheus
│   ├── storage/                     # Sistema de arquivos
│   │   └── local_storage.py
│   └── config/                      # Configurações
│       └── settings.py
│
├── presentation/                    # Camada de Apresentação
│   ├── api/                         # FastAPI routes
│   │   ├── routes/
│   │   │   ├── transcription.py
│   │   │   └── health.py
│   │   └── dependencies.py
│   └── schemas/                     # DTOs (Data Transfer Objects)
│       ├── request.py
│       └── response.py
│
└── main.py                          # Entry point
```

**🆕 v3.0 - Novos Módulos (YouTube Resilience)**:
- `download_config.py`: Centraliza todas as configurações de download (retries, timeouts, rate limits)
- `download_strategies.py`: Implementa 7 estratégias diferentes (Strategy Pattern)
- `rate_limiter.py`: Rate limiting + Circuit Breaker Pattern
- `user_agent_rotator.py`: Rotaciona 17 User-Agents automaticamente
- `proxy_manager.py`: Gerencia Tor proxy (SOCKS5)
- `metrics.py`: 26 métricas Prometheus para monitoramento

---

## Fluxo de Dados

### Transcrição de Vídeo (Request → Response)

```
┌──────────────┐
│   Client     │
│  (Browser)   │
└──────┬───────┘
       │ POST /api/v1/transcribe
       ↓
┌──────────────────────────────────────────────┐
│         Presentation Layer                   │
│  ┌──────────────────────────────────────┐   │
│  │  TranscriptionRouter                 │   │
│  │  (presentation/api/routes/)          │   │
│  └───────────────┬──────────────────────┘   │
│                  │ TranscriptionRequest      │
│                  ↓                            │
│  ┌──────────────────────────────────────┐   │
│  │  DTOs Validation                     │   │
│  │  (presentation/schemas/)             │   │
│  └───────────────┬──────────────────────┘   │
└──────────────────┼──────────────────────────┘
                   │
                   ↓
┌──────────────────────────────────────────────┐
│       Application Layer (Use Cases)          │
│  ┌──────────────────────────────────────┐   │
│  │  TranscribeVideoUseCase              │   │
│  │  (application/use_cases/)            │   │
│  │                                       │   │
│  │  1. Download audio                   │   │
│  │  2. Convert to WAV                   │   │
│  │  3. Transcribe                       │   │
│  │  4. Cleanup                          │   │
│  └───────────────┬──────────────────────┘   │
└──────────────────┼──────────────────────────┘
                   │
       ┌───────────┼───────────┐
       │           │           │
       ↓           ↓           ↓
┌─────────────────────────────────────────────┐
│      Infrastructure Layer                   │
│                                              │
│  ┌──────────────┐  ┌───────────────────┐   │
│  │YouTubeDown-  │  │ Transcription     │   │
│  │loader        │  │ Service           │   │
│  │              │  │ (Whisper)         │   │
│  │ • yt-dlp     │  │ • openai-whisper  │   │
│  │ • FFmpeg     │  │ • multiprocessing │   │
│  └──────────────┘  └───────────────────┘   │
│                                              │
│  ┌──────────────┐                           │
│  │ Storage      │                           │
│  │ Service      │                           │
│  │ • Cleanup    │                           │
│  └──────────────┘                           │
└─────────────────────────────────────────────┘
       │           │           │
       └───────────┼───────────┘
                   │
                   ↓
┌──────────────────────────────────────────────┐
│         Domain Layer (Entities)              │
│  ┌──────────────────────────────────────┐   │
│  │  TranscriptionResult                 │   │
│  │  • video_url                         │   │
│  │  • video_title                       │   │
│  │  • transcription                     │   │
│  │  • segments                          │   │
│  └──────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
       │
       │ TranscriptionResponse
       ↓
┌──────────────┐
│   Client     │
│  (Browser)   │
└──────────────┘
```

---

## Camadas

### 1. Domain Layer

**Responsabilidade**: Regras de negócio puras.

**Conteúdo**:
- **Entities**: Objetos com identidade (`TranscriptionResult`)
- **Value Objects**: Objetos sem identidade (`TranscriptionSegment`)
- **Interfaces**: Contratos (`ITranscriptionService`)
- **Exceptions**: Erros de domínio (`TranscriptionError`)

**Regras**:
- ❌ Não depende de nenhuma outra camada
- ❌ Não conhece frameworks (FastAPI, Whisper)
- ❌ Não tem I/O (sem file system, DB, API)

**Exemplo**:
```python
# src/domain/value_objects/transcription_segment.py
@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str
    
    def duration(self) -> float:
        return self.end - self.start
```

---

### 2. Application Layer (Use Cases)

**Responsabilidade**: Orquestração da lógica de aplicação.

**Conteúdo**:
- **Use Cases**: Casos de uso do sistema

**Regras**:
- ✅ Depende apenas de Domain (interfaces)
- ❌ Não conhece detalhes de implementação
- ✅ Coordena múltiplos serviços

**Exemplo**:
```python
# src/application/use_cases/transcribe_video_use_case.py
class TranscribeVideoUseCase:
    def __init__(
        self,
        downloader: IDownloader,
        transcriber: ITranscriptionService,
        storage: IStorageService
    ):
        self._downloader = downloader
        self._transcriber = transcriber
        self._storage = storage
    
    def execute(self, video_url: str) -> TranscriptionResult:
        # Orquestra o fluxo
        audio_path = self._downloader.download(video_url)
        result = self._transcriber.transcribe(audio_path)
        self._storage.cleanup(audio_path)
        return result
```

---

### 3. Infrastructure Layer

**Responsabilidade**: Implementações concretas, frameworks, I/O.

**Conteúdo**:
- **Whisper**: Implementação de transcrição
- **YouTube**: Implementação de download
- **Storage**: Implementação de armazenamento
- **Config**: Configurações (`.env`)

**Regras**:
- ✅ Implementa interfaces do Domain
- ✅ Usa frameworks externos (Whisper, yt-dlp)
- ✅ Faz I/O real (file system, network)

**Exemplo**:
```python
# src/infrastructure/whisper/transcription_service.py
class TranscriptionService(ITranscriptionService):
    def __init__(self, model: str = "base"):
        self._model = whisper.load_model(model)
    
    def transcribe(self, audio_path: str) -> dict:
        # Implementação real usando Whisper
        return self._model.transcribe(audio_path)
```

---

### 4. Presentation Layer

**Responsabilidade**: Interface com o mundo externo (API REST).

**Conteúdo**:
- **Routes**: Endpoints FastAPI
- **Schemas**: DTOs (Request/Response)
- **Dependencies**: Dependency Injection

**Regras**:
- ✅ Usa Use Cases (Application Layer)
- ✅ Valida entrada (DTOs)
- ✅ Formata saída (Serialização)

**Exemplo**:
```python
# src/presentation/api/routes/transcription.py
@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_video(
    request: TranscriptionRequest,
    use_case: TranscribeVideoUseCase = Depends(get_transcribe_use_case)
):
    result = use_case.execute(request.video_url)
    return TranscriptionResponse.from_entity(result)
```

---

## Dependency Injection

### Container

```python
# src/presentation/api/dependencies.py
from functools import lru_cache

@lru_cache()
def get_downloader() -> IDownloader:
    return YouTubeDownloader()

@lru_cache()
def get_transcriber() -> ITranscriptionService:
    model = settings.WHISPER_MODEL
    if settings.ENABLE_PARALLEL_TRANSCRIPTION:
        return ParallelTranscriptionService(model)
    else:
        return TranscriptionService(model)

@lru_cache()
def get_storage() -> IStorageService:
    return LocalStorageService()

def get_transcribe_use_case(
    downloader: IDownloader = Depends(get_downloader),
    transcriber: ITranscriptionService = Depends(get_transcriber),
    storage: IStorageService = Depends(get_storage)
) -> TranscribeVideoUseCase:
    return TranscribeVideoUseCase(downloader, transcriber, storage)
```

### Benefícios

- ✅ **Testabilidade**: Mock fácil de dependências
- ✅ **Flexibilidade**: Troca implementações facilmente
- ✅ **Singleton**: `@lru_cache()` garante instância única

---

## Para Desenvolvedores

### Adicionar Nova Feature

**Exemplo**: Adicionar suporte a Vimeo.

#### 1. Criar Interface (Domain)

```python
# src/domain/interfaces/downloader.py
class IDownloader(ABC):
    @abstractmethod
    def download(self, url: str) -> str:
        """Download video and return audio path"""
        ...
    
    @abstractmethod
    def supports(self, url: str) -> bool:
        """Check if URL is supported"""
        ...
```

#### 2. Implementar (Infrastructure)

```python
# src/infrastructure/vimeo/downloader.py
class VimeoDownloader(IDownloader):
    def download(self, url: str) -> str:
        # Implementação Vimeo
        pass
    
    def supports(self, url: str) -> bool:
        return "vimeo.com" in url
```

#### 3. Atualizar Use Case (Application)

```python
# src/application/use_cases/transcribe_video_use_case.py
class TranscribeVideoUseCase:
    def __init__(
        self,
        youtube_downloader: IDownloader,
        vimeo_downloader: IDownloader,  # Nova dependência
        transcriber: ITranscriptionService,
        storage: IStorageService
    ):
        self._downloaders = [youtube_downloader, vimeo_downloader]
        self._transcriber = transcriber
        self._storage = storage
    
    def execute(self, video_url: str):
        # Seleciona downloader correto
        downloader = next(d for d in self._downloaders if d.supports(video_url))
        audio = downloader.download(video_url)
        # ... resto igual
```

#### 4. Configurar DI (Presentation)

```python
# src/presentation/api/dependencies.py
@lru_cache()
def get_vimeo_downloader() -> IDownloader:
    return VimeoDownloader()

def get_transcribe_use_case(
    youtube: IDownloader = Depends(get_downloader),
    vimeo: IDownloader = Depends(get_vimeo_downloader),
    transcriber: ITranscriptionService = Depends(get_transcriber),
    storage: IStorageService = Depends(get_storage)
):
    return TranscribeVideoUseCase(youtube, vimeo, transcriber, storage)
```

---

### Testes

#### Unit Tests (Domain/Application)

```python
# tests/application/test_transcribe_use_case.py
def test_transcribe_video():
    # Mock dependencies
    downloader = Mock(spec=IDownloader)
    transcriber = Mock(spec=ITranscriptionService)
    storage = Mock(spec=IStorageService)
    
    # Configure mocks
    downloader.download.return_value = "audio.wav"
    transcriber.transcribe.return_value = {"text": "Hello"}
    
    # Execute use case
    use_case = TranscribeVideoUseCase(downloader, transcriber, storage)
    result = use_case.execute("https://youtube.com/watch?v=123")
    
    # Assert
    assert result.transcription["text"] == "Hello"
    downloader.download.assert_called_once()
    storage.cleanup.assert_called_once()
```

#### Integration Tests (Infrastructure)

```python
# tests/infrastructure/test_whisper_service.py
def test_real_transcription():
    service = TranscriptionService(model="tiny")
    result = service.transcribe("tests/fixtures/sample.wav")
    
    assert "text" in result
    assert len(result["segments"]) > 0
```

---

### Padrões de Código

#### 1. Naming Conventions

- **Interfaces**: `IServiceName` (prefixo `I`)
- **Implementations**: `ServiceName` (sem prefixo)
- **Use Cases**: `VerbNounUseCase` (ex: `TranscribeVideoUseCase`)
- **DTOs**: `EntityRequest`/`EntityResponse`

#### 2. Error Handling

**Domain Exceptions**:
```python
# src/domain/exceptions/domain_exceptions.py
class DomainException(Exception):
    """Base exception"""
    pass

class TranscriptionError(DomainException):
    """Transcription failed"""
    pass
```

**Use em Infrastructure**:
```python
try:
    result = whisper.transcribe(audio)
except Exception as exc:
    raise TranscriptionError(f"Failed: {exc}") from exc
```

#### 3. Logging

```python
import logging

logger = logging.getLogger(__name__)

class TranscriptionService:
    def transcribe(self, audio_path: str):
        logger.info(f"Transcribing {audio_path}")
        try:
            result = self._model.transcribe(audio_path)
            logger.info(f"Transcription completed: {len(result['text'])} chars")
            return result
        except Exception as exc:
            logger.error(f"Transcription failed: {exc}")
            raise
```

---

## 🆕 v3.0 - YouTube Resilience Architecture

### Diagrama de Componentes (v3.0)

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│                  (FastAPI Routes)                            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│               Application Layer (Use Case)                   │
│          TranscribeVideoUseCase.execute()                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│             Infrastructure - YouTube Module (v3.0)           │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │              YouTubeDownloader                      │    │
│  │            (Orchestrator/Facade)                    │    │
│  └─────────────┬──────────────────────────────────────┘    │
│                │                                             │
│    ┌───────────┼───────────┬───────────┬──────────────┐    │
│    │           │           │           │              │    │
│    ↓           ↓           ↓           ↓              ↓    │
│  ┌─────┐  ┌─────────┐  ┌──────┐  ┌─────────┐  ┌────────┐ │
│  │ DNS │  │ Multi-  │  │ Rate │  │  User   │  │  Tor   │ │
│  │Layer│  │Strategy │  │Limiter  │ Agent   │  │ Proxy  │ │
│  │     │  │         │  │Circuit │ │Rotator  │  │Manager │ │
│  │8.8. │  │ (7      │  │Breaker│  │ (17 UAs)│  │(SOCKS5)│ │
│  │8.8  │  │strategies  │        │  │         │  │        │ │
│  └─────┘  └─────────┘  └──────┘  └─────────┘  └────────┘ │
│                            │                                │
│                            ↓                                │
│                      ┌──────────┐                          │
│                      │ Metrics  │ ← 26 Prometheus metrics  │
│                      │ (v3.0)   │                          │
│                      └─────┬────┘                          │
└────────────────────────────┼─────────────────────────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │   Monitoring     │
                    │ Prometheus +     │
                    │   Grafana        │
                    └──────────────────┘
```

### Fluxo de Download (v3.0)

```
Request
  │
  ↓
┌─────────────────────────────────┐
│ 1. DownloadConfig               │ ← Carrega configurações (.env)
│    • Max retries: 5             │
│    • Rate limits: 10/min        │
│    • Circuit breaker: 10 erros  │
└────────┬────────────────────────┘
         │
         ↓
┌─────────────────────────────────┐
│ 2. RateLimiter Check            │ ← Verifica limites
│    • Requests/min OK?           │
│    • Circuit breaker OPEN?      │
└────────┬────────────────────────┘
         │ YES (continua)
         ↓
┌─────────────────────────────────┐
│ 3. UserAgentRotator             │ ← Seleciona UA aleatório
│    • Rotaciona entre 17 UAs     │
│    • Chrome/Firefox/Safari/Edge │
└────────┬────────────────────────┘
         │
         ↓
┌─────────────────────────────────┐
│ 4. ProxyManager (Tor)           │ ← Configura proxy (se habilitado)
│    • SOCKS5: tor-proxy:9050     │
│    • Nova identidade a cada N   │
└────────┬────────────────────────┘
         │
         ↓
┌─────────────────────────────────┐
│ 5. DownloadStrategies (7x)      │ ← Tenta estratégias sequencialmente
│    Strategy 1: Direct           │
│    Strategy 2: Cookies          │ ← Se 1 falha
│    Strategy 3: Mobile UA        │ ← Se 2 falha
│    Strategy 4: Referer          │ ← Se 3 falha
│    Strategy 5: Extract Format   │ ← Se 4 falha
│    Strategy 6: Embedded         │ ← Se 5 falha
│    Strategy 7: OAuth2           │ ← Se 6 falha
└────────┬────────────────────────┘
         │
    ┌────┴────┐
    │         │
SUCCESS    FAILURE (todas as 7)
    │         │
    ↓         ↓
┌────────┐  ┌─────────────────────┐
│Metrics │  │ 6. Retry with       │ ← Exponential backoff
│Update  │  │    Exponential      │   delay = min * 2^attempt
└────────┘  │    Backoff          │
            └─────────┬───────────┘
                      │
                      ↓
            ┌─────────────────────┐
            │ 7. Circuit Breaker  │ ← Abre após N falhas
            │    (se > threshold) │   Aguarda timeout
            │    • Cooldown: 60s  │
            └─────────────────────┘
```

### Design Patterns Aplicados (v3.0)

#### 1. Strategy Pattern
**Onde**: `download_strategies.py`

```python
class DownloadStrategy(ABC):
    @abstractmethod
    def download(self, url: str) -> str:
        pass

class DirectStrategy(DownloadStrategy):
    def download(self, url: str) -> str:
        # Implementação direta

class CookiesStrategy(DownloadStrategy):
    def download(self, url: str) -> str:
        # Com cookies do navegador

# ... 5 outras estratégias
```

**Benefício**: Adicionar nova estratégia sem modificar código existente (Open/Closed).

---

#### 2. Circuit Breaker Pattern
**Onde**: `rate_limiter.py`

```python
class CircuitBreaker:
    def __init__(self, threshold: int, timeout: int):
        self.failures = 0
        self.threshold = threshold
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func):
        if self.state == "OPEN":
            raise CircuitOpenError("Too many failures")
        
        try:
            result = func()
            self.on_success()
            return result
        except Exception:
            self.on_failure()
            raise
```

**Benefício**: Previne sobrecarga do YouTube, evita bans permanentes.

---

#### 3. Retry Pattern with Exponential Backoff
**Onde**: `downloader.py`

```python
def download_with_retry(self, url: str) -> str:
    for attempt in range(self.max_retries):
        try:
            return self._try_download(url)
        except Exception as exc:
            delay = min(
                self.retry_delay_min * (2 ** attempt),
                self.retry_delay_max
            )
            time.sleep(delay)
            continue
    
    raise AllStrategiesFailedError()
```

**Benefício**: Aumenta taxa de sucesso sem sobrecarregar YouTube.

---

#### 4. Singleton Pattern (Metrics)
**Onde**: `metrics.py`

```python
class YouTubeMetrics:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_metrics()
        return cls._instance
```

**Benefício**: Métricas centralizadas, thread-safe.

---

## Benefícios da Arquitetura

### ✅ Testabilidade

- Mocks fáceis (interfaces)
- Testes unitários isolados
- Sem dependências externas em testes
- **v3.0**: Estratégias testáveis individualmente

### ✅ Manutenibilidade

- Código organizado
- Fácil localizar funcionalidades
- Mudanças isoladas
- **v3.0**: 7 estratégias em módulos separados

### ✅ Escalabilidade

- Adicionar features sem quebrar existentes
- Trocar implementações facilmente
- Paralelização natural (Use Cases independentes)
- **v3.0**: Adicionar nova estratégia sem modificar existentes

### ✅ Independência de Framework

- Migrar de FastAPI para Flask: só muda Presentation
- Trocar Whisper por outro: só muda Infrastructure
- **v3.0**: Trocar yt-dlp por outro downloader: só modifica estratégias

### ✅ Resiliência (v3.0)

- 5 camadas de proteção (DNS, multi-strategy, rate limiting, UA rotation, Tor)
- Circuit Breaker previne bans
- Auto-recovery após erros
- Monitoramento completo (26 métricas)
- Business logic (Domain) permanece intacta

---

## Recursos Adicionais

- **Clean Architecture** (Robert C. Martin): https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- **SOLID Principles**: https://en.wikipedia.org/wiki/SOLID
- **Dependency Injection**: https://en.wikipedia.org/wiki/Dependency_injection

---

**Voltar**: [Getting Started](./01-GETTING-STARTED.md)

**Versão**: 1.3.3+  
**Última atualização**: 19/10/2025
