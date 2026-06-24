# PLAN.md — NSFW Pipeline

**Data:** 2026-06-24  
**Status:** ✅ v15 em produção + 🟡 nsfw_test em teste  
**Rotas:**
- Produção: `POST /jobs {"mode": "nsfw"}` → v15 body_mask
- Teste: `POST /jobs {"mode": "nsfw_test"}` → smooth mask + head_adjusted + collage

---

## Pendências nsfw_test
1. Optimizar dilatação (3% → testar 5-10%)
2. PLAN-2: haarcascade head detection
3. GFPGAN face restore

---

## Estado Final — v15 (Production Ready)

### Pipeline
```
1. SE10 Florence-2 detecta pessoa → person_mask
2. Body = pessoa - head(40% + dilatação 15px)
3. Exposed skin = body AND NOT clothes → skin color reference
4. Inpaint mask = dilate(body_mask, 16px, 2 iter) → torso inteiro
5. SE8 Inpainting (1 pass):
   - base_model: juggernautXL_v8Rundiffusion
   - prompt: "NSFW×5, bare skin, detailed breast anatomy, hyperrealistic..."
   - negative: clothes/fabric/bra/straps/underwear/top/blouse/shirt/dress...
   - denoise: 0.75, field: 0.85, sharpness: 2.0, CFG: 4.0
   - LoRAs: NsfwPov 0.2, offset 0.1, detail 0.8
6. Color transfer com exposed_skin reference
7. Force head = original
8. Morphological edge blend + bilateral filter
9. Debug: 8 masks sequenciais (00-07)
```

### Parâmetros Produção

| Parâmetro | Valor |
|-----------|-------|
| base_model | juggernautXL_v8Rundiffusion |
| NsfwPov LoRA | 0.2 |
| inpaint_strength | 0.75 |
| inpaint_respective_field | 0.85 |
| inpaint_erode_or_dilate | -8 |
| sharpness | 2.0 |
| guidance_scale | 4.0 |
| clip_skip | 2 |
| inpaint_engine | v2.6 |
| steps | 30 (default) |
| head cutoff | 40% bbox |
| head dilation | kernel 15px, 2 iter |
| inpaint kernel | 16px, 2 iter |

---

## Descobertas Críticas

1. **Simplicidade > Complexidade** — params simples (juggernautXL, 1 pass, CFG 4) superaram 3 passes + lustify + CFG 7
2. **Job `cr_f5a80bef266e`** (20 Jun) já fazia NSFW realista — nós super-complicámos
3. **body_mask > clothing_exact** — modelo precisa de espaço para gerar corpo, não só roupa
4. **5x NSFW no prompt** — força o modelo a gerar conteúdo explícito
5. **Negative sem "nipples/areola"** — remover estes termos do negative permite geração
6. **color_transfer** — destruía cores quando activo em pipelines complexos, mas funciona no pipeline simples
7. **fooocus_fill()** — cria blur da cor média; com body_mask dá cor de pele, com clothing_exact dava cor da roupa

---

## Arquivos de Referência

| Arquivo | Caminho |
|---------|---------|
| Pipeline principal | `services/se11-clothes-removal/app/services/pipeline.py` |
| HTTP Client | `services/se11-clothes-removal/app/infrastructure/http_client.py` |
| Models | `services/se11-clothes-removal/app/core/models.py` |
| Masks doc | `services/se11-clothes-removal/docs/TOP-MASK-CONFIG.md` |
| Plano anterior | `UPGRADE-1.md` (Phase 1+2) |
| Avaliação honesta | `UPGRADE-2.md` (v15 + nsfw_test) |
| Plano nsfw_test | `PLAN-1.md` (clothing + collage) |
| Plano head detect | `PLAN-2.md` (haarcascade adaptativo) |
