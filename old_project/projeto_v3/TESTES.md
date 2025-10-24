# TESTES

## 1. Estratégia de Testes

### Pirâmide de Testes

```
         ╱╲
        ╱  ╲          E2E Tests (10%)
       ╱────╲
      ╱      ╲        Integration (30%)
     ╱────────╲
    ╱          ╲      Unit Tests (60%)
   ╱────────────╲
```

### Target Coverage

```
Unit:        80%+ (business logic)
Integration: 60%+ (service boundaries)
E2E:         Critical paths only
Overall:     70%+ code coverage
```

---

## 2. Unit Tests

### Structure

```
services/
├── api-gateway/
│   ├── app/
│   │   ├── controllers/
│   │   ├── services/
│   │   └── models/
│   └── tests/
│       ├── test_controllers.py
│       ├── test_services.py
│       └── test_models.py
```

### Example: Job Manager Service

```python
# services/job-manager/app/services/job_service.py
class JobService:
    def __init__(self, db_repository):
        self.db = db_repository
    
    async def create_job(self, user_id, url, idempotency_key):
        # Check idempotency
        if existing := await self.db.find_by_idempotency_key(idempotency_key):
            return existing
        
        # Create job
        job = Job(
            id=str(uuid.uuid4()),
            user_id=user_id,
            url=url,
            status="new",
            idempotency_key=idempotency_key,
            created_at=datetime.now()
        )
        
        await self.db.save(job)
        return job

# services/job-manager/tests/test_job_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def db_mock():
    return AsyncMock()

@pytest.fixture
def job_service(db_mock):
    return JobService(db_mock)

@pytest.mark.asyncio
async def test_create_job_success(job_service, db_mock):
    """Should create a new job"""
    db_mock.find_by_idempotency_key.return_value = None
    db_mock.save.return_value = None
    
    job = await job_service.create_job(
        user_id="user-123",
        url="https://youtube.com/watch?v=abc",
        idempotency_key="key-123"
    )
    
    assert job.id is not None
    assert job.status == "new"
    assert job.url == "https://youtube.com/watch?v=abc"
    db_mock.save.assert_called_once()

@pytest.mark.asyncio
async def test_create_job_idempotency(job_service, db_mock):
    """Should return existing job if idempotency_key matches"""
    existing_job = Job(
        id="job-123",
        user_id="user-123",
        url="https://youtube.com/watch?v=abc",
        status="new"
    )
    db_mock.find_by_idempotency_key.return_value = existing_job
    
    job = await job_service.create_job(
        user_id="user-123",
        url="https://youtube.com/watch?v=abc",
        idempotency_key="key-123"
    )
    
    assert job.id == "job-123"
    db_mock.save.assert_not_called()

@pytest.mark.asyncio
async def test_create_job_validation_error(job_service, db_mock):
    """Should raise error for invalid URL"""
    with pytest.raises(ValueError, match="Invalid URL"):
        await job_service.create_job(
            user_id="user-123",
            url="invalid-url",
            idempotency_key="key-123"
        )
```

### Run Unit Tests

```bash
pytest services/job-manager/tests/ -v --cov=services/job-manager/app
```

---

## 3. Integration Tests

### Database Integration

```python
# services/job-manager/tests/test_job_repository.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine

@pytest.fixture
async def db_session():
    """Create test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = AsyncSession(async_engine)
    yield async_session
    await async_session.close()

@pytest.mark.asyncio
async def test_save_and_retrieve_job(db_session):
    """Should persist and retrieve job from database"""
    repo = JobRepository(db_session)
    
    job = Job(
        id="job-123",
        user_id="user-123",
        url="https://youtube.com/watch?v=abc",
        status="queued"
    )
    
    await repo.save(job)
    retrieved = await repo.find_by_id("job-123")
    
    assert retrieved.id == job.id
    assert retrieved.status == "queued"
```

### Message Queue Integration

