# LIÇÕES-NSFW.md — Lições Aprendidas do Pipeline NSFW (SE11)

**Serviço:** SE11 (clothes-removal)
**Migrado de:** `LIÇÕES.md` (raiz do projeto) em 2026-07-05

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
| FooocusExpansion GPT-2 | N/A | Carregado mas nunca chamado (use_expansion=False) |
| Safety checker (black_out_nsfw) | N/A | Código existe mas nunca é chamado |

---

## 13. Mask Research + Pose Preservation (2026-06-29)

### Head Mask — Fluxo Oficial
```
1. Elipse detecta face+cabelo (expand_w=0.5, expand_up=1.5, expand_down=1.8)
2. Subtrai clothes_combined → só face+cabelo
3. Distance transform (8px) → preenche concavidades da subtração
4. OR com original → mantém centro, infla bordas
5. Morphological close (9px, 2 iters) → fecha buracos residuais
6. GaussianBlur (15px, σ=5.0) → bordas orgânicas suaves
7. Re-threshold 0.5 → binário limpo
8. Clip ao person_binary
9. Remove noise <0.5% área
```
**Porquê:** Elipse cruza roupa → subtrair roupa gera bordas serrilhadas → distance transform preenche → blur suaviza.

### Pose Preservation
- **IP-Adapter com imagem original** (não mascarada) preserva postura
- **weight=0.8, stop=0.5** — melhor resultado visual (Grid 1-4, 28 configs)
- face-masked reference causava ghost face diferente a cada seed
- Campo 0.618 (golden ratio) dá contexto suficiente para manter pose
- **strength=0.84** é o sweet spot — mais baixo preserva pose mas roupa "vaza"

### Grid Exploration (28 configs testadas)

| Grid | Params testados | Melhor |
|------|----------------|--------|
| 1 (A-G) | strength, field, weight, stop, erode, seed | D (weight=0.7) |
| 2 (H-M) | weight 0.7-0.8 + combos | D (visual > scores) |
| 3 (N-S) | weight 0.8 + intermediários | J (mão no rosto) |
| 4 (T-Y) | stop 0.6-0.7, weight 0.85, combos | T/W (limbs 7.3-7.5%) |
| Brute (10 seeds) | W × 5 seeds | **W_sd-1** (vencedor) |

**Config vencedora final: weight=0.8, strength=0.84, stop=0.5, field=0.618**

### Lições dos Grids
- **erode negativo DESTRÓI pose** (F: corpo deitado) — NUNCA usar
- **IP weight alto (0.8) + strength baixo (0.80)** gera pose ERRADA (braços cruzados em vez de mão no rosto)
- **IP weight alto (0.8) + strength 0.84** = sweet spot — preserva mão no rosto
- **IP stop 0.6-0.7** não melhora significativamente vs 0.5
- **field=0.45** gera artefatos — manter 0.618
- **seed=-1 (random)** pode ser melhor que seeds fixos — brute force de 5 seeds é eficaz
- **MediaPipe scores ≠ qualidade visual** — F era #1 nos scores mas péssimo visualmente
- **Suéter residual** é trade-off: IP weight alto preserva pose MAS também preserva roupa

### Color Matching — Reinhard LAB
- Transferência de cor em espaço LAB (canal L=lightness, A=verde/vermelho, B=azul/amarelo)
- Usar APENAS pixels de pele como referência (HSV: H=0-30, S=15-170, V=60-255)
- **Se usar body inteira → puxa cor do background** (azul, verde, etc.)
- Aplicar DEPOIS do head paste, e reaplicar head paste ao final

### SE8 ESRGAN Crash
- Erro: `handle_0 INTERNAL ASSERT FAILED` no upscaler
- Causa: crop do InpaintWorker < 1024px
- Fix: pre-escalar imagem para min 1024px antes de enviar ao SE8
- SE8 `require_base64: False` + download via URL (data URI corrompido para imgs >800KB)

### Clothes Detection (Florence-2) — Hair False Positive
- Florence-2 detecta cabelo como roupa
- Fix: subtrair head_mask de clothes_combined ANTES de calcular exposed_skin
- `clothes_clean = clothes AND NOT head`

### Exploration Script
- `exploration/run_mask_pipeline.py` — roda toda pipeline (masks + inpainting)
- `--skip-inpaint` para só mascaras (~22s)
- Grid mode: varia 1 param por config, MediaPipe pose detection automática
- Brute force: 5 seeds × melhor config, seleciona por score
- Output: `exploration/data/{image}/` com grid_summary.json + result.png por config
- Tempo: ~15s por try (com cache SE8), ~150s para grid 10 configs

---

## 14. Leffa-style: Controlar o que o encoder vê (2026-06-30)

**Problema:** Suéter residual — IP-Adapter com weight=0.8 preservava pose mas também preservava roupa. Trade-off fundamental.

**Causa raiz (diagnosticada via pesquisa VTON):** O IP-Adapter recebia a imagem original VESTIDA como referência. O encoder CLIP extraía features de roupa junto com pose/rosto/corpo. Essa atenção vazando para a região errada é EXATAMENTE o que a Leffa (CVPR 2025) descreve como "inadequate attention to corresponding regions in the reference image" → distorção de textura.

**Solução (Opção A do `services/se11-clothes-removal/docs/plans/UPGRADE-V2.md`):** `_build_clothes_neutral_ref()` — antes de passar a imagem ao IP-Adapter, preencher a região de roupa com tom de pele médio (amostrado da pele exposta da própria pessoa) + ruído sutil + blur. O encoder então só vê pose/rosto/formato-do-corpo, sem acesso à textura da roupa.

**Resultado:** Suéter residual desapareceu. Config vencedora: B_neu_s086 (ref neutra + strength=0.86). Pose: head=0.0%, torso=2.0%, limbs=4.1% (baseline era limbs=10.0%). Speed: 16s/try (era 46s).

**Lições:**
- Neutral ref precisa strength MAIOR (0.86 vs 0.84) — a neutralização enfraquece o sinal, a difusão precisa mais passos para compensar
- Amostrar tom de pele da própria pessoa (HSV mediana da pele exposta) — não usar tom fixo
- Erode clothes mask 5px antes de preencher + blur 15px na borda → transição natural
- Pesquisa de papers paga off: entender o mecanismo de como VTON models funcionam (sintetizar não colar, dual-encoder, attention regularization) levou direto à solução
- `services/se11-clothes-removal/docs/plans/UPGRADE-VTON.md` documenta a pesquisa completa (IDM-VTON, OOTDiffusion, Leffa)


## 15. Pose stick figure como IP-Adapter reference DEGRADA resultado (2026-06-30)

**Hipótese:** Usar MediaPipe para gerar um OpenPose-style stick figure e passar como segunda imagem do IP-Adapter ajudaria a preservar a estrutura corporal.

