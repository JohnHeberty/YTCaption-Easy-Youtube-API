# 📝 Planejamento: Audio Transcriber Service

## 🎯 Objetivo

Transformar o serviço **audio-normalization** em um serviço de **transcrição de áudio** que:
- Recebe áudio e transcreve para texto
- Mantém a arquitetura assíncrona (Celery + Redis)
- Suporta múltiplos idiomas
- Gera legendas nos formatos: SRT, VTT, TXT
- Cache inteligente por hash do áudio

---

## 📊 Estado Atual vs. Estado Desejado

| Aspecto | Audio Normalization (atual) | Audio Transcriber (desejado) |
|---------|------------------------------|------------------------------|
| **Função** | Normaliza áudio (ruído, volume, mono) | Transcreve áudio para texto |
| **Input** | Arquivo de áudio | Arquivo de áudio |
| **Output** | Áudio normalizado (.opus) | Legendas (SRT/VTT/TXT) |
| **Operações** | Vocal isolation, noise reduction, normalization | Transcrição com Whisper AI |
| **Cache** | Hash do áudio + operações | Hash do áudio + idioma |
| **Porta** | 8001 | **8002** |
| **Redis** | 6380 | **6381** |

---

## 🏗️ Arquitetura do Novo Serviço

```
┌─────────────────────┐
│   FastAPI (8002)    │ ← Upload de áudio
│  /transcribe        │
│  /jobs/{job_id}     │
└──────────┬──────────┘
           │
           ▼
    ┌─────────────┐
    │  Redis      │
    │  (6381)     │
    └──────┬──────┘
           │
           ▼
┌─────────────────────┐
│  Celery Worker      │ ← Transcreve com Whisper
│  + Whisper AI       │
└─────────────────────┘
```

---

## 🔧 Mudanças Necessárias

### 1. **Dependências (requirements.txt)**

```diff
- openunmix==1.3.0
- torch==2.1.0
- torchaudio==2.1.0
- noisereduce==3.0.0
- librosa==0.10.1

+ openai-whisper==20231117
+ faster-whisper==0.10.0  # Alternativa mais rápida
```

**Justificativa:**
- `openai-whisper`: Modelo oficial da OpenAI (preciso, mas lento)
- `faster-whisper`: Implementação otimizada com CTranslate2 (até 4x mais rápido)

**Recomendação:** Usar `faster-whisper` para produção.

---

### 2. **Models (app/models.py)**

#### Mudanças no `Job`:

```python
class Job(BaseModel):
    # Campos existentes
    id: str
    status: JobStatus
    progress: float = 0.0
    input_file: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    # REMOVER (específicos de normalização)
    # ❌ isolate_vocals: bool = False
    # ❌ remove_noise: bool = False
    # ❌ normalize_volume: bool = False
    # ❌ convert_to_mono: bool = False
    
    # ADICIONAR (específicos de transcrição)
    language: str = "auto"  # pt, en, es, auto
    format: str = "srt"     # srt, vtt, txt
    
    # Output
    output_file: Optional[str] = None  # Caminho do arquivo .srt/.vtt/.txt
    transcription_text: Optional[str] = None  # Texto completo da transcrição
    
    # Metadata
    detected_language: Optional[str] = None  # Idioma detectado pelo Whisper
    segments_count: Optional[int] = None     # Número de segmentos transcritos
    audio_duration: Optional[float] = None   # Duração do áudio em segundos
    
    @staticmethod
    def create_new(
        input_file: str,
        language: str = "auto",
        format: str = "srt"
    ) -> "Job":
        """
        Cria novo job de transcrição com ID baseado em hash
        
        Job ID format: {hash_audio}_{language}_{format}
        Ex: abc123def456_pt_srt
        """
        file_hash = calculate_file_hash(input_file)
        job_id = f"{file_hash}_{language}_{format}"
        
        return Job(
            id=job_id,
            status=JobStatus.QUEUED,
            input_file=input_file,
            language=language,
            format=format,
            created_at=datetime.now()
        )
```

