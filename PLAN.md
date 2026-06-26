# PLAN.md — NSFW Pipeline

**Data:** 2026-06-26  
**Status:** ✅ v17 em produção (BEST RESULT)  
**Rotas:**
- Produção: `POST /jobs {"mode": "nsfw"}` → v17 body_mask + binary + smooth blend
- Teste: `POST /jobs {"mode": "nsfw_test"}` → alias para v17

---

## Pendências
1. PLAN-2: haarcascade head detection (detecção adaptativa)
2. GFPGAN face restore
3. Testar dilatação 5-10% (atual: 3.5%)

---

## Estado Final — v17 (PRODUCTION READY — BEST RESULT)

### Pipeline
```
1. SE10 Florence-2 detecta pessoa → person_binary
2. body_mask = person - head (top 40% + dilatação 15px)
3. body_closed = body_mask (cópia)
4. Dilation 3.5% adaptativa → body_expanded
5. morphOpen 3px (suaviza cantos)
6. GaussianBlur 3px + threshold > 127 (SE8 vê binário)
7. morphClose 5px ellipse + vertical 1x7 (fecha gaps)
8. inpaint_mask → SE8
9. SE8: juggernautXL, erode=-3, strength=0.65, field=0.85
10. Paste binário → GaussianBlur 7px blend no resultado FINAL
11. head_adjusted force → resultado final
```

### Parâmetros Produção

| Parâmetro | Valor |
|-----------|-------|
| base_model | juggernautXL_v8Rundiffusion |
| NsfwPov LoRA | 0.3 |
| add-detail-xl LoRA | 1.0 |
| inpaint_strength | 0.65 |
| inpaint_respective_field | 0.85 |
| inpaint_erode_or_dilate | -3 |
| sharpness | 2.0 |
| guidance_scale | 4.0 |
| clip_skip | 2 |
| inpaint_engine | v2.6 |
| steps | 30 (default) |
| head cutoff | 40% bbox + dilation 15px |
| dilation adaptativa | 3.5% |
| morphOpen | 3px |
| GaussianBlur (mask) | 3px |
| morphClose | 5px + vertical 1x7 |
| Smooth blend (output) | GaussianBlur 7px |

---

> **Lições aprendidas / Descobertas Críticas:** Ver `LIÇÕES.md`

---

## Arquivos de Referência

| Arquivo | Caminho |
|---------|---------|
| Pipeline principal | `services/se11-clothes-removal/app/services/pipeline.py` |
| HTTP Client | `services/se11-clothes-removal/app/infrastructure/http_client.py` |
| Models | `services/se11-clothes-removal/app/core/models.py` |
| Masks doc | `services/se11-clothes-removal/docs/TOP-MASK-CONFIG.md` |
| Plano anterior | `UPGRADE-1.md` (Phase 1+2) |
| Avaliação honesta | `UPGRADE-2.md` (v17 production) |
| Plano nsfw_test | `PLAN-1.md` (v17 best result) |
| Plano head detect | `PLAN-2.md` (haarcascade adaptativo) |
