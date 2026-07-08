# SOLID Refactoring Plan — All Services

## Ranking Geral (Pior → Melhor)

| Rank | Service | Linhas | Nota | Esforço Est. |
|------|---------|--------|------|-------------|
| **10º** | **SE8** image-generation | 10,355 | **F** | 40-60h |
| **9º** | **SE11** clothes-removal | 8,056 | **F** | 50-70h |
| **8º** | **SE6** youtube-search | 5,382 | **D** | 18-22h |
| **7º** | **SE9** make-video-img | 2,184 | **D** | 14-18h |
| **6º** | **SE1** orchestrator | — | **C** | ~8h |
| **5º** | **SE2** video-downloader | — | **C** | ~6h |
| **4º** | **SE3** audio-normalization | — | **C** | ~6h |
| **3º** | **SE4** audio-transcriber | — | **C** | ~6h |
| **2º** | **SE10** clothes-segmentation | 1,936 | **C+** | 12-18h |
| **1º** | **SE7** audio-generation | 1,860 | **B-** | 6-8h |

## Top 5 God Modules (Piores do Monorepo)

1. **SE5 `celery_tasks.py`** — 2,078 linhas (1 arquivo = 5+ responsabilidades)
2. **SE11 `_helpers.py`** — 1,045 linhas (config loading + image utils + scoring + detection)
3. **SE6 `channel.py`** — 856 linhas (3 estratégias de parsing YouTube)
4. **SE8 `worker.py`** — 1,472 linhas (8 responsabilidades num arquivo)
5. **SE11 `pose_detector.py`** — 888 linhas (dataclasses + detector + renderer + CLI)

## Top 5 God Functions

1. **SE11 `run_nsfw()`** — 618 linhas (10 stages monolíticas)
2. **SE11 `run_nsfw_experimental()`** — 638 linhas (70% duplicado do anterior)
3. **SE5 celery task handler** — ~400+ linhas
4. **SE6 `extract_channel_metadata()`** — ~380 linhas (5 estratégias YouTube)
5. **SE8 `_apply_inpaint()`** — 257 linhas (VAE + mask + LoRA + CUDA cleanup)

## Bare Except (catch-all)

| Service | Ocorrências |
|---------|-------------|
| SE8 | **74** |
| SE11 | 53 |
| SE1-SE5 (total) | 98 |
| SE6 | 12+ |
| SE7 | 8 |
| SE10 | 17 |

## Top Prioridades de Refatoração

| # | Arquivo | Problema | Esforço | Impacto |
|---|---------|----------|---------|---------|
| 1 | SE5 `celery_tasks.py` | God Module 2,078L | 12h | ⭐⭐⭐ |
| 2 | SE11 `_helpers.py` | God Module 1,045L | 12h | ⭐⭐⭐ |
| 3 | SE11 pipelines | God Functions 618L+638L | 24h | ⭐⭐⭐ |
| 4 | SE8 `worker.py` | God Module 1,472L | 16h | ⭐⭐⭐ |
| 5 | SE6 `ytbpy/` | 3 God Modules (2,005L) | 12h | ⭐⭐ |
| 6 | SE9 zero DIP | 4 VideoJobStore instances | 5h | ⭐⭐ |
| 7 | SE10 `segmentor.py` | God Class 457L | 6h | ⭐⭐ |

## Detalhes por Service

### SE8 — Image Generation (Port 8008) — NOTA F

| Métrica | Valor |
|---------|-------|
| Arquivos fonte | 37 Python files |
| Total linhas | ~10,355 |
| Maior arquivo | `worker.py` — 1,472 linhas |
| Files >300 linhas | 10 |

**Top 3 Violações:**

1. **God Module — `worker.py` (1,472 linhas) — CRITICAL**
   - 8 responsabilidades: Task detection, AsyncTask building, File I/O, IP-Adapter loading, Inpaint pipeline, ControlNet, Orchestrator, Worker loop
   - God Functions: `_apply_inpaint()` 257L, `process_generate()` 207L, `_apply_ip_adapter()` 170L
   - Ref: `services/se8-image-generation/app/services/worker.py:742-996`

