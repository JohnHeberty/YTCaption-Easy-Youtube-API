# 🧪 Guia de Testes - v2.0

Guia completo para testar todas as otimizações implementadas na versão 2.0.

---

## 📋 Índice

1. [Preparação](#preparação)
2. [Teste 1: Cache de Modelos Whisper](#teste-1-cache-de-modelos-whisper)
3. [Teste 2: Cache de Transcrições](#teste-2-cache-de-transcrições)
4. [Teste 3: Validação de Áudio](#teste-3-validação-de-áudio)
5. [Teste 4: Limpeza Automática](#teste-4-limpeza-automática)
6. [Teste 5: Endpoints de Métricas](#teste-5-endpoints-de-métricas)
7. [Teste 6: FFmpeg Otimizado](#teste-6-ffmpeg-otimizado)
8. [Teste de Carga](#teste-de-carga)

---

## Preparação

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar settings

Editar `.env` ou `settings.py`:

```bash
# Cache de modelos
MODEL_CACHE_TIMEOUT_MINUTES=30

# Cache de transcrições
ENABLE_TRANSCRIPTION_CACHE=true
CACHE_MAX_SIZE=100
CACHE_TTL_HOURS=24

# Validação de áudio
ENABLE_AUDIO_VALIDATION=true

# Cleanup automático
ENABLE_AUTO_CLEANUP=true
CLEANUP_INTERVAL_MINUTES=30
MAX_TEMP_AGE_HOURS=24

# FFmpeg otimizado
ENABLE_FFMPEG_HW_ACCEL=true
```

### 3. Iniciar servidor

```bash
# Modo desenvolvimento
uvicorn src.presentation.api.main:app --reload

# Ou via Makefile
make run
```

---

## Teste 1: Cache de Modelos Whisper

**Objetivo**: Verificar que modelos Whisper são carregados uma vez e reutilizados.

### Procedimento

1. **Primeira requisição** (modelo não está em cache):
```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "en"
  }'
```

2. **Segunda requisição** (mesmo modelo):
```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=OUTRO_VIDEO",
    "language": "en"
  }'
```

3. **Verificar métricas**:
```bash
curl "http://localhost:8000/metrics"
```

### ✅ Resultado Esperado

- **Primeira requisição**: Logs mostram `🔄 Loading Whisper model: base` (demora 5-30s)
- **Segunda requisição**: Logs mostram `✅ Model 'base' loaded from cache` (instantâneo)
- **Métricas**: 
  ```json
  "model_cache": {
    "cache_size": 1,
    "cached_models": ["base"],
    "total_loads": 1,
    "cache_hits": 1,
    "cache_misses": 0
  }
  ```

---

## Teste 2: Cache de Transcrições

**Objetivo**: Verificar que transcrições são cacheadas e reutilizadas.

### Procedimento

1. **Primeira transcrição**:
```bash
time curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "en"
  }'
```

2. **Segunda transcrição** (mesma URL + idioma):
```bash
time curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "en"
  }'
```

3. **Listar cache**:
```bash
curl "http://localhost:8000/cache/transcriptions"
```

### ✅ Resultado Esperado

- **Primeira requisição**: 
  - Demora ~30-120s (processa tudo)
  - Response: `"cache_hit": false`
  - Logs: `❌ Cache miss for dQw4w9WgXcQ`
  - Logs: `💾 Cached transcription for dQw4w9WgXcQ`

- **Segunda requisição**:
  - Demora <1s (retorna do cache)
  - Response: `"cache_hit": true`
  - Logs: `✅ Cache hit for dQw4w9WgXcQ`

- **Métricas**:
  ```json
  "transcription_cache": {
    "cache_size": 1,
    "total_size_mb": 0.5,
    "hits": 1,
    "misses": 1,
    "hit_rate": 0.5
  }
  ```

---

## Teste 3: Validação de Áudio

**Objetivo**: Verificar que arquivos inválidos são rejeitados antes de processar.

### Procedimento

1. **Áudio válido**:
```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  }'
```

2. **Simular áudio inválido** (criar arquivo corrompido):
```bash
# Criar arquivo de áudio corrompido no temp_dir
echo "FAKE AUDIO" > /tmp/ytcaption/corrupt.mp3
```

### ✅ Resultado Esperado

- **Áudio válido**:
  - Logs: `🔍 Validating audio file...`
  - Logs: `✅ Audio validation passed in 0.5s`
  - Processa normalmente

- **Áudio inválido**:
  - Logs: `🔍 Validating audio file...`
  - Logs: `❌ Invalid audio file: Invalid codec, Missing audio stream`
  - HTTP 400: `{"error": "ValidationError", "message": "Invalid audio file: ..."}`
  - **NÃO** processa com Whisper (economiza recursos)

---

## Teste 4: Limpeza Automática

**Objetivo**: Verificar que arquivos antigos são limpos automaticamente.

### Procedimento

1. **Criar arquivos temporários**:
```bash
# Fazer algumas transcrições
for i in {1..5}; do
  curl -X POST "http://localhost:8000/api/v1/transcribe" \
    -H "Content-Type: application/json" \
    -d '{"youtube_url": "https://www.youtube.com/watch?v=VIDEO_'$i'"}'
done
```

2. **Verificar arquivos criados**:
```bash
ls -lh /tmp/ytcaption/
```

3. **Aguardar intervalo de limpeza** (default: 30 minutos) OU **executar manualmente**:
```bash
curl -X POST "http://localhost:8000/cleanup/run"
```

4. **Verificar estatísticas**:
```bash
curl "http://localhost:8000/metrics" | jq '.file_cleanup'
```

### ✅ Resultado Esperado

- **Após transcrições**:
  - Logs: `📁 Tracking temp file: /tmp/ytcaption/session_ABC/video.mp4`
  
- **Após cleanup**:
  - Logs: `🧹 Starting periodic cleanup...`
  - Logs: `🗑️  Removed 5 old files (125.3 MB freed)`
  - Logs: `📊 Cleanup stats: files_removed=5, space_freed_mb=125.3`
  
- **Métricas**:
  ```json
  "file_cleanup": {
    "total_files_tracked": 5,
    "total_cleanups": 1,
    "last_cleanup": "2024-01-15T10:30:00",
    "files_removed": 5,
    "space_freed_mb": 125.3
  }
  ```

---

## Teste 5: Endpoints de Métricas

**Objetivo**: Verificar novos endpoints de monitoramento.

### Procedimento

1. **Health check**:
```bash
curl "http://localhost:8000/health"
```

2. **Métricas completas**:
```bash
curl "http://localhost:8000/metrics" | jq
```

3. **Listar cache de transcrições**:
```bash
curl "http://localhost:8000/cache/transcriptions" | jq
```

4. **Limpar todos os caches**:
```bash
curl -X POST "http://localhost:8000/cache/clear"
```

5. **Limpar apenas expirados**:
```bash
curl -X POST "http://localhost:8000/cache/cleanup-expired"
```

6. **Executar limpeza manual**:
```bash
curl -X POST "http://localhost:8000/cleanup/run"
```

### ✅ Resultado Esperado

Todos os endpoints retornam JSON válido com informações detalhadas:

```json
{
  "timestamp": "2024-01-15T10:00:00",
  "uptime_seconds": 3600,
  "model_cache": {...},
  "transcription_cache": {...},
  "file_cleanup": {...},
  "ffmpeg": {...},
  "worker_pool": {...}
}
```

---

## Teste 6: FFmpeg Otimizado

**Objetivo**: Verificar detecção de aceleração por hardware.

### Procedimento

1. **Verificar capacidades do FFmpeg**:
```bash
curl "http://localhost:8000/metrics" | jq '.ffmpeg'
```

2. **Logs de inicialização**:
```bash
# Verificar logs ao iniciar servidor
tail -f logs/app.log | grep -i "ffmpeg\|cuda\|nvenc"
```

### ✅ Resultado Esperado

**Com NVIDIA GPU**:
```json
"ffmpeg": {
  "version": "4.4.2",
  "has_hw_acceleration": true,
  "has_cuda": true,
  "has_nvenc": true,
  "has_nvdec": true,
  "has_vaapi": false
}
```

**Logs**:
- `🚀 FFmpeg hardware acceleration detected: CUDA, NVENC, NVDEC`
- `⚡ Conversion will use h264_nvenc encoder`

**Sem GPU**:
```json
"ffmpeg": {
  "version": "4.4.2",
  "has_hw_acceleration": false,
  "has_cuda": false
}
```

---

## Teste de Carga

**Objetivo**: Verificar comportamento sob carga com todas as otimizações.

### Ferramenta: Apache Bench

```bash
# 100 requisições, 10 concorrentes
ab -n 100 -c 10 -T 'application/json' \
  -p request.json \
  http://localhost:8000/api/v1/transcribe
```

**request.json**:
```json
{"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "language": "en"}
```

### Ferramenta: Python Script

```python
import asyncio
import aiohttp
import time

async def transcribe(session, url):
    start = time.time()
    async with session.post(
        "http://localhost:8000/api/v1/transcribe",
        json={"youtube_url": url, "language": "en"}
    ) as resp:
        data = await resp.json()
        elapsed = time.time() - start
        return elapsed, data.get("cache_hit", False)

async def main():
    urls = ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"] * 50
    
    async with aiohttp.ClientSession() as session:
        tasks = [transcribe(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
    
    cache_hits = sum(1 for _, hit in results if hit)
    avg_time = sum(t for t, _ in results) / len(results)
    
    print(f"Total requests: {len(results)}")
    print(f"Cache hits: {cache_hits} ({cache_hits/len(results)*100:.1f}%)")
    print(f"Average time: {avg_time:.2f}s")

asyncio.run(main())
```

### ✅ Resultado Esperado

- **Primeira requisição**: ~60s (processa tudo)
- **Requisições subsequentes**: <1s (cache hit)
- **Cache hit rate**: >95%
- **Sem erros de memória**
- **Sem vazamento de recursos**

---

## 📊 Checklist de Validação

- [ ] ✅ Cache de modelos funciona (logs confirmam reuso)
- [ ] ✅ Cache de transcrições funciona (segunda chamada <1s)
- [ ] ✅ Validação de áudio rejeita arquivos inválidos
- [ ] ✅ Limpeza automática remove arquivos antigos
- [ ] ✅ Endpoint `/metrics` retorna estatísticas
- [ ] ✅ Endpoint `/cache/clear` limpa caches
- [ ] ✅ Endpoint `/cleanup/run` executa limpeza
- [ ] ✅ FFmpeg detecta hardware acceleration (se disponível)
- [ ] ✅ Teste de carga não causa vazamentos
- [ ] ✅ Logs mostram todos os emojis v2.0 (🚀 ✅ 💾 🔍 🧹)

---

## 🐛 Troubleshooting

### Cache não funciona

**Problema**: Segunda requisição não retorna do cache.

**Solução**:
```bash
# Verificar configuração
curl "http://localhost:8000/metrics" | jq '.transcription_cache'

# Deve mostrar:
{
  "enabled": true,
  "cache_size": 1,
  ...
}
```

### Validação não rejeita arquivos

**Problema**: Arquivos inválidos são processados.

**Solução**:
```bash
# Verificar se validação está habilitada
grep ENABLE_AUDIO_VALIDATION .env

# Deve ser:
ENABLE_AUDIO_VALIDATION=true
```

### Cleanup não executa

**Problema**: Arquivos antigos não são removidos.

**Solução**:
```bash
# Executar manualmente
curl -X POST "http://localhost:8000/cleanup/run"

# Verificar logs
tail -f logs/app.log | grep cleanup
```

---

## 📝 Relatório de Teste

Após executar todos os testes, preencher:

```markdown
## Relatório de Testes - v2.0

**Data**: _____/_____/_____
**Ambiente**: Development / Staging / Production
**Sistema**: Windows / Linux / macOS
**Python**: ___.___.___
**FFmpeg**: ___.___.___
**GPU**: Sim / Não (modelo: _____________)

### Resultados

| Teste | Status | Tempo | Observações |
|-------|--------|-------|-------------|
| Cache de Modelos | ✅ / ❌ | ___s | |
| Cache de Transcrições | ✅ / ❌ | ___s | |
| Validação de Áudio | ✅ / ❌ | ___s | |
| Limpeza Automática | ✅ / ❌ | ___s | |
| Endpoints Métricas | ✅ / ❌ | ___s | |
| FFmpeg Otimizado | ✅ / ❌ | ___s | |
| Teste de Carga | ✅ / ❌ | ___s | |

### Métricas de Performance

- **Primeira transcrição**: _____s
- **Segunda transcrição (cache)**: _____s
- **Melhoria**: _____%
- **Cache hit rate**: _____%
- **Memória usada**: _____ MB
- **Arquivos limpos**: _____
- **Espaço liberado**: _____ MB

### Problemas Encontrados

1. _____________________________________
2. _____________________________________

### Recomendações

1. _____________________________________
2. _____________________________________
```

---

**Próximo passo**: [DEPLOYMENT.md](07-DEPLOYMENT.md) para deploy em produção.
