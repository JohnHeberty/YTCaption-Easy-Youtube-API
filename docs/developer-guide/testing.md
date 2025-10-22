# 🧪 Testing Guide

Comprehensive testing strategy and guidelines for YTCaption.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Testing Philosophy](#testing-philosophy)
3. [Test Types](#test-types)
4. [Setup](#setup)
5. [Running Tests](#running-tests)
6. [Writing Tests](#writing-tests)
7. [Test Fixtures](#test-fixtures)
8. [Mocking Strategies](#mocking-strategies)
9. [Code Coverage](#code-coverage)
10. [CI/CD Integration](#cicd-integration)
11. [Best Practices](#best-practices)

---

## Overview

YTCaption uses **pytest** as the testing framework with comprehensive coverage across all layers:

**Test distribution**:
- 🔹 **Unit tests**: 70% (fast, isolated, no external dependencies)
- 🔸 **Integration tests**: 20% (with external services: Whisper, YouTube, FFmpeg)
- 🔶 **E2E tests**: 10% (full API workflow tests)

**Current metrics**:
- Test coverage: **85%** (target: ≥80%)
- Total tests: **120+**
- Execution time: ~45 seconds (unit only), ~5 minutes (all tests)

---

## Testing Philosophy

### Test Pyramid

```
         ┌─────────┐
        ╱           ╲
       ╱     E2E     ╲       10% - Slow, high value
      ╱               ╲
     ╱─────────────────╲
    ╱                   ╲
   ╱    Integration      ╲   20% - Medium speed, test boundaries
  ╱                       ╲
 ╱─────────────────────────╲
╱                           ╲
╱         Unit Tests         ╲  70% - Fast, isolated, detailed
─────────────────────────────
```

### Principles

**1. Fast by default**:
- Unit tests run in <5 seconds
- Use mocks for external dependencies
- Parallel execution where possible

**2. Isolated**:
- Each test is independent
- No shared state between tests
- Clean setup/teardown

**3. Deterministic**:
- Same input → same output
- No flaky tests
- Use fixed seeds for randomness

**4. Meaningful**:
- Test behavior, not implementation
- Clear test names describing what's tested
- One assertion per test (when possible)

**5. Maintainable**:
- DRY principle (use fixtures)
- Clear arrange-act-assert structure
- Easy to debug when failing

---

## Test Types

### 1. Unit Tests

**Purpose**: Test individual components in isolation.

**Characteristics**:
- ✅ Fast (<100ms per test)
- ✅ No external dependencies
- ✅ Mock all I/O operations
- ✅ Test edge cases and errors

**Location**: `tests/unit/`

**Example**:
```python
# tests/unit/domain/test_youtube_url.py
import pytest
from src.domain.value_objects import YouTubeURL
from src.domain.exceptions import InvalidYouTubeURLError

class TestYouTubeURL:
    """Unit tests for YouTubeURL value object."""
    
    def test_valid_url(self):
        """Should accept valid YouTube URL."""
        url = YouTubeURL("https://youtube.com/watch?v=dQw4w9WgXcQ")
        assert url.value == "https://youtube.com/watch?v=dQw4w9WgXcQ"
    
    def test_invalid_url_raises_error(self):
        """Should reject non-YouTube URLs."""
        with pytest.raises(InvalidYouTubeURLError):
            YouTubeURL("https://vimeo.com/123")
    
    @pytest.mark.parametrize("url,expected_id", [
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ])
    def test_extract_video_id(self, url: str, expected_id: str):
        """Should extract video ID from various URL formats."""
        youtube_url = YouTubeURL(url)
        assert youtube_url.video_id() == expected_id
    
    def test_empty_url_raises_error(self):
        """Should reject empty URL."""
        with pytest.raises(InvalidYouTubeURLError):
            YouTubeURL("")
    
    def test_url_immutability(self):
        """YouTubeURL should be immutable."""
        url = YouTubeURL("https://youtube.com/watch?v=123")
        with pytest.raises(AttributeError):
            url.value = "https://youtube.com/watch?v=456"
```

---

### 2. Integration Tests

**Purpose**: Test interaction between components and external services.

**Characteristics**:
- ⚠️ Slower (1-10 seconds per test)
- ⚠️ Requires external services (Whisper, FFmpeg)
- ✅ Tests real integrations
- ✅ Marks with `@pytest.mark.integration`

**Location**: `tests/integration/`

**Example**:
```python
# tests/integration/test_whisper_transcription.py
import pytest
from pathlib import Path
from src.infrastructure.whisper import WhisperTranscriptionService

@pytest.mark.integration
@pytest.mark.slow
class TestWhisperTranscription:
    """Integration tests for Whisper transcription."""
    
    @pytest.fixture(scope="class")
    def transcription_service(self):
        """Create Whisper service (loaded once per class)."""
        return WhisperTranscriptionService(model="tiny", device="cpu")
    
    def test_transcribe_english_audio(self, transcription_service, tmp_path):
        """Should transcribe English audio correctly."""
        # Arrange
        audio_path = Path("tests/fixtures/english_sample.wav")
        
        # Act
        result = transcription_service.transcribe(audio_path, language="en")
        
        # Assert
        assert result.text
        assert len(result.segments) > 0
        assert result.language == "en"
        assert result.duration > 0
    
    def test_transcribe_with_timestamps(self, transcription_service):
        """Should include accurate timestamps in segments."""
        audio_path = Path("tests/fixtures/english_sample.wav")
        result = transcription_service.transcribe(audio_path)
        
        # Check segment timestamps are sequential
        for i in range(len(result.segments) - 1):
            assert result.segments[i].end <= result.segments[i + 1].start
    
    @pytest.mark.skipif(not GPU_AVAILABLE, reason="Requires GPU")
    def test_gpu_transcription(self):
        """Should use GPU for faster transcription."""
        service = WhisperTranscriptionService(model="base", device="cuda")
        audio_path = Path("tests/fixtures/english_sample.wav")
        
        result = service.transcribe(audio_path)
        assert result.text
```

---

### 3. End-to-End Tests

**Purpose**: Test complete workflows through the API.

**Characteristics**:
- 🐌 Slowest (10-60 seconds per test)
- 🐌 Full stack integration
- ✅ Tests user scenarios
- ✅ Marks with `@pytest.mark.e2e`

**Location**: `tests/e2e/`

**Example**:
```python
# tests/e2e/test_api_transcription.py
import pytest
from fastapi.testclient import TestClient
from src.presentation.api.main import app

@pytest.mark.e2e
class TestTranscriptionAPI:
    """End-to-end tests for transcription API."""
    
    @pytest.fixture(scope="class")
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_full_transcription_workflow(self, client):
        """Should complete full transcription workflow."""
        # Arrange
        payload = {
            "youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "language": "en",
            "task": "transcribe"
        }
        
        # Act
        response = client.post("/api/v1/transcribe", json=payload)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["video_url"] == payload["youtube_url"]
        assert data["transcription"]
        assert data["language"] == "en"
        assert len(data["segments"]) > 0
    
    def test_invalid_url_returns_400(self, client):
        """Should return 400 for invalid YouTube URL."""
        payload = {"youtube_url": "https://vimeo.com/123"}
        
        response = client.post("/api/v1/transcribe", json=payload)
        
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()
    
    def test_health_check(self, client):
        """Should return healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
```

---

## Setup

### Install Dependencies

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov pytest-mock

# Or use Makefile
make dev-install
```

### Configuration

**pytest.ini** (or `pyproject.toml`):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --cov=src --cov-report=html --cov-report=term"
markers = [
    "integration: Integration tests (with external services)",
    "e2e: End-to-end tests (full API workflow)",
    "slow: Slow tests (>5 seconds)",
    "gpu: Requires GPU",
]
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/domain/test_youtube_url.py

# Run specific test class
pytest tests/unit/domain/test_youtube_url.py::TestYouTubeURL

# Run specific test method
pytest tests/unit/domain/test_youtube_url.py::TestYouTubeURL::test_valid_url

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l

# Run last failed tests only
pytest --lf

# Run failed tests first, then others
pytest --ff
```

### By Test Type

```bash
# Unit tests only (fast)
pytest tests/unit/

# Integration tests only
pytest tests/integration/ -m integration

# E2E tests only
pytest tests/e2e/ -m e2e

# Skip slow tests
pytest -m "not slow"

# Skip integration and e2e tests
pytest -m "not integration and not e2e"
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run with 4 workers
pytest -n 4

# Auto-detect CPU count
pytest -n auto
```

### Using Makefile

```bash
# Run all tests
make test

# Run with coverage
make coverage

# Quick test (unit only)
make test-fast
```

---

## Writing Tests

### Test Structure (AAA Pattern)

**Arrange - Act - Assert**:
```python
def test_download_video():
    # Arrange: Set up test data and dependencies
    downloader = YouTubeDownloader()
    url = "https://youtube.com/watch?v=123"
    
    # Act: Execute the code being tested
    result = downloader.download(url)
    
    # Assert: Verify the outcome
    assert result.exists()
    assert result.suffix == ".mp4"
```

### Test Naming

**Convention**: `test_<what>_<condition>_<expected_result>`

**Examples**:
```python
# Good ✅
def test_download_valid_url_returns_path():
    pass

def test_download_invalid_url_raises_error():
    pass

def test_transcribe_empty_audio_raises_error():
    pass

def test_cache_hit_returns_cached_result():
    pass

# Bad ❌
def test_download():  # Too vague
    pass

def test_1():  # Meaningless
    pass

def test_transcription_service_transcribe_method_with_english_language():  # Too long
    pass
```

### Parametrized Tests

**Test multiple inputs efficiently**:
```python
@pytest.mark.parametrize("url,expected_id", [
    ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
])
def test_extract_video_id(url: str, expected_id: str):
    """Should extract video ID from various URL formats."""
    youtube_url = YouTubeURL(url)
    assert youtube_url.video_id() == expected_id

# Multiple parameters
@pytest.mark.parametrize("model,device", [
    ("tiny", "cpu"),
    ("base", "cpu"),
    ("small", "cpu"),
])
def test_load_model(model: str, device: str):
    service = WhisperTranscriptionService(model, device)
    assert service._model is not None
```

### Testing Exceptions

```python
# Test that exception is raised
def test_invalid_url_raises_error():
    with pytest.raises(InvalidYouTubeURLError):
        YouTubeURL("https://vimeo.com/123")

# Test exception message
def test_invalid_url_error_message():
    with pytest.raises(InvalidYouTubeURLError, match="Invalid YouTube URL"):
        YouTubeURL("invalid")

# Test exception attributes
def test_download_error_includes_url():
    with pytest.raises(DownloadError) as exc_info:
        downloader.download("https://youtube.com/watch?v=invalid")
    
    assert "invalid" in str(exc_info.value)
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_download():
    """Test async download method."""
    downloader = AsyncYouTubeDownloader()
    result = await downloader.download_async("https://youtube.com/watch?v=123")
    assert result.exists()
```

---

## Test Fixtures

### Basic Fixtures

**Reusable test data**:
```python
# tests/conftest.py (shared across all tests)
import pytest
from pathlib import Path
from src.domain.value_objects import YouTubeURL

@pytest.fixture
def sample_youtube_url() -> YouTubeURL:
    """Fixture with sample YouTube URL."""
    return YouTubeURL("https://youtube.com/watch?v=dQw4w9WgXcQ")

@pytest.fixture
def sample_audio_file(tmp_path) -> Path:
    """Fixture with temporary audio file."""
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake audio content")
    return audio_path

# Use in tests
def test_download(sample_youtube_url):
    downloader = YouTubeDownloader()
    result = downloader.download(sample_youtube_url)
    assert result.exists()
```

### Fixture Scopes

**Control fixture lifecycle**:
```python
# Function scope (default, new instance per test)
@pytest.fixture(scope="function")
def temp_file():
    return Path("temp.txt")

# Class scope (shared across test class)
@pytest.fixture(scope="class")
def transcription_service():
    """Load Whisper model once per test class."""
    return WhisperTranscriptionService("tiny")

# Module scope (shared across test file)
@pytest.fixture(scope="module")
def database_connection():
    conn = connect_db()
    yield conn
    conn.close()

# Session scope (shared across entire test session)
@pytest.fixture(scope="session")
def docker_services():
    """Start Docker containers once for all tests."""
    start_docker()
    yield
    stop_docker()
```

### Fixture Cleanup

**Use `yield` for teardown**:
```python
@pytest.fixture
def temp_directory(tmp_path):
    """Create and cleanup temporary directory."""
    temp_dir = tmp_path / "test_temp"
    temp_dir.mkdir()
    
    yield temp_dir  # Test runs here
    
    # Cleanup after test
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_environment_vars():
    """Temporarily set environment variables."""
    original = os.environ.copy()
    os.environ["WHISPER_MODEL"] = "tiny"
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original)
```

---

## Mocking Strategies

### Using unittest.mock

**Mock external dependencies**:
```python
from unittest.mock import Mock, patch, MagicMock

# Mock method return value
def test_download_with_mock():
    downloader = Mock(spec=IDownloader)
    downloader.download.return_value = Path("audio.wav")
    
    use_case = TranscribeVideoUseCase(downloader, ...)
    result = use_case.execute("https://youtube.com/...")
    
    downloader.download.assert_called_once()

# Mock exception
def test_download_failure():
    downloader = Mock(spec=IDownloader)
    downloader.download.side_effect = DownloadError("Network error")
    
    use_case = TranscribeVideoUseCase(downloader, ...)
    
    with pytest.raises(DownloadError):
        use_case.execute("https://youtube.com/...")

# Mock with patch decorator
@patch('src.infrastructure.youtube.downloader.yt_dlp')
def test_youtube_downloader(mock_yt_dlp):
    mock_yt_dlp.YoutubeDL.return_value.download.return_value = None
    
    downloader = YouTubeDownloader()
    result = downloader.download("https://youtube.com/...")
    
    mock_yt_dlp.YoutubeDL.assert_called_once()
```

### Mock Fixtures

```python
# tests/conftest.py
@pytest.fixture
def mock_downloader():
    """Mock downloader fixture."""
    mock = Mock(spec=IDownloader)
    mock.download.return_value = Path("audio.wav")
    return mock

@pytest.fixture
def mock_transcriber():
    """Mock transcription service fixture."""
    mock = Mock(spec=ITranscriptionService)
    mock.transcribe.return_value = TranscriptionResult(
        text="Test transcription",
        segments=[],
        language="en"
    )
    return mock

# Use in tests
def test_transcribe_use_case(mock_downloader, mock_transcriber):
    use_case = TranscribeVideoUseCase(mock_downloader, mock_transcriber, ...)
    result = use_case.execute("https://youtube.com/...")
    assert result.text == "Test transcription"
```

### Spy Pattern

**Track calls without changing behavior**:
```python
from unittest.mock import wraps

def test_cache_hit_optimization():
    # Create real service
    real_service = WhisperTranscriptionService("tiny")
    
    # Wrap method to spy on calls
    original_transcribe = real_service.transcribe
    call_count = 0
    
    def spy_transcribe(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_transcribe(*args, **kwargs)
    
    real_service.transcribe = spy_transcribe
    
    # Act
    result1 = real_service.transcribe("audio.wav")
    result2 = real_service.transcribe("audio.wav")  # Should use cache
    
    # Assert
    assert call_count == 1  # Only called once due to caching
```

---

## Code Coverage

### Measuring Coverage

```bash
# Run tests with coverage
pytest --cov=src --cov-report=term

# Generate HTML report
pytest --cov=src --cov-report=html

# Open HTML report
open htmlcov/index.html  # Mac/Linux
start htmlcov/index.html  # Windows

# Coverage summary
pytest --cov=src --cov-report=term-missing
```

### Coverage Targets

**Minimum thresholds**:
- Overall: **≥80%**
- Domain layer: **≥90%** (pure business logic)
- Application layer: **≥85%** (use cases)
- Infrastructure layer: **≥70%** (external integrations)
- Presentation layer: **≥75%** (API routes)

### Coverage Configuration

```toml
# pyproject.toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/__init__.py",
    "*/conftest.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

### Improving Coverage

**Identify uncovered lines**:
```bash
pytest --cov=src --cov-report=term-missing
```

**Add tests for uncovered code**:
```python
# Before (uncovered)
def download(self, url: str) -> Path:
    if not url:
        raise ValueError("URL required")  # Not tested
    return self._download_internal(url)

# After (covered)
def test_download_empty_url_raises_error():
    downloader = YouTubeDownloader()
    with pytest.raises(ValueError, match="URL required"):
        downloader.download("")
```

---

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install FFmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio
      
      - name: Lint with flake8
        run: |
          pip install flake8
          flake8 src/ tests/ --count --show-source --statistics
      
      - name: Run tests with coverage
        run: |
          pytest --cov=src --cov-report=xml --cov-report=term
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true
      
      - name: Check coverage threshold
        run: |
          coverage report --fail-under=80
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
        language_version: python3.11
  
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
  
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/unit/
        language: system
        pass_filenames: false
        always_run: true
```

---

## Best Practices

### ✅ DO

1. **Test behavior, not implementation**
```python
# Good ✅
def test_transcribe_returns_text():
    result = service.transcribe("audio.wav")
    assert result.text  # Tests behavior

# Bad ❌
def test_transcribe_calls_whisper_load_model():
    service.transcribe("audio.wav")
    assert service._model is not None  # Tests implementation
```

2. **Use descriptive test names**
```python
# Good ✅
def test_download_unavailable_video_raises_video_not_found_error():
    pass

# Bad ❌
def test_download_error():
    pass
```

3. **One assertion per test (when possible)**
```python
# Good ✅
def test_result_has_text():
    assert result.text

def test_result_has_segments():
    assert len(result.segments) > 0

# Bad ❌ (too many concerns)
def test_result():
    assert result.text
    assert len(result.segments) > 0
    assert result.language == "en"
    assert result.duration > 0
```

4. **Use fixtures for common setup**
5. **Mock external dependencies**
6. **Test edge cases and errors**

### ❌ DON'T

1. **Don't test external libraries**
```python
# Bad ❌
def test_whisper_library():
    # Don't test OpenAI's Whisper implementation
    pass

# Good ✅
def test_our_transcription_service_integration():
    # Test OUR wrapper around Whisper
    pass
```

2. **Don't write flaky tests**
```python
# Bad ❌
def test_transcription_time():
    start = time.time()
    service.transcribe("audio.wav")
    assert time.time() - start < 1.0  # Flaky, depends on system load
```

3. **Don't share state between tests**
```python
# Bad ❌
class TestTranscription:
    result = None  # Shared state
    
    def test_transcribe(self):
        self.result = service.transcribe("audio.wav")
    
    def test_result_has_text(self):
        assert self.result.text  # Depends on previous test
```

4. **Don't ignore warnings**
5. **Don't skip tests without good reason**

---

## Troubleshooting Tests

### Common Issues

**1. Import errors**:
```bash
# Solution: Install package in editable mode
pip install -e .
```

**2. Fixture not found**:
```bash
# Solution: Check conftest.py location
tests/
├── conftest.py        # Shared fixtures
├── unit/
│   └── conftest.py    # Unit-specific fixtures
```

**3. Tests pass individually but fail together**:
```bash
# Cause: Shared state or side effects
# Solution: Ensure proper cleanup in fixtures
```

**4. Slow tests**:
```bash
# Solution: Use markers and run fast tests only
pytest -m "not slow"
```

---

## Next Steps

- [Architecture Overview](./architecture-overview.md) - Understand the codebase
- [Contributing Guide](./contributing.md) - Learn contribution workflow
- [User Guide](../user-guide/) - See how users interact with the API

---

**Version**: 3.0.0  
**Last Updated**: October 22, 2025  
**Contributors**: YTCaption Team