# UPGRADE-2.md — NSFW Pendências Activas

**Data:** 2026-06-24
**Status:** v15 em produção + nsfw_test em teste

---

## Pendências

### 1. Optimizar dilatação nsfw_test
- **Problema:** 3% é pouco — head_adjusted几乎=idêntico ao head_mask
- **Solução:** testar 5-10% ou usar dilatação diferenciada para head vs inpaint
- **Impacto:** alças removidas + head zone correcta

### 2. PLAN-2: Detecção adaptativa de cabeça
- **Problema:** top 40% fixo — funciona para close-up mas não para full body
- **Solução:** haarcascade (OpenCV, CPU, ~10ms)
- **Referência:** `PLAN-2.md`

### 3. Promover nsfw_test para produção
- **Condição:** só após dilatação optimizada + PLAN-2 aprovados

### 4. GFPGAN/CodeFormer face restore
- **O que:** face restore pós-inpainting
- **Modelos:** já baixados em `data/models/face_restore/`
- **Complexidade:** MÉDIA
