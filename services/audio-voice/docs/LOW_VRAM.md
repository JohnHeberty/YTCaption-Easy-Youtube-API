# LOW VRAM Mode - Implementation Guide

Guia de implementação do modo LOW_VRAM para economizar memória da GPU.

---

## 🎯 Objetivo

Permitir que o sistema rode em GPUs com pouca VRAM (4GB-6GB) através de:
1. **Carregamento sob demanda**: Modelo só é carregado quando necessário
2. **Descarregamento imediato**: Modelo é removido da VRAM após uso
3. **Pipeline sequencial**: TTS → RVC (um de cada vez)

---

## 📊 Comparação de VRAM

### Modo NORMAL (LOW_VRAM=false)
```
GPU VRAM Usage:
├─ XTTS model: ~2-4GB (sempre carregado)
├─ F5-TTS model: ~3-8GB (sempre carregado)
├─ RVC model: ~2-4GB (sempre carregado)
└─ Total Peak: ~10-16GB VRAM
```

### Modo LOW VRAM (LOW_VRAM=true)
```
GPU VRAM Usage (sequential):
├─ Step 1: XTTS generates audio
│   └─ VRAM: ~2-4GB
├─ Step 2: Unload XTTS
│   └─ VRAM: ~0GB
├─ Step 3: RVC processes audio
│   └─ VRAM: ~2-4GB
├─ Step 4: Unload RVC
│   └─ VRAM: ~0GB
└─ Total Peak: ~4GB VRAM (vs 16GB)
```

**Economia**: ~70-75% de VRAM

---

## ⚙️ Configuração

### Variável de Ambiente

```bash
# Ativar modo LOW_VRAM
export LOW_VRAM=true

# Desativar (modo normal)
export LOW_VRAM=false
```

### docker-compose.yml

```yaml
services:
  audio-voice:
    environment:
      - LOW_VRAM=true  # Ativar para GPUs pequenas (4-6GB)
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

---

## 🔧 Arquitetura

### Componentes

1. **VRAMManager** (`app/vram_manager.py`)
   - Gerencia carregamento/descarregamento
   - Context manager para uso temporário
   - Cache de modelos (modo normal)
   - Estatísticas de VRAM

2. **Engine Integration**
   - `XttsEngine` adaptado
   - `F5TtsEngine` adaptado
   - Lazy loading de modelos
   - Automatic unloading

3. **RVC Integration**
   - `RvcClient` adaptado
   - Load modelo apenas quando RVC usado
   - Unload após processamento

### Fluxo de Execução

```python
# Modo LOW_VRAM=true
async def process_tts_job(text, voice_id):
    # 1. Carregar XTTS
    with vram_manager.load_model('xtts', load_xtts):
        audio_tts = await xtts.generate(text, voice_id)
    # XTTS descarregado automaticamente aqui
    
    # 2. Carregar RVC (se necessário)
    if use_rvc:
        with vram_manager.load_model('rvc', load_rvc):
            audio_final = await rvc.convert(audio_tts, rvc_model)
        # RVC descarregado automaticamente aqui
    
    return audio_final
```

---

## 📝 Implementação

### 1. Configuração (app/config.py)

```python
# Já implementado ✅
'low_vram_mode': os.getenv('LOW_VRAM', 'false').lower() == 'true',
```

### 2. VRAM Manager (app/vram_manager.py)

```python
# Já implementado ✅
class VRAMManager:
    @contextmanager
    def load_model(self, model_key, load_fn, *args):
        # Carrega modelo
        model = load_fn(*args)
        
        yield model
        
        # Descarrega modelo
        if self.low_vram_mode:
            self._unload_model(model)
```

### 3. XTTS Engine Adaptation

**Arquivo**: `app/engines/xtts_engine.py`

**Mudanças necessárias**:

```python
from ..vram_manager import get_vram_manager

class XttsEngine(TTSEngine):
    def __init__(self, ...):
        self.vram_mgr = get_vram_manager()
        
        # Em LOW_VRAM, NÃO carregar modelo no __init__
        if not self.vram_mgr.low_vram_mode:
            self.tts = self._load_xtts_model()
        else:
            self.tts = None  # Lazy load
    
    def _load_xtts_model(self):
        """Carrega modelo XTTS"""
        gpu = (self.device == 'cuda')
        return TTS(self.model_name, gpu=gpu, progress_bar=False)
    
    async def generate_dubbing(self, text, voice_profile, ...):
        # Em LOW_VRAM, carregar temporariamente
        if self.vram_mgr.low_vram_mode:
            with self.vram_mgr.load_model('xtts', self._load_xtts_model):
                result = await self._generate_internal(text, voice_profile)
        else:
            # Modo normal, modelo já está carregado
            result = await self._generate_internal(text, voice_profile)
        
        return result
    
    async def _generate_internal(self, text, voice_profile):
        """Lógica de geração (usa self.tts que está carregado)"""
        # ... código existente ...
```

### 4. F5-TTS Engine Adaptation

**Arquivo**: `app/engines/f5tts_engine.py`

**Similar ao XTTS**:

```python
from ..vram_manager import get_vram_manager

class F5TtsEngine(TTSEngine):
    def __init__(self, ...):
        self.vram_mgr = get_vram_manager()
        
        if not self.vram_mgr.low_vram_mode:
            self.model = self._load_f5tts_model()
            self.vocoder = self._load_vocoder()
        else:
            self.model = None
            self.vocoder = None
    
    def _load_f5tts_model(self):
        """Carrega F5-TTS model"""
        # ... código de carregamento ...
        return model
    
    async def generate_dubbing(self, text, voice_profile, ...):
        if self.vram_mgr.low_vram_mode:
            with self.vram_mgr.load_model('f5tts', self._load_f5tts_model):
                with self.vram_mgr.load_model('vocoder', self._load_vocoder):
                    result = await self._generate_internal(text, voice_profile)
        else:
            result = await self._generate_internal(text, voice_profile)
        
        return result
