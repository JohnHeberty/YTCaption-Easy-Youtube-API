# UPGRADE — Como modelos VTON trocam roupa sem colagem (lições para o SE11)

Pesquisa baseada em 3 papers SOTA de Virtual Try-On:
- **IDM-VTON** (ECCV 2024, arXiv:2403.05139) — arquitetura de referência dual-encoder
- **OOTDiffusion** (AAAI 2025, arXiv:2403.01779) — outfitting fusion em latent space
- **Leffa** (CVPR 2025, arXiv:2412.08486) — SOTA atual, resolve distorção de textura via flow fields em attention

---

## Princípio central: SINTETIZAR, não COLAR

Os modelos VTON **nunca colam a peça de roupa**. A peça é **codificada em features** e o modelo de difusão **gera pixels novos** que casam com a roupa mas se conformam à geometria/pose/iluminação do corpo. É por isso que não há aparência de colagem — os pixels são sintetizados de novo, integrados ao corpo.

---

## Mecanismo técnico (IDM-VTON = arquitetura de referência)

1. **Dual encoder da peça** — a peça é codificada por **dois caminhos** e injetada no UNet:
   - (a) **CLIP/image encoder → cross-attention** (semântica de alto nível: "que peça é")
   - (b) **UNet paralelo → self-attention** (features de baixo nível: textura/padrão/detalhe)
2. **Imagem-pessoa agnóstica** — a região da roupa é **removida** (mascarada) da pessoa; rosto/mãos/cabelo/pele **ficam intactos**. Somada a **DensePose** (geometria do corpo UV) + prompt textual.
3. **Difusão inpainta só a região da roupa** — parte da imagem-pessoa mascarada + ruído, regenera apenas a roupa, sintetizada para casar com as features da peça E com a pose/iluminação do corpo.
4. **O rosto é preservado por construção** — porque a máscara agnóstica só remove a roupa; o rosto/mãos/skin já estão no latent base e não são regenerados.

---

## Por que não vira "colagem" (insight da Leffa, CVPR 2025 — o SOTA)

A Leffa diagnosticou exatamente o problema: **"prior methods often distort fine-grained textural details"** porque há **"inadequate attention to corresponding regions in the reference image"**. Ou seja, o query do alvo não está prestando atenção na região certa da referência.

Solução da Leffa: **"learning flow fields in attention"** — uma **regularização loss sobre o attention map** que força o query do alvo a atender ao **key correto** da referência durante o treino. É **model-agnóstica**, melhora qualquer difusão.

---

## Mapeamento direto para o problema SE11 (e por que temos "suéter residual")

O SE11 faz o **problema inverso**: em vez de trocar roupa, **remove roupa e gera pele**. Mas a estrutura é a mesma. O pipeline atual já faz a coisa certa conceitualmente — usa **IP-Adapter** (sintetizar, não colar) com a **imagem original como referência**.

**O bug:** usar a imagem original **vestida** como referência do IP-Adapter = o codificador extrai features de **roupa também**. É **exatamente** a distorção que a Leffa descreve: atenção vazando para a região errada (roupa em vez de pele). Por isso `weight=0.8` preserva pose mas **também preserva roupa** → suéter residual. É um trade-off fundamental dessa escolha de referência.

---

## Plano proposto para o SE11 (sem treinar modelo custom)

Três abordagens testáveis, em ordem de custo/benefício:

### Opção A — Referência com roupa mascarada (análogo direto da Leffa via pré-processamento)
- Em vez de passar a imagem original vestida ao IP-Adapter, **mascarar a região de roupa** (zerar/blurar/tom de pele neutro) **antes** de codificar.
- O IP-Adapter recebe pose/rosto/formato-do-corpo mas **não tem acesso à textura da roupa** → não pode regenerá-la.
- Muda ~1 função no `pipeline_nsfw.py` (preparar a referência). Teste rápido no `exploration/run_mask_pipeline.py`.

**STATUS (2026-06-30): ✅ IMPLEMENTADO e VALIDADO**
- Config vencedora: `B_neu_s086` — clothes-neutralized ref + strength=0.86
- Resultado: suéter residual desapareceu, pose melhorou (limbs 4.1% vs 10.0%), 3x mais rápido
- Arquivos: `pipeline_nsfw.py`, `exploration/run_mask_pipeline.py`

### Opção B — Dois passes (destrói roupa → refina)
- Passo 1: inpaint da roupa com prompt genérico de pele, **strength alto** (destrói a roupa, corpo tosco).
- Passo 2: usar o **resultado do passo 1 (nu)** como referência do IP-Adapter + re-inpaint para qualidade.
- A referência do passo 2 não tem roupa para vazar. Custo: 2x geração.

### Opção C — Estrutura estilo IDM-VTON (overkill, precisa treino)
- Codificador dedicado de pele (UNet paralelo) → só vale se A e B não resolverem. Exige dataset/treino.

---

## Plano de melhorias no ecossistema SE10/SE8/SE11

Após resolver o suéter residual no SE11, o próximo passo é espelhar a arquitetura completa dos modelos VTON SOTA (IDM-VTON/OOTDiffusion/Leffa), que dependem de três condicionamentos simultâneos:
1. **Imagem agnóstica** (sem roupa) — já coberto pelo SE11
2. **Referência da aparência** (clothes-neutralized) — já coberto pelo SE11
3. **Geometria do corpo (DensePose)** — **FALTA**
4. **Parsing semântico do corpo** — **FALTA**

### Fase 1 — SE10: DensePose + Human Parsing
**Esforço:** médio | **Valor:** alto

