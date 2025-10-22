# 📚 YTCaption - Documentação Completa

**Sistema de transcrição de vídeos do YouTube com Whisper AI**

---

## 🎯 Navegação Rápida

### 👤 Para Usuários

**Quer usar a API?** → [User Guide](./user-guide/)

- [Quick Start (5min)](./user-guide/01-quick-start.md) - Primeiros passos
- [Instalação](./user-guide/02-installation.md) - Docker, Proxmox, bare metal
- [Configuração](./user-guide/03-configuration.md) - Todas as env vars explicadas
- [API Usage](./user-guide/04-api-usage.md) - Como fazer requests
- [Troubleshooting](./user-guide/05-troubleshooting.md) - Problemas comuns
- [Deployment](./user-guide/06-deployment.md) - Produção (Nginx, SSL)
- [Monitoring](./user-guide/07-monitoring.md) - Grafana + Prometheus

---

### 👨‍💻 Para Desenvolvedores

**Quer contribuir ou entender o código?** → [Developer Guide](./developer-guide/)

- [Architecture Overview](./developer-guide/architecture-overview.md) - Clean Architecture
- [Contributing](./developer-guide/contributing.md) - Como contribuir
- [Testing](./developer-guide/testing.md) - Unit tests, integration tests
- [Changelog](./developer-guide/changelog.md) - Histórico de versões

---

### 🏛️ Arquitetura Técnica

**Quer entender como cada módulo funciona?** → [Architecture](./architecture/)

#### Camadas (Clean Architecture)

1. **[Domain Layer](./architecture/domain/)** - Regras de negócio puras
2. **[Application Layer](./architecture/application/)** - Use Cases (orquestração)
3. **[Infrastructure Layer](./architecture/infrastructure/)** - Implementações concretas
4. **[Presentation Layer](./architecture/presentation/)** - FastAPI (controllers)
5. **[Config](./architecture/config/)** - Configurações e validação

#### Módulos Principais

- **[YouTube Module](./architecture/infrastructure/youtube/)** - v3.0 Resilience System (5 camadas)
- **[Whisper Module](./architecture/infrastructure/whisper/)** - v2.0 Parallel Transcription
- **[Storage Module](./architecture/infrastructure/storage/)** - File management + cleanup
- **[Monitoring](./architecture/infrastructure/monitoring/)** - Prometheus metrics

---

### 📊 Diagramas Visuais

**Quer visualizar fluxos e arquitetura?** → [Diagrams](./diagrams/)

- [Clean Architecture](./diagrams/clean-architecture.md) - Camadas e dependências
- [YouTube Resilience Flow](./diagrams/youtube-resilience-flow.md) - v3.0 (5 camadas)
- [Parallel Transcription](./diagrams/parallel-transcription-flow.md) - v2.0 (workers)
- [Request Lifecycle](./diagrams/request-lifecycle.md) - Request → Response completo
- [Design Patterns](./diagrams/design-patterns.md) - Padrões aplicados

---

## 🚀 Quick Links

