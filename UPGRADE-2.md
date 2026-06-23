# UPGRADE-2.md — Plano NSFW Completo: Remoção de Roupa Preservando Pessoa

**Data:** 2026-06-22  
**Status:** Investigação ativa  
**Objetivo:** Remoção 100% de roupa preservando rosto, corpo e pele da pessoa original

---

## BUG CRÍTICO ENCONTRADO E CORRIGIDO (pipe_nsfw)

### O que acontecia
O `DEFAULT_CLOTHES_NEGATIVE` continha `"nudity, nude, naked, nipples, areola, breast"` — termos que **BLOQUEIAM geração de nudez**. O SE8 recebia contradição: prompt="gerar pele" + negative="NÃO gere nudez" → gerava **roupa com cor de pele**.

### Correção aplicada
- pipe_nsfw agora usa `NSFW_PROMPT` + `NSFW_NEGATIVE` (sem bloqueio de nudez)
- LoRA NsfwPovAllInOne weight 0.5
- Denoise 0.70

---

## Pipeline NSFW Proposta (pipe_nsfw)

### Etapas da Pipeline
```
1. Clothes detection (Florence-2) → detectar SÓ a roupa
2. Inpainting (denoise 0.65) → gerar pele na área da roupa
3. Person detection (na ORIGINAL) → máscara da pessoa inteira
4. Composite: colar resultado NSFW dentro da máscara de pessoa sobre original
5. Bilateral filter nas bordas → suavizar transição da colagem
6. (OPCIONAL) SE8 upscale 2x → melhorar qualidade
```

### Descobertas Importantes

| Componente | Resultado | Nota |
|------------|-----------|------|
| Clothes detection | ✅ Funciona | Florence-2 detecta roupa corretamente |
| Inpainting denoise=0.65 | ✅ Funciona | Gera pele nova na área mascarada |
| Person mask composite | ⚠️ Parcial | Funciona mas precisa proteger rosto (top 35%) |
| Bilateral filter | ✅ Suaviza | Remove artefatos de borda |
| **SE8 upscale** | **❌ DESTRÓI** | **Regenera imagem inteira, face SSIM=0.649** |
| **Prompt bug (FIXED)** | **❌ Gerava roupa** | **DEFAULT_CLOTHES_NEGATIVE bloqueava nudez** |
| Morphological open/close | ⚠️ Agressivo | Degrada bordas, preferir bilateral |

### Pipeline Ideal (v83)

```
POST /jobs {"image": "<base64>", "mode": "progressive"}
```
- Face SSIM: 1.000 (perfeito)
- Bot: 62.9% (remoção significativa)
- BG: preservado
- **PIPELINE RECOMENDADO: progressive mode**

### Problemas Pendentes
1. **Progressive não remove 100%** — denoise baixo preserva demais
2. **NSFW mode (person detection)** — máscara cobre muito, degrada fundo/rosto
3. **pipe_nsfw (composite)** — upscaler destrói tudo, sem upscale funciona melhor
4. **Single-pass NSFW** — face 0.803-0.832, muito degradado

### Próximos Passos
1. ~~Remover upscaler do pipe_nsfw~~ (feito — destrói resultado)
2. Testar pipe_nsfw SEM upscale (composite + bilateral apenas)
3. Testar denoise 0.70 com composite (mais remoção)
4. Investigar upscaler separado (aplicar ANTES do composite, não depois)
5. Considerar modelo upscale diferente (Real-ESRGAN em vez de Fooocus)

## Contexto

### Problema Atual
Após testar 20+ abordagens (v24-v46), identificamos o limite fundamental:

| Abordagem | Preservação | Remoção | Problema |
|-----------|-------------|---------|----------|
| **Clothes mode** | ✅ Perfeita | ⚠️ 18% torso | Só encontra roupa VISÍVEL |
| **Person mode** | ❌ Troca pessoa | ✅ 57% torso | Troca rosto e corpo |

