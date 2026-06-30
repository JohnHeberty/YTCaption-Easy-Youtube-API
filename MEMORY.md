# Estado Atual — Monorepo YTCaption

## Última sessão (2026-06-29)

### 🟢 NSFW v20 — PRODUCTION (Mask research + improvements)
- **Rota oficial:** `POST /jobs` (file upload) `mode="nsfw"`
- **Pipeline:** `pipeline_nsfw.py` (v20 — distance transform head mask)
- **Config ótima (TESTED v1-v10):**
  - **Head mask:** subtract clothes → distance transform (8px) → inflate → close (9px) → GaussianBlur (15px, σ=5) → clip to person
  - body_mask como inpaint (person - head) — cobre TODA a roupa
  - person_expanded clip (dilate 3x) — preenche gaps do SE10
  - face paste simples (sem feathered blend — causa ghost)
  - **face_protect_mask:** margin_above=0.50, margin_below=0.70, margin_sides=0.40
  - head_mask: max_head_pct=0.50, neck_margin_below=1.2, expand_up=1.5
  - **IP-Adapter:** original image (weight=0.4, stop=0.4) — preserva pose
  - strength 0.85/0.90/1.00 (3 tentativas progressivas)
  - field=0.618, erode=0
  - CFG 7.0, 40 steps, dpmpp_2m_sde_gpu, karras
  - NsfwPov 0.6, offset 0.1, add-detail 0.7
  - Inpaint patch LoRA v2.6: 582 keys at weight=1.0
  - **Reinhard color transfer** (LAB space, skin-only reference)
  - Pre-scale to min 1024px (avoids SE8 ESRGAN upscaler CUDA crash)
- **Exploration script:** `exploration/run_mask_pipeline.py`
  - Roda toda pipeline (SE10 masks + SE8 inpainting)
  - `--skip-inpaint` para só mascaras
  - Salva em `exploration/data/{image}/` com debug grid
- **SE8 CRITICAL FIX:** worker.py estava stale (916 linhas). Container SE8 = image-engine
  - docker cp worker.py + restart para carregar inpaint patch LoRA
  - Sem o patch LoRA: resultado era mancha pele lisa sem anatomia
- **Prompt positive:** NSFW×5, solo, bare skin, detailed anatomy, pose preservation, skin tone matching
- **Prompt negative:** deformed:1.3, extra face:1.8, pose change:1.5, skin tone mismatch
- **Compositing:** SE8 post_process + head paste + Reinhard color transfer
- **Head mask pipeline:** ellipse → subtract clothes → distance transform → inflate → close → blur → clip
> **Lições aprendidas:** Ver `LIÇÕES.md`
> **Pendências:** Ver `PENDENCIAS.md`

### Arquivos modificados nesta sessão
| Arquivo | Mudança |
|---------|---------|
| `services/se8-image-generation/app/services/worker.py` | Inpaint patch LoRA loading + use_fill fix |
| `services/se11-clothes-removal/app/services/pipeline_nsfw.py` | Body-mask, face protection, floodFill, prompts |

### Container SE8
- Nome: `image-engine` (NÃO `se8-image-engine`)
- Porta: 8008
- NÃO monta código via bind mount — código baked na imagem
- Para atualizar: `docker cp file.py image-engine:/app/app/path/ && docker restart image-engine`

## Sessão anterior (2026-06-26)

### 🟢 NSFW v18 — PRODUCTION (Fooocus migration + body-mask)
- **Rota oficial:** `POST /jobs` (file upload) `mode="nsfw"`
- **Pipeline:** `pipeline_nsfw.py` (v18 — body-mask + person_expanded + face paste)
- **Config óptima (PROVEN):**
  - body_mask como inpaint (não clothing mask)
  - 3.5% dilation adaptativa
  - erode_or_dilate=-3
  - morphOpen 3px + GaussianBlur 3px + morphClose 5px + vertical 1x7
  - strength=0.65, field=0.85
  - NsfwPov 0.3, add-detail-xl 1.0
  - Sem Reinhard LAB (pele correcta do SE8)
  - Smooth blend GaussianBlur 7px no resultado FINAL
