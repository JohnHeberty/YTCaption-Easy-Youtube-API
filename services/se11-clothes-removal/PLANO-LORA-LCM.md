# PLANO: LoRA sdxl_lcm_lora (Latent Consistency Model)

## Status: ⏳ PENDENTE
**Peso sugerido:** 0.5-1.0
**Compatibilidade:** SDXL 1.0 — LCM LoRA para inference rápida (4-8 steps)

## O que é
LCM (Latent Consistency Model) LoRA. Permite geração em 4-8 steps em vez de 30+.
Útil para SPEED mas NÃO para qualidade máxima.
393MB, keys UNet + CLIP.

## Trade-off
- **Ganho:** Speed ~5x mais rápido (4 steps vs 30)
- **Perda:** Qualidade pode diminuir — LCM gera outputs mais suaves/menos detalhados
- **Uso recomendado:** Teste rápido, não para produção final

## Teste
1. Adicionar ao payload: `{"model_name": "sdxl_lcm_lora.safetensors", "weight": 1.0}`
2. Reduzir steps para 8
3. Testar speed vs qualidade
4. Comparar com sd_xl_offset

## Parâmetros
| Param | Valor |
|-------|-------|
| Weight | 1.0 |
| Steps | 8 (em vez de 30) |
| CFG | 1.0-2.0 (LCM funciona melhor com CFG baixo) |
| Denoise | 0.75 |
