# HISTORY.md — SE11 Pipeline History (Resolved Items)

**Serviço:** SE11 (clothes-removal)
**Migrado de:** `PENDENCIAS.md` (raiz do projeto) em 2026-07-05

---

## ✅ Resolved Items

### ✅ RESOLVIDO — Steps 60→50 (2026-07-05)
- **Problema:** 60 steps = ~150s/tentativa
- **Solução:** Reduzido para 50 steps (~100s/tentativa)
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — OpenPose ControlNet Union SDXL (2026-07-05)
- **Problema:** LoRA-based ControlNet incompatible with SDXL inpainting (9-channel UNet)
- **Solução:** `xinsir/controlnet-union-sdxl-1.0` (standard ControlNet, 2.4GB)
- **Otimização:** weight=0.3, stop=0.6 → composite=5.17 (vs 8.76 sem ControlNet)
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — SDXL Refiner testado e rejeitado (2026-07-05)
- **Problema:** SDXL Refiner destrói pose (5/5 attempts pose_changed=True)
- **Causa:** Joint denoising do refiner sobrescreve pose do base+ControlNet
- **RAM:** Pico 34.5GB (93.9%) — quase 100%
- **Status:** ✅ RESOLVIDO — Refiner removido, pipeline sem refiner

### ✅ RESOLVIDO — GroundingDINO + SAM2 + BiRefNet removidos do SE10 (2026-07-05)
- **Problema:** SE10 carregava 4 detectores, apenas 2 funcionavam (GD sempre falhava, SAM2 sempre pulado, BiRefNet OOM)
- **Solução:** Remoção completa de TODO o código morto (ensemble reescrito, birefnet_detector.py deletado)
- **Resultado:** RAM idle 1.9GB→1.0GB, zero erros startup
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — SE8 GPU/RAM memory leak fix (2026-07-05)
- **Problema:** Após job, GPU 6469 MiB e RAM 32GB retidos
- **Solução:** Dual model_manager cleanup (SE8 + ComfyUI) no finally block
- **Resultado:** GPU 576 MiB, RAM 431 MB (SE8)
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — Multi-Detector Ensemble (YOLO11-seg + GD + BiRefNet) (2026-07-03)
- **Problema:** GroundingDINO falha em 1.6% coverage para TESTE1.jpg (roupa escura, fundo complexo)
- **Solução:** YOLO11-seg + BiRefNet-portrait + ensemble voting
- **Resultado:** 99.7% confiança, 48.8% coverage, ~1.2s
- **Status:** ✅ RESOLVIDO (GD e BiRefNet depois removidos, YOLO mantido)

### ✅ RESOLVIDO — Face-ellipse fallback (2026-07-03)
- **Problema:** SE10 GroundingDINO falha em imagens com fundo complexo
- **Solução:** Three-level fallback chain: retry → GrabCut → face-ellipse
- **Resultado:** E2E success, composite=10.611, face 100% preservada
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — Florence-2 REMOVIDO (2026-07-04)
- **Problema:** Falsos positivos catastroficos (logo "GUCCI" = "spaghetti strap", cabelo = "skirt")
- **Solução:** Substituído por SegFormer B2 (pixel-level, 18 classes)
- **Código:** `florence_detector.py` deletado (202 linhas), todas referências removidas de SE10+SE11
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — SegFormer B2 integrado e validado E2E (2026-07-04)
- **Problema:** Florence-2 falsos positivos, detecções bounding box imprecisas
- **Solução:** SegFormer B2 (mattmdjaga/segformer_b2_clothes) com detecções per-class separadas
- **Resultado:** 3 detecções (Upper-clothes 42%, Skirt 0.6%, Pants 8%), 795ms GPU
- **Bugs corrigidos:** max_area_pct, nesting filter, labels, nova instância por call
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — Máscara com buracos entre itens de roupa (2026-07-04)
- **Problema:** Gap entre hoodie e pants na barriga exposta ficava sem inpainting
- **Solução:** Morphological closing k=100-120 + bitwise_and(person_binary)
- **Resultado:** Máscara 100% sólida, sem buracos, sem bleeding para fundo
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — GPU memory management (2026-07-04)
- **Problema:** SE10+SE8 VRAM overlap causava CUDA corruption
- **Solução:** unload_all_models() imediato pós-request, del sd, MODEL_IDLE_TIMEOUT=60
- **Resultado:** VRAM idle 12MiB, RAM idle 8.4GB (20%)
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — DWPose substitui MediaPipe (2026-07-04)
- **Problema:** MediaPipe 33 landmarks era impreciso
- **Solução:** DWPose (YOLOX + transformer, 126 keypoints, ~1.7s CPU)
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — NSFW Prompt hardcoded (2026-07-03)
- **Problema:** Prompt do usuário sobrescrevia NSFW prompt
- **Solução:** /jobs/nsfw sempre ignora prompt do usuário
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — Container crash 1G→2G (2026-07-03)
- **Status:** ✅ RESOLVIDO

---

## ✅ Implementados nesta sessão (2026-07-04/05)

| Item | Status |
|------|--------|
| SegFormer B2 detector (18 classes, per-class masks) | ✅ |
| Ensemble: SegFormer PRIMARY clothes, YOLO11 PRIMARY person | ✅ |
| max_area_pct=0.80 para SegFormer | ✅ |
| Nesting filter pulado para SegFormer | ✅ |
| Labels via LABELS[cls_id] | ✅ |
| Morphological closing k=100-120 | ✅ |
| bitwise_and(person_binary) anti-bleeding | ✅ |
| Steps 60→50 | ✅ |
| NSFW prompt ultra-realistic | ✅ |
| Florence-2 REMOVIDO (código + referências) | ✅ |
| GroundingDINO + SAM2 + BiRefNet REMOVIDOS (código + referências) | ✅ |
| birefnet_detector.py DELETADO | ✅ |
| DetectorType enum: SEGFORMER + ENSEMBLE | ✅ |
| PROGRESSIVE_PASSES: florence2→segformer | ✅ |
| ControlNet Union SDXL (xinsir/controlnet-union-sdxl-1.0) | ✅ |
| ControlNet weight optimization (w=0.3 optimal) | ✅ |
| ESRGAN 4x-UltraSharp pure upscaler | ✅ |
| `/v1/tools/upscale-esrgan` endpoint | ✅ |
| SE8 GPU/RAM memory leak fix (dual model_manager) | ✅ |
