"""
TESTE COMPLETO 2: Envio de Tasks Celery
Testa o envio REAL de tasks e verificação na queue
"""
import pytest
import redis
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_01_send_task_simple():
    """Teste 2.1: Enviar task simples"""
    print("\n🧪 TEST 2.1: Enviando task simples...")
    
    from app.infrastructure.celery_config import celery_app
    from app.infrastructure.celery_tasks import process_make_video
    
    # Conectar ao Redis
    broker_url = celery_app.conf.broker_url
    parts = broker_url.replace('redis://', '').split('/')
    host_port = parts[0].split(':')
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    db = int(parts[1]) if len(parts) > 1 else 0
    
    r = redis.Redis(host=host, port=port, db=db)
    
    # Limpar queue antes do teste
    queue_name = 'make_video_queue'
    if r.exists(queue_name):
        initial_len = r.llen(queue_name)
        print(f"   Queue existe com {initial_len} mensagens, limpando...")
        r.delete(queue_name)
    
    print("   Enviando task...")
    result = process_make_video.delay('test_job_id_simple')
    
    print(f"✅ Task enviada!")
    print(f"   Task ID: {result.id}")
    print(f"   Task state: {result.state}")
    
    # Aguardar mensagem chegar
    time.sleep(2)
    
    # Verificar queue
    queue_len = r.llen(queue_name)
    
    print(f"\n📊 Estado da queue:")
    print(f"   Nome: {queue_name}")
    print(f"   Length: {queue_len}")
    
    if queue_len > 0:
        print("✅ MENSAGEM CHEGOU NA QUEUE!")
        # Ler mensagem (sem remover)
        msg = r.lindex(queue_name, 0)
        print(f"   Mensagem (primeiros 200 chars): {str(msg)[:200]}")
    else:
        # Verificar priority queues
        print("\n   Verificando priority queues...")
        for suffix in ['\x06\x163', '\x06\x166', '\x06\x169']:
            pq_name = f'{queue_name}{suffix}'
            pq_len = r.llen(pq_name)
            if pq_len > 0:
                print(f"   ✅ ENCONTRADA em {repr(pq_name)}: len={pq_len}")
                msg = r.lindex(pq_name, 0)
                print(f"      Mensagem: {str(msg)[:200]}")
                break
        else:
            # Listar TODAS as queues
            print("\n   Listando TODAS keys com make_video:")
            keys = r.keys('*make_video*')
            for key in sorted(keys)[:20]:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)
                key_type = r.type(key).decode('utf-8') if isinstance(r.type(key), bytes) else r.type(key)
                if key_type == 'list':
                    klen = r.llen(key)
                    print(f"     - {key_str}: type={key_type}, len={klen}")
            
            pytest.fail(f"❌ MENSAGEM NÃO CHEGOU! Queue length = {queue_len}")


def test_02_send_task_apply_async():
    """Teste 2.2: Enviar com apply_async()"""
    print("\n🧪 TEST 2.2: Enviando com apply_async()...")
    
    from app.infrastructure.celery_config import celery_app
    from app.infrastructure.celery_tasks import process_make_video
    import redis
    
    # Redis connection
    broker_url = celery_app.conf.broker_url
    parts = broker_url.replace('redis://', '').split('/')
    host_port = parts[0].split(':')
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    db = int(parts[1]) if len(parts) > 1 else 0
    
    r = redis.Redis(host=host, port=port, db=db)
    
    # Limpar
    queue_name = 'make_video_queue'
    r.delete(queue_name)
    
    print("   Enviando com apply_async()...")
    result = process_make_video.apply_async(
        args=('test_job_apply_async',),
        queue='make_video_queue',
        routing_key='make_video_queue',
    )
    
    print(f"✅ Task enviada via apply_async!")
    print(f"   Task ID: {result.id}")
    
    time.sleep(2)
    
    queue_len = r.llen(queue_name)
    print(f"\n📊 Queue length: {queue_len}")
    
    assert queue_len > 0, f"❌ apply_async não funcionou! Queue length = {queue_len}"
    print("✅ apply_async funcionou!")


