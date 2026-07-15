# PLAN — Pendências Restantes do Monorepo YTCaption

**Última atualização:** 2026-07-14
**Fase atual:** Resolver 4 pendências restantes (testes + deprecation warnings)
**Status anterior:** Clean Code Audit 54/54 COMPLETO + todos os testes unitários passando

---

## Pendência 1: SE9 Mock Fix — testes FFmpeg falham com code 254

**Problema:** 9 testes em `test_ffmpeg_utils.py` patcham `ffmpeg_utils.run_ffmpeg` (re-export facade), mas o código chama `run_ffmpeg` do módulo original → mock não intercepta → FFmpeg roda com arquivo inexistente → RuntimeError code 254.

**Fix:** Trocar target do patch para o módulo onde a função é definida:

| Testes | Patch errado | Patch correto |
|---|---|---|
| `test_create_segment_*`, `test_create_title_card_*` | `ffmpeg_utils.run_ffmpeg` | `ffmpeg_segments.run_ffmpeg` |
| `test_concat_*` | `ffmpeg_utils.run_ffmpeg` | `ffmpeg_concat.run_ffmpeg` |
| `test_add_audio_*`, `test_trim_*` | `ffmpeg_utils.run_ffmpeg` | `ffmpeg_assembly.run_ffmpeg` |

**Arquivo:** `services/se9-make-video-img/tests/unit/test_ffmpeg_utils.py`
**Status:** `[ ]` Pendente

---

## Pendência 2: SE3 Lazy Imports — noisereduce não instalado

**Problema:** `app/services/__init__.py` importa `AudioNormalizer` eagerly, que tem `import noisereduce` no nível de módulo. Módulo é legacy (o `AudioProcessor` ativo não usa noisereduce).

**Fix:** Mover `import noisereduce as nr`, `import soundfile as sf`, `import librosa` dos imports de módulo para dentro dos métodos `_remove_noise()` e `_isolate_vocals()`.

**Arquivo:** `services/se3-audio-normalization/app/services/audio_normalizer.py`
**Status:** `[ ]` Pendente

---

## Pendência 3: SE4/SE9 Testes Timeout — hang por modelo pesado

**Problema SE4:** Testes de resiliência carregam modelo Whisper real (10-60s cada, sem timeout). 10 testes carregam modelo independentemente.

**Fix SE4:**
- Criar `pytest.ini` com `addopts = -m "not slow and not real and not resilience"`
- Adicionar `pytest.mark.timeout(120)` nos testes que carregam modelo real

**Problema SE9:** Testes E2E rodam FFmpeg real com Ken Burns (até 300s). Fixture `services_online` usa async-wrapping-sync com risco de deadlock.

**Fix SE9:**
- Adicionar `addopts = -m "not e2e"` no `pytest.ini`
- Converter `services_online` para httpx sync
- Mover checks de import-time para fixtures

**Arquivos:**
- `services/se4-audio-transcriber/pytest.ini` (novo)
- `services/se4-audio-transcriber/tests/resilience/*.py`
- `services/se9-make-video-img/pytest.ini` (atualizar)
- `services/se9-make-video-img/tests/e2e/*.py`
- `services/se9-make-video-img/tests/conftest.py`

**Status:** `[ ]` Pendente

---

## Pendência 4: Pydantic v2 Deprecation — Field(env=...) em 4 serviços

**Problema:** 62 campos em 4 serviços usam `Field(env="VAR")` deprecated no Pydantic V2. O `SettingsConfigDict` já mapeia automaticamente.

**Fix:** Remover `env=` de todos os campos. Para 2 campos com `PROCESSING__` (duplo underscore), usar `validation_alias`.

| Serviço | Campos | Arquivo |
|---|---|---|
| SE3 | 19 | `app/core/config.py` |
| SE6 | 11 | `app/core/config.py` |
| SE8 | 18 | `app/core/config.py` |
| SE10 | 14 | `app/core/config.py` |

**Status:** `[ ]` Pendente

---

## Ordem de Execução

| # | Pendência | Esforço | Arquivos |
|---|---|---|---|
| 1 | SE9 mock fix | Baixo | 1 |
| 2 | SE3 lazy imports | Baixo | 1 |
| 3 | SE3 Pydantic fix | Baixo | 1 |
| 4 | SE6/SE8/SE10 Pydantic fix | Baixo | 3 |
| 5 | SE4 pytest.ini + timeout markers | Médio | 4 |
| 6 | SE9 pytest.ini + timeout + fixture fix | Médio | 4 |
