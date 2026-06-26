# PLAN-1.md — nsfw_test Pipeline (v17 BEST)

**Data:** 2026-06-26
**Status:** ✅ MELHOR RESULTADO ALCANÇADO

---

## Pipeline Final

```
1. SE10 Florence-2 detecta pessoa → person_binary
2. body_mask = person - head (top 40% + dilatação 15px)
3. body_closed = body_mask (copia)
4. Dilation 3.5% adaptativa → body_expanded
5. morphOpen 3px (suaviza cantos)
6. GaussianBlur 3px + threshold > 127 (SE8 vê binário)
7. morphClose 5px ellipse + vertical 1x7 (fecha gaps)
8. inpaint_mask → SE8
9. SE8: juggernautXL, erode=-3, strength=0.65, field=0.85
10. Paste binário → GaussianBlur 7px blend no resultado FINAL
11. head_adjusted force → resultado final
```

## Config Óptima (PROVEN)

| Parâmetro | Valor | Porquê |
|-----------|-------|--------|
| Dilation | 3.5% | Cobertura sem comer fundo |
| erode_or_dilate | -3 | Bordas limpas |
| strength | 0.65 | Pose preservada |
| field | 0.85 | Contexto amplo |
| morphOpen | 3px | Suaviza cantos |
| GaussianBlur | 3px | SE8 vê bordas suaves |
| morphClose | 5px + vertical | Fecha gaps (mão-cintura) |
| Smooth blend | 7px no output | Transição natural |
| NsfwPov | 0.3 | Textura pele |
| add-detail-xl | 1.0 | Detalhe máximo |

## Prompts

**Positive:** `NSFW×5, solo, bare skin, same body position, unchanged pose, skin tone matching arms/face, 8k uhd`

**Negative:** `(deformed:1.3), extra limbs, airbrushed, plastic skin, (changed pose:1.5), clothes, fabric, bra, straps`

## Lições

| O que NÃO funciona | O que FUNCIONA |
|---------------------|----------------|
| 5% dilation | 3.5% dilation |
| Máscara suave para SE8 | Binário para SE8 + suave no output |
| Reinhard LAB | Sem LAB (pele correcta) |
| strength 0.55/0.80 | strength 0.65 |
| 2-pass | 1 pass |
| GaussianBlur 15px | GaussianBlur 7px no output |
| face_only (V3) | head_adjusted (binário) |
| bilateral filter | Sem bilateral |
