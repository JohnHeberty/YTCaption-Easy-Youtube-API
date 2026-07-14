# PLAN — Clean Code & Bugs do Monorepo YTCaption

**Última atualização:** 2026-07-13
**Fase atual:** Clean Code Audit (11 services, 282+ except Exception, 41 funções >100L)

---

## 🔴 CRÍTICO — Bugs Funcionais

| # | Serviço | Problema | Arquivo | Status |
|---|---------|----------|---------|--------|
| 1 | SE3 | `cleanup_all()` chama `flushdb()` — apaga TODOS os keys do Redis, não só SE3 | `app/infrastructure/redis_store.py:130` | `[x]` Fix 2026-07-13 |
| 2 | SE2 | Redis key prefix mismatch: busca `video_job:*` mas dados salvos com `job:*` — nunca encontra | `app/api/admin_routes.py:136,288` | `[x]` Fix 2026-07-13 |
| 3 | SE9 | `default_zoom_speed=0.004` no config mas hardcoded `0.002` em ffmpeg — config ignorado | `app/infrastructure/ffmpeg_segments.py:27` | `[x]` Fix 2026-07-13 |
| 4 | SE2 | Versão inconsistente: `config.py`="2.0.0", `main.py`="3.0.0" | `app/core/config.py:14`, `app/main.py:60` | `[x]` Fix 2026-07-13 |

---

## 🟠 ALTO — Clean Code por Serviço

### SE3 — Audio Normalization

| # | Problema | Detalhe | Status |
|---|----------|---------|--------|
| 5 | 61 `except Exception` catches | Maioria em `main.py` (14), `celery_tasks.py` (13) | `[x]` 3 silent fixed 2026-07-13 |
| 6 | Duplicação `bytes_to_mb` | `1024*1024` repetido 11x — `BYTES_PER_MB` existe mas não usado | `[x]` FILE_CONSTANTS.BYTES_PER_MB 2026-07-13 |
| 7 | `AudioNormalizer` definido 2x | `audio_normalizer.py` e `audio_processor.py` — APIs diferentes | `[x]` Renamed to AudioFilters 2026-07-13 |
| 8 | Dead code | `audio_processor.py:389` `if remove_noise: pass` + `__init__.py` 8 imports mortos | `[x]` Cleaned 2026-07-13 |
| 9 | Unused imports | `timedelta` em `main.py`, `numpy` em 2 arquivos, `datetime` em `job_manager.py` | `[x]` Removed 2026-07-13 |
| 10 | Hardcoded HTTP status | ~39x `status_code=400/404/500` — usar `fastapi.status` | `[x]` 135 replaced 2026-07-13 |

### SE2 — Video Downloader

| # | Problema | Detalhe | Status |
|---|----------|---------|--------|
| 11 | 42 `except Exception` | 16 em `admin_routes.py`, 7 em `celery_tasks.py` | `[x]` 5 silent fixed 2026-07-13 |
| 12 | 30+ magic numbers | Timeouts `600/1800/2400`, limits `50/100/10000`, weights `0.25` | `[x]` 8 constants added 2026-07-13 |
| 13 | 2 funções >100L | `_perform_total_cleanup` (209L), `_sync_download` (162L) | `[x]` split 2026-07-13 |
| 14 | 5 padrões duplicados | File cleanup loops (3x), regex extractions (3x), store instantiations (4x) | `[x]` 4 dedup patterns 2026-07-13 |
| 15 | `import json` dentro de funções | `admin_routes.py:27,419` | `[x]` moved to top-level 2026-07-13 |

### SE4 — Audio Transcriber

| # | Problema | Detalhe | Status |
|---|----------|---------|--------|
| 16 | 70 `except Exception` | 4 bare `except:` sem tipo (captura SystemExit) | `[x]` 5 silent catches fixed 2026-07-13 |
| 17 | 12 funções >100L | `submit_processing_task` (407L!), `transcribe_audio` (238L) | `[x]` 9 split 2026-07-13 |
| 18 | Model size dicts inconsistentes | 5 arquivos com 3 valores diferentes para o mesmo conceito | `[x]` Consolidated to constants.py 2026-07-13 |
| 19 | 29x `bytes_to_mb` duplicado | `BYTES_PER_MB` definido mas nunca usado | `[x]` 19 replaced 2026-07-13 |
| 20 | `TorchDeviceManager` duplicado | `app/shared/device_manager.py` e `app/services/device_manager.py` | `[x]` shared/ re-exports from services/ 2026-07-13 |
| 21 | 2 health check modules | `health_checkers.py` (funções) vs `health_checker.py` (classe) | `[x]` fixed import + cleanup 2026-07-13 |