#### Nova Request DTO:

```python
class TranscriptionRequest(BaseModel):
    """Request para transcrição de áudio"""
    language: str = "auto"  # pt, en, es, fr, auto
    format: str = "srt"     # srt, vtt, txt
    
    class Config:
        json_schema_extra = {
            "example": {
                "language": "pt",
                "format": "srt"
            }
        }
```

---

### 3. **Processor (app/processor.py)**

#### Nova Classe: `TranscriptionProcessor`

```python
class TranscriptionProcessor:
    """Processador de transcrição usando Whisper"""
    
    def __init__(self, output_dir: str = "./transcriptions"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.job_store = None
        
        # Lazy load do modelo Whisper
        self._model = None
    
    def get_whisper_model(self):
        """Lazy load do Whisper (carrega só quando necessário)"""
        if self._model is None:
            from faster_whisper import WhisperModel
            
            # Usa modelo "base" (74MB) - bom equilíbrio velocidade/precisão
            # Alternativas:
            # - tiny: 39MB, rápido mas menos preciso
            # - small: 244MB, mais preciso
            # - medium: 769MB, muito preciso
            # - large: 1550MB, máxima precisão
            
            self._model = WhisperModel(
                "base",
                device="cpu",  # Use "cuda" se tiver GPU
                compute_type="int8"  # Quantização para economia de memória
            )
            logger.info("✅ Whisper modelo 'base' carregado")
        
        return self._model
    
    def transcribe_audio(self, job: Job) -> Job:
        """
        Transcreve áudio usando Whisper
        
        Etapas:
        1. Carrega modelo Whisper (lazy)
        2. Transcreve áudio com timestamps
        3. Gera arquivo no formato solicitado (SRT/VTT/TXT)
        4. Salva metadados (idioma detectado, duração, etc.)
        """
        try:
            job.status = JobStatus.PROCESSING
            self._update_progress(job, 5.0, "Iniciando transcrição")
            
            # Valida arquivo
            input_path = Path(job.input_file)
            if not input_path.exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {job.input_file}")
            
            # Carrega modelo Whisper
            self._update_progress(job, 10.0, "Carregando modelo Whisper")
            model = self.get_whisper_model()
            
            # Transcreve
            self._update_progress(job, 20.0, "Transcrevendo áudio (pode demorar)")
            
            language = None if job.language == "auto" else job.language
            
            segments, info = model.transcribe(
                str(input_path),
                language=language,
                task="transcribe",  # ou "translate" para traduzir para inglês
                beam_size=5,
                vad_filter=True  # Remove silêncios
            )
            
            # Coleta segmentos
            self._update_progress(job, 60.0, "Processando segmentos")
            segments_list = list(segments)
            
            # Salva metadados
            job.detected_language = info.language
            job.segments_count = len(segments_list)
            job.audio_duration = info.duration
            
            # Gera arquivo no formato solicitado
            self._update_progress(job, 80.0, f"Gerando arquivo {job.format.upper()}")
            
            output_filename = f"{job.id}.{job.format}"
            output_path = self.output_dir / output_filename
            
            if job.format == "srt":
                self._generate_srt(segments_list, output_path)
            elif job.format == "vtt":
                self._generate_vtt(segments_list, output_path)
            else:  # txt
                self._generate_txt(segments_list, output_path)
            
            # Extrai texto completo
            full_text = " ".join(seg.text.strip() for seg in segments_list)
            job.transcription_text = full_text
            
            # Finaliza job
            job.output_file = str(output_path)
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            job.progress = 100.0
            
            self._update_progress(job, 100.0, "Transcrição concluída")
            
            # Remove arquivo de input
            input_path.unlink()
            logger.info(f"Arquivo de entrada removido: {input_path}")
            
            return job
            
        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            
            # Remove input mesmo em caso de erro
            if Path(job.input_file).exists():
                Path(job.input_file).unlink()
            
            return job
    
    def _generate_srt(self, segments, output_path: Path):
        """Gera arquivo SRT (SubRip Subtitle)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, start=1):
                # Índice
                f.write(f"{i}\n")
                
                # Timestamps (formato: 00:00:00,000 --> 00:00:05,000)
                start = self._format_timestamp_srt(segment.start)
                end = self._format_timestamp_srt(segment.end)
                f.write(f"{start} --> {end}\n")
                
                # Texto
                f.write(f"{segment.text.strip()}\n")
                f.write("\n")
    
    def _generate_vtt(self, segments, output_path: Path):
        """Gera arquivo VTT (WebVTT)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            
            for segment in segments:
                # Timestamps (formato: 00:00:00.000 --> 00:00:05.000)
                start = self._format_timestamp_vtt(segment.start)
                end = self._format_timestamp_vtt(segment.end)
                f.write(f"{start} --> {end}\n")
                
                # Texto
                f.write(f"{segment.text.strip()}\n")
                f.write("\n")
    
    def _generate_txt(self, segments, output_path: Path):
        """Gera arquivo TXT (texto puro)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for segment in segments:
                f.write(f"{segment.text.strip()}\n")
    
    def _format_timestamp_srt(self, seconds: float) -> str:
        """Formata timestamp para SRT (00:00:00,000)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _format_timestamp_vtt(self, seconds: float) -> str:
        """Formata timestamp para VTT (00:00:00.000)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    
    def _update_progress(self, job: Job, progress: float, message: str = ""):
        """Atualiza progresso do job"""
        job.progress = min(progress, 99.9)
        if self.job_store:
            self.job_store.update_job(job)
        logger.info(f"Job {job.id}: {progress:.1f}% - {message}")
```

