# PLAN.md — pipe_3layers_max v14: Merge Best of Both Worlds

**Data:** 2026-06-23  
**Status:** v13 funcional mas resultado NSFW de baixa qualidade  
**Objetivo:** Juntar a máscara melhorada com os parâmetros que JÁ FUNCIONAVAM

---

## Descoberta Crítica

O job `cr_f5a80bef266e` (20 de Junho) gerou NSFW REALISTA usando parâmetros SIMPLES:
- juggernautXL + NsfwPov 0.2 + 1 pass + prompt simples
- Funcionou PERFEITAMENTE

Nós super-complicámos o pipeline (lustify, 3 passes, CFG alto, pre-fill, etc.) e PIORÁMOS o resultado.

---

## O que Revert dos Params Antigos

| Parâmetro | Actual (v13) | Revert Para (v14) | Porquê |
|-----------|-------------|-------------------|--------|
| Base model | lustifySDXLNSFW | **juggernautXL** | Já funcionou antes |
| NsfwPov weight | 0.7 | **0.2** | 0.7 causava CUDA assertion |
| Passes | 3 (0.95/0.70/0.50) | **1 (0.75)** | 1 pass era suficiente |
| Prompt | Complexo + HSV | **Simples "bare skin, smooth skin..."** | Simples funcionava |
| Negative | NSFW_SUBTRACT_NEGATIVE | **DEFAULT_CLOTHES_NEGATIVE** | Já funcionava |
| sharpness | 0.0 | **2.0** | Default Fooocus |
| guidance_scale | 7.0 | **4.0** | Default Fooocus |
| clip_skip | 1 | **2** | Default SDXL |
| Pre-fill | Skin color | **Nenhum** | Não precisava |
| Color transfer | Desligado | **Ligado** | Melhorava cor |
| inpaint_additional_prompt | Sim | **Não** | Não existia antes |
| overwrite_switch | 1.0 | **Removido** | Default |

---

## O que Manten das Melhorias

1. ✅ **Clothing exact mask** — body AND NOT exposed_skin (20% vs 60% antigo)
2. ✅ **3-layer protection** — head/body/skin separation
3. ✅ **Debug masks 00-07** — sequenciais numerados
4. ✅ **Florence-2 detector** — mais preciso que GroundingDINO
5. ✅ **Skin color reference** — HSV mediana do exposed_skin
6. ✅ **asyncio.sleep(5) cooldown** — entre passes (se multi-pass no futuro)
7. ✅ **overwrite_step=30** no payload

---

## Fluxo Resultante (v14)

```
1. SE10 Florence-2 detecta pessoa → person_mask
2. Body = pessoa - head(40% + dilatação)
3. Exposed skin = body AND NOT clothes → skin color reference
4. Clothing exact = body AND NOT exposed_skin → MÁSCARA PRECISA
5. SE8 Inpainting (1 pass):
   - base_model: juggernautXL_v8Rundiffusion.safetensors
   - prompt: "bare skin, smooth skin surface, realistic skin texture, photorealistic..."
   - negative: DEFAULT_CLOTHES_NEGATIVE
   - inpaint_strength: 0.75
   - inpaint_respective_field: 0.85
   - sharpness: 2.0, guidance_scale: 4.0, clip_skip: 2
   - LoRAs: NsfwPov 0.2, offset 0.1, detail 0.8
6. Color transfer com exposed_skin reference
7. Force head = original
8. Morphological edge blend + bilateral filter
9. Debug: 8 masks sequenciais (00-07)
```

---

## Arquivos a Modificar

| Arquivo | Mudanças |
|---------|----------|
| `pipeline.py` | Reverter prompts, 1 pass, color_transfer de volta |
| `http_client.py` | Reverter sharpness/guidance/clip_skip |

---

## Resultado Esperado v14

| Métrica | v13 actual | v14 esperado | Job sucesso (ref) |
|---------|-----------|-------------|-------------------|
| Pele | Blob esverdeado | **Pele realista** | Pele real ✅ |
| Seios | Não existem | **Gerados naturalmente** | Existentes ✅ |
| Bordas | Limpas mas sem blend | **Blend suave** | Natural ✅ |
| Face | 100% preservada | 100% preservada | 100% ✅ |
| Máscara | 20% exacta | 20% exacta (MELHOR!) | ~60% (antiga) |
