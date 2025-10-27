"""
Testes de integração para os endpoints da API de normalização de áudio
"""
import pytest
from fastapi.testclient import TestClient
import time
from pathlib import Path


class TestHealthEndpoint:
    """Testes para o endpoint de health check"""
    
    def test_health_check_returns_200(self, client):
        """Health check deve retornar 200"""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_health_check_response_structure(self, client):
        """Health check deve retornar estrutura esperada"""
        response = client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert "service" in data
        assert data["service"] == "audio-normalization"


class TestJobCreationEndpoint:
    """Testes para criação de jobs de normalização"""
    
    def test_create_job_returns_immediately(self, client, sample_audio_file):
        """Job deve retornar em menos de 2 segundos"""
        start_time = time.time()
        
        response = client.post(
            "/jobs",
            data={
                "input_file": str(sample_audio_file),
                "remove_noise": "true",
                "convert_to_mono": "true",
                "sample_rate_16k": "true"
            }
        )
        
        elapsed = time.time() - start_time
        
        assert response.status_code in [200, 201]
        assert elapsed < 2.0, f"Response took {elapsed:.2f}s, expected < 2s"
    
    def test_create_job_returns_job_id(self, client, sample_audio_file):
        """Job deve retornar job_id"""
        response = client.post(
            "/jobs",
            data={
                "input_file": str(sample_audio_file),
                "remove_noise": "true"
            }
        )
        
        assert response.status_code in [200, 201]
        data = response.json()
        
        assert "job_id" in data
        assert len(data["job_id"]) > 0
    
    def test_create_job_with_default_parameters(self, client, sample_audio_file):
        """Job deve aceitar parâmetros padrão"""
        response = client.post(
            "/jobs",
            data={"input_file": str(sample_audio_file)}
        )
        
        assert response.status_code in [200, 201]
    
    def test_create_job_with_all_parameters(self, client, sample_audio_file):
        """Job deve aceitar todos os parâmetros"""
        response = client.post(
            "/jobs",
            data={
                "input_file": str(sample_audio_file),
                "remove_noise": "true",
                "convert_to_mono": "true",
                "sample_rate_16k": "true"
            }
        )
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert "job_id" in data
    
    def test_create_job_without_input_file(self, client):
        """Job sem input_file deve retornar 422"""
        response = client.post(
            "/jobs",
            data={"remove_noise": "true"}
        )
        
        assert response.status_code == 422


class TestJobStatusEndpoint:
    """Testes para consulta de status de jobs"""
    
    def test_get_job_status_existing_job(self, client, sample_audio_file):
        """Deve retornar status de job existente"""
        # Cria job
        create_response = client.post(
            "/jobs",
            data={"input_file": str(sample_audio_file)}
        )
        job_id = create_response.json()["job_id"]
        
        # Consulta status
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "job_id" in data
        assert "status" in data
        assert data["job_id"] == job_id
    
    def test_get_job_status_nonexistent_job(self, client):
        """Deve retornar 404 para job inexistente"""
        response = client.get("/jobs/nonexistent123")
        assert response.status_code == 404
    
    def test_job_status_includes_progress(self, client, sample_audio_file):
        """Status deve incluir progresso"""
        # Cria job
        create_response = client.post(
            "/jobs",
            data={"input_file": str(sample_audio_file)}
        )
        job_id = create_response.json()["job_id"]
        
        # Consulta status
        response = client.get(f"/jobs/{job_id}")
        data = response.json()
        
        assert "progress" in data
        assert isinstance(data["progress"], (int, float))
        assert 0 <= data["progress"] <= 100


class TestAdminEndpoints:
    """Testes para endpoints administrativos"""
    
    def test_stats_endpoint(self, client):
        """Endpoint de estatísticas deve retornar 200"""
        response = client.get("/admin/stats")
        assert response.status_code == 200
    
    def test_stats_response_structure(self, client):
        """Estatísticas devem ter estrutura esperada"""
        response = client.get("/admin/stats")
        data = response.json()
        
        # Pode ter diferentes estruturas dependendo da implementação
        assert isinstance(data, dict)
    
    def test_cleanup_endpoint_returns_immediately(self, client):
        """Cleanup deve retornar imediatamente"""
        start_time = time.time()
        
        response = client.post("/admin/cleanup")
        
        elapsed = time.time() - start_time
        
        # Cleanup deve ser resiliente (background)
        assert response.status_code in [200, 202]
        assert elapsed < 2.0, f"Cleanup took {elapsed:.2f}s, expected < 2s"


class TestAPIResilience:
    """Testes de resiliência da API"""
    
    def test_concurrent_job_creation(self, client, sample_audio_file):
        """API deve suportar criação de múltiplos jobs"""
        job_ids = []
        
        for i in range(3):
            response = client.post(
                "/jobs",
                data={"input_file": str(sample_audio_file)}
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            job_ids.append(data["job_id"])
        
        # Todos os IDs devem ser únicos
        assert len(job_ids) == len(set(job_ids))
    
    def test_job_status_query_resilience(self, client):
        """Consultas de status devem ser resilientes"""
        # Múltiplas consultas de job inexistente
        for _ in range(5):
            response = client.get("/jobs/nonexistent123")
            assert response.status_code == 404


class TestNormalizationParameters:
    """Testes para parâmetros de normalização"""
    
    def test_remove_noise_parameter(self, client, sample_audio_file):
        """Parâmetro remove_noise deve ser aceito"""
        for value in ["true", "false"]:
            response = client.post(
                "/jobs",
                data={
                    "input_file": str(sample_audio_file),
                    "remove_noise": value
                }
            )
            assert response.status_code in [200, 201]
    
    def test_convert_to_mono_parameter(self, client, sample_audio_file):
        """Parâmetro convert_to_mono deve ser aceito"""
        for value in ["true", "false"]:
            response = client.post(
                "/jobs",
                data={
                    "input_file": str(sample_audio_file),
                    "convert_to_mono": value
                }
            )
            assert response.status_code in [200, 201]
    
    def test_sample_rate_16k_parameter(self, client, sample_audio_file):
        """Parâmetro sample_rate_16k deve ser aceito"""
        for value in ["true", "false"]:
            response = client.post(
                "/jobs",
                data={
                    "input_file": str(sample_audio_file),
                    "sample_rate_16k": value
                }
            )
            assert response.status_code in [200, 201]
