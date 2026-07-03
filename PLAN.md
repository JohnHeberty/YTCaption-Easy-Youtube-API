# Plano de Otimização de Memória — Monorepo YTCaption

## Problema Atual

- **RAM**: 99.8% (39.73 / 39.81 GiB)
- **SE10**: 20.11 GiB RAM (54.5%) — deveria ser ~2-4 GB com DEVICE=cpu
- **SE8**: 13.05 GiB RAM (35.4%) + 10.6 GB GPU — double-loading
- **Total SE10+SE8**: 33.16 GiB = 83.5% da RAM total

---

## Fase 1 — SE10 Urgente (liberar ~15GB imediatamente)

### Diagnóstico

| Causa | RAM extra | Solução |
|---|---|---|
| `torch==2.12.0+cu130` inicia CUDA context | ~1-2 GB | Trocar para `torch` CPU-only |
| `onnxruntime-gpu` carrega CUDA EP libs | ~0.5-1 GB | Trocar para `onnxruntime` (CPU) |
| 4 pacotes nvidia-* memory-mapped | ~2-3 GB | Remover quando DEVICE=cpu |
| 4 modelos carregados no startup | ~2.6 GB | Lazy loading (sob demanda) |
| NVIDIA devices montados no container | ~1 GB | `CUDA_VISIBLE_DEVICES=""` |

### Ações

1. **Criar `requirements-cpu.txt`** em `services/se10-clothes-segmentation/docker/`
   - `torch` (CPU-only, sem +cu130)
   - `onnxruntime` (sem -gpu)
   - Remover: `nvidia-cublas-cu12`, `nvidia-cuda-runtime-cu12`, `nvidia-cudnn-cu12`, `nvidia-cufft-cu12`

2. **Atualizar `docker-compose.yml`**
   - Adicionar `CUDA_VISIBLE_DEVICES=""` quando DEVICE=cpu
   - Remover volume mounts de NVIDIA devices (`/dev/nvidia0`, etc) quando DEVICE=cpu
   - Manter apenas volume mounts de driver libs como fallback

3. **Atualizar `Dockerfile`**
   - Build stage com conditional: se DEVICE=cpu, instalar requirements-cpu.txt
   - Remover symlinks CUDA quando DEVICE=cpu

4. **Rebuild container SE10**
   - `docker compose up -d --build --force-recreate`

### Resultado Esperado

- SE10 RAM: 20 GB → ~4-6 GB (redução de ~14-16 GB)
- GPU: permanece ~500 MB (ONNX CPU context mínimo)

---

## Fase 2 — SE10 Model Lifecycle

### Diagnóstico

- 4 modelos carregados permanentemente no startup: GroundingDINO (1.3 GB), SAM2 (300 MB), YOLO (86 MB), BiRefNet (928 MB)
- `Segmentor` é singleton que nunca descarrega modelos
- PoseRenderer sempre inicializado mesmo quando `include_pose=False`

### Ações

1. **Lazy Loading no `Segmentor`**
   - Carregar detector apenas no primeiro request
   - Cache com timestamp de último uso
   - Auto-unload após 60s sem requests

2. **`unload_all()` no `Segmentor`**
   - Método para liberar todos os modelos
   - `del self._yolo_detector`, `del self._birefnet_detector`, etc.
   - `gc.collect()` + `torch.cuda.empty_cache()` (se GPU)

3. **Reverter SE10 para GPU com memory management**
   - Após lifecycle implementado, trocar DEVICE=cpu → DEVICE=cuda
   - YOLO + BiRefNet em GPU = ~1.5 GB VRAM (vs 20 GB RAM)
   - SE8 e SE10 não rodam simultaneamente (fila de requests)

4. **Auto-unload idle timer**
   - Se 60s sem requests → unload todos os modelos
   - Próximo request → reload sob demanda

### Resultado Esperado

- SE10 RAM idle: ~400 MB (apenas FastAPI)
- SE10 RAM ativo: ~2 GB (1 detector carregado)
- SE10 GPU ativo: ~1.5 GB (YOLO + BiRefNet)

---

## Fase 3 — SE8 Memory Management

### Diagnóstico

| Causa | Impacto | Solução |
|---|---|---|
| Checkpoint loading: state_dict + model simultâneos | ~13 GB pico | `del sd` + `gc.collect()` |
| Modelos ficam em GPU após job | ~10 GB permanente | Offload explícito pós-job |
| Idle timer 300s muito longo | Modelos ficam 5min | Reduzir para 60s |
| Dual model management | Overhead | Consolidar gestão |

### Ações

