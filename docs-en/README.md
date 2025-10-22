# 📚 YTCaption - Complete Documentation

**YouTube video transcription system with Whisper AI**

---

## 🎯 Quick Navigation

### 👤 For Users

**Want to use the API?** → [User Guide](./user-guide/)

- [Quick Start (5min)](./user-guide/01-quick-start.md) - Getting started
- [Installation](./user-guide/02-installation.md) - Docker, Proxmox, bare metal
- [Configuration](./user-guide/03-configuration.md) - All env vars explained
- [API Usage](./user-guide/04-api-usage.md) - How to make requests
- [Troubleshooting](./user-guide/05-troubleshooting.md) - Common issues
- [Deployment](./user-guide/06-deployment.md) - Production (Nginx, SSL)
- [Monitoring](./user-guide/07-monitoring.md) - Grafana + Prometheus

---

### 👨‍💻 For Developers

**Want to contribute or understand the code?** → [Developer Guide](./developer-guide/)

- [Architecture Overview](./developer-guide/architecture-overview.md) - Clean Architecture
- [Contributing](./developer-guide/contributing.md) - How to contribute
- [Testing](./developer-guide/testing.md) - Unit tests, integration tests
- [Changelog](./developer-guide/changelog.md) - Version history

---

### 🏛️ Technical Architecture

**Want to understand how each module works?** → [Architecture](./architecture/)

#### Layers (Clean Architecture)

1. **[Domain Layer](./architecture/domain/)** - Pure business rules
2. **[Application Layer](./architecture/application/)** - Use Cases (orchestration)
3. **[Infrastructure Layer](./architecture/infrastructure/)** - Concrete implementations
4. **[Presentation Layer](./architecture/presentation/)** - FastAPI (controllers)
5. **[Config](./architecture/config/)** - Settings and validation

#### Main Modules

- **[YouTube Module](./architecture/infrastructure/youtube/)** - v3.0 Resilience System (5 layers)
- **[Whisper Module](./architecture/infrastructure/whisper/)** - v2.0 Parallel Transcription
- **[Storage Module](./architecture/infrastructure/storage/)** - File management + cleanup
- **[Monitoring](./architecture/infrastructure/monitoring/)** - Prometheus metrics

---

### 📊 Visual Diagrams

**Want to visualize flows and architecture?** → [Diagrams](./diagrams/)

- [Clean Architecture](./diagrams/clean-architecture.md) - Layers and dependencies
- [YouTube Resilience Flow](./diagrams/youtube-resilience-flow.md) - v3.0 (5 layers)
- [Parallel Transcription](./diagrams/parallel-transcription-flow.md) - v2.0 (workers)
- [Request Lifecycle](./diagrams/request-lifecycle.md) - Complete Request → Response
- [Design Patterns](./diagrams/design-patterns.md) - Applied patterns

---

## 🚀 Quick Links

| I want to... | Go to... |
|-------------|-----------|
| Get started in 5 minutes | [Quick Start](./user-guide/01-quick-start.md) |
| Configure YouTube Resilience v3.0 | [Configuration - YouTube Resilience](./user-guide/03-configuration.md#youtube-resilience-v30) |
| Fix 403 Forbidden error | [Troubleshooting - HTTP 403](./user-guide/05-troubleshooting.md#http-403-forbidden) |
| Understand the Downloader code | [YouTube Downloader](./architecture/infrastructure/youtube/downloader.md) |
| View Prometheus metrics | [Monitoring Guide](./user-guide/07-monitoring.md) |
| Contribute code | [Contributing Guide](./developer-guide/contributing.md) |
| Understand Clean Architecture | [Architecture Overview](./developer-guide/architecture-overview.md) |

---

## 📖 Documentation Structure

```
docs/
├── README.md (you are here)
│
├── user-guide/              # 📘 For end users
│   ├── 01-quick-start.md
│   ├── 02-installation.md
│   ├── 03-configuration.md
│   ├── 04-api-usage.md
│   ├── 05-troubleshooting.md
│   ├── 06-deployment.md
│   └── 07-monitoring.md
│
├── developer-guide/         # 👨‍💻 For contributors
│   ├── architecture-overview.md
│   ├── contributing.md
│   ├── testing.md
│   └── changelog.md
│
├── architecture/            # 🏛️ Technical documentation (mirrors src/)
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
├── diagrams/                # 📊 Visual diagrams
│   ├── clean-architecture.md
│   ├── youtube-resilience-flow.md
│   ├── parallel-transcription-flow.md
│   ├── request-lifecycle.md
│   └── design-patterns.md
│
└── old/                     # 📦 Previous documentation (reference)
```

---

## 🎓 Main Concepts

### YouTube Resilience v3.0

System with **5 layers of protection** against YouTube blocking:

1. **DNS Resilience** - Google DNS (8.8.8.8) + Cloudflare (1.1.1.1)
2. **Multi-Strategy** - 7 download strategies (direct, cookies, mobile, referer, extract, embedded, oauth)
3. **Rate Limiting** - Requests/min control + Circuit Breaker
4. **User-Agent Rotation** - 17 different User-Agents (Chrome, Firefox, Safari, Edge)
5. **Tor Proxy** - IP anonymization via SOCKS5

**Result**: Success rate 60% → 95% (+58%)

📖 [Complete documentation](./architecture/infrastructure/youtube/)

---

### Parallel Transcription v2.0

Parallel transcription system with **persistent workers**:

- Pre-warmed worker pool (avoids spawn overhead)
- Smart audio chunking (120s per chunk)
- Whisper model shared between workers
- Auto-cleanup of temporary files

**Result**: 3-5x faster than single-core

📖 [Complete documentation](./architecture/infrastructure/whisper/)

---

### Clean Architecture

Architecture in **4 layers** with **dependencies pointing inward**:

```
Infrastructure → Application → Domain ← (core)
Presentation ↗
```

**Benefits**:
- ✅ Testability (easy mocks)
- ✅ Maintainability (organized code)
- ✅ Scalability (add features without breaking)
- ✅ Framework independence (swap FastAPI/Whisper without rewriting)

📖 [Complete documentation](./developer-guide/architecture-overview.md)

---

## 📊 Project Statistics

### Code

- **Lines of code**: ~8,500 (Python)
- **Modules**: 55 Python files
- **Layers**: 4 (Domain, Application, Infrastructure, Presentation)
- **Tests**: Unit + Integration (pytest)

### Performance

- **Download success rate**: 95% (before: 60%)
- **Latency**: 3-5s (cache) / 30s-2min (CPU) / 8-12min (parallel)
- **Throughput**: 10-15 req/min (before: 2 req/min)
- **RAM usage**: 2GB (before: 8GB)

### Monitoring

- **Prometheus metrics**: 26 metrics (YouTube) + 15 metrics (global)
- **Grafana dashboards**: 2 dashboards (YouTube Resilience + System)
- **Uptime**: 99.5% (before: 92%)

---

## 🤝 Contributing

Want to contribute? See the [Contributing Guide](./developer-guide/contributing.md)!

Main areas:
- 🐛 Bug fixes
- ✨ New features (download strategies, Whisper optimizations)
- 📖 Documentation (improvements, examples, translations)
- 🧪 Tests (increase coverage)

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/issues)
- **Discussions**: [GitHub Discussions](https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/discussions)
- **Email**: john@example.com

---

## 📝 License

MIT License - see [LICENSE](../LICENSE)

---

**Documentation Version**: 3.0.0  
**Last updated**: 10/22/2025  
**Maintained by**: [@JohnHeberty](https://github.com/JohnHeberty)
