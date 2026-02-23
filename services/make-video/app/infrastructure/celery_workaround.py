"""
Workaround: Envio de tasks Celery usando Kombu direto

PROBLEMA IDENTIFICADO:
- Celery task.delay(), apply_async(), send_task() TODOS FALHAM silenciosamente  
- Mensagens nunca chegam ao Redis
- Bug em Celery 5.3.4 + Kombu 5.6.2 + Redis transport

SOLUÇÃO:
- Usar Kombu direto para publicar mensagens
- Formato compatível com Celery para workers processar normalmente
"""
import json
import uuid
from typing import Any, Dict, Optional
from kombu import Connection, Producer, Exchange
import logging

logger = logging.getLogger(__name__)


class CeleryKombuWorkaround:
    """
    Publica tasks do Celery usando Kombu direto (bypass do bug do Celery)
    """
    
    def __init__(self, broker_url: str, queue_name: str = 'make_video_queue'):
        self.broker_url = broker_url
        self.queue_name = queue_name
        self.exchange = Exchange(queue_name, type='direct', durable=True)
    
    def send_task(
        self, 
        task_name: str, 
        args: tuple = (), 
        kwargs: Optional[Dict] = None,
        task_id: Optional[str] = None,
        **options
    ) -> str:
        """
        Envia task usando Kombu direto (compatível com formato Celery)
        
        Args:
            task_name: Nome completo da task (ex: 'app.infrastructure.celery_tasks.process_make_video')
            args: Argumentos posicionais da task
            kwargs: Argumentos nomeados da task  
            task_id: ID da task (gerado automaticamente se None)
            **options: Opções adicionais (routing_key, etc.)
        
        Returns:
            str: ID da task enviada
        """
        if kwargs is None:
            kwargs = {}
        
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # Montar body no formato Celery simplificado (apenas args/kwargs)
        # Workers Celery aceitam: (args, kwargs) ou [args, kwargs] ou [args, kwargs, embed]
        body = {
            'args': list(args),
            'kwargs': kwargs,
        }
        
        # Headers Celery
        headers = {
            'lang': 'py',
            'task': task_name,
            'id': task_id,
            'root_id': task_id,
            'parent_id': None,
            'group': None,
        }
        
        # Routing
        routing_key = options.get('routing_key', self.queue_name)
        
        try:
            # Conectar e publicar (CÓDIGO EXATO QUE FUNCIONOU NO TESTE)
            from kombu import Queue
            
            conn = Connection(self.broker_url)
            
            with conn.channel() as channel:
                # Declarar exchange e queue
                queue = Queue(self.queue_name, exchange=self.exchange, routing_key=routing_key)
                queue.declare(channel=channel)
                
                # Usar Producer dentro do context
                with Producer(channel) as producer:
                    # Serializar body manualmente
                    import json
                    serialized_body = json.dumps(body)
                    
                    producer.publish(
                        serialized_body,
                        exchange=self.exchange,
                        routing_key=routing_key,
                        headers=headers,
                        content_type='application/json',
                        content_encoding='utf-8',
                    )
                    
                    logger.info(f"✅ Task enviada via Kombu: {task_name} (ID: {task_id})")
            
            return task_id
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar task via Kombu: {e}")
            raise


def send_make_video_task_workaround(job_id: str, broker_url: str) -> str:
    """
    Helper para enviar process_make_video task usando workaround
    
    Args:
        job_id: ID do job
        broker_url: URL do broker Redis
    
    Returns:
        str: ID da task Celery
    """
    workaround = CeleryKombuWorkaround(broker_url)
    
    task_id = workaround.send_task(
        task_name='app.infrastructure.celery_tasks.process_make_video',
        args=(job_id,),
        routing_key='make_video_queue',
    )
    
    return task_id
