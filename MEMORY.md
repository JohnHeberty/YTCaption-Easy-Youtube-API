# Estado Atual — Monorepo YTCaption

## Última sessão (2026-06-20)
- **Strong Typing Batch 7 SE8** — 44 SE8-image-generation files typed (all py_compile OK)
- **Strong Typing Batch 6 SE5** — 33 SE5-make-video-clip files typed (all py_compile OK)
- **Strong Typing Batch 5 SE6** — 33 SE6-youtube-search files typed (all py_compile OK)
- **Strong Typing Batch 4** — 29 SE3-audio-normalization files typed (all py_compile OK)
- **Clean Code Audit COMPLETE** — 5-phase audit across all 11 services + shared library
- **Commits**: `51202c2` (SE9+Pydantic v2), `c20c55a` (SE11 E2E+SE8 inpaint), `3526fe7` (agent docs), `64014b7` (Fase 3 SE6+SE7), `4ae828d` (Fase 4 SE1-SE4), `a02c75c` (Fase 5 SE5+SE8)
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
- ✅ **E2E passou (compose-persisted)**: SE11 → SE10 → SE8 → RGB 482×789, 449KB, ~84s
- ✅ **PNG transparency fix**: resultado é RGB (não RGBA)
- ✅ **Inpainting quality fix**: aspect ratio dinâmico, inpaint_respective_field=0.8, sem styles agressivas

### SE11 Config
- Port: 8011, API_KEY: se11-test-key-2026
- DIVISOR=11, Redis DB=11
- SE10_URL=http://host.docker.internal:8010 (Docker) / http://localhost:8010 (local)
- SE8_URL=http://host.docker.internal:8008 (Docker) / http://localhost:8008 (local)
- DEFAULT_PROMPT="nude, naked body, smooth skin"

### Fixes aplicados
1. **base64 padding** — `_fix_b64_padding()` antes de `b64.b64decode()`
2. **PNG transparency** — `require_base64=False` em SE8 client + download via file URL, evita base64 truncado do SE8
3. **Aspect ratio dinâmico** — `_pick_sdxl_ratio()` detecta proporção da imagem e escolhe SDXL ratio mais próximo
4. **Styles limpas** — removido "Fooocus Enhance" e "Fooocus Sharp" que alteravam demais a aparência
5. **inpaint_respective_field=0.8** — crop cobre mais contexto ao redor da máscara (era 0.5 default)
6. **advanced_params always sent** — engine/strength/field sempre enviados ao SE8

## SE10 — Clothes Segmentation

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

## Próximos Passos
1. ✅ SE8 Inpainting full pipeline — VAE+InpaintHead+patched sampler, Docker rebuild persisted
2. ✅ SE11 Params fix — aspect ratio, styles, advanced_params
3. ✅ E2E validated — full SE11→SE10→SE8 pipeline, compose-persisted images
4. ✅ Pydantic v2 migration completa — 348/348 arquivos, zero warnings
5. ✅ SE8 Docker rebuild — all inpainting fixes persisted (2026-06-20)
6. Integração SE11 ao SE1 ou APIs externas
7. SE10 detection quality — GroundingDINO occasionally misplaces objects (e.g., blouse at wrong y-position)
