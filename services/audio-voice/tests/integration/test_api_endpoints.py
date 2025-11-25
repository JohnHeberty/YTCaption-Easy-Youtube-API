"""
Testes de integração para endpoints da API
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Testes para /health"""
    
    def test_health_check(self):
        """Testa health check"""
        response = client.get("/health")
        assert response.status_code in [200, 503]  # Pode falhar se Redis não estiver rodando
        
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert data["service"] == "audio-voice"


class TestPresetsEndpoint:
    """Testes para /presets"""
    
    def test_get_presets(self):
        """Testa listagem de vozes genéricas"""
        response = client.get("/presets")
        assert response.status_code == 200
        
        data = response.json()
        assert "presets" in data
        assert isinstance(data["presets"], dict)
        assert "female_generic" in data["presets"]


class TestLanguagesEndpoint:
    """Testes para /languages"""
    
    def test_get_languages(self):
        """Testa listagem de idiomas"""
        response = client.get("/languages")
        assert response.status_code == 200
        
        data = response.json()
        assert "languages" in data
        assert "total" in data
        assert isinstance(data["languages"], list)
        assert len(data["languages"]) > 0


class TestJobsEndpoint:
    """Testes para /jobs"""
    
    def test_create_dubbing_job(self):
        """Testa criação de job de dublagem"""
        payload = {
            "mode": "dubbing",
            "text": "Hello world test",
            "source_language": "en",
            "voice_preset": "female_generic"
        }
        
        response = client.post("/jobs", json=payload)
        
        # Pode falhar se Redis/Celery não estiverem rodando
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert data["mode"] == "dubbing"
            assert data["text"] == "Hello world test"
    
    def test_create_job_invalid_language(self):
        """Testa criação de job com idioma inválido"""
        payload = {
            "mode": "dubbing",
            "text": "Test",
            "source_language": "invalid_lang",
            "voice_preset": "female_generic"
        }
        
        response = client.post("/jobs", json=payload)
        assert response.status_code == 400
    
    def test_create_job_text_too_long(self):
        """Testa criação de job com texto muito longo"""
        payload = {
            "mode": "dubbing",
            "text": "x" * 20000,  # Excede limite
            "source_language": "en",
            "voice_preset": "female_generic"
        }
        
        response = client.post("/jobs", json=payload)
        assert response.status_code == 400


class TestVoicesEndpoint:
    """Testes para /voices"""
    
    def test_list_voices(self):
        """Testa listagem de vozes"""
        response = client.get("/voices")
        
        # Pode falhar se Redis não estiver rodando
        if response.status_code == 200:
            data = response.json()
            assert "total" in data
            assert "voices" in data
            assert isinstance(data["voices"], list)