- **Prompt positive:** NSFW×5, solo, same body position, unchanged pose, skin tone matching
- **Prompt negative:** (deformed:1.3), extra limbs, airbrushed, plastic skin, changing pose:1.5
- **head_adjusted:** 100% sólido (close + floodFill)
- **Compositing:** paste binário → GaussianBlur 7px blend → head force
- **GPU:** RTX 3090 24GB — quando CUDA assertion, `pkill -f python` no SE8
> **Lições aprendidas:** Ver `LIÇÕES.md`
> **Pendências:** Ver `PENDENCIAS.md`

### Modos antigos (DEPRECATED)
- `pipe_3layers_max`, `pipe_3layers`, `pipe_nsfw`, `pipe_nsfw_subtract`, `progressive` → todos redirecionam para `nsfw` (v17) com deprecation warning
- `nsfw_test` → alias para `nsfw` (mesmo pipeline v17)

### Config SE11
- `mode="nsfw"` = pipeline oficial (produção, v17 BEST RESULT)
- `mode="nsfw_test"` = alias para `nsfw` (mesmo pipeline v17)
- `mode="clothes"` = default (remoção padrão)
- `mode="person"` = remoção por pessoa
- Lustify NSFW (6.9GB) disponível mas NÃO usado (juggernautXL é melhor)
- GFPGAN/CodeFormer disponíveis mas não integrados

## Sessão anterior (2026-06-22)
- **UPGRADE-1.md Fase 1+2 CONCLUÍDA** — 8+ items implemented and tested (v24-v46)
- **UPGRADE-2.md ATUALIZADO** — 60+ abordagens testadas (v24-v82)
- **v6**: NSFW clothes-only + hard composite, Face=1.000, BG=0.0, Torso=2.2%, Bot=40%
- **Melhor rota**: `mode=progressive` (v83) — Face=1.000, Bot=62.9%, BG=0.3
- **Investigação NSFW (v24-v82)**: 60+ abordagens testadas
- **SE11 Quality Pipeline v2** — 6 improvements: auto erosion, coverage cap, max 3 objects, per-garment, webhook, HSV color transfer (reverted to BGR after testing)
- **Strict filtering**: max 3 objects by confidence, min confidence 0.10, coverage cap at 15% with erosion
- **Auto erosion**: erode_or_dilate computed from mask coverage (-5 to -30)
- **Per-garment mode**: optional flag to inpaint each mask separately
- **Webhook**: POST to webhook_url on job completion
- **Test results**: v21 (clothes) mean=2.3 PSNR=40.7dB, v22 (person) mean=2.8 PSNR=39.1dB
- **SE8 CUDA mitigation**: retry backoff 5/10/15s, cache clear reverted (broke inpainting)
- **Commits**: `e99c2e8`, `2ad5730`, `6e3d1e4`, `7631cd0`, `5d5659f`, `06b9c67`, `269856a`
- **Previous session commits**: `6f1b161`, `48cd6d9`, `e1bc46a`, `a340fac`, `4c0907d`, `84e5ddf`, `774dc7a`, `70a439a`
- **Fase 1**: Exception hierarchy consolidated (ServiceError→BaseServiceException), BaseJob dead code removed (135 lines), SE8 worker.py:481 bug fix, SE6 hardcoded API keys→get_innertube_api_key(), SE7 Celery mismatch fixed, SE7 test imports removed, SE8+SE10 Pydantic v2 config, rate_limiter utcnow→now(UTC), ResilientRedisStore._safe_call extraction
- **Fase 2**: SE9+SE11 already committed (redis_store._use_raw, redundant close removal, models cleanup)
- **Fase 3**: SE6 enum consolidation (removed duplicate SearchType/JobStatus from constants.py), f-string→%s logging, asyncio.run() replacement; SE7 generator re-raise fix (critical: swallowed errors→Celery false success)
- **Fase 4**: Removed 17 now_brazil fallbacks (SE1-SE4), SE1 exception consolidation (merged infrastructure→core), SE3 is_orphaned bug fix (fromisoformat on instance), SE4 processor.py cleanup
- **Fase 5**: SE5 undefined variable fixes (audio_base_path, input_path), duplicate OCRDetector removal, Optional[any]→np.ndarray (6 files), print→logger (19 instances), SE8 mutable default fix, SE8 dead enums.py removed
- **Pydantic v2 migration COMPLETE** — All 11 services + shared library, zero deprecation warnings

