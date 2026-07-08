# BUG.md — VRAM Leak: CUDA context retention after model release

**Status**: Aberto
**Severidade**: Baixa
**Afeta**: SE4 audio-transcriber (celery worker)
**Detectado**: 2026-07-08

## Sintoma

O container `audio-transcriber-celery` consome **294 MiB** de VRAM mesmo sem jobs em execução. O PyTorch reporta 0 bytes alocados mas o driver CUDA retém a memória.

```
nvidia-smi:
  PID 1727 (python) → 294 MiB

torch.cuda.memory_allocated(0):  0
torch.cuda.memory_reserved(0):   0
```

## Causa Raiz

1. O Celery worker carregou o modelo Whisper numa task anterior
2. Após completar, os tensores foram liberados do PyTorch
3. O CUDA context (cuDNN handles, cuBLAS handles) ficou ativo no processo
4. O driver CUDA não liberou os 294 MiB do context

## Impacto

Baixo — 294 MiB é relativamente pouco. Porém contribui para o consumo total de VRAM quando combinado com SE7 e SE10.

## Solução Proposta

Lazy unload similar ao SE7: após timeout sem jobs, fazer `del model` + `torch.cuda.empty_cache()` + `torch.cuda.synchronize()`.

**Refs**:
- `services/se4-audio-transcriber/app/infrastructure/whisper_engine.py`
