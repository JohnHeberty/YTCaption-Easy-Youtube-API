# TOP-MASK-CONFIG.md — Configuração de Máscaras pipe_3layers_max

**Data:** 2026-06-23  
**Versão:** v7 (clothing mask exata como inpaint)  
**Objetivo:** Documentar TODA a configuração de máscaras do pipeline NSFW mais avançado

---

## Visão Geral

O `pipe_3layers_max` é o pipeline NSFW mais avançado implementado. Ele usa **máscaras baseadas em detecção real** (SE10 GroundingDINO/Florence-2) em vez de retângulos aproximados.

**Mudança v7:** Inpaint mask agora usa a **roupa EXATA** (body AND NOT exposed_skin) em vez do body dilatado. Modelo sabe exatamente onde remover.

---

## Pipeline — 8 Máscaras Sequenciais (00-07)

### 00: Original
```
Imagem de entrada (base64)
```
**Arquivo:** `00_original.png`

### 01: Person Mask (SE10 Detection)
```
SE10 segment(mode="person", classes="person, woman, man")
→ person_mask: máscara binária irregular da pessoa inteira
→ Inclui: cabeça, rosto, cabelo, braços, torso, pernas
→ Formato: segue o contorno real da pessoa (não retangular)
```
**Arquivo:** `01_person.png` (preto=0, branco=255)

### 02: Head Mask (Rosto+Cabeça+Cabelo — PRESERVADO)
```
head_mask = person_mask[top 40% da bbox] AND person_mask
head_mask = dilate(head_mask, kernel=15px, 2 iter) AND person_mask
→ Protege: rosto, cabelo, pescoço
→ NUNCA tocado pelo SE8
```
**Arquivo:** `02_head_protected.png` (branco=protegido)  
**Cores no overlay:** VERMELHO

### 03: Body Mask (Corpo = Pessoa - Cabeça)
```
body_mask = person_mask AND NOT head_mask
→ Corpo: torso, ombros, braços, pernas
→ Esta é a área base para cálculos
```
**Arquivo:** `03_body.png` (branco=corpo)

### 04: Exposed Skin (Pele Exposta — Referência de Cor)
```
clothes_mask = SE10 clothes detection (Florence-2)
exposed_skin = body_mask AND NOT clothes_mask
→ Pele visível: braços, pernas, pescoço
→ Usada como REFERÊNCIA de cor para HSV color transfer
```
**Arquivo:** `04_exposed_skin.png` (branco=pele exposta)  
**Cores no overlay:** VERDE

### 05: Clothing Mask (ROUPA EXATA — A mais importante!)
```
clothing_exact = body_mask AND NOT exposed_skin
→ É o INVERSO da exposed_skin dentro do corpo
→ Representa EXATAMENTE onde tem roupa na pessoa
→ ESTA é a máscara usada como inpaint mask
```
**Arquivo:** `05_clothing.png` (branco=roupa)  
**Cores no overlay:** MAGENTA

### 06: Inpaint Mask (ROUPA EXATA dilatada — onde o SE8 gera NSFW)
```
inpaint_mask = dilate(clothing_exact, kernel=7px, 2 iter)
→ Área que o SE8 vai preencher com pele
→ APENAS a roupa (não o corpo inteiro!)
→ Modelo sabe exatamente onde remover
```
**Arquivo:** `06_inpaint_mask.png` (branco=inpaint)  
**Cores no overlay:** AMARELO

### 07: Result (Resultado Final)
```
composited = inpainted * inpaint_soft + original * (1 - inpaint_soft)
composited[head_mask] = original[head_mask]  # força cabeça = original
```
**Arquivo:** `07_result.png`

### Overlay (Visualização Combinada)
```
overlay = original
overlay[head_mask] = vermelho (preservado)
overlay[exposed_skin] = verde (referência)
overlay[clothing_exact] = magenta (roupa)
overlay[inpaint_mask] = amarelo (NSFW)
→ Texto: "1=HEAD 4=SKIN 5=CLOTH 6=INPAINT"
```
**Arquivo:** `{job_id}_mask_overlay.png`

