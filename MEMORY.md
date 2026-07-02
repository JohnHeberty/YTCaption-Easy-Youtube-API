# Estado Atual — Monorepo YTCaption

## Última sessão (2026-07-02)

### 🟢 NSFW TEST → PRODUCTION REDIRECT (2026-07-02)

**Ação:** `mode="nsfw_test"` agora redireciona para `pipeline_nsfw.py` (produção). Arquivos experimentais deletados.

**Arquivos alterados:**
- `pipeline.py`: Dispatcher `nsfw_test` → `run_nsfw()` (production)
- `schemas.py`: Descriptions removidas "Experimental v2"
- `routes.py`: Descriptions atualizadas

**Arquivos deletados:**
- `pipeline_nsfw_experimental_v2.py`
- `pipeline_nsfw_experimental.py`

**Motivo:** Produção já tem todas as features do V2 (scoring multidimensional, 5 tentativas, skin HSV, SE10 clothes, early stop). Rotas experimentais eram código morto.

### 🟢 NSFW TEST V2 — SCORING MULTIDIMENSIONAL (Exploratório)

**Resultado E2E validado:** `cr_f7e6ef75b636` — 5 tentativas, scoring multidimensional (head + clothes + landmark).

#### Scoring Multidimensional

Fórmula: `score = 0.5 × head_avg + 0.3 × clothes_pct + 0.2 × max_landmark`

| Try | Strength | Head% | Clothes% | MaxLandmark | Composite | Winner? |
|-----|----------|-------|----------|-------------|-----------|---------|
| 1 | 0.86 | 0.585 | **27.2** | 14.52 | **11.361** | **YES** |
| 2 | 0.89 | **0.265** | 33.9 | **8.11** | 11.922 | |
| 3 | 0.92 | 0.435 | 29.1 | 14.49 | 11.848 | |
| 4 | 0.95 | 0.406 | 31.5 | 10.45 | 11.733 | |
| 5 | 0.98 | 0.610 | 43.5 | 18.77 | 17.102 | |

**Conclusão:** Attempt 1 (0.86) vence porque tem MENOS roupa residual (27.2%). O scoring corretamente equilibra preservação facial + remoção de roupa + estabilidade de pose.

### 🟢 PRODUCTION MERGE — LustifyNSFW Pipeline (2026-07-02)

**Resultado E2E validado:** `cr_5c8931461b5b` — LustifyNSFW 0.86, head_pct=0.342%, pose_changed=False, roupa 100% removida, rosto preservado.

#### Descoberta crítica: LustifyNSFW vs JuggernautXL

| Modelo | Resultado | Roupa | Rosto | Pose |
|--------|-----------|-------|-------|------|
| JuggernautXL 0.35 | Cinza/blobs | ❌ | ✅ | ✅ |
| JuggernautXL 0.65 | Suéter azul visível | ❌ | ✅ | ✅ |
| JuggernautXL 0.75 | Parcial NSFW + roupa | ❌ | ⚠️ | ✅ |
| JuggernautXL 0.86 | Artefato facial + roupa | ❌ | ❌ | ✅ |
| **LustifyNSFW 0.86** | **Perfeito** | **✅** | **✅** | **✅** |

**Conclusão:** LustifyNSFW_v20-inpainting é modelo NSFW+inpainting nativo, supera JuggernautXL para remoção de roupa.

#### Correções implementadas nesta sessão:

| Passo | Arquivo | Mudança |
|---|---|---|
| 1. Modelo | pipeline_v2, routes, schemas | Default JuggernautXL → LustifyNSFW |
| 2. Strength | pipeline_v2, routes, schemas | 0.35→0.65→0.75→**0.86** |
| 3. Hair protection | pipeline_v2 | head_subtract com expand_up=2.5, expand_w=0.8, dilate=25px, iter=3 |
| 4. Head detector | head_detector.py | Novos params: expand_up, expand_w (eram hardcoded 1.5/0.5) |
| 5. OpenPose condicional | pipeline_v2 | Só para Juggernaut (Lustify incompatível) |

#### Bugs corrigidos:
- **OpenPose RuntimeError:** Lustify UNet architecture incompatible with ControlNet — fixed by making OpenPose conditional
- **Hair bleed:** clothes_mask + dilate(15px) bleeds into hair → head subtraction with larger ellipse

