# 🛠️ Developer Guide

Technical documentation for contributors and developers.

---

## 📚 Documentation Index

### 🏛️ [Architecture Overview](./architecture-overview.md)
Complete guide to YTCaption's Clean Architecture implementation with SOLID principles.

**Topics covered**:
- Clean Architecture layers (Domain, Application, Infrastructure, Presentation)
- SOLID principles with code examples (S, O, L, I, D)
- Complete project structure breakdown (`src/` tree)
- Data flow diagrams (Request → Response)
- Dependency Injection with FastAPI
- Design patterns (Strategy, Circuit Breaker, Factory, Repository)
- Step-by-step guide for adding new features (Vimeo example)
- Best practices (naming, errors, logging, testing, documentation)
- Architecture benefits (testability, maintainability, scalability)

**Perfect for**: Understanding the codebase architecture and design decisions.

---

### 🤝 [Contributing Guide](./contributing.md)
Guidelines for contributing to YTCaption project.

**Topics covered**:
- Getting started (fork, clone, setup)
- Development workflow (branch strategy, commit conventions)
- Code standards (PEP 8, Black, Flake8, MyPy)
- Testing requirements (80% coverage, pytest)
- Documentation requirements (docstrings, user guides)
- Pull request process (checklist, review, approval)
- Issue guidelines (bug reports, feature requests)
- Release process (semantic versioning, changelog)

**Perfect for**: New contributors learning the development workflow.

---

### 🧪 [Testing Guide](./testing.md)
Comprehensive testing strategy and guidelines.

**Topics covered**:
- Testing philosophy (Test Pyramid: 70% unit, 20% integration, 10% e2e)
- Test types (unit, integration, end-to-end)
- Setup (pytest, coverage, fixtures)
- Running tests (basic commands, by type, parallel execution)
- Writing tests (AAA pattern, naming conventions, parametrized tests)
- Test fixtures (basic, scopes, cleanup)
- Mocking strategies (unittest.mock, spies)
- Code coverage (measuring, targets, configuration)
- CI/CD integration (GitHub Actions, pre-commit hooks)
- Best practices (DO's and DON'Ts)

**Perfect for**: Writing high-quality tests and achieving coverage targets.

---

### 📜 [Changelog](./changelog.md)
Project version history and release notes.

**Topics covered**:
- Version history (v3.0.0, v2.2.0, v2.1.0, v2.0.0, v1.x)
- Release notes for each version
- Breaking changes highlighted
- Migration guides
- Performance improvements documented

**Perfect for**: Understanding what changed between versions.

---

## 🚀 Quick Start for Contributors

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
git remote add upstream https://github.com/YourOrg/YTCaption-Easy-Youtube-API.git
```

### 2. Setup Development Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov black flake8 mypy

# Or use Makefile
make dev-install
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Verify Setup

```bash
# Run tests
make test

# Check code style
make lint

