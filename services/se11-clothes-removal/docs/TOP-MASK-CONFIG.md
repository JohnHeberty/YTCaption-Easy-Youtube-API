# TOP-MASK-CONFIG.md — Configuração de Máscaras pipe_3layers_max

**Data:** 2026-06-23  
**Objetivo:** Documentar TODA a configuração de máscaras do pipeline NSFW mais avançado

---

## Visão Geral

O `pipe_3layers_max` é o pipeline NSFW mais avançado implementado. Ele usa **máscaras baseadas em detecção real** (SE10 GroundingDINO/Florence-2) em vez de retângulos aproximados.

**Status atual:** Remoção PARCIAL (~32% torso, ~72% bottom). NÃO é 100% NSFW.  
**O que funciona:** Preservação perfeita de rosto, cabeça, cabelo e fundo.

---

## Pipeline Completo — 6 Máscaras

### Máscara 1: Person Mask (SE10 Detection)
```
SE10 segment(mode="person", classes="person, woman, man")
→ person_mask: máscara binária irregular da pessoa inteira
→ Inclui: cabeça, rosto, cabelo, braços, torso, pernas
→ Formato: segue o contorno real da pessoa (não retangular)
```
**Arquivo:** `{job_id}_mask_person.png` (preto=0, branco=255)

### Máscara 2: Head Mask (Rosto+Cabeça+Cabelo — PRESERVADO)
```
head_mask = person_mask[top 40% da bbox] AND person_mask
head_mask = dilate(head_mask, kernel=15px, 2 iter) AND person_mask
→ Protege: rosto, cabelo, pescoço
→ NUNCA tocado pelo SE8
```
**Arquivo:** `{job_id}_mask_head.png` (branco=protegido)  
**Cores no overlay:** VERMELHO

### Máscara 3: Body Mask (Corpo = Pessoa - Cabeça)
```
body_mask = person_mask AND NOT head_mask
→ Corpo: torso, ombros, braços, pernas
→ Esta é a área potencial de inpaint
```
**Arquivo:** `{job_id}_mask_body.png` (branco=corpo)

### Máscara 4: Exposed Skin (Pele Exposta — Referência de Cor)
```
clothes_mask = SE10 clothes detection (Florence-2)
exposed_skin = body_mask AND NOT clothes_mask
→ Pele visível: braços, pernas, pescoço
→ Usada como REFERÊNCIA de cor para HSV color transfer
```
**Arquivo:** `{job_id}_mask_exposed_skin.png` (branco=pele exposta)  
**Cores no overlay:** VERDE

### Máscara 5: Inpaint Mask (Área de INPAINT — onde o SE8 gera NSFW)
```
inpaint_mask = dilate(body_mask, kernel=7px, 1 iter)
→ Área que o SE8 vai preencher com pele
→ Inclui: torso, ombros, braços, pernas
→ NÃO inclui: rosto, cabeça, cabelo, fundo
```
**Arquivo:** `{job_id}_mask_inpaint.png` (branco=inpaint)  
**Cores no overlay:** AMARELO

### Máscara 6: Overlay (Visualização Combinada)
```
overlay = original
overlay[head_mask] = vermelho (preservado)
overlay[exposed_skin] = verde (referência)
overlay[inpaint_mask] = amarelo (NSFW)
→ Transparência 60% cores / 40% original
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
   └→ skin_hsv = mediana HSV de exposed_skin

4. Inpainting 2-pass
   └→ Pass 1: denoise 0.75 (remoção principal)
   └→ Pass 2: denoise 0.45 (refinamento)
   └→ Prompt dinâmico: "hue={skin_hsv.H} sat={skin_hsv.S} matching exposed skin"
   └→ Modelo: LUSTIFY SDXL NSFW Inpainting (6.9GB)
   └→ LoRAs: NsfwPovAllInOne 0.5, add-detail-xl 0.8

5. Composição
   └→ result = original (fund + rosto + cabeça)
   └→ result[inpaint_mask] = inpainted[inpaint_mask]
   └→ result[head_mask] = EXATAMENTE original (forçado)

6. Pós-processamento
   └→ HSV color transfer (usando exposed_skin como referência)
   └→ Force head = original (garantia dupla)
   └→ Morfologia abertura + fechamento nas bordas
   └→ Bilateral filter nas bordas da máscara
```

### Parâmetros

| Parâmetro | Valor | Nota |
|-----------|-------|------|
| head cutoff | 40% da bbox | Inclui rosto+cabeça+cabelo |
| head dilatação | kernel 15px, 2 iter | Pega bordas de cabelo |
| inpaint dilatação | kernel 7px, 1 iter | Cobre bordas da roupa |
| feather blur | 5px Gaussian | Transição suave |
| Pass 1 denoise | 0.75 | Remoção principal |
| Pass 2 denoise | 0.45 | Refinamento |
| NSFW LoRA weight | 0.5 | 0.6+ causa CUDA assertion |
| LUSTIFY model | lustifySDXLNSFW_v20-inpainting | 6.9GB |
| HSV color transfer | exposed_skin median | Cor exata da pessoa |

---

## Métricas

| Métrica | Resultado | Status |
|---------|-----------|--------|
| Face SSIM | 1.000 | ✅ Perfeita |
| Face diff | 0.00 | ✅ Zero mudança |
| Face pixels afetados | 0 | ✅ Limpo |
| BG diff | 0.00 | ✅ Fundo intacto |
| Torso change | 32.5% | ⚠️ Parcial |
| Bot change | 72.2% | ⚠️ Parcial |
| Total changed | 28.5% | ⚠️ Parcial |

**IMPORTANTE:** O resultado NÃO é 100% NSFW. É remoção parcial. O modelo gera pele mas não consegue remover 100% da roupa em uma passagem.

---

## Arquivos de Debug

O pipeline salva automaticamente 6 PNGs de debug no output_dir:

```
{job_id}_result.png          ← resultado final
{job_id}_mask_person.png     ← SE10 detection
{job_id}_mask_head.png       ← head protection
{job_id}_mask_body.png       ← body region
{job_id}_mask_exposed_skin.png ← skin color reference
{job_id}_mask_inpaint.png    ← inpaint area
{job_id}_mask_overlay.png    ← overlay colored
```

### Visualização pipe_3layers_max_masks.png (9 painéis)

```
┌──────────────────┬──────────────────┬──────────────────┐
│   ORIGINAL       │   RESULTADO v5   │   HEAD MASK      │
│                  │                  │   (vermelho)     │
├──────────────────┼──────────────────┼──────────────────┤
│   PERSON MASK    │   BODY MASK      │   EXPOSED SKIN   │
│   (SE10 real)    │   (corpo)        │   (referência)   │
├──────────────────┼──────────────────┼──────────────────┤
│   INPAINT MASK   │   OVERLAY ALL    │   DIFERENÇA      │
│   (área NSFW)    │   (camadas)      │   (pixels mudou) │
└──────────────────┴──────────────────┴──────────────────┘
```

---

## Limitações Conhecidas

1. **Não é 100% NSFW** — modelo gera pele mas remoção parcial (~32% torso)
2. **CUDA assertion** — SE8 bug intermitente (`driver_api.cpp:15`), single-pass evita
3. **Head cutoff 40%** — funciona para a maioria, mas poses diferentes podem precisar ajuste
4. **Dilatação 15px** — pode não capturar todo o cabelo em pessoas com cabelo muito grande
5. **Exposed skin pode ser pequeno** — se pessoa não tem pele exposta, referência de cor é fraca
6. **LUSTIFY model** — 6.9GB, precisa de GPU com VRAM suficiente
