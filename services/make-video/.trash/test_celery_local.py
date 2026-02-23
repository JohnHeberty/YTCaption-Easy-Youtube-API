#!/usr/bin/env python
"""
Teste local do Celery - Enviar e processar task
"""
import sys
sys.path.insert(0, '.')

import time
from app.infrastructure.celery_config import celery_app
from app.infrastructure.celery_tasks import process_make_video

print("=" * 70)
print("🧪 TESTE LOCAL DO CELERY")
print("=" * 70)

# 1. Verificar tasks registradas
print("\n1️⃣ Tasks registradas no celery_app:")
registered_tasks = [t for t in celery_app.tasks.keys() if not t.startswith('celery.')]
for task in registered_tasks[:10]:
    print(f"   - {task}")

# 2. Verificar task específica
print(f"\n2️⃣ Task process_make_video:")
print(f"   Name: {process_make_video.name}")
print(f"   Registered: {'app.infrastructure.celery_tasks.process_make_video' in celery_app.tasks}")

# 3. Enviar task de teste
print(f"\n3️⃣ Enviando task de teste...")
test_job_id = "test_local_job_123"

try:
    # Enviar task
    result = process_make_video.apply_async(
        args=(test_job_id,),
        queue='make_video_queue'
    )
    
    print(f"   ✅ Task enviada!")
    print(f"   Task ID: {result.id}")
    print(f"   Queue: make_video_queue")
    print(f"   Task name: {result.task_name}")
    
    # 4. Aguardar e verificar status
    print(f"\n4️⃣ Monitorando status...")
    
    for i in range(10):
        state = result.state
        print(f"   [{i+1}/10] State: {state}")
        
        if state in ['SUCCESS', 'FAILURE']:
            print(f"\n   ✅ Task completou: {state}")
            if state == 'SUCCESS':
                print(f"   Resultado: {result.result}")
            else:
                print(f"   Erro: {result.info}")
            break
            
        time.sleep(2)
    else:
        print(f"\n   ⏱️ Timeout após 20s")
        print(f"   Estado final: {result.state}")
        
except Exception as e:
    print(f"   ❌ Erro ao enviar: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("🏁 TESTE COMPLETO")
print("=" * 70)