2. **God Module — `pipeline.py` (836L) + `model_manager.py` (792L) — HIGH**
   - `process_diffusion()` 249 linhas
   - Ref: `services/se8-image-generation/app/services/pipeline.py:532-780`

3. **74 Bare Except — HIGH**
   - Silent swallowing em 12+ locais
   - `worker.py:1366-1414` — finally block com 6 catch-alls

**Esforço estimado:** 40-60h

---

### SE11 — Clothes Removal (Port 8011) — NOTA F

| Métrica | Valor |
|---------|-------|
| Arquivos fonte | 16 Python files |
| Total linhas | ~8,056 |
| Maior arquivo | `_helpers.py` — 1,045 linhas |
| Files >300 linhas | 8 |

**Top 3 Violações:**

1. **God Function — `run_nsfw()` (618L) e `run_nsfw_experimental()` (638L) — CRITICAL**
   - 10 stages monolíticas: SE10 detect → mask → SE10 clothes → IP-Adapter → FaceID → SE8 inpaint → pose validate → score → post-process → save
   - 70% código duplicado entre as duas versões
   - Ref: `services/se11-clothes-removal/app/services/pipeline_nsfw.py:293-910`

2. **God Module — `_helpers.py` (1,045 linhas) — CRITICAL**
   - Catch-all: YAML config loading (300L), NSFWConfig (80 fields), image utils, scoring, detection fallbacks, upscale, face restore
   - Ref: `services/se11-clothes-removal/app/services/_helpers.py:1-1045`

3. **God Module — `pose_detector.py` (888 linhas) — HIGH**
   - Dataclasses + detector + comparator + renderer + CLI `main()` (133L) num arquivo
   - Ref: `services/se11-clothes-removal/app/validators/pose_detector.py:1-888`

**Esforço estimado:** 50-70h

---

### SE6 — YouTube Search (Port 8006) — NOTA D

| Métrica | Valor |
|---------|-------|
| Arquivos fonte | 33 Python files |
| Total linhas | 5,382 |
| Maior arquivo | `channel.py` — 856 linhas |

**Top 3 Violações:**

1. **God Modules — `channel.py` (856L), `playlist.py` (684L), `search.py` (465L) — HIGH**
   - `extract_channel_metadata()` ~380 linhas com 5 estratégias YouTube
   - `_extract_playlist_videos()` ~190 linhas duplicado em `_fetch_continuation_page()` ~180 linhas
   - Ref: `services/se6-youtube-search/app/services/ytbpy/channel.py:210-588`

2. **Código Duplicado — playlist.py — HIGH**
   - Video extraction logic copiada 2x (~180 linhas)
   - Duration parsing copiado 3x

3. **Hardcoded Values + No DIP — MEDIUM-HIGH**
   - INNERTUBE_API_KEY copiado 3x em arquivos diferentes
   - Concrete `RedisJobStore` sem interface

**Esforço estimado:** 18-22h

---

### SE9 — Make Video IMG (Port 8009) — NOTA D

| Métrica | Valor |
|---------|-------|
| Arquivos fonte | 17 Python files |
| Total linhas | 2,184 |

**Top 3 Violações:**

1. **Zero DIP — HIGH**
   - `VideoJobStore()` instanciado 4x independentemente em 4 arquivos
   - Sem interfaces, sem DI, sem singleton
   - Ref: `services/se9-make-video-img/app/api/routes.py:24`

2. **God Module — `ffmpeg_utils.py` (384L) — MEDIUM-HIGH**
   - 10 responsabilidades: run_ffmpeg, get_audio_duration, create_title_card, create_segment, concat_segments, concat_simple, concat_batched, add_audio, trim_to_duration, probe

3. **Hardcoded Values — MEDIUM**
   - `MAX_SEGMENTS=12`, `MIN_SCENE_DURATION=3.0`, API keys como defaults

**Esforço estimado:** 14-18h

---

### SE10 — Clothes Segmentation (Port 8010) — NOTA C+

| Métrica | Valor |
|---------|-------|
| Arquivos fonte | 12 Python files |
| Total linhas | ~1,936 |
| Maior arquivo | `segmentor.py` — 457 linhas |

