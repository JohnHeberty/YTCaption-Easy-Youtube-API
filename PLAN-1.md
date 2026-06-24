# PLAN-1.md — nsfw_test Pipeline Actual

**Data:** 2026-06-24
**Status:** 🟡 Em teste — funcionando, pendente optimizar dilatação

---

## Pipeline actual

```
1. SE10 Florence-2 detecta pessoa → person_mask
2. Head zone (top 40%) → head_mask
3. Body = person - head → body_mask
4. Clothing = body AND NOT exposed_skin → clothing_exact
5. FloodFill fecha buracos da roupa → clothing_closed
6. Dilate 3% → clothes_expanded
7. GaussianBlur 15px → inpaint_mask (suavizado)
8. head_adjusted = head AND NOT inpaint_bin
9. SE8 juggernautXL 1 pass (0.75, NsfwPov 0.2)
10. Reinhard LAB color transfer
11. GaussianBlur collage (31+15px) → resultado
```

## O que funciona
- Máscara da roupa fechada (floodFill)
- Bordas suaves (GaussianBlur 15px)
- Head_adjusted usa a mesma máscara que vai ao SE8
- Sem force de cabeça no resultado final
- Face limpa, corpo realista, fundo preservado

## O que precisa de optimizar
- **Dilatação 3% é pouco** — head_adjusted quase igual a head_mask
- **Alças** ainda parcialmente visíveis
- **3% não chega à head zone** — subtração mínima (0.2%)

## Lições documentadas
- ❌ Smooth antes de SE8 OK, mas head_adjusted precisa de binário
- ❌ head_force no resultado final = máscara antiga visível
- ❌ face_only (V3) = bordas feias na face
- ❌ seamlessClone MIXED_CLONE = traz roupa de volta
- ❌ HSV correction = artefactos vermelhos
- ❌ 2-pass 0.50 = blobs (regenera conteúdo)
- ✅ Smooth + head_adjusted + sem force final
- ✅ Reinhard LAB > HSV para matching de cor
- ✅ GaussianBlur collage > color_transfer