**Conclusão:** O GroundingDINO/Florence-2 só detecta a parte VISÍVEL da roupa (~18% da imagem). Para remoção completa, precisamos de abordagens diferentes.

---

## Abordagem 1: ControlNet com OpenPose/DensePose

### Conceito
Usar ControlNet para guiar o inpainting com a estrutura do corpo humano, preservando pose e contornos enquanto remove a roupa.

### Como Funciona
1. **Extrair pose** do corpo usando OpenPose ou DensePose
2. **Usar pose como condição** para o modelo de inpainting
3. **Gerar pele** que segue a estrutura do corpo original
4. **Preservar rosto** usando máscara separada ou inpainting seletivo

### Vantagens
- ✅ Preserva pose e contornos do corpo
- ✅ Não troca a pessoa (usa a mesma estrutura)
- ✅ Pode ser combinado com inpainting por máscara

### Desafios
- ⚠️ Precisa de modelo ControlNet treinado para pele/corpo
- ⚠️ DensePose pode não detectar bem roupa transparente
- ⚠️ Qualidade depende do modelo base

### Implementação Sugerida
```python
# 1. Extrair DensePose da imagem original
from densepose import DensePoseEstimator
densepose = DensePoseEstimator()
pose_map = densepose.estimate(image)

# 2. Usar ControlNet com pose como condição
from diffusers import StableDiffusionXLControlNetPipeline, ControlNetModel
controlnet = ControlNetModel.from_pretrained("controlnet-densepose-sdxl")
pipeline = StableDiffusionXLControlNetPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    controlnet=controlnet
)

# 3. Gerar com máscara de roupa
result = pipeline(
    prompt="natural skin, realistic body",
    image=original_image,
    mask_image=clothing_mask,
    control_image=pose_map,
    controlnet_conditioning_scale=0.8,
    strength=0.7
)
```

### Modelos Necessários
- **DensePose** (Facebook Research) — Extração de pose 3D do corpo
- **ControlNet DensePose** — Modelo treinado para condição de pose
- **SDXL Inpainting** — Base para geração de pele

### Estimativa de Esforço
- **Complexidade:** ALTA
- **Tempo:** 2-3 semanas
- **GPU necessária:** 12GB+ VRAM

---

## Abordagem 2: img2img com Referência (IP-Adapter)

### Conceito
Usar IP-Adapter para manter a identidade da pessoa enquanto gera nova pele na área de roupa.

### Como Funciona
1. **Extrair embedding** da pessoa original (rosto, corpo)
2. **Usar embedding como referência** para gerar pele similar
3. **Aplicar inpainting** apenas na área de roupa
4. **Manter rosto e corpo** usando referência

### Vantagens
- ✅ Mantém identidade da pessoa
- ✅ Gera pele com textura e cor similar
- ✅ Não troca a pessoa inteira

### Desafios
- ⚠️ IP-Adapter foca em rosto, não corpo inteiro
- ⚠️ Pode gerar inconsistências entre rosto e corpo
- ⚠️ Precisa de ajuste fino para NSFW

### Implementação Sugerida
```python
# 1. Carregar IP-Adapter
from diffusers import StableDiffusionXLImg2ImgPipeline
from ip_adapter import IPAdapter

pipeline = StableDiffusionXLImg2ImgPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0"
)
ip_adapter = IPAdapter(pipeline, "ip-adapter_sdxl.bin")

# 2. Extrair referência da pessoa
reference_image = crop_person(original_image)

# 3. Gerar pele usando referência
result = ip_adapter.generate(
    prompt="natural skin, realistic body",
    image=clothing_area,
    reference_image=reference_image,
    scale=0.6,  # Força da referência
    strength=0.5  # Preservar mais da original
)
```

### Modelos Necessários
- **IP-Adapter SDXL** — Extração e aplicação de referência
- **SDXL Inpainting** — Base para geração
- **CLIP Image Encoder** — Extração de embedding

### Estimativa de Esforço
- **Complexidade:** MÉDIA
- **Tempo:** 1-2 semanas
- **GPU necessária:** 8GB+ VRAM