#### Arquivos alterados:
- `services/se11-clothes-removal/app/services/pipeline_nsfw_experimental_v2.py` — LustifyNSFW, head_subtract, OpenPose conditional
- `services/se11-clothes-removal/app/services/head_detector.py` — expand_up, expand_w params
- `services/se11-clothes-removal/app/api/routes.py` — default strength 0.86, default model LustifyNSFW
- `services/se11-clothes-removal/app/api/schemas.py` — default strength 0.86, default model LustifyNSFW

#### Próximos passos:
- ~~**Migrar para produção** (`pipeline_nsfw.py`): LustifyNSFW + FaceID + invert_mask + debug masks~~ **✅ FEITO**
- ~~**Remover face blending** (Lustify preserva rosto nativamente)~~ **✅ FEITO**
- ~~**Manter 3 retry attempts** (0.86/0.87/0.90)~~ **✅ FEITO**
- ~~**Salvar debug masks em produção**~~ **✅ FEITO**

### 🟢 PRODUCTION MERGE — LustifyNSFW Pipeline (2026-07-02)

**Production pipeline (`pipeline_nsfw.py`) migrated to LustifyNSFW.**

#### Changes applied:
1. **Face blending removed**: Laplacian/LAB harmonization replaced with simple passthrough (`composited = inpainted_img.copy()`)
2. **FaceID extraction**: `extract_faceid_embedding()` called before retry loop, passed to SE8 inpaint
3. **OpenPose conditional**: Only sent when `juggernaut` in base_model (Lustify incompatible)
4. **Debug masks**: `30_mask_overlay.png`, `detection_meta.json`, `20_garment_N_class.png` saved per job
5. **Pose thresholds relaxed**: `head=1.5%, torso=8.0%, limbs=5.0%` (NSFW regenerates body but preserves face)

#### E2E Production Test:
- **Job `cr_58e0d3d4cb9e`**: All 3 attempts `pose_changed=false`, best=try_3 (strength=0.9), head_pct=0.442%
- **Previous failure `cr_60a81e06739a`**: All attempts `pose_changed=true` (thresholds too strict — fixed)

#### Files modified:
- `services/se11-clothes-removal/app/services/pipeline_nsfw.py` — FaceID, debug masks, relaxed thresholds

### Known Issues
- `POST /jobs` 307 redirect_slashes → `/jobs/` — pre-existing Starlette behavior
- SE8 logger não output para docker logs (configuração de logging)
- FaceID SE8: `_load_faceid_adapter()` implementado mas não verificável via logs — precisa teste visual comparativo

## Sessão anterior (2026-07-01)

### 🟡 NSFW TEST V2 — HEAD MASK FIX + FACE BLENDING (Committed + Pushed)
- **Commits:** `fd556cb` (feat), `b8000ca` (fix mask), `5572c0b` (fix head params + blend_utils + SE8 face_routes)
- **Branch:** main, 3 commits ahead of origin (all pushed)
- **Head detection fix:** `neck_margin_below` 0.15→0.50, `max_head_pct` 0.40→0.45 in 4 files
  - **Root cause:** `neck_margin_below=0.15` made head mask too small → face was included in inpaint mask
  - **Fix:** Now matches production default (0.50), face properly excluded from inpaint region
  - **E2E validated:** `cr_testmaskfix01` — mask stops at neck, face 100% preserved
- **New files:** `blend_utils.py` (selectable laplacian/alpha face blending), `face_routes.py` (SE8 face crop/restore endpoints)
- **SE8 improvements:** face_crop.py, face_restoration.py updates, docker-compose GPU config
- **Results:** `show/v2_headfix_*.png` — debug overlay, result, inpaint mask

### Known Issues
- `POST /jobs` 307 redirect_slashes → `/jobs/` (only GET) — pre-existing Starlette behavior, jobs must be submitted via pipeline function directly or through Swagger UI
- FaceID CUDA assertion at strength ≥0.55 — works at 0.45 without FaceID, or 0.65 without FaceID
- Skin generation quality needs tuning (prompt + strength optimization)

## Última sessão (2026-06-30)

### 🟢 NSFW v22/v23 — PRODUCTION (Leffa-style clothes-neutralized IP-Adapter ref + OpenPose ControlNet)
- **Rota oficial:** `POST /jobs` (file upload) `mode="nsfw"`
- **Pipeline:** `pipeline_nsfw.py` (v22 — clothes-neutralized IP-Adapter reference)
- **BREAKTHROUGH (2026-06-30):** Suéter residual RESOLVIDO via Opção A do UPGRADE.md
  - **Causa raiz:** IP-Adapter usava imagem original vestida → encoder extraía features de roupa → vazava para o resultado (exatamente a distorção que Leffa CVPR2025 descreve: "inadequate attention to corresponding regions")
  - **Solução:** `_build_clothes_neutral_ref()` — preenche região de roupa com tom de pele médio + ruído sutil antes de codificar. Encoder vê pose/rosto/corpo mas NÃO vê textura da roupa.
