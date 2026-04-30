import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def orchestrator_client():
    from unittest.mock import patch

    mock_store = MagicMock()
    mock_store.ping.return_value = True
    mock_store.save_job = MagicMock()
    mock_store.get_job = MagicMock(return_value=None)
    mock_store.list_jobs = MagicMock(return_value=[])

    mock_orchestrator = MagicMock()
    mock_orchestrator.check_services_health = AsyncMock(return_value={
        "video-downloader": "healthy",
        "audio-normalization": "healthy",
        "audio-transcriber": "healthy",
    })

    with patch("infrastructure.dependency_injection.get_store", return_value=mock_store), \
         patch("infrastructure.dependency_injection.get_pipeline_orchestrator", return_value=mock_orchestrator), \
         patch("infrastructure.dependency_injection.get_health_checker", return_value=MagicMock()), \
         patch("main.get_store", return_value=mock_store), \
         patch("main.redis_store", mock_store), \
         patch("main.orchestrator", mock_orchestrator), \
         patch("api.health_routes.get_store", return_value=mock_store), \
         patch("api.health_routes._get_redis_store", return_value=mock_store), \
         patch("api.health_routes._get_orchestrator", return_value=mock_orchestrator), \
         patch("infrastructure.dependency_injection.set_app_start_time"):
        from datetime import datetime
        from infrastructure.dependency_injection import set_app_start_time
        set_app_start_time(datetime.now())

        from main import app
        from fastapi.testclient import TestClient
        yield TestClient(app)


@pytest.mark.unit
class TestHealthRoutes:
    def test_health_endpoint(self, orchestrator_client):
        response = orchestrator_client.get("/health")
        assert response.status_code in [200, 503]