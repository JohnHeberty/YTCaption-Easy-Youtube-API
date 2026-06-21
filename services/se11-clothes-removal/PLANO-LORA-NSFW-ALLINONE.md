# PLANO: LoRA NsfwPovAllInOneLoraSdxl

## Status: ⏳ PENDENTE (era ignorada por bug de key_map)
**Peso sugerido:** 0.3-0.6
**Compatibilidade:** SDXL 1.0 — treinada para pele/corpo realista

## O que é
LoRA NSFW "All-In-One" para SDXL. Treinada para:
- Pele realista com textura e sombreamento
- Corpo feminino com anatomia correta
- Iluminação natural
1.8GB, ~2958 unmatched keys (era ignorada pelo bug anterior)

## IMPORTANTE
Esta LoRA era ignorada por "2958 unmatched keys" — mas era o mesmo bug de key_map vazio.
Agora com o fix de rebuild key_map, DEVE funcionar.

## Teste
1. Verificar se carrega: `LoRA [NsfwPov...] → UNet: XXX keys at weight 0.5`
2. Se carregar, testar E2E
3. Ajustar peso (0.3 = sutil, 0.6 = forte)
4. Cuidado: pode gerar conteúdo NSFW forte

## Parâmetros
| Param | Valor |
|-------|-------|
| Weight | 0.3 (conservador) |
| Prompt | bare skin, smooth skin surface, realistic skin texture |
| Negative | clothes, fabric, bra, straps, underwear |
| Denoise | 0.75 |
| Respective field | 0.85 |
