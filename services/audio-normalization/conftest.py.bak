"""
Configuração do pytest e fixtures compartilhadas
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from typing import Generator

# Importações do projeto
from app.models import Job, JobStatus
from app.redis_store_new import RedisJobStore
from app.config import get_settings


@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop para toda a sessão de testes"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def settings():
    """Fixture com configurações de teste"""
    with patch.dict('os.environ', {
        'REDIS_URL': 'redis://localhost:6379/15',  # DB específico para testes
        'ENVIRONMENT': 'test',
        'LOG_LEVEL': 'DEBUG',
        'RATE_LIMIT_REQUESTS': '100',
        'RATE_LIMIT_WINDOW': '60',
        'MAX_FILE_SIZE': '52428800',  # 50MB para testes
        'PROCESSING_TIMEOUT': '300',  # 5 minutos
        'MAX_CONCURRENT_JOBS': '5'
    }):
        yield get_settings()


@pytest.fixture
def redis_mock():
    """Mock do Redis para testes unitários"""
    mock_redis = Mock()
    mock_redis.ping = Mock(return_value=True)
    mock_redis.set = Mock(return_value=True)
    mock_redis.get = Mock(return_value=None)
    mock_redis.delete = Mock(return_value=1)
    mock_redis.keys = Mock(return_value=[])
    mock_redis.pipeline = Mock()
    mock_redis.pipeline.return_value.__enter__ = Mock(return_value=mock_redis)
    mock_redis.pipeline.return_value.__exit__ = Mock(return_value=None)
    mock_redis.execute_command = Mock()
    
    return mock_redis


@pytest.fixture
def job_store(redis_mock, settings) -> RedisJobStore:
    """Fixture do job store com Redis mockado"""
    with patch('app.redis_store_new.redis.Redis') as mock_redis_class:
        mock_redis_class.return_value = redis_mock
        
        store = RedisJobStore(settings)
        
        # Adiciona métodos de teste
        store._test_data = {}
        
        # Sobrescreve métodos para usar dicionário em memória
        original_save = store.save_job
        original_get = store.get_job
        original_delete = store.delete_job
        
        def mock_save_job(job: Job):
            store._test_data[job.id] = job.model_dump_json()
            return original_save(job)
        
        def mock_get_job(job_id: str):
            if job_id in store._test_data:
                from app.models import Job
                job_data = store._test_data[job_id]
                return Job.model_validate_json(job_data)
            return None
        
        def mock_delete_job(job_id: str):
            if job_id in store._test_data:
                del store._test_data[job_id]
            return original_delete(job_id)
        
        store.save_job = mock_save_job
        store.get_job = mock_get_job
        store.delete_job = mock_delete_job
        
        yield store


@pytest.fixture
def sample_job() -> Job:
    """Fixture com job de exemplo"""
    return Job.create_new(
        input_file="/tmp/test_audio.mp3",
        remove_noise=True,
        normalize_volume=True,
        convert_to_mono=False,
        apply_highpass_filter=False,
        set_sample_rate_16k=False
    )


@pytest.fixture
def temp_audio_file() -> Generator[Path, None, None]:
    """Cria arquivo de áudio temporário para testes"""
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
        # Escreve cabeçalho MP3 básico
        mp3_header = b'\xff\xfb\x90\x00'  # MP3 frame header
        temp_file.write(mp3_header)
        temp_file.write(b'\x00' * 1000)  # Dados de áudio simulados
        temp_path = Path(temp_file.name)
    
    yield temp_path
    
    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Cria diretório temporário para testes"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_audio_processor():
    """Mock do processador de áudio"""
    mock_processor = Mock()
    
    # Resultado de processamento bem-sucedido
    success_result = Mock()
    success_result.success = True
    success_result.output_file = "/tmp/processed_output.mp3"
    success_result.processing_time = 5.2
    success_result.error = None
    
    # Resultado de processamento com falha
    failure_result = Mock()
    failure_result.success = False
    failure_result.output_file = None
    failure_result.processing_time = 0
    failure_result.error = "Processing failed"
    
    mock_processor.process_audio = AsyncMock(return_value=success_result)
    mock_processor.success_result = success_result
    mock_processor.failure_result = failure_result
    
    return mock_processor


@pytest.fixture
def mock_file_upload():
    """Mock de arquivo enviado via upload"""
    mock_file = Mock()
    mock_file.filename = "test_audio.mp3"
    mock_file.content_type = "audio/mpeg"
    mock_file.size = 1024 * 1024  # 1MB
    
    # Conteúdo de arquivo MP3 válido
    mp3_content = b'\xff\xfb\x90\x00' + b'\x00' * 1000
    mock_file.read = AsyncMock(return_value=mp3_content)
    mock_file.seek = AsyncMock()
    
    return mock_file


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Limpa arquivos temporários após cada teste"""
    yield
    
    # Lista de padrões de arquivos temporários para limpar
    temp_patterns = [
        "/tmp/test_*.mp3",
        "/tmp/chaos_*.mp3",
        "/tmp/perf_test_*.mp3",
        "/tmp/memory_test_*.mp3",
        "/tmp/cleanup_*.mp3",
        "/tmp/*_output.mp3"
    ]
    
    import glob
    for pattern in temp_patterns:
        for file_path in glob.glob(pattern):
            try:
                Path(file_path).unlink()
            except (FileNotFoundError, PermissionError):
                pass  # Arquivo já foi removido ou não pode ser removido


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Configura ambiente de teste"""
    # Configurações específicas para testes
    import os
    os.environ.setdefault('TESTING', '1')
    os.environ.setdefault('LOG_LEVEL', 'DEBUG')
    
    # Limpa cache de configurações
    from app.config import get_settings
    get_settings.cache_clear()
    
    yield
    
    # Cleanup final
    if 'TESTING' in os.environ:
        del os.environ['TESTING']


# Marcadores personalizados para pytest
def pytest_configure(config):
    """Configura marcadores personalizados"""
    config.addinivalue_line(
        "markers", "unit: marca testes unitários"
    )
    config.addinivalue_line(
        "markers", "integration: marca testes de integração"
    )
    config.addinivalue_line(
        "markers", "performance: marca testes de performance"
    )
    config.addinivalue_line(
        "markers", "load: marca testes de carga"
    )
    config.addinivalue_line(
        "markers", "stress: marca testes de stress"
    )
    config.addinivalue_line(
        "markers", "chaos: marca testes de chaos engineering"
    )
    config.addinivalue_line(
        "markers", "recovery: marca testes de recuperação"
    )
    config.addinivalue_line(
        "markers", "edge_case: marca testes de casos extremos"
    )
    config.addinivalue_line(
        "markers", "slow: marca testes que demoram mais de 5 segundos"
    )


# Configuração para testes assíncronos
@pytest.fixture(scope="session")
def asyncio_mode():
    return "auto"


# Hook para capturar e relatar métricas de performance
@pytest.fixture(autouse=True)
def performance_metrics(request):
    """Coleta métricas de performance para cada teste"""
    import time
    import psutil
    
    # Métricas iniciais
    start_time = time.time()
    process = psutil.Process()
    start_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    yield
    
    # Métricas finais
    end_time = time.time()
    end_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    duration = end_time - start_time
    memory_delta = end_memory - start_memory
    
    # Adiciona métricas como atributos do teste
    request.node.user_properties.append(("duration", f"{duration:.3f}s"))
    request.node.user_properties.append(("memory_delta", f"{memory_delta:.1f}MB"))
    
    # Log para testes lentos ou que consomem muita memória
    if duration > 5.0:
        print(f"\n⚠️  Teste lento: {request.node.name} levou {duration:.3f}s")
    
    if abs(memory_delta) > 50:
        print(f"\n⚠️  Alto uso de memória: {request.node.name} usou {memory_delta:.1f}MB")


# Plugin para relatório de cobertura de testes
def pytest_html_report_title(report):
    """Customiza título do relatório HTML"""
    report.title = "Audio Normalization Service - Test Report"


def pytest_metadata(metadata):
    """Adiciona metadados ao relatório"""
    metadata['Service'] = 'Audio Normalization Microservice'
    metadata['Environment'] = 'Test'
    metadata['Python Version'] = f"{metadata.get('Python', 'Unknown')}"