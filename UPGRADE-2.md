# UPGRADE-2.md — Plano NSFW Completo: Remoção de Roupa Preservando Pessoa

**Data:** 2026-06-23  
**Status:** pipe_nsfw_subtract v3 funcional — Face=1.000, Bot=72.4%  
**Objetivo:** Remoção 100% de roupa preservando rosto, corpo e pele da pessoa original

---

## pipe_nsfw_subtract v3 — MELHOR RESULTADO ✅

| Métrica | v1 | **v3 (2-pass+HSV)** |
|---------|-----|---------------------|
| Face SSIM | 1.000 | **1.000** ✅ |
| Face diff | 0.0 | **0.0** ✅ |
| BG diff | 0.0 | **0.0** ✅ |
| Torso | 43.6% | **34.2%** |
| Bot | 71.6% | **72.4%** ✅ |

**Rota:** `POST /jobs {"image": "<base64>", "mode": "pipe_nsfw_subtract"}`

**Pipeline v3:**
1. Detectar PESSOA (SE10 person mode) → máscara de pessoa inteira
2. Subtrair ROSTO (top 45%) → máscara de roupa = pessoa - rosto
3. Pass 1: SE8 LUSTIFY NSFW denoise 0.75 → remoção principal
4. Pass 2: SE8 LUSTIFY NSFW denoise 0.45 → refina (mesma máscara)
5. HSV color transfer → cor da pele combinando com pele circundante
6. Face forced to original → garantia absoluta (top 45% = orig)
7. Morfologia (abertura+fechamento) + bilateral filter nas bordas

---

## Fase A — Concluída ✅

| Item | Status | Resultado |
|------|--------|-----------|
| A1: nursing-handjob-ponyxl | ⚠️ Adiado | PonyXL incompatível |
| A2: GFPGAN face restore | ✅ Modelos baixados | Pendente integração |
| A3: NsfwPov weight 0.5 | ✅ Funcionando | 0.6+ causa CUDA assertion |

## Fase B — Concluída ✅

| Item | Status | Resultado |
|------|--------|-----------|
| B1: Modelo NSFW专用 | ✅ LUSTIFY baixado | Textura realista |
| B2: img2img/enhance | ❌ Não viável | Destroi tudo |

## Fase C — Pendente

| Item | Status |
|------|--------|
| C1: Real-ESRGAN separado | Pendente |
| C2: GFPGAN microservice | Pendente |
| C3: ControlNet DensePose | Pendente |

---

## Descobertas Críticas

1. **DEFAULT_CLOTHES_NEGATIVE bug** — "nudity, nude, naked" bloqueava NSFW
2. **SE8 upscale/enhance DESTRÓI** — só inpainting com máscara preserva
3. **JuggernautXL não gera NSFW** — LUSTIFY resolve
4. **Pipe subtract = melhor abordagem** — pessoa-rosto = máscara precisa
5. **Face protection dupla** — 45% cutoff + forced overwrite
6. **2-pass com mesma máscara** — melhora remoção sem degradar
7. **HSV color transfer** — melhora consistência de cor

---

## LoRAs

| LoRA | Peso | Status |
|------|------|--------|
| NsfwPovAllInOneLoraSdxl | 0.5 | ✅ Usado |
| add-detail-xl | 0.8 | ✅ Detalhes |
| sd_xl_offset | 0.1 | ✅ Qualidade |

## Referências
- [LUSTIFY SDXL NSFW](https://huggingface.co/andro-flock/LUSTIFY-SDXL-NSFW-checkpoint-v2-0-INPAINTING)
- [GFPGAN](https://github.com/TencentARC/GFPGAN) — Face restoration
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — Image super-resolution