---

### 4. **API Endpoints (app/main.py)**

#### Endpoint Principal: `/transcribe`

```python
@app.post("/transcribe", response_model=Job)
async def create_transcription_job(
    file: UploadFile = File(...),
    language: str = "auto",
    format: str = "srt"
) -> Job:
    """
    Cria job de transcrição de áudio
    
    - **file**: Arquivo de áudio (mp3, wav, m4a, etc.)
    - **language**: Idioma do áudio (pt, en, es, auto)
    - **format**: Formato de saída (srt, vtt, txt)
    
    Sistema de cache:
    - Se mesmo arquivo + idioma + formato já foi transcrito, retorna resultado em cache
    """
    # Salva upload
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Cria job
    new_job = Job.create_new(
        input_file=str(file_path),
        language=language,
        format=format
    )
    
    # Verifica cache
    existing_job = job_store.get_job(new_job.id)
    if existing_job and existing_job.status == JobStatus.COMPLETED:
        return existing_job
    
    # Job novo - submete para Celery
    job_store.save_job(new_job)
    transcribe_audio_task.apply_async(
        args=[new_job.model_dump()],
        task_id=new_job.id
    )
    
    return new_job
```

#### Novo Endpoint: Download de Legendas

```python
@app.get("/jobs/{job_id}/download")
async def download_subtitles(job_id: str):
    """Download do arquivo de legenda (.srt/.vtt/.txt)"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=f"Transcrição não concluída. Status: {job.status}"
        )
    
    file_path = Path(job.output_file)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    # Define media type baseado no formato
    media_types = {
        "srt": "application/x-subrip",
        "vtt": "text/vtt",
        "txt": "text/plain"
    }
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=media_types.get(job.format, "text/plain")
    )
```

#### Novo Endpoint: Texto da Transcrição

```python
@app.get("/jobs/{job_id}/text")
async def get_transcription_text(job_id: str):
    """Retorna texto completo da transcrição (sem timestamps)"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=f"Transcrição não concluída. Status: {job.status}"
        )
    
    return {
        "job_id": job.id,
        "text": job.transcription_text,
        "language": job.detected_language,
        "segments_count": job.segments_count,
        "duration": job.audio_duration
    }
```

---

### 5. **Celery Tasks (app/celery_tasks.py)**

