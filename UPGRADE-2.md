# UPGRADE-2.md — Plano NSFW Completo: Remoção de Roupa Preservando Pessoa

**Data:** 2026-06-22  
**Status:** Pesquisa concluída — Próximos passos definidos  
**Objetivo:** Remoção 100% de roupa preservando rosto, corpo e pele da pessoa original

---

## Estado Atual

### O que funciona ✅
| Componente | Versão | Resultado |
|------------|--------|-----------|
| Detecção de roupa | v83/v82 (progressive) | Face=1.000, Bot=62.9% |
| Detecção straps | v24 (single pass) | Remove alças corretamente |
| Face protection | top 35% zeroed | Rosto preservado |
| Color correction | HSV BGR mean shift | Cor consistente |

### O que NÃO funciona ❌
| Componente | Problema |
|------------|----------|
| **SDXL inpainting NSFW** | Gera manchas cinza em máscaras >15% |
| **SE8 upscale pós-inpainting** | Regenera imagem inteira (Face=0.649) |
| **Morphological open/close** | Degrada bordas excessivamente |
| **DEFAULT_CLOTHES_NEGATIVE** | Contém "nudity, nude" — bloqueia NSFW |

### LoRAs Disponíveis no SE8
| LoRA | Tamanho | Status |
|------|---------|--------|
| **NsfwPovAllInOneLoraSdxl** | 1.8GB | ✅ Instalado (peso 0.5) |
| **nursing-handjob-ponyxl** | 228MB | ⚠️ PonyXL (incompatível com SDXL) |
| **Minecraft_nsfw** | 228MB | ❌ Minecraft style |
| **add-detail-xl** | 228MB | ✅ Detalhes |
| **sd_xl_offset** | 49MB | ✅ Qualidade |
| **sdxl_lcm_lora** | 393MB | ✅ LCM fast inference |

### Modelos Face Restore (BAIXADOS ✅)
| Modelo | Status | Caminho |
|--------|--------|---------|
| **GFPGANv1.4.pth** | ✅ Baixado (348MB) | `data/models/face_restore/` |
| **codeformer.pth** | ✅ Baixado (376MB) | `data/models/face_restore/` |
| **Fooocus face_restoration.py** | ✅ Código existe | `app/services/face_restoration.py` |

### Checkpoint
- **juggernautXL_v8Rundiffusion** (7.1GB) — SDXL base, NÃO NSFW-treinado

---

## Próximos Passos — Plano de Ação

### FASE A: Testar LoRAs e Face Restore (curto prazo)

**A1. Testar nursing-handjob-ponyxl** — LoRA NSFW PonyXL, pode ter efeito melhor que NsfwPov
- Risco: PonyXL pode ser incompatível com SDXL base
- Ação: testar com peso 0.3-0.5, verificar se gera resultado diferente

**A2. Testar GFPGAN face restore pós-inpainting**
- O SE8 já tem `face_restoration.py` com código para GFPGAN e CodeFormer
- Ação: chamar `restore_face()` após o inpainting para restaurar rosto
- Esperado: rosto mais realista, sem degradação

**A3. Testar NsfwPovAllInOne com peso MAIOR (0.8-1.0)**
- Peso atual: 0.5 (pouco efeito)
- Ação: testar com 0.8 e 1.0

### FASE B: Modelo NSFW专用 (médio prazo)

**B1. Baixar modelo NSFW fine-tuned**
- Opções:
  - **Pony Diffusion V6 XL** — SDXL fine-tuned para NSFW
  - **Animagine XL** — SDXL NSFW (anime focus)
  - **Unstable AI Horizons** — SDXL NSFW
- Ação: substituir `juggernautXL` por modelo NSFW no SE8
- Risco: ~6.5GB download, precisa testar compatibilidade com Fooocus

**B2. Usar img2img em vez de inpainting**
- SDXL img2img usa `strength` para controlar mudança
- Com strength=0.5-0.6: preserva estrutura original, gera conteúdo novo
- Ação: testar via SE8 rota `/v1/generation/image-prompt` com denoise controlado
- Esperado: melhor geração de pele que inpainting com máscara

### FASE C: Pipeline Externo (longo prazo)

**C1. Real-ESRGAN separado**
- Não usar SE8 upscale (destrói imagem)
- Instalar Real-ESRGAN como serviço Python separado
- Usar apenas para melhorar resolução FINAL após tudo processado

**C2. ControlNet DensePose**
- Detectar corpo 3D → guiar geração de pele
- Requer: DensePose model + ControlNet adapter
- Complexidade: ALTA (novo modelo ~2GB + treinamento)

**C3. API externa NSFW**
- Considerar serviços dedicados: Replicate, fal.ai, etc.
- Vantagem: modelos treinados para NSFW
- Desvantagem: custo, latência, dependência externa

---

## Pipeline NSFW Ideal (quando completo)

```
1. Florence-2 detecta roupa → máscara
2. SE8 inpaint com modelo NSFW + LoRAs pesados → remove roupa
3. GFPGAN/CodeFormer → restaura rosto
4. Person mask composite → protege fundo
5. Bilateral filter → suaviza bordas
6. Real-ESRGAN → melhora resolução final
```

---

## Referências
- [GFPGAN](https://github.com/TencentARC/GFPGAN) — Face restoration (37.5k stars)
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — Image super-resolution (35.9k stars)
- [Fooocus face_restoration.py](services/se8-image-generation/app/services/face_restoration.py) — Já integrado no SE8
- [NsfwPovAllInOne LoRA](data/models/loras/NsfwPovAllInOneLoraSdxl-000009.safetensors) — 1.8GB, peso atual 0.5