## Serviços Ativos

| Service | Port | Container | Status | Description |
|---|---|---|---|---|
| se1-orchestrator | 8001 | — | ✅ Healthy | Pipeline orchestrator |
| se2-video-downloader | 8002 | — | ✅ Healthy | Video download |
| se3-audio-normalization | 8003 | — | ✅ Healthy | Audio normalization |
| se4-audio-transcriber | 8004 | — | ✅ Healthy | Whisper transcription |
| se5-video-clip | 8005 | — | ✅ Healthy | Video clip generation |
| se6-youtube-search | 8006 | — | ✅ Healthy | YouTube search |
| se7-audio-generation | 8007 | — | ✅ Healthy | TTS Chatterbox (GPU) |
| se8-image-generation | 8008 | image-engine | ✅ Healthy | Fooocus SDXL (GPU), **inpainting functional** |
| se9-make-video-img | 8009 | se9-make-video-img | ✅ Healthy | Ken Burns video builder |
| se10-clothes-segmentation | 8010 | ytcaption-se10-clothes-segmentation | ✅ Healthy | GroundingDINO+SAM2 (CPU) |
| se11-clothes-removal | 8011 | se11-clothes-removal | ✅ E2E validated | SE10→SE8 inpaint pipeline |

## SE11 — Clothes Removal Service

### Arquitetura
Fluxo: imagem → SE10 (detecção de roupas + masks) → combina masks (union OpenCV) → SE8 (Fooocus inpaint) → resultado

### Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /jobs | ✅ | Criar job (image base64) |
| GET | /jobs | ✅ | Listar jobs |
| GET | /jobs/{id} | ✅ | Status do job |
| DELETE | /jobs/{id} | ✅ | Deletar job |
| GET | /jobs/{id}/download | ✅ | Download resultado |
| GET | /health | ❌ | Health check |
| GET | /health/deep | ❌ | Deep health (SE10+SE8) |
| GET | /ping | ❌ | Pong |
| GET | /admin/stats | ✅ | Estatísticas |
| POST | /admin/cleanup | ✅ | Cleanup |

### Validação SE11
- ✅ 11/11 testes unitários passando
- ✅ Todos os módulos py_compile OK
- ✅ API server inicia, health/ping respondem
- ✅ Deep health detecta SE8=ok, SE10=ok
- ✅ **E2E clothes mode**: SE11→SE10→SE8 → RGB 482×789, 398KB, ~40s, mean_diff=2.4, PSNR=40.5dB
- ✅ **E2E person mode**: SE11→SE10→SE8 → RGB 482×789, 404KB, ~35s, mean_diff=2.8, PSNR=39.3dB
- ✅ **SE8 direct inpainting**: 3 LoRAs (NsfwPov+detail+offset), 22s, PSNR=29.6dB
- ✅ **SE10 clothes**: 5 objects/5 masks, 15s
- ✅ **SE10 person**: 2 objects/2 masks, 15s
- ✅ **Face preservation**: 0% change in top 30% across all tests
- ✅ **Hybrid fallback**: auto-activates when clothing coverage < 5%
- ✅ **PNG transparency fix**: resultado é RGB (não RGBA)
- ✅ **Inpainting quality fix**: aspect ratio dinâmico, inpaint_respective_field=0.85, 3 LoRAs

### SE11 Config
- Port: 8011, API_KEY: se11-test-key-2026
- DIVISOR=11, Redis DB=11
- SE10_URL=http://host.docker.internal:8010 (Docker) / http://localhost:8010 (local)
- SE8_URL=http://host.docker.internal:8008 (Docker) / http://localhost:8008 (local)
- DEFAULT_PROMPT="natural skin tone matching surrounding skin, seamless texture, photorealistic, professional photography, soft lighting"
- denoise=0.70, inpaint_respective_field=0.85, erode_or_dilate=-10
- LoRAs: NsfwPov(0.6) + offset(0.1) + detail(0.8)
- BEST_CLOTHING_CLASSES="top, blouse, camisole, shirt, spaghetti strap"
- Inpaint mask: clothing_exact (body AND NOT exposed_skin) dilatado kernel=7px, 2 iter
- text_threshold=0.04 for SE10
- detector=florence2 for clothes detection

