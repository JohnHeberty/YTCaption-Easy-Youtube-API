"""
Testes de Integração - API Endpoints
Princípio SOLID: Testa integração entre componentes (API + Store + Processor)
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def sample_audio_file(tmp_path):
    """Arquivo de áudio de exemplo para testes"""
    test_file = tmp_path / "test_audio.mp3"
    test_file.write_bytes(b"fake audio content")
    return str(test_file)


@pytest.fixture(autouse=True)
def mock_disk_space():
    """Mock disk space check to always return healthy."""
    with patch("app.api.health_routes.check_disk_space") as mock:
        mock.return_value = {"status": "ok", "free_gb": 100.0, "total_gb": 200.0, "percent_free": 50.0}
        yield mock


@pytest.fixture(autouse=True)
def mock_job_store_dep(mock_job_store):
    """Mock the _get_job_store_dep function used in jobs_routes."""
    with patch("app.api.jobs_routes._get_job_store_dep", return_value=mock_job_store):
        yield


@pytest.fixture
def api_headers():
    """Headers with API key for authenticated requests."""
    return {"X-API-Key": "se4-test-key-2026"}


@pytest.fixture
def auth_client(client, api_headers):
    """Test client with API key authentication."""
    client.headers.update(api_headers)
    return client


class TestHealthEndpoint:
    """Testa endpoint de health check"""
    
    def test_health_check_returns_200(self, auth_client):
        """Health check deve retornar 200"""
        response = auth_client.get("/health")
        assert response.status_code == 200
    
    def test_health_check_returns_json(self, auth_client):
        """Health check deve retornar JSON"""
        response = auth_client.get("/health")
        assert response.headers["content-type"] == "application/json"
    
    def test_health_check_has_status(self, auth_client):
        """Health check deve ter status 'healthy'"""
        response = auth_client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"


class TestLanguagesEndpoint:
    """Testa endpoint de linguagens suportadas"""
    
    def test_languages_endpoint_returns_200(self, auth_client):
        """Endpoint deve retornar 200"""
        response = auth_client.get("/languages")
        assert response.status_code == 200
    
    def test_languages_returns_list(self, auth_client):
        """Deve retornar lista de linguagens"""
        response = auth_client.get("/languages")
        data = response.json()
        
        assert "transcription" in data
        assert "supported_languages" in data["transcription"]
        assert isinstance(data["transcription"]["supported_languages"], list)
        assert len(data["transcription"]["supported_languages"]) > 0
    
    def test_languages_contains_auto(self, auth_client):
        """Lista deve conter 'auto'"""
        response = auth_client.get("/languages")
        data = response.json()
        
        assert "auto" in data["transcription"]["supported_languages"]
    
    def test_languages_has_total_count(self, auth_client):
        """Deve retornar total de linguagens"""
        response = auth_client.get("/languages")
        data = response.json()
        
        assert "total_languages" in data["transcription"]
        assert data["transcription"]["total_languages"] > 0
        assert data["transcription"]["total_languages"] == len(data["transcription"]["supported_languages"])
    
    def test_languages_has_models_list(self, auth_client):
        """Deve retornar lista de modelos disponíveis"""
        response = auth_client.get("/languages")
        data = response.json()
        
        assert "models" in data
        assert isinstance(data["models"], list)
        assert "base" in data["models"]


class TestJobCreationEndpoint:
    """Testa criação de jobs"""
    
    def test_create_job_returns_immediately(self, auth_client, sample_audio_file):
        """Criação de job deve retornar imediatamente"""
        with open(sample_audio_file, "rb") as f:
            response = auth_client.post(
                "/jobs",
                files={"file": ("test.mp3", f, "audio/mpeg")},
                data={"language_in": "pt"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
    
    def test_create_job_returns_job_object(self, auth_client, sample_audio_file):
        """Deve retornar objeto job completo"""
        with open(sample_audio_file, "rb") as f:
            response = auth_client.post(
                "/jobs",
                files={"file": ("test.mp3", f, "audio/mpeg")},
                data={"language_in": "pt"}
            )
        
        data = response.json()
        assert "id" in data
        assert "status" in data
        assert "created_at" in data
    
    def test_create_job_with_auto_language(self, auth_client, sample_audio_file):
        """Deve aceitar language=auto"""
        with open(sample_audio_file, "rb") as f:
            response = auth_client.post(
                "/jobs",
                files={"file": ("test.mp3", f, "audio/mpeg")},
                data={"language_in": "auto"}
            )
        
        assert response.status_code == 200
    
    def test_create_job_with_invalid_language(self, auth_client, sample_audio_file):
        """Deve rejeitar linguagem inválida"""
        with open(sample_audio_file, "rb") as f:
            response = auth_client.post(
                "/jobs",
                files={"file": ("test.mp3", f, "audio/mpeg")},
                data={"language_in": "invalid"}
            )
        
        assert response.status_code == 400
    
    def test_create_job_without_file(self, auth_client):
        """Deve rejeitar requisição sem arquivo"""
        response = auth_client.post(
            "/jobs",
            data={"language_in": "pt"}
        )
        
        assert response.status_code == 422
    
    def test_create_job_initial_status_is_queued(self, auth_client, sample_audio_file):
        """Job deve ter status inicial 'queued'"""
        with open(sample_audio_file, "rb") as f:
            response = auth_client.post(
                "/jobs",
                files={"file": ("test.mp3", f, "audio/mpeg")},
                data={"language_in": "pt"}
            )
        
        data = response.json()
        assert data["status"] == "queued"


class TestJobStatusEndpoint:
    """Testa consulta de status de jobs"""
    
    def test_get_nonexistent_job_returns_404(self, auth_client):
        """Job inexistente deve retornar 404"""
        response = auth_client.get("/jobs/nonexistent-job-id")
        assert response.status_code == 404
    
    def test_get_job_status(self, auth_client, sample_audio_file):
        """Deve retornar status do job"""
        # Criar job
        with open(sample_audio_file, "rb") as f:
            create_response = auth_client.post(
                "/jobs",
                files={"file": ("test.mp3", f, "audio/mpeg")},
                data={"language_in": "pt"}
            )
        
        job_id = create_response.json()["id"]
        
        # Consultar status
        response = auth_client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == job_id
        assert "status" in data


class TestAdminEndpoints:
    """Testa endpoints administrativos"""
    
    def test_admin_stats_returns_200(self, auth_client):
        """Admin stats deve retornar 200"""
        response = auth_client.get("/admin/stats")
        assert response.status_code == 200
    
    def test_admin_stats_has_metrics(self, auth_client):
        """Deve conter métricas"""
        response = auth_client.get("/admin/stats")
        data = response.json()
        
        assert "total_jobs" in data
        assert "by_status" in data
    
    def test_admin_cleanup_returns_immediately(self, auth_client):
        """Cleanup deve retornar imediatamente"""
        response = auth_client.post("/admin/cleanup")
        assert response.status_code == 200


class TestAPIResilience:
    """Testa resiliência da API"""
    
    def test_concurrent_job_creation(self, auth_client, sample_audio_file):
        """Deve lidar com criação concorrente de jobs"""
        import concurrent.futures
        
        def create_job():
            with open(sample_audio_file, "rb") as f:
                return auth_client.post(
                    "/jobs",
                    files={"file": ("test.mp3", f, "audio/mpeg")},
                    data={"language_in": "pt"}
                )
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_job) for _ in range(3)]
            results = [f.result() for f in futures]
        
        # Todas devem ter sucesso
        for response in results:
            assert response.status_code == 200
    
    def test_api_handles_large_language_list(self, auth_client):
        """Deve lidar com lista grande de linguagens"""
        response = auth_client.get("/languages")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["transcription"]["supported_languages"]) > 0
