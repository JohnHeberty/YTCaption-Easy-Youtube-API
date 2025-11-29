# ✅ RESOLVIDO: Device Mismatch Error (2025-11-29)

## Erro Original
```
RuntimeError: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0!
```

## Causa Raiz
Quando o F5-TTS é descarregado da VRAM (modo LOW_VRAM) e recarregado posteriormente, alguns tensors internos (especialmente `text_embed` em `dit.py`) não eram movidos de volta para CUDA, permanecendo na CPU.

## Solução Implementada (3 Camadas de Proteção)

### 1. Método `_ensure_model_on_device()`
Garante que todos os submodelos estão no device correto após carregamento:
- Move modelo principal via `.to(device)`
- Move submodelos: `ema_model`, `vocoder`, `model`, `mel_spec`
- Verifica tensors em `__dict__`
- Flush de CUDA cache

### 2. Chamada após carregamento
```python
# Modo normal (sem LOW_VRAM)
self.tts = F5TTS(...)
self._ensure_model_on_device(self.tts)  # ← CRÍTICO

# Modo lazy (LOW_VRAM)
self.tts = self._f5tts_class(...)
self._ensure_model_on_device(self.tts)  # ← CRÍTICO
```

### 3. Fallback para CPU em caso de falha
Se mesmo com proteção ocorrer device mismatch:
- Detecta `RuntimeError` com "Expected all tensors to be on the same device"
- Move todo o modelo para CPU temporariamente
- Refaz síntese em CPU
- Log de warning para debug

## Arquivos Modificados
- `app/engines/f5tts_engine.py`:
  - Adicionado `_ensure_model_on_device()` (linha ~209)
  - Modificado `_load_model()` (linha ~254)
  - Modificado `_synthesize_blocking()` (linha ~475) com try-except e fallback

## Testes Realizados
✅ Carregamento inicial: ema_model em cuda:0
✅ Recarregamento após unload: ema_model em cuda:0
✅ Fallback CPU funcional em caso de erro

## Prevenção Futura
A API agora é **resiliente** e **nunca deve falhar** com device mismatch:
1. Previne o erro movendo tensors antes da inferência
2. Se falhar, faz fallback automático para CPU
3. Logs detalhados para debug

---