**Implementação:**
- Adicionado `render_pose_stick_figure()` em `app/validators/pose_detector.py`
- Gerado a partir da imagem original via MediaPipe Pose (model_complexity=1)
- Passado como IP-Adapter ImagePrompt com weight=0.4

**Resultado:**
- Com stick figure: best score 21.3, pose_changed=true
- Sem stick figure: score 0.0, pose_changed=false
- **Conclusão: degradou a preservação de pose**

**Por que falhou:**
- IP-Adapter usa CLIP image encoder treinado em fotos reais
- Stick figure sintético (fundo preto + linhas coloridas) é codificado como "desenho abstrato" / "arte vetorial"
- A atenção do diffusion se mistura entre referência foto-realista (clothes-neutral ref) e referência sintética, criando conflito
- Para usar pose como conditioning efetivo, precisa ser via **ControlNet** (treinado especificamente para condicionamento estrutural) ou **DensePose**, NÃO via IP-Adapter

**Lição:** Não confundir "condicionamento de aparência" (IP-Adapter) com "condicionamento estrutural" (ControlNet/DensePose). São mecanismos diferentes e não são intercambiáveis.

**Status:** Código mantido em `pose_detector.py` para futuras experimentações, mas desativado em produção.


## 16. OpenPose ControlNet integrado, mas qualidade precisa de ajuste (2026-06-30)

**Objetivo:** Adicionar condicionamento estrutural de pose ao pipeline NSFW via ControlNet OpenPose, conforme fase 2 do `services/se11-clothes-removal/docs/plans/UPGRADE-V2.md`.

**Implementação:**
- SE10: novo `pose_renderer.py` gera stick figure a partir de landmarks MediaPipe Pose; endpoint `/v1/segment` aceita `include_pose=true`
- SE11: requisita `controlnet_image` do SE10 no modo person e envia ao SE8 como image prompt `cn_type="OpenPose"` (weight=0.5, stop=0.7)
- SE8: `_apply_controlnet()` carrega `controlnet-openpose-sdxl.safetensors`, decodifica a imagem de controle e aplica via `ControlNetApplyAdvanced`
- Corrigido formato do tensor: ComfyUI espera `[B, H, W, C]` e faz `movedim(-1,1)` internamente
- Corrigido decodificação quando `cn_img` chega como `bytes` (API V2 faz `_decode_image()` antes de enfileirar)

**Resultado E2E:**
- Job `cr_b7565e9710cc` completou com OpenPose ControlNet aplicado (verificado nos logs)
- Job `cr_adfbaeb973e3` (weight=0.5, stop=0.7) best score = 17.9
- Job `cr_31850bf1a28b` (ControlNet não aplicado por bug de bytes) best score = 6.7
- **Conclusão:** integração funciona, mas ControlNet atual DEGRADA pose preservation em relação ao clothes-neutral ref sozinho

**Por que pode estar degradando:**
- O modelo `control-lora-openposeXL2-rank256` foi treinado no formato de skeleton OpenPose COCO/Body_25
- MediaPipe Pose produz 33 landmarks com topologia diferente; nosso stick figure é uma aproximação visual
- O ControlNet pode estar interpretando a figura como pose errada ou aplicando condicionamento em conflito com o IP-Adapter
- Weight/stop ainda não calibrados para este pipeline

**Lições:**
- ControlNet NÃO é plug-and-play: o preprocessador de pose deve gerar imagem compatível com o modelo usado
- Para OpenPose ControlNet SDXL, o ideal é usar o preprocessador oficial OpenPose (25 keypoints) em vez de MediaPipe
- Tensor shape importa: `[B, H, W, C]` para `ControlNetApplyAdvanced`, `[B, C, H, W]` para a maioria dos outros operadores
- Sempre verificar se `cn_img` chega como string, bytes ou numpy — diferentes caminhos da API tratam diferente
- Bind mounts GPU são necessários com driver 590 (`libnvidia-ml.so.1`, `libcuda.so.1`, dispositivos `/dev/nvidia*`)

**Status:** Código integrado e funcional. Ajuste fino de pose renderer/weight fica como próxima iteração.

**⚠️ CONCLUSÃO FINAL (2026-07-05):** 
- **LoRA-based ControlNets** (`control-lora-openposeXL2-rank256`) são **INCOMPATÍVEIS** com modelos inpainting SDL. Causa: ControlLora copia pesos do UNet inpainting (9 canais) e sobrepõe pesos LoRA (4 canais) → shape mismatch.
- **Solução: `xinsir/controlnet-union-sdxl-1.0`** (ControlNet padrão, 2.4GB) funciona perfeitamente com LustifyNSFW inpainting. Commit `3906bb9a`. E2E validado: `cr_aa5a54e9da76`, todos os 5 attempts pose_changed=False.


## 17. Face blending: proteger só o centro do rosto evita efeito recorte (2026-06-30)

**Problema:** Usuário reportou que a face parecia um recorte colado da original ("efeito colagem").

**Causa raiz:** O pipeline protegia a cabeça inteira (face + cabelo + pescoço) via `head_adjusted` e a colava de volta com alpha feather de 21px. Como a cabeça, o cabelo e o pescoço permaneciam 100% originais, enquanto o corpo era gerado, a fronteira ficava visível — especialmente sob luz diferente ou com textura de pele gerada.