### Fixes aplicados
1. **base64 padding** — `_fix_b64_padding()` antes de `b64.b64decode()`
2. **PNG transparency** — `require_base64=False` em SE8 client + download via file URL, evita base64 truncado do SE8
3. **Aspect ratio dinâmico** — `_pick_sdxl_ratio()` detecta proporção da imagem e escolhe SDXL ratio mais próximo
4. **Styles limpas** — removido "Fooocus Enhance" e "Fooocus Sharp" que alteravam demais a aparência
5. **inpaint_respective_field=0.85** — crop cobre mais contexto ao redor da máscara
6. **advanced_params always sent** — engine/strength/field sempre enviados ao SE8
7. **Mask filtering fix** — objetos E masks são filtrados juntos via `_keep_object()`, evita masks de false positives (cortina) no combined mask
8. **Negative prompt** — removido "exposed skin" (auto-sabotava CFG), adicionado nudity/nude/naked/wrinkled/scarred
9. **Denoise 0.70** — sweet spot: suficiente para gerar pele, baixo o bastante para evitar nipples
10. **LoRA matching fix** — direct matching de `model.state_dict().keys()` para key_map vazio

## SE10 — Clothes Segmentation

### Person Mode (2026-06-20)
- `POST /v1/segment` aceita `mode="person"` (default: `"clothes"`)
- `PERSON_CLASSES = ["person", "woman", "man"]` — joinhado como `"person. woman. man."`
- `DEFAULT_MAX_AREA_PCT_PERSON = 0.80` (era 0.29 para roupas — pessoa pode cobrir 40%+ da imagem)
- Backward compatible: `mode` é opcional, default `"clothes"` mantém comportamento existente

### Docker Deploy
- Container: `ytcaption-se10-clothes-segmentation`, port 8010
- Image: `docker-se10-clothes-segmentation:latest` (9.85GB, compose-persisted)
- CPU only (DEVICE=cpu)
- HEALTHCHECK start_period: 120s (model loading)

### Bugs corrigidos (3)
1. **SAM2 Hydra config** — `constants.py:39`: path relativo ao pacote sam2, não filesystem path
2. **transformers 5.x compat** — `bertwarper.py:128-133`: `get_extended_attention_mask()` 3rd arg mudou de `device` para `dtype`
3. **Detections.area** — `segmentor.py:246-260`: pre-compute `areas` ao invés de iterar Detections (yield tuples)

### Checkpoints
- `groundingdino_swint_ogc.pth` (662MB) em `checkpoints/`
- `sam2_hiera_tiny.pt` (149MB) em `checkpoints/`

### External deps
- `external/GroundingDINO/` ← IDEA-Research/GroundingDINO (depth 1)
- `external/segment-anything-2/` ← facebookresearch/sam2 (depth 1)
- Bertwarper patchado para transformers>=5.0

## SE8 — Image Engine
- Port: 8008, Container: `image-engine`, nvidia/cuda:12.1.1
- Docker: `docker-compose.gpu.yml`, Dockerfile: `Dockerfile.gpu-api`
- Rotas: Health(4) + Engines(4) + V1 Gen(5) + V2 Gen(5) + Query(4) + Files(1)
- **Inpainting FULLY FUNCTIONAL**: VAE encode + InpaintHead CNN + patched KSampler + post_process

### SE8 Inpainting Architecture (full pipeline)
- `_apply_inpaint()`: decode image+mask → InpaintWorker(img, mask, use_fill=True, k=inpaint_respective_field) → VAE encode (torch.inference_mode) → load_latent → set modules.inpaint_worker.current_task → patch UNet with InpaintHead
- `_process_diffusion()`: uses inpaint latent (not empty latent) as initial state
- `patched_KSamplerX0Inpaint_forward`: mixes inpaint latent + energy noise into unmasked regions during denoising
- `worker.post_process()`: resizes generated content → color_correction (alpha blend) → pastes into original image
- `finally`: clears `modules.inpaint_worker.current_task = None`

