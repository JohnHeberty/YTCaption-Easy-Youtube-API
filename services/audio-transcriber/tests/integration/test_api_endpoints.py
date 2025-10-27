"""
Testes de Integração - API Endpoints
Princípio SOLID: Testa integração entre componentes (API + Store + Processor)
"""
import pytest
import os
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Cliente de teste FastAPI"""
    return TestClient(app)


@pytest.fixture
def sample_audio_file():
    """Arquivo de áudio de exemplo para testes"""
    # Cria arquivo fake para teste
    test_file = "test_audio.mp3"
    with open(test_file, "wb") as f:
        f.write(b"fake audio content")
    yield test_file
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


class TestHealthEndpoint:
    """Testa endpoint de health check"""
    
    def test_health_check_returns_200(self, client):
        """Health check deve retornar 200"""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_health_check_returns_json(self, client):
        """Health check deve retornar JSON"""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"
    
    def test_health_check_has_status(self, client):
        """Health check deve ter status 'healthy'"""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"


class TestLanguagesEndpoint:
    """Testa endpoint de linguagens suportadas"""
    
    def test_languages_endpoint_returns_200(self, client):
        """Endpoint deve retornar 200"""
        response = client.get("/languages")
        assert response.status_code == 200
    
    def test_languages_returns_list(self, client):
        """Deve retornar lista de linguagens"""
        response = client.get("/languages")
        data = response.json()
        
        assert "supported_languages" in data
        assert isinstance(data["supported_languages"], list)
        assert len(data["supported_languages"]) > 0
    
    def test_languages_contains_auto(self, client):
        """Lista deve conter 'auto'"""
        response = client.get("/languages")
        data = response.json()
        
        assert "auto" in data["supported_languages"]
    
    def test_languages_has_total_count(self, client):
        """Deve retornar total de linguagens"""
        response = client.get("/languages")
        data = response.json()
        
        assert "total_languages" in data
        assert data["total_languages"] > 0
        assert data["total_languages"] == len(data["supported_languages"])
    
    def test_languages_has_models_list(self, client):
        """Deve retornar lista de modelos disponíveis"""
        response = client.get("/languages")
        data = response.json()
        
        assert "models" in data
        assert isinstance(data["models"], list)
        assert "base" in data["models"]


class TestJobCreationEndpoint:
    """Testa criação de jobs"""
    
    def test_create_job_returns_immediately(self, client, sample_audio_file):
        """Job deve retornar imediatamente (<2s)"""
        import time
        
        with open(sample_audio_file, "rb") as f:
            start = time.time()
            response = client.post(
                "/jobs",
                files={"file": ("audio.mp3", f, "audio/mpeg")},
                data={"language": "en"}
            )
            elapsed = time.time() - start
        
        assert response.status_code in [200, 201]
        assert elapsed < 2.0, f"Resposta demorou {elapsed}s (deve ser <2s)"
    
    def test_create_job_returns_job_object(self, client, sample_audio_file):
        """Deve retornar objeto Job completo"""
        with open(sample_audio_file, "rb") as f:
            response = client.post(
                "/jobs",
                files={"file": ("audio.mp3", f, "audio/mpeg")},
                data={"language": "en"}
            )
        
        assert response.status_code in [200, 201]
        data = response.json()
        
        assert "id" in data
        assert "status" in data
        assert "language" in data
        assert data["language"] == "en"
    
    def test_create_job_with_auto_language(self, client, sample_audio_file):
        """Deve aceitar language='auto'"""
        with open(sample_audio_file, "rb") as f:
            response = client.post(
                "/jobs",
                files={"file": ("audio.mp3", f, "audio/mpeg")},
                data={"language": "auto"}
            )
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["language"] == "auto"
    
    def test_create_job_with_invalid_language(self, client, sample_audio_file):
        """Deve rejeitar linguagem inválida"""
        with open(sample_audio_file, "rb") as f:
            response = client.post(
                "/jobs",
                files={"file": ("audio.mp3", f, "audio/mpeg")},
                data={"language": "xyz"}
            )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
    
    def test_create_job_without_file(self, client):
        """Deve retornar erro se não enviar arquivo"""
        response = client.post(
            "/jobs",
            data={"language": "en"}
        )
        
        assert response.status_code == 422  # Unprocessable Entity
    
    def test_create_job_initial_status_is_queued(self, client, sample_audio_file):
        """Status inicial deve ser QUEUED"""
        with open(sample_audio_file, "rb") as f:
            response = client.post(
                "/jobs",
                files={"file": ("audio.mp3", f, "audio/mpeg")},
                data={"language": "en"}
            )
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["status"] in ["queued", "processing"]  # Pode já estar processing


class TestJobStatusEndpoint:
    """Testa consulta de status de jobs"""
    
    def test_get_nonexistent_job_returns_404(self, client):
        """Job inexistente deve retornar 404"""
        response = client.get("/jobs/nonexistent-job-id")
        assert response.status_code == 404
    
    def test_get_job_status(self, client, sample_audio_file):
        """Deve retornar status de job existente"""
        # Cria job
        with open(sample_audio_file, "rb") as f:
            create_response = client.post(
                "/jobs",
                files={"file": ("audio.mp3", f, "audio/mpeg")},
                data={"language": "en"}
            )
        
        job_id = create_response.json()["id"]
        
        # Consulta status
        status_response = client.get(f"/jobs/{job_id}")
        assert status_response.status_code == 200
        
        data = status_response.json()
        assert data["id"] == job_id
        assert "status" in data
        assert "progress" in data


class TestAdminEndpoints:
    """Testa endpoints administrativos"""
    
    def test_admin_stats_returns_200(self, client):
        """Stats deve retornar 200"""
        response = client.get("/admin/stats")
        assert response.status_code == 200
    
    def test_admin_stats_has_metrics(self, client):
        """Stats deve ter métricas"""
        response = client.get("/admin/stats")
        data = response.json()
        
        assert "total_jobs" in data or "cache" in data
    
    def test_admin_cleanup_returns_immediately(self, client):
        """Cleanup deve retornar imediatamente"""
        import time
        
        start = time.time()
        response = client.post("/admin/cleanup")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 2.0, f"Cleanup demorou {elapsed}s (deve ser <2s)"
    
    def test_admin_cleanup_returns_message(self, client):
        """Cleanup deve retornar mensagem de confirmação"""
        response = client.post("/admin/cleanup")
        data = response.json()
        
        assert "message" in data or "status" in data


class TestAPIResilience:
    """Testa resiliência da API"""
    
    def test_concurrent_job_creation(self, client, sample_audio_file):
        """Deve suportar criação concorrente de jobs"""
        import concurrent.futures
        
        def create_job():
            with open(sample_audio_file, "rb") as f:
                return client.post(
                    "/jobs",
                    files={"file": ("audio.mp3", f, "audio/mpeg")},
                    data={"language": "en"}
                )
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_job) for _ in range(3)]
            responses = [f.result() for f in futures]
        
        # Todos devem ter sucesso
        for response in responses:
            assert response.status_code in [200, 201]
        
        # Jobs devem ter IDs únicos
        job_ids = [r.json()["id"] for r in responses]
        assert len(set(job_ids)) == len(job_ids), "IDs duplicados encontrados"
    
    def test_api_handles_large_language_list(self, client):
        """API deve lidar com lista grande de linguagens"""
        response = client.get("/languages")
        data = response.json()
        
        # Deve retornar mesmo com muitas linguagens
        assert len(data["supported_languages"]) >= 50
        assert response.status_code == 200
