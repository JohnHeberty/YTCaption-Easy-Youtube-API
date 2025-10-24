# Phase 5: Batch Processing API

**Status**: ⏳ PENDENTE  
**Prioridade**: 🟡 MEDIUM  
**Esforço Estimado**: 3 horas  
**Impacto**: Médio  
**ROI**: ⭐⭐⭐⭐

---

## 📋 Objetivo

Permitir transcrição de múltiplos vídeos em uma única requisição, otimizando throughput e reduzindo overhead de rede para usuários que precisam processar playlists ou listas de vídeos.

---

## 🎯 Motivação

**Casos de uso**:
- 📺 Canal do YouTube quer transcrever todos os vídeos
- 🎓 Curso online com múltiplas aulas
- 📊 Análise em massa de conteúdo
- 🤖 Processamento automatizado de playlists

**Problemas atuais**:
- ❌ Usuário precisa fazer N requisições sequenciais
- ❌ Alto overhead de rede (handshake, headers, etc.)
- ❌ Difícil gerenciar múltiplas transcrições
- ❌ Sem progresso consolidado

**Benefícios esperados**:
- ✅ Redução de 70% no overhead de rede
- ✅ Processamento paralelo automático
- ✅ Progresso consolidado em tempo real
- ✅ Retry automático de falhas individuais
- ✅ Melhor UX para processamento em massa

---

## 🏗️ Arquitetura Proposta

### Endpoint

```http
POST /api/v1/transcribe/batch
Content-Type: application/json
Authorization: Bearer <token>

{
  "videos": [
    {
      "youtube_url": "https://youtube.com/watch?v=abc123",
      "language": "en",
      "model": "base"
    },
    {
      "youtube_url": "https://youtube.com/watch?v=def456",
      "language": "pt",
      "model": "small"
    }
  ],
  "options": {
    "parallel": true,
    "max_concurrent": 3,
    "continue_on_error": true,
    "notify_webhook": "https://myapp.com/webhook"
  }
}
```

### Response Structure

```json
{
  "batch_id": "batch_abc123xyz",
  "status": "processing",
  "total_videos": 2,
  "completed": 0,
  "failed": 0,
  "in_progress": 2,
  "estimated_completion": "2025-10-21T15:30:00Z",
  "results": [],
  "created_at": "2025-10-21T15:25:00Z",
  "updated_at": "2025-10-21T15:25:05Z"
}
```

### Status Endpoint

```http
GET /api/v1/transcribe/batch/{batch_id}
Authorization: Bearer <token>

Response:
{
  "batch_id": "batch_abc123xyz",
  "status": "completed",
  "total_videos": 2,
  "completed": 2,
  "failed": 0,
  "in_progress": 0,
  "results": [
    {
      "video_index": 0,
      "youtube_url": "https://youtube.com/watch?v=abc123",
      "status": "success",
      "transcription_id": "trans_123",
      "processing_time": 45.2,
      "completed_at": "2025-10-21T15:26:30Z"
    },
    {
      "video_index": 1,
      "youtube_url": "https://youtube.com/watch?v=def456",
      "status": "success",
      "transcription_id": "trans_124",
      "processing_time": 52.8,
      "completed_at": "2025-10-21T15:27:15Z"
    }
  ],
  "progress_percentage": 100,
  "estimated_completion": null,
  "completed_at": "2025-10-21T15:27:15Z"
}
```

---

## 🛠️ Implementação Técnica

### 1. Batch Request DTO

```python
# src/application/dtos/batch_dtos.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional

class BatchVideoRequest(BaseModel):
    youtube_url: str
    language: str = "auto"
    model: str = "base"

class BatchOptions(BaseModel):
    parallel: bool = True
    max_concurrent: int = Field(default=3, ge=1, le=10)
    continue_on_error: bool = True
    notify_webhook: Optional[str] = None

class BatchTranscribeRequestDTO(BaseModel):
    videos: List[BatchVideoRequest] = Field(..., min_items=1, max_items=10)
    options: BatchOptions = BatchOptions()
    
    @validator('videos')
    def validate_max_videos(cls, v):
        if len(v) > 10:
            raise ValueError('Maximum 10 videos per batch')
        return v

class BatchVideoResult(BaseModel):
    video_index: int
    youtube_url: str
    status: str  # success, failed, pending, processing
    transcription_id: Optional[str] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None
    completed_at: Optional[str] = None

class BatchTranscribeResponseDTO(BaseModel):
    batch_id: str
    status: str  # pending, processing, completed, failed
    total_videos: int
    completed: int
    failed: int
    in_progress: int
    progress_percentage: float
    results: List[BatchVideoResult]
    estimated_completion: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
```

