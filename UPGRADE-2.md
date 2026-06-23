# UPGRADE-2.md — Plano NSFW Completo: Remoção de Roupa Preservando Pessoa

**Data:** 2026-06-23  
**Status:** Fase A concluída — Fase B em andamento  
**Objetivo:** Remoção 100% de roupa preservando rosto, corpo e pele da pessoa original

---

## Resultados Mais Recentes

### pipe_nsfw (Fase A+B — B1 concluída) ✅
| Métrica | JuggernautXL | **LUSTIFY NSFW** |
|---------|-------------|----------------|
| Face SSIM | 0.996 | **0.996** ✅ |
| BG diff | 0.3 | **0.3** ✅ |
| Torso | 20.5% | **20.2%** |
| Bot | 51.1% | **50.6%** |

**Configuração atual do pipe_nsfw:**
- Single-pass (1 chamada ao SE8 — evita CUDA assertion)
- NSFW_PROMPT + NSFW_NEGATIVE (sem bloqueio de nudez)
- NsfwPovAllInOne LoRA peso 0.5 (0.6+ causa CUDA assertion)
- Person mask composite + bilateral edge softening
- Face protection: top 35% zeroed

### Rota recomendada
```
POST /jobs {"image": "<base64>", "mode": "pipe_nsfw"}
```

---

## Fase A — Concluída ✅

### A1: nursing-handjob-ponyxl LoRA
- Status: ⚠️ Adiado
- Motivo: PonyXL format, pode ser incompatível com SDXL base

### A2: GFPGAN face restore
- Status: ✅ Modelos baixados
  - `data/models/face_restore/GFPGANv1.4.pth` (348MB)
  - `data/models/face_restore/codeformer.pth` (376MB)
- Próximo: criar microservice separado ou integrar via SE8

### A3: NsfwPovAllInOne peso 0.5
- Status: ✅ Funcionando
- Peso 0.6+: causa CUDA assertion (driver_api.cpp:15)
- LoRA carrega corretamente no SE8

---

## Fase B — Em Andamento

### B1: Modelo NSFW专用 ✅
- Status: ✅ Baixado e testado
- Modelo: `lustifySDXLNSFW_v20-inpainting.safetensors` (6.9GB)
- Source: `andro-flock/LUSTIFY-SDXL-NSFW-checkpoint-v2-0-INPAINTING`
- Resultado: Face=0.996, Bot=50.6% (similar ao JuggernautXL, mas deve gerar pele melhor)
- **Nota: verificar visualmente se a qualidade da pele melhorou vs JuggernautXL**

### B2: img2img em vez de inpainting
- SDXL img2img com strength controlado (0.5-0.6)
- Pode gerar pele melhor em áreas maiores
- Ação: testar via `/v1/generation/image-prompt`

---

## Fase C — Planejamento

### C1: Real-ESRGAN separado
- Não usar SE8 upscale (destrói imagem)
- Instalar como serviço Python dedicado

### C2: GFPGAN microservice
- Modelo já baixado, código existe em SE8
- Criar endpoint dedicado para face restore pós-processamento

### C3: ControlNet DensePose
- Detectar corpo 3D → guiar geração de pele
- Requer: DensePose model + ControlNet adapter

---

## Pipeline NSFW Ideal (quando completo)

```
1. Florence-2 detecta roupa → máscara
2. SE8 inpaint com modelo NSFW + LoRAs → remove roupa
3. GFPGAN/CodeFormer → restaura rosto
4. Person mask composite → protege fundo
5. Bilateral filter → suaviza bordas
6. Real-ESRGAN → melhora resolução final
```

---

## LoRAs Disponíveis no SE8
| LoRA | Tamanho | Peso | Status |
|------|---------|------|--------|
| NsfwPovAllInOneLoraSdxl | 1.8GB | 0.5 | ✅ Usado |
| nursing-handjob-ponyxl | 228MB | — | ⚠️ Adiado (PonyXL) |
| Minecraft_nsfw | 228MB | — | ❌ Minecraft |
| add-detail-xl | 228GB | 0.8 | ✅ Detalhes |
| sd_xl_offset | 49MB | 0.1 | ✅ Qualidade |
| sdxl_lcm_lora | 393MB | — | ✅ LCM fast |

## Referências
- [GFPGAN](https://github.com/TencentARC/GFPGAN) — Face restoration (37.5k stars)
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — Image super-resolution (35.9k stars)
- [Fooocus face_restoration.py](services/se8-image-generation/app/services/face_restoration.py)
