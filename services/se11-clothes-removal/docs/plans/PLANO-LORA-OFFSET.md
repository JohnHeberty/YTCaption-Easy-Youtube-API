# PLANO: LoRA sd_xl_offset_example-lora_1.0

## Status: ✅ JÁ USANDO (padrão)
**Peso atual:** 0.1
**Compatibilidade:** SDXL 1.0 — mas 2364 unmatched keys (bug: key_map vazio no init)

## O que é
LoRA built-in do SDXL para offset noise. Aumenta sutilmente detalhe e textura.
49MB, 2364 keys (todas UNet).

## Bug Corrigido
- `_init_lora_key_maps()` chamado antes do modelo estar carregado → key_map vazio
- `match_lora()` retorna 0 matched → LoRA ignorada
- Fix: rebuild key_map no `_apply_single_lora()` se vazio

## Teste
1. Rebuild SE8 com fix do `model_base.py`
2. Verificar logs: `LoRA [sd_xl_offset...] → UNet: XXX keys at weight 0.1`
3. E2E test SE11 com mesma imagem
4. Comparar com resultado anterior (v12)

## Parâmetros
| Param | Valor |
|-------|-------|
| Weight | 0.1 |
| Prompt | bare skin, smooth skin surface, realistic skin texture, photorealistic |
| Negative | clothes, fabric, bra, straps, underwear, nipples, areola |
| Denoise | 0.75 |
| Erode | -10 |
| Respective field | 0.85 |
