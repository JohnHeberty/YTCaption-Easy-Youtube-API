# Arquitetura do Sistema

## Visão Geral

A **Whisper Transcription API** foi projetada seguindo os princípios de **Clean Architecture** e **SOLID**, garantindo:

- ✅ **Manutenibilidade**: Código organizado e fácil de manter
- ✅ **Testabilidade**: Componentes desacoplados e testáveis
- ✅ **Escalabilidade**: Fácil adição de novas funcionalidades
- ✅ **Independência**: Regras de negócio independentes de frameworks

## Clean Architecture

### Diagrama de Camadas

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│  FastAPI Routes, Middlewares, API Schemas, HTTP Handlers │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│                   Application Layer                      │
│     Use Cases, DTOs, Business Logic Orchestration        │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│                     Domain Layer                         │
│  Entities, Value Objects, Interfaces, Business Rules     │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│                 Infrastructure Layer                     │
│    External Services, Databases, File System, APIs       │
└─────────────────────────────────────────────────────────┘
```

### Descrição das Camadas

#### 1. Domain Layer (Núcleo)

**Responsabilidade**: Contém as regras de negócio puras, independentes de frameworks.

**Componentes**:
- **Entities**: `Transcription`, `VideoFile`
  - Objetos com identidade única
  - Contém lógica de negócio
  
- **Value Objects**: `YouTubeURL`, `TranscriptionSegment`
  - Objetos imutáveis sem identidade
  - Validação incorporada
  
- **Interfaces**: `IVideoDownloader`, `ITranscriptionService`, `IStorageService`
  - Contratos que definem capacidades
  - Implementam Dependency Inversion (SOLID)
  
- **Exceptions**: Exceções customizadas do domínio

**Princípios Aplicados**:
- ✅ **SRP** (Single Responsibility): Cada classe tem uma única responsabilidade
- ✅ **DIP** (Dependency Inversion): Dependências através de interfaces
- ✅ **ISP** (Interface Segregation): Interfaces específicas e focadas

#### 2. Application Layer

**Responsabilidade**: Orquestra casos de uso e fluxos de aplicação.

**Componentes**:
- **Use Cases**: 
  - `TranscribeYouTubeVideoUseCase`: Coordena download + transcrição + cleanup
  - `CleanupOldFilesUseCase`: Gerencia limpeza de arquivos
  
- **DTOs** (Data Transfer Objects):
  - `TranscribeRequestDTO`, `TranscribeResponseDTO`
  - Validação com Pydantic
  - Isolam camadas externas do domínio

**Fluxo de um Use Case**:
```
1. Receber Request DTO
2. Validar entrada
3. Criar entidades de domínio
4. Executar lógica de negócio
5. Retornar Response DTO
```

**Princípios Aplicados**:
- ✅ **SRP**: Um use case = uma responsabilidade
- ✅ **OCP** (Open/Closed): Aberto para extensão, fechado para modificação
- ✅ **DIP**: Depende de interfaces, não de implementações

#### 3. Infrastructure Layer

**Responsabilidade**: Implementações concretas de serviços externos.

**Componentes**:

**YouTube Downloader** (`YouTubeDownloader`):
```python
- Usa yt-dlp para download
- Baixa na pior qualidade (worstaudio)
- Gerencia timeouts e erros
- Implementa IVideoDownloader
```

**Whisper Service** (`WhisperTranscriptionService`):
```python
- Carrega modelo Whisper (lazy loading)
- Transcreve áudio com timestamps
- Detecta idioma automaticamente
- Implementa ITranscriptionService
```

**Storage Service** (`LocalStorageService`):
```python
- Gerencia diretórios temporários
- Limpeza automática de arquivos antigos
- Monitora uso de storage
- Implementa IStorageService
```

**Princípios Aplicados**:
- ✅ **LSP** (Liskov Substitution): Implementações substituíveis
- ✅ **DIP**: Implementam interfaces do domínio

#### 4. Presentation Layer

**Responsabilidade**: Interface com o mundo externo (HTTP/REST).

**Componentes**:

**FastAPI Application** (`main.py`):
```python
- Configuração da aplicação
- Middleware stack
- Exception handlers
- Lifecycle events (startup/shutdown)
```

**Routes**:
- `/api/v1/transcribe`: Endpoint de transcrição
- `/health`: Health check
- `/`: Informações da API

**Middlewares**:
- `LoggingMiddleware`: Log de requisições/respostas
- `CORSMiddleware`: Configuração de CORS

**Dependency Injection** (`dependencies.py`):
```python
Container gerencia instâncias:
- Singleton para serviços pesados (Whisper)
- Factory para use cases
```

## Fluxo Completo de Requisição

```
┌─────────────────────────────────────────────────────────────┐
│ 1. HTTP Request                                             │
│    POST /api/v1/transcribe                                  │
│    {"youtube_url": "...", "language": "auto"}               │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│ 2. Presentation Layer                                       │
│    - LoggingMiddleware (log request)                        │
│    - Route Handler                                          │
│    - Validação com Pydantic                                 │
│    - Dependency Injection                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│ 3. Application Layer                                        │
│    TranscribeYouTubeVideoUseCase.execute()                  │
│    - Validar URL (Value Object)                             │
│    - Criar diretório temporário                             │
│    - Coordenar download                                     │
│    - Coordenar transcrição                                  │
│    - Criar Response DTO                                     │
│    - Cleanup (finally)                                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│ 4. Infrastructure Layer                                     │
│    YouTubeDownloader.download()                             │
│    - yt-dlp download (worstaudio)                           │
│    - Retorna VideoFile entity                               │
│                                                             │
│    WhisperTranscriptionService.transcribe()                 │
│    - Load Whisper model (lazy)                              │
│    - Transcribe audio                                       │
│    - Retorna Transcription entity                           │
│                                                             │
│    LocalStorageService.cleanup_directory()                  │
│    - Remove arquivos temporários                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│ 5. Response                                                 │
│    HTTP 200 OK                                              │
│    {                                                        │
│      "transcription_id": "...",                             │
│      "language": "en",                                      │
│      "segments": [...],                                     │
│      ...                                                    │
│    }                                                        │
└─────────────────────────────────────────────────────────────┘
```

## Princípios SOLID Aplicados

### 1. Single Responsibility Principle (SRP)

Cada classe tem uma única razão para mudar:

- `YouTubeURL`: Apenas validação de URLs
- `YouTubeDownloader`: Apenas download de vídeos
- `WhisperTranscriptionService`: Apenas transcrição
- `TranscribeYouTubeVideoUseCase`: Apenas orquestração

### 2. Open/Closed Principle (OCP)

Aberto para extensão, fechado para modificação:

- Novas implementações de `IVideoDownloader` podem ser adicionadas sem modificar código existente
- Novos formats de export podem ser adicionados estendendo a funcionalidade

### 3. Liskov Substitution Principle (LSP)

Implementações são substituíveis:

```python
# Qualquer implementação de ITranscriptionService funciona
transcription_service: ITranscriptionService = WhisperTranscriptionService()
# Ou futuramente:
transcription_service: ITranscriptionService = GoogleSpeechToTextService()
```

### 4. Interface Segregation Principle (ISP)

Interfaces específicas e focadas:

- `IVideoDownloader`: Apenas métodos de download
- `ITranscriptionService`: Apenas métodos de transcrição
- `IStorageService`: Apenas métodos de storage

### 5. Dependency Inversion Principle (DIP)

Dependências através de abstrações:

```python
class TranscribeYouTubeVideoUseCase:
    def __init__(
        self,
        video_downloader: IVideoDownloader,  # Interface, não implementação
        transcription_service: ITranscriptionService,
        storage_service: IStorageService
    ):
        ...
