# 🤝 Contributing Guide

Guidelines for contributing to YTCaption project.

---

## 📋 Table of Contents

1. [Welcome](#welcome)
2. [Code of Conduct](#code-of-conduct)
3. [Getting Started](#getting-started)
4. [Development Workflow](#development-workflow)
5. [Code Standards](#code-standards)
6. [Testing Requirements](#testing-requirements)
7. [Documentation](#documentation)
8. [Pull Request Process](#pull-request-process)
9. [Issue Guidelines](#issue-guidelines)
10. [Release Process](#release-process)

---

## Welcome

Thank you for considering contributing to YTCaption! 🎉

We welcome contributions of all kinds:
- 🐛 Bug reports and fixes
- ✨ New features and enhancements
- 📝 Documentation improvements
- 🧪 Test coverage improvements
- 🌍 Translations
- 💡 Ideas and suggestions

**First time contributing?** Check out issues labeled [`good first issue`](https://github.com/YourOrg/YTCaption/labels/good%20first%20issue).

---

## Code of Conduct

### Our Standards

**Be respectful**:
- Use welcoming and inclusive language
- Respect differing viewpoints and experiences
- Accept constructive criticism gracefully
- Focus on what's best for the community

**Be collaborative**:
- Help others learn and grow
- Share knowledge generously
- Give credit where due

**Be professional**:
- Avoid personal attacks
- Keep discussions on-topic
- Be patient with newcomers

**Unacceptable behavior**:
- Harassment, trolling, or discriminatory comments
- Publishing others' private information
- Other conduct that could reasonably be considered inappropriate

**Enforcement**: Violations may result in temporary or permanent bans. Report issues to [maintainers@example.com].

---

## Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API

# Add upstream remote
git remote add upstream https://github.com/YourOrg/YTCaption-Easy-Youtube-API.git
```

### 2. Set Up Development Environment

**Requirements**:
- Python 3.9 - 3.11 (3.12 not supported yet)
- FFmpeg installed
- 8 GB RAM minimum (16 GB recommended)
- GPU optional (NVIDIA CUDA for faster transcription)

**Installation**:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov black flake8 mypy

# Or use Makefile
make dev-install
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# Minimum required:
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
TEMP_DIR=./temp
LOG_LEVEL=INFO
```

### 4. Verify Setup

```bash
# Run tests
make test

# Check code style
make lint

# Run application
make run

# Test API
curl http://localhost:8000/health
```

**Expected output**:
```json
{
  "status": "healthy",
  "version": "3.0.0",
  "whisper_model": "base",
  "device": "cpu"
}
```

---

## Development Workflow

### Branch Strategy

**Main branches**:
- `main`: Production-ready code (protected)
- `develop`: Development branch (protected)

**Feature branches**:
- `feature/description`: New features
- `bugfix/description`: Bug fixes
- `hotfix/description`: Urgent production fixes
- `docs/description`: Documentation only
- `refactor/description`: Code refactoring
- `test/description`: Test improvements

**Example**:
```bash
# Create feature branch from develop
git checkout develop
git pull upstream develop
git checkout -b feature/add-vimeo-support

# Work on your feature...
git add .
git commit -m "feat: Add Vimeo downloader support"

# Push to your fork
git push origin feature/add-vimeo-support

# Create Pull Request on GitHub
```

### Commit Message Convention

We follow **Conventional Commits** specification:

**Format**:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style (formatting, no logic change)
- `refactor`: Code refactoring (no feature/bug change)
- `perf`: Performance improvement
- `test`: Add/update tests
- `build`: Build system changes
- `ci`: CI/CD changes
- `chore`: Maintenance tasks

**Examples**:

```bash
# Feature
feat(youtube): Add Tor proxy support for blocked regions

Implements Tor SOCKS5 proxy as fallback strategy when direct
download fails due to regional restrictions.

- Add TorProxyStrategy class
- Configure Tor container in docker-compose
- Add ENABLE_TOR_PROXY environment variable
- Add circuit breaker protection

Closes #123

# Bug fix
fix(transcription): Handle empty audio files gracefully

Previously crashed with IndexError when audio file had no content.
Now raises TranscriptionError with clear message.

Fixes #456

# Documentation
docs(api): Update transcription endpoint examples

Add curl and Python examples for all query parameters.

# Refactoring
refactor(storage): Extract file cleanup to separate service

Moves cleanup logic from TranscribeVideoUseCase to dedicated
FileCleanupManager for better separation of concerns.

# Performance
perf(whisper): Reduce memory usage in parallel transcription

Use memory-mapped files for audio chunks instead of loading
entire file into RAM. Reduces memory footprint by 60%.
```

**Rules**:
- ✅ Use imperative mood ("Add feature" not "Added feature")
- ✅ First line ≤ 72 characters
- ✅ Body explains WHAT and WHY, not HOW
- ✅ Reference issues/PRs in footer

---

## Code Standards

### Python Style Guide

**Follow PEP 8** with these adjustments:
- Line length: 100 characters (Black default)
- Use Black for auto-formatting
- Use type hints for all functions

### Code Formatting

**Black** (auto-formatter):
```bash
# Format all code
make format

# Or manually
black src/ tests/

# Check formatting without changes
black --check src/ tests/
```

**Configuration** (pyproject.toml):
```toml
[tool.black]
line-length = 100
target-version = ['py311']
```

### Linting

**Flake8** (style checker):
```bash
# Check code style
make lint

# Or manually
flake8 src/ tests/
```

**Configuration** (pyproject.toml):
```toml
[tool.pylint]
max-line-length = 120
disable = [
    "C0111",  # missing-docstring
    "C0103",  # invalid-name
]
```

**MyPy** (type checker):
```bash
# Check types
mypy src/

# Configuration in pyproject.toml
```

### Naming Conventions

**Files and directories**:
- Lowercase with underscores: `transcription_service.py`
- No spaces or special characters

**Classes**:
- PascalCase: `TranscriptionService`
- Interfaces: `ITranscriptionService` (prefix with `I`)

**Functions and variables**:
- snake_case: `download_video()`, `audio_path`
- Private: `_internal_method()` (prefix with `_`)

**Constants**:
- UPPER_SNAKE_CASE: `MAX_RETRIES`, `DEFAULT_MODEL`

**Example**:
```python
# Good
class TranscriptionService(ITranscriptionService):
    MAX_RETRIES = 3
    
    def __init__(self, model: str):
        self._model = model
        self.retry_count = 0
    
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        return self._process_audio(audio_path)
    
    def _process_audio(self, path: Path) -> TranscriptionResult:
        # Private helper method
        pass

# Bad
class transcription_service:  # ❌ Wrong case
    maxRetries = 3  # ❌ camelCase constant
    
    def Transcribe(self, AudioPath):  # ❌ Wrong case
        return self.processAudio(AudioPath)
```

### Type Hints

**Always use type hints**:
```python
from typing import List, Optional, Dict, Any
from pathlib import Path

# Good ✅
def download_video(url: str, output_dir: Path) -> Optional[Path]:
    """Download video and return path."""
    pass

def process_segments(segments: List[Dict[str, Any]]) -> List[TranscriptionSegment]:
    """Convert raw segments to domain objects."""
    pass

# Bad ❌
def download_video(url, output_dir):  # No type hints
    pass
```

### Docstrings

**Google style docstrings**:
```python
def transcribe(
    self,
    audio_path: Path,
    language: str = "en",
    task: str = "transcribe"
) -> TranscriptionResult:
    """
    Transcribe audio file using Whisper.
    
    Args:
        audio_path: Path to audio file (WAV, MP3, etc.)
        language: Language code (ISO 639-1, e.g., "en", "es")
        task: Task type ("transcribe" or "translate")
    
    Returns:
        TranscriptionResult with text and timestamped segments
    
    Raises:
        FileNotFoundError: If audio file doesn't exist
        TranscriptionError: If Whisper transcription fails
        ValueError: If language code is invalid
    
    Example:
        >>> service = WhisperTranscriptionService("base")
        >>> result = service.transcribe(Path("audio.wav"), language="en")
        >>> print(result.text)
        "Hello, world!"
    
    Note:
        Large files (>100MB) may take several minutes to process.
    """
    pass
```

**Required sections**:
- Summary (one-line description)
- `Args`: All parameters
- `Returns`: Return value and type
- `Raises`: All exceptions
- `Example`: Usage example (optional but recommended)

### Error Handling

**Use specific exceptions**:
```python
# Good ✅
from src.domain.exceptions import InvalidYouTubeURLError, DownloadError

def download(self, url: str) -> Path:
    if not self._is_valid_url(url):
        raise InvalidYouTubeURLError(f"Invalid YouTube URL: {url}")
    
    try:
        return yt_dlp.download(url)
    except yt_dlp.DownloadError as e:
        raise DownloadError(f"Failed to download {url}: {e}") from e

# Bad ❌
def download(self, url: str) -> Path:
    if not self._is_valid_url(url):
        raise Exception("Invalid URL")  # Too generic
    
    try:
        return yt_dlp.download(url)
    except Exception:  # Too broad
        return None  # Swallowing exception
```

**Exception hierarchy**:
```python
# src/domain/exceptions.py
class DomainException(Exception):
    """Base exception for domain layer"""
    pass

class InvalidYouTubeURLError(DomainException):
    """Invalid YouTube URL format"""
    pass

class VideoNotFoundError(DomainException):
    """Video not found or unavailable"""
    pass
```

### Logging

**Use structured logging** (loguru):
```python
from loguru import logger

# Good ✅
logger.info(f"Downloading video: {url}")
logger.info(f"Transcription complete: {len(result.text)} chars, {duration:.2f}s")
logger.warning(f"Strategy {strategy} failed, trying next: {e}")
logger.error(f"All strategies failed for {url}", exc_info=True)

# Bad ❌
print(f"Downloading {url}")  # Use logger, not print
logger.info("Transcription complete")  # Add useful details
logger.error("Failed")  # Too vague, add context
```

**Log levels**:
- `DEBUG`: Detailed debugging info
- `INFO`: General informational messages
- `WARNING`: Something unexpected but handled
- `ERROR`: Error occurred, may affect functionality
- `CRITICAL`: Critical failure, application may crash

---

## Testing Requirements

### Test Coverage

**Minimum coverage**: 80% for new code

**Check coverage**:
```bash
# Run tests with coverage report
make coverage

# Or manually
pytest --cov=src --cov-report=html --cov-report=term

# Open HTML report
open htmlcov/index.html  # Mac/Linux
start htmlcov/index.html  # Windows
```

### Writing Tests

**Test structure**:
```
tests/
├── unit/                  # Unit tests (no external dependencies)
│   ├── domain/
│   ├── application/
│   └── infrastructure/
├── integration/           # Integration tests (with external services)
│   ├── test_youtube_download.py
│   └── test_whisper_transcription.py
└── e2e/                   # End-to-end tests (full API workflow)
    └── test_api_transcription.py
```

**Unit test example**:
```python
# tests/unit/domain/test_youtube_url.py
import pytest
from src.domain.value_objects import YouTubeURL
from src.domain.exceptions import InvalidYouTubeURLError

class TestYouTubeURL:
    """Test YouTubeURL value object."""
    
    def test_valid_url(self):
        """Should accept valid YouTube URLs."""
        url = YouTubeURL("https://youtube.com/watch?v=123")
        assert url.value == "https://youtube.com/watch?v=123"
    
    def test_invalid_url(self):
        """Should reject non-YouTube URLs."""
        with pytest.raises(InvalidYouTubeURLError):
            YouTubeURL("https://vimeo.com/123")
    
    @pytest.mark.parametrize("url,expected_id", [
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ])
    def test_extract_video_id(self, url: str, expected_id: str):
        """Should extract video ID from various URL formats."""
        youtube_url = YouTubeURL(url)
        assert youtube_url.video_id() == expected_id
```

**Mocking dependencies**:
```python
# tests/unit/application/test_transcribe_use_case.py
from unittest.mock import Mock, patch
import pytest
from pathlib import Path

from src.application.use_cases import TranscribeVideoUseCase
from src.domain.interfaces import IDownloader, ITranscriptionService, IStorageService

class TestTranscribeVideoUseCase:
    """Test TranscribeVideoUseCase."""
    
    @pytest.fixture
    def mock_downloader(self):
        """Mock downloader."""
        mock = Mock(spec=IDownloader)
        mock.download.return_value = Path("audio.wav")
        return mock
    
    @pytest.fixture
    def mock_transcriber(self):
        """Mock transcription service."""
        mock = Mock(spec=ITranscriptionService)
        mock.transcribe.return_value = TranscriptionResult(
            text="Test transcription",
            segments=[],
            language="en"
        )
        return mock
    
    @pytest.fixture
    def mock_storage(self):
        """Mock storage service."""
        return Mock(spec=IStorageService)
    
    def test_execute_success(self, mock_downloader, mock_transcriber, mock_storage):
        """Should successfully transcribe video."""
        # Arrange
        use_case = TranscribeVideoUseCase(
            downloader=mock_downloader,
            transcriber=mock_transcriber,
            storage=mock_storage
        )
        
        # Act
        result = use_case.execute("https://youtube.com/watch?v=123")
        
        # Assert
        assert result.text == "Test transcription"
        mock_downloader.download.assert_called_once()
        mock_transcriber.transcribe.assert_called_once()
        mock_storage.cleanup.assert_called_once()
```

**Integration test example**:
```python
# tests/integration/test_whisper_transcription.py
import pytest
from pathlib import Path
from src.infrastructure.whisper import WhisperTranscriptionService

@pytest.mark.integration
@pytest.mark.slow
class TestWhisperTranscription:
    """Integration tests for Whisper transcription."""
    
    def test_transcribe_real_audio(self, tmp_path):
        """Should transcribe real audio file."""
        # Arrange
        service = WhisperTranscriptionService(model="tiny")
        audio_path = Path("tests/fixtures/sample.wav")
        
        # Act
        result = service.transcribe(audio_path, language="en")
        
        # Assert
        assert result.text
        assert len(result.segments) > 0
        assert result.language == "en"
```

**Running tests**:
```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests (slower)
pytest tests/integration/ -m integration

# Specific test file
pytest tests/unit/domain/test_youtube_url.py

# Specific test method
pytest tests/unit/domain/test_youtube_url.py::TestYouTubeURL::test_valid_url

# With coverage
pytest --cov=src --cov-report=term

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

**Test markers**:
```python
# Mark slow tests
@pytest.mark.slow
def test_large_file_processing():
    pass

# Mark integration tests
@pytest.mark.integration
def test_real_api_call():
    pass

# Skip test conditionally
@pytest.mark.skipif(not GPU_AVAILABLE, reason="Requires GPU")
def test_gpu_transcription():
    pass
```

---

## Documentation

### Code Documentation

**Required**:
- ✅ All public functions/classes have docstrings
- ✅ Complex logic has inline comments
- ✅ Type hints on all functions

**Optional but recommended**:
- Examples in docstrings
- Architecture Decision Records (ADRs) for major decisions

### User Documentation

When adding features, update:
- **User Guide**: End-user documentation (`docs/user-guide/`)
- **API Documentation**: Endpoint examples (`docs/user-guide/04-api-usage.md`)
- **Configuration**: New environment variables (`docs/user-guide/03-configuration.md`)
- **Troubleshooting**: Common issues (`docs/user-guide/05-troubleshooting.md`)

### Developer Documentation

When changing architecture:
- **Architecture Overview**: Update diagrams (`docs/developer-guide/architecture-overview.md`)
- **Testing Guide**: New test patterns (`docs/developer-guide/testing.md`)
- **Changelog**: Add entry (`docs/developer-guide/changelog.md`)

---

## Pull Request Process

### Before Creating PR

**Checklist**:
- [ ] Code follows style guide (run `make lint`)
- [ ] All tests pass (run `make test`)
- [ ] Coverage ≥ 80% for new code
- [ ] Documentation updated (if applicable)
- [ ] Commit messages follow convention
- [ ] Branch is up-to-date with `develop`

```bash
# Update your branch
git checkout develop
git pull upstream develop
git checkout feature/your-feature
git rebase develop

# Run checks
make lint
make test
make coverage
```

### Creating Pull Request

1. **Push to your fork**:
```bash
git push origin feature/your-feature
```

2. **Open PR on GitHub**:
   - Base branch: `develop` (not `main`)
   - Compare branch: `feature/your-feature`
   - Use PR template (auto-populated)

3. **Fill PR template**:

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to break)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests pass locally

## Checklist
- [ ] Code follows project style guide
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings generated

## Related Issues
Closes #123
Related to #456

## Screenshots (if applicable)
```

### PR Review Process

**What reviewers check**:
1. **Code quality**: Follows standards, readable, maintainable
2. **Architecture**: Fits Clean Architecture, SOLID principles
3. **Tests**: Adequate coverage, meaningful tests
4. **Documentation**: Clear, complete, up-to-date
5. **Performance**: No obvious bottlenecks
6. **Security**: No vulnerabilities introduced

**Responding to feedback**:
```bash
# Make requested changes
git add .
git commit -m "refactor: Address review feedback"

# Push updates
git push origin feature/your-feature
```

**PR approval**:
- Requires **2 approvals** from maintainers
- All checks must pass (lint, tests, coverage)
- No unresolved conversations

**After merge**:
```bash
# Update local develop branch
git checkout develop
git pull upstream develop

# Delete feature branch
git branch -d feature/your-feature
git push origin --delete feature/your-feature
```

---

## Issue Guidelines

### Reporting Bugs

**Use bug report template**:
```markdown
**Bug Description**
Clear description of the bug.

**Steps to Reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.11]
- YTCaption version: [e.g., 3.0.0]
- Whisper model: [e.g., base]
- Device: [e.g., CPU, CUDA GPU]

**Logs**
```
Paste relevant logs here
```

**Additional Context**
Any other relevant information.
```

### Feature Requests

**Use feature request template**:
```markdown
**Feature Description**
Clear description of the feature.

**Use Case**
Why is this feature needed? What problem does it solve?

**Proposed Solution**
How should this feature work?

**Alternatives Considered**
Other solutions you've thought about.

**Additional Context**
Mockups, examples, references.
```

### Issue Labels

- `bug`: Something isn't working
- `feature`: New feature request
- `documentation`: Documentation improvements
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention needed
- `question`: Further information requested
- `wontfix`: Will not be worked on
- `duplicate`: Already reported
- `priority:high`: High priority
- `priority:medium`: Medium priority
- `priority:low`: Low priority

---

## Release Process

### Versioning

We follow **Semantic Versioning** (SemVer): `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes (incompatible API changes)
- **MINOR**: New features (backward-compatible)
- **PATCH**: Bug fixes (backward-compatible)

**Examples**:
- `2.0.0 → 2.1.0`: Added parallel transcription (new feature)
- `2.1.0 → 2.1.1`: Fixed memory leak (bug fix)
- `2.1.1 → 3.0.0`: Changed API response format (breaking change)

### Release Workflow

**For maintainers**:

1. **Create release branch**:
```bash
git checkout develop
git pull upstream develop
git checkout -b release/v3.1.0
```

2. **Update version**:
```bash
# pyproject.toml
version = "3.1.0"

# src/__init__.py
__version__ = "3.1.0"
```

3. **Update CHANGELOG**:
```markdown
# Changelog

## [3.1.0] - 2025-10-22

### Added
- Vimeo downloader support (#123)
- Portuguese language support (#456)

### Fixed
- Memory leak in parallel transcription (#789)

### Changed
- Improved circuit breaker threshold (#234)
```

4. **Merge to main**:
```bash
git add .
git commit -m "chore: Bump version to 3.1.0"
git push origin release/v3.1.0

# Create PR: release/v3.1.0 → main
# After approval, merge and tag
git checkout main
git pull upstream main
git tag -a v3.1.0 -m "Release v3.1.0"
git push upstream v3.1.0
```

5. **Create GitHub release**:
   - Go to GitHub releases
   - Create release from tag `v3.1.0`
   - Copy changelog content
   - Publish release

6. **Merge back to develop**:
```bash
git checkout develop
git merge main
git push upstream develop
```

---

## Questions?

- 📖 **Documentation**: [docs/](../README.md)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/YourOrg/YTCaption/discussions)
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/YourOrg/YTCaption/issues)
- 📧 **Email**: maintainers@example.com

**Thank you for contributing!** 🎉

---

## Next Steps

- [Architecture Overview](./architecture-overview.md) - Understand the codebase
- [Testing Guide](./testing.md) - Learn testing patterns
- [User Guide](../user-guide/) - See how users interact with the API

---

**Version**: 3.0.0  
**Last Updated**: October 22, 2025  
**Contributors**: YTCaption Team