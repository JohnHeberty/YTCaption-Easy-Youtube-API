# PLAN.md — pipe_3layers_max v15: Body mask + Realismo Máximo

**Data:** 2026-06-23  
**Status:** v14 funcional — NSFW realista mas seios errados por falta de espaço  
**Objetivo:** Corrigir seios + maximizar realismo

---

## Problema Actual (v14)

A máscara `clothing_exact = body AND NOT exposed_skin` exclui a pele visível do decote → sobra só as alças e o corpo da camisola → o modelo não tem espaço para gerar seios correctos.

**Evidence:** debug masks mostram `05_clothing.png` com só alças+corpo camisola, sem zona do peito.

**O job original `cr_f5a80bef266e`** usava `combine_masks()` que cobria área muito maior → gerou NSFW correcto.

---

## Plano v15 — 4 Mudanças

### 1. Body mask como inpaint mask (CRÍTICO)

**ANTES:** `inpaint_mask = dilate(clothing_exact, 12px)` — só roupa (~20%)  
**NOVO:** `inpaint_mask = dilate(body_mask, 16px)` — torso inteiro (~40%)

```python
# ANTES:
clothing_exact = _cv2.bitwise_and(body_mask, _cv2.bitwise_not(exposed_skin))
inpaint_mask = _cv2.dilate(clothing_exact, kernel_12px, iterations=2)

# NOVO:
inpaint_mask = _cv2.dilate(body_mask, kernel_16px, iterations=2)
```

O modelo ganha TODO o torso para gerar pele/corpo → seios correctos.

### 2. Prompt mais realista

```python
DEFAULT_CLOTHES_PROMPT = (
    "NSFW, NSFW, NSFW, NSFW, NSFW, "
    "bare skin, smooth skin surface, realistic skin texture, "
    "detailed breast anatomy, realistic nipples, natural skin pores, "
    "seamless skin transition, consistent skin tone with surrounding body, "
    "photorealistic, professional photography, studio lighting, "
    "high resolution, sharp focus on skin detail, 8k uhd, "
    "hyperrealistic, detailed skin rendering, natural body proportions"
)
```

### 3. Negative mais forte contra roupa

```python
DEFAULT_CLOTHES_NEGATIVE = (
    "clothes, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pattern, floral, textile, garment, "
    "text, watermark, deformed, blurry, cartoon, anime, painting, CGI, "
    "extra limbs, disfigured, poorly drawn face, mutated hands, "
    "bad anatomy, deformed skin, wrinkled, scarred"
)
```

Adicionado: `top, blouse, shirt, dress, skirt, pattern, floral, textile, garment` (deteção mais forte contra roupa).

### 4. Dilatação 12px → 16px

```python
kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (16, 16))
inpaint_mask = _cv2.dilate(body_mask, kernel, iterations=2)
```

Cobre mais bordas entre pele e roupa.

---

## Parâmetros Mantidos do v14 (que já funcionavam)

- base_model: **juggernautXL**
- NsfwPov: **0.2**
- 1 pass: **0.75**
- sharpness: **2.0**
- guidance_scale: **4.0**
- clip_skip: **2**
- Color transfer: **activado**
- Clothing exact mask: **mantido para debug** (masks 05/06)

---

## Resultado Esperado v15

| Métrica | v14 actual | v15 esperado |
|---------|-----------|-------------|
| Área inpaint | ~20% (clothing exact) | **~40% (body mask)** |
| Seios | Errados (espaço pequeno) | **Correctos (espaço suficiente)** |
| Pele | Boa mas incompleta | **Hyperrealista** |
| Roupa residual | Alças visíveis | **Removida (negative forte)** |
| Face | 100% preservada | 100% preservada |
| BG | 100% preservado | 100% preservado |

---

## Arquivos a Modificar

| Arquivo | Linhas | Mudança |
|---------|--------|---------|
| `pipeline.py` | 24-27 | Prompt realista |
| `pipeline.py` | 32-37 | Negative forte |
| `pipeline.py` | 1984-1992 | body_mask + kernel 16px |