```

## Padrões de Projeto

### 1. Dependency Injection

Gerenciado pelo `Container`:
- Cria instâncias
- Gerencia ciclo de vida
- Resolve dependências

### 2. Factory Pattern

Value Objects usam factory methods:
```python
youtube_url = YouTubeURL.create(url_string)
```

### 3. Repository Pattern

Abstraído através de interfaces de serviços

### 4. Strategy Pattern

Diferentes implementações de interfaces (ex: diferentes downloaders)

## Benefícios da Arquitetura

### ✅ Testabilidade

- Mocks fáceis através de interfaces
- Use cases testáveis isoladamente
- Sem dependência de frameworks nos testes

### ✅ Manutenibilidade

- Código organizado por responsabilidade
- Fácil localização de bugs
- Mudanças isoladas

### ✅ Escalabilidade

- Fácil adicionar novos use cases
- Fácil adicionar novas implementações
- Suporta crescimento do time

### ✅ Flexibilidade

- Trocar implementações sem afetar código
- Migrar para outros frameworks facilmente
- Adaptar a novos requisitos

## Considerações de Performance

### Otimizações Implementadas

1. **Lazy Loading**: Modelo Whisper carregado sob demanda
2. **Async/Await**: Operações I/O não bloqueantes
3. **Cleanup Automático**: Libera recursos após uso
4. **Download Otimizado**: Pior qualidade = menor arquivo = mais rápido

### Limitações e Trade-offs

- **Memória**: Modelo Whisper consome RAM significativa
- **CPU**: Transcrição é CPU-intensive
- **Disk I/O**: Download e storage temporário

### Recomendações de Hardware

- **Desenvolvimento**: 4GB RAM, 2 cores
- **Produção**: 8GB+ RAM, 4+ cores
- **GPU**: Opcional, melhora performance significativamente

## Evolução Futura

### Possíveis Melhorias

1. **Cache de Transcrições**: Redis/Memcached
2. **Queue System**: Celery para processamento assíncrono
3. **Múltiplos Workers**: Processar múltiplos vídeos em paralelo
4. **Database**: Persistir histórico de transcrições
5. **Webhooks**: Notificar quando transcrição completar
6. **Suporte a Outros Formatos**: Upload direto de arquivos

### Mantendo Clean Architecture

Ao adicionar features:
1. Definir interface no Domain
2. Criar use case no Application
3. Implementar serviço no Infrastructure
4. Expor via route no Presentation

---

**Conclusão**: A arquitetura foi desenhada para ser robusta, manutenível e preparada para crescimento, seguindo as melhores práticas da indústria.
