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
| Plano production | `docs/archived/PLAN.md` |

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
| Plano head detect | `PLAN-2.md` |

## 14. Leffa-style: Controlar o que o encoder vê (2026-06-30)

**Problema:** Suéter residual — IP-Adapter com weight=0.8 preservava pose mas também preservava roupa. Trade-off fundamental.

**Causa raiz (diagnosticada via pesquisa VTON):** O IP-Adapter recebia a imagem original VESTIDA como referência. O encoder CLIP extraía features de roupa junto com pose/rosto/corpo. Essa atenção vazando para a região errada é EXATAMENTE o que a Leffa (CVPR 2025) descreve como "inadequate attention to corresponding regions in the reference image" → distorção de textura.

**Solução (Opção A do UPGRADE.md):** `_build_clothes_neutral_ref()` — antes de passar a imagem ao IP-Adapter, preencher a região de roupa com tom de pele médio (amostrado da pele exposta da própria pessoa) + ruído sutil + blur. O encoder então só vê pose/rosto/formato-do-corpo, sem acesso à textura da roupa.

**Resultado:** Suéter residual desapareceu. Config vencedora: B_neu_s086 (ref neutra + strength=0.86). Pose: head=0.0%, torso=2.0%, limbs=4.1% (baseline era limbs=10.0%). Speed: 16s/try (era 46s).

**Lições:**
- Neutral ref precisa strength MAIOR (0.86 vs 0.84) — a neutralização enfraquece o sinal, a difusão precisa mais passos para compensar
- Amostrar tom de pele da própria pessoa (HSV mediana da pele exposta) — não usar tom fixo
- Erode clothes mask 5px antes de preencher + blur 15px na borda → transição natural
- Pesquisa de papers paga off: entender o mecanismo de como VTON models funcionam (sintetizar não colar, dual-encoder, attention regularization) levou direto à solução
- `exploration/UPGRADE.md` documenta a pesquisa completa (IDM-VTON, OOTDiffusion, Leffa)


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

**Objetivo:** Adicionar condicionamento estrutural de pose ao pipeline NSFW via ControlNet OpenPose, conforme fase 2 do `UPGRADE.md`.

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


## 17. Face blending: proteger só o centro do rosto evita efeito recorte (2026-06-30)

**Problema:** Usuário reportou que a face parecia um recorte colado da original ("efeito colagem").

**Causa raiz:** O pipeline protegia a cabeça inteira (face + cabelo + pescoço) via `head_adjusted` e a colava de volta com alpha feather de 21px. Como a cabeça, o cabelo e o pescoço permaneciam 100% originais, enquanto o corpo era gerado, a fronteira ficava visível — especialmente sob luz diferente ou com textura de pele gerada.

**Solução implementada (v23.1 → v23.2):**
1. Reduzir a máscara de proteção para **apenas o centro do rosto** (`face_protect_mask` com margens mínimas: 10% acima, 15% abaixo, 15% laterais).
2. Deixar o modelo gerar **testa, bochechas, queixo, mandíbula, pescoço e bordas do cabelo** naturalmente.
3. Substituir feather Gaussiano por **distance transform** (`cv2.distanceTransform`): alpha 1.0 no centro do rosto, decaindo para 0.0 ao longo de ~40px. A transição segue a geometria real da máscara, não uma caixa de blur fixa.
4. Erodir `head_mask` antes de subtrair de `person_binary`, criando uma **transition band** explícita que o SE8 é instruído a gerar.
5. Aplicar **harmonização de cor (Reinhard LAB) localizada** na faixa de transição + pele exposta original, e só depois re-aplicar a face protegida.

**Resultado:**
- Job `cr_75c5996737ab` (v23.1): `face_protect_mask` = 29.9k px vs `head_adjusted` = 131.1k px (~23% da área anterior); best score = 12.5.
- Job `cr_54e5dff89d04` (v23.2): `face_protect_mask` = 13.8k px vs `head_adjusted` = 131.1k px (~10.5% da área anterior); best score = 7.4.
- Score melhorou (menor = melhor preservação de pose) à medida que a máscara facial foi reduzida, indicando que o modelo ganha liberdade para gerar transição natural.
- Visualmente a fronteira entre face e corpo gerado fica mais natural porque o modelo cria a transição de pele em vez de colar uma borda suavizada.

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

