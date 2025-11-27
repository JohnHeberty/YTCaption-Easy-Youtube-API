# Performance Tuning Guide

Guia completo de otimização de performance para o sistema multi-engine TTS.

---

## 📋 Índice

1. [Quick Wins](#quick-wins)
2. [GPU Optimization](#gpu-optimization)
3. [CPU Fallback](#cpu-fallback)
4. [Cache Strategies](#cache-strategies)
5. [Profiling](#profiling)
6. [Benchmarking](#benchmarking)

---

## ⚡ Quick Wins

### 1. Use GPU Sempre Que Possível

```python
# ❌ Forçar CPU (LENTO)
settings.tts_engines['xtts']['fallback_to_cpu'] = False
os.environ['CUDA_VISIBLE_DEVICES'] = ''

# ✅ Usar GPU (RÁPIDO)
settings.tts_engines['xtts']['device'] = 'cuda:0'
settings.tts_engines['f5tts']['device'] = 'cuda:0'
```

**Ganho**: ~10-20x mais rápido

### 2. Cache de Voice Profiles

```python
# ❌ Reprocessar a cada request
voice = await processor.process_voice_upload(audio_bytes)

# ✅ Usar cache (Redis)
voice_id = await processor.save_voice_profile(audio_bytes)
# Reusar voice_id nas próximas chamadas
result = await processor.process_tts(text, voice_id=voice_id)
```

**Ganho**: ~5-10s economizados por request

### 3. Pré-carregamento de Modelos

```python
# ❌ Lazy loading (lento na primeira chamada)
processor = MultiEngineTTSProcessor()

# ✅ Pré-carregar engines na inicialização
@app.on_event("startup")
async def startup():
    # Force load
    processor.get_engine('xtts')
    processor.get_engine('f5tts')
```

**Ganho**: ~30-60s economizados na primeira request

---

## 🎮 GPU Optimization

### 1. VRAM Management

**Monitorar uso:**
```python
import torch

def get_gpu_memory():
    if torch.cuda.is_available():
        return {
            'allocated': torch.cuda.memory_allocated() / 1024**3,  # GB
            'reserved': torch.cuda.memory_reserved() / 1024**3,
            'free': torch.cuda.mem_get_info()[0] / 1024**3
        }
```

**Limpar cache quando necessário:**
```python
import gc

def clear_gpu_cache():
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
    gc.collect()
```

### 2. Otimizar Batch Size

```python
# F5-TTS (usa mais VRAM)
settings.tts_engines['f5tts']['batch_size'] = 1  # Se VRAM < 12GB
settings.tts_engines['f5tts']['batch_size'] = 2  # Se VRAM >= 12GB

# XTTS (mais eficiente)
settings.tts_engines['xtts']['batch_size'] = 4
```

### 3. FP16 (Half Precision)

```python
# ❌ FP32 (mais VRAM)
model = load_model().to('cuda')

# ✅ FP16 (metade da VRAM, ~mesma qualidade)
model = load_model().to('cuda').half()
```

**Ganho**: ~50% menos VRAM, ~10-20% mais rápido

### 4. Multi-GPU

```python
# docker-compose.yml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          device_ids: ['0', '1']  # GPUs 0 e 1
          capabilities: [gpu]

# app/config.py
settings.tts_engines = {
    'xtts': {'device': 'cuda:0'},
    'f5tts': {'device': 'cuda:1'}
}
```

**Ganho**: 2x throughput (processar 2 jobs simultaneamente)

---

## 💻 CPU Fallback

### 1. Quando Usar

- **GPU indisponível** (no CUDA, VRAM insuficiente)
- **Jobs de baixa prioridade** (batch processing)
- **Textos curtos** (< 50 caracteres, overhead de GPU não compensa)

### 2. Otimizações CPU

```python
# Usar todas as threads disponíveis
import torch
torch.set_num_threads(os.cpu_count())

# ONNXRuntime (mais rápido em CPU)
import onnxruntime as ort
ort.set_default_logger_severity(3)  # Desabilitar warnings
providers = ['CPUExecutionProvider']
```

### 3. Comparação de Performance

| Métrica | GPU (RTX 3090) | CPU (32 cores) | Diferença |
|---------|----------------|----------------|-----------|
| RTF (XTTS) | 0.08 | 1.2 | **15x mais lento** |
| RTF (F5-TTS) | 0.12 | 2.5 | **20x mais lento** |
| VRAM/RAM | 6GB | 12GB | 2x mais RAM |
| Latência | 2s | 30s | **15x mais lento** |

**Recomendação**: Usar CPU apenas como fallback de emergência.

---

## 🗂️ Cache Strategies

### 1. Voice Profile Cache (Redis)

```python
# app/redis_store.py
class VoiceProfileCache:
    def __init__(self, ttl=2592000):  # 30 dias
        self.ttl = ttl
    
    async def get(self, voice_id: str):
        """Cache hit: ~5ms, Cache miss: ~5000ms"""
        data = await redis.get(f"voice:{voice_id}")
        if data:
            return pickle.loads(data)
        return None
    
    async def set(self, voice_id: str, embeddings):
        await redis.setex(
            f"voice:{voice_id}",
            self.ttl,
            pickle.dumps(embeddings)
        )
```

**Ganho**: ~5-10s por request (evita reprocessar audio de referência)

### 2. Model Cache (Disk)

```bash
# Pré-baixar modelos
export HF_HOME=/mnt/ssd/models/huggingface
export TTS_HOME=/mnt/ssd/models/coqui

# Primeira vez (download)
python -c "from app.engines.factory import TTSEngineFactory; factory = TTSEngineFactory(); factory.get_engine('xtts'); factory.get_engine('f5tts')"

# Próximas vezes (carrega do cache)
# 30-60s mais rápido
```

### 3. HTTP Cache (Outputs)

```nginx
# nginx.conf
location /outputs/ {
    alias /var/www/outputs/;
    expires 7d;  # Cache de 7 dias
    add_header Cache-Control "public, immutable";
    
    # Compressão
    gzip on;
    gzip_types audio/wav audio/mpeg;
}
```

**Ganho**: Reduz largura de banda em ~50%

---

## 🔬 Profiling

### 1. cProfile (CPU)

```python
import cProfile
import pstats

# Profiling
profiler = cProfile.Profile()
profiler.enable()

result = await processor.process_tts(text, voice_id)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 funções
```

**Output:**
```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.001    0.001   10.234   10.234 processor.py:45(process_tts)
        1    8.456    8.456    8.456    8.456 xtts_engine.py:78(synthesize)
       10    1.234    0.123    1.234    0.123 torch/nn/functional.py:2345(conv1d)
```

### 2. NVIDIA Profiler (GPU)

```bash
# Instalar
pip install nvidia-pyprof

# Profiling
nsys profile -o profile.qdrep python run.py

# Visualizar
nsys-ui profile.qdrep
```

**Métricas:**
- Kernel launch overhead
- Memory transfer time (CPU → GPU)
- Compute time
- Memory bandwidth utilization

### 3. Line Profiler

```python
# pip install line_profiler

from line_profiler import LineProfiler

lp = LineProfiler()
lp.add_function(processor.process_tts)
lp.enable()

result = await processor.process_tts(text, voice_id)

lp.disable()
lp.print_stats()
```

**Output:**
```
Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
    45         1        100.0    100.0      0.0      engine = self.get_engine(tts_engine)
    46         1    8456000.0 8456000.0     82.6      audio = await engine.synthesize(...)
    47         1    1780000.0 1780000.0     17.4      audio = await self.normalize(audio)
```

---

## 📊 Benchmarking

### 1. RTF (Real-Time Factor)

```python
import time

def measure_rtf(audio_duration: float, processing_time: float) -> float:
    """
    RTF < 1.0 = Mais rápido que real-time (bom)
    RTF > 1.0 = Mais lento que real-time (ruim)
    """
    return processing_time / audio_duration

# Exemplo
start = time.time()
audio = await engine.synthesize(text, voice_id)
processing_time = time.time() - start

audio_duration = len(audio) / 24000  # 24kHz
rtf = measure_rtf(audio_duration, processing_time)

print(f"RTF: {rtf:.2f} ({'✅ FAST' if rtf < 1.0 else '⚠️ SLOW'})")
```

### 2. Usar Framework de Benchmarks

```bash
cd services/audio-voice/benchmarks

# Executar benchmarks PT-BR
python run_benchmark.py \
  --engines xtts f5tts \
  --dataset dataset_ptbr.json \
  --voices all \
  --output results/

# Analisar resultados
python analyze_results.py results/
```

**Output:**
```
📊 BENCHMARK RESULTS
════════════════════════════════════════

Engine: XTTS
  RTF (mean): 0.08 ± 0.02
  Quality: 4.2/5.0
  Success: 98%

Engine: F5-TTS
  RTF (mean): 0.12 ± 0.03
  Quality: 4.5/5.0
  Success: 95%

Recommendation: Use XTTS for speed, F5-TTS for quality
```

### 3. Load Testing (Locust)

```python
# locustfile.py
from locust import HttpUser, task, between

class TTSUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def tts_request(self):
        self.client.post("/tts/synthesize", json={
            "text": "Olá, este é um teste de carga.",
            "tts_engine": "xtts",
            "voice_id": "voice_123"
        })

# Executar
locust -f locustfile.py --host=http://localhost:8000
```

**Métricas:**
- Requests/s
- Latência (p50, p95, p99)
- Taxa de erro
- Throughput

---

## 🎯 Performance Targets

### Latência (P95)

| Engine | Target | Aceitável | Inaceitável |
|--------|--------|-----------|-------------|
| XTTS | < 3s | < 5s | > 10s |
| F5-TTS | < 5s | < 8s | > 15s |

### RTF (Real-Time Factor)

| Cenário | Target | Aceitável | Inaceitável |
|---------|--------|-----------|-------------|
| GPU | < 0.2 | < 0.5 | > 1.0 |
| CPU | < 2.0 | < 5.0 | > 10.0 |

### Throughput

| Hardware | Target | Aceitável |
|----------|--------|-----------|
| 1x RTX 3090 | 50 req/min | 30 req/min |
| 2x RTX 3090 | 100 req/min | 60 req/min |
| CPU (32 cores) | 5 req/min | 2 req/min |

---

## 🔧 Troubleshooting

### Problema: Alto RTF (> 1.0)

**Causas:**
- CPU em vez de GPU
- VRAM insuficiente (swapping)
- Modelo não otimizado

**Soluções:**
```bash
# Verificar GPU
nvidia-smi

# Limpar cache CUDA
python -c "import torch; torch.cuda.empty_cache()"

# Reduzir batch size
# config.py: batch_size = 1
```

### Problema: CUDA Out of Memory

**Causas:**
- Batch size muito grande
- Múltiplos modelos carregados simultaneamente
- Memory leak

**Soluções:**
```python
# Reduzir batch size
settings.tts_engines['f5tts']['batch_size'] = 1

# Limpar cache após cada job
torch.cuda.empty_cache()

# Usar FP16
model.half()
```

### Problema: Latência Alta (> 10s)

**Causas:**
- Lazy loading de modelos
- Voice profile não cacheado
- I/O lento (HDD em vez de SSD)

**Soluções:**
```python
# Pré-carregar modelos
@app.on_event("startup")
async def startup():
    processor.get_engine('xtts')
    processor.get_engine('f5tts')

# Usar Redis para cache
await cache.set(voice_id, embeddings)

# Migrar para SSD
export HF_HOME=/mnt/nvme/models
```

---

## 📚 Recursos Adicionais

- [DEPLOYMENT.md](DEPLOYMENT.md) - Deploy em produção
- [MIGRATION.md](MIGRATION.md) - Migração multi-engine
- [benchmarks/README.md](../benchmarks/README.md) - Framework de benchmarks

---

**Performance tuning validado em produção** ✅