---

## Abordagem 3: Modelo Especializado em Detecção de Roupa

### Conceito
Treinar modelo customizado para detectar a área COMPLETA da roupa (não apenas partes visíveis).

### Como Funciona
1. **Coletar dataset** de imagens com máscaras de roupa completas
2. **Treinar modelo de segmentação** (Mask R-CNN, SAM, etc.)
3. **Detectar área completa** da roupa, não apenas bordas visíveis
4. **Usar máscara completa** para inpainting

### Vantagens
- ✅ Detecta área completa da roupa
- ✅ Máscara mais precisa e abrangente
- ✅ Pode ser otimizado para tipos específicos de roupa

### Desafios
- ⚠️ Precisa de dataset grande e anotado
- ⚠️ Treinamento demorado e custoso
- ⚠️ Generalização para diferentes tipos de roupa

### Implementação Sugerida
```python
# 1. Dataset de treinamento
# Cada imagem com máscara anotada da roupa COMPLETA
dataset = [
    {"image": "img1.jpg", "mask": "mask1.png", "label": "dress"},
    {"image": "img2.jpg", "mask": "mask2.png", "label": "shirt"},
    ...
]

# 2. Treinar Mask R-CNN
from detectron2.engine import DefaultTrainer
cfg = get_cfg()
cfg.MODEL.MASK_ON = True
cfg.MODEL.ROI_HEADS.NUM_CLASSES = 10  # Tipos de roupa
trainer = DefaultTrainer(cfg)
trainer.train(dataset)

# 3. Usar para detecção
model = load_trained_model()
mask = model.predict(image)  # Máscara COMPLETA da roupa
```

### Modelos Necessários
- **Mask R-CNN** ou **SAM** — Base para segmentação
- **Dataset anotado** — 1000+ imagens com máscaras
- **GPU para treinamento** — 24GB+ VRAM

### Estimativa de Esforço
- **Complexidade:** MUITO ALTA
- **Tempo:** 4-6 semanas
- **GPU necessária:** 24GB+ VRAM

---

## Abordagem 4: Máscara Progressiva (Multi-Pass)

### Conceito
Múltiplas passadas de inpainting com máscaras cada vez maiores, preservando o que já foi gerado.

### Como Funciona
1. **Pass 1:** Detectar e remover itens pequenos (alças, detalhes)
2. **Pass 2:** Expandir máscara e remover itens médios (top, blouse)
3. **Pass 3:** Expandir mais e remover itens grandes (dress, shirt)
4. **Cada passada preserva** o resultado anterior

### Vantagens
- ✅ Não degrada a imagem (preserva cada passada)
- ✅ Controle fino do processo
- ✅ Pode parar em qualquer estágio

### Desafios
- ⚠️ Demorado (múltiplas passadas)
- ⚠️ Acumulação de erros entre passadas
- ⚠️ Precisa de limiares bem ajustados

### Implementação Sugerida
```python
# Pipeline de múltiplas passadas
passes = [
    {"classes": "spaghetti strap, camisole", "threshold": 0.05, "denoise": 0.65},
    {"classes": "top, blouse", "threshold": 0.10, "denoise": 0.60},
    {"classes": "dress, shirt", "threshold": 0.15, "denoise": 0.55},
]

result = original_image
for pass_config in passes:
    # Detectar roupa
    mask = detect_clothing(result, pass_config["classes"], pass_config["threshold"])
    
    # Inpainting
    result = inpaint(result, mask, pass_config["denoise"])
    
    # Preservar rosto (não incluir na máscara)
    result = blend_face(original_image, result)
```

### Modelos Necessários
- **GroundingDINO** ou **Florence-2** — Detecção
- **Fooocus SDXL** — Inpainting
- **OpenCV** — Processamento de máscaras

### Estimativa de Esforço
- **Complexidade:** MÉDIA
- **Tempo:** 1 semana
- **GPU necessária:** 8GB+ VRAM

---