### 2. Batch Manager Service

```python
# src/infrastructure/batch/batch_manager.py
import asyncio
from typing import List, Dict
from datetime import datetime, timedelta
import uuid

class BatchTranscriptionManager:
    def __init__(self):
        self._batches: Dict[str, BatchState] = {}
        self._lock = asyncio.Lock()
    
    async def create_batch(
        self,
        videos: List[BatchVideoRequest],
        options: BatchOptions,
        user_id: str
    ) -> str:
        """Cria um novo batch e retorna o batch_id."""
        batch_id = f"batch_{uuid.uuid4().hex[:12]}"
        
        batch_state = BatchState(
            batch_id=batch_id,
            videos=videos,
            options=options,
            user_id=user_id,
            total_videos=len(videos),
            created_at=datetime.utcnow()
        )
        
        async with self._lock:
            self._batches[batch_id] = batch_state
        
        return batch_id
    
    async def process_batch(
        self,
        batch_id: str,
        transcribe_use_case: TranscribeYouTubeVideoUseCase
    ):
        """Processa todos os vídeos do batch."""
        batch = self._batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        batch.status = "processing"
        batch.updated_at = datetime.utcnow()
        
        if batch.options.parallel:
            await self._process_parallel(batch, transcribe_use_case)
        else:
            await self._process_sequential(batch, transcribe_use_case)
        
        batch.status = "completed" if batch.failed == 0 else "partially_failed"
        batch.completed_at = datetime.utcnow()
        batch.updated_at = datetime.utcnow()
    
    async def _process_parallel(
        self,
        batch: BatchState,
        transcribe_use_case: TranscribeYouTubeVideoUseCase
    ):
        """Processa vídeos em paralelo com semáforo."""
        semaphore = asyncio.Semaphore(batch.options.max_concurrent)
        
        async def process_video(index: int, video: BatchVideoRequest):
            async with semaphore:
                await self._transcribe_single_video(
                    batch, index, video, transcribe_use_case
                )
        
        tasks = [
            process_video(i, video)
            for i, video in enumerate(batch.videos)
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _transcribe_single_video(
        self,
        batch: BatchState,
        index: int,
        video: BatchVideoRequest,
        transcribe_use_case: TranscribeYouTubeVideoUseCase
    ):
        """Transcreve um único vídeo e atualiza resultado."""
        result = BatchVideoResult(
            video_index=index,
            youtube_url=video.youtube_url,
            status="processing"
        )
        batch.results[index] = result
        batch.in_progress += 1
        
        try:
            start_time = time.time()
            
            # Executar transcrição
            request_dto = TranscribeRequestDTO(
                youtube_url=video.youtube_url,
                language=video.language,
                model=video.model
            )
            response = await transcribe_use_case.execute(request_dto)
            
            # Sucesso
            result.status = "success"
            result.transcription_id = response.transcription_id
            result.processing_time = time.time() - start_time
            result.completed_at = datetime.utcnow().isoformat()
            
            batch.completed += 1
            
        except Exception as e:
            # Falha
            result.status = "failed"
            result.error = str(e)
            result.completed_at = datetime.utcnow().isoformat()
            
            batch.failed += 1
            
            if not batch.options.continue_on_error:
                raise
        
        finally:
            batch.in_progress -= 1
            batch.updated_at = datetime.utcnow()
            batch.progress_percentage = (
                (batch.completed + batch.failed) / batch.total_videos * 100
            )
    
    def get_batch_status(self, batch_id: str) -> BatchTranscribeResponseDTO:
        """Retorna status atual do batch."""
        batch = self._batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        return BatchTranscribeResponseDTO(
            batch_id=batch.batch_id,
            status=batch.status,
            total_videos=batch.total_videos,
            completed=batch.completed,
            failed=batch.failed,
            in_progress=batch.in_progress,
            progress_percentage=batch.progress_percentage,
            results=batch.results,
            estimated_completion=self._estimate_completion(batch),
            created_at=batch.created_at.isoformat(),
            updated_at=batch.updated_at.isoformat(),
            completed_at=batch.completed_at.isoformat() if batch.completed_at else None
        )
    
    def _estimate_completion(self, batch: BatchState) -> Optional[str]:
        """Estima tempo de conclusão baseado no progresso."""
        if batch.status == "completed":
            return None
        
        completed_count = batch.completed + batch.failed
        if completed_count == 0:
            return None
        
        elapsed = (datetime.utcnow() - batch.created_at).total_seconds()
        avg_time_per_video = elapsed / completed_count
        remaining_videos = batch.total_videos - completed_count
        estimated_seconds = avg_time_per_video * remaining_videos
        
        estimated_time = datetime.utcnow() + timedelta(seconds=estimated_seconds)
        return estimated_time.isoformat()
```