```python
# services/job-manager/tests/test_rabbitmq_integration.py
@pytest.fixture
def rabbitmq_mock():
    return AsyncMock()

@pytest.mark.asyncio
async def test_publish_job_created_event(rabbitmq_mock):
    """Should publish job.created event"""
    publisher = RabbitMQPublisher(rabbitmq_mock)
    
    job = Job(id="job-123", user_id="user-123")
    await publisher.publish_job_created(job)
    
    rabbitmq_mock.publish.assert_called_once()
    call_args = rabbitmq_mock.publish.call_args
    assert call_args[1]["queue"] == "jobs.created"
    assert "job-123" in str(call_args[1]["message"])
```

### External API Integration (Mock)

```python
# services/downloader/tests/test_youtube_client.py
@pytest.fixture
def youtube_client_mock():
    return AsyncMock()

@pytest.mark.asyncio
async def test_download_video_success(youtube_client_mock):
    """Should handle successful YouTube download"""
    youtube_client_mock.get_metadata.return_value = {
        "title": "Video Title",
        "duration": 3600,
        "format_id": "18"
    }
    youtube_client_mock.download.return_value = b"video_data"
    
    downloader = Downloader(youtube_client_mock)
    result = await downloader.download("https://youtube.com/watch?v=abc")
    
    assert result["title"] == "Video Title"
    assert result["duration"] == 3600
    youtube_client_mock.get_metadata.assert_called_once()
```

### Run Integration Tests

```bash
pytest services/*/tests/ -v -m integration --cov=services/*/app
```

---

## 4. Contract Tests

### Producer (Job Manager) Contract

```python
# services/job-manager/tests/test_job_created_event.py
"""
Contract: job-manager publishes jobs.created event

Event schema:
{
  "job_id": "string",
  "user_id": "string",
  "url": "string",
  "created_at": "ISO8601"
}
"""

import json

def test_job_created_event_schema():
    """Event must conform to schema"""
    event = {
        "job_id": "job-123",
        "user_id": "user-123",
        "url": "https://youtube.com/watch?v=abc",
        "created_at": "2025-10-23T10:30:45Z"
    }
    
    # Validate schema
    schema = {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "user_id": {"type": "string"},
            "url": {"type": "string"},
            "created_at": {"type": "string", "format": "date-time"}
        },
        "required": ["job_id", "user_id", "url", "created_at"]
    }
    
    jsonschema.validate(event, schema)
    assert True
```

### Consumer (Downloader) Contract

```python
# services/downloader/tests/test_job_created_consumer.py
"""
Contract: downloader consumes jobs.created event

Expected behavior:
- Receive job.created event
- Download video from URL
- Publish jobs.download_completed
"""

@pytest.mark.asyncio
async def test_consume_job_created_event():
    """Should process job.created event correctly"""
    
    # Simulate received event
    event = {
        "job_id": "job-123",
        "user_id": "user-123",
        "url": "https://youtube.com/watch?v=abc",
        "created_at": "2025-10-23T10:30:45Z"
    }
    
    consumer = JobCreatedConsumer()
    result = await consumer.process(event)
    
    # Should return valid response
    assert result["job_id"] == "job-123"
    assert result["status"] in ["completed", "failed"]
```

---

## 5. E2E Tests

### Scenario 1: Create Job and Get Results

```python
# tests/e2e/test_create_job_flow.py
import pytest
import httpx

BASE_URL = "http://localhost:8000"

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_job_and_get_results():
    """
    1. Create job
    2. Poll status until completed
    3. Get results
    """
    async with httpx.AsyncClient() as client:
        # 1. Create job
        response = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={
                "url": "https://youtube.com/watch?v=test",
                "language": "pt-BR"
            },
            headers={"Authorization": f"Bearer {JWT_TOKEN}"}
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        # 2. Poll status
        max_retries = 120  # 2 minutes
        for _ in range(max_retries):
            response = await client.get(
                f"{BASE_URL}/api/v1/jobs/{job_id}",
                headers={"Authorization": f"Bearer {JWT_TOKEN}"}
            )
            status = response.json()["status"]
            
            if status == "completed":
                break
            elif status == "failed":
                pytest.fail(f"Job failed: {response.json()}")
            
            await asyncio.sleep(1)
        else:
            pytest.fail("Job timeout after 2 minutes")
        
        # 3. Get results
        response = await client.get(
            f"{BASE_URL}/api/v1/jobs/{job_id}/results",
            headers={"Authorization": f"Bearer {JWT_TOKEN}"}
        )
        assert response.status_code == 200
        results = response.json()
        
        assert "transcript" in results
        assert len(results["transcript"]) > 0
```

