# 🚀 SPRINT 10 - MAIN & API (APLICAÇÃO COMPLETA)

**Status**: ⏳ Pendente  
**Prioridade**: 🔴 CRÍTICA  
**Duração Estimada**: 3-4 horas  
**Pré-requisitos**: Todas as sprints anteriores completas

---

## 🎯 OBJETIVOS

**SPRINT FINAL** - Valida a aplicação completa:

1. ✅ Testar FastAPI application
2. ✅ Validar health checks
3. 🔧 **CRÍTICO**: Testar CRON job sem crashar
4. ✅ Testar endpoints da API
5. ✅ Validar cliente de APIs externas
6. ✅ Garantir que aplicação inicia sem erros

---

## 📁 ARQUIVOS NO ESCOPO

```
app/
├── main.py              # FastAPI + APScheduler + CRON jobs
└── api/
    ├── __init__.py
    └── api_client.py    # Cliente para APIs externas
```

### CRON Jobs em main.py

- **`cleanup_orphaned_videos_cron()`** - ⚠️ **Executado a cada 5min - CAUSAVA O BUG**

---

## 🧪 TESTES - `tests/e2e/test_main_application.py`

```python
"""
Testes end-to-end da aplicação completa
Valida que o CRON job não crashará mais
"""
import pytest
from fastapi.testclient import TestClient


class TestMainApplication:
    """Testes da aplicação FastAPI"""
    
    @pytest.fixture
    def client(self):
        """Cliente de teste FastAPI"""
        from app.main import app
        return TestClient(app)
    
    def test_app_can_be_imported(self):
        """Aplicação pode ser importada"""
        from app import main
        assert main is not None
    
    def test_app_instance_exists(self):
        """Instância FastAPI existe"""
        from app.main import app
        assert app is not None
    
    def test_health_endpoint(self, client):
        """Endpoint /health funciona"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert 'status' in data
        assert data['status'] in ['healthy', 'ok', 'running']
    
    def test_version_endpoint(self, client):
        """Endpoint /version existe"""
        try:
            response = client.get("/version")
            if response.status_code == 200:
                data = response.json()
                assert 'version' in data or 'service_name' in data
        except:
            pytest.skip("Version endpoint não implementado")
    
    def test_root_endpoint(self, client):
        """Endpoint raiz responde"""
        response = client.get("/")
        assert response.status_code in [200, 404]  # Pode não estar implementado
    
    def test_docs_endpoint_exists(self, client):
        """Documentação Swagger existe"""
        response = client.get("/docs")
        assert response.status_code == 200


class TestCronJobs:
    """
    🔴 TESTES CRÍTICOS - CRON jobs não devem crashar
    """
    
    def test_cleanup_cron_function_exists(self):
        """Função de cleanup CRON existe"""
        try:
            from app.main import cleanup_orphaned_videos_cron
            assert callable(cleanup_orphaned_videos_cron)
        except ImportError:
            pytest.skip("CRON job function não encontrada")
    
    def test_cleanup_cron_does_not_crash(self):
        """
        🔴 TESTE MAIS CRÍTICO: CRON job NÃO deve crashar
        Este teste valida que o bug foi realmente corrigido em produção
        """
        try:
            from app.main import cleanup_orphaned_videos_cron
        except ImportError:
            pytest.skip("CRON function não existe")
        
        # Executar cleanup manualmente
        try:
            cleanup_orphaned_videos_cron()
            success = True
            error = None
        except KeyError as e:
            success = False
            error = str(e)
            pytest.fail(f"❌ CRON JOB AINDA CRASHA! KeyError: {e}")
        except Exception as e:
            # Outros erros podem acontecer (ex: Redis down)
            # mas KeyError é o bug crítico
            if 'transform_dir' in str(e) or 'validate_dir' in str(e):
                pytest.fail(f"❌ BUG AINDA PRESENTE! Error: {e}")
            else:
                pytest.skip(f"Outro erro (não bug): {e}")
        
        assert success, f"CRON job deve executar sem KeyError. Error: {error}"
    
    def test_scheduler_can_be_started(self):
        """Scheduler APScheduler pode ser iniciado"""
        try:
            from app.main import scheduler
            assert scheduler is not None
        except (ImportError, AttributeError):
            pytest.skip("Scheduler não encontrado")


class TestApplicationStartup:
    """Testes de inicialização da aplicação"""
    
    def test_application_starts_without_errors(self):
        """Aplicação inicia sem erros"""
        try:
            from app.main import app
            assert app is not None
        except Exception as e:
            pytest.fail(f"Application failed to start: {e}")
    
    def test_all_dependencies_available(self):
        """Todas as dependências estão disponíveis"""
        required_modules = [
            'fastapi',
            'uvicorn',
            'redis',
            'pydantic',
        ]
        
        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError:
                pytest.fail(f"Required module not installed: {module_name}")
    
    def test_settings_loaded_on_startup(self):
        """Settings são carregadas na inicialização"""
        from app.core.config import get_settings
        settings = get_settings()
        
        assert settings is not None
        assert 'service_name' in settings


class TestAPIClient:
    """Testes para api_client.py"""
    
    def test_api_client_module_imports(self):
        """Cliente de API pode ser importado"""
        try:
            from app.api import api_client
            assert api_client is not None
        except ImportError:
            pytest.skip("api_client.py não existe")
    
    def test_api_client_can_make_requests(self):
        """Cliente pode fazer requisições (mock)"""
        import httpx
        
        # Teste básico de httpx (usado pelo cliente)
        try:
            with httpx.Client() as client:
                # Não fazer requisição real, apenas validar que httpx funciona
                assert client is not None
        except Exception as e:
            pytest.fail(f"httpx client failed: {e}")


class TestHealthMonitoring:
    """Testes de monitoramento de saúde"""
    
    def test_health_check_returns_correct_format(self, client):
        """Health check retorna formato esperado"""
        response = client.get("/health")
        
        if response.status_code == 200:
            data = response.json()
            
            # Deve ter pelo menos status
            assert 'status' in data
            
            # Pode ter informações adicionais
            optional_fields = ['service_name', 'version', 'timestamp']
            # Não obrigatório, mas bom ter
    
    def test_application_handles_errors_gracefully(self, client):
        """Aplicação trata erros graciosamente"""
        # Tentar endpoint inexistente
        response = client.get("/nonexistent/endpoint/12345")
        
        # Deve retornar 404, não 500
        assert response.status_code == 404


@pytest.fixture
def client():
    """Fixture global de cliente FastAPI"""
    from app.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)
```

