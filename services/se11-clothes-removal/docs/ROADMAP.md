# ROADMAP.md — SE11 Clothes Removal

**Última atualização:** 2026-07-05

---

## Status Atual

Pipeline funcional: SE10 (SegFormer B2 + YOLO11) → SE11 (head mask, body mask, inpaint mask) → SE8 (LustifyNSFW + ControlNet Union SDXL + IP-Adapter + ESRGAN 4x). Composite score: 3.83 (TESTE1.jpg, 3 tentativas). GPU idle: 502 MiB.

---

## 🎯 Prioridade ALTA

### 1. Testar com mais imagens
- **Problema:** Só testamos com TESTE1.jpg (mulher, fundo gaming)
- **Necessário:** Diversos poses, camadas de roupa, ângulos, iluminação
- **Status:** PENDENTE

### 2. Detecção Real vs IA (Anti-Fotos Reais)
- **Problema:** Precisamos impedir que fotos de pessoas reais entrem na pipeline NSFW
- **Solução:** Bombek1/ai-image-detector-siglip-dinov2 (99.1% acurácia, SDXL/MJ/DALL-E/Flux)
- **Ação:** Rejeitar com erro 400 antes de qualquer processamento
- **Onde:** Todas as rotas NSFW (`/jobs/nsfw`, `/jobs/nsfw-test`)
- **Plano detalhado:** `services/se11-clothes-removal/docs/plans/PLAN-AI-DETECT.md`
- **Status:** IMPLEMENTADO (2026-07-10) — `ai_image_detector.py` + routes.py pre-check + config toggle `AI_DETECTION_ENABLED`

### 3. Face ghost no pescoço
- **Problema:** SE8 gera segundo rosto onde máscara de roupa encontra face protegida
- **Status:** PENDENTE

### 4. Artefatos de borda
- **Problema:** Restos de roupa nas laterais quando detecção não cobre 100%
- **Status:** PENDENTE

---

## 🟡 Prioridade MÉDIA

### 5. Otimizar composite score — landmark drift
- **Problema:** strength=0.92 algumas vezes causa pose_changed=true
- **Causa provável:** DWPose landmarks muito sensíveis a micro-mudanças
- **Solução candidata:** Ajustar thresholds ou usar métrica diferente
- **Status:** PENDENTE

### 6. Fase 4: Centroid-based person matching — multi-person
- **Problema:** Pipeline assume 1 pessoa por imagem
- **Solução:** Centroid-based person matching para múltiplas pessoas
- **Complexidade:** ALTA
- **Status:** PENDENTE

### 7. Face Restoration (GFPGAN/CodeFormer)
- **Ação:** após o blend final, aplicar GFPGAN ou CodeFormer na região facial
- **Modelos já baixados:** `data/models/face_restore/GFPGANv1.4.pth` + CodeFormer
- **Plano:** Fase C do PLAN-HEAD.md
- **Status:** PENDENTE

### 8. Advanced Blending (Poisson Editing)
- **Ação:** tentar `cv2.seamlessClone` com NORMAL_CLONE apenas na região de transição
- **Plano:** Fase B do PLAN-HEAD.md
- **Status:** PENDENTE

---

## 🔵 Prioridade BAIXA

### 9. Lazy-load IP-Adapter/ControlNet no SE8
- **Problema:** IP-Adapter e ControlNet carregados na memória mesmo sem uso
- **Economia:** ~2.7GB RAM
- **Complexidade:** MÉDIA
- **Status:** PENDENTE

### 10. Lazy-load ControlNet Union no SE8
- **Problema:** Modelo é carregado toda request
- **Economia:** ~2.4GB
- **Status:** PENDENTE

### 11. show/ Permission Denied
- **Problema:** SE11 (container Docker) não consegue copiar resultado para `/root/YTCaption-Easy-Youtube-API/show/`
- **Solução:** Montar `show/` como volume no docker-compose do SE11
- **Complexidade:** BAIXA
- **Status:** PENDENTE

### 12. Old stuck jobs no Redis
- **Status:** PENDENTE

---

## 🚀 Upgrades Arquiteturais (LONGO PRAZO)

### DensePose + Human Parsing (SE10)
- **Fase 1 do UPGRADE-VTON.md**
- Adicionar DensePose ao SE10 para geometria real do corpo
- Usar human parsing para proteger cabelo/mãos/pés
- **Status:** PENDENTE

### ControlNet real no SE8 (já parcialmente feito)
- **Fase 2 do UPGRADE-VTON.md**
- ✅ Union SDXL integrado (weight=0.3)
- Restante: ativar DensePose como condicionamento adicional
- **Status:** PARCIAL

### SE11 integração DensePose
- **Fase 3 do UPGRADE-VTON.md**
- Enviar densepose do SE10 para SE8 no payload de inpaint
- **Status:** PENDENTE

### IP-Adapter FaceID (identidade por embedding)
- **Fase D do PLAN-HEAD.md**
- Usar rosto original como referência via IP-Adapter FaceID
- Requer modelo `ip-adapter-faceid-plusv2_sdxl`
- **Status:** PENDENTE

### Encoder dedicado de pele (IDM-VTON style)
- **Fase 4 do UPGRADE-VTON.md**
- Modificar UNet do Fooocus para codificador paralelo de aparência
- Complexo demais — só se Fase 1+2+3 não forem suficientes
- **Status:** PENDENTE

---

## Itens Rejeitados

| Item | Motivo | Data |
|------|--------|------|
| SDXL Refiner | Destrói pose (5/5), RAM +75% | 2026-07-05 |
| OpenPose ControlNet quality tuning | INCOMPATÍVEL com LustifyNSFW (9 canais) | 2026-07-05 |
| Refiner realista pós-inpainting | Disco com 5GB livres insuficiente | — |
| MediaPipe → DWPose | DWPose substituído (126 keypoints) | 2026-07-04 |
| Florence-2 | Falsos positivos catastroficos | 2026-07-04 |
| GroundingDINO/SAM2/BiRefNet | Broken/unused, fully removed | 2026-07-05 |

---

## Referências

| Documento | Caminho |
|-----------|---------|
| Plano master face blend | `services/se11-clothes-removal/docs/plans/PLAN-HEAD.md` |
| Pesquisa VTON | `services/se11-clothes-removal/docs/plans/UPGRADE-VTON.md` |
| Plano nsfw_test v2 | `services/se11-clothes-removal/docs/plans/UPGRADE-V2.md` |
| Pesquisa pipeline | `services/se11-clothes-removal/docs/plans/SEARCH.md` |
| Plano master qualidade | `services/se11-clothes-removal/docs/plans/PLANO-MAESTRO.md` |
| Lições aprendidas | `services/se11-clothes-removal/docs/LICOES-NSFW.md` |
