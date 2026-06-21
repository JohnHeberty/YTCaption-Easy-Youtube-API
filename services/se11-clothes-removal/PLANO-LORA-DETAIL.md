# PLANO: LoRA add-detail-xl (Detail Tweaker XL)

## Status: ⏳ PENDENTE (bug de key_map impedia carregamento)
**Peso sugerido:** 0.8-1.2
**Compatibilidade:** SDXL 1.0 ✅

## O que é
Detail Tweaker XL (CivitAI ID 122359, 432K downloads). Aumenta/reduz detalhes da imagem.
Peso positivo = mais detalhe. Peso negativo = menos detalhe.
228MB, ~2958 keys.

## Teste
1. Adicionar ao payload SE11: `{"model_name": "add-detail-xl.safetensors", "weight": 1.0}`
2. Combinar com sd_xl_offset no slot 1
3. Testar com denoise=0.75 e prompt de skin
4. Comparar com e sem LoRA

## Parâmetros
| Param | Valor |
|-------|-------|
| Weight | 0.8 (conservador) |
| Prompt | bare skin, smooth skin surface, realistic skin texture |
| Denoise | 0.75 |
