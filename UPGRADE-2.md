# UPGRADE-2.md — Plano NSFW Completo: Remoção de Roupa Preservando Pessoa

**Data:** 2026-06-23  
**Status:** pipe_3layers_max v5 funcional — Skin Color Reference implementado  
**Objetivo:** Remoção 100% de roupa preservando rosto, cabeça, cabelo e fundo + pele realista

---

## pipe_3layers_max v5 — MELHOR RESULTADO ✅

| Métrica | Resultado |
|---------|-----------|
| Face SSIM | **1.000** ✅ |
| Face diff | **0.00** ✅ |
| BG diff | **0.00** ✅ |
| Torso | 32.5% |
| Bot | 72.2% |
| Head cutoff | 40% + dilatação 15px para cabelo |
| Skin color | **Exato** (HSV mediana da pele exposta) |

**Rota:** `POST /jobs {"image": "<base64>", "mode": "pipe_3layers_max"}`

### Pipeline v5 — 6 camadas de proteção
```
1. SE10 detecta pessoa → person_mask
2. Body = pessoa - head(40%) + dilatação para cabelo
3. Exposed skin = body AND NOT clothes → cor de pele como referência
4. SE8 LUSTIFY NSFW 2-pass com prompt de cor (hue=X sat=Y)
5. Force head → original
6. Color transfer usando exposed_skin como referência
7. HSV + morfologia + bilateral blend
```

### Debug visualization
Salvo automaticamente como `{job_id}_debug.png`:
- VERMELHO = rosto+cabeça (preservado)
- VERDE = pele exposta (referência de cor)
- AMARELO = área de inpaint (NSFW)
- AZUL = máscara de pessoa

---

## Histórico Completo

| Versão | Bot | Torso | Face | Melhoria |
|--------|-----|-------|------|----------|
| pipe_nsfw_subtract v3 | 72.4% | 34.2% | 1.000 | baseline |
| pipe_3layers v1 | 51.3% | 8.0% | 1.000 | precisão |
| pipe_3layers_max v1 | 51.3% | 23.3% | 1.000 | corpo inteiro |
| pipe_3layers_max v2 | 72.1% | 41.2% | 1.000 | head 30% (incluir ombros) |
| pipe_3layers_max v3 | 72.2% | 37.9% | 1.000 | head 35% (sweet spot) |
| pipe_3layers_max v4 | 72.1% | 32.4% | 1.000 | head mask com cabelo |
| **pipe_3layers_max v5** | **72.2%** | **32.5%** | **1.000** | **skin color reference** |

---

## Skin Color Reference ✅

### Problema
Modelo NSFW gera pele genérica — tom pode ser diferente da pessoa.

### Solução implementada
1. **exposed_skin** = body_mask AND NOT clothes_mask (braços, pernas, pescoço)
2. **median HSV** da pele exposta → cor EXATA da pessoa
3. **Prompt dinâmico**: `"skin tone hue=100 saturation=50 matching person's exposed skin"`
4. **Color transfer**: usa exposed_skin como referência (não border genérica)

---

## Descobertas Críticas

1. **DEFAULT_CLOTHES_NEGATIVE bug** — bloqueava NSFW
2. **SE8 upscale/enhance DESTRÓI** — só inpainting com máscara preserva
3. **JuggernautXL não gera NSFW** — LUSTIFY resolve
4. **3-camadas = melhor precisão** — pessoa→head→body→clothes→inpaint
5. **Head mask 40% + dilatação** — protege rosto+cabeça+cabelo
6. **exposed_skin reference** — pele gerada combina com a pessoa
7. **2-pass (0.75+0.45)** — remoção + refinamento sem degradar
8. **Debug visualization** — mostra todas as camadas em overlaid

---

## Referências
- [LUSTIFY SDXL NSFW](https://huggingface.co/andro-flock/LUSTIFY-SDXL-NSFW-checkpoint-v2-0-INPAINTING) — 6.9GB
- [GFPGAN](https://github.com/TencentARC/GFPGAN) — Face restoration (pendente integração)
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — Image super-resolution