---

## Pipeline Técnico Completo

### Etapas

```
1. SE10 Detecta Pessoa
   └→ person_mask (irregular, contorno real da pessoa)

2. Calcula Body Mask
   └→ body = person - head(40% bbox + dilatação 15px)
   └→ head sigue formato da pessoa (AND com person_mask)

3. Detecta Roupa + Pele Exposta
   └→ clothes_mask = SE10 Florence-2 clothes detection
   └→ exposed_skin = body AND NOT clothes
   └→ clothing_exact = body AND NOT exposed_skin (ROUPA EXATA)
   └→ skin_hsv = mediana HSV de exposed_skin

4. Inpainting 2-pass (AGORA com clothing mask exata!)
   └→ Pass 1: denoise 0.75 (remoção principal)
   └→ Pass 2: denoise 0.45 (refinamento)
   └→ Prompt dinâmico: "remove clothing, expose skin hue={H} sat={S}"
   └→ Modelo: LUSTIFY SDXL NSFW Inpainting (6.9GB)
   └→ LoRAs: NsfwPovAllInOne 0.6, add-detail-xl 0.8

5. Composição
   └→ result = inpainted * soft + original * (1-soft)
   └→ result[head_mask] = EXATAMENTE original (forçado)

6. Pós-processamento
   └→ HSV color transfer (usando exposed_skin como referência)
   └→ Force head = original (garantia dupla)
   └→ Morfologia abertura + fechamento nas bordas
   └→ Bilateral filter nas bordas da máscara
```

### Parâmetros (v7)

| Parâmetro | Valor | Nota |
|-----------|-------|------|
| head cutoff | 40% da bbox | Inclui rosto+cabeça+cabelo |
| head dilatação | kernel 15px, 2 iter | Pega bordas de cabelo |
| **inpaint mask** | **clothing_exact dilatado** | **ROUPA EXATA (não body!)** |
| inpaint dilatação | kernel 7px, 2 iter | Cobre bordas da roupa |
| feather blur | 5px Gaussian | Transição suave |
| Pass 1 denoise | 0.75 | Remoção principal |
| Pass 2 denoise | 0.45 | Refinamento |
| **NSFW LoRA weight** | **0.6** | **era 0.5, subiu para mais textura** |
| LUSTIFY model | lustifySDXLNSFW_v20-inpainting | 6.9GB |
| HSV color transfer | exposed_skin median | Cor exata da pessoa |

---

## Métricas

| Métrica | v5 (body dilatado) | v7 (clothing exata) | Status |
|---------|-------------------|---------------------|--------|
| Face SSIM | 1.000 | 1.000 | ✅ Perfeita |
| Face diff | 0.00 | 0.00 | ✅ Zero mudança |
| BG diff | 0.00 | 0.00 | ✅ Fundo intacto |
| Inpaint area | ~60% body | ~20% clothing | ✅ Mais preciso |
| Skin blending | Parcial | Melhor (matching arms) | ✅ Melhorou |

---

## Arquivos de Debug (Sequenciais 00-07)

```
00_original.png       ← imagem de entrada
01_person.png         ← detecção SE10
02_head_protected.png ← cabeça (protegida)
03_body.png           ← corpo = pessoa - cabeça
04_exposed_skin.png   ← pele exposta (ref cor)
05_clothing.png       ← ROUPA EXATA (inverso pele)
06_inpaint_mask.png   ← dilatado → NSFW
07_result.png         ← resultado final
{job_id}_mask_overlay.png ← cores + legenda numérica
```

---

## Limitações Conhecidas

1. **CUDA assertion** — SE8 bug intermitente (`driver_api.cpp:15`), retry com backoff
2. **Head cutoff 40%** — funciona para a maioria, poses diferentes podem precisar ajuste
3. **Exposed skin pode ser pequeno** — se pessoa não tem pele exposta, referência de cor é fraca
4. **LUSTIFY model** — 6.9GB, precisa de GPU com VRAM suficiente
5. **NsfwPov 0.6** — 0.7+ causa CUDA assertion, 0.6 é o máximo estável