- **Config vencedora (B_neu_s086 — validada visualmente pelo usuário):**
  - **IP-Adapter:** CLOTHES-NEUTRALIZED ref (weight=0.8, stop=0.5)
  - strength=0.86 (era 0.84 — neutral ref precisa mais força para compensar)
  - field=0.618, erode=0, seed=-1
  - Retry: 0.86/0.87/0.90
  - **Head mask:** subtract clothes → DT(8px) → inflate → close(9px) → blur(15px,σ=5) → clip person
  - **Feathered composite:** GaussianBlur(21px) alpha blend
  - **Reinhard LAB color transfer:** skin-only reference
  - Pre-scale to min 1024px
- **Pose scores (B_neu_s086):** head=0.0%, torso=2.0%, limbs=4.1% (baseline A_orig era limbs=10.0%)
- **Speed:** 16s/try (era 46s — 3x mais rápido, possivelmente porque neutral ref é mais simples de processar)
- **E2E test:** cr_40d2cb20f12e — try_1 aceito (pose_changed=false), result 1MB
- **Pose conditioning test (2026-06-30):**
  - Adicionado `render_pose_stick_figure()` no `pose_detector.py` usando MediaPipe
  - Testado como segunda imagem do IP-Adapter (weight=0.4) no pipeline de produção
  - **Resultado: DEGRADOU** a preservação de pose (score 21.3 vs 0.0 sem stick)
  - **Razão:** IP-Adapter/CLIP codifica stick figure sintético como "desenho abstrato", não como estrutura corporal
  - **Status:** desativado em produção, código mantido para futuras experiências
- **SE11 Docker:** rebuild com mediapipe + libs gráficas (libxcb). Imagem funcional.
- **OpenPose ControlNet integration (v23):**
  - SE10 `/v1/segment` now accepts `include_pose=true` and returns `controlnet_image` (MediaPipe stick figure)
  - SE11 requests pose control image during person detection and passes it to SE8 as `OpenPose` image prompt
  - SE8 `_apply_controlnet()` loads `controlnet-openpose-sdxl.safetensors` and applies it during diffusion
  - Tensor format: `[B, H, W, C]` — ComfyUI `ControlNetApplyAdvanced` internally moves channel to position 1
  - **E2E validated:** job `cr_b7565e9710cc` completed with OpenPose ControlNet applied
  - **Quality observation:** on the tested 1024×1536 image, OpenPose ControlNet degraded pose scores vs clothes-neutral ref alone (best score 14.6 vs 6.7 without ControlNet). Likely cause: MediaPipe 33-landmark skeleton differs from OpenPose COCO/Body_25 format expected by the ControlNet model.
- **Face blend improvement (v23.1 → v23.2 → v23.3 → v23.4):**
  - v23.1: Protected region reduced from full head+hair+neck to inner face only (~23% of previous mask)
  - v23.2: Protected region reduced further to central face only (~10.5% of head mask)
  - v23.2: Distance-transform feather substitui Gaussian blur
  - v23.2: Eroded head mask cria transition band para SE8 gerar queixo/bochechas
  - v23.2: Harmonização LAB localizada na faixa de transição + pele exposta original
  - v23.3: Tentativa com MediaPipe Face Mesh para centralizar máscara; descartado por falha de contexto GPU no container
  - **v23.4:** Voltou a Haar bbox com máscara de FACE COMPLETA (margin_above=0.05, margin_below=0.55, margin_sides=0.40) para preservar geometria facial e evitar deslocamento
  - **v23.4:** Feather direcional: bordas superior/laterais duras, só queixo/pescoço é suavizado por distance transform
  - **E2E validated:** job `cr_4c585ccaada4` completed; face_protect_mask = 38.8k px vs head_adjusted = 131.1k px (~29.6%); best score = 11.8
  - Resultados visuais copiados para `/root/YTCaption-Easy-Youtube-API/show/`
