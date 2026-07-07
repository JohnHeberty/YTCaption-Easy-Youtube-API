# Plano de Otimização de Memória — Monorepo YTCaption

## Problema Atual

- **RAM**: 99.8% (39.73 / 39.81 GiB)
- **SE10**: 20.11 GiB RAM (54.5%) — deveria ser ~2-4 GB com DEVICE=cpu
- **SE8**: 13.05 GiB RAM (35.4%) + 10.6 GB GPU — double-loading
- **Total SE10+SE8**: 33.16 GiB = 83.5% da RAM total

---

## Fase 1 — SE10 Urgente (liberar ~15GB imediatamente) ✅ IMPLEMENTADO

### Diagnóstico

| Causa | RAM extra | Solução |
|---|---|---|
| `torch==2.12.0+cu130` inicia CUDA context | ~1-2 GB | Trocar para `torch` CPU-only |
| `onnxruntime-gpu` carrega CUDA EP libs | ~0.5-1 GB | Trocar para `onnxruntime` (CPU) |
| 4 pacotes nvidia-* memory-mapped | ~2-3 GB | Remover quando DEVICE=cpu |
| 4 modelos carregados no startup | ~2.6 GB | Lazy loading (sob demanda) |
| NVIDIA devices montados no container | ~1 GB | `CUDA_VISIBLE_DEVICES=""` |

### Ações

1. ✅ **Criar `requirements-cpu.txt`** — `torch==2.12.0+cpu`, `onnxruntime>=1.17.0` (sem -gpu), sem nvidia-*
2. ✅ **Atualizar `docker-compose.yml`** — `CUDA_VISIBLE_DEVICES=""`, NVIDIA device mounts removidos
3. ✅ **Atualizar `Dockerfile`** — Build condicional CPU/GPU via `DEVICE` build arg, CUDA symlinks só quando DEVICE!=cpu
4. ✅ **Rebuild container SE10** — `docker compose build --no-cache && up -d`

### Resultado Obtido

- SE10 RAM: 20.11 GB → **2.93 GB** (redução de 17.18 GB) ✅ SUPEROU META

---

## Fase 2 — SE10 Model Lifecycle ⚠️ PARCIALMENTE IMPLEMENTADO

### Diagnóstico

- 4 modelos carregados permanentemente no startup: GroundingDINO (1.3 GB), SAM2 (300 MB), YOLO (86 MB), BiRefNet (928 MB)
- `Segmentor` é singleton que nunca descarrega modelos
- PoseRenderer sempre inicializado mesmo quando `include_pose=False`

### Ações

1. ✅ **Lazy Loading no `Segmentor`** — Background idle timer (120s) + reload sob demanda via `state.py`
2. ✅ **`unload_all()` no `Segmentor`** — Zera todos os modelos + `malloc_trim` + `gc.collect()`
3. ❌ **Reverter SE10 para GPU com memory management** — NÃO IMPLEMENTADO
   - **Motivo**: Primeiro precisa validar que SE10+SE8 não competem por GPU (24GB VRAM). O problema original era CUDA handle corruption quando ambos rodam em GPU. Precisa de investigação adicional: testar SE10 em GPU com SE8 idle (modelos descarregados) para verificar se 24GB é suficiente.
4. ✅ **Auto-unload idle timer** — 120s timeout (ajustado de 60s original para dar margem a requests consecutivos)

### Resultado Obtido

- SE10 idle: 20.11 GB → **697 MB** após idle timeout ✅ SUPEROU META
- SE10 recarrega sob demanda no próximo request (~5-10s overhead aceitável)

---

## Fase 3 — SE8 Memory Management ✅ IMPLEMENTADO

### Diagnóstico

| Causa | Impacto | Solução |
|---|---|---|
| Checkpoint loading: state_dict + model simultâneos | ~13 GB pico | `del sd` + `gc.collect()` |
| Modelos ficam em GPU após job | ~10 GB permanente | Offload explícito pós-job |
| Idle timer 300s muito longo | Modelos ficam 5min | Reduzir para 60s |
| Dual model management | Overhead | Consolidar gestão |

### Ações

1. ✅ **Fix `checkpoint.py` — `del sd` após loading** — Libera ~6GB de state_dict imediatamente após uso
2. ✅ **Offload explícito pós-job em `process_generate()`** — `soft_empty_cache()` (ldm_patched) + `malloc_trim` + `gc.collect()` + `torch.cuda.empty_cache()` + `torch.cuda.synchronize()` no finally block
3. ✅ **Reduzir idle timer** — `MODEL_IDLE_TIMEOUT`: 300s → 60s (5x mais rápido)
4. ❌ **Lazy-load IP-Adapter e ControlNet** — NÃO IMPLEMENTADO
   - **Motivo**: Cancelado por prioridade baixa. IP-Adapter (~2GB) e ControlNet (~739MB) são carregados sob demanda apenas quando `ip_adapter_image` ou `control_net` são fornecidos no request. A maioria dos requests NSFW não usa IP-Adapter (usa FaceID que já é lazy). O impacto seria ~2.7GB extra no pico, mas não é crítico.