```python
from celery import Task
from .celery_config import celery_app
from .models import Job
from .processor import TranscriptionProcessor
from .redis_store import RedisJobStore
import os

# Instâncias globais
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
job_store = RedisJobStore(redis_url=redis_url)
processor = TranscriptionProcessor()
processor.job_store = job_store


class CallbackTask(Task):
    """Task base com callback de progresso"""
    
    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)
    
    def run(self, *args, **kwargs):
        """Método abstrato implementado"""
        return None


@celery_app.task(bind=True, base=CallbackTask, name="transcribe_audio")
def transcribe_audio_task(self, job_data: dict):
    """
    Task Celery para transcrever áudio
    """
    job = Job(**job_data)
    
    try:
        # Processa transcrição
        result_job = processor.transcribe_audio(job)
        
        # Salva resultado no Redis
        job_store.update_job(result_job)
        
        return result_job.model_dump()
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Erro na task de transcrição: %s", e)
        
        job.status = "failed"
        job.error_message = str(e)
        job_store.update_job(job)
        
        raise
```

---

### 6. **Docker Compose (docker-compose.yml)**

```yaml
version: '3.8'

services:
  api:
    build: .
    container_name: audio-transcriber-api
    ports:
      - "8002:8000"  # Porta diferente do audio-normalization
    environment:
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./app:/app/app
      - ./uploads:/app/uploads
      - ./transcriptions:/app/transcriptions
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    depends_on:
      - redis
    networks:
      - transcriber-network

  celery:
    build: .
    container_name: audio-transcriber-worker
    environment:
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./app:/app/app
      - ./uploads:/app/uploads
      - ./transcriptions:/app/transcriptions
    command: celery -A app.celery_config worker --loglevel=info
    depends_on:
      - redis
    networks:
      - transcriber-network

  redis:
    image: redis:7-alpine
    container_name: audio-transcriber-redis
    ports:
      - "6381:6379"  # Porta diferente do audio-normalization
    networks:
      - transcriber-network

networks:
  transcriber-network:
    driver: bridge
```

---

### 7. **Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema (incluindo ffmpeg para Whisper)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código
COPY . .

# Cria diretórios necessários
RUN mkdir -p /app/uploads /app/transcriptions /app/temp

# Cria usuário não-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 🧪 Testes

### Script de Teste PowerShell

```powershell
# test_transcription.ps1

Write-Host "🧪 Testando Audio Transcriber Service" -ForegroundColor Cyan

# 1. Upload de áudio para transcrição
Write-Host "`n1️⃣ Upload de áudio..." -ForegroundColor Yellow
$audioFile = Get-Item "C:\path\to\audio.mp3"
$form = @{
    file = $audioFile
    language = "pt"
    format = "srt"
}

$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8002/transcribe" -Form $form
$jobId = $response.id

Write-Host "✅ Job criado: $jobId" -ForegroundColor Green
Write-Host "   Status: $($response.status)"
Write-Host "   Idioma: $($response.language)"
Write-Host "   Formato: $($response.format)"

# 2. Aguarda processamento
Write-Host "`n2️⃣ Aguardando transcrição..." -ForegroundColor Yellow
do {
    Start-Sleep -Seconds 5
    $job = Invoke-RestMethod -Uri "http://localhost:8002/jobs/$jobId"
    Write-Host "   Progresso: $($job.progress)% - Status: $($job.status)"
} while ($job.status -ne "completed" -and $job.status -ne "failed")

if ($job.status -eq "completed") {
    Write-Host "`n✅ Transcrição concluída!" -ForegroundColor Green
    Write-Host "   Idioma detectado: $($job.detected_language)"
    Write-Host "   Segmentos: $($job.segments_count)"
    Write-Host "   Duração: $($job.audio_duration)s"
    
    # 3. Download da legenda
    Write-Host "`n3️⃣ Baixando legenda..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "http://localhost:8002/jobs/$jobId/download" -OutFile "subtitle.srt"
    Write-Host "✅ Legenda salva: subtitle.srt" -ForegroundColor Green
    
    # 4. Exibe texto
    Write-Host "`n4️⃣ Texto da transcrição:" -ForegroundColor Yellow
    $text = Invoke-RestMethod -Uri "http://localhost:8002/jobs/$jobId/text"
    Write-Host $text.text -ForegroundColor White
    
} else {
    Write-Host "`n❌ Transcrição falhou: $($job.error_message)" -ForegroundColor Red
}

