# 📋 Sprints Futuras - Observabilidade e Otimizações

**Make-Video Service - Melhorias Futuras**  
**Data**: 2026-02-12  
**Status**: 📝 **PLANEJADO**

---

## 🎯 Contexto

Este documento lista sprints **futuras** que podem ser implementadas conforme necessidade.

**Sprints já implementadas:**
- ✅ Sprint-01: Auto-Recovery System
- ✅ Sprint-02: Granular Checkpoints
- ✅ Sprint-03: Smart Timeout Management
- ✅ Sprint-04: Retry & Circuit Breaker
- ✅ Sprint-07: Comprehensive Health Checks

**Sprints futuras** (este documento):
- 📋 Sprint-06: Resource Management & Cleanup
- 📋 Sprint-08: Rate Limiting & Backpressure

---

## 🧹 Sprint-06: Resource Management & Cleanup

**Prioridade**: P2 (NICE TO HAVE)  
**Esforço**: 4 horas  
**Quando implementar**: Se uso de disco/memória for problema

### Objetivo

Cleanup agressivo de recursos temporários + limites de uso de memória/disco.

### Estratégias

**1. Cleanup Incremental**

```python
# app/services/video_builder.py

class VideoBuilder:
    def __init__(self, ...):
        self.temp_files = []  # Track temp files
        
    async def build_video(self, ...):
        try:
            # ... processamento ...
            
            # Cleanup após cada etapa
            await self._cleanup_stage("download")
            result = await self._download_shorts(...)
            
            await self._cleanup_stage("validation")
            result = await self._validate_shorts(...)
            
            await self._cleanup_stage("build")
            final_video = await self._build_final(...)
            
            return final_video
            
        finally:
            # Cleanup total ao final
            await self._cleanup_all()
    
    async def _cleanup_stage(self, stage: str):
        """Limpa arquivos da etapa anterior"""
        if stage == "validation":
            # Pode deletar shorts rejeitados
            pass
        elif stage == "build":
            # Pode deletar shorts individuais após merge
            pass
```

**2. Limites de Memória**

```python
# app/infrastructure/resource_limiter.py

from dataclasses import dataclass
import psutil
import asyncio

@dataclass
class ResourceLimits:
    max_memory_mb: int = 2048  # 2GB
    max_disk_gb: float = 5.0  # 5GB livre
    max_concurrent_jobs: int = 5

class ResourceManager:
    def __init__(self, limits: ResourceLimits):
        self.limits = limits
        
    async def can_start_job(self) -> tuple[bool, str]:
        """Verifica se recursos disponíveis para novo job"""
        
        # Check memory
        memory = psutil.virtual_memory()
        if memory.available < self.limits.max_memory_mb * 1024 * 1024:
            return False, f"Low memory: {memory.available / 1024 / 1024:.0f}MB"
        
        # Check disk
        disk = psutil.disk_usage('/tmp')
        if disk.free < self.limits.max_disk_gb * 1024 * 1024 * 1024:
            return False, f"Low disk: {disk.free / 1024 / 1024 / 1024:.1f}GB"
        
        # Check concurrent jobs
        active_jobs = await redis_store.get_active_jobs_count()
        if active_jobs >= self.limits.max_concurrent_jobs:
            return False, f"Max concurrent jobs: {active_jobs}"
        
        return True, "OK"
```

**3. Auto-Cleanup de Arquivos Antigos**

```python
# Celery periodic task
@celery_app.task(name='app.celery_tasks.cleanup_old_files')
def cleanup_old_files():
    """Limpa arquivos temporários com mais de 24 horas"""
    import time
    from pathlib import Path
    
    temp_dir = Path('/tmp/makevideo')
    cutoff = time.time() - (24 * 3600)  # 24 horas
    
    cleaned = 0
    freed_bytes = 0
    
    for file_path in temp_dir.rglob('*'):
        if file_path.is_file():
            stat = file_path.stat()
            if stat.st_mtime < cutoff:
                freed_bytes += stat.st_size
                file_path.unlink()
                cleaned += 1
    
    logger.info(
        f"Cleaned {cleaned} files, "
        f"freed {freed_bytes / 1024 / 1024:.1f}MB"
    )

# Agendar para rodar a cada 6 horas
from celery.schedules import crontab

celery_app.conf.beat_schedule['cleanup-old-files'] = {
    'task': 'app.celery_tasks.cleanup_old_files',
    'schedule': crontab(minute=0, hour='*/6'),
}
```

### Benefícios