Adicionar ao SE10:
- **DensePose** (detectron2): gera UV map do corpo (IUV image)
- **Human Parsing** (SCHP): segmenta face, cabelo, braços, pernas, torso, pés, mãos
- Novo campo no retorno `/v1/segment`: `densepose` (base64) + `human_parsing` (base64)

**Resultado para SE11:**
- Máscaras anatomicamente precisas por parte do corpo
- `body_mask` pode ser separado em torso/arms/legs
- Melhor proteção de cabelo/mãos
- Material para ControlNet DensePose no SE8

### Fase 1 — SE10: DensePose + Human Parsing
**Esforço:** médio | **Valor:** alto

Adicionar ao SE10:
- **DensePose** (detectron2): gera UV map do corpo (IUV image)
- **Human Parsing** (SCHP): segmenta face, cabelo, braços, pernas, torso, pés, mãos
- Novo campo no retorno `/v1/segment`: `densepose` (base64) + `human_parsing` (base64)

**Resultado para SE11:**
- Máscaras anatomicamente precisas por parte do corpo
- `body_mask` pode ser separado em torso/arms/legs
- Melhor proteção de cabelo/mãos
- Material para ControlNet DensePose no SE8

**NOTA (2026-06-30):** Testamos uma alternativa pragmática — gerar stick figure via MediaPipe e passar como segunda imagem do IP-Adapter. **Falhou:** degradou a preservação de pose (score 21.3 vs 0.0 sem stick). IP-Adapter/CLIP codifica figuras sintéticas como "desenho abstrato", não como estrutura corporal. Isso confirma que **condicionamento de aparência (IP-Adapter) ≠ condicionamento estrutural (ControlNet/DensePose)**.

### Fase 2 — SE8: ControlNet DensePose no endpoint de inpaint
**Esforço:** alto | **Valor:** alto

**Barreira técnica real (2026-06-30):**
- `app/infrastructure/operators.py::ControlNetApplyAdvanced` está como **stub** ("full implementation pending")
- `modules/core.py` tem `apply_controlnet` real via ComfyUI, mas o **pipeline de inpaint do SE8 não o chama**
- Não há modelos ControlNet baixados em `data/models/controlnet/`

Para funcionar precisa:
1. Implementar o stub `ControlNetApplyAdvanced` ou usar `modules/core.apply_controlnet`
2. Integrar a chamada no fluxo de inpaint (`app/services/worker.py` / `_process_diffusion`)
3. Baixar modelo ControlNet SDXL compatível (ex: `diffusers_xl_canny_mid`, `controlnet-openpose-sdxl`, ou DensePose SDXL)
4. Expor no endpoint `/v1/generation/image-inpaint-outpaint` campos `cn_tasks` com imagem de controle

**Resultado para SE11:**
- Geração condicionada pela geometria real do corpo
- Reduz dependência do IP weight=0.8
- Permite reduzir `strength` sem perder pose → menos artefatos

### Fase 3 — SE11: Integrar SE10→SE8 com DensePose
**Esforço:** baixo | **Valor:** alto

- Enviar `densepose` do SE10 para o SE8 no payload de inpaint
- Usar human parsing do SE10 para:
  - Proteger cabelo/mãos/pés com máscaras mais precisas
  - Separar torso das extremidades para inpaint adaptativo
  - Detectar skin tone por região (cara, braços, torso) para color transfer

### Fase 4 — Encoder dedicado de pele (IDM-VTON-style) — complexo
**Esforço:** muito alto | **Valor:** incerto

- Modificar UNet do Fooocus para adicionar codificador paralelo de "aparência alvo"
- Possivelmente fine-tuning de modelo

**Decisão:** só executar se Fase 1+2+3 não forem suficientes.

---

## Recomendação atualizada

1. ✅ **Opção A no SE11** — concluída
2. ❌ **Abordagem pragmática (MediaPipe stick figure como IP-Adapter)** — testada e descartada
3. 🎯 **Próximo passo real:** Fase 1 (SE10 DensePose + Human Parsing) + Fase 2 (ativar ControlNet real no SE8)
4. Depois: Fase 3 (SE11 integração)
5. Só então avaliar Fase 4

**Conclusão central (2026-06-30):** Para implementar de verdade o condicionamento de pose do UPGRADE.md, será necessário ativar **ControlNet no SE8** (trabalho arquitetural) e/ou adicionar **DensePose no SE10**. A abordagem pragmática via IP-Adapter não funcionou.

---

## Referências

- IDM-VTON: https://github.com/yisol/IDM-VTON — paper: https://arxiv.org/abs/2403.05139
- OOTDiffusion: https://github.com/levihsu/OOTDiffusion — paper: https://arxiv.org/abs/2403.01779
- Leffa: https://github.com/franciszzj/Leffa — paper: https://arxiv.org/abs/2412.08486

## Config atual do SE11 (baseline → vencedora)
- **VENCEDORA v22 (2026-06-30):** clothes-neutralized ref, weight=0.8, strength=0.86, stop=0.5, field=0.618, seed=-1
- Retry strengths: 0.86/0.87/0.90
- IP-Adapter: **imagem com roupa neutralizada** como referência (não mais vestida)
- Pipeline: SE10 person → SE10 clothes → head mask → body_mask → SE8 inpaint (3 tries) → feathered composite → Reinhard LAB color transfer
- **Próxima evolução:** DensePose + ControlNet real no SE8 (a alternativa via IP-Adapter foi descartada — ver nota na Fase 1)