## Abordagem 5: Combinar ControlNet + img2img (Recomendada)

### Conceito
Usar ControlNet para preservar estrutura + IP-Adapter para manter identidade + inpainting para gerar pele.

### Como Funciona
1. **Extrair pose** (ControlNet) e **identidade** (IP-Adapter)
2. **Criar máscara** da área de roupa
3. **Gerar pele** usando pose como guia e identidade como referência
4. **Combinar** com rosto original (máscara separada)

### Vantagens
- ✅ Preserva pose (ControlNet)
- ✅ Mantém identidade (IP-Adapter)
- ✅ Gera pele realista (SDXL)
- ✅ Não troca a pessoa

### Desafios
- ⚠️ Complexo de implementar
- ⚠️ Precisa de múltiplos modelos
- ⚠️ Otimização de parâmetros

### Implementação Sugerida
```python
# Pipeline completo
def nsfw_removal_pipeline(image):
    # 1. Extrair pose
    pose = extract_densepose(image)
    
    # 2. Extrair identidade
    identity = extract_identity(image)
    
    # 3. Criar máscara de roupa
    clothing_mask = detect_clothing_complete(image)
    
    # 4. Gerar pele com ControlNet + IP-Adapter
    result = generate_skin(
        image=image,
        mask=clothing_mask,
        pose=pose,
        identity=identity,
        prompt="natural skin, realistic body",
        denoise=0.5
    )
    
    # 5. Combinar com rosto original
    result = blend_face(original=image, generated=result)
    
    return result
```

### Modelos Necessários
- **DensePose** — Extração de pose
- **IP-Adapter** — Extração de identidade
- **ControlNet DensePose** — Geração guiada por pose
- **SDXL Inpainting** — Geração de pele
- **Face Restoration** — Preservação do rosto

### Estimativa de Esforço
- **Complexidade:** ALTA
- **Tempo:** 2-3 semanas
- **GPU necessária:** 12GB+ VRAM

---

## Comparação das Abordagens

| Abordagem | Complexidade | Tempo | Qualidade | GPU |
|-----------|-------------|-------|-----------|-----|
| ControlNet OpenPose | ALTA | 2-3 sem | ⭐⭐⭐⭐ | 12GB+ |
| IP-Adapter | MÉDIA | 1-2 sem | ⭐⭐⭐ | 8GB+ |
| Modelo Especializado | MUITO ALTA | 4-6 sem | ⭐⭐⭐⭐⭐ | 24GB+ |
| Máscara Progressiva | MÉDIA | 1 sem | ⭐⭐⭐ | 8GB+ |
| **ControlNet + IP-Adapter** | **ALTA** | **2-3 sem** | **⭐⭐⭐⭐⭐** | **12GB+** |

---

## Recomendação

### Prioridade 1: Máscara Progressiva (Rápido)
- **Objetivo:** Melhorar abordagem atual (v35)
- **Tempo:** 1 semana
- **Retorno:** Melhoria imediata sem novos modelos

### Prioridade 2: IP-Adapter (Médio Prazo)
- **Objetivo:** Manter identidade da pessoa
- **Tempo:** 1-2 semanas
- **Retorno:** Preservação de identidade

### Prioridade 3: ControlNet + IP-Adapter (Longo Prazo)
- **Objetivo:** Solução completa
- **Tempo:** 2-3 semanas
- **Retorno:** Qualidade máxima

---

## Próximos Passos Imediatos

1. **Implementar máscara progressiva** na SE11
2. **Testar IP-Adapter** com SDXL
3. **Avaliar DensePose** para extração de pose
4. **Criar dataset** de teste com pessoas diversas

---

## Resultados Preliminares (v47-v48)

### Máscara Progressiva — Resultados (v47-v54)

