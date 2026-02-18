"""
TESTE COMPLETO 1: Celery Configuration
Testa TODAS as configurações do Celery
"""
import pytest
import redis
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_01_import_celery_config():
    """Teste 1.1: Importar celery_config"""
    print("\n🧪 TEST 1.1: Importando celery_config...")
    
    from app.infrastructure.celery_config import celery_app
    
    assert celery_app is not None, "celery_app não pode ser None"
    assert celery_app.main == 'make-video', f"celery_app.main incorreto: {celery_app.main}"
    
    print("✅ celery_app importado com sucesso")
    print(f"   Nome: {celery_app.main}")
    print(f"   ID: {id(celery_app)}")


def test_02_celery_basic_configs():
    """Teste 1.2: Configurações básicas do Celery"""
    print("\n🧪 TEST 1.2: Verificando configs básicas...")
    
    from app.infrastructure.celery_config import celery_app
    
    # Serialization
    assert celery_app.conf.task_serializer == 'json', f"task_serializer incorreto: {celery_app.conf.task_serializer}"
    assert 'json' in celery_app.conf.accept_content, f"accept_content incorreto: {celery_app.conf.accept_content}"
    assert celery_app.conf.result_serializer == 'json', f"result_serializer incorreto: {celery_app.conf.result_serializer}"
    
    print("✅ Configurações de serialização corretas")
    print(f"   task_serializer: {celery_app.conf.task_serializer}")
    print(f"   accept_content: {celery_app.conf.accept_content}")
    print(f"   result_serializer: {celery_app.conf.result_serializer}")
    
    # Broker
    assert celery_app.conf.broker_url is not None, "broker_url não configurado"
    assert 'redis://' in celery_app.conf.broker_url, f"broker_url não é Redis: {celery_app.conf.broker_url}"
    
    print("✅ Broker configurado")
    print(f"   broker_url: {celery_app.conf.broker_url}")
    
    # Queue
    assert celery_app.conf.task_default_queue == 'make_video_queue', f"task_default_queue incorreto: {celery_app.conf.task_default_queue}"
    
    print("✅ Queue configurada")
    print(f"   task_default_queue: {celery_app.conf.task_default_queue}")


def test_03_broker_connection():
    """Teste 1.3: Conexão com broker Redis"""
    print("\n🧪 TEST 1.3: Testando conexão com Redis...")
    
    from app.infrastructure.celery_config import celery_app
    
    # Criar conexão
    conn = celery_app.broker_connection()
    assert conn is not None, "Conexão não criada"
    
    print("✅ Conexão com broker criada")
    print(f"   Connection: {conn}")
    
    # Testar conectar
    try:
        conn.connect()
        print("✅ Conectado ao broker com sucesso")
    except Exception as e:
        pytest.fail(f"Falha ao conectar ao broker: {e}")
    finally:
        conn.release()


def test_04_import_celery_tasks():
    """Teste 1.4: Importar celery_tasks"""
    print("\n🧪 TEST 1.4: Importando celery_tasks...")
    
    from app.infrastructure.celery_tasks import process_make_video
    
    assert process_make_video is not None, "process_make_video não importado"
    assert process_make_video.name == 'app.infrastructure.celery_tasks.process_make_video', \
        f"Nome da task incorreto: {process_make_video.name}"
    
    print("✅ Task importada com sucesso")
    print(f"   Nome: {process_make_video.name}")
    print(f"   App: {process_make_video.app.main}")


def test_05_task_registration():
    """Teste 1.5: Verificar tasks registradas"""
    print("\n🧪 TEST 1.5: Verificando tasks registradas...")
    
    from app.infrastructure.celery_config import celery_app
    
    registered_tasks = list(celery_app.tasks.keys())
    
    assert 'app.infrastructure.celery_tasks.process_make_video' in registered_tasks, \
        "process_make_video não registrada"
    
    print("✅ Tasks registradas corretamente")
    print(f"   Total de tasks: {len(registered_tasks)}")
    print(f"   Tasks principais:")
    for task in registered_tasks:
        if 'app.infrastructure' in task:
            print(f"     - {task}")


def test_06_producer_creation():
    """Teste 1.6: Criar Producer"""
    print("\n🧪 TEST 1.6: Criando Producer...")
    
    from app.infrastructure.celery_config import celery_app
    
    with celery_app.producer_or_acquire() as producer:
        assert producer is not None, "Producer não criado"
        
        print("✅ Producer criado")
        print(f"   Producer class: {type(producer)}")
        print(f"   Producer.serializer: {producer.serializer}")
        print(f"   Producer.connection: {type(producer.connection)}")


def test_07_redis_direct_connection():
    """Teste 1.7: Conexão direta com Redis"""
    print("\n🧪 TEST 1.7: Testando Redis direto...")
    
    from app.infrastructure.celery_config import celery_app
    import redis
    
    # Extrair host/port do broker_url
    broker_url = celery_app.conf.broker_url
    # Formato: redis://host:port/db
    parts = broker_url.replace('redis://', '').split('/')
    host_port = parts[0].split(':')
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    db = int(parts[1]) if len(parts) > 1 else 0
    
    r = redis.Redis(host=host, port=port, db=db)
    
    # Testar ping
    try:
        assert r.ping(), "Redis não respondeu ao ping"
        print("✅ Redis respondendo")
        print(f"   Host: {host}:{port}")
        print(f"   DB: {db}")
    except Exception as e:
        pytest.fail(f"Redis não acessível: {e}")


def test_08_queue_exists():
    """Teste 1.8: Verificar se queue existe no Redis"""
    print("\n🧪 TEST 1.8: Verificando queue no Redis...")
    
    from app.infrastructure.celery_config import celery_app
    import redis
    
    # Conectar ao Redis
    broker_url = celery_app.conf.broker_url
    parts = broker_url.replace('redis://', '').split('/')
    host_port = parts[0].split(':')
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    db = int(parts[1]) if len(parts) > 1 else 0
    
    r = redis.Redis(host=host, port=port, db=db)
    
    # Listar keys relacionadas a make_video
    keys = r.keys('*make_video*')
    
    print(f"✅ Verificado Redis")
    print(f"   Keys com 'make_video': {len(keys)}")
    for key in sorted(keys)[:10]:
        key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)
        key_type = r.type(key).decode('utf-8') if isinstance(r.type(key), bytes) else r.type(key)
        print(f"     - {key_str} (type={key_type})")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