### Scenario 2: Error Handling

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_invalid_url_handling():
    """Should reject invalid URLs"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/jobs",
            json={"url": "invalid-url"},
            headers={"Authorization": f"Bearer {JWT_TOKEN}"}
        )
        assert response.status_code == 400
        assert "Invalid URL" in response.json()["error"]

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_rate_limiting():
    """Should enforce rate limits"""
    async with httpx.AsyncClient() as client:
        for i in range(101):  # Exceeds per-user limit of 100/min
            response = await client.post(
                f"{BASE_URL}/api/v1/jobs",
                json={
                    "url": f"https://youtube.com/watch?v={i}",
                    "idempotency_key": f"key-{i}"
                },
                headers={"Authorization": f"Bearer {JWT_TOKEN}"}
            )
            
            if i == 100:
                assert response.status_code == 429
                assert "retry_after" in response.headers
```

### Scenario 3: Resilience Patterns

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_circuit_breaker_resilience():
    """
    Circuit breaker should fail-fast after repeated failures
    """
    
    # Simulate external service down
    with patch("app.services.youtube_client") as mock_yt:
        mock_yt.get_metadata.side_effect = TimeoutError("Service down")
        
        # First few requests should timeout
        for i in range(5):
            with pytest.raises(TimeoutError):
                await downloader.download(f"https://youtube.com/watch?v={i}")
        
        # After fail_max=5, circuit should be open
        with pytest.raises(CircuitBreakerOpen):
            await downloader.download("https://youtube.com/watch?v=6")
```

### Run E2E Tests

```bash
# Requires services running locally
docker-compose up -d
pytest tests/e2e/ -v -m e2e --timeout=300
```

---

## 6. Performance Tests

### Load Test (Locust)

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def create_job(self):
        self.client.post(
            "/api/v1/jobs",
            json={
                "url": "https://youtube.com/watch?v=test",
                "idempotency_key": f"key-{uuid.uuid4()}"
            },
            headers={"Authorization": f"Bearer {JWT_TOKEN}"}
        )
    
    @task(1)
    def get_status(self):
        job_id = "job-123"  # Get from previously created
        self.client.get(
            f"/api/v1/jobs/{job_id}",
            headers={"Authorization": f"Bearer {JWT_TOKEN}"}
        )

# Run
# locust -f tests/load/locustfile.py --host=http://localhost:8000
```

### Stress Test Metrics

```
Target:
├─ Throughput: 1000 req/s
├─ P95 latency: < 500ms
├─ Error rate: < 0.1%
└─ Connection pool: No exhaustion

Expected results:
├─ At 500 req/s: P95=100ms, errors=0%
├─ At 1000 req/s: P95=250ms, errors=0%
└─ At 2000 req/s: P95=800ms, errors<0.5%
```

---

## 7. Test Automation

### CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest services/*/tests/ -v --cov --cov-report=xml
      - uses: codecov/codecov-action@v3

  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
      rabbitmq:
        image: rabbitmq:3.12
    steps:
      - uses: actions/checkout@v3
      - run: pytest services/*/tests/ -v -m integration

  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: docker-compose up -d
      - run: pytest tests/e2e/ -v -m e2e --timeout=300
      - run: docker-compose logs --tail=100
        if: failure()
```

---

## 8. Testing Checklist

### Before Each Service Deployment

```
□ Unit tests: 80%+ coverage
□ Integration tests: All service boundaries
□ Contract tests: Event schema validation
□ E2E tests: Critical paths pass
□ Load tests: P95 latency acceptable
□ Security tests: No SQL injection, XSS
□ Regression tests: Previous bugs don't return
```

### Test Execution Order

```
1. Unit (1-2 min)
2. Integration (5-10 min)
3. Contract (2-3 min)
4. E2E (10-15 min, requires services running)
5. Load (optional, manual, 30 min)
```

---

**Próximo**: Leia `README.md` (já deve estar criado)
