# 🔧 Guia de Integração das Otimizações

Este guia mostra como integrar todas as otimizações implementadas aos endpoints existentes da API.

---

## 📋 Passo a Passo de Integração

### 1. Atualizar Dependências (main.py)

**Arquivo**: `src/presentation/api/main.py`

Adicionar imports das novas funcionalidades:

```python
# Importar novos módulos
from src.infrastructure.whisper.model_cache import get_model_cache
from src.infrastructure.storage.file_cleanup_manager import FileCleanupManager
from src.infrastructure.cache import get_transcription_cache
from src.infrastructure.validators import AudioValidator
from src.infrastructure.utils import get_ffmpeg_optimizer

# Variáveis globais
model_cache = None
file_cleanup_manager = None
transcription_cache = None
audio_validator = None
ffmpeg_optimizer = None
```

### 2. Inicializar Serviços no Startup

Adicionar no `lifespan` do `main.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação."""
    global model_cache, file_cleanup_manager, transcription_cache, audio_validator, ffmpeg_optimizer
    
    # Startup
    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version} (OPTIMIZED)")
    
    # 1. Inicializar cache de modelos Whisper
    logger.info("Initializing Whisper model cache...")
    model_cache = get_model_cache()
    model_cache.set_unload_timeout(settings.model_cache_timeout_minutes)
    
    # 2. Inicializar cache de transcrições
    if settings.enable_transcription_cache:
        logger.info("Initializing transcription cache...")
        transcription_cache = get_transcription_cache(
            max_size=settings.cache_max_size,
            ttl_hours=settings.cache_ttl_hours
        )
    
    # 3. Inicializar gerenciador de cleanup
    logger.info("Initializing file cleanup manager...")
    file_cleanup_manager = FileCleanupManager(
        base_temp_dir=Path(settings.temp_dir),
        default_ttl_hours=settings.max_temp_age_hours,
        cleanup_interval_minutes=settings.cleanup_interval_minutes
    )
    
    # Iniciar limpeza periódica
    if settings.enable_periodic_cleanup:
        file_cleanup_manager.start_periodic_cleanup()
    
    # 4. Inicializar validador de áudio
    logger.info("Initializing audio validator...")
    audio_validator = AudioValidator()
    
    # 5. Inicializar otimizador FFmpeg
    logger.info("Initializing FFmpeg optimizer...")
    ffmpeg_optimizer = get_ffmpeg_optimizer()
    capabilities = ffmpeg_optimizer.get_capabilities()
    logger.info(f"FFmpeg capabilities: hw_accel={capabilities.has_hw_acceleration}")
    
    # [Resto do startup existente...]
    
    logger.info("=" * 60)
    logger.info("🚀 Application startup complete (OPTIMIZED)!")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("Shutting down application...")
    
    # 1. Parar cleanup periódico
    if file_cleanup_manager:
        await file_cleanup_manager.stop_periodic_cleanup()
        logger.info("File cleanup manager stopped")
    
    # 2. Limpar cache de modelos
    if model_cache:
        model_cache.clear_all()
        logger.info("Model cache cleared")
    
    # 3. Limpar cache de transcrições
    if transcription_cache:
        stats = transcription_cache.get_stats()
        logger.info(f"Transcription cache stats: {stats}")
        transcription_cache.clear()
    
    # [Resto do shutdown existente...]
    
    logger.info("=" * 60)
```

---

### 3. Adicionar Funções de Dependência

**Arquivo**: `src/presentation/api/dependencies.py`

```python
def get_audio_validator() -> AudioValidator:
    """Retorna validador de áudio."""
    from src.presentation.api.main import audio_validator
    if audio_validator is None:
        raise RuntimeError("Audio validator not initialized")
    return audio_validator


def get_transcription_cache_service():
    """Retorna cache de transcrições."""
    from src.presentation.api.main import transcription_cache
    if settings.enable_transcription_cache and transcription_cache:
        return transcription_cache
    return None


def get_file_cleanup_manager_service():
    """Retorna gerenciador de cleanup."""
    from src.presentation.api.main import file_cleanup_manager
    return file_cleanup_manager
```

---

### 4. Atualizar Endpoint de Transcrição

**Arquivo**: `src/presentation/api/routes/transcription.py`

#### 4.1 - Adicionar Validação Antecipada