# Run application
make run
```

---

## 📖 Development Resources

### Code Style

- **Format code**: `make format` (Black auto-formatter)
- **Check style**: `make lint` (Flake8 + MyPy)
- **Line length**: 100 characters
- **Type hints**: Required for all functions

### Testing

- **Run all tests**: `make test`
- **With coverage**: `make coverage`
- **Unit tests only**: `pytest tests/unit/`
- **Minimum coverage**: 80%

### Commit Messages

Follow **Conventional Commits**:
```
feat(youtube): Add Tor proxy support
fix(transcription): Handle empty audio files
docs(api): Update endpoint examples
refactor(storage): Extract file cleanup service
perf(whisper): Reduce memory usage in parallel mode
```

### Branch Strategy

- `main`: Production-ready code
- `develop`: Development branch
- `feature/*`: New features
- `bugfix/*`: Bug fixes
- `hotfix/*`: Urgent production fixes

---

## 🏗️ Architecture Overview

YTCaption follows **Clean Architecture** with 4 layers:

```
┌────────────────────────────────────────────────────┐
│         4. Infrastructure (External Tools)         │
│      FastAPI, Whisper, YouTube, FFmpeg, Tor       │
├────────────────────────────────────────────────────┤
│         3. Presentation (API Controllers)          │
│           Routes, Schemas, Middlewares            │
├────────────────────────────────────────────────────┤
│     2. Application (Use Cases / Workflows)         │
│  TranscribeVideo, DownloadAudio, CleanupFiles     │
├────────────────────────────────────────────────────┤
│      1. Domain (Business Rules / Entities)         │
│    YouTubeURL, Transcription, Interfaces          │
└────────────────────────────────────────────────────┘
```

**Key Principles**:
- Dependencies point inward (Infrastructure → Application → Domain)
- Domain layer has NO external dependencies
- Use interfaces for abstraction (Dependency Inversion)
- One responsibility per class (Single Responsibility)

Read more: [Architecture Overview](./architecture-overview.md)

---

## 🧩 Project Structure

```
src/
├── domain/              # Business logic (entities, value objects, interfaces)
├── application/         # Use cases (orchestration)
├── infrastructure/      # External tools (Whisper, YouTube, storage)
│   ├── whisper/         # Transcription implementations
│   ├── youtube/         # v3.0 Download resilience system
│   ├── storage/         # File management
│   ├── cache/           # Caching layer
│   └── monitoring/      # Prometheus metrics
├── presentation/        # API layer (FastAPI routes)
└── config/              # Configuration (settings.py)
```

---

## 🎯 Common Tasks

### Adding a New Feature

**Example**: Add Vimeo support

1. **Create interface** (Domain layer):
```python
# src/domain/interfaces/video_downloader.py
class IVideoDownloader(ABC):
    @abstractmethod
    def download(self, url: str) -> Path: ...
    
    @abstractmethod
    def supports_url(self, url: str) -> bool: ...
```

2. **Implement for Vimeo** (Infrastructure layer):
```python
# src/infrastructure/vimeo/downloader.py
class VimeoDownloader(IVideoDownloader):
    def download(self, url: str) -> Path:
        # Implementation
        pass
    
    def supports_url(self, url: str) -> bool:
        return "vimeo.com" in url
```

3. **Update use case** (Application layer):
```python
# src/application/use_cases/transcribe_video.py
class TranscribeVideoUseCase:
    def __init__(self, downloaders: List[IVideoDownloader], ...):
        self._downloaders = downloaders
```

4. **Register in DI container** (Presentation layer):
```python
# src/presentation/api/dependencies.py
@lru_cache()
def get_vimeo_downloader() -> IVideoDownloader:
    return VimeoDownloader()
```

5. **Add tests**:
```python
# tests/unit/infrastructure/test_vimeo_downloader.py
def test_vimeo_download():
    downloader = VimeoDownloader()
    result = downloader.download("https://vimeo.com/123")
    assert result.exists()
```

Read more: [Architecture Overview § Adding New Features](./architecture-overview.md#adding-new-features)

---

## 📊 Key Technologies

- **Language**: Python 3.9 - 3.11
- **Framework**: FastAPI 0.115+
- **Testing**: pytest, pytest-cov, pytest-asyncio
- **Code Quality**: Black, Flake8, MyPy
- **Transcription**: OpenAI Whisper
- **Video Download**: yt-dlp (v3.0 with 7 strategies)
- **Audio Processing**: FFmpeg
- **Monitoring**: Prometheus + Grafana
- **Containerization**: Docker + Docker Compose

---

## 🔗 Related Documentation

- **[User Guide](../user-guide/)**: End-user documentation
- **[Architecture Diagrams](../old/09-ARCHITECTURE.md)**: Detailed technical diagrams
- **[v3.0 YouTube Resilience](../old/YOUTUBE-RESILIENCE-v3.0.md)**: Download system architecture
- **[v2.0 Parallel Transcription](../old/10-PARALLEL-ARCHITECTURE.md)**: Worker pool architecture

---

## 💬 Getting Help

- **Documentation**: Read guides in this folder
- **GitHub Issues**: [Report bugs or request features](https://github.com/YourOrg/YTCaption/issues)
- **GitHub Discussions**: [Ask questions or discuss ideas](https://github.com/YourOrg/YTCaption/discussions)
- **Email**: maintainers@example.com

---

## 🙏 Thank You!

Thank you for contributing to YTCaption! Your contributions help make this project better for everyone. 🎉

---

**[⬅️ Back to Main Documentation](../README.md)**

---

**Version**: 3.0.0  
**Last Updated**: October 22, 2025  
**Contributors**: YTCaption Team
