# LIÇÕES.md — Lições Aprendidas (NSFW Pipeline)

**Data:** 2026-06-26
**Última atualização:** Consolidação de todos os .md files do projeto

---

## 1. Configuração Óptima (v17 BEST RESULT)

Pipeline production: `_run_nsfw_test()` via `mode="nsfw"`

| Parâmetro | Valor | Porquê |
|-----------|-------|--------|
| Dilation | 3.5% adaptativa | Cobertura sem comer fundo |
| erode_or_dilate | -3 | Bordas limpas |
| strength | 0.65 | Pose preservada + boa qualidade |
| field | 0.85 | Contexto amplo |
| morphOpen | 3px | Suaviza cantos |
| GaussianBlur (mask) | 3px | SE8 vê bordas suaves |
| morphClose | 5px ellipse + vertical 1x7 | Fecha gaps (mão-cintura) |
| GaussianBlur (output) | 7px blend no resultado final | Transição natural |
| NsfwPov LoRA | 0.3 | Textura pele |
| add-detail-xl LoRA | 1.0 | Detalhe máximo |
| Reinhard LAB | DESLIGADO | Pele correcta do SE8 |
| Bilateral filter | DESLIGADO | Não necessário |
| base_model | juggernautXL | Melhor que lustify para NSFW |

**Prompt positive:** `NSFW×5, solo, bare skin, same body position, unchanged pose, skin tone matching arms/face, 8k uhd`

**Prompt negative:** `(deformed:1.3), extra limbs, airbrushed, plastic skin, (changed pose:1.5), clothes, fabric, bra, straps`

---

## 2. O que NÃO funciona

| # | O que falhou | Por que falha | Fonte |
|---|-------------|---------------|-------|
| 1 | **5% dilation** | Máscara demasiado grande → SE8 gera blobs cinza | INVESTIGATE |
| 2 | **erode_or_dilate=-2** | Demasiado agressivo nas áreas finas | INVESTIGATE |
| 3 | **Máscara suave (0-255) para SE8** | SE8 espera binário (0 ou 255), suave confunde o modelo | INVESTIGATE, PLAN-1 |
| 4 | **Reinhard LAB color transfer** | Escurece a pele (canal L deslocado) | INVESTIGATE, PLAN-1 |
| 5 | **inpaint_strength=0.55** | Pouca criatividade → blobs | INVESTIGATE |
| 6 | **inpaint_strength=0.80** | Muita criatividade → muda pose | INVESTIGATE |
| 7 | **GaussianBlur 15px na máscara** | Expandia demais, comia área do rosto | INVESTIGATE, PLAN-1 |
| 8 | **2-pass (0.75 + 0.45)** | Regenera conteúdo, causa blobs | PLAN-1, UPGRADE-2 |
| 9 | **face_only (V3)** | Bordas feias na face | PLAN-1 |
| 10 | **bilateral filter** | Não necessário, acrescenta latência | PLAN-1 |
| 11 | **lustifySDXLNSFW model** | JuggernautXL é melhor para NSFW | PLAN-1, UPGRADE-2 |
| 12 | **NsfwPov weight 0.7** | Causa CUDA assertion | MEMORY |
| 13 | **cfg 7.0** | CFG alto demais, oversaturação | MEMORY |
| 14 | **GaussianBlur 31+15px collage** | Borrão excessivo, perde detalhe | UPGRADE-2 |
| 15 | **seamlessClone MIXED_CLONE** | Traz roupa de volta (preserva gradientes do destino) | UPGRADE-2 |
| 16 | **HSV correction pós-processamento** | Artefactos vermelhos mesmo com feathering | UPGRADE-2 |
| 17 | **clothing_exact como inpaint mask** | Área demasiado pequena (~15%) para NSFW | UPGRADE-2 |
| 18 | **3-pass progressivo** | Causa blobs, degrada qualidade | MEMORY |
| 19 | **IP-Adapter** | CUDA assertion, incompatível | MEMORY |
| 20 | **torch.cuda.empty_cache()** | Quebra pipeline de inpainting (descarta tensores ativos) | UPGRADE-1 |
| 21 | **GaussianBlur 51x51 no smooth_mask** | Vazou para fora da máscara, 60%+ da imagem afetada | UPGRADE-1 |
| 22 | **Force-include strap detections** | Máscara expande para face (Top=24-27%) | UPGRADE-1 |
| 23 | **Edge detection (Canny) na zona de straps** | Adiciona 14.6% coverage → erosão mata tudo | UPGRADE-1 |
| 24 | **Selective erosion (bottom-only)** | Máscara ainda cobre face | UPGRADE-1 |

---

## 3. O que FUNCIONA

| # | Técnica | Por que funciona | Fonte |
|---|---------|-----------------|-------|
| 1 | **3.5% dilation adaptativa** | Cobertura optimal, adapta a qualquer resolução | INVESTIGATE, PLAN-1 |
| 2 | **erode_or_dilate=-3** | Bordas limpas sem perder detalhe | INVESTIGATE |
| 3 | **Máscara binária para SE8** | Binário puro funciona | INVESTIGATE, PLAN-1 |
| 4 | **body_mask como inpaint** | Modelo precisa de espaço para gerar corpo, não só roupa | PLAN, UPGRADE-2 |
| 5 | **Smooth blend GaussianBlur 7px no output** | Transição natural sem confundir SE8 | INVESTIGATE, PLAN-1 |
| 6 | **morphOpen 3px + GaussianBlur 3px + morphClose 5px + vertical 1x7** | Bordas suaves + sem gaps | INVESTIGATE |
| 7 | **Prompts com weights no negative (1.3, 1.5)** | Reforça pose, previne deformação | INVESTIGATE, PLAN-1 |
| 8 | **5x NSFW no prompt** | Força o modelo a gerar conteúdo explícito | PLAN |
| 9 | **Negative sem "nipples/areola"** | Remover estes termos permite geração | PLAN |
| 10 | **Collage: paste NSFW person na original** | Preserva fundo perfeitamente | UPGRADE-2 |
| 11 | **7% adaptive dilation (em teste)** | Adapta a qualquer resolução | UPGRADE-2 |
| 12 | **head_adjusted (binário)** | Melhor que face_only para preservação facial | PLAN-1 |
| 13 | **juggernautXL + 1 pass + CFG 4** | Simplicidade > complexidade | PLAN, UPGRADE-2 |
| 14 | **Florence-2 detector** | Melhor acurácia que GroundingDINO para clothing | UPGRADE-1 |
| 15 | **ipc_collect() em vez de empty_cache()** | Mais seguro, não descarta tensores ativos | UPGRADE-1 |

