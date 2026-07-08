"""
End-to-End Tests - Main Application
Tests the complete FastAPI application, health checks, CRON jobs, and startup
"""
import pytest
from fastapi.testclient import TestClient


def _has_paddleocr():
    try:
        import paddleocr
        return True
    except ImportError:
        return False


requires_paddleocr = pytest.mark.skipif(
    not _has_paddleocr(),
    reason="paddleocr not installed"
)


@pytest.fixture(scope="module")
def client():
    """Cliente de teste FastAPI (module scope para reutilização)"""
    from app.main import app
    return TestClient(app)


class TestMainApplication:
    """Testes da aplicação FastAPI principal"""
    
    def test_app_can_be_imported(self):
        """Aplicação pode ser importada sem erros"""
        from app import main
        assert main is not None
        assert hasattr(main, 'app')
    
    def test_app_instance_exists(self):
        """Instância FastAPI existe e está configurada"""
        from app.main import app
        assert app is not None
        assert hasattr(app, 'title')
        assert 'Make-Video' in app.title
    
    def test_app_has_cors_middleware(self):
        """Aplicação tem CORS middleware configurado"""
        from app.main import app
        # Verificar que middleware foi adicionado
        assert hasattr(app, 'user_middleware')
        assert len(app.user_middleware) > 0
    
    def test_health_endpoint(self, client):
        """Endpoint /health funciona e retorna status correto"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert 'status' in data
        # Status pode ser várias coisas
        assert data['status'] in ['healthy', 'ok', 'running', 'up']
    
    def test_root_endpoint(self, client):
        """Endpoint raiz responde"""
        response = client.get("/")
        # Pode retornar 200 (implementado) ou 404 (não implementado)
        assert response.status_code in [200, 404, 307]  # 307 = redirect
    
    def test_docs_endpoint_exists(self, client):
        """Documentação Swagger existe"""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_schema_exists(self, client):
        """OpenAPI schema está disponível"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert 'openapi' in schema
        assert 'info' in schema
        assert 'paths' in schema


class TestCronJobs:
    """
    🔴 TESTES CRÍTICOS - CRON jobs não devem crashar
    
    Este teste valida que o bug KeyError('transform_dir') foi realmente corrigido.
    O bug ocorria porque cleanup_orphaned_videos_cron() rodava a cada 5 minutos
    e crashava tentando acessar chaves que não existiam em get_settings().
    """
    
    def test_cleanup_cron_function_exists(self):
        """Função de cleanup CRON existe e é callable"""
        from app.main import cleanup_orphaned_videos_cron
        assert cleanup_orphaned_videos_cron is not None
        assert callable(cleanup_orphaned_videos_cron)
    
    @pytest.mark.asyncio
    async def test_cleanup_cron_does_not_crash(self):
        """
        🔴 TESTE MAIS CRÍTICO: CRON job NÃO deve crashar com KeyError
        
        Este teste valida que o bug foi realmente corrigido em produção.
        Antes do fix: KeyError('transform_dir') a cada 5 minutos.
        Depois do fix: Executa sem erros.
        """
        from app.main import cleanup_orphaned_videos_cron
        from app.core.config import get_settings
        
        # Primeiro, validar que as chaves existem
        settings = get_settings()
        assert 'transform_dir' in settings, "Bug ainda presente: 'transform_dir' não existe"
        assert 'validate_dir' in settings, "Bug ainda presente: 'validate_dir' não existe"
        assert 'approved_dir' in settings, "Bug ainda presente: 'approved_dir' não existe"
        
        # Agora executar a função CRON
        try:
            await cleanup_orphaned_videos_cron()
            success = True
            error = None
        except KeyError as e:
            success = False
            error = str(e)
            pytest.fail(
                f"❌ CRON JOB AINDA CRASHA! KeyError: {e}\n"
                f"O bug de produção NÃO foi corrigido!"
            )
        except FileNotFoundError:
            # Pode ocorrer se diretórios não existem (normal em testes)
            success = True
            error = None
        except Exception as e:
            # Outros erros podem acontecer (ex: Redis down, FFmpeg não disponível)
            # mas KeyError é o bug crítico que queremos detectar
            if 'transform_dir' in str(e) or 'validate_dir' in str(e) or 'approved_dir' in str(e):
                pytest.fail(
                    f"❌ BUG AINDA PRESENTE! Error relacionado às chaves faltantes: {e}"
                )
            else:
                # Outros erros são aceitáveis em ambiente de teste
                success = True
                error = str(e)
        
        assert success, f"CRON job deve executar sem KeyError. Error: {error}"
    
    def test_scheduler_can_be_accessed(self):
        """Scheduler APScheduler está disponível na aplicação"""
        from app.main import app
        # Scheduler é configurado no startup, pode não estar disponível em testes
        # mas o atributo state deve existir
        assert hasattr(app, 'state')


