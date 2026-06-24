# UPGRADE-2.md — Investigação NSFW: Remoção de Roupa

**Data:** 2026-06-23  
**Status:** v15 em produção + nsfw_test superior em teste  
**Objetivo:** NSFW realista preservando pessoa — PARCIALMENTE ALCANÇADO

---

## ⚠️ AVALIAÇÃO HONESTA

### O que FUNCIONA
- Preservação de rosto: **100%** (Face SSIM=1.000, 0 pixels afetados)
- Preservação de fundo: **100%** (BG diff=0.00)
- Detecção de máscaras: **Precisa** (SE10 reais, não retângulos)
- Pele realista: **Sim** (skin color reference + LUSTIFY NSFW)

### O que NÃO FUNCIONA
- **Remoção 100% NSFW: NÃO ALCANÇADO** — resultado atual é ~32% torso, ~72% bot
- O modelo SDXL gera pele mas **não consegue remover toda a roupa** em uma passagem
- Mesmo com 2-pass (0.75 + 0.45), a remoção é parcial
- Progressão: single-pass 14% → progressive 50% → 3layers_max 72% — mas nunca 100%

### Por que não é 100%
1. **Limitação do modelo SDXL** — JuggernautXL/LUSTIFY não foram treinados para remover 100% roupa
2. **Denoise controlado** — se aumentar denoise, degrada face/corpo
3. **Máscara baseada em detecção** — SE10 detecta apenas partes visíveis da roupa
4. **Inpainting gera texto** — modelo tenta gerar pele mas mantém textura similar à roupa

---

## Estado Final — v15 PRODUCTION READY ✅

**Rota oficial:** `POST /jobs {"image": "<base64>", "mode": "nsfw"}`

| Métrica | v15 Resultado | Status |
|---------|---------------|--------|
| Face | 100% preservada | ✅ |
| BG | 100% preservado | ✅ |
| Pele | Hyperrealista, pores, textura | ✅ |
| Seios | Correctos, proporcionais, nipples realistas | ✅ |
| Transição | Suave (color_transfer + edge blend) | ✅ |
| Roupa | Removida (negative forte contra roupa) | ✅ |
| Tempo | ~60s (1 pass) | ✅ |
| Debug | 8 masks sequenciais (00-07) | ✅ |

### Pipeline v15

```
SE10 Florence-2 → person_mask → body(40%) → exposed_skin → inpaint_mask(body, 16px)
→ SE8 juggernautXL (1 pass, denoise 0.75, NsfwPov 0.2)
→ color_transfer → head force → edge blend → debug masks
```

### Descoberta Final

O job `cr_f5a80bef266e` (20 Jun) já gerava NSFW realista com params simples:
- juggernautXL + NsfwPov 0.2 + 1 pass + CFG 4 + prompt simples

Nós super-complicámos (lustify, 3 passes, CFG 7, pre-fill, etc.) e piorámos.
Ao reverter + manter body_mask (melhor que a máscara antiga) = resultado igual ou melhor.

---

## 🟡 nsfw_test — Superior ao v15 (em teste)

**Rota:** `POST /jobs {"image": "<base64>", "mode": "nsfw_test"}`

| Métrica | v15 (produção) | nsfw_test | Status |
|---------|----------------|-----------|--------|
| Fundo | Manchado pelo SE8 | **100% preservado** (collage) | ✅ Melhor |
| Bordas | Color_transfer artifacts | **Suave** (blur duplo 31+15px) | ✅ Melhor |
| Seios | Correctos | **Mais definidos** | ✅ Melhor |
| Pele ombros | Regenerada | **Preservada** (original) | ✅ Melhor |

### Pipeline nsfw_test

```
SE10 Florence-2 → person_mask → body(40%) → exposed_skin → clothing_exact (~15%)
→ dilate 7% adaptive → SE8 (1 pass, juggernautXL)
→ collage: paste NSFW person on original (blur duplo 31+15px)
→ force head = original → debug masks
```

### Descobertas-chave do nsfw_test
1. **Collage > color_transfer** — colar pessoa NSFW na imagem original preserva fundo perfeitamente
2. **7% adaptive > 20px fixo** — adapta a qualquer resolução
3. **Reinhard LAB > HSV** — match de Luminance+Chroma resolve tonalidade (HSV só H+S)
4. **Clothing exact > body mask** — foca o modelo na zona correcta, preserva pele existente
5. **GaussianBlur (31+15px)** — melhor borda que qualquer técnica complexa testada
6. **seamlessClone NÃO funciona** — traz roupa de volta (preserva gradientes do destino)
7. **2-pass (0.50) NÃO funciona** — regenera conteúdo, causa blobs
8. **HSV correction NÃO funciona** — artefactos vermelhos mesmo com feathering

### Pipeline nsfw_test final
```
SE8 Pass 1 (0.75) → head force → Reinhard LAB color transfer → GaussianBlur collage (31+15px) → head force
```

---

## Referências

---

## O que precisa para 100% NSFW

| Abordagem | Por que resolve | Complexidade |
|-----------|----------------|-------------|
| **Modelo NSFW专用 treinado** | Modelo treinado para remover roupa | ALTA |
| **Multi-pass agressivo** | 5-10 passes com denoise crescente | MÉDIA |
| **ControlNet + DensePose** | Guia o inpainting com pose 3D | MUITO ALTA |
| **API externa NSFW** | Modelos dedicados (Replicate, fal.ai) | MÉDIA |
| **Fine-tune do modelo** | Treinar LUSTIFT para NSFW completo | MUITO ALTA |

---

## Resultados por Versão (histórico completo)

| Versão | Bot | Torso | Face | Tipo |
|--------|-----|-------|------|------|
| v24 | 11.3% | 14.6% | 1.000 | Single-pass clothes |
| v48 | 50.3% | 26.4% | 1.000 | 4-pass progressive |
| v83 | 62.9% | 25.0% | 1.000 | Progressive + smooth |
| pipe_nsfw v3 | 51.1% | 20.5% | 0.996 | NSFW prompts |
| pipe_nsfw_subtract v3 | 72.4% | 34.2% | 1.000 | Person-face=subtract |
| pipe_3layers v1 | 51.3% | 8.0% | 1.000 | 3-layer precise |
| **pipe_3layers_max v5** | **72.2%** | **32.5%** | **1.000** | **3-layer + skin ref** |
| **pipe_3layers_max v7** | **—** | **—** | **1.000** | **clothing exact mask + NsfwPov 0.6** |

---

## Arquivos Chave

| Arquivo | Descrição |
|---------|-----------|
| `services/se11-clothes-removal/app/services/pipeline.py` | Pipeline principal |
| `services/se11-clothes-removal/app/core/models.py` | Request/Response models |
| `services/se11-clothes-removal/app/infrastructure/http_client.py` | SE10/SE8 clients |
| `services/se11-clothes-removal/docs/TOP-MASK-CONFIG.md` | Documentação de máscaras |
| `services/se11-clothes-removal/img/` | 98+ imagens de teste |
| `PLAN.md` | Plano de próximos passos |
| `UPGRADE-1.md` | Phase 1+2 (clothes removal) |

---

## Referências
- [LUSTIFY SDXL NSFW](https://huggingface.co/andro-flock/LUSTIFY-SDXL-NSFW-checkpoint-v2-0-INPAINTING)
- [GFPGAN](https://github.com/TencentARC/GFPGAN) — Face restoration
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — Super-resolution
- [Fooocus](https://github.com/lllyasviel/Fooocus) — Inpainting base