- **Exploration script:** `exploration/run_mask_pipeline.py` — grid REF A vs REF B
- **Research doc:** `exploration/UPGRADE.md` — como VTON models (IDM-VTON, OOTDiffusion, Leffa) funcionam
- **SE8 LoRAs:** NsfwPov(0.6) + offset(0.1) + add-detail(0.7) + Inpaint patch v2.6 (582 keys)
- **Prompt positive/negative:** mantido igual ao v21
- **Compositing:** SE8 post_process + head paste + Reinhard color transfer
> **Lições aprendidas:** Ver `LIÇÕES.md`
> **Pendências:** Ver `PENDENCIAS.md`

### Arquivos modificados nesta sessão
| Arquivo | Mudança |
|---------|---------|
| `exploration/UPGRADE.md` | Pesquisa VTON + plano de fases SE10/SE8/SE11 |
| `exploration/run_mask_pipeline.py` | Opção A: `build_clothes_neutral_ref()` + grid REF A vs REF B |
| `services/se11-clothes-removal/app/services/pipeline_nsfw.py` | `_build_clothes_neutral_ref()` + IP-Adapter ref neutral + OpenPose ControlNet prompt + landmark-centered face blend + strength 0.86/0.87/0.90 |
| `services/se11-clothes-removal/app/services/head_detector.py` | NOVO: `detect_face_landmark_mask()` via MediaPipe Face Mesh |
| `services/se11-clothes-removal/app/infrastructure/http_client.py` | `SE10Client.segment()` accepts `include_pose` |
| `services/se11-clothes-removal/app/validators/pose_detector.py` | `render_pose_stick_figure()` + `detect_pose()` aceita ndarray |
| `services/se11-clothes-removal/requirements.txt` | Adicionado mediapipe |
| `services/se11-clothes-removal/docker/Dockerfile` | Libs gráficas + chmod site-packages para mediapipe |
| `services/se10-clothes-segmentation/app/services/pose_renderer.py` | NOVO: MediaPipe → OpenPose stick figure renderer |
| `services/se10-clothes-segmentation/app/services/segmentor.py` | `include_pose` support, returns `controlnet_image` + `pose_landmarks` |
| `services/se10-clothes-segmentation/app/api/routes/segment.py` | `include_pose` form field |
| `services/se10-clothes-segmentation/app/domain/models.py` | Response fields for `controlnet_image`/`pose_landmarks` |
| `services/se10-clothes-segmentation/docker/Dockerfile` | mediapipe + libxcb dependencies |
| `services/se8-image-generation/app/services/worker.py` | `_apply_controlnet()` + OpenPose type parsing + tensor conversion |
| `services/se8-image-generation/app/services/preprocessors.py` | `openpose_identity()` pass-through |
| `services/se8-image-generation/app/domain/models.py` | `ControlNetType.cn_openpose` |
| `services/se8-image-generation/app/infrastructure/operators.py` | Real `ControlNetApplyAdvanced` wrapper |

### Container SE8
- Nome: `image-engine` (NÃO `se8-image-engine`)
- Porta: 8008
- **Agora usa bind mounts** para código (`app`, `modules`, `ldm_patched`, `extras`, `sdxl_styles`, `args_manager.py`) e `data`
- **GPU mounts obrigatórios** para driver 590 (workaround nvidia-container-toolkit):
  - `/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1`
  - `/usr/lib/x86_64-linux-gnu/libcuda.so.1`
  - `/usr/lib/x86_64-linux-gnu/libnvidia-ml.so`
  - `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-uvm`, `/dev/nvidia-uvm-tools`, `/dev/nvidia-modeset`
- Criado `/app/data/wildcards` com ownership `1000:1000` para evitar `PermissionError` no startup
- Para atualizar: restart container (código via bind mount); recriar se precisar adicionar mounts GPU

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
| se11-clothes-removal | 8011 | se11-clothes-removal | ✅ E2E validated | SE10→SE8 inpaint pipeline, OpenPose ControlNet integrated |

## SE11 — Clothes Removal Service

### Arquitetura
Fluxo v22: imagem → SE10 (person + clothes + pose) → head/body separation → SE8 inpaint (clothes-neutral IP-Adapter ref) → compositing → resultado
Fluxo v23 (experimental): imagem → SE10 (person `include_pose=true`) → SE8 inpaint (neutral ref + OpenPose ControlNet) → compositing → resultado

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
- **OpenPose ControlNet**: `data/models/controlnet/controlnet-openpose-sdxl.safetensors` (739MB, `control-lora-openposeXL2-rank256`)
- **ControlNet tensor format**: pass `[B, H, W, C]` to `ControlNetApplyAdvanced`; it does `image.movedim(-1,1)` internally

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
