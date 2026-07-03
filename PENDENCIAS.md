# PENDENCIAS.md — Items Pendentes

**Data:** 2026-07-03
**Última atualização:** TESTE1.jpg face-ellipse fallback E2E success

---

## NSFW Pipeline — Status Atual

### ✅ RESOLVIDO — Multi-Detector Ensemble (YOLO11-seg + GD) (2026-07-03)
- **Problema:** GroundingDINO falha em 1.6% coverage para TESTE1.jpg (roupa escura, fundo complexo)
- **Solução:** YOLO11-seg como detector paralelo + ensemble voting com centroid consensus
- **Resultado:** YOLO11-seg detecta 53.3% coverage (33x melhor que GD)
- **Deploy:** SE10: `yolo_detector.py`, `ensemble_detector.py`, `segmentor.py` atualizados. `pip install ultralytics`
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — BiRefNet-portrait como detector SOTA (2026-07-03)
- **Problema:** Queríamos a melhor precisão possível para person segmentation
- **Solução:** BiRefNet-portrait ONNX como terceiro detector no ensemble, GPU via RTX 3090
- **Resultado:** 98.9% confiança, 49.4% coverage, **0.8s no GPU** (vs 31s CPU = 39x speedup)
- **Deploy:** SE10: `birefnet_detector.py` + Dockerfile CUDA symlinks + docker-compose GPU runtime
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — Face-ellipse fallback para detecção de pessoa (2026-07-03)
- **Problema:** SE10 GroundingDINO falha em imagens com fundo complexo/roupa escura (TESTE1.jpg: 1.6% coverage)
- **Solução:** Three-level fallback chain: (1) retry lower thresholds → (2) GrabCut from face → (3) face-ellipse 4×8
- **Resultado:** E2E success job `cr_987fd61e9121`, composite=10.611, face 100% preservada
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — Florence-2 clothes false positives (2026-07-03)
- **Problema:** 31 garment detections (spaghetti strap ×15, camisole ×8, hoodie ×7)
- **Solução:** box_threshold 0.06→0.12, text_threshold 0.04→0.08
- **Status:** ✅ RESOLVIDO (ainda detecta 14, mas confidences baixas 0.12-0.20, pipeline funciona)

### ✅ RESOLVIDO — Docker haarcascade missing (2026-07-03)
- **Problema:** `opencv-python-headless` não inclui haarcascade XML
- **Solução:** Cópia local em `app/haarcascade_frontalface_default.xml` + path fallback
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — Container crash com 1G memory (2026-07-03)
- **Problema:** InsightFace ONNX + MediaPipe + SE10 calls > 1G
- **Solução:** Memory increased 1G → 2G
- **Status:** ✅ RESOLVIDO

### ✅ RESOLVIDO — Face protection layered mask (2026-07-02)
- **Problema:** Body-based approach (person − head) criava buracos e comia roupa
- **Solução:** Layered approach (person − (hair OR face)) profissional
- **Status:** ✅ RESOLVIDO em produção + experimental

---

## Pendências Ativas

### 1. Face ghost no pescoço
- **Problema:** SE8 gera segundo rosto onde máscara de roupa encontra face protegida
- **Causa:** Prompt NSFW força anatomia em regiões de transição
- **Solução candidata:** Ajustar prompt por região ou inpaint em 2 passes
- **Status:** PENDENTE

### 2. Artefatos de borda
- **Problema:** Restos de roupa nas laterais quando detecção não cobre 100%
- **Solução candidata:** Dilatação adaptativa ou multi-pass mask refinement
- **Status:** PENDENTE

### 3. SE8 CUDA assertion com 60 steps
- **Problema:** 60 steps x 5 tries pode causar CUDA assertion na RTX 3090
- **Solução candidata:** Reduzir steps para 40 ou adicionar delay entre tries
- **Status:** PENDENTE

### 4. GFPGAN/CodeFormer face restore
- **O que:** Face restore pós-inpainting
- **Modelos:** Já baixados em `data/models/face_restore/`
- **Complexidade:** MÉDIA
- **Status:** PENDENTE

### 5. OpenPose ControlNet quality tuning
- **Problema:** MediaPipe 33-landmark stick figure incompatível com OpenPose COCO/Body_25
- **Solução candidata:** Substituir por preprocessador OpenPose oficial ou mapear landmarks
- **Status:** PENDENTE

### 6. Florence-2 ainda detecta muitos garments (14) mesmo com threshold 0.12
- **Problema:** 14 detecções com confidences baixas (0.12-0.20) — hoodie, camisole, spaghetti strap, blouse
- **Impacto baixo:** Pipeline funciona, masks de IP-Adapter ref são utilitárias
- **Solução candidata:** Aumentar threshold ainda mais (0.15?) ou usar NMS para suprimir overlapping boxes
- **Status:** BAIXA PRIORIDADE

### 7. Old stuck jobs no Redis
- **Problema:** Jobs antigos ficam com status QUEUED e reprocessam infinitamente
- **Jobs limpos:** `cr_e5308ec29643`, `cr_64b8c8ada8e6` removidos manualmente
- **Solução candidata:** TTL no status QUEUED ou limpeza automática no worker
- **Status:** PENDENTE

### 8. BiRefNet-portrait como detector avançado (Futuro)
- **O que:** BiRefNet-portrait é SOTA em segmentação de pessoa (melhor que rembg/u2net)
- **Impacto:** Poderia substituir face-ellipse fallback com máscara de alta qualidade
- **Complexidade:** MÉDIA — ONNX exportável, ~200MB modelo
- **Status:** ✅ RESOLVIDO — Implementado como detector no SE10 + ensemble. 928MB ONNX model, 99.7% confiança

---

## ✅ Implementados nesta sessão

| Item | Status |
|------|--------|
| Haarcascade adaptive head detection | ✅ |
| Debug grid 3x3 (8 painéis) | ✅ |
| Masks individuais (00-07) | ✅ |
| Person mask hole fill (floodFill) | ✅ |
| Head mask bottom clip (não cresce para corpo) | ✅ |
| CFG Scale 4.0 → 7.0 (Fooocus match) | ✅ |
| Steps 40 → 60 (Fooocus Quality) | ✅ |
| Sampler → dpmpp_2m_sde_gpu | ✅ |
| Strength 0.65 → 0.85/0.90/1.00 | ✅ |
| Clothes-only inpaint mask strategy | ✅ |
| LAB color transfer (skin tone match) | ✅ |
| Face-only protection (haarcascade small) | ✅ |
| Clothes classes expanded (skirt, pants, etc.) | ✅ |
| Pipeline separation (prod vs test) | ✅ |
| SE11 API refactoring (15→23 schemas) | ✅ |
| Swagger: file upload + dropdowns + auth | ✅ |
| POLITICA-USO.md + README.md | ✅ |
| SE4 field name fix (transcription bug) | ✅ |
| Layered mask construction (person − (hair OR face)) | ✅ |
| Face-ellipse fallback (3-level chain) | ✅ |
| Florence-2 threshold 0.06→0.12 | ✅ |
| Docker haarcascade copy + path fallback | ✅ |
| SE11 memory 1G→2G | ✅ |
| Per-mask independent debug saves | ✅ |

---

## Referências

| Arquivo | Caminho |
|---------|---------|
| Pipeline NSFW | `docs/archived/PLAN.md` |
| Spec haarcascade | `docs/archived/PLAN-2.md` |
| Spec SE9 animação | `services/se9-make-video-img/docs/SE9-UP.md` |
| Lições aprendidas | `LIÇÕES.md` |
| Política de uso | `services/se11-clothes-removal/POLITICA-USO.md` |