---

## 4. Descobertas Críticas

1. **Simplicidade > Complexidade** — Params simples (juggernautXL, 1 pass, CFG 4) superaram 3 passes + lustify + CFG 7. O job `cr_f5a80bef266e` (20 Jun) já gerava NSFW realista com params simples — nós super-complicámos.

2. **body_mask > clothing_exact** — Modelo precisa de espaço para gerar corpo, não só roupa. clothing_exact (~15%) é demasiado pequeno para NSFW.

3. **SE8 espera máscaras binárias** — Máscara suave (0-255) confunde o modelo. Usar binário para SE8 e smooth blend no output final.

4. **Smooth blend NO output, não no input** — GaussianBlur na máscara de entrada → SE8 confuso. GaussianBlur no resultado final → transição suave.

5. **5x NSFW no prompt** — Força o modelo a gerar conteúdo explícito. Sem isto, o modelo tende a gerar roupa leve.

6. **Negative sem termos de pele** — Remover "nipples, areola, breast, nudity, nude, naked" do negative permite geração. O DEFAULT_CLOTHES_NEGATIVE original bloqueava NSFW.

7. **color_transfer destruía cores** — Quando activo em pipelines complexos, mas funciona no pipeline simples (v15). No v17, desligado = melhor resultado.

8. **fooocus_fill() com body_mask** — Cria blur da cor média; com body_mask dá cor de pele (bom), com clothing_exact dava cor da roupa (mau).

---

## 5. Limitações Conhecidas

### SDXL Inpainting
- **JuggernautXL/LUSTIFY não foram treinados para remover 100% roupa** — gera pele mas não remove toda a roupa em uma passagem
- **Resultado atual:** ~32% torso, ~72% bot (nunca 100%)
- **Denoise controlado:** se aumentar denoise, degrada face/corpo
- **Máscara baseada em detecção:** SE10 detecta apenas partes visíveis da roupa

### Para 100% NSFW (avaliado, não implementado)
| Abordagem | Complexidade |
|-----------|-------------|
| Modelo NSFW专用 treinado | ALTA |
| Multi-pass agressivo (5-10 passes) | MÉDIA |
| ControlNet + DensePose | MUITO ALTA |
| API externa NSFW (Replicate, fal.ai) | MÉDIA |
| Fine-tune do modelo | MUITO ALTA |

---

## 6. CUDA / GPU

### RTX 3090 (24GB)
- Padrão 97% VRAM cheio após uso
- Quando SE8 falha 3x com CUDA assertion → `nvidia-smi` verificar memória
- **Fix:** `docker exec image-engine pkill -f python` limpa GPU

### torch.cuda.empty_cache()
- **NÃO usar** — descarta tensores que o InpaintWorker precisa
- Causa: `_soft_empty_cache()` em `model_manager.py:562` em toda carga de modelo
- **Substituir por:** `del` de tensores temporários + `torch.cuda.ipc_collect()`

---

## 7. Técnicas Avaliadas (Rejection Log)

| Técnica | Resultado | Por que falhou |
|---------|-----------|---------------|
| seamlessClone MIXED_CLONE | ❌ | Traz roupa de volta — preserva gradientes do destino |
| seamlessClone NORMAL_CLONE | ❌ | Bleeding de cor do fundo para dentro da pessoa |
| Reinhard LAB color transfer | ❌ | Escurece pele (canal L shift) |
| HSV correction | ❌ | Artefactos vermelhos |
| 2-pass inpainting | ❌ | Regenera conteúdo, causa blobs |
| GaussianBlur 31+15px collage | ❌ | Borrão excessivo |
| GrabCut refinement | ❌ | ~15s em 1080p, demasiado lento |
| Color inRange (HSV) | ⚠️ | Risco de false positives (fundo igual à roupa) |
| Connected components | ❌ | Não encontra straps (spatially connected ao topo) |
| Per-garment mode | ⚠️ | N× mais lento, errou alças |
| SAHI high-res tiling | pendente | Não testado |
| FooocusExpansion GPT-2 | N/A | Carregado mas nunca chamado (use_expansion=False) |
| Safety checker (black_out_nsfw) | N/A | Código existe mas nunca é chamado |

---

## Referências

| Arquivo | Caminho |
|---------|---------|
| Pipeline principal | `services/se11-clothes-removal/app/services/pipeline.py` |
| HTTP Client | `services/se11-clothes-removal/app/infrastructure/http_client.py` |
| Models | `services/se11-clothes-removal/app/core/models.py` |
| Masks doc | `services/se11-clothes-removal/docs/TOP-MASK-CONFIG.md` |
| Plano production | `PLAN.md` |
| Plano head detect | `PLAN-2.md` |