| Eu quero... | Ir para... |
|-------------|-----------|
| Começar em 5 minutos | [Quick Start](./user-guide/01-quick-start.md) |
| Configurar YouTube Resilience v3.0 | [Configuration - YouTube Resilience](./user-guide/03-configuration.md#youtube-resilience-v30) |
| Resolver erro 403 Forbidden | [Troubleshooting - HTTP 403](./user-guide/05-troubleshooting.md#http-403-forbidden) |
| Entender o código do Downloader | [YouTube Downloader](./architecture/infrastructure/youtube/downloader.md) |
| Ver métricas Prometheus | [Monitoring Guide](./user-guide/07-monitoring.md) |
| Contribuir com código | [Contributing Guide](./developer-guide/contributing.md) |
| Entender Clean Architecture | [Architecture Overview](./developer-guide/architecture-overview.md) |

---

## 📖 Estrutura da Documentação

```
docs/
├── README.md (você está aqui)
│
├── user-guide/              # 📘 Para usuários finais
│   ├── 01-quick-start.md
│   ├── 02-installation.md
│   ├── 03-configuration.md
│   ├── 04-api-usage.md
│   ├── 05-troubleshooting.md
│   ├── 06-deployment.md
│   └── 07-monitoring.md
│
├── developer-guide/         # 👨‍💻 Para contribuidores
│   ├── architecture-overview.md
│   ├── contributing.md
│   ├── testing.md
│   └── changelog.md
│
├── architecture/            # 🏛️ Documentação técnica (espelha src/)
│   ├── domain/              # Domain Layer
│   ├── application/         # Application Layer
│   ├── infrastructure/      # Infrastructure Layer
│   │   ├── youtube/         # YouTube module (v3.0)
│   │   ├── whisper/         # Whisper module (v2.0)
│   │   ├── storage/         # Storage + cleanup
│   │   ├── cache/           # Transcription cache
│   │   ├── monitoring/      # Prometheus metrics
│   │   ├── validators/      # Audio validation
│   │   └── utils/           # FFmpeg, Circuit Breaker
│   ├── presentation/        # Presentation Layer (API)
│   └── config/              # Settings
│
├── diagrams/                # 📊 Diagramas visuais
│   ├── clean-architecture.md
│   ├── youtube-resilience-flow.md
│   ├── parallel-transcription-flow.md
│   ├── request-lifecycle.md
│   └── design-patterns.md
│
└── old/                     # 📦 Documentação anterior (referência)
```

---

## 🎓 Conceitos Principais

### YouTube Resilience v3.0

Sistema com **5 camadas de proteção** contra bloqueios do YouTube:

1. **DNS Resilience** - Google DNS (8.8.8.8) + Cloudflare (1.1.1.1)
2. **Multi-Strategy** - 7 estratégias de download (direct, cookies, mobile, referer, extract, embedded, oauth)
3. **Rate Limiting** - Controle de requests/min + Circuit Breaker
4. **User-Agent Rotation** - 17 User-Agents diferentes (Chrome, Firefox, Safari, Edge)
5. **Tor Proxy** - Anonimização de IP via SOCKS5

**Resultado**: Taxa de sucesso 60% → 95% (+58%)

📖 [Documentação completa](./architecture/infrastructure/youtube/)

---

### Parallel Transcription v2.0

Sistema de transcrição paralela com **workers persistentes**:

- Worker pool pré-aquecido (evita overhead de spawn)
- Chunking inteligente de áudio (120s por chunk)
- Modelo Whisper compartilhado entre workers
- Auto-cleanup de arquivos temporários

**Resultado**: 3-5x mais rápido que single-core

📖 [Documentação completa](./architecture/infrastructure/whisper/)

---

### Clean Architecture

Arquitetura em **4 camadas** com **dependências apontando para dentro**:

```
Infrastructure → Application → Domain ← (núcleo)
Presentation ↗
```

**Benefícios**:
- ✅ Testabilidade (mocks fáceis)
- ✅ Manutenibilidade (código organizado)
- ✅ Escalabilidade (adicionar features sem quebrar)
- ✅ Independência de frameworks (trocar FastAPI/Whisper sem reescrever)

📖 [Documentação completa](./developer-guide/architecture-overview.md)

---

## 📊 Estatísticas do Projeto

### Código

- **Linhas de código**: ~8.500 (Python)
- **Módulos**: 55 arquivos Python
- **Camadas**: 4 (Domain, Application, Infrastructure, Presentation)
- **Testes**: Unit + Integration (pytest)

### Performance

- **Taxa de sucesso downloads**: 95% (antes: 60%)
- **Latência**: 3-5s (cache) / 30s-2min (CPU) / 8-12min (paralelo)
- **Throughput**: 10-15 req/min (antes: 2 req/min)
- **Uso de RAM**: 2GB (antes: 8GB)

### Monitoramento

- **Métricas Prometheus**: 26 métricas (YouTube) + 15 métricas (global)
- **Dashboards Grafana**: 2 dashboards (YouTube Resilience + System)
- **Uptime**: 99.5% (antes: 92%)

---

## 🤝 Contribuindo

Quer contribuir? Veja o [Contributing Guide](./developer-guide/contributing.md)!

Principais áreas:
- 🐛 Bug fixes
- ✨ Novas features (estratégias de download, otimizações Whisper)
- 📖 Documentação (melhorias, exemplos, traduções)
- 🧪 Testes (aumentar cobertura)

---

## 📞 Suporte

- **Issues**: [GitHub Issues](https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/issues)
- **Discussions**: [GitHub Discussions](https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/discussions)
- **Email**: john@example.com

---

## 📝 Licença

MIT License - veja [LICENSE](../LICENSE)

---

**Versão da Documentação**: 3.0.0  
**Última atualização**: 22/10/2025  
**Mantido por**: [@JohnHeberty](https://github.com/JohnHeberty)