## Erro Anterior (Para Referência)
audio-voice-celery  | [2025-11-29 18:45:26,461: INFO/MainProcess] 🔋 LOW_VRAM: Descarregando modelo 'f5tts' da VRAM...
audio-voice-celery  | [2025-11-29 18:45:26,876: INFO/MainProcess] 📊 VRAM liberada: 0.00 GB (antes=0.01, depois=0.01 GB)
audio-voice-celery  | [2025-11-29 18:45:26,876: ERROR/MainProcess] F5-TTS synthesis failed: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | [2025-11-29 18:45:26,876: INFO/MainProcess] 📊 VRAM liberada: 0.00 GB (antes=0.01, depois=0.01 GB)
audio-voice-celery  | [2025-11-29 18:45:26,876: ERROR/MainProcess] F5-TTS synthesis failed: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 345, in generate_dubbing
audio-voice-celery  |     audio_array = await loop.run_in_executor(
audio-voice-celery  |                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/lib/python3.11/concurrent/futures/thread.py", line 58, in run
audio-voice-celery  |     result = self.fn(*self.args, **self.kwargs)
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 419, in _synthesize_blocking
audio-voice-celery  |     audio_np, sample_rate, _ = self.tts.infer(
audio-voice-celery  |                                ^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/api.py", line 124, in infer
audio-voice-celery  |     wav, sr, spec = infer_process(
audio-voice-celery  |                     ^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 409, in infer_process
audio-voice-celery  |     return next(
audio-voice-celery  |            ^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 531, in infer_batch_process
audio-voice-celery  |     generated_wave, generated_mel_spec = next(result)
audio-voice-celery  |                                          ^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 490, in process_batch
audio-voice-celery  |     generated, _ = model_obj.sample(
audio-voice-celery  |                    ^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/utils/_contextlib.py", line 116, in decorate_context
audio-voice-celery  |     return func(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/cfm.py", line 217, in sample
audio-voice-celery  |     trajectory = odeint(fn, y0, t, **self.odeint_kwargs)
audio-voice-celery  |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/odeint.py", line 80, in odeint
audio-voice-celery  |     solution = solver.integrate(t)
audio-voice-celery  |                ^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/solvers.py", line 114, in integrate
audio-voice-celery  |     dy, f0 = self._step_func(self.func, t0, dt, t1, y0)
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/fixed_grid.py", line 10, in _step_func
audio-voice-celery  |     f0 = func(t0, y0, perturb=Perturb.NEXT if self.perturb else Perturb.NONE)
audio-voice-celery  |          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/misc.py", line 197, in forward
audio-voice-celery  |     return self.base_func(t, y)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/cfm.py", line 180, in fn
audio-voice-celery  |     pred_cfg = self.transformer(
audio-voice-celery  |                ^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 283, in forward
audio-voice-celery  |     x_cond = self.get_input_embed(
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 252, in get_input_embed
audio-voice-celery  |     self.text_cond = self.text_embed(text, seq_len, drop_text=False, audio_mask=audio_mask)
audio-voice-celery  |                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 100, in forward
audio-voice-celery  |     text = self.text_embed(text)  # b n -> b n d
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/sparse.py", line 164, in forward
audio-voice-celery  |     return F.embedding(
audio-voice-celery  |            ^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/functional.py", line 2267, in embedding
audio-voice-celery  |     return torch.embedding(weight, input, padding_idx, scale_grad_by_freq, sparse)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  | RuntimeError: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | [2025-11-29 18:45:26,881: ERROR/MainProcess] Dubbing job job_52eaa101c8c9 failed: TTS engine error: F5-TTS synthesis error: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 345, in generate_dubbing
audio-voice-celery  |     audio_array = await loop.run_in_executor(
audio-voice-celery  |                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/lib/python3.11/concurrent/futures/thread.py", line 58, in run
audio-voice-celery  |     result = self.fn(*self.args, **self.kwargs)
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 419, in _synthesize_blocking
audio-voice-celery  |     audio_np, sample_rate, _ = self.tts.infer(
audio-voice-celery  |                                ^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/api.py", line 124, in infer
audio-voice-celery  |     wav, sr, spec = infer_process(
audio-voice-celery  |                     ^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 409, in infer_process
audio-voice-celery  |     return next(
audio-voice-celery  |            ^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 531, in infer_batch_process
audio-voice-celery  |     generated_wave, generated_mel_spec = next(result)
audio-voice-celery  |                                          ^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 490, in process_batch
audio-voice-celery  |     generated, _ = model_obj.sample(
audio-voice-celery  |                    ^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/utils/_contextlib.py", line 116, in decorate_context
audio-voice-celery  |     return func(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/cfm.py", line 217, in sample
audio-voice-celery  |     trajectory = odeint(fn, y0, t, **self.odeint_kwargs)
audio-voice-celery  |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/odeint.py", line 80, in odeint
audio-voice-celery  |     solution = solver.integrate(t)
audio-voice-celery  |                ^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/solvers.py", line 114, in integrate
audio-voice-celery  |     dy, f0 = self._step_func(self.func, t0, dt, t1, y0)
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/fixed_grid.py", line 10, in _step_func
audio-voice-celery  |     f0 = func(t0, y0, perturb=Perturb.NEXT if self.perturb else Perturb.NONE)
audio-voice-celery  |          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/misc.py", line 197, in forward
audio-voice-celery  |     return self.base_func(t, y)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/cfm.py", line 180, in fn
audio-voice-celery  |     pred_cfg = self.transformer(
audio-voice-celery  |                ^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 283, in forward
audio-voice-celery  |     x_cond = self.get_input_embed(
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 252, in get_input_embed
audio-voice-celery  |     self.text_cond = self.text_embed(text, seq_len, drop_text=False, audio_mask=audio_mask)
audio-voice-celery  |                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 100, in forward
audio-voice-celery  |     text = self.text_embed(text)  # b n -> b n d
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/sparse.py", line 164, in forward
audio-voice-celery  |     return F.embedding(
audio-voice-celery  |            ^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/functional.py", line 2267, in embedding
audio-voice-celery  |     return torch.embedding(weight, input, padding_idx, scale_grad_by_freq, sparse)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  | RuntimeError: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | 
audio-voice-celery  | The above exception was the direct cause of the following exception:
audio-voice-celery  | 
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/processor.py", line 144, in process_dubbing_job
audio-voice-celery  |     audio_bytes, duration = await engine.generate_dubbing(
audio-voice-celery  |                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 397, in generate_dubbing
audio-voice-celery  |     raise TTSEngineException(f"F5-TTS synthesis error: {e}") from e
audio-voice-celery  | app.exceptions.TTSEngineException: TTS engine error: F5-TTS synthesis error: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | [2025-11-29 18:45:26,882: ERROR/MainProcess] ❌ Celery dubbing task failed: Dubbing error: TTS engine error: F5-TTS synthesis error: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 345, in generate_dubbing
audio-voice-celery  |     audio_array = await loop.run_in_executor(
audio-voice-celery  |                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/lib/python3.11/concurrent/futures/thread.py", line 58, in run
audio-voice-celery  |     result = self.fn(*self.args, **self.kwargs)
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 419, in _synthesize_blocking
audio-voice-celery  |     audio_np, sample_rate, _ = self.tts.infer(
audio-voice-celery  |                                ^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/api.py", line 124, in infer
audio-voice-celery  |     wav, sr, spec = infer_process(
audio-voice-celery  |                     ^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 409, in infer_process
audio-voice-celery  |     return next(
audio-voice-celery  |            ^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 531, in infer_batch_process
audio-voice-celery  |     generated_wave, generated_mel_spec = next(result)
audio-voice-celery  |                                          ^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 490, in process_batch
audio-voice-celery  |     generated, _ = model_obj.sample(
audio-voice-celery  |                    ^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/utils/_contextlib.py", line 116, in decorate_context
audio-voice-celery  |     return func(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/cfm.py", line 217, in sample
audio-voice-celery  |     trajectory = odeint(fn, y0, t, **self.odeint_kwargs)
audio-voice-celery  |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/odeint.py", line 80, in odeint
audio-voice-celery  |     solution = solver.integrate(t)
audio-voice-celery  |                ^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/solvers.py", line 114, in integrate
audio-voice-celery  |     dy, f0 = self._step_func(self.func, t0, dt, t1, y0)
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/fixed_grid.py", line 10, in _step_func
audio-voice-celery  |     f0 = func(t0, y0, perturb=Perturb.NEXT if self.perturb else Perturb.NONE)
audio-voice-celery  |          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/misc.py", line 197, in forward
audio-voice-celery  |     return self.base_func(t, y)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/cfm.py", line 180, in fn
audio-voice-celery  |     pred_cfg = self.transformer(
audio-voice-celery  |                ^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 283, in forward
audio-voice-celery  |     x_cond = self.get_input_embed(
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 252, in get_input_embed
audio-voice-celery  |     self.text_cond = self.text_embed(text, seq_len, drop_text=False, audio_mask=audio_mask)
audio-voice-celery  |                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 100, in forward
audio-voice-celery  |     text = self.text_embed(text)  # b n -> b n d
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/sparse.py", line 164, in forward
audio-voice-celery  |     return F.embedding(
audio-voice-celery  |            ^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/functional.py", line 2267, in embedding
audio-voice-celery  |     return torch.embedding(weight, input, padding_idx, scale_grad_by_freq, sparse)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  | RuntimeError: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | 
audio-voice-celery  | The above exception was the direct cause of the following exception:
audio-voice-celery  | 
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/processor.py", line 144, in process_dubbing_job
audio-voice-celery  |     audio_bytes, duration = await engine.generate_dubbing(
audio-voice-celery  |                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 397, in generate_dubbing
audio-voice-celery  |     raise TTSEngineException(f"F5-TTS synthesis error: {e}") from e
audio-voice-celery  | app.exceptions.TTSEngineException: TTS engine error: F5-TTS synthesis error: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | 
audio-voice-celery  | The above exception was the direct cause of the following exception:
audio-voice-celery  | 
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/celery_tasks.py", line 81, in _process
audio-voice-celery  |     job = await get_processor().process_dubbing_job(job, voice_profile)
audio-voice-celery  |           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/processor.py", line 191, in process_dubbing_job
audio-voice-celery  |     raise DubbingException(str(e)) from e
audio-voice-celery  | app.exceptions.DubbingException: Dubbing error: TTS engine error: F5-TTS synthesis error: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | [2025-11-29 18:45:26,886: ERROR/MainProcess] Task app.celery_tasks.dubbing_task[job_52eaa101c8c9] raised unexpected: DubbingException('Dubbing error: TTS engine error: F5-TTS synthesis error: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)')
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 345, in generate_dubbing
audio-voice-celery  |     audio_array = await loop.run_in_executor(
audio-voice-celery  |                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/lib/python3.11/concurrent/futures/thread.py", line 58, in run
audio-voice-celery  |     result = self.fn(*self.args, **self.kwargs)
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 419, in _synthesize_blocking
audio-voice-celery  |     audio_np, sample_rate, _ = self.tts.infer(
audio-voice-celery  |                                ^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/api.py", line 124, in infer
audio-voice-celery  |     wav, sr, spec = infer_process(
audio-voice-celery  |                     ^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 409, in infer_process
audio-voice-celery  |     return next(
audio-voice-celery  |            ^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 531, in infer_batch_process
audio-voice-celery  |     generated_wave, generated_mel_spec = next(result)
audio-voice-celery  |                                          ^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/infer/utils_infer.py", line 490, in process_batch
audio-voice-celery  |     generated, _ = model_obj.sample(
audio-voice-celery  |                    ^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/utils/_contextlib.py", line 116, in decorate_context
audio-voice-celery  |     return func(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/cfm.py", line 217, in sample
audio-voice-celery  |     trajectory = odeint(fn, y0, t, **self.odeint_kwargs)
audio-voice-celery  |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/odeint.py", line 80, in odeint
audio-voice-celery  |     solution = solver.integrate(t)
audio-voice-celery  |                ^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/solvers.py", line 114, in integrate
audio-voice-celery  |     dy, f0 = self._step_func(self.func, t0, dt, t1, y0)
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/fixed_grid.py", line 10, in _step_func
audio-voice-celery  |     f0 = func(t0, y0, perturb=Perturb.NEXT if self.perturb else Perturb.NONE)
audio-voice-celery  |          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torchdiffeq/_impl/misc.py", line 197, in forward
audio-voice-celery  |     return self.base_func(t, y)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/cfm.py", line 180, in fn
audio-voice-celery  |     pred_cfg = self.transformer(
audio-voice-celery  |                ^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 283, in forward
audio-voice-celery  |     x_cond = self.get_input_embed(
audio-voice-celery  |              ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 252, in get_input_embed
audio-voice-celery  |     self.text_cond = self.text_embed(text, seq_len, drop_text=False, audio_mask=audio_mask)
audio-voice-celery  |                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/f5_tts/model/backbones/dit.py", line 100, in forward
audio-voice-celery  |     text = self.text_embed(text)  # b n -> b n d
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1553, in _wrapped_call_impl
audio-voice-celery  |     return self._call_impl(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/module.py", line 1562, in _call_impl
audio-voice-celery  |     return forward_call(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/modules/sparse.py", line 164, in forward
audio-voice-celery  |     return F.embedding(
audio-voice-celery  |            ^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/torch/nn/functional.py", line 2267, in embedding
audio-voice-celery  |     return torch.embedding(weight, input, padding_idx, scale_grad_by_freq, sparse)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  | RuntimeError: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | 
audio-voice-celery  | The above exception was the direct cause of the following exception:
audio-voice-celery  | 
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/app/app/processor.py", line 144, in process_dubbing_job
audio-voice-celery  |     audio_bytes, duration = await engine.generate_dubbing(
audio-voice-celery  |                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/engines/f5tts_engine.py", line 397, in generate_dubbing
audio-voice-celery  |     raise TTSEngineException(f"F5-TTS synthesis error: {e}") from e
audio-voice-celery  | app.exceptions.TTSEngineException: TTS engine error: F5-TTS synthesis error: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)
audio-voice-celery  | 
audio-voice-celery  | The above exception was the direct cause of the following exception:
audio-voice-celery  | 
audio-voice-celery  | Traceback (most recent call last):
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/celery/app/trace.py", line 477, in trace_task
audio-voice-celery  |     R = retval = fun(*args, **kwargs)
audio-voice-celery  |                  ^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/local/lib/python3.11/dist-packages/celery/app/trace.py", line 760, in __protected_call__
audio-voice-celery  |     return self.run(*args, **kwargs)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/celery_tasks.py", line 99, in dubbing_task
audio-voice-celery  |     return run_async_task(_process())
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/celery_tasks.py", line 52, in run_async_task
audio-voice-celery  |     return loop.run_until_complete(coro)
audio-voice-celery  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/usr/lib/python3.11/asyncio/base_events.py", line 654, in run_until_complete
audio-voice-celery  |     return future.result()
audio-voice-celery  |            ^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/celery_tasks.py", line 81, in _process
audio-voice-celery  |     job = await get_processor().process_dubbing_job(job, voice_profile)
audio-voice-celery  |           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
audio-voice-celery  |   File "/app/app/processor.py", line 191, in process_dubbing_job
audio-voice-celery  |     raise DubbingException(str(e)) from e
audio-voice-celery  | app.exceptions.DubbingException: Dubbing error: TTS engine error: F5-TTS synthesis error: Expected all tensors to be on the same device, but found at least two devices, cpu and cuda:0! (when checking argument for argument index in method wrapper_CUDA__index_select)