| Métrica | v34 (single) | v47 (3-pass) | v48 (4-pass) | v49 (5-pass) | v50 (GD) | v51 (mixed) | v53 (tight) | v54 (2-pass) |
|---------|-------------|-------------|-------------|-------------|---------|------------|------------|-------------|
| Face SSIM | 1.000 | 1.000 | 1.000 ✅ | 0.986 | 1.000 | 1.000 | 1.000 | 1.000 |
| Face diff | 0.0 | 0.0 | 0.0 ✅ | 1.5 | 0.0 | 0.0 | 0.0 | 0.0 |
| Edge sim | 0.671 | 0.663 | 0.516 | 0.464 | 0.655 | 0.463 | 0.462 | 0.688 |
| Ref diff | 1.0 | 18.5 | 17.8 | 16.9 | 17.9 | 15.9 | 15.5 | 0.8 |
| **Torso** | **18.1%** | **17.6%** | **26.4%** | **38.4%** | 13.4% | 24.6% | 26.4% | 18.0% |
| **Bottom** | **14.1%** | **43.6%** | **50.3%** ✅ | **43.8%** | 42.9% | 41.8% | 46.9% | 13.3% |
| Overall | 11.5% | 20.2% | 25.7% | 32.9% | 18.2% | 22.4% | 24.7% | 11.2% |

**Melhor resultado:** v48 (4-pass) — equilíbrio ideal entre remoção (50% bottom) e preservação (Face SSIM 1.000).

**Descobertas:**
- 2-pass (v54) = ineficaz, segunda passada não detecta nada novo
- 5-pass (v49) = agressivo demais, destrói rosto
- 5-pass estável (v59) = 40% bot, preservação OK
- 4-pass (v48) = sweet spot ideal
- Mix de detectores (v51) = não melhora vs todos Florence
- **IP-Adapter + SE8** = CUDA assertion, não funciona com inpainting simultâneo
- **IP-Adapter sem máscara** = destrói imagem (regenera tudo)

### Resultados Completos (v34-v62)

**Top 10 Melhores:**

| # | Versão | Abordagem | Torso | Bot | Face | Qualidade Visual |
|---|--------|-----------|-------|-----|------|-----------------|
| 1 | **v82** | **Clothes progressive + smooth blend** | 18.5% | 62.9% | 1.000 | **✅ MELHOR (sem rastros)** |
| 2 | **v75** | Person single + face protection | 35.8% | 79.9% | 1.000 | ✅ Boa |
| 3 | v81 | Person progressive + smooth blend | 55.4% | 76.6% | 1.000 | ⚠️ Tocou pele |
| 4 | v73 | Person progressive baseline | 56.6% | 77.5% | 1.000 | ⚠️ Tocou pele |
| 5 | v77 | Person progressive low threshold | 97.7% | 100.0% | 0.999 | ❌ Colou imagem |
| 6 | v66 | Clothes progressive + color correction | 49.8% | 83.5% | 0.990 | ❌ Degradou face |
| 7 | v64 | Clothes progressive + face protection | 19.8% | 62.6% | 1.000 | ✅ Sem smooth blend |
| 8 | v55 | Máscara simples torso | 76.5% | 37.2% | 1.000 | ✅ Sem progressivo |

**Conclusão Final:**
- **v82 = MELHOR para NSFW** — detecta roupas corretamente, sem rastros de máscara, face 100%
- **Person mode é PERVERSO** — detecta pele sã como roupa (v77-v81 = desastres)
- **Clothes mode + progressive + smooth blend = combinação vencedora**
- **Rota NSFW**: `POST /jobs {"mode": "progressive", "image": "..."}` → v82 pipeline

---

## Referências

- [ControlNet](https://github.com/lllyasviel/ControlNet) — Controle de difusão com condições
- [IP-Adapter](https://github.com/tencent-ailab/IP-Adapter) — Referência de imagem
- [DensePose](https://github.com/facebookresearch/DensePose) — Pose 3D do corpo
- [Fooocus](https://github.com/lllyasviel/Fooocus) — Inpainting SDXL
- [GroundingDINO](https://github.com/IDEA-Research/GroundingDINO) — Detecção de objetos
- [Florence-2](https://huggingface.co/microsoft/Florence-2-large) — Detecção alternativa