### 3. Route Implementation

```python
# src/presentation/api/routes/batch.py
from fastapi import APIRouter, Depends, BackgroundTasks
from src.application.dtos import BatchTranscribeRequestDTO, BatchTranscribeResponseDTO

router = APIRouter(prefix="/api/v1/transcribe/batch", tags=["Batch"])

@router.post("", response_model=BatchTranscribeResponseDTO)
@limiter.limit("1/minute")  # Max 1 batch por minuto
async def create_batch_transcription(
    request: Request,
    request_dto: BatchTranscribeRequestDTO,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    use_case: TranscribeYouTubeVideoUseCase = Depends(get_transcribe_use_case),
    batch_manager: BatchTranscriptionManager = Depends(get_batch_manager)
):
    """
    Cria um batch de transcrições.
    Processa assincronamente em background.
    """
    # Validar quota do usuário
    total_videos = len(request_dto.videos)
    if current_user.monthly_usage + total_videos > current_user.monthly_quota:
        raise HTTPException(429, "Quota exceeded for batch request")
    
    # Criar batch
    batch_id = await batch_manager.create_batch(
        videos=request_dto.videos,
        options=request_dto.options,
        user_id=current_user.id
    )
    
    # Processar em background
    background_tasks.add_task(
        batch_manager.process_batch,
        batch_id,
        use_case
    )
    
    # Retornar status inicial
    return batch_manager.get_batch_status(batch_id)

@router.get("/{batch_id}", response_model=BatchTranscribeResponseDTO)
async def get_batch_status(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    batch_manager: BatchTranscriptionManager = Depends(get_batch_manager)
):
    """Obtém status de um batch."""
    return batch_manager.get_batch_status(batch_id)
```

---

## 📊 Métricas

```python
batch_requests_total = Counter('batch_requests_total', ['user_tier'])
batch_videos_processed = Counter('batch_videos_processed', ['status'])
batch_processing_duration = Histogram('batch_processing_duration_seconds')
batch_size_distribution = Histogram('batch_size_videos', buckets=[1, 2, 5, 10])
```

---

## 🧪 Testing

```python
async def test_batch_transcription():
    response = await client.post("/api/v1/transcribe/batch", json={
        "videos": [
            {"youtube_url": "https://youtube.com/watch?v=abc", "language": "en"},
            {"youtube_url": "https://youtube.com/watch?v=def", "language": "pt"}
        ]
    })
    
    assert response.status_code == 202
    batch_id = response.json()["batch_id"]
    
    # Aguardar conclusão
    await asyncio.sleep(60)
    
    # Verificar status
    status_response = await client.get(f"/api/v1/transcribe/batch/{batch_id}")
    assert status_response.json()["status"] == "completed"
    assert status_response.json()["completed"] == 2
```

---

**Próxima Phase**: [Phase 6: Queue System (Celery + Redis)](./06-queue-system.md)
