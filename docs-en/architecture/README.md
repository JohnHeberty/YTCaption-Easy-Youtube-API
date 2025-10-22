# 🏛️ Architecture Documentation

**Documentação técnica completa - espelha estrutura de `src/`**

---

## 📚 Visão Geral

Esta seção documenta **cada módulo do código** seguindo **Clean Architecture**.

A estrutura desta documentação **espelha exatamente** a estrutura de `src/`:

```
src/domain/                  → docs/architecture/domain/
src/application/             → docs/architecture/application/
src/infrastructure/youtube/  → docs/architecture/infrastructure/youtube/
src/presentation/            → docs/architecture/presentation/
```

---

## 🎯 Clean Architecture - 4 Camadas

### 1. [Domain Layer](./domain/) (Núcleo)

**Responsabilidade**: Regras de negócio puras

**Contém**:
- Entities (Transcription, VideoFile)
- Value Objects (TranscriptionSegment, YouTubeURL)
- Interfaces (contratos)
- Exceptions

**Regra**: Não depend

e de NADA

---

### 2. [Application Layer](./application/) (Use Cases)

**Responsabilidade**: Orquestração da lógica de aplicação

**Contém**:
- Use Cases (TranscribeVideo, CleanupFiles)
- DTOs (Data Transfer Objects)

**Depende de**: Domain (interfaces)

---

### 3. [Infrastructure Layer](./infrastructure/) (Implementações)

**Responsabilidade**: Implementações concretas

**Módulos principais**:
- **[YouTube](./infrastructure/youtube/)** - v3.0 Resilience System
- **[Whisper](./infrastructure/whisper/)** - v2.0 Parallel Transcription
- **[Storage](./infrastructure/storage/)** - File management
- **[Cache](./infrastructure/cache/)** - Transcription cache
- **[Monitoring](./infrastructure/monitoring/)** - Prometheus metrics
- **[Validators](./infrastructure/validators/)** - Audio validation
- **[Utils](./infrastructure/utils/)** - FFmpeg, Circuit Breaker

**Depende de**: Domain (interfaces)

---

### 4. [Presentation Layer](./presentation/) (API)

**Responsabilidade**: Controllers (FastAPI)

**Contém**:
- Routes (endpoints)
- Middlewares (logging, Prometheus)
- Dependency Injection

**Depende de**: Application (Use Cases)

---

### 5. [Config](./config/)

**Responsabilidade**: Configurações e validação de env vars

---

## 🚀 Módulos Principais

### YouTube Resilience v3.0

Sistema com 5 camadas de proteção:

- **[Downloader](./infrastructure/youtube/downloader.md)** - Orchestrator (Facade)
- **[DownloadConfig](./infrastructure/youtube/download-config.md)** - Configurações centralizadas
- **[DownloadStrategies](./infrastructure/youtube/download-strategies.md)** - 7 estratégias
- **[RateLimiter](./infrastructure/youtube/rate-limiter.md)** - Rate limiting + Circuit Breaker
- **[UserAgentRotator](./infrastructure/youtube/user-agent-rotator.md)** - 17 User-Agents
- **[ProxyManager](./infrastructure/youtube/proxy-manager.md)** - Tor SOCKS5
- **[Metrics](./infrastructure/youtube/metrics.md)** - 26 métricas Prometheus

📖 [Documentação completa](./infrastructure/youtube/)

---

### Whisper Parallel v2.0

Sistema de transcrição paralela:

- **[TranscriptionService](./infrastructure/whisper/transcription-service.md)** - Core (single)
- **[ParallelTranscriptionService](./infrastructure/whisper/parallel-transcription-service.md)** - Parallel workers
- **[ModelCache](./infrastructure/whisper/model-cache.md)** - Singleton cache
- **[PersistentWorkerPool](./infrastructure/whisper/persistent-worker-pool.md)** - Worker pool
- **[TranscriptionFactory](./infrastructure/whisper/transcription-factory.md)** - Factory pattern

📖 [Documentação completa](./infrastructure/whisper/)

---

## 📊 Navegação

### Por Camada

| Camada | Documentação | Código |
|--------|--------------|--------|
| Domain | [docs](./domain/) | [src/domain/](../../src/domain/) |
| Application | [docs](./application/) | [src/application/](../../src/application/) |
| Infrastructure | [docs](./infrastructure/) | [src/infrastructure/](../../src/infrastructure/) |
| Presentation | [docs](./presentation/) | [src/presentation/](../../src/presentation/) |
| Config | [docs](./config/) | [src/config/](../../src/config/) |

### Por Módulo

| Módulo | Versão | Documentação |
|--------|--------|--------------|
| YouTube | v3.0 | [docs](./infrastructure/youtube/) |
| Whisper | v2.0 | [docs](./infrastructure/whisper/) |
| Storage | v2.0 | [docs](./infrastructure/storage/) |
| Cache | v2.0 | [docs](./infrastructure/cache/) |
| Monitoring | v3.0 | [docs](./infrastructure/monitoring/) |

---

## 🔍 Como Usar Esta Documentação

### Sou novo no projeto

1. Leia [Domain Layer](./domain/) - Entenda o núcleo
2. Leia [Application Layer](./application/) - Entenda os Use Cases
3. Escolha um módulo (YouTube ou Whisper) e explore

### Quero entender um módulo específico

1. Vá para `architecture/infrastructure/<módulo>/`
2. Leia o `README.md` do módulo
3. Leia os arquivos individuais (ex: `downloader.md`)

### Quero modificar o código

1. Encontre o arquivo Python (ex: `src/infrastructure/youtube/downloader.py`)
2. Leia a documentação correspondente (`architecture/infrastructure/youtube/downloader.md`)
3. Entenda dependências (seção "Relacionamentos")
4. Faça as mudanças
5. Atualize a documentação correspondente

---

## 📖 Padrão de Documentação

Cada arquivo de módulo segue este padrão:

```markdown
# NomeDoMódulo

**Path**: `src/camada/modulo.py`

## Visão Geral
Responsabilidade, camada, versão

## Propósito
O que faz e por quê

## Arquitetura
Dependências, padrões aplicados

## Interface Pública
Métodos, parâmetros, exceções

## Fluxo de Execução
Diagrama em texto

## Métricas Emitidas
(se aplicável)

## Exemplo de Uso
Código funcional

## Relacionamentos
Usa, Usado por, Implementa

## Referências
Links para diagramas, outros módulos
```

---

## 🔗 Referências

- [Diagrams](../diagrams/) - Diagramas visuais
- [Developer Guide](../developer-guide/) - Contribuir, testar
- [User Guide](../user-guide/) - Usar a API

---

**[← Voltar para documentação principal](../README.md)**