**Solução implementada (v23.1 → v23.2 → v23.3 → v23.4):**
1. v23.1/v23.2: Reduzir a máscara de proteção para centro do rosto e usar distance transform para transição suave.
2. v23.2: Erodir `head_mask` antes de subtrair de `person_binary`, criando uma **transition band** explícita.
3. v23.2: Aplicar **harmonização de cor (Reinhard LAB) localizada** na faixa de transição + pele exposta original.
4. v23.3: Tentativa de centralizar com MediaPipe Face Mesh — descartada por falha de contexto GPU no container Docker.
5. **v23.4:** Voltar a Haar cascade bbox com máscara de **FACE COMPLETA** (`margin_above=0.05`, `margin_below=0.55`, `margin_sides=0.40). Isso preserva olhos, nariz, boca, queixo e mandíbula originais.
6. **v23.4:** Feather **direcional**: bordas superior e laterais da face permanecem duras (alpha=1.0); só a região do queixo/pescoço é suavizada por distance transform. Isso evita deslocamento mantendo transição no pescoço.

**Resultado:**
- Job `cr_75c5996737ab` (v23.1): `face_protect_mask` = 29.9k px vs `head_adjusted` = 131.1k px (~23% da área anterior); best score = 12.5.
- Job `cr_54e5dff89d04` (v23.2): `face_protect_mask` = 13.8k px vs `head_adjusted` = 131.1k px (~10.5% da área anterior); best score = 7.4.
- Job `cr_4203b2e571c5` (v23.3): tentativa MediaPipe Face Mesh falhou por contexto GPU no container; máscara ficou vazia.
- Job `cr_4c585ccaada4` (v23.4): Haar bbox com máscara de FACE COMPLETA (38.8k px, ~29.6% da cabeça) + feather direcional só no queixo; best score = 11.8. Preserva geometria facial completa, evitando deslocamento.
- **Lição:** máscara pequena (só centro do rosto) gera queixo/mandíbula novos que podem ficar deslocados. Preservar a face inteira e misturar só no pescoço é mais seguro para alinhamento.
- Visualmente a fronteira entre face e corpo gerado fica mais natural quando o modelo só precisa gerar o pescoço, não recriar a mandíbula.

**Padrões de mercado para este problema:**
- **Face-only protection** (nunca proteger cabelo/pescoço inteiro) — usado em pipelines de face-swap e inpainting com preservação facial.
- **Poisson blending / seamlessClone** — integra gradientes na fronteira; requer máscara bem definida e pode trazer artefatos se houver diferença grande de cor.
- **Laplacian pyramid blending** — transição multi-escala, melhor que alpha feather simples.
- **Color harmonization** (Reinhard, histogram matching) — iguala estatísticas de cor entre regiões preservadas e geradas.
- **Face restoration** (GFPGAN/CodeFormer) — aplicado depois do blend para aumentar coerência e nitidez facial.
- **Face identity preservation via IP-Adapter FaceID / InsightFace** — ao invés de colar face, guia a difusão para gerar a mesma identidade.

**Lições:**
- Proteger menos = resultado mais natural. A tentação de proteger cabelo/pescoço aumenta o "efeito colagem".
- Feather pequeno e bem localizado é melhor que feather grande que espalha a borda.
- Harmonização de cor deve ser aplicada ANTES de re-colocar a face, senão a face fica fora do novo espaço de cor.
- Poisson/Laplacian são os próximos passos se o feather Gaussiano ainda não for suficiente.

**Status:** Melhoria aplicada e validada. Face restoration (GFPGAN) e Laplacian blending ficam como próximas iterações.

---

## 18. Florence-2 REMOVIDO — falsos positivos catastroficos (2026-07-04)

**Problema:** Florence-2 (base e large) gera falsos positivos absurdos:
- Logo "GUCCI" detectado como "spaghetti strap" 
- Cabelo/fundo detectado como "skirt"
- Máscara de inpainting ficou no logo e cabelo, NÃO nas roupas
- Resultado: imagem praticamente idêntica ao original

**Causa raiz:** Florence-2 usa bounding boxes imprecisos. Detecção "pequena" ≠ detecção correta. O modelo foi treinado para detecção genérica, não para segmentação de roupa pixel-level.

**Decisão:** Florence-2彻底 REMOVIDO do pipeline. Código deletado (`florence_detector.py`, 202 linhas). Todas as referências removidas de SE10 e SE11.

**Lição:** 
- **NUNCA usar modelos de detecção por texto (GroundingDINO, Florence-2) para segmentação de roupa** — eles geram bounding boxes, não masks pixel-level
- **Prefira modelos de segmentação treinados para a tarefa específica** (SegFormer B2, U2Net, SCHP)
- **Validar detecção olhando a imagem**, não apenas os números — 31 detecções "baixas" pareciam ok no log mas eram catastroficas na imagem
- **Falsos positivos em segmentação são piores que falsos negativos** — uma máscara errada destrói a imagem, uma máscara faltante pode ser compensada

---

## 19. SegFormer B2 — segmentação pixel-level para roupa (2026-07-04)

**Solução:** SegFormer B2 (mattmdjaga/segformer_b2_clothes, 502 likes) com 18 classes de roupa.

**Arquitetura:**
- Input: imagem RGB → modelo gera mask por pixel para cada classe
- Output: 18 masks binárias (Background, Hat, Hair, Sunglasses, Upper-clothes, Skirt, Pants, Dress, Belt, Left-shoe, Right-shoe, Face, Left-leg, Right-leg, Left-arm, Right-arm, Bag, Scarf)
- Velocidade: ~800ms GPU, ~2s CPU

**Lições de implementação:**
1. **Detecções SEPARADAS por classe** (não combinadas) — se combinar tudo em 1 detecção, o filtro `max_area_pct` rejeita a máscara inteira quando uma classe é grande
2. **`max_area_pct=0.80` para SegFormer** — cada classe é independente, um Upper-clothes pode cobrir 40% da imagem validamente
3. **Nesting filter PULADO para SegFormer** — bboxes de classes diferentes se sobrepõem naturalmente (Pants dentro de Upper-clothes bbox)
4. **Labels via `LABELS[cls_id]`** — não usar array hardcoded, pois os IDs do SegFormer são específicos do modelo
5. **Morphological closing k=100-120** — necessário para fechar gaps entre itens de roupa (ex: gap entre hoodie e pants na barriga exposta)

**Resultado:** 3 detecções separadas (Upper-clothes 42%, Skirt 0.6%, Pants 8%) = 50.6% total. Sem falsos positivos.

---

## 20. Morphological closing — fechar buracos na máscara (2026-07-04)

**Problema:** máscara de roupa tinha buracos entre itens (ex: gap entre hoodie e pants na barriga exposta). Buracos = inpainting não atinge aquela área = roupa visível no resultado.

**Solução em 2 camadas:**
1. **SE10 (segformer_detector.py):** closing kernel 120×120 no `clothing_mask` + flood-fill para preencher buracos internos + connected components para manter só a maior componente
2. **SE11 (pipeline_nsfw_experimental.py):** closing kernel 100×100 no `inpaint_mask` + `bitwise_and` com `person_binary` para evitar bleeding

**Lição:**
- **Closing sozinho expande a máscara para fora da pessoa** — SEMPRE fazer `bitwise_and` com `person_binary` depois
- **Filtros morfológicos grandes (k>50) só fazem sentido em imagens grandes** — em imagens pequenas (300px) um kernel de 100px é 33% da imagem
- **Connected components após closing** — o closing pode conectar regiões não-conectadas, gerando uma máscara gigante. Manter só a maior componente evita isso
- **Fechar buracos entre itens de roupa é ESSENCIAL** — sem isso, o modelo vê "ilhas" de roupa e pode gerar artefatos

---

## 21. Steps vs Qualidade vs Velocidade (2026-07-04)

**Teste:** Aumentar steps de 40 para 60 para melhorar qualidade do inpainting.

**Resultado:**
| Steps | Velocidade | Qualidade | Landmark drift |
|-------|-----------|-----------|----------------|
| 40 | ~20s/tentativa | Boa | Baixo |
| 60 | ~150s/tentativa | Melhor | Às vezes alto (49.7%) |

**Lição:**
- **60 steps melhora textura mas pode causar landmark drift** — o modelo "cria demais" e desloca a pose
- **Velocidade 7x mais lenta** (20s → 150s) pode não justificar a melhoria
- **Early stop ajuda** — se composite < 5.0 e pose_changed=false, parar antes (min 2 tentativas)
- **Steps ideais provavelmente são 50** — compromisso entre qualidade e velocidade

---

## 22. Ensamble multi-detector — arquitetura e lições (2026-07-04)

**Arquitetura final:**
```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ GroundingDINO │  │  YOLO11-seg  │  │ BiRefNet-port│  │ SegFormer B2 │
│  (text-prompt)│  │ (COCO person)│  │ (SOTA person) │  │ (18 classes)  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                  │                  │                  │
       └────────┬─────────┴──────────────────┴──────────────────┘
                ▼
       ┌────────────────┐
       │Consensus Voting│
       │(coverage+SOTA) │
       └───────┬────────┘
               ▼
       ┌────────────────┐
       │ Quality Gate   │
       │(coverage > 10%)│
       └───────┬────────┘
               ▼
       Mask final → SAM2 (se bbox) ou direto (se mask)
```

**Lições:**
- **SegFormer é PRIMARY para clothes** — pixel-level, 18 classes, sem falsos positivos
- **BiRefNet é PRIMARY para person** — treinado em DIS benchmark, melhor que GD para pessoa
- **YOLO11 é fallback rápido** — 1.4s CPU, 94% confiança, mas só 1 classe (pessoa)
- **GroundingDINO é fallback de texto** — útil quando usuário especifica classes específicas
- **Consensus voting evita falsos positivos** — se 2+ detectores concordam, é mais provável ser real

---

## 24. DWPose vs MediaPipe (2026-07-04)

**Problema:** MediaPipe Pose Detection (33 landmarks) era impreciso para validação de pose.

**Solução:** DWPose (YOLOX + DWPose transformer, 126 keypoints) via ONNX.

**Lições:**
- **126 keypoints vs 33** — diferença massiva na precisão da validação
- **~1.7s CPU** — aceitável para pipeline que já leva ~2min
- **Modelos ONNX** — sem dependência de PyTorch, mais leve
- **DWPose é o novo SOTA** — substitui MediaPipe para pose estimation em produção

---

## 25. NSFW Prompt — ultra-realistic (2026-07-04)

**Prompt aprimorado:**
```
ultra realistic photograph, DSLR photo, natural skin subsurface scattering, 
film grain, micro details on skin, lifelike skin translucency, 
NSFW, NSFW, NSFW, NSFW, NSFW, solo, same body position, 
unchanged pose, skin tone matching arms/face, 8k uhd
```

**Lição:**
- **"subsurface scattering"** — efeito de luz penetrando na pele (realismo)
- **"film grain"** — ruído de filme evita pele "plástica"
- **"micro details on skin"** — poros, textura, pequenas imperfeições
- **5x NSFW** — reforço para modelo não gerar roupa leve
- **NSFW prompt SEMPRE hardcoded** — `/jobs/nsfw` ignora prompt do usuário

---

## 26. Referências atualizadas

| Arquivo | Caminho |
|---------|---------|
| Pipeline principal | `services/se11-clothes-removal/app/services/pipeline.py` |
| Pipeline NSFW | `services/se11-clothes-removal/app/services/pipeline_nsfw.py` |
| Pipeline NSFW experimental | `services/se11-clothes-removal/app/services/pipeline_nsfw_experimental.py` |
| HTTP Client | `services/se11-clothes-removal/app/infrastructure/http_client.py` |
| Models | `services/se11-clothes-removal/app/core/models.py` |
| SegFormer detector | `services/se10-clothes-segmentation/app/services/segformer_detector.py` |
| Ensemble detector | `services/se10-clothes-segmentation/app/services/ensemble_detector.py` |
| YOLO detector | `services/se10-clothes-segmentation/app/services/yolo_detector.py` |
| BiRefNet detector | `services/se10-clothes-segmentation/app/services/birefnet_detector.py` |
| Segmentor | `services/se10-clothes-segmentation/app/services/segmentor.py` |
| DWPose detector | `services/se11-clothes-removal/app/validators/pose_detector.py` |
| Head detector | `services/se11-clothes-removal/app/services/head_detector.py` |
| Exploration script | `exploration/run_mask_pipeline.py` |
| Pesquisa VTON | `services/se11-clothes-removal/docs/plans/UPGRADE-VTON.md` |

---

## 27. Real-ESRGAN Upscaler — DESABILITADO por distorção de cores (2026-07-04)

**Problema original:** Resultados de inpainting tinham detalhes embaçados.

**Implementação tentada:** Upscale 2x via Real-ESRGAN como etapa pós-processamento.

| Componente | Implementação |
|-----------|---------------|
| `http_client.py` | Método `upscale()` → SE8 `/v1/generation/image-upscale-vary` |
| `pipeline_nsfw_experimental.py` | Etapa `8b` (DESABILITADA) |
| `pipeline_nsfw.py` | Etapa upscale (DESABILITADA) |
| Modelo SE8 | `fooocus_upscaler_s409985e5.bin` (Real-ESRGAN 4x, 32MB) |

**Resultado — FALHOU:**
- Canal Blue: 160→90 (38% mais escuro)
- Histograma pico: 255→92 (imagem muito mais escura)
- Std deviation: 74→23 (perda massiva de contraste)
- **O Real-ESRGAN do SE8 degrada严重mente a distribuição de cores**

**Causa raiz:** Real-ESRGAN 4x foi treinado em imagens gerais (landscape, objects). Não preserva distribuição de cores em fotos de pessoas/pele.

**Estado atual:** Upscaler DESABILITADO nos dois pipelines. `upscale()` mantido em `http_client.py` para uso futuro.

**Próximo:** Investigar alternativas (Lanczos, Real-ESRGAN 2x, waifu2x).

---

## 28. Método duplicado em Python — bug silencioso (2026-07-04)

**Problema:** `http_client.py` tinha DOIS métodos `upscale()` na mesma classe (linhas 348 e 482).

**Comportamento Python:** Usa o **último** método definido — silenciosamente sobrescreve o anterior.

**Consequência:** O método ativo (linha 482) tinha:
- LoRAs NSFW habilitados (NsfwPovAllInOne 0.5, add-detail 0.8)
- Endpoint `/v1/` em vez de `/v2/`
- `current_tab: "uov"` em vez de `"upscaling"`

**Resultado:** SE8 não apenas ampliava — **regenerava a imagem com LoRAs NSFW**, distorcendo completamente o resultado.

**Lição:** SEMPRE verificar se há métodos com o mesmo nome em uma classe. Python não avisa sobre sobrescrita silenciosa.

---

## 29. Formato de URL do SE8 — varia entre endpoints (2026-07-04)

**Observação:** O SE8 retorna URLs em formatos diferentes conforme o endpoint:

| Endpoint | `require_base64` | Formato da URL |
|----------|-------------------|----------------|
| `/v1/` | `False` | `/files/2026-07-05/xxx.png` (arquivo real) |
| `/v2/` | `False` | `/files/../../data:image/png;base64,...` (data URI embutido) |
| `/v2/` | `True` | `base64` vazio, `url` contém data URI |

**Problema:** URLs `/files/../../data:image/...` não são HTTP nem data URI padrão.

**Solução:** Extrair base64 buscando `base64,` na string, independentemente do prefixo.

**Lição:** Não assumir formato de URL — sempre fazer fallback para extração de base64 quando a URL não é HTTP.

---

## 30. Base64 padding — rstrip antes de verificar (2026-07-04)

**Problema:** Extração de base64 de data URIs do SE8 resultava em strings com tamanho ≡ 1 (mod 4).

**Causa:** O `url_val` já continha `=` no final. Adicionar padding sem remover causava padding duplo.

**Solução:** `raw_b64.rstrip("=")` antes de calcular e adicionar padding correto.

**Lição:** Base64 de fontes externas pode ter padding inconsistente — SEMPRE limpar e re-adicionar.

---

## 31. cv2.imdecode vs cv2.imread — fallback para arquivos (2026-07-04)

**Problema:** `cv2.imdecode(buffer)` retornava None para PNGs válidos (magic bytes `89504e47` corretos).

**Causa:** Provavelmente buffer corrompido ou formato ligeiramente inválido para o decoder interno do OpenCV.

**Solução:** Salvar bytes em arquivo temporário e usar `cv2.imread()` como fallback.

**Resultado:** Mesmo com fallback, imagem ficava com cores distorcidas — problema era do modelo, não do decoder.

**Lição:** `cv2.imdecode` e `cv2.imread` podem falhar em casos diferentes — ter ambos como fallback.

---

## 32. SE8 v2 endpoint retorna data URI corrompido (2026-07-04)

**Problema:** Endpoint `/v2/generation/image-upscale-vary` retorna URL no formato:
```
/files/../../data:image/png;base64,<dados corrompidos>
```

**Causa:** O SE8v2 não suporta `require_base64=True` corretamente — retorna data URI embutido em path relativo.

**Solução:** Usar endpoint `/v1/generation/image-upscale-vary` com `require_base64=False` — retorna URL de arquivo real (`/files/2026-07-05/xxx.png`).

**Lição:** Endpoint v1 é mais estável para upscale. v2 tem bugs de serialização de URL.

---

## 33. Real-ESRGAN 4x Fooocus — distorção de cores em fotos de pessoas (2026-07-04)

**Problema:** Modelo `fooocus_upscaler_s409985e5.bin` (Real-ESRGAN 4x) degrada严重mente cores:
- Canal Blue: 160→90 (38% mais escuro)
- Histograma pico: 255→92
- Std deviation: 74→23 (perda massiva de contraste)

**Causa raiz (investigação):**
1. Real-ESRGAN foi treinado em imagens gerais (landscape, objects, anime)
2. Modelo Real-ESRGAN_x4plus (15.9M params) é otimizado para **restauração de degradação** (blur, noise, JPEG artifacts), não para **preservação de cores**
3. O discriminador GAN pode estar incentivando distribuição de cores "média" do treino
4. Fooocus pode estar aplicando processamento adicional (denoise strength) que distorce cores

**Possíveis soluções:**
- **Lanczos (OpenCV)**: `cv2.resize(img, (w*2, h*2), interpolation=cv2.INTER_LANCZOS4)` — sem ML, preserva cores 100%
- **Real-ESRGAN 2x** (menos agressivo que 4x): modelo `RealESRGAN_x2plus`
- **Correção de pós-cor**: aplicar histogram matching após upscale
- **Verificar denoise strength**: SE8 pode estar aplicando denoise durante upscale

---

## 34. ControlNet LoRA vs Standard com modelos inpainting (2026-07-05)

**Problema:** Tentamos habilitar OpenPose ControlNet para LustifyNSFW inpainting. LoRA-based ControlNet crashou, Standard ControlNet funcionou.

**Causa raiz (investigação técnica):**
1. **LoRA-based ControlNet** (`control-lora-openposeXL2-rank256`): Tem chave `lora_controlnet`. Durante `pre_run()`, copia pesos do UNet inpainting (9 canais) para o ControlNet, depois sobrepõe pesos LoRA (4 canais) → `RuntimeError: shape '[320, 9, 3, 3]' invalid for input of size 11520`
2. **Standard ControlNet** (`xinsir/controlnet-union-sdxl-1.0`): NÃO tem chave `lora_controlnet`. Arquitetura independente, não copia pesos do UNet → funciona normalmente

**Diferença fundamental:**
| Tipo | Chave `lora_controlnet` | Copia pesos UNet | Compatível com inpainting |
|------|------------------------|------------------|--------------------------|
| LoRA ControlNet | ✅ Sim | ✅ Sim (9 canais) | ❌ Não |
| Standard ControlNet | ❌ Não | ❌ Não | ✅ Sim |

**Solução:** Usar `xinsir/controlnet-union-sdxl-1.0` (2.4GB, standard ControlNet) em vez de `control-lora-openposeXL2-rank256` (739MB, LoRA).

**Lição:**
- O tamanho do modelo NÃO indica compatibilidade — o LoRA (739MB) é menor mas incompatível
- A arquitetura importa: LoRA precisa copiar pesos do UNet, Standard não
- `controlnet-union-sdxl-1.0` suporta 10+ tipos de controle (OpenPose, Canny, Depth, etc.) em um único modelo
- Funciona com QUALQUER modelo SDXL, incluindo inpainting (9 canais)

**Validação E2E:** Job `cr_aa5a54e9da76` — 5 attempts, todos pose_changed=False, composite=10.18 (best)

**Otimização de peso (2026-07-05):**
| Peso | Best Composite | Observação |
|------|---------------|------------|
| 0.3 | **5.17** | Melhor — sutil, não sobrepõe inpainting |
| 0.5 | 10.18 | Médio |
| 0.7 | 8.35 | Segundo melhor — mais forte, menos flexível |

**Conclusão:** weight=0.3 é ideal para LustifyNSFW + ControlNet Union. O peso baixo dá guidance sutil de pose sem competir com o processo de inpainting. Commit `35be6b24`.

---

## 35. SDXL Refiner é INCOMPATÍVEL com pipeline NSFW (2026-07-05)

**Problema:** Testamos `sd_xl_refiner_1.0.safetensors` para melhorar textura/detalhes.

**Resultados:**
| Métrica | Sem Refiner | Com Refiner |
|---------|-------------|-------------|
| RAM pico | 20GB (61%) | **34.5GB (93.9%)** |
| Pose changed | 0/5 | **5/5 (100%)** |
| Melhor composite | **5.17** | 13.91 |
| Landmark drift | 12-17% | **35-61%** |

**Causa:** O SDXL Refiner usa `joint denoising` — ele denoisa juntamente com o base model, mas o refiner foi treinado em dados diferentes e altera a pose completamente. Mesmo com `refiner_switch=0.5` (muda na metade dos steps), o refiner sobrescreve a pose estabelecida pelo base+ControlNet.

**Lição:**
- SDXL Refiner NÃO melhora qualidade em pipelines de inpainting com pose control
- O refiner causa: (1) RAM +75%, (2) pose_changed=100%, (3) composite 2.7x pior
- Para melhorar textura/detalhes, usar LoRAs (add-detail-xl) ou ESRGAN pós-processamento
- Refiner é útil apenas para text-to-image puro, não para inpainting com restrições de pose

---

## 36. Base64 vs cv2.imread — fallback para arquivos (2026-07-04)

**Problema:** `cv2.imdecode()` falha com imagens grandes via base64 em containers com memória limitada.

**Solução:** Fallback para salvar arquivo temporário e usar `cv2.imread()` quando `imdecode()` falha.

**Lição:** Sempre ter fallback I/O para containers Docker com limitação de memória.

---

## 37. Steps 60→50 + NSFW Prompt Ultra-Realistic (2026-07-04)

**Mudanças:**
- Steps: 40→60→50 (50 steps = compromisso ideal, ~100s vs ~150s)
- NSFW prompt: adicionado "ultra realistic photograph, DSLR photo, natural skin subsurface scattering, film grain, micro details on skin"

**Trade-off:** 50 steps mantém qualidade boa com velocidade 3x mais rápida que 60.

### Testes 50 steps — 4 imagens validadas

| Imagem | Composite | Head% | Clothes% | Landmark% | Pose OK |
|--------|-----------|-------|----------|-----------|---------|
| test01 (casual) | 5.161 | 0.07 | 48.0 | 1.99 | ✅ |
| test02 (dress) | 2.782 | 0.16 | 16.9 | 3.88 | ✅ |
| test03 (sport) | 2.755 | 0.05 | 23.8 | 1.28 | ✅ |
| test04 (formal) | 2.866 | 0.14 | 18.7 | 5.10 | ✅ |

**Conclusão:** 50 steps funciona bem em todas as imagens. Velocidade ~100s/tentativa (vs ~150s com 60). Pose preservada em 100% dos casos.

**Imagens de teste:** `show/test_images/` (8 imagens baixadas de Unsplash)

---

## 38. E2E Ensemble Fix — SE11 pipelines sem detector (2026-07-03)

**Problema:** Pipeline NSFW falhava com `name '_C' is not defined` no SE10. Raiz: duas chamadas SE10 no pipeline não passavam `detector` param, defaultando para GroundingDINO (quebrado).

**Causa raiz investigada:** Debug logging revelou que SE10 recebia `detector=groundingdino` em vez de `detector=ensemble`. Três chamadas SE10 no pipeline:
1. **Person detection** (line 406): `detector="ensemble"` ✅
2. **Clothes detection** (line 642): `detector="florence2"` ❌ → Florence2 quebrado
3. **Result clothes detection** (line 152): sem `detector` → default `groundingdino` ❌

**Fixes:**
- `_detect_result_clothes()`: adicionado `detector="ensemble"`
- Clothes detection: trocado `detector="florence2"` → `detector="ensemble"`
- Ambos pipelines (production + experimental)

**Resultado E2E (TESTE1.jpg):** Sucesso! Job `cr_dcc0421c5a3a`, 1 tentativa, composite=1.816, person 48.9% coverage, conf=0.9972.

---

## 39. NSFW Prompt Override Fix — /jobs/nsfw sempre usa prompt hardcoded (2026-07-03)

**Problema:** Usuário enviava `prompt=woman in elegant dress` na rota `/jobs/nsfw`. O pipeline usava `job.request.prompt or nsfw_prompt` — como prompt do usuário é não-vazio, sobrescrevia o NSFW prompt. Resultado: vestido gerado em vez de nudez.

**Fix:** `/jobs/nsfw` agora ignora `job.request.prompt` e sempre usa `nsfw_prompt` hardcoded. Log de warning quando prompt do usuário é descartado. Para prompts customizados, usar `/jobs/nsfw-test`.

**Commits:** `c48556e` (NSFW prompt), `5caa896` (ensemble fix)

---

## 40. Face-ellipse fallback pipeline E2E SUCCESS (2026-07-03)

**Job:** `cr_987fd61e9121` — TESTE1.jpg processed end-to-end with face-ellipse fallback.

### Problem: SE10 GroundingDINO completely fails on TESTE1.jpg
- TESTE1.jpg: woman in pink jacket, gaming chair, monitors background
- GroundingDINO detects only 1.6% person coverage (face-only bbox: [116,0,269,63])
- Three-level fallback chain implemented:
  1. **Retry with lower thresholds** (box=0.10, text=0.08) — still 1.6%
  2. **GrabCut seeded from haarcascade** — fails with assertion error (face bbox too small)
  3. **Face-ellipse fallback** — **WORKS! 63.7% coverage**

### Fallback chain implementation
- **Retry**: lowered SE10 thresholds from box=0.20/text=0.15 to box=0.10/text=0.08
- **GrabCut**: `cv2.grabCut()` with face bbox as seed — `!bgdSamples.empty()` assertion fails because face is small relative to image
- **Face-ellipse**: haarcascade face detection → `cv2.ellipse()` with 4× face_width × 8× face_height → 63.7% coverage

### Additional fixes applied
1. **body_mask NameError (Fix 2)**: Replaced monolithic try/except debug save block with per-mask independent saves
2. **Florence-2 threshold (Fix 3)**: box_threshold 0.06→0.12, text_threshold 0.04→0.08 (reduced 31 garment false positives)
3. **Haarcascade Docker**: Copied `haarcascade_frontalface_default.xml` to app dir + path fallback in `_get_face_cascade()`
4. **Memory increase**: SE11 container 1G→2G (ONNX + MediaPipe + InsightFace needed more)

### E2E Results (try_3 = best, composite=10.611)
| Try | Strength | Composite | SkinRatio | Head% | Landmark% | Clothes% | PoseOK |
|-----|----------|-----------|-----------|-------|-----------|----------|--------|
| 1 | 0.86 | 18.846 | 3.311 | 0.825 | 40.35 | 75.002 | ✅ |
| 2 | 0.89 | 19.125 | 3.035 | 0.588 | 44.06 | 66.035 | ✅ |
| **3** | **0.92** | **10.611** | **3.407** | **0.871** | **12.892** | **75.315** | **✅** |
| 4 | 0.95 | 27.091 | 2.967 | 0.956 | 67.17 | 75.359 | ❌ |
| 5 | 0.98 | 22.008 | 2.997 | 0.962 | 52.31 | 69.210 | ✅ |

- Face 100% preserved (identity, expression, pink hair)
- try_3 best balance: strength=0.92, minimal landmark deviation (12.89%), pose NOT changed
- try_4 worst: strength=0.95 caused 67% landmark deviation (pose drift)

### Files copied to show/
- `show/teste1_nsfw_best.png` — final result
- `show/teste1_try3_best.png` — try_3 result
- `show/teste1_mask_overlay.png` — inpaint mask (53.9%)
- `show/teste1_face_protect.png` — head protect (14.8%)
- `show/teste1_nsfw_grid.png` — debug grid (8 panels)
- `show/teste1_original.jpg` — original

---

## 41. Face protection — layered mask construction (2026-07-02)

**Problema:** Na OK2.png (AI model), o rosto era alterado pelo LustifyNSFW e a roupa nem sempre era removida. A abordagem body-based (person − head) com head_mask processado criava buracos e comia área de roupa.

**Solução:** Reescrita completa da construção da máscara com abordagem em camadas profissional:

```
Layer 1: Person silhouette (SE10) — fundo removido
Layer 2: Hair protection — head_mask (expand_up=2.5, neck_margin=0.3)
Layer 3: Face protection — face_oval_mask (MediaPipe Face Mesh)
Layer 4: Combined protection = hair OR face
Layer 5: Inpaint = person − protection (roupa + pele exposta)
Layer 6: Dilate + close para bordas suaves do SE8
```

**Resultado (OK2.png):**
| Métrica | v1 (bugado) | v4 (final) |
|---------|-------------|------------|
| Inpaint mask | 46.5% | 40.9% |
| Head protect | 0.4% | 9.3% |
| Face preservada | NÃO | SIM |
| Roupa removida | NÃO | SIM |

**Commits:** `038ab64`, `391af29`

**Arquivos alterados:**
- `services/se11-clothes-removal/app/services/pipeline_nsfw.py` (principal)

---

## 42. Stage "detecting" nunca completava (2026-07-02)

**Problema:** Nos 2 pipelines NSFW (`pipeline_nsfw.py`, `pipeline_nsfw_experimental.py`), o stage "detecting" era marcado como "processing" mas nunca como "completed" antes de transicionar para "inpainting". Isso fazia o progress bar ficar travado em ~70% mesmo com job "completed".

**Fix:** Adicionado `job.update_stage("detecting", "completed", progress=100.0)` + `store.save_job()` antes da transição para "inpainting" em todos os 3 arquivos.

**Arquivos alterados:**
- `services/se11-clothes-removal/app/services/pipeline_nsfw.py:567`
- `services/se11-clothes-removal/app/services/pipeline_nsfw_experimental.py:530`

---

## 43. NSFW TEST V2 — Scoring Multidimensional (2026-07-02)

**Resultado E2E validado:** `cr_f7e6ef75b636` — 5 tentativas, scoring multidimensional (head + clothes + landmark).

### Scoring Multidimensional

Fórmula: `score = 0.5 × head_avg + 0.3 × clothes_pct + 0.2 × max_landmark`

| Try | Strength | Head% | Clothes% | MaxLandmark | Composite | Winner? |
|-----|----------|-------|----------|-------------|-----------|---------|
| 1 | 0.86 | 0.585 | **27.2** | 14.52 | **11.361** | **YES** |
| 2 | 0.89 | **0.265** | 33.9 | **8.11** | 11.922 | |
| 3 | 0.92 | 0.435 | 29.1 | 14.49 | 11.848 | |
| 4 | 0.95 | 0.406 | 31.5 | 10.45 | 11.733 | |
| 5 | 0.98 | 0.610 | 43.5 | 18.77 | 17.102 | |

**Conclusão:** Attempt 1 (0.86) vence porque tem MENOS roupa residual (27.2%). O scoring corretamente equilibra preservação facial + remoção de roupa + estabilidade de pose.

---

## 44. LustifyNSFW vs JuggernautXL — Production Merge (2026-07-02)

**Resultado E2E validado:** `cr_5c8931461b5b` — LustifyNSFW 0.86, head_pct=0.342%, pose_changed=False, roupa 100% removida, rosto preservado.

### Descoberta crítica: LustifyNSFW vs JuggernautXL

| Modelo | Resultado | Roupa | Rosto | Pose |
|--------|-----------|-------|-------|------|
| JuggernautXL 0.35 | Cinza/blobs | ❌ | ✅ | ✅ |
| JuggernautXL 0.65 | Suéter azul visível | ❌ | ✅ | ✅ |
| JuggernautXL 0.75 | Parcial NSFW + roupa | ❌ | ⚠️ | ✅ |
| JuggernautXL 0.86 | Artefato facial + roupa | ❌ | ❌ | ✅ |
| **LustifyNSFW 0.86** | **Perfeito** | **✅** | **✅** | **✅** |

**Conclusão:** LustifyNSFW_v20-inpainting é modelo NSFW+inpainting nativo, supera JuggernautXL para remoção de roupa.

### Correções implementadas nesta sessão:

| Passo | Arquivo | Mudança |
|---|---|---|
| 1. Modelo | pipeline_v2, routes, schemas | Default JuggernautXL → LustifyNSFW |
| 2. Strength | pipeline_v2, routes, schemas | 0.35→0.65→0.75→**0.86** |
| 3. Hair protection | pipeline_v2 | head_subtract com expand_up=2.5, expand_w=0.8, dilate=25px, iter=3 |
| 4. Head detector | head_detector.py | Novos params: expand_up, expand_w (eram hardcoded 1.5/0.5) |
| 5. OpenPose condicional | pipeline_v2 | Só para Juggernaut (Lustify incompatível) |

### Bugs corrigidos:
- **OpenPose RuntimeError:** Lustify UNet architecture incompatible with ControlNet → SOLVED via ControlNet Union SDXL. Commit `3906bb9a`.
- **OpenPose CRASH with exit code 137 (OOM):** ControlNet Union SDXL is lighter and compatible. Commit `3906bb9a`.
- **ControlNet Union weight optimization:** Tested w=0.3, 0.5, 0.7. Best: **w=0.3 → composite=5.17**. Commit `35be6b24`.
- **SDXL Refiner INCOMPATIBLE:** RAM peak: 34.5GB, ALL 5 attempts pose_changed=True. Deleted model, reverted. Commit `76095eaa`.
- **Hair bleed:** clothes_mask + dilate(15px) bleeds into hair → head subtraction with larger ellipse

### Production pipeline migration:
1. **Face blending removed**: Laplacian/LAB harmonization replaced with simple passthrough
2. **FaceID extraction**: `extract_faceid_embedding()` called before retry loop
3. **OpenPose conditional**: Only sent when `juggernaut` in base_model
4. **Debug masks**: `30_mask_overlay.png`, `detection_meta.json`, `20_garment_N_class.png` saved per job
5. **Pose thresholds relaxed**: `head=1.5%, torso=8.0%, limbs=5.0%`

---

## 45. NSFW v22/v23 — Leffa-style clothes-neutralized IP-Adapter ref (2026-06-30)

**Rota oficial:** `POST /jobs` (file upload) `mode="nsfw"`
**Pipeline:** `pipeline_nsfw.py` (v22 — clothes-neutralized IP-Adapter reference)

### BREAKTHROUGH: Suéter residual RESOLVIDO

**Causa raiz:** IP-Adapter usava imagem original vestida → encoder extraía features de roupa → vazava para o resultado (exatamente a distorção que Leffa CVPR2025 descreve: "inadequate attention to corresponding regions")

**Solução:** `_build_clothes_neutral_ref()` — preenche região de roupa com tom de pele médio + ruído sutil antes de codificar. Encoder vê pose/rosto/corpo mas NÃO vê textura da roupa.

### Config vencedora (B_neu_s086 — validada visualmente pelo usuário):
- **IP-Adapter:** CLOTHES-NEUTRALIZED ref (weight=0.8, stop=0.5)
- strength=0.86 (era 0.84 — neutral ref precisa mais força para compensar)
- field=0.618, erode=0, seed=-1
- Retry: 0.86/0.87/0.90
- **Head mask:** subtract clothes → DT(8px) → inflate → close(9px) → blur(15px,σ=5) → clip person
- **Feathered composite:** GaussianBlur(21px) alpha blend
- **Reinhard LAB color transfer:** skin-only reference
- Pre-scale to min 1024px

### Pose conditioning test:
- Adicionado `render_pose_stick_figure()` no `pose_detector.py` usando MediaPipe
- Testado como segunda imagem do IP-Adapter (weight=0.4)
- **Resultado: DEGRADOU** a preservação de pose (score 21.3 vs 0.0 sem stick)
- **Razão:** IP-Adapter/CLIP codifica stick figure sintético como "desenho abstrato", não como estrutura corporal
- **Status:** desativado em produção, código mantido para futuras experiências

### OpenPose ControlNet integration (v23 → v26):
- SE10 `/v1/segment` now accepts `include_pose=true` and returns `controlnet_image` (DWPose stick figure)
- SE11 requests pose control image during person detection and passes it to SE8 as `OpenPose` image prompt
- SE8 `_apply_controlnet()` loads `controlnet-union-sdxl-1.0.safetensors` and applies it during diffusion
- **v26: Switched from LoRA to Standard ControlNet** — `control-lora-openposeXL2-rank256` incompatible with inpainting (9ch UNet), `xinsir/controlnet-union-sdxl-1.0` works perfectly

### Face blend improvement (v23.1 → v23.4):
- v23.1: Protected region reduced from full head+hair+neck to inner face only (~23% of previous mask)
- v23.2: Protected region reduced further to central face only (~10.5% of head mask)
- v23.2: Distance-transform feather substitui Gaussian blur
- v23.2: Eroded head mask cria transition band para SE8 gerar queixo/bochechas
- v23.2: Harmonização LAB localizada na faixa de transição + pele exposta original
- v23.3: Tentativa com MediaPipe Face Mesh para centralizar máscara; descartado por falha de contexto GPU
- **v23.4:** Voltou a Haar bbox com máscara de FACE COMPLETA (margin_above=0.05, margin_below=0.55, margin_sides=0.40)
- **v23.4:** Feather direcional: bordas superior/laterais duras, só queixo/pescoço é suavizado por distance transform
- **E2E validated:** job `cr_4c585ccaada4` completed; face_protect_mask = 38.8k px vs head_adjusted = 131.1k px (~29.6%); best score = 11.8

### SE11 Docker rebuild
- Rebuild com mediapipe + libs gráficas (libxcb). Imagem funcional.

---

## 46. NSFW v18 — Fooocus migration + body-mask (2026-06-26)

**Rota oficial:** `POST /jobs` (file upload) `mode="nsfw"`
**Pipeline:** `pipeline_nsfw.py` (v18 — body-mask + person_expanded + face paste)

### Config óptima (PROVEN):
- body_mask como inpaint (não clothing mask)
- 3.5% dilation adaptativa
- erode_or_dilate=-3
- morphOpen 3px + GaussianBlur 3px + morphClose 5px + vertical 1x7
- strength=0.65, field=0.85
- NsfwPov 0.3, add-detail-xl 1.0
- Sem Reinhard LAB (pele correcta do SE8)
- Smooth blend GaussianBlur 7px no resultado FINAL

**Prompt positive:** `NSFW×5, solo, same body position, unchanged pose, skin tone matching`
**Prompt negative:** `(deformed:1.3), extra limbs, airbrushed, plastic skin, changing pose:1.5`

### Compositing:
- paste binário → GaussianBlur 7px blend → head force
- GPU: RTX 3090 24GB — quando CUDA assertion, `pkill -f python` no SE8

---

## 47. Config SE11 (referência rápida)

- Port: 8011, API_KEY: se11-test-key-2026
- DIVISOR=11, Redis DB=11
- SE10_URL=http://host.docker.internal:8010 (Docker) / http://localhost:8010 (local)
- SE8_URL=http://host.docker.internal:8008 (Docker) / http://localhost:8008 (local)
- DEFAULT_PROMPT="natural skin tone matching surrounding skin, seamless texture, photorealistic, professional photography, soft lighting"
- denoise=0.70, inpaint_respective_field=0.85, erode_or_dilate=-10
- LoRAs: NsfwPov(0.6) + offset(0.1) + detail(0.8)
- BEST_CLOTHING_CLASSES="top, blouse, camisole, shirt, spaghetti strap"
- Inpaint mask: clothing_exact (body AND NOT exposed_skin) dilatado kernel=7px, 2 iter
- text_threshold=0.04 for SE10
- detector=florence2 for clothes detection

---

## 48. Fixes aplicados (pipeline SE11)

1. **base64 padding** — `_fix_b64_padding()` antes de `b64.b64decode()`
2. **PNG transparency** — `require_base64=False` em SE8 client + download via file URL, evita base64 truncado do SE8
3. **Aspect ratio dinâmico** — `_pick_sdxl_ratio()` detecta proporção da imagem e escolhe SDXL ratio mais próximo
4. **Styles limpas** — removido "Fooocus Enhance" e "Fooocus Sharp" que alteravam demais a aparência
5. **inpaint_respective_field=0.85** — crop cobre mais contexto ao redor da máscara
6. **advanced_params always sent** — engine/strength/field sempre enviados ao SE8
7. **Mask filtering fix** — objetos E masks são filtrados juntos via `_keep_object()`, evita masks de false positives
8. **Negative prompt** — removido "exposed skin" (auto-sabotava CFG), adicionado nudity/nude/naked/wrinkled/scarred
9. **Denoise 0.70** — sweet spot: suficiente para gerar pele, baixo o bastante para evitar nipples
10. **LoRA matching fix** — direct matching de `model.state_dict().keys()` para key_map vazio

---

## Referências

| Arquivo | Caminho |
|---------|---------|
| Roadmap | `services/se11-clothes-removal/docs/ROADMAP.md` |
| History | `services/se11-clothes-removal/docs/HISTORY.md` |
| Plans | `services/se11-clothes-removal/docs/plans/` |
| Pipeline NSFW | `app/services/pipeline_nsfw.py` |
| Pipeline NSFW Experimental | `app/services/pipeline_nsfw_experimental.py` |
| Routes | `app/api/routes.py` |