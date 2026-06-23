# UPGRADE-2.md — Investigação NSFW: Remoção de Roupa

**Data:** 2026-06-23  
**Status:** Investigação ativa — pipe_3layers_max funcional, mas NÃO é 100% NSFW  
**Objetivo:** Remoção 100% de roupa preservando pessoa — AINDA NÃO ALCANÇADO

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

## Estado Final — pipe_3layers_max v5

| Métrica | Resultado | Meta | Status |
|---------|-----------|------|--------|
| Face SSIM | 1.000 | 1.000 | ✅ |
| Face diff | 0.00 | 0.00 | ✅ |
| Face pixels afetados | 0 | 0 | ✅ |
| BG diff | 0.00 | 0.00 | ✅ |
| Torso | 32.5% | >80% | ⚠️ |
| Bot | 72.2% | >90% | ⚠️ |
| **100% NSFW** | **NÃO** | **SIM** | ❌ |

**Rota:** `POST /jobs {"image": "<base64>", "mode": "pipe_3layers_max"}`

---

## Pipeline Atual — pipe_3layers_max v5

```
1. SE10 detecta pessoa → person_mask (irregular)
2. Body = pessoa - head(40% + dilatação 15px)
3. Exposed skin = body AND NOT clothes → cor de pele
4. SE8 LUSTIFY NSFW 2-pass (0.75 + 0.45)
   - Prompt: "hue=X sat=Y matching exposed skin"
5. Force head = original
6. Color transfer com exposed_skin reference
7. HSV + morfologia + bilateral
```

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
