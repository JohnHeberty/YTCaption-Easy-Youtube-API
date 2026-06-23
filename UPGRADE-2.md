# UPGRADE-2.md — Plano NSFW Completo: Remoção de Roupa Preservando Pessoa

**Data:** 2026-06-23  
**Status:** Fase A+B concluídas — pipe_nsfw funcional com LUSTIFY NSFW  
**Objetivo:** Remoção 100% de roupa preservando rosto, corpo e pele da pessoa original

---

## Estado Final — pipe_nsfw ✅

| Métrica | 1-pass (antes) | **2-pass (atual)** |
|---------|---------------|-------------------|
| Face SSIM | 0.996 | **0.996** ✅ |
| BG diff | 0.3 | **0.3** ✅ |
| Torso | 20.5% | **32.3%** ✅ |
| Bot | 51.1% | **45.8%** |
| Overall | 24.1% | **27.3%** |
| Modelo | LUSTIFY NSFW | **LUSTIFY NSFW** |

**Rota:** `POST /jobs {"image": "<base64>", "mode": "pipe_nsfw"}`

**Pipeline 2-pass:**
1. Pass 1: Florence-2 wide classes + low threshold (0.04) → SE8 LUSTIFY NSFW denoise 0.70
2. Pass 2: Re-detect remaining clothing → SE8 LUSTIFY NSFW denoise 0.55
3. Person mask composite (protege rosto+fundo)
4. Bilateral filter nas bordas

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
| B1: Modelo NSFW专用 | ✅ LUSTIFY baixado | Textura realista (variance 3404) |
| B2: img2img/enhance | ❌ Não viável | Destroi tudo (100% change) |

## Fase C — Pendente

| Item | Status | Próximo |
|------|--------|---------|
| C1: Real-ESRGAN separado | Pendente | Serviço Python dedicado |
| C2: GFPGAN microservice | Pendente | Modelo já baixado |
| C3: ControlNet DensePose | Pendente | Requer pesquisa |

---

## Descobertas Críticas

1. **DEFAULT_CLOTHES_NEGATIVE bug** — "nudity, nude, naked" bloqueava NSFW → gerava roupa
2. **SE8 upscale/enhance DESTRÓI** — só inpainting com máscara preserva
3. **JuggernautXL não gera NSFW** — manchas cinza em máscaras >15%
4. **LUSTIFY gera textura realista** — variance 3404, histogram 0.813
5. **Face protection** — zero top 35% antes de inpainting
6. **Person mode = desastres** — detecta pele como roupa
7. **Clothes mode = correto** — detecta só roupa
8. **CUDA assertion** — 0.6+ LoRA weight causa, single-pass evita

---

## LoRAs

| LoRA | Peso | Status |
|------|------|--------|
| NsfwPovAllInOneLoraSdxl | 0.5 | ✅ Usado |
| nursing-handjob-ponyxl | — | ⚠️ Adiado |
| add-detail-xl | 0.8 | ✅ Detalhes |
| sd_xl_offset | 0.1 | ✅ Qualidade |

## Referências
- [LUSTIFY SDXL NSFW](https://huggingface.co/andro-flock/LUSTIFY-SDXL-NSFW-checkpoint-v2-0-INPAINTING)
- [GFPGAN](https://github.com/TencentARC/GFPGAN) — Face restoration
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — Image super-resolution
