# BUG.md — VRAM Leak: Chatterbox model memory not released after job completion

**Status**: Aberto
**Severidade**: Média
**Afeta**: SE7 audio-generation (celery worker)
**Detectado**: 2026-07-08

## Sintoma

O container `audio-generation-celery` consome **3838 MiB (~3.75 GB)** de VRAM mesmo sem jobs em execução. O health check reporta `"Model not loaded"` mas a memória GPU não é liberada.

```
nvidia-smi:
  PID 1800 (python) → 3838 MiB

torch.cuda.mem_get_info():
  free: 18.77 GB / total: 23.55 GB
  used by driver: 4.78 GB

torch.cuda.memory_allocated(0):  0  ← PyTorch diz que não tem nada
torch.cuda.memory_reserved(0):   0  ← mas o driver CUDA segura 4.78 GB
```

## Causa Raiz

1. O Celery worker (`--pool=solo`) executa tasks sequencialmente no processo principal
2. Na primeira task TTS, o `ChatterboxModelManager` carrega o modelo na GPU (~3.8 GB)
3. Após completar a task, os tensores PyTorch são liberados (`memory_allocated: 0`)
4. Mas o **CUDA caching allocator** e o **driver CUDA** não devolvem a memória
5. O `ChatterboxModelManager` perde a referência ao objeto, mas o driver mantém a memória alocada
6. Resultado: ~3.75 GB de VRAM "fantasma" — inacessível pelo Python, mas indisponível para outros processos

## Impacto

- VRAM desperdiçada: ~3.75 GB que poderiam ser usados por SE8 (Fooocus) ou SE10
- Rodar SE7 + SE8 + SE10 simultaneamente fica no limite de VRAM
- Reiniciar o container libera a memória (workaround temporário)

## Solução Proposta

**Lazy Unload com timeout**: Se nenhum job chegar em 60 segundos após a última execução, fazer unload explícito do modelo da GPU:

```python
# Conceito:
class ChatterboxModelManager:
    _last_used: float = 0.0
    _unload_timeout: float = 60.0

    def maybe_unload(self):
        if self._model is not None:
            if time.time() - self._last_used > self._unload_timeout:
                del self._model
                self._model = None
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
```

**Refs**:
- `services/se7-audio-generation/app/services/model_manager.py`
- `services/se7-audio-generation/app/tasks/generate_audio.py`
