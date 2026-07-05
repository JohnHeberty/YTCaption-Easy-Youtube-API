# PENDENCIAS.md — Items Pendentes

**Data:** 2026-07-05
**Última atualização:** ControlNet Union SDXL integrated and weight-optimized

---

## NSFW Pipeline — Status Atual

### ✅ RESOLVIDO — Multi-Detector Ensemble (YOLO11-seg + GD + BiRefNet) (2026-07-03)
- **Problema:** GroundingDINO falha em 1.6% coverage para TESTE1.jpg (roupa escura, fundo complexo)
- **Solução:** YOLO11-seg + BiRefNet-portrait + ensemble voting
- **Resultado:** 99.7% confiança, 48.8% coverage, ~1.2s
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — Face-ellipse fallback (2026-07-03)
- **Problema:** SE10 GroundingDINO falha em imagens com fundo complexo
- **Solução:** Three-level fallback chain: retry → GrabCut → face-ellipse
- **Resultado:** E2E success, composite=10.611, face 100% preservada
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — Florence-2 REMOVIDO (2026-07-04)
- **Problema:** Falsos positivos catastroficos (logo "GUCCI" = "spaghetti strap", cabelo = "skirt")
- **Solução:** Substituído por SegFormer B2 (pixel-level, 18 classes)
- **Código:** `florence_detector.py` deletado (202 linhas), todas referências removidas de SE10+SE11
- **Status:** ✅ RESOLVIDO —彻底 REMOVIDO

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

## Pendências Ativas

### ✅ RESOLVIDO — Steps 60→50 (2026-07-05)
- **Problema:** 60 steps = ~150s/tentativa
- **Solução:** Reduzido para 50 steps (~100s/tentativa)
- **Status:** ✅ RESOLVIDO

### 2. Testar com mais imagens (PRIORIDADE ALTA)
- **Problema:** Só testamos com TESTE1.jpg (mulher, fundo gaming)
- **Necessário:** Diversos poses, camadas de roupa, ângulos, iluminação
- **Status:** PENDENTE

### 3. Otimizar composite score — landmark drift (PRIORIDADE MÉDIA)
- **Problema:** strength=0.92 algumas vezes causa pose_changed=true
- **Causa provável:** DWPose landmarks muito sensíveis a micro-mudanças
- **Solução candidata:** Ajustar thresholds ou usar métrica diferente
- **Status:** PENDENTE

### 4. Fase 4: Matching por centróide — multi-person (PRIORIDADE MÉDIA)
- **Problema:** Pipeline assumes 1 pessoa por imagem
- **Solução:** Centroid-based person matching para múltiplas pessoas
- **Complexidade:** ALTA
- **Status:** PENDENTE

### 5. Lazy-load IP-Adapter/ControlNet no SE8 (PRIORIDADE BAIXA)
- **Problema:** IP-Adapter e ControlNet carregados na memória mesmo sem uso
- **Solução:** Lazy-load sob demanda
- **Economia:** ~2.7GB RAM
- **Complexidade:** MÉDIA
- **Status:** PENDENTE

### 6. Face ghost no pescoço
- **Problema:** SE8 gera segundo rosto onde máscara de roupa encontra face protegida
- **Status:** PENDENTE

### 7. Artefatos de borda
- **Problema:** Restos de roupa nas laterais quando detecção não cobre 100%
- **Status:** PENDENTE

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

### 9. GFPGAN/CodeFormer face restore
- **Status:** PENDENTE

### 10. Old stuck jobs no Redis
- **Status:** PENDENTE

---

## ✅ Implementados nesta sessão (2026-07-04/05)

| Item | Status |
|------|--------|
| SegFormer B2 detector (18 classes, per-class masks) | ✅ |
| Ensemble: SegFormer PRIMARY clothes, BiRefNet PRIMARY person | ✅ |
| max_area_pct=0.80 para SegFormer | ✅ |
| Nesting filter pulado para SegFormer | ✅ |
| Labels via LABELS[cls_id] | ✅ |
| Morphological closing k=100-120 | ✅ |
| bitwise_and(person_binary) anti-bleeding | ✅ |
| Steps 60→50 | ✅ |
| NSFW prompt ultra-realistic | ✅ |
| Florence-2 REMOVIDO (código + referências) | ✅ |
| DetectorType enum: SEGFORMER + ENSEMBLE | ✅ |
| PROGRESSIVE_PASSES: florence2→segformer | ✅ |
| ControlNet Union SDXL (xinsir/controlnet-union-sdxl-1.0) | ✅ |
| ControlNet weight optimization (w=0.3 optimal) | ✅ |
| ESRGAN 4x-UltraSharp pure upscaler | ✅ |
| `/v1/tools/upscale-esrgan` endpoint | ✅ |

---

## Referências

| Arquivo | Caminho |
|---------|---------|
| Pipeline NSFW production | `services/se11-clothes-removal/app/services/pipeline_nsfw.py` |
| Pipeline NSFW experimental | `services/se11-clothes-removal/app/services/pipeline_nsfw_experimental.py` |
| SegFormer detector | `services/se10-clothes-segmentation/app/services/segformer_detector.py` |
| Ensemble detector | `services/se10-clothes-segmentation/app/services/ensemble_detector.py` |
| Lições aprendidas | `LIÇÕES.md` |
| Pesquisa VTON | `exploration/UPGRADE.md` |