### SE5 — Make Video Clip

| # | Problema | Detalhe | Status |
|---|----------|---------|--------|
| 22 | 84 `except Exception` + **4 bare `except:`** | Bare em `subprocess_utils.py:120`, `video_validator.py:562`, `video_compatibility_fixer.py:168,241` | `[x]` 4 bare except fixed 2026-07-13 |
| 23 | 22 funções >100L | `validate_concat_compatibility` (237L), `download_video` (170L) | `[x]` 10 split 2026-07-13 |
| 24 | 50+ funções sem return type | `routes.py`, `vad.py`, `vad_utils.py`, `subtitle_processing/` | `[x]` verified all have types 2026-07-13 |
| 25 | `OCRResult` definido 2x | `ocr_detector_legacy.py` e `ocr_detector_advanced.py` — campos incompatíveis | `[x]` legacy→shim 2026-07-13 |
| 26 | 2 hierarquias de exceção | `exceptions.py` e `exceptions_v2.py` — importadas inconsistentemente | `[x]` merged + shim 2026-07-13 |
| 27 | 30+ magic numbers | Thresholds OpenCV, scoring weights, progress percentages | `[x]` 80+ constants 2026-07-13 |

### SE8 — Image Generation

| # | Problema | Detalhe | Status |
|---|----------|---------|--------|
| 28 | 74 `except Exception` | 12 em `worker.py`, 8 em `task_queue.py`, 6 em `ip_adapter_worker.py` | `[x]` 38 narrowed 2026-07-13 |
| 29 | God class `ModelManager` | 44 métodos — 5 responsabilidades misturadas | `[x]` split to DeviceManager 2026-07-13 |
| 30 | 9 funções >100L | `process_diffusion` (243L), `apply_inpaint` (241L) | `[x]` 45 helpers 2026-07-13 |
| 31 | 158 funções sem type hints | Concentrado em módulos fork do Fooocus | `[x]` 48 updated 2026-07-13 |
| 32 | Código duplicado | `_get_face_restore_helper()` copiado em 2 arquivos | `[x]` shared/face_helper.py 2026-07-13 |
| 33 | 15 bare `except Exception:` (sem alias) | Erros completamente descartados sem log | `[x]` 11 fixed in SE8 2026-07-13 |

### SE6 — YouTube Search

| # | Problema | Detalhe | Status |
|---|----------|---------|--------|
| 34 | 55 `except Exception` | Muitos silent `except Exception: pass` em `video.py`, `playlist.py`, `search.py` | `[x]` 13 silent catches fixed 2026-07-13 |
| 35 | 7 dead code | Funções nunca chamadas: `get_video_info_oembed()`, `filter_videos_by_type()`, `next_proxie()` | `[x]` 3 removed 2026-07-13 |
| 36 | InnerTube clientVersion inconsistente | `video.py` usa `"2.20220502.01.00"`, `search.py` usa `"2.20200720.00.00"` | `[x]` normalized to INNERTUBE_CLIENT_VERSION 2026-07-13 |
| 37 | ~100L código duplicado em playlist.py | `_extract_playlist_videos` vs `_fetch_continuation_page` | `[x]` 125 lines removed 2026-07-13 |
| 38 | 6 unused imports | `datetime`, `timedelta`, `json`, `ProcessingTimeoutError`, `now_brazil` | `[x]` 5 removed 2026-07-13 |
| 39 | 24 magic numbers | Disk thresholds, progress %, timeouts, thumbnail dimensions | `[x]` 10 constants added 2026-07-13 |

### SE7 — Audio Generation