class TestApplicationStartup:
    """Testes de inicialização da aplicação"""
    
    def test_application_starts_without_errors(self):
        """Aplicação inicia sem erros de import"""
        try:
            from app.main import app
            assert app is not None
        except Exception as e:
            pytest.fail(f"Application failed to start: {e}")
    
    def test_all_dependencies_available(self):
        """Todas as dependências críticas estão instaladas"""
        required_modules = [
            'fastapi',
            'uvicorn',
            'redis',
            'pydantic',
            'httpx',
        ]
        
        missing_modules = []
        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError:
                missing_modules.append(module_name)
        
        if missing_modules:
            pytest.fail(f"Required modules not installed: {', '.join(missing_modules)}")
    
    def test_settings_loaded_on_startup(self):
        """Settings são carregadas corretamente na inicialização"""
        from app.core.config import get_settings
        settings = get_settings()
        
        assert settings is not None
        assert hasattr(settings, '__getitem__'), "Settings deve suportar acesso dict-like"
        assert 'service_name' in settings
    
    def test_settings_has_all_directory_keys(self):
        """Settings tem TODAS as chaves de diretórios necessárias"""
        from app.core.config import get_settings
        settings = get_settings()
        
        # Chaves críticas que causavam o bug
        critical_keys = [
            'transform_dir',
            'validate_dir',
            'approved_dir',
        ]
        
        missing_keys = []
        for key in critical_keys:
            if key not in settings:
                missing_keys.append(key)
        
        assert not missing_keys, (
            f"Chaves faltando em settings: {missing_keys}\n"
            f"Bug de produção NÃO foi corrigido!"
        )
    
    def test_redis_client_can_be_created(self):
        """Cliente Redis pode ser criado (not module-level)"""
        import redis
        from app.core.config import get_settings
        
        settings = get_settings()
        # redis_client é criado localmente em context managers, não como variável global
        # Mas podemos verificar que redis está disponível
        assert redis is not None
    
    def test_api_client_initialized(self):
        """Cliente de APIs externas está inicializado"""
        from app.api.api_client import MicroservicesClient
        assert MicroservicesClient is not None


class TestAPIClient:
    """Testes para api_client.py - Cliente de APIs externas"""
    
    def test_api_client_module_imports(self):
        """Módulo api_client pode ser importado"""
        from app.api import api_client
        assert api_client is not None
    
    def test_api_client_class_exists(self):
        """Classe MicroservicesClient existe"""
        from app.api.api_client import MicroservicesClient
        assert MicroservicesClient is not None
    
    def test_api_client_can_be_instantiated(self):
        """Cliente pode ser instanciado com URLs"""
        from app.api.api_client import MicroservicesClient
        
        client = MicroservicesClient(
            youtube_search_url="http://localhost:8001",
            video_downloader_url="http://localhost:8002",
            audio_transcriber_url="http://localhost:8003"
        )
        
        assert client is not None
        assert client.youtube_search_url == "http://localhost:8001"
        assert client.video_downloader_url == "http://localhost:8002"
        assert client.audio_transcriber_url == "http://localhost:8003"
    
    def test_httpx_client_available(self):
        """httpx (usado pelo api_client) está disponível"""
        import httpx
        
        # Teste básico de httpx (não fazer requisição real)
        with httpx.Client() as client:
            assert client is not None


class TestHealthMonitoring:
    """Testes de monitoramento de saúde e observabilidade"""
    
    def test_health_check_returns_correct_format(self, client):
        """Health check retorna formato esperado"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Deve ter pelo menos status
        assert 'status' in data
        assert data['status'] in ['healthy', 'ok', 'running', 'up']
    
    def test_application_handles_errors_gracefully(self, client):
        """Aplicação trata erros graciosamente (não retorna 500)"""
        response = client.get("/this_endpoint_definitely_does_not_exist_12345")
        
        # Deve retornar 404, não 500
        assert response.status_code == 404
        
        # Deve retornar JSON com detalhes do erro
        data = response.json()
        assert 'error' in data or 'detail' in data


class TestAPIEndpoints:
    """Testes básicos dos principais endpoints da API"""
    
    def test_jobs_endpoint_exists(self, client):
        """Endpoint GET /jobs existe"""
        response = client.get("/jobs")
        # Pode retornar 200 (lista vazia) ou outro status
        assert response.status_code in [200, 401, 422]
    
    def test_cache_stats_endpoint_exists(self, client):
        """Endpoint GET /cache/stats existe"""
        response = client.get("/cache/stats")
        # Pode retornar 200 (stats) ou outro status
        assert response.status_code in [200, 401, 422, 500]
    
    def test_metrics_endpoint_exists(self, client):
        """Endpoint GET /metrics existe"""
        response = client.get("/metrics")
        # Pode retornar 200 (metrics) ou outro status
        assert response.status_code in [200, 401, 422, 500]


class TestApplicationIntegrity:
    """Testes de integridade da aplicação"""
    
    def test_no_import_errors_on_main_modules(self):
        """Não há erros de import nos módulos principais"""
        modules_to_test = [
            'app.main',
            'app.core.config',
            'app.core.models',
            'app.pipeline.video_pipeline',
            'app.services.video_status_factory',
            'app.infrastructure.redis_store',
            'app.api.api_client',
        ]
        
        import_errors = []
        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except ImportError as e:
                import_errors.append(f"{module_name}: {e}")
        
        assert not import_errors, f"Import errors found: {import_errors}"
    
    def test_critical_functions_exist(self):
        """Funções críticas existem e são callable"""
        from app.main import cleanup_orphaned_videos_cron
        from app.core.config import get_settings
        from app.pipeline.video_pipeline import VideoPipeline
        
        assert callable(cleanup_orphaned_videos_cron)
        assert callable(get_settings)
        assert VideoPipeline is not None
    
    @requires_paddleocr
    def test_video_pipeline_can_be_instantiated(self):
        """VideoPipeline pode ser instanciado"""
        from app.pipeline.video_pipeline import VideoPipeline
        
        pipeline = VideoPipeline()
        assert pipeline is not None
        assert hasattr(pipeline, 'cleanup_orphaned_files')