**Top 3 Violações:**

1. **God Class — `segmentor.py` (457L) — MEDIUM-HIGH**
   - `segment()` 122 linhas monolíticas
   - Model lifecycle + preprocessing + detection + filtering + annotation + pose

2. **Route Mixed com Service Logic — MEDIUM**
   - `segment.py` (147L) com validação + dispatch + GPU unload + response building
   - `ThreadPoolExecutor` em module level

3. **Module-Level Mutable State — MEDIUM**
   - `_segmentor`, `_idle_timer` como globals em `state.py`

**Esforço estimado:** 12-18h

---

### SE7 — Audio Generation (Port 8007) — NOTA B-

| Métrica | Valor |
|---------|-------|
| Arquivos fonte | 20 Python files |
| Total linhas | 1,860 |

**Top 3 Violações:**

1. **Interfaces existem mas não fully used — MEDIUM**
   - ABCs definidos (`IModelManager`, `IJobStore`, `IVoiceStore`, `ITTSGenerator`)
   - `get_voice_manager()` retorna `Any` (perde type safety)
   - `voices_routes.py` tipa como concrete `VoiceProfileManager`

2. **Dead Config Values — MEDIUM-HIGH**
   - 6 constants mortas: `DRAMATIC_EXAGGERATION`, `DRAMATIC_CFG_WEIGHT`, `DRAMATIC_TEMPERATURE`, `NEUTRAL_EXAGGERATION`, `NEUTRAL_CFG_WEIGHT`, `NEUTRAL_TEMPERATURE`
   - .env vs constants CONFLICT: `CELERY_TASK_SOFT_TIME_LIMIT` 3300 vs 2700 (600s discrepancy)

3. **Bare Except Pattern — MEDIUM**
   - 8x `except (CircuitBreakerOpenError, Exception)` — CircuitBreakerOpenError é subclasse de Exception (catch específico é dead code)

**Esforço estimado:** 6-8h

---

## Observações Importantes

- **SE11** já passou por refatoração SOLID mas `_helpers.py` e pipelines continuam como God Functions — a refatoração anterior focou em config/dataclass mas não decompôs as funções principais
- **SE8** tem o maior God Module do monorepo (`worker.py` 1,472L) e 74 bare excepts — pior caso de debugging
- **SE7** é o melhor estruturado — já tem interfaces ABC mas não usa fully
- **SE5** `celery_tasks.py` é o arquivo único mais grande do monorepo (2,078L)
- **Total estimado de refatoração: ~160-200 horas**

## Ordem de Execução Recomendada

1. **SE5** `celery_tasks.py` (12h) — maior impacto single-file
2. **SE11** `_helpers.py` (12h) — split em 4 módulos
3. **SE11** pipelines (24h) — Template Method para compartilhar 70% código
4. **SE8** `worker.py` (16h) — extrair 5 módulos de service
5. **SE6** `ytbpy/` (12h) — refatorar parsing YouTube
6. **SE9** DIP (5h) — interfaces + DI container
7. **SE10** `segmentor.py` (6h) — extrair detector/annotator/filter
8. **SE1-SE4** (~26h) — auditoria detalhada pendente

## Status

- [x] Auditoria completa SE6, SE7, SE8, SE9, SE10, SE11
- [ ] Auditoria detalhada SE1, SE2, SE3, SE4, SE5
- [x] SE5 `celery_tasks.py` refactoring (commit `1e027113` — 2,078L → 13 módulos)
- [x] SE11 `_helpers.py` refactoring (commit `eb6797b2` — 1,045L → 6 módulos)
- [ ] SE11 pipelines Template Method (24h — run_nsfw 618L + run_nsfw_experimental 638L compartilham ~70% código)
- [ ] SE8 `worker.py` refactoring (16h — 1,472L God Module, extrair 5 módulos)
- [ ] SE6 `ytbpy/` refactoring (12h — 3 God Modules, eliminar duplicação)
- [ ] SE9 DIP refactoring (5h — interfaces + DI container)
- [ ] SE10 `segmentor.py` refactoring (6h — extrair detector/annotator/filter)
