# Pesquisa: Como Empresas Profissionais Editam Fotos Preservando Rosto e Fundo

## Resumo da Pesquisa

### Principais Descobertas

| Técnica | Propósito | Implementação |
|---------|-----------|---------------|
| **Modelos VTON Especializados** (IDM-VTON, OOTDiffusion, CatVTON) | Fidelidade da roupa + preservação de identidade | Two-stream diffusion: GarmentNet (baixo nível) + TryonNet (pessoa) + IP-Adapter (alto nível) |
| **IP-Adapter FaceID / Plus Face** | Travar identidade do rosto | Embeddings InsightFace + LoRA, strength 0.7-1.0 |
| **Segmentação Precisa** (Segformer B2/B3) | Máscara exata da roupa | Auto-masking com expansão de borda (10-20px) |
| **ControlNet** (OpenPose/Canny/Depth) | Preservar pose/estrutura | Weight 0.5-1.0, stop 0.5-0.7 |
| **Denoising Strength Baixo** | Mudanças mínimas no original | 0.2-0.4 para edições localizadas |
| **Crop & Stitch / Multi-pass** | Detalhe em alta resolução | Inpaint em resolução ótima, blend de volta |

---

### Problemas Atuais no Pipeline SE11

1. **Modelo base errado**: Usa `juggernautXL_v8Rundiffusion.safetensors` (SDXL genérico) em vez dos modelos Fooocus inpainting (`inpaint_v26.fooocus.patch` + `fooocus_lama.safetensors` + `fooocus_inpaint_head.pth`)

2. **Sem travamento de identidade facial**: Sem IP-Adapter FaceID - o rosto deriva porque não há condicionamento de identidade

3. **Denoising muito alto**: `inpaint_strength=0.65-0.75` sobrescreve tudo. Sistemas profissionais usam 0.2-0.4

4. **Blending simples apenas**: Laplacian/alpha é pós-hoc - não impede drift do rosto durante geração

5. **Sem fidelidade de vestuário**: Sem mecanismo para preservar logos/texturas/detalhes da roupa

---

### Mudanças Recomendadas na Arquitetura

#### 1. Trocar para Modelos Fooocus Inpainting
```python
# No payload do cliente SE8, mudar base_model_name para modelos Fooocus inpaint
# Precisam ser instalados no SE8: inpaint_v26.fooocus.patch, fooocus_lama.safetensors, fooocus_inpaint_head.pth
```

#### 2. Adicionar IP-Adapter FaceID para Preservação Facial
- Instalar `ip-adapter-faceid-plusv2_sdxl.bin` + `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` + `insightface/buffalo_l`
- No SE8, adicionar condicionamento IP-Adapter FaceID com o rosto original como referência
- Weight: 0.8-1.0 para travamento forte de identidade

#### 3. Denoising Baixo + Multi-Pass
```python
# Passada 1: denoise baixo (0.3) para preservação de estrutura
# Passada 2: refinamento facial específico com IP-Adapter FaceID
# Passada 3: Laplacian blend para bordas suaves
```

#### 4. Segmentação Precisa + Expansão de Máscara
- Usar Segformer B2/B3 para segmentação de roupas (já no SE10 via GroundingDINO+SAM2)
- Expandir máscara 10-20px para cobrir bordas
- Inverter máscara para workflow "manter rosto/corpo, mudar roupa"

#### 5. Abordagem Duas Etapas: Estrutura → Textura
1. **Passada estrutura**: Pyracanny + CPDS + denoise baixo → preserva pose/corpo
2. **Passada textura**: IP-Adapter FaceID + referência da roupa → corrige rosto, adiciona detalhes

---

### Correções Imediatas (Implementáveis Agora)

**A. Reduzir inpaint_strength no cliente SE11**
```python
```python# Em http_client.py, mudar inpaint_strength padrão de 0.65 para 0.35
# Modo nsfw retry loop: 0.35 → 0.40 → 0.45 (em vez de 0.65 → 0.70 → 0.75)
```

**B. Adicionar IP-Adapter FaceID no SE8**
- Requer mudanças no SE8 (carregamento de modelo + pipeline)
- Maior ganho de qualidade para preservação facial

**C. Usar workflow "Invert Mask"
- Mascarar a ROUPA (não o corpo)- Usar `inpaint_engine` que respeita invert mask- Assim rosto/corpo/fundo ficam nas regiões "keep"

**D. Geração duas passadas no pipeline_nsfw.py```python
# Passada 1: Gerar com denoise baixo (0.3), manter estrutura
# Passada 2: Restauração facial via SE8 /v1/face/restore (já implementado)# Passada 3: Laplacian blend (já implementado)
```

---

### Parâmetros Baseados na Pesquisa

| Parâmetro | Atual | Recomendado | Fonte |
|-----------|-------|-------------|-------|
| `inpaint_strength` | 0.65-0.75 | 0.30-0.45 | Fooocus discussions, papers VTON |
| `inpaint_respective_field` | 0.618 | 0.5-0.6 (crop mais apertado) | Fooocus docs |
| `overwrite_step` | 40 | 20-30 (mais rápido, menos drift) | Fooocus inpaint guide |
| IP-Adapter FaceID weight | N/A | 0.8-1.0 | Tutoriais IP-Adapter |
| ControlNet OpenPose weight | 0.5 | 0.6-0.8 | WearView, IDM-VTON |
| ControlNet stop | 0.7 | 0.5-0.6 | Guia Fooocus Pyracanny/CPDS |

---

### Próximos Passos (Ordem de Prioridade)

1. **Quick win**: Reduzir `inpaint_strength` para 0.35 no cliente SE11, testar E2E
2. **Médio**: Adicionar workflow invert-mask (mascarar roupas, não corpo) no pipeline SE11
3. **Maior**: Implementar IP-Adapter FaceID no SE8 (requer download de modelo + mudanças no pipeline)
4. **Maior**: Trocar SE8 para modelos Fooocus inpainting em vez de SDXL genérico
5. **Pesquisa**: Avaliar IDM-VTON/OOTDiffusion para fidelidade de vestuário em produção

---

### Fontes Consultadas

- IDM-VTON (GitHub/project page) - Two-stream diffusion para virtual try-on
- OOTDiffusion paper - Outfitting Fusion Based Latent Diffusion
- IP-Adapter FaceID (HuggingFace/h94) - InsightFace embeddings + LoRA
- Fooocus inpainting docs/discussions - Denoising strength, Pyracanny, CPDS
- WearView/Aragon/Snappyit - Produção: face swap preservando roupa/pose/fundo
- PromptHero/Civitai workflows - Auto clothes inpainting com Segformer + Fooocus
- Runware API docs - Automatic mask generation + inpainting
- 10b.ai blog - Keep same face img2img workflow
- ComfyUI inpainting tutorials - VAE Encoder for Inpainting, mask editor
- Fooocus GitHub discussions - Inpainting denoising strength issues

---

### Observação Importante

A mudança mais impactante para preservação facial é **IP-Adapter FaceID** - é o que todos os sistemas de produção usam (WearView, Aragon, IDM-VTON, PuLID) para travar identidade. O Laplacian blending ajuda com costuras, mas não impede o rosto de derivar durante a geração.