### SE8 Key Fixes (2026-06-20)
1. **VAE encode** — encode_vae_inpaint wrapped in `torch.inference_mode()` (model weights are inference tensors)
2. **operators.py torch import** — `NameError: name 'torch' not defined` in `_decode_standard()` fallback
3. **InpaintHead patch** — loads 52KB CNN, feeds [latent_mask, process_latent_in(latent)] → patches UNet input block 0
4. **current_task activation** — `miw.current_task = worker` activates `patched_KSamplerX0Inpaint_forward`
5. **Inpaint latent as initial** — `_process_diffusion()` uses inpaint latent dict instead of empty latent
6. **Docker rebuild** — all fixes persisted in `docker-image-engine` image (rebuilt 2026-06-20)

## SE9 — Make Video IMG
- **27/27 testes passando, 0 warnings** (era 65)
- Critical bug fix: `chosen_seq` NameError em `video_assembler.py`
- Redis store refactor: `_use_raw` property
- Lazy import fix: `audio_generator.py`
- Dead code removal: `hook_text` param de `create_title_card()`
- ARCHITECTURE.md sincronizado com código real
- Pydantic v2 migration completa (shared library)

## Shared Library
- Pydantic v2 migration completa — 0 warnings
- `config_utils/base_settings.py`: SettingsConfigDict, field_validator, model_validator
- `models/base.py`: ConfigDict, json_encoders removido
- `di.py`: dependency injection container

## Pydantic v2 Migration — ALL SERVICES COMPLETE (2026-06-20)
348/348 arquivos py_compile OK, zero deprecation warnings.

| Service | Changes | Status |
|---|---|---|
| shared/ | Already migrated (earlier session) | ✅ |
| se1-orchestrator | `class Config` → `ConfigDict(json_schema_extra=...)`, removed `json_encoders` | ✅ |
| se2-video-downloader | 2x `class Config` → `ConfigDict(json_schema_extra=...)`, removed `json_encoders` | ✅ |
| se3-audio-normalization | Removed `json_encoders` | ✅ |
| se4-audio-transcriber | Already clean | ✅ |
| se5-make-video-clip | `@validator` → `@field_validator`+`@classmethod`, `class Config` → `ConfigDict(extra='forbid', json_schema_extra=...)`, `schema_extra` → `json_schema_extra`, `.dict()` → `.model_dump()`, removed `json_encoders` | ✅ |
| se6-youtube-search | Already clean | ✅ |
| se7-audio-generation | `class Config`+`json_encoders` removed | ✅ |
| se8-image-generation | Already clean (uses `model_config = {...}`) | ✅ |
| se9-make-video-img | Already clean | ✅ |
| se10-clothes-segmentation | Already clean (uses `model_config = {...}`) | ✅ |
| se11-clothes-removal | Already clean | ✅ |

## Docs Arquivados
```
docs/archive/se9-make-video-img/
├── FIX-ERROS-2026-06-19.md
├── FIX-2-2026-06-19.md
├── INVESTIGACAO-v4.1.md
└── VALID-2026-06-17.md
```

## Strong Typing — Batch 2 (2026-06-20)
11 shared/ files typed: `from __future__ import annotations`, return types on all functions/methods, `dict[str, Any]`/`list[str]` parameterized, `Optional` → `X | None`, bare `list` → `list[str]`.

Files: `health_utils.py`, `datetime_utils/__init__.py`, `datetime_utils/helpers.py`, `datetime_utils/conftest.py`, `log_utils/__init__.py`, `log_utils/structured.py`, `redis_utils/__init__.py`, `redis_utils/resilient_store.py`, `redis_utils/serializers.py`, `http_utils/__init__.py`, `http_utils/resilient_client.py`

All 11 py_compile OK, no logic changes.

## Strong Typing — Batch 3 (2026-06-20)
28 se2-video-downloader files typed: `from __future__ import annotations`, return types on all functions/methods/properties, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed.

