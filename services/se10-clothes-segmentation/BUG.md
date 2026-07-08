# BUG.md — VRAM consumption: SegFormer + YOLO persistent on GPU

**Status**: Corrigido (2026-07-08) — cleanup_cuda() centralizado no shared
**Severidade**: Baixa
**Afeta**: SE10 clothes-segmentation (FastAPI server)
**Detectado**: 2026-07-08
**Corrigido**: 2026-07-08

## Sintoma

O container `ytcaption-se10-clothes-segmentation` consumia **486 MiB** de VRAM mesmo com idle unload ativo. A causa era `torch.cuda.empty_cache()` sem `synchronize()` + `ipc_collect()` — memória retida pelo driver CUDA.

## Causa Raiz

O `_cleanup_memory()` original fazia apenas `gc.collect()` + `malloc_trim()`, sem tocar no CUDA. O `unload_gpu_models()` chamava `torch.cuda.empty_cache()` mas sem `synchronize()` nem `ipc_collect()`.

## Solução Aplicada

Centralização do CUDA cleanup no shared library:

```python
# shared/gpu_utils.py
def cleanup_cuda() -> None:
    gc.collect()
    torch.cuda.synchronize()     # ← adicionado
    torch.cuda.empty_cache()     # já existia
    torch.cuda.ipc_collect()     # ← adicionado
    ctypes.CDLL("libc.so.6").malloc_trim(0)
```

`_cleanup_memory()` agora chama `cleanup_cuda()` — 1 linha取代 8.

## Resultado

VRAM: 486 MiB → 372 MiB (redução de ~114 MiB). O restante é contexto CUDA mínimo do PyTorch no CPU (esperado).

## Modelos em uso

- SegFormer B2 (`mattmdjaga/segformer_b2_clothes`) — 18 classes, pixel-level
- YOLO11-seg (`yolo11m-seg.pt`) — detecção de pessoas com máscaras

**Refs**:
- `shared/gpu_utils.py` — CUDA cleanup centralizado
- `services/se10-clothes-segmentation/app/services/segmentor.py` — `_cleanup_memory()`
- `services/se10-clothes-segmentation/app/services/segformer_detector.py`
- `services/se10-clothes-segmentation/app/services/yolo_detector.py`
