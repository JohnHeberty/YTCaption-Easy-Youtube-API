# PLAN — Pendências do Monorepo YTCaption

**Última atualização:** 2026-07-13

---

## 🔴 CRÍTICO

| # | Serviço | Problema | Status |
|---|---------|----------|--------|
| 1 | SE1 | Container **UNHEALTHY** — orchestrator health check falhando | `[x]` Fix 2026-07-10 |

---

## 🟠 ALTO

| # | Serviço | Problema | Status |
|---|---------|----------|--------|
| 2 | SE11 | Testado com 1 única imagem (TESTE1.jpg) — precisa mais validação | `[x]` 6 fixtures + 54 parametrized tests 2026-07-13 |
| 3 | SE11 | **AI Image Detection** não implementado — fotos reais entram no NSFW pipeline | `[x]` Implemented 2026-07-10 |
| 4 | SE11 | Ghost face no pescoço — artefato visual | `[x]` Negative 2.2 + ghost zone applied to both pipelines 2026-07-13 |
| 5 | SE11 | Edge artifacts — restos de roupa nas bordas | `[x]` dilation_pct=0.03 + 7x7 closing kernel in both pipelines 2026-07-13 |
| 6 | SE8 | `worker.py` ainda 1,161 linhas — precisa decompor mais | `[x]` 1161→388L 2026-07-10 |
| 7 | SE8 | 74 bare `except Exception:` — engolem erros silenciosamente | `[x]` 9 silent blocks fixed 2026-07-10 |
| 8 | SE6 | `channel.py` 848 linhas — precisa decompor | `[x]` 848→117L 2026-07-10 |
| 9 | SE4 | `job_state_updater.py` com ~25 `type: ignore` suppressions | `[x]` 24/30 removed 2026-07-10 |

---

## 🟡 MÉDIO

| # | Serviço | Problema | Status |
|---|---------|----------|--------|
| 10 | SE7 | VRAM leak — fix aplicado mas precisa monitoramento | `[x]` GPU check + VRAM tracking in health 2026-07-10 |
| 11 | SE11 | Composite score optimization — landmark drift | `[x]` strength_ceiling=0.92 + graduated early stop 2026-07-10 |
| 12 | SE11 | Multi-person support — pipeline assume 1 pessoa | `[x]` MultiPersonPipeline + dispatch in run_nsfw (auto-detect >1 person). Tests: 118 pass. 2026-07-13 |
| 13 | SE11 | Face Restoration — modelos baixados, não integrados | `[x]` Already wired, added face_restore_default config 2026-07-10 |
| 14 | SE11 | Advanced Blending — Poisson editing planejado não implementado | `[x]` poisson_blend added, blend mode option added 2026-07-10 |
| 15 | SE8 | GPU mount workaround para driver 590.x | `[x]` Added libnvidia-encode/decode.so.1 mounts + mimalloc in Dockerfile.gpu + LD_PRELOAD in docker-compose.yml. Host fix: `apt install nvidia-container-toolkit=1.20.0~rc.1-1`. 2026-07-13 |
| 16 | SE8 | Python RSS retention: 13.64GB não retornados ao OS | `[x]` Added LD_PRELOAD=mimalloc + MIMALLOC_PURGE_DELAY=0 + CUDA_LAUNCH_BLOCKING=1 to docker-compose.yml (api + worker). Mimalloc installed in Dockerfile.gpu base stage. 2026-07-13 |

---

## 🔵 BAIXO

| # | Serviço | Problema | Status |
|---|---------|----------|--------|
| 17 | SE11 | show/ permission denied no container | `[x]` Volume mount added 2026-07-10 |
| 18 | SE11 | Old stuck jobs no Redis | `[x]` TTL 2d + stale cleanup in list_jobs |
| 19 | SE11 | Lazy-load IP-Adapter/ControlNet (~2.7GB RAM) | `[x]` Already lazy-loaded on demand |
| 20 | SE11 | Lazy-load ControlNet Union (~2.4GB RAM) | `[x]` Already lazy-loaded on demand |
| 21 | SE9 | `ffmpeg_utils.py` 521 linhas — 10 responsabilidades | `[x]` 521→57L + 5 modules 2026-07-10 |
| 22 | Docker | 4 containers órfãos rodando (build leftovers) | `[x]` N/A — MCP servers (repomix+serena) |

---

## ✅ Concluído (referência — commits recentes)

| Commit | Data | Descrição |
|--------|------|-----------|
| `3861e70e` | 2026-07-10 | TRSD activation + fps bug fix |
| `39992ec0` | 2026-07-09 | SE5 DDD architecture (Phases 1-6) |
| `6df49212` | 2026-07-09 | Event publishing fix + stage display names |
| `6b4eeb54` | 2026-07-09 | 15 unit tests for stage callback |
| `7edce3cc` | 2026-07-09 | Real-time stage tracking in DDD path |
| `b12902e5` | 2026-07-09 | SE5 E2E real support |
| `84d57a44` | 2026-07-09 | SE6 YouTube Shorts extraction fix |
| `b87b6225` | 2026-07-10 | Event publishing + legacy code cleanup |
| `ef468235` | 2026-07-10 | SE4 DLQ + SE5 user tier |
| `11b77c3f` | 2026-07-10 | SE8 TODO cleanup |

---

## Refatoração SOLID (histórico)

### Status

| Item | Status |
|------|--------|
| Auditoria completa SE6-SE11 | `[x]` Feita |
| Auditoria detalhada SE1-SE5 | `[x]` Feita |
| SE5 `celery_tasks.py` refactoring | `[x]` 2,078L → 13 módulos |
| SE11 `_helpers.py` refactoring | `[x]` 1,045L → 6 módulos |
| SE10 `segmentor.py` refactoring | `[x]` 457L → 377L |
| SE9 DIP refactoring | `[x]` singleton |
| SE6 `ytbpy/` refactoring | `[x]` duration parsing dedup |
| SE8 `worker.py` refactoring | `[x]` 1,472L → 1,161L |
| SE11 pipelines Template Method | `[x]` 910L+776L → 257L+307L |

### God Functions restantes

| # | Arquivo | Linhas | Problema |
|---|---------|--------|----------|
| 1 | SE8 `worker.py` | 1,161 | Ainda precisa decompor mais |
| 2 | SE6 `channel.py` | 848 | 3 estratégias de parsing YouTube |
| 3 | SE9 `ffmpeg_utils.py` | 521 | 10 responsabilidades |
| 4 | SE11 `pose_detector.py` | 888 | Dataclasses + detector + renderer + CLI |

---

## Métricas do Monorepo

| Service | Arquivos | Linhas | Nota | Esforço Est. |
|---------|----------|--------|------|-------------|
| SE8 | 37 | ~10,355 | F | 40-60h |
| SE11 | 16 | ~8,056 | F | 50-70h |
| SE6 | 33 | 5,382 | D | 18-22h |
| SE9 | 17 | 2,184 | D | 14-18h |
| SE10 | 12 | ~1,936 | C+ | 12-18h |
| SE7 | 20 | 1,860 | B- | 6-8h |
| SE1-SE5 | — | — | C | ~26h |
| **Total** | — | — | — | **~160-200h** |

### Bare Except (catch-all)

| Service | Ocorrências |
|---------|-------------|
| SE8 | 74 |
| SE11 | 53 |
| SE1-SE5 (total) | 98 |
| SE6 | 12+ |
| SE7 | 8 |
| SE10 | 17 |