Write-Host "`n✅ Teste concluído!" -ForegroundColor Cyan
```

---

## 📋 Checklist de Implementação

### Fase 1: Setup Básico
- [ ] Atualizar `requirements.txt` com `faster-whisper`
- [ ] Atualizar portas no `docker-compose.yml` (8002, 6381)
- [ ] Atualizar `README.md` com nova descrição
- [ ] Criar diretório `./transcriptions`

### Fase 2: Models & Core
- [ ] Modificar `app/models.py`:
  - [ ] Remover campos de normalização
  - [ ] Adicionar campos de transcrição
  - [ ] Atualizar `Job.create_new()`
- [ ] Criar `app/processor.py` (TranscriptionProcessor)
  - [ ] Implementar `transcribe_audio()`
  - [ ] Implementar `_generate_srt()`
  - [ ] Implementar `_generate_vtt()`
  - [ ] Implementar `_generate_txt()`

### Fase 3: API
- [ ] Atualizar `app/main.py`:
  - [ ] Renomear endpoint `/normalize` → `/transcribe`
  - [ ] Atualizar parâmetros (language, format)
  - [ ] Modificar `/jobs/{job_id}/download` para legendas
  - [ ] Criar endpoint `/jobs/{job_id}/text`
  - [ ] Atualizar health check

### Fase 4: Celery
- [ ] Atualizar `app/celery_tasks.py`:
  - [ ] Renomear task para `transcribe_audio_task`
  - [ ] Injetar `TranscriptionProcessor`

### Fase 5: Docker
- [ ] Rebuild containers: `docker compose build --no-cache`
- [ ] Testar inicialização: `docker compose up -d`
- [ ] Verificar logs: `docker compose logs -f`

### Fase 6: Testes
- [ ] Criar `test_transcription.ps1`
- [ ] Testar com áudio em português
- [ ] Testar com áudio em inglês
- [ ] Testar formatos: SRT, VTT, TXT
- [ ] Testar sistema de cache

---

## ⚡ Performance Estimada

| Modelo Whisper | Tamanho | Precisão | Velocidade (CPU) |
|----------------|---------|----------|------------------|
| tiny | 39 MB | ⭐⭐ | 32x tempo real |
| base | 74 MB | ⭐⭐⭐ | 16x tempo real |
| small | 244 MB | ⭐⭐⭐⭐ | 6x tempo real |
| medium | 769 MB | ⭐⭐⭐⭐⭐ | 2x tempo real |
| large | 1.5 GB | ⭐⭐⭐⭐⭐ | 1x tempo real |

**Recomendação:** Modelo `base` (74MB) para produção - bom equilíbrio.

**Exemplo:** Áudio de 5 minutos = ~18 segundos de processamento com modelo `base`.

---

## 🔐 Portas do Sistema Completo

| Serviço | Porta API | Porta Redis |
|---------|-----------|-------------|
| video-downloader | 8000 | 6379 |
| audio-normalization | 8001 | 6380 |
| **audio-transcriber** | **8002** | **6381** |

---

## 📚 Documentação Complementar

- **Whisper**: https://github.com/openai/whisper
- **Faster Whisper**: https://github.com/guillaumekln/faster-whisper
- **SRT Format**: https://en.wikipedia.org/wiki/SubRip
- **WebVTT Format**: https://www.w3.org/TR/webvtt1/

---

## 🎯 Próximos Passos

1. **Revisar planejamento** com você
2. **Confirmar decisões**:
   - Modelo Whisper (base recomendado)
   - Formatos de saída (SRT, VTT, TXT confirmados?)
   - Idiomas suportados (lista completa?)
3. **Iniciar implementação** seguindo checklist

---

**Status:** 📋 Planejamento completo - aguardando aprovação para implementação