Files: `app/__init__.py`, `app/main.py`, `app/core/config.py`, `app/core/constants.py`, `app/core/logging_config.py`, `app/core/models.py`, `app/core/validators.py`, `app/core/__init__.py`, `app/api/jobs_routes.py`, `app/api/admin_routes.py`, `app/api/health_routes.py`, `app/api/__init__.py`, `app/domain/interfaces.py`, `app/domain/__init__.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/dependencies.py`, `app/infrastructure/redis_store.py`, `app/infrastructure/__init__.py`, `app/services/video_downloader.py`, `app/services/user_agent_manager.py`, `app/services/validators.py`, `app/services/__init__.py`, `app/middleware/body_size.py`, `app/middleware/rate_limiter.py`, `app/middleware/__init__.py`, `app/shared/exceptions.py`, `app/shared/__init__.py`

All 28 py_compile OK, no logic changes.

## Strong Typing — Batch 3 SE1 (2026-06-20)
26 SE1 orchestrator files typed: `from __future__ import annotations`, return types on all functions/methods, `dict[str, Any]`/`list[str]` parameterized, `Optional` → `X | None`, bare `list` → `list[str]`, bare `dict` → `dict[str, Any]`.

Files (26): `app/__init__.py`, `app/main.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/exceptions.py`, `app/core/ssl_config.py`, `app/api/__init__.py`, `app/api/jobs_routes.py`, `app/api/admin_routes.py`, `app/api/health_routes.py`, `app/domain/__init__.py`, `app/domain/models.py`, `app/domain/interfaces.py`, `app/domain/builders.py`, `app/domain/pipeline_job_v2.py`, `app/infrastructure/__init__.py`, `app/infrastructure/microservice_client.py`, `app/infrastructure/redis_store.py`, `app/infrastructure/circuit_breaker.py`, `app/infrastructure/dependency_injection.py`, `app/services/__init__.py`, `app/services/pipeline_orchestrator.py`, `app/services/pipeline_background.py`, `app/services/health_checker.py`, `app/middleware/__init__.py`, `app/shared/__init__.py`

All 26 py_compile OK, no logic changes.

## Strong Typing — Batch 5 SE7 (2026-06-20)
29 se7-audio-generation files typed: `from __future__ import annotations`, return types on all functions/methods/properties, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed.

Files (29): `app/__init__.py`, `app/main.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/constants.py`, `app/api/__init__.py`, `app/api/jobs_routes.py`, `app/api/admin_routes.py`, `app/api/health_routes.py`, `app/api/schemas.py`, `app/api/voices_routes.py`, `app/domain/__init__.py`, `app/domain/exceptions.py`, `app/domain/interfaces.py`, `app/domain/models.py`, `app/infrastructure/__init__.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/dependencies.py`, `app/infrastructure/redis_store.py`, `app/services/__init__.py`, `app/services/audio_utils.py`, `app/services/generator.py`, `app/services/model_manager.py`, `app/services/pt_br_normalizer.py`, `app/services/voice_manager.py`, `app/services/voice_seeder.py`, `app/middleware/__init__.py`, `app/shared/__init__.py`

All 29 py_compile OK, no logic changes.

## Strong Typing — Batch 4 SE3 (2026-06-20)
29 se3-audio-normalization files typed: `from __future__ import annotations`, return types on all functions/methods/properties, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed.

Files (29): `app/__init__.py`, `app/main.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/constants.py`, `app/core/exceptions.py`, `app/core/logging_config.py`, `app/core/models.py`, `app/core/validators.py`, `app/domain/__init__.py`, `app/domain/interfaces.py`, `app/infrastructure/__init__.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/dependencies.py`, `app/infrastructure/redis_store.py`, `app/middleware/__init__.py`, `app/middleware/body_size.py`, `app/middleware/rate_limiter.py`, `app/services/__init__.py`, `app/services/audio_extractor.py`, `app/services/audio_normalizer.py`, `app/services/audio_processor.py`, `app/services/cleanup_service.py`, `app/services/file_validator.py`, `app/services/job_manager.py`, `app/services/job_service.py`, `app/shared/__init__.py`, `app/shared/exceptions.py`

All 29 py_compile OK, no logic changes.

## Strong Typing — Batch 5 SE6 (2026-06-20)
33 se6-youtube-search files typed: `from __future__ import annotations`, return types on all functions/methods/properties, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed.