def test_03_send_task_explicit_serializer():
    """Teste 2.3: Enviar com serializer explícito"""
    print("\n🧪 TEST 2.3: Enviando com serializer='json' explícito...")
    
    from app.infrastructure.celery_config import celery_app
    from app.infrastructure.celery_tasks import process_make_video
    import redis
    
    # Redis
    broker_url = celery_app.conf.broker_url
    parts = broker_url.replace('redis://', '').split('/')
    host_port = parts[0].split(':')
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    db = int(parts[1]) if len(parts) > 1 else 0
    
    r = redis.Redis(host=host, port=port, db=db)
    
    # Limpar
    queue_name = 'make_video_queue'
    r.delete(queue_name)
    
    print("   Enviando com serializer explícito...")
    result = process_make_video.apply_async(
        args=('test_explicit_serializer',),
        queue='make_video_queue',
        serializer='json',
    )
    
    print(f"✅ Task enviada!")
    print(f"   Task ID: {result.id}")
    
    time.sleep(2)
    
    queue_len = r.llen(queue_name)
    print(f"\n📊 Queue length: {queue_len}")
    
    assert queue_len > 0, f"❌ Serializer explícito não funcionou! Queue length = {queue_len}"
    print("✅ Serializer explícito funcionou!")


def test_04_kombu_direct_publish():
    """Teste 2.4: Publicar direto com Kombu"""
    print("\n🧪 TEST 2.4: Publicando direto com Kombu...")
    
    from kombu import Connection, Producer, Exchange, Queue
    from app.infrastructure.celery_config import celery_app
    import redis
    
    # Redis
    broker_url = celery_app.conf.broker_url
    parts = broker_url.replace('redis://', '').split('/')
    host_port = parts[0].split(':')
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    db = int(parts[1]) if len(parts) > 1 else 0
    
    r = redis.Redis(host=host, port=port, db=db)
    
    # Limpar
    queue_name = 'test_kombu_direct'
    r.delete(queue_name)
    
    # Criar conexão Kombu
    conn = Connection(broker_url)
    
    with conn.channel() as channel:
        # Declarar exchange e queue
        exchange = Exchange(queue_name, type='direct')
        queue = Queue(queue_name, exchange=exchange, routing_key=queue_name)
        queue.declare(channel=channel)
        
        # Publicar
        with Producer(channel) as producer:
            print("   Publicando com Kombu direto...")
            producer.publish(
                {'test': 'kombu_direct_message'},
                exchange=exchange,
                routing_key=queue_name,
                serializer='json',
            )
            print("✅ Mensagem publicada!")
    
    time.sleep(2)
    
    queue_len = r.llen(queue_name)
    print(f"\n📊 Queue length: {queue_len}")
    
    assert queue_len > 0, f"❌ Kombu direto não funcionou! Queue length = {queue_len}"
    print("✅ Kombu direto funcionou!")
    
    # Limpar
    r.delete(queue_name)


def test_05_celery_app_send_task():
    """Teste 2.5: Usar celery_app.send_task()"""
    print("\n🧪 TEST 2.5: Usando celery_app.send_task()...")
    
    from app.infrastructure.celery_config import celery_app
    import redis
    
    # Redis
    broker_url = celery_app.conf.broker_url
    parts = broker_url.replace('redis://', '').split('/')
    host_port = parts[0].split(':')
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    db = int(parts[1]) if len(parts) > 1 else 0
    
    r = redis.Redis(host=host, port=port, db=db)
    
    # Limpar
    queue_name = 'make_video_queue'
    r.delete(queue_name)
    
    print("   Enviando com send_task()...")
    result = celery_app.send_task(
        'app.infrastructure.celery_tasks.process_make_video',
        args=('test_send_task',),
        queue='make_video_queue',
    )
    
    print(f"✅ Task enviada via send_task!")
    print(f"   Task ID: {result.id}")
    
    time.sleep(2)
    
    queue_len = r.llen(queue_name)
    print(f"\n📊 Queue length: {queue_len}")
    
    assert queue_len > 0, f"❌ send_task não funcionou! Queue length = {queue_len}"
    print("✅ send_task funcionou!")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
