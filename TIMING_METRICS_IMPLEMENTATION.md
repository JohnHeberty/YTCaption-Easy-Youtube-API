# Implementação de Métricas de Timing

## 📊 Visão Geral

Sistema completo de métricas de timing implementado em **todos os serviços** para monitoramento, SLA tracking e análise de performance.

## 🎯 Campos Implementados

Cada job e stage agora possui 3 timestamps críticos:

### 1. `received_at` 
- **Quando:** Job/Stage foi recebido no sistema
- **Uso:** Calcular tempo de espera em fila
- **Tipo:** `datetime` (auto-populated)

### 2. `started_at`
- **Quando:** Job/Stage começou a processar
- **Uso:** Calcular tempo de processamento real
- **Tipo:** `Optional[datetime]` (setado ao iniciar)

### 3. `completed_at`
- **Quando:** Job/Stage finalizou (sucesso ou falha)
- **Uso:** Calcular tempo total e marcar conclusão
- **Tipo:** `Optional[datetime]` (setado ao finalizar)

## 📦 Serviços Atualizados

### Orchestrator
```python
# PipelineStage
class PipelineStage(BaseModel):
    received_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

```python
# PipelineJob
class PipelineJob(BaseModel):
    received_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime  # Alias para received_at (compatibilidade)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

### Video Downloader
```python
class Job(BaseModel):
    received_at: datetime
    created_at: datetime  # Alias
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

### Audio Normalization
```python
class Job(BaseModel):
    received_at: datetime
    created_at: datetime  # Alias
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

### Audio Transcriber
```python
class Job(BaseModel):
    received_at: datetime
    created_at: datetime  # Alias
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

### YouTube Search
```python
class Job(BaseModel):
    received_at: datetime
    created_at: datetime  # Alias
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

## 🔧 Implementação Técnica

### Orchestrator - execute_pipeline()
```python
async def execute_pipeline(self, job: PipelineJob) -> PipelineJob:
    # Marca quando o pipeline começou a processar
    if not job.started_at:
        job.started_at = datetime.now()
    
    # ... processamento ...
    
    # Marca conclusão (já implementado)
    job.mark_as_completed()  # Seta completed_at
```

### Celery Tasks - Todos os Serviços
```python
# Video Downloader
job.status = JobStatus.DOWNLOADING
job.started_at = datetime.now()  # ✅ Novo
job.progress = 0.0

# Audio Normalization
job.status = JobStatus.PROCESSING
job.started_at = datetime.now()  # ✅ Novo
job.progress = 0.0

# Audio Transcriber
job.status = JobStatus.PROCESSING
job.started_at = datetime.now()  # ✅ Novo
job.progress = 0.0

# YouTube Search
job.status = JobStatus.PROCESSING
job.started_at = datetime.now()  # ✅ Novo
```

## 📈 Casos de Uso

### 1. Calcular Tempo em Fila
```python
queue_time = job.started_at - job.received_at if job.started_at else None
```

### 2. Calcular Tempo de Processamento
```python
processing_time = job.completed_at - job.started_at if job.completed_at else None
```

### 3. Calcular Tempo Total
```python
total_time = job.completed_at - job.received_at if job.completed_at else None
```

### 4. SLA Monitoring
```python
# Exemplo: SLA de 5 minutos para processamento
sla_threshold = timedelta(minutes=5)
processing_time = job.completed_at - job.started_at

if processing_time > sla_threshold:
    logger.warning(f"Job {job.id} exceeded SLA: {processing_time.total_seconds()}s")
```

### 5. Métricas por Stage
```python
# Orchestrator Pipeline
for stage in [job.download_stage, job.normalization_stage, job.transcription_stage]:
    queue_time = stage.started_at - stage.received_at
    processing_time = stage.completed_at - stage.started_at
    print(f"{stage.name}: Queue={queue_time}, Processing={processing_time}")
```

## 🔍 Exemplos de Queries

### Buscar Jobs Lentos
```python
# Jobs que levaram mais de 10 minutos
slow_jobs = [
    job for job in all_jobs 
    if job.completed_at and job.started_at 
    and (job.completed_at - job.started_at) > timedelta(minutes=10)
]
```