```

### 5. RVC Client Adaptation

**Arquivo**: `app/rvc_client.py` (ou onde RVC está)

```python
from .vram_manager import get_vram_manager

class RvcClient:
    def __init__(self, ...):
        self.vram_mgr = get_vram_manager()
        
        if not self.vram_mgr.low_vram_mode:
            # Carregar modelo RVC
            self.rvc_model = self._load_rvc_model()
        else:
            self.rvc_model = None
    
    def _load_rvc_model(self, model_path):
        """Carrega modelo RVC"""
        # ... código de carregamento ...
        return model
    
    async def convert_voice(self, audio, rvc_model_path, ...):
        if self.vram_mgr.low_vram_mode:
            with self.vram_mgr.load_model(f'rvc_{rvc_model_path}', 
                                           self._load_rvc_model, 
                                           rvc_model_path):
                result = await self._convert_internal(audio)
        else:
            result = await self._convert_internal(audio)
        
        return result
```

---

## 📈 Trade-offs

### Vantagens

✅ **70-75% menos VRAM**: Roda em GPUs pequenas  
✅ **Sem OOM errors**: Evita crashes por falta de memória  
✅ **Flexibilidade**: Permite escolher entre speed vs memory  
✅ **Transparente**: Mesma API, apenas config diferente

### Desvantagens

⚠️ **Latência maior**: +2-5s por carregamento de modelo  
⚠️ **Throughput menor**: ~30-50% menos requests/min  
⚠️ **Disco I/O**: Mais leitura de modelos (cache pode ajudar)

### Quando Usar

**LOW_VRAM=true**:
- GPU com ≤ 6GB VRAM
- Batch processing (latência não crítica)
- Desenvolvimento local
- Teste de múltiplos modelos

**LOW_VRAM=false** (recomendado):
- GPU com ≥ 8GB VRAM
- Produção com alta demanda
- Real-time ou near-real-time
- Latência crítica

---

## 🧪 Teste

### 1. Verificar VRAM Stats

```python
from app.vram_manager import get_vram_usage

stats = get_vram_usage()
print(stats)
```

**Output**:
```json
{
  "available": true,
  "low_vram_mode": true,
  "allocated_gb": 0.5,
  "reserved_gb": 1.2,
  "free_gb": 3.8,
  "total_gb": 6.0,
  "cached_models": 0
}
```

### 2. Testar Carregamento/Descarregamento

```bash
# Ativar LOW_VRAM
export LOW_VRAM=true

# Processar job
curl -X POST http://localhost:8000/tts/synthesize \
  -F "text=Teste LOW VRAM" \
  -F "tts_engine=xtts"

# Verificar logs
# Deve mostrar: "Carregando modelo 'xtts'" e "Descarregando modelo 'xtts'"
```

### 3. Benchmark VRAM

```python
# benchmarks/benchmark_vram.py
import asyncio
from app.engines.factory import create_engine
from app.vram_manager import get_vram_usage

async def benchmark_vram():
    # Antes
    stats_before = get_vram_usage()
    print(f"VRAM antes: {stats_before['allocated_gb']}GB")
    
    # Processar
    engine = create_engine('xtts', settings)
    await engine.generate_dubbing("Test", voice_profile)
    
    # Depois
    stats_after = get_vram_usage()
    print(f"VRAM depois: {stats_after['allocated_gb']}GB")
    
    # Delta
    delta = stats_after['allocated_gb'] - stats_before['allocated_gb']
    print(f"VRAM usada: {delta}GB")
```

---

## 📋 Checklist de Implementação

### Fase 1: Setup (Completo ✅)
- [x] Adicionar `LOW_VRAM` em config.py
- [x] Criar `app/vram_manager.py`
- [x] Criar documentação

### Fase 2: Engines (Pendente)
- [ ] Adaptar `XttsEngine` para lazy loading
- [ ] Adaptar `F5TtsEngine` para lazy loading
- [ ] Testar XTTS com LOW_VRAM=true
- [ ] Testar F5-TTS com LOW_VRAM=true

### Fase 3: RVC (Pendente)
- [ ] Adaptar `RvcClient` para lazy loading
- [ ] Testar RVC com LOW_VRAM=true
- [ ] Testar pipeline TTS → RVC

### Fase 4: Testing (Pendente)
- [ ] Testes unitários `test_vram_manager.py`
- [ ] Benchmark VRAM usage
- [ ] Teste E2E com LOW_VRAM=true
- [ ] Documentar resultados

---

## 🚀 Deploy

### Production

```yaml
# docker-compose.yml
services:
  # GPU pequena (RTX 3060 6GB)
  audio-voice-low-vram:
    environment:
      - LOW_VRAM=true
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
  
  # GPU grande (RTX 3090 24GB)
  audio-voice-high-perf:
    environment:
      - LOW_VRAM=false
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1']
              capabilities: [gpu]
```

---

## 📚 Recursos

- [vram_manager.py](../app/vram_manager.py) - Implementação
- [config.py](../app/config.py) - Configuração
- [PyTorch CUDA Best Practices](https://pytorch.org/docs/stable/notes/cuda.html)

---

**LOW_VRAM Mode: Economize 70% de VRAM!** 🔋
