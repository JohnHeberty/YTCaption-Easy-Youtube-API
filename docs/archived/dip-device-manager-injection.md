# DIP Fix — Device Manager Injection (2026-06-13)

## Problem
`_detect_device()` duplicated across 5 files despite `TorchDeviceManager` existing as the centralized IDeviceManager implementation. Violation of Dependency Inversion Principle (DIP).

## Files Changed
| File | Change |
|---|---|
| `faster_whisper_manager.py` | Removed `_detect_device()`, injected `device_mgr = TorchDeviceManager()` in `__init__`, updated `load_model()` to use manager |
| `openai_whisper_manager.py` | Same pattern + added import for `TorchDeviceManager` |
| `whisperx_manager.py` | Same pattern + added import for `TorchDeviceManager` |
| `processor.py:106` | `_detect_device()` now delegates to centralized `TorchDeviceManager(preferred_device).detect_device()` instead of inspecting manager state |

## Validation
- All 4 files pass `py_compile` syntax check.
- Validated inside Docker container (`ytcaption-se4-audio-transcriber-api`):
  - `FasterWhisperModelManager().device_mgr.detect_device()` → returns `"cuda"` (RTX 3090).

## Not Changed
- `infrastructure/whisper_engine.py:80` — uses different validation (`cuda.init()`), higher blast radius, deferred.