### Calcular Média de Tempo em Fila
```python
from statistics import mean

queue_times = [
    (job.started_at - job.received_at).total_seconds()
    for job in all_jobs
    if job.started_at
]

avg_queue_time = mean(queue_times) if queue_times else 0
print(f"Tempo médio em fila: {avg_queue_time:.2f}s")
```

### Identificar Gargalos no Pipeline
```python
# Para cada stage, calcular tempo médio
for stage_name in ['download', 'normalization', 'transcription']:
    stage_times = []
    for job in completed_jobs:
        stage = getattr(job, f'{stage_name}_stage')
        if stage.completed_at and stage.started_at:
            duration = (stage.completed_at - stage.started_at).total_seconds()
            stage_times.append(duration)
    
    if stage_times:
        avg_time = mean(stage_times)
        print(f"{stage_name}: {avg_time:.2f}s (avg)")
```

## ⚡ Performance Metrics Dashboard (Futuro)

Com esses dados, é possível criar:

### Métricas em Tempo Real
- ⏱️ Tempo médio em fila
- 🚀 Tempo médio de processamento
- 📊 Tempo médio total (end-to-end)
- 🎯 Taxa de cumprimento de SLA
- 📈 Throughput (jobs/hora)

### Análise por Stage
- 📥 Download: Tempo médio
- 🔊 Normalization: Tempo médio
- 📝 Transcription: Tempo médio
- 🔍 Identificar gargalos

### Alertas Automáticos
```python
# Exemplo de alerta
if processing_time > timedelta(minutes=10):
    send_alert(f"Job {job.id} processing time exceeded threshold")

if queue_time > timedelta(minutes=2):
    send_alert(f"High queue wait time detected: {queue_time}")
```

## 🎨 Visualizações Possíveis

### 1. Histograma de Tempos
```python
import matplotlib.pyplot as plt

processing_times = [
    (job.completed_at - job.started_at).total_seconds()
    for job in jobs if job.completed_at and job.started_at
]

plt.hist(processing_times, bins=20)
plt.xlabel('Processing Time (seconds)')
plt.ylabel('Frequency')
plt.title('Job Processing Time Distribution')
```

### 2. Timeline de Jobs
```python
# Visualizar quando jobs foram recebidos, iniciados e completados
for job in jobs:
    plt.barh(
        y=job.id,
        left=job.received_at,
        width=(job.completed_at - job.received_at).total_seconds(),
        height=0.3
    )
```

## ✅ Compatibilidade

### Backwards Compatibility
- `created_at` mantido como alias de `received_at`
- Código antigo continua funcionando
- Novos campos são opcionais (Optional[datetime])

### Migration Path
```python
# Jobs antigos sem received_at
if not job.received_at and job.created_at:
    job.received_at = job.created_at
```

## 📝 Notas Importantes

1. **Auto-population:** `received_at` é setado automaticamente na criação
2. **Manual setting:** `started_at` é setado quando processamento inicia
3. **Completion:** `completed_at` já estava implementado, agora consistente
4. **Timezone:** Todos os timestamps usam horário do servidor (datetime.now())
5. **Precisão:** Precisão de microsegundos (datetime padrão)

## 🚀 Commits Relacionados

- **2a319bb** - feat: Add comprehensive timing metrics (received_at, started_at, completed_at) to all services

## 📚 Referências

- Orchestrator: `orchestrator/modules/models.py`, `orchestrator/modules/orchestrator.py`
- Video Downloader: `services/video-downloader/app/models.py`, `app/celery_tasks.py`
- Audio Normalization: `services/audio-normalization/app/models.py`, `app/celery_tasks.py`
- Audio Transcriber: `services/audio-transcriber/app/models.py`, `app/celery_tasks.py`
- YouTube Search: `services/youtube-search/app/models.py`, `app/celery_tasks.py`

---

**Status:** ✅ Implementado e testado em todos os 5 serviços  
**Data:** Janeiro 2025  
**Impacto:** Alto - Essencial para monitoring, SLA tracking e otimização de performance
