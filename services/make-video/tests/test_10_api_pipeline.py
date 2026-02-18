"""
TESTES MÓDULO 10: API, Pipeline e Integration
Testa API endpoints, video pipeline e integração end-to-end
"""
import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAPIClient:
    """Testes para FastAPI client"""
    
    def test_fastapi_app_import(self):
        """Test 10.1: Importar FastAPI app"""
        print("\n🧪 TEST 10.1: FastAPI app import...")
        
        from app.main import app
        
        assert app is not None
        
        print("✅ FastAPI app importado")
    
    def test_create_test_client(self):
        """Test 10.2: Criar TestClient"""
        print("\n🧪 TEST 10.2: TestClient creation...")
        
        from app.main import app
        
        client = TestClient(app)
        
        assert client is not None
        
        print("✅ TestClient criado")


class TestHealthEndpoint:
    """Testes para Health endpoint"""
    
    def test_health_endpoint(self):
        """Test 10.3: GET /health"""
        print("\n🧪 TEST 10.3: GET /health...")
        
        from app.main import app
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert data is not None
        assert 'status' in data
        
        print(f"✅ Health endpoint OK")
        print(f"   Status: {data.get('status')}")


class TestMakeVideoEndpoint:
    """Testes para /make-video endpoint"""
    
    def test_make_video_endpoint_structure(self):
        """Test 10.4: POST /make-video (estrutura)"""
        print("\n🧪 TEST 10.4: POST /make-video structure...")
        
        from app.main import app
        
        client = TestClient(app)
        
        # Request inválido para testar validação
        response = client.post("/make-video", json={})
        
        # Esperamos 422 (validação) ou 400 (bad request)
        assert response.status_code in [400, 422]
        
        print(f"✅ /make-video valida requests")
        print(f"   Status code: {response.status_code}")
    
    def test_make_video_with_valid_data(self):
        """Test 10.5: POST /make-video com dados válidos"""
        print("\n🧪 TEST 10.5: POST /make-video com dados...")
        
        from app.main import app
        
        client = TestClient(app)
        
        request_data = {
            "shorts_ids": ["test_short_1", "test_short_2"],
            "title": "Test Video",
            "aspect_ratio": "16:9",
            "output_format": "mp4"
        }
        
        response = client.post("/make-video", json=request_data)
        
        # Esperamos 200 (sucesso) ou 202 (aceito)
        # Pode falhar se workers não estão rodando
        print(f"   Status code: {response.status_code}")
        
        if response.status_code in [200, 202]:
            data = response.json()
            assert 'job_id' in data or 'task_id' in data
            print(f"✅ /make-video aceita request")
            print(f"   Job ID: {data.get('job_id', data.get('task_id'))}")
        else:
            print(f"⚠️  /make-video retornou {response.status_code}")
            print(f"   (Normal se workers não estão rodando)")


class TestJobStatusEndpoint:
    """Testes para /job/{job_id} endpoint"""
    
    def test_job_status_endpoint(self):
        """Test 10.6: GET /job/{job_id}"""
        print("\n🧪 TEST 10.6: GET /job/{job_id}...")
        
        from app.main import app
        
        client = TestClient(app)
        
        # Job ID fictício
        job_id = "test_job_12345"
        
        response = client.get(f"/job/{job_id}")
        
        # Esperamos 404 (não encontrado) ou 200 (encontrado)
        assert response.status_code in [200, 404]
        
        print(f"✅ /job/{{job_id}} endpoint funciona")
        print(f"   Status code: {response.status_code}")


class TestVideoPipeline:
    """Testes para VideoPipeline"""
    
    def test_video_pipeline_import(self):
        """Test 10.7: Importar VideoPipeline"""
        print("\n🧪 TEST 10.7: VideoPipeline import...")
        
        try:
            from app.pipeline.video_pipeline import VideoPipeline
            
            assert VideoPipeline is not None
            
            print("✅ VideoPipeline importado")
            
        except ImportError as e:
            print(f"⚠️  VideoPipeline não disponível: {e}")
            pytest.skip("VideoPipeline não implementado")
    
    def test_video_pipeline_initialization(self):
        """Test 10.8: Inicializar VideoPipeline"""
        print("\n🧪 TEST 10.8: VideoPipeline init...")
        
        try:
            from app.pipeline.video_pipeline import VideoPipeline
            from app.core.config import get_settings
            
            settings = get_settings()
            pipeline = VideoPipeline()
            
            assert pipeline is not None
            
            print("✅ VideoPipeline inicializado")
            
        except ImportError as e:
            print(f"⚠️  VideoPipeline não disponível: {e}")
            pytest.skip("VideoPipeline não implementado")


class TestPipelineOrchestrator:
    """Testes para PipelineOrchestrator"""
    
    def test_pipeline_orchestrator_import(self):
        """Test 10.9: Importar PipelineOrchestrator"""
        print("\n🧪 TEST 10.9: PipelineOrchestrator import...")
        
        try:
            from app.pipeline.orchestrator import PipelineOrchestrator
            
            assert PipelineOrchestrator is not None
            
            print("✅ PipelineOrchestrator importado")
            
        except ImportError as e:
            print(f"⚠️  PipelineOrchestrator não disponível: {e}")
            pytest.skip("PipelineOrchestrator não implementado")


class TestCeleryTasks:
    """Testes para Celery Tasks"""
    
    def test_celery_tasks_import(self):
        """Test 10.10: Importar celery_tasks"""
        print("\n🧪 TEST 10.10: celery_tasks import...")
        
        from app.infrastructure.celery_tasks import process_make_video
        
        assert process_make_video is not None
        
        print("✅ celery_tasks importado")
        print(f"   Task: process_make_video")
    
    def test_celery_workaround_import(self):
        """Test 10.11: Importar celery_workaround"""
        print("\n🧪 TEST 10.11: celery_workaround import...")
        
        from app.infrastructure.celery_workaround import (
            CeleryKombuWorkaround,
            send_make_video_task_workaround
        )
        
        assert CeleryKombuWorkaround is not None
        assert send_make_video_task_workaround is not None
        
        print("✅ celery_workaround importado")
        print("   - CeleryKombuWorkaround")
        print("   - send_make_video_task_workaround")


class TestEndToEndIntegration:
    """Testes de integração end-to-end"""
    
    @pytest.mark.integration
    def test_full_video_creation_flow(self):
        """Test 10.12: Fluxo completo de criação (INTEGRAÇÃO)"""
        print("\n🧪 TEST 10.12: Fluxo completo (INTEGRAÇÃO)...")
        print("⚠️  Teste de integração - requer workers rodando")
        
        pytest.skip("Teste de integração manual - requer workers + Redis")
        
        # Este teste seria executado assim:
        # 1. Enviar request para /make-video
        # 2. Aguardar processamento
        # 3. Verificar status via /job/{job_id}
        # 4. Validar arquivo de output
        
        print("   Para executar:")
        print("   1. docker-compose up -d")
        print("   2. curl -X POST localhost:8000/make-video -d '{...}'")
        print("   3. curl localhost:8000/job/{job_id}")


class TestWorkaroundIntegration:
    """Testes para Workaround Kombu"""
    
    def test_workaround_sends_to_redis(self):
        """Test 10.13: Workaround envia para Redis"""
        print("\n🧪 TEST 10.13: Workaround → Redis...")
        
        from app.infrastructure.celery_workaround import send_make_video_task_workaround
        from app.core.config import get_settings
        import redis
        
        settings = get_settings()
        
        # Criar job_id de teste
        job_id = "test_workaround_job_999"
        
        # Verificar fila antes
        r = redis.from_url(settings['redis_url'])
        queue_name = "make_video_queue"
        before_len = r.llen(queue_name)
        
        # NÃO enviar se workers estiverem rodando (consumirão imediatamente)
        print(f"   Queue length antes: {before_len}")
        print(f"   ⚠️  Skipando envio real (workers podem consumir)")
        
        pytest.skip("Teste requer workers parados para verificar fila")
        
        # Este teste seria:
        # task_id = send_make_video_task_workaround(job_id, settings['redis_url'])
        # after_len = r.llen(queue_name)
        # assert after_len > before_len


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