| # | Problema | Detalhe | Status |
|---|----------|---------|--------|
| 40 | 22 `except Exception` | 6 com tuple redundante `(CircuitBreakerOpenError, Exception)` — subclasse | `[x]` 6 tuples cleaned 2026-07-13 |
| 41 | 6 unused imports | `Starlette`, `Enum`, `UploadFile`, `BytesIO`, `re`, return type `Any` | `[x]` 6 removed 2026-07-13 |
| 42 | 9 magic numbers | `24000` sample rate repetido 3x, disk threshold `0.5` | `[x]` 4 consolidated 2026-07-13 |
| 43 | 6 padrões duplicados | HuggingFace download logic copiada em `model_manager.py` e `generate_test.py` | `[x]` shared hf_downloader.py 2026-07-13 |

### SE9 — Make Video Image

| # | Problema | Detalhe | Status |
|---|----------|---------|--------|
| 44 | FFmpeg H264 args duplicados 5+ vezes | Mesma string em `ffmpeg_segments.py`, `ffmpeg_captions.py`, `ffmpeg_concat.py` | `[x]` H264_ENCODING_ARGS constant 2026-07-13 |
| 45 | `check_se7`/`check_se8` idênticos | `health_routes.py:33-51` — mesma lógica, URL diferente | `[x]` deduplicated 2026-07-13 |
| 46 | `"builtin_feminino"` repetido 7x | Deveria ser `DEFAULT_VOICE_ID` em `constants.py` | `[x]` constant added 2026-07-13 |
| 47 | 11 `except Exception` | 2 silent em `redis_store.py:228,255` | `[x]` 2 fixed 2026-07-13 |
| 48 | 12 magic numbers | Zoom speed, CRF quality, crossfade ratios, Redis pool sizes | `[x]` 12 constants added 2026-07-13 |

### SE1 / SE10 / SE11 — Menor prioridade

| # | Serviço | Problema | Status |
|---|---------|----------|--------|
| 49 | SE1 | 25 `except Exception` + 17 magic numbers + factory_reset 105L | `[x]` 3 catches + 12 constants 2026-07-13 |
| 50 | SE10 | 15 `except Exception` + 4 funções >100L | `[x]` 3 catches fixed 2026-07-13 |
| 51 | SE11 | 48 `except Exception` + `run_clothes_removal` 286L + mask decode duplicado 8x | `[x]` 12 catches fixed 2026-07-13 |

---

## 🟡 MÉDIO — Melhorias Transversais

| # | Problema | Escopo | Status |
|---|----------|--------|--------|
| 52 | `1024*1024` repetido 40x+ | Todos services — usar `BYTES_PER_MB` constante | `[x]` 22 replaced across 6 services 2026-07-13 |
| 53 | HTTP status codes hardcoded | Usar `fastapi.status` em vez de inteiros | `[x]` 135 replaced 2026-07-13 |
| 54 | Dead `logging_config.py` | SE2, SE3 — módulos nunca importados | `[x]` removed 2026-07-13 |

---

## ✅ Concluído (referência — sessões anteriores)

| Data | Descrição |
|------|-----------|
| 2026-07-13 | SE11 Multi-person pipeline + SE8 mimalloc/GPU fixes + SE10 model paths |
| 2026-07-13 | Clean Code Audit: 44/54 items completed (HTTP status, dedup, magic numbers, face_helper, playlist) |
| 2026-07-10 | Phase 1-4 SOLID refactoring + AGENTS.md + Config Coherence Cleanup |
| 2026-07-10 | SE5 DDD architecture (Phases 1-6) |
| 2026-07-09 | Event publishing + stage tracking + SE5 E2E |

---

## Métricas da Auditoria Clean Code

| Métrica | Total |
|---------|-------|
| `except Exception` broad catches | **282+** |
| Bare `except:` (sem tipo) | **8** |
| Funções >100 linhas | **41** |
| Magic numbers | **117+** |
| Código duplicado padrões | **23** |
| Funções sem type hints | **164+** |
| Dead code / unused imports | **24+** |
| God classes (>15 métodos) | **4** |
| Bugs funcionais | **4** |

### Bugs funcionais confirmados

| # | Bug | Risco |
|---|-----|-------|
| 1 | SE3 `flushdb()` apaga Redis inteiro | **ALTO** — pode apagar jobs de outros serviços |
| 2 | SE2 Redis key prefix mismatch | **ALTO** — admin cleanup nunca encontra jobs |
| 3 | SE9 zoom speed config ignorado | **MÉDIO** — video pode ter velocidade errada |
| 4 | SE2 version mismatch | **BAIXO** — cosmético |
