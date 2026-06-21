# PLANO MAESTRO: Melhoria de Qualidade SE11 Clothes Removal

## Estado Atual
- v12: resultado aceitável mas blusa verde em vez de pele
- SE10 detecta parcialmente a roupa
- SE8 gera roupa nova em vez de pele (bias do JuggernautXL)
- Bug de LoRA key_map corrigido mas não testado

## Abordagens Disponíveis

### A) LoRAs Compatíveis (AGORA POSSÍVEL com fix de key_map)

| LoRA | Peso | Prioridade | Arquivo |
|------|------|------------|---------|
| sd_xl_offset | 0.1 | ALTA (já usado) | `PLANO-LORA-OFFSET.md` |
| add-detail-xl | 0.8-1.0 | ALTA | `PLANO-LORA-DETAIL.md` |
| sdxl_lcm_lora | 1.0 | MÉDIA (speed) | `PLANO-LORA-LCM.md` |
| NsfwPovAllInOneLoraSdxl | 0.3-0.6 | ALTA (pele realista) | `PLANO-LORA-NSFW-ALLINONE.md` |
| nursing-handjob-ponyxl | — | ❌ INCOMPATÍVEL | `PLANO-LORAS-INCOMPATIVEIS.md` |
| Minecraft_nsfw | — | ❌ NÃO ÚTIL | `PLANO-LORAS-INCOMPATIVEIS.md` |

### B) Combinações de LoRAs a Testar

**Combo 1: Qualidade Máxima**
- sd_xl_offset (0.1) + add-detail-xl (0.8) + NsfwPovAllInOne (0.3)
- Denoise=0.75, steps=30
- Risco: VRAM pode ser insuficiente (3 LoRAs = ~2.3GB extra)

**Combo 2: Qualidade + Speed**
- sd_xl_offset (0.1) + sdxl_lcm (0.8)
- Steps=8, CFG=1.5
- Risco: qualidade reduzida

**Combo 3: Seguro (1 LoRA)**
- add-detail-xl (1.0) sozinha
- Denoise=0.75

### C) Download de LoRAs Externas (CivitAI)

| LoRA | ID CivitAI | Download | Compatível |
|------|-----------|----------|------------|
| Detail Tweaker XL | 122359 | ✅ Já baixada | SDXL 1.0 |
| SDXL Skin Detail | — | Pesquisar | SDXL 1.0 |
| EpicRealism SDXL | — | Pesquisar | SDXL 1.0 |

### D) Refiner SDXL
- Baixar modelo refiner SDXL (ex: juggernautXL_refiner)
- Ativar pipeline refiner para segunda passada
- Melhora detalhes mas aumenta VRAM

### E) Prompt Engineering Adicional
- Testar prompts de referência (Fooocus inpaint default prompts)
- Testar inpaint_additional_prompt separado do prompt principal
- Testar weight/emphasis: "(skin:1.3), (seamless:1.2)"

## Ordem de Execução Recomendada

1. **IMEDIATO:** Testar sd_xl_offset corrigido (key_map fix)
2. **PRÓXIMO:** Testar add-detail-xl sozinha
3. **DEPOIS:** Combo sd_xl_offset + add-detail-xl
4. **SE VIÁVEL:** Testar NsfwPovAllInOneLoraSdxl
5. **FUTURO:** Refiner, LoRAs externas, prompt engineering avançado

## Critérios de Sucesso
- Resultado com pele realista que combina com o tom da mulher
- Sem textura cinza/esverdeada
- Sem conteúdo NSFW visível
- Bordas suaves entre original e inpainted
- Fundo 100% preservado