```python
from src.presentation.api.dependencies import get_audio_validator

@router.post("/transcribe")
async def transcribe_video(
    # ... parâmetros existentes ...
    validator: AudioValidator = Depends(get_audio_validator)
):
    """Transcreve vídeo com validação antecipada."""
    
    try:
        # 1. VALIDAR ARQUIVO ANTES DE PROCESSAR
        logger.info("Validating audio file...")
        metadata = validator.validate_file(video_file.file_path, strict=True)
        
        if not metadata.is_valid:
            logger.warning(f"Audio validation failed: {metadata.validation_errors}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidAudioFile",
                    "message": "Audio file validation failed",
                    "validation_errors": metadata.validation_errors,
                    "file_info": {
                        "duration": metadata.duration_formatted,
                        "format": metadata.format_name,
                        "codec": metadata.codec_name,
                        "size_mb": metadata.file_size_mb
                    }
                }
            )
        
        logger.info(
            f"Audio validation passed: {metadata.duration_formatted}, "
            f"{metadata.file_size_mb:.2f}MB, {metadata.codec_name}"
        )
        
        # 2. ESTIMAR TEMPO DE PROCESSAMENTO
        min_time, max_time = validator.estimate_processing_time(
            metadata,
            model_name=model or settings.whisper_model,
            device=settings.whisper_device
        )
        
        logger.info(f"Estimated processing time: {min_time:.1f}s - {max_time:.1f}s")
        
        # 3. VERIFICAR CACHE DE TRANSCRIÇÃO
        cache = get_transcription_cache_service()
        
        if cache:
            file_hash = cache.compute_file_hash(video_file.file_path)
            cached_result = cache.get(
                file_hash,
                model or settings.whisper_model,
                language or "auto"
            )
            
            if cached_result:
                logger.info(f"🎯 Cache HIT! Returning cached transcription")
                return {
                    "cached": True,
                    "transcription": cached_result,
                    "processing_time": 0.0
                }
        
        # 4. PROCESSAR TRANSCRIÇÃO (código existente)
        start_time = time.time()
        
        # [Código de transcrição existente...]
        
        processing_time = time.time() - start_time
        
        # 5. CACHEAR RESULTADO
        if cache:
            cache.put(
                file_hash,
                transcription_data,
                model or settings.whisper_model,
                language or "auto",
                metadata.file_size_bytes
            )
            logger.info("Transcription cached for future requests")
        
        return {
            "cached": False,
            "transcription": transcription_data,
            "processing_time": processing_time,
            "estimated_time": {"min": min_time, "max": max_time}
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### 5. Adicionar Endpoint de Métricas

**Arquivo**: `src/presentation/api/routes/system.py`

```python
@router.get("/metrics")
async def get_metrics():
    """
    Retorna métricas do sistema.
    
    **Informações retornadas**:
    - Cache de modelos Whisper
    - Cache de transcrições
    - Gerenciador de cleanup
    - FFmpeg capabilities
    """
    from src.presentation.api.main import (
        model_cache,
        transcription_cache,
        file_cleanup_manager,
        ffmpeg_optimizer
    )
    
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "model_cache": None,
        "transcription_cache": None,
        "file_cleanup": None,
        "ffmpeg": None
    }
    
    # Cache de modelos
    if model_cache:
        metrics["model_cache"] = model_cache.get_cache_stats()
    
    # Cache de transcrições
    if transcription_cache:
        metrics["transcription_cache"] = transcription_cache.get_stats()
    
    # Cleanup manager
    if file_cleanup_manager:
        metrics["file_cleanup"] = file_cleanup_manager.get_stats()
    
    # FFmpeg
    if ffmpeg_optimizer:
        capabilities = ffmpeg_optimizer.get_capabilities()
        metrics["ffmpeg"] = {
            "version": capabilities.version,
            "has_hw_acceleration": capabilities.has_hw_acceleration,
            "has_cuda": capabilities.has_cuda,
            "has_nvenc": capabilities.has_nvenc,
            "has_vaapi": capabilities.has_vaapi
        }
    
    return metrics


@router.post("/cache/clear")
async def clear_caches():
    """Limpa todos os caches."""
    from src.presentation.api.main import model_cache, transcription_cache
    
    results = {}
    
    # Limpar cache de modelos
    if model_cache:
        model_cache.clear_all()
        results["model_cache"] = "cleared"
    
    # Limpar cache de transcrições
    if transcription_cache:
        transcription_cache.clear()
        results["transcription_cache"] = "cleared"
    
    logger.info("All caches cleared")
    return {"message": "Caches cleared", "results": results}


@router.post("/cleanup/run")
async def run_cleanup():
    """Executa limpeza manual de arquivos antigos."""
    from src.presentation.api.main import file_cleanup_manager
    
    if not file_cleanup_manager:
        raise HTTPException(status_code=503, detail="Cleanup manager not initialized")
    
    logger.info("Running manual cleanup...")
    stats = await file_cleanup_manager.cleanup_old_files()
    
    return {
        "message": "Cleanup completed",
        "stats": stats
    }
```

---

### 6. Atualizar Serviço de Transcrição

**Arquivo**: `src/infrastructure/whisper/transcription_service.py`

O arquivo já foi atualizado para usar o cache global de modelos. Não precisa de mais alterações!

---

### 7. Variáveis de Ambiente

**Arquivo**: `.env`

Adicionar as novas configurações:

```env
# ============================================
# OTIMIZAÇÕES v2.0
# ============================================

# Cache de Transcrições
ENABLE_TRANSCRIPTION_CACHE=true
CACHE_MAX_SIZE=100              # Máximo de transcrições em cache
CACHE_TTL_HOURS=24              # Tempo de vida do cache em horas

# Cache de Modelos Whisper
MODEL_CACHE_TIMEOUT_MINUTES=30  # Descarregar modelos não usados após 30min

