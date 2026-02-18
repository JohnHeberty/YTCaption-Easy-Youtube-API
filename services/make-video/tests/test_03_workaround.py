"""
TESTE 3: Workaround Kombu
Testa solução usando Kombu direto
"""
import pytest
import redis
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_01_workaround_send_task():
    """Teste 3.1: Enviar task via workaround"""
    print("\n🧪 TEST 3.1: Testando workaround Kombu...")
    
    from app.infrastructure.celery_workaround import CeleryKombuWorkaround
    from app.infrastructure.celery_config import celery_app
    import redis
    
    # Redis connection
    broker_url = celery_app.conf.broker_url
    parts = broker_url.replace('redis://', '').split('/')
    host_port = parts[0].split(':')
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    db = int(parts[1]) if len(parts) > 1 else 0
    
    r = redis.Redis(host=host, port=port, db=db)
    
    # Limpar queue
    queue_name = 'make_video_queue'
    r.delete(queue_name)
    
    # Usar workaround
    workaround = CeleryKombuWorkaround(broker_url, queue_name)
    
    print("   Enviando task via workaround...")
    task_id = workaround.send_task(
        task_name='app.infrastructure.celery_tasks.process_make_video',
        args=('test_workaround_job',),
        routing_key=queue_name,
    )
    
    print(f"✅ Task enviada via workaround!")
    print(f"   Task ID: {task_id}")
    
    time.sleep(2)
    
    queue_len = r.llen(queue_name)
    print(f"\n📊 Queue length: {queue_len}")
    
    assert queue_len > 0, f"❌ Workaround falhou! Queue length = {queue_len}"
    
    print("✅✅✅ WORKAROUND FUNCIONOU!")
    
    # Ler mensagem para verificar formato
    msg = r.lindex(queue_name, 0)
    print(f"\n📦 Mensagem (primeiros 300 chars):")
    print(f"   {str(msg)[:300]}")


def test_02_workaround_helper():
    """Teste 3.2: Usar helper send_make_video_task_workaround"""
    print("\n🧪 TEST 3.2: Testando helper do workaround...")
    
    from app.infrastructure.celery_workaround import send_make_video_task_workaround
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
    
    print("   Enviando via helper...")
    task_id = send_make_video_task_workaround('test_helper_job', broker_url)
    
    print(f"✅ Task enviada via helper!")
    print(f"   Task ID: {task_id}")
    
    time.sleep(2)
    
    queue_len = r.llen(queue_name)
    print(f"\n📊 Queue length: {queue_len}")
    
    assert queue_len > 0, f"❌ Helper falhou! Queue length = {queue_len}"
    
    print("✅✅✅ HELPER FUNCIONOU!")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
