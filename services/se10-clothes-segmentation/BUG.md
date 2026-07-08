# BUG.md — VRAM consumption: GroundingDINO + SAM2 persistent on GPU

**Status**: Aberto
**Severidade**: Informativa
**Afeta**: SE10 clothes-segmentation (FastAPI server)
**Detectado**: 2026-07-08

## Sintoma

O container `ytcaption-se10-clothes-segmentation` consome **486 MiB** de VRAM. Diferente do SE7 e SE4, esta memória é **legítima** — os modelos estão ativos e prontos para uso.

```
nvidia-smi:
  PID 1208753 (python3.11) → 486 MiB

Porta 8010: FastAPI server (não Celery)
Modelos: GroundingDINO + SAM2 (CPU/GPU)
```

## Análise

O SE10 é um servidor FastAPI (não Celery) que mantém os modelos carregados permanentemente para baixa latência. Os 486 MiB representam:
- GroundingDINO: ~200 MiB
- SAM2: ~286 MiB

**Esta não é uma leak** — é o comportamento esperado para um servidor de segmentação que precisa de resposta rápida.

## Solução Proposta (Opcional)

Se VRAM ficar crítica, implementar lazy loading:
- Carregar modelos sob demanda no primeiro request
- Unload após timeout sem requests
- Complexidade: alta (FastAPI é síncrono, precisa de thread separada para cleanup)

**Refs**:
- `services/se10-clothes-segmentation/app/main.py`