5. ✅ **Liberar inpaint patch após uso** — `del lora_data` + `gc.collect()` após `add_patches()` (~1.3GB liberados)

### Resultado Obtido

- SE8 idle: 13.05 GB → **432 MB** ✅ SUPEROU META
- SE8 VRAM: 0 models loaded após job (unload via soft_empty_cache funciona)
- SE8 RAM pico durante job: ~17 GB (reduzido de ~34GB anteriormente, antes do `del sd`)

---

## Fase 4 — Validação ✅ PARCIALMENTE VALIDADO

### Checklist

1. ✅ **Job NSFW completo** com TESTE1.jpg — Job `cr_61b1c1005074`, try_2 best, composite=3.782, pose_changed=False, 2 tentativas
2. ✅ **RAM idle < 50%** — 20% (8.6 GB) ✅
3. ❌ **Performance (latência de first-byte)** — NÃO TESTADO
   - **Motivo**: SE10 em CPU é ~30x mais lento (~30s vs ~1s). Precisa de teste dedicado medindo tempo total do pipeline. O PLANEJAMENTO indica que é aceitável para pipeline de ~2min, mas não foi medido formalmente.
4. ✅ **GPU memory** — SE10 em CPU (0 VRAM), SE8 usa ~10 GB VRAM, total ~10 GB < 15 GB ✅

### Métricas de Sucesso

| Métrica | Meta | Resultado Final | Status |
|---|---|---|---|
| RAM idle | < 16 GB | **8.6 GB (20%)** | ✅ SUPEROU |
| RAM pico (job) | < 28 GB | **28 GB** | ⚠️ NO MÁXIMO |
| SE10 RAM idle | < 4 GB | **2.93 GB** | ✅ SUPEROU |
| SE10 RAM após idle | — | **697 MB** | ✅ EXCELENTE |
| SE8 RAM idle | < 1 GB | **432 MB** | ✅ SUPEROU |
| GPU VRAM | < 15 GB | **~10 GB** | ✅ |

---

## Arquivos Afetados (Implementados)

### SE10
- ✅ `services/se10-clothes-segmentation/requirements-cpu.txt` — **CRIADO** (torch+cpu, onnxruntime CPU, sem nvidia-*)
- ✅ `services/se10-clothes-segmentation/docker/Dockerfile` — conditional CPU/GPU build
- ✅ `services/se10-clothes-segmentation/docker/docker-compose.yml` — CUDA_VISIBLE_DEVICES, device mounts
- ✅ `services/se10-clothes-segmentation/app/services/segmentor.py` — unload_all + idle timer + lazy PoseRenderer + malloc_trim
- ✅ `services/se10-clothes-segmentation/app/state.py` — background idle checker thread

### SE8
- ✅ `services/se8-image-generation/app/services/checkpoint.py` — del sd after loading
- ✅ `services/se8-image-generation/app/services/worker.py` — offload in finally block + del inpaint patch
- ✅ `services/se8-image-generation/app/core/config.py` — idle timer 300s→60s

### Não implementados (com motivo)
- ❌ `requirements-gpu.txt` — Não necessário (requirements.txt existente serve para GPU)
- ❌ `birefnet_detector.py` unload method — Não necessário (unload_all() zera referência diretamente)
- ❌ `yolo_detector.py` unload method — Não necessário (unload_all() zera referência diretamente)
- ❌ `model_manager.py` unload_all — Não alterado (usamos soft_empty_cache do ldm_patched que é mais direto)
- ❌ `pipeline.py` lazy IP-Adapter/ControlNet — Cancelado (prioridade baixa)
- ❌ SE10 revert para GPU — Requer investigação adicional de GPU contention

---

## Commits

- `3d21953` — perf: reduce RAM from 39.73GB to 8.2GB idle (79% reduction)

---

## Próximos Passos (não prioritários)

1. **Reverter SE10 para GPU** — Investigar se SE10+SE8 em GPU simultaneamente cabe em 24GB VRAM. SE10 usa ~1.5GB (YOLO+BiRefNet), SE8 idle descarrega modelos. Pode funcionar se SE8 descarrega antes de SE8 carregar.
2. **Lazy-load IP-Adapter/ControlNet** — Carregar sob demanda (~2.7GB economizados no pico)
3. **Teste de performance** — Medir latência de first-byte com SE10 em CPU vs GPU
4. **Monitoramento contínuo** — Dashboard de RAM/VRAM para detectar regressões