Files (33): `app/__init__.py`, `app/main.py`, `app/api/__init__.py`, `app/api/admin.py`, `app/api/jobs.py`, `app/api/routes.py`, `app/api/search.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/constants.py`, `app/core/logging_config.py`, `app/core/validators.py`, `app/domain/__init__.py`, `app/domain/interfaces.py`, `app/domain/models.py`, `app/domain/processor.py`, `app/infrastructure/__init__.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/dependencies.py`, `app/infrastructure/redis_store.py`, `app/middleware/__init__.py`, `app/middleware/body_size.py`, `app/middleware/rate_limiter.py`, `app/services/__init__.py`, `app/services/ytbpy/__init__.py`, `app/services/ytbpy/channel.py`, `app/services/ytbpy/playlist.py`, `app/services/ytbpy/search.py`, `app/services/ytbpy/utils.py`, `app/services/ytbpy/video.py`, `app/shared/__init__.py`, `app/shared/exceptions.py`

All 33 py_compile OK, no logic changes.

## Strong Typing — Batch 6 SE5 (2026-06-20)
33 se5-make-video-clip files typed: `from __future__ import annotations`, return types on all functions/methods/properties, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed.

Files (33): `app/infrastructure/__init__.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/checkpoint_manager.py`, `app/infrastructure/circuit_breaker.py`, `app/infrastructure/dependencies.py`, `app/infrastructure/file_logger.py`, `app/infrastructure/health_checker.py`, `app/infrastructure/lock_manager.py`, `app/infrastructure/metrics.py`, `app/infrastructure/redis_store.py`, `app/infrastructure/subprocess_utils.py`, `app/infrastructure/telemetry.py`, `app/api/__init__.py`, `app/api/api_client.py`, `app/api/routes.py`, `app/services/__init__.py`, `app/services/blacklist_factory.py`, `app/services/blacklist_manager.py`, `app/services/cache_manager.py`, `app/services/cleanup_service.py`, `app/services/file_operations.py`, `app/services/job_manager.py`, `app/services/shorts_manager.py`, `app/services/sqlite_blacklist.py`, `app/services/subtitle_generator.py`, `app/services/subtitle_postprocessor.py`, `app/services/sync_validator.py`, `app/services/video_builder.py`, `app/services/video_compatibility_fixer.py`, `app/services/video_compatibility_validator.py`, `app/services/video_status_factory.py`, `app/services/video_status_store.py`

All 33 py_compile OK, no logic changes.

## Strong Typing — Batch 7 SE8 (2026-06-20)
44 se8-image-generation files typed: `from __future__ import annotations` added to all files, return types on all functions/methods/properties/`__init__`, `dict[str, Any]`/`list[str]` parameterized, `Optional[X]` → `X | None`, `Dict`/`List`/`Set`/`Tuple` → lowercase builtins, `Any` added to typing imports where needed, `Callable` moved to `collections.abc`.

Files (44): `app/__init__.py`, `app/main.py`, `args_manager.py`, `app/api/__init__.py`, `app/api/admin_routes.py`, `app/api/api_utils.py`, `app/api/file_routes.py`, `app/api/generate_routes.py`, `app/api/generate_v2_routes.py`, `app/api/health_routes.py`, `app/api/image_utils.py`, `app/api/models_routes.py`, `app/api/query_routes.py`, `app/api/tools_routes.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/constants.py`, `app/domain/__init__.py`, `app/domain/models.py`, `app/domain/task_models.py`, `app/infrastructure/__init__.py`, `app/infrastructure/celery_config.py`, `app/infrastructure/celery_tasks.py`, `app/infrastructure/core_ops.py`, `app/infrastructure/operators.py`, `app/services/__init__.py`, `app/services/checkpoint.py`, `app/services/controlnet.py`, `app/services/expansion.py`, `app/services/face_crop.py`, `app/services/face_restoration.py`, `app/services/inpaint_worker.py`, `app/services/ip_adapter.py`, `app/services/lora_manager.py`, `app/services/model_base.py`, `app/services/model_manager.py`, `app/services/model_patcher.py`, `app/services/pipeline.py`, `app/services/preprocessors.py`, `app/services/task_queue.py`, `app/services/upscaler.py`, `app/services/vae_interpose.py`, `app/services/worker.py`, `app/shared/__init__.py`, `app/extras/__init__.py`

All 44 py_compile OK, no logic changes.

> **Próximos passos / Pendências:** Ver `PENDENCIAS.md`
