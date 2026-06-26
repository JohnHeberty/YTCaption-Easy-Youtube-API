# UPGRADE-2.md — Investigação NSFW: Remoção de Roupa

**Data:** 2026-06-23  
**Status:** v15 em produção + nsfw_test superior em teste  
**Objetivo:** NSFW realista preservando pessoa — PARCIALMENTE ALCANÇADO

---

## ⚠️ AVALIAÇÃO HONESTA

> **Lições aprendidas (o que funciona, o que não funciona, limitações):** Ver `LIÇÕES.md` (Secções 2, 3, 4, 5)

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

> **Lição sobre simplicidade vs complexidade:** Ver `LIÇÕES.md` Secção 4

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

> **Lições sobre collage, seamlessClone, HSV, 2-pass:** Ver `LIÇÕES.md` Secções 2, 3, 7

### Pipeline nsfw_test final
```
SE8 Pass 1 (0.75) → head force → Reinhard LAB color transfer → GaussianBlur collage (31+15px) → head force
```

---

## Referências

---

## O que precisa para 100% NSFW

> **Avaliação de abordagens:** Ver `LIÇÕES.md` Secção 5

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