- 💾 **Disco**: Menos uso de armazenamento
- 🧠 **Memória**: Prevenção de OOM
- ⚡ **Performance**: Sistema mais responsivo
- 🛡️ **Estabilidade**: Menos crashes por falta de recursos

---

## 🚦 Sprint-08: Rate Limiting & Backpressure

**Prioridade**: P3 (LOW)  
**Esforço**: 3 horas  
**Quando implementar**: Se sobrecarga for problema

### Objetivo

Limites globais de requisições + backpressure para proteger sistema.

### Implementação

```python
# app/infrastructure/rate_limiter.py

from datetime import datetime, timedelta
from collections import deque
import asyncio

class SlidingWindowRateLimiter:
    """Rate limiter com sliding window"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()  # (timestamp, )
        self.lock = asyncio.Lock()
    
    async def is_allowed(self) -> bool:
        """Verifica se requisição é permitida"""
        async with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)
            
            # Remove requests antigas
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            # Verifica limite
            if len(self.requests) >= self.max_requests:
                return False
            
            # Adiciona nova request
            self.requests.append(now)
            return True
    
    async def wait_if_needed(self, timeout: float = 60.0):
        """Aguarda até que rate limit permita (com timeout)"""
        start = datetime.now()
        
        while True:
            if await self.is_allowed():
                return True
            
            # Check timeout
            elapsed = (datetime.now() - start).total_seconds()
            if elapsed > timeout:
                return False
            
            # Wait 100ms e tenta novamente
            await asyncio.sleep(0.1)


# Global rate limiter
_rate_limiter = SlidingWindowRateLimiter(
    max_requests=30,  # 30 requisições
    window_seconds=60  # por minuto
)


# No app/main.py
@app.post("/make-video")
async def create_video(...):
    # Check rate limit
    if not await _rate_limiter.is_allowed():
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later."
        )
    
    # ... resto do código ...
```

### Backpressure

```python
# Limitar jobs no queue
@app.post("/make-video")
async def create_video(...):
    # Check queue size
    queue_size = await redis_store.get_queue_size()
    
    if queue_size > 100:  # Max 100 jobs enfileirados
        raise HTTPException(
            status_code=503,
            detail="System overloaded. Queue is full. Try again later."
        )
    
    # ... resto do código ...
```

### Benefícios

- 🛡️ **Proteção**: Evita sobrecarga
- ⚖️ **Fairness**: Distribui recursos igualmente
- 💰 **Custo**: Controla uso de APIs externas

---

## 📅 Roadmap de Implementação Futura

### Quando Implementar Cada Sprint

**Sprint-05 (Observability):** 
- ✅ Implementar quando: Sistema em produção
- 🎯 Objetivo: Monitoramento e alertas
- 📊 Prioridade: Alta (após produção)

**Sprint-06 (Resource Management):**
- ✅ Implementar quando: Problemas de disco/memória
- 🎯 Objetivo: Otimização de recursos
- 📊 Prioridade: Média

**Sprint-08 (Rate Limiting):**
- ✅ Implementar quando: Sobrecarga ou abuso
- 🎯 Objetivo: Proteção contra overload
- 📊 Prioridade: Baixa

### Ordem Recomendada

1. **Sprint-05** (Observability) - Primeiro após produção
   - Fornece visibilidade necessária para identificar problemas
   - Base para decisões sobre outras otimizações

2. **Sprint-06** (Resource Management) - Se métricas mostrarem problema
   - Implementar se observability mostrar alto uso de recursos
   - Pode prevenir crashes

3. **Sprint-08** (Rate Limiting) - Último, se necessário
   - Apenas se houver abuso ou sobrecarga
   - Pode não ser necessário

---

## 📊 Critérios de Decisão

**Implementar Sprint-05 se:**
- ✅ Sistema em produção
- ✅ Necessidade de monitoramento 24/7
- ✅ Time DevOps disponível para configurar Grafana

**Implementar Sprint-06 se:**
- ⚠️ Uso de disco > 80%
- ⚠️ Memory leaks detectados
- ⚠️ Crashes por falta de recursos

**Implementar Sprint-08 se:**
- ⚠️ Abuso de API detectado
- ⚠️ Sobrecarga constante
- ⚠️ Necessidade de controle de custo

---

## 📚 Referências

- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Dashboard Examples](https://grafana.com/grafana/dashboards/)
- [Rate Limiting Strategies](https://cloud.google.com/architecture/rate-limiting-strategies-techniques)
- [Resource Management in Python](https://docs.python.org/3/library/resource.html)

---

**Atualizado**: 2026-02-12  
**Status**: 📝 Planejado para implementação futura conforme necessidade