1. **Fix `checkpoint.py` — `del sd` após loading**
   ```python
   sd = utils.load_torch_file(ckpt_path)
   model = model_config.get_model(sd, ...)
   model.load_model_weights(sd, ...)
   del sd  # Liberar state_dict imediatamente
   import gc; gc.collect()
   ```

2. **Offload explícito pós-job em `process_generate()`**
   ```python
   finally:
       gc.collect()
       pipeline.clear_caches()
       manager = get_model_manager()
       manager.unload_all()  # NOVO: descarregar modelos pesados
   ```

3. **Reduzir idle timer**
   - `MODEL_IDLE_TIMEOUT`: 300s → 60s
   - Modelos descarregam 5x mais rápido quando idle

4. **Lazy-load IP-Adapter e ControlNet**
   - Carregar apenas quando `ip_adapter_image` ou `control_net` são fornecidos
   - Evita carregar ~3 GB de IP-Adapter para requests que não usam

5. **Liberar inpaint patch após uso**
   ```python
   lora_data = _utils.load_torch_file(inpaint_patch_path)
   # ... aplicar patches ...
   del lora_data  # Liberar 1.3 GB
   ```

### Resultado Esperado

- SE8 RAM pico: 13 GB → ~3-4 GB (apenas modelo ativo)
- SE8 RAM idle: ~400 MB (apenas FastAPI)
- SE8 GPU pico: ~10 GB → ~7 GB (offload mais agressivo)

---

## Fase 4 — Validação

### Checklist

1. **Job NSFW completo** com TESTE1.jpg
   - Medir RAM peak durante processamento
   - Verificar que modelos são descarregados corretamente
   - Confirmar resultado visual não degradou

2. **RAM idle < 50%**
   - Após 2 min sem jobs, RAM deve estar < 20 GB
   - Todos os modelos pesados devem estar descarregados

3. **Performance**
   - Tempo de first-byte não deve aumentar > 20%
   - Throughput de requests deve ser similar

4. **GPU memory**
   - SE10+SE8 não devem ultrapassar 20 GB VRAM combinados
   - SE10 em CPU quando SE8 está processando (vice-versa)

### Métricas de Sucesso

| Métrica | Antes | Depois | Meta |
|---|---|---|---|
| RAM idle | 39.73 GB (99.8%) | < 16 GB | < 50% |
| RAM pico (job) | 39.73 GB | < 28 GB | < 70% |
| SE10 RAM | 20.11 GB | < 4 GB | < 10% |
| SE8 RAM idle | 13.05 GB | < 1 GB | < 5% |
| GPU VRAM | 11.2 GB | < 15 GB | < 60% |

---

## Prioridade de Implementação

1. **Fase 1** (urgente): SE10 CPU fix — libera ~15GB imediatamente
2. **Fase 3** (alto): SE8 memory management — reduz pico de 13GB
3. **Fase 2** (médio): SE10 model lifecycle — otimiza uso a longo prazo
4. **Fase 4** (contínuo): Validação e monitoramento

## Riscos e Mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| SE10 em CPU é mais lento | ~30s vs ~1s detecção | Aceitável para pipeline de ~2min; reverter para GPU com lifecycle |
| Lazy loading aumenta latência do primeiro request | ~5-10s no primeiro request | Warm-up no startup ou background loading |
| Offload agressivo causa reload frequente | CPU overhead de reload | Idle timer calibrado (60s é sweet spot) |
| `del sd` pode causar referências penduradas | Memory leak se variável referenciada | Usar `gc.collect()` + verificações |

---

## Arquivos Afetados

### SE10
- `services/se10-clothes-segmentation/docker/Dockerfile` — conditional CPU/GPU build
- `services/se10-clothes-segmentation/docker/docker-compose.yml` — CUDA_VISIBLE_DEVICES, device mounts
- `services/se10-clothes-segmentation/requirements.txt` → `requirements-cpu.txt` + `requirements-gpu.txt`
- `services/se10-clothes-segmentation/app/services/segmentor.py` — lazy loading + unload_all
- `services/se10-clothes-segmentation/app/services/birefnet_detector.py` — unload method
- `services/se10-clothes-segmentation/app/services/yolo_detector.py` — unload method

### SE8
- `services/se8-image-generation/app/services/checkpoint.py` — del sd after loading
- `services/se8-image-generation/app/services/worker.py` — offload in finally block
- `services/se8-image-generation/app/services/model_manager.py` — unload_all, idle timer
- `services/se8-image-generation/app/services/pipeline.py` — lazy IP-Adapter/ControlNet