# Otimização FFmpeg
ENABLE_FFMPEG_HW_ACCEL=true     # Usar aceleração por hardware (CUDA/NVENC)

# Limpeza Automática de Arquivos
ENABLE_PERIODIC_CLEANUP=true    # Ativar limpeza periódica
CLEANUP_INTERVAL_MINUTES=30     # Intervalo de limpeza
```

---

## 🧪 Testes

### Teste 1: Cache de Modelos

```bash
# Primeira requisição (carrega modelo)
curl -X POST http://localhost:8000/transcribe \
  -F "youtube_url=https://www.youtube.com/watch?v=VIDEO_ID" \
  -F "model=base"
# Resposta: ~10s

# Segunda requisição (usa cache)
curl -X POST http://localhost:8000/transcribe \
  -F "youtube_url=https://www.youtube.com/watch?v=OUTRO_VIDEO" \
  -F "model=base"
# Resposta: ~0.5s (modelo já carregado!)
```

### Teste 2: Cache de Transcrições

```bash
# Primeira transcrição
curl -X POST http://localhost:8000/transcribe \
  -F "youtube_url=https://www.youtube.com/watch?v=VIDEO_ID"
# Resposta: {"cached": false, "processing_time": 15.3}

# Segunda transcrição do MESMO vídeo
curl -X POST http://localhost:8000/transcribe \
  -F "youtube_url=https://www.youtube.com/watch?v=VIDEO_ID"
# Resposta: {"cached": true, "processing_time": 0.0}
```

### Teste 3: Validação Antecipada

```bash
# Upload de arquivo inválido
curl -X POST http://localhost:8000/transcribe \
  -F "file=@corrupted.mp4"
# Resposta: HTTP 400 {"error": "InvalidAudioFile", "validation_errors": [...]}
```

### Teste 4: Métricas

```bash
# Ver métricas do sistema
curl http://localhost:8000/metrics

# Resposta:
{
  "model_cache": {
    "cache_size": 2,
    "total_usage_count": 45,
    "models": {...}
  },
  "transcription_cache": {
    "hit_rate_percent": 68.5,
    "cache_size": 23,
    "total_size_mb": 145.2
  },
  "file_cleanup": {
    "tracked_files": 5,
    "total_size_mb": 23.4
  }
}
```

---

## ✅ Checklist de Integração

- [ ] Atualizar `main.py` com inicialização dos novos serviços
- [ ] Adicionar funções de dependência em `dependencies.py`
- [ ] Atualizar endpoint `/transcribe` com validação e cache
- [ ] Adicionar endpoint `/metrics` em `system.py`
- [ ] Adicionar endpoint `/cache/clear` em `system.py`
- [ ] Adicionar endpoint `/cleanup/run` em `system.py`
- [ ] Atualizar arquivo `.env` com novas variáveis
- [ ] Testar cache de modelos
- [ ] Testar cache de transcrições
- [ ] Testar validação antecipada
- [ ] Testar endpoint de métricas
- [ ] Documentar API atualizada

---

## 🚀 Deploy

### Desenvolvimento

```bash
# Instalar dependências (se houver novas)
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com configurações de otimização

# Rodar servidor
python -m src.presentation.api.main
```

### Produção (Docker)

```bash
# Build com otimizações
docker-compose build

# Rodar
docker-compose up -d

# Ver logs
docker-compose logs -f

# Ver métricas
curl http://localhost:8000/metrics
```

---

## 📊 Monitoramento

### Dashboards Recomendados

1. **Cache Hit Rate**: Monitorar efetividade do cache
2. **Model Load Time**: Tempo de carregamento de modelos
3. **Disk Usage**: Uso de disco por arquivos temporários
4. **Processing Time**: Tempo médio de processamento

### Alertas Sugeridos

- Cache hit rate < 30% (cache pequeno demais)
- Disk usage > 80% (cleanup não está funcionando)
- Model load time > 15s (problema de I/O)
- Processing time > 2x estimado (problema de performance)

---

## 🐛 Troubleshooting

### Cache não está funcionando

```python
# Verificar se cache está habilitado
curl http://localhost:8000/metrics | jq '.transcription_cache'

# Limpar cache manualmente
curl -X POST http://localhost:8000/cache/clear
```

### Arquivos temporários acumulando

```python
# Executar cleanup manual
curl -X POST http://localhost:8000/cleanup/run

# Verificar status
curl http://localhost:8000/metrics | jq '.file_cleanup'
```

### Modelo não está sendo cacheado

```python
# Verificar cache de modelos
curl http://localhost:8000/metrics | jq '.model_cache'

# Reiniciar servidor para resetar cache
docker-compose restart
```

---

## 📚 Recursos Adicionais

- [Relatório de Otimizações](./OPTIMIZATION-REPORT.md)
- [Documentação da API](./04-API-USAGE.md)
- [Guia de Deploy](./07-DEPLOYMENT.md)

---

**Última atualização**: 21/10/2025  
**Versão**: 2.0 (Optimized)