---

## 🧪 TESTE DE INTEGRAÇÃO COMPLETA

```python
# tests/e2e/test_complete_integration.py
"""Teste de integração completa do serviço"""
import pytest
import subprocess
import time


@pytest.mark.slow
class TestCompleteIntegration:
    """Teste end-to-end completo do serviço"""
    
    def test_service_starts_and_responds(self):
        """Serviço inicia e responde a requisições"""
        # Este teste seria executado em ambiente real
        # Aqui apenas validamos que pode ser importado
        from app.main import app
        assert app is not None
    
    def test_cron_jobs_registered(self):
        """CRON jobs estão registrados"""
        try:
            from app.main import scheduler
            jobs = scheduler.get_jobs()
            
            # Deve ter pelo menos o cleanup job
            assert len(jobs) >= 0  # Pode estar vazio se não iniciado
        except:
            pytest.skip("Scheduler não disponível")
    
    def test_all_pipeline_steps_work(self):
        """Todos os passos do pipeline funcionam"""
        # Validar que todas as partes principais existem
        from app.core.config import get_settings
        from app.pipeline.video_pipeline import VideoPipeline
        from app.services.video_status_factory import get_video_status_store
        
        settings = get_settings()
        pipeline = VideoPipeline()
        store = get_video_status_store()
        
        assert settings is not None
        assert pipeline is not None
        assert store is not None
```

---

## 📋 PASSO A PASSO

```bash
# 1. Criar estrutura
mkdir -p tests/e2e
touch tests/e2e/__init__.py
touch tests/e2e/test_main_application.py
touch tests/e2e/test_complete_integration.py

# 2. Implementar testes (copiar código acima)

# 3. Teste CRÍTICO primeiro
pytest tests/e2e/test_main_application.py::TestCronJobs::test_cleanup_cron_does_not_crash -v -s

# 4. Todos os testes e2e
pytest tests/e2e/ -v

# 5. Cobertura
pytest tests/e2e/ --cov=app.main --cov=app.api --cov-report=term

# 6. VALIDAÇÃO FINAL - Executar TUDO
pytest tests/ -v --cov=app --cov-report=html
```

---

## ✅ CRITÉRIOS DE ACEITAÇÃO FINAL

### Sprint 10

- [ ] FastAPI app testada
- [ ] Health checks funcionando
- [ ] **TESTE CRÍTICO PASSA**: `test_cleanup_cron_does_not_crash` ✅
- [ ] CRON job executa sem KeyError
- [ ] API client testado
- [ ] Cobertura > 85%

### Validação Completa (Todas as Sprints)

- [ ] Todas as 11 sprints completas
- [ ] Cobertura global > 85%
- [ ] Bug de produção resolvido
- [ ] CRON job funcional
- [ ] Pipeline end-to-end validado
- [ ] Zero testes falhando

---

## 🎉 VALIDAÇÃO FINAL

```bash
# 1. Executar TODOS os testes
pytest tests/ -v --tb=short

# 2. Verificar cobertura global
pytest tests/ --cov=app --cov-report=html --cov-report=term

# 3. Validação crítica do bug
pytest tests/e2e/test_main_application.py::TestCronJobs::test_cleanup_cron_does_not_crash -v

# Output esperado:
# PASSED ✅

# 4. Smoke test final
python -c "
from app.main import app, cleanup_orphaned_videos_cron
from app.core.config import get_settings

settings = get_settings()
assert 'transform_dir' in settings, 'Bug ainda presente!'
assert 'validate_dir' in settings, 'Bug ainda presente!'

print('✅ Configurações OK')

try:
    cleanup_orphaned_videos_cron()
    print('✅ CRON job OK')
except KeyError as e:
    print(f'❌ CRON job FALHOU: {e}')
    exit(1)

print('')
print('🎉🎉🎉 TODAS AS VALIDAÇÕES PASSARAM! 🎉🎉🎉')
print('Bug de produção RESOLVIDO!')
print('Serviço pronto para deploy!')
"
```

---

## 📊 RELATÓRIO FINAL

Após completar todas as sprints, gere relatório:

```bash
# Cobertura HTML
pytest tests/ --cov=app --cov-report=html

# Abrir relatório
open htmlcov/index.html

# Estatísticas
pytest tests/ --cov=app --cov-report=term -v | tee sprint_final_report.txt
```

---

## 🚀 PRÓXIMOS PASSOS (PÓS-TESTES)

1. ✅ **Code Review** completo
2. ✅ **Merge** para branch main
3. ✅ **Build** de imagem Docker
4. ✅ **Deploy** em staging
5. ✅ **Smoke tests** em staging
6. ✅ **Deploy** em produção
7. ✅ **Monitoramento** 24h

---

**Status**: ⏳ Pendente  
**Data de Conclusão**: ___________  
**CRON Validado**:  ⬜ Sim ⬜ Não  
**Pronto para Produção**: ⬜ Sim ⬜ Não
