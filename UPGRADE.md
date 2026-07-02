# PLANO MASTER: nsfw_test v2 — Correção e Re-alinhamento

## Visão Geral da Arquitetura

```
Rota /jobs (mode=nsfw)      → pipeline.py → run_nsfw()              → pipeline_nsfw.py (PRODUÇÃO)
Rota /jobs (mode=nsfw_test) → pipeline.py → run_nsfw_experimental_v2() → pipeline_nsfw_experimental_v2.py (TESTE)
```

**Zero código compartilhado entre produção e teste.** Alterações em nsfw_test são seguras.

---

## DIAGNÓSTICO: O que Fizemos vs o Plano Original

### O que o Search.md e UPGRADE.md original diziam

| Princípio | Fonte | Implementado? |
|---|---|---|
| Strength **0.30-0.45** (mínimo = preserva tudo) | Search.md §Parâmetros | **NÃO** — usamos 0.45-0.77 |
| **IP-Adapter FaceID** trava identidade facial | Search.md §Técnicas | **QUEBRADO** — SE8 loga e descarta |
| **ControlNet OpenPose** trava pose | Search.md §Técnicas | **AUSENTE** — nunca implementado |
| **Fooocus inpaint models** (não SDXL genérico) | UPGRADE.md Fase 1 | **NÃO** — usamos Juggernaut |
| Máscara = **clothes_mask** (só roupas) | UPGRADE.md §4.4 | **DESVIADO** — usamos body-not-head |
| `invert_mask=True` no SE8 | UPGRADE.md §3.1 | **NÃO ENVIADO** (funciona por acaso) |

### Bugs Críticos Encontrados

#### BUG 1: FaceID é um no-op (SE8 worker)
- **Local:** `services/se8-image-generation/app/services/worker.py` linhas 502-519
- O SE11 extrai embedding InsightFace (512-d), envia ao SE8
- O SE8 recebe, loga, e **descarta** — tem um `TODO`:
  ```python
  # TODO: Implement proper FaceID adapter preprocessing
  # This requires insightface + custom projection layer
  # For now, log the intent
  ```
- **Impacto:** Preservação facial depende APENAS do IP-Adapter ref (clothes-neutral), não do rosto

#### BUG 2: OpenPose ControlNet nunca enviado
- **Local:** `pipeline_nsfw_experimental_v2.py` linhas 434-436
- O plano original previa `cn_type: "OpenPose"` weight 0.5, stop 0.6
- Implementação atual: apenas 1 image_prompt (clothes-neutral ref)
- SE8 worker JÁ TEM suporte a OpenPose (`_apply_controlnet()` linhas 880-984)
- **Impacto:** Sem controle estrutural de pose — corpo deriva livremente

#### BUG 3: Strength muito alto
- **Local:** `pipeline_nsfw_experimental_v2.py` linha 418
- Default: 0.45, ramp até 0.57. Testamos até 0.77 em iterações
- Search.md recomenda **0.30-0.45**, sistemas profissionais usam **0.2-0.4**
- **Impacto:** Strength ≥0.55 causa rosto duplo, destrói pose

#### BUG 4: Máscara complexa demais
- Criamos máscara "cirúrgica" (clothes + 50px - head - exposed_skin)
- O plano original era simples: `clothes_mask + dilate(15px)`
- **Impacto:** Complexidade desnecessária, resultado imprevisível

#### BUG 5: `invert_mask` parameter não enviado ao SE8
- `http_client.py` aceita `invert_mask` mas não adiciona ao payload
- Funciona por acaso porque SE11 já inverte a máscara do seu lado
- **Impacto:** Frágil — qualquer mudança no SE8 pode quebrar

---

## PLANO DE CORREÇÃO (5 Passos)

### Passo 1: Revert strength para 0.35

**Arquivos:**
- `services/se11-clothes-removal/app/services/pipeline_nsfw_experimental_v2.py`
  - `base_strength` default: 0.45 → **0.35**
  - Ramp: 0.35 → 0.38 → 0.41 → 0.44 → 0.47 (step 0.03)
- `services/se11-clothes-removal/app/api/routes.py`
  - `test_inpaint_strength` Form default: 0.45 → **0.35**
- `services/se11-clothes-removal/app/api/schemas.py`
  - `test_inpaint_strength` Field default: 0.45 → **0.35**

**Justificativa:** Search.md §Parâmetros recomenda 0.30-0.45. Sistemas profissionais (WearView, Aragon) usam 0.2-0.4.

### Passo 2: Simplificar máscara para clothes_mask

**Arquivo:** `pipeline_nsfw_experimental_v2.py`

Substituir toda a lógica de Stage 4 (Build Invert Mask) por:

```python
if inpaint_mode == "invert_mask":
    # Máscara cirúrgica: SÓ roupas + margem leve
    inpaint_mask = clothes_combined.copy()
    dilate_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
    inpaint_mask = _cv2.dilate(inpaint_mask, dilate_k, iterations=1)
```

**Remover:**
- Head mask expandido (neck_margin_below=0.80, kernel=25, iter=3)
- Exposed skin detection
- Clothes margin 50px
- Clips ao person_binary

**Justificativa:** UPGRADE.md §4.4 planejava: `inpaint_mask = clothes_mask + dilate(15px)`. Simples e funcional.

### Passo 3: Adicionar OpenPose ControlNet

**Arquivo:** `pipeline_nsfw_experimental_v2.py`

1. Criar função `_build_openpose_image(pose_result, orig_h, orig_w)`:
   - Desenha esqueleto de MediaPipe em canvas preto
   - Landmarks: ombros, cotovelos, pulso, quadril, joelhos, tornozelos

2. Adicionar como segundo image_prompt:
   ```python
   image_prompts = [
       {"cn_img": ref_b64, "cn_stop": 0.5, "cn_weight": 0.8, "cn_type": "ImagePrompt"},
       {"cn_img": openpose_b64, "cn_stop": 0.6, "cn_weight": 0.5, "cn_type": "OpenPose"},
   ]
   ```

3. Gerar openpose ANTES do loop de tentativas (uma vez só)

**Verificar:** SE8 worker `_apply_controlnet()` suporta `"OpenPose"` — já implementado linhas 880-984.

**Justificativa:** Search.md §Técnicas: "ControlNet (OpenPose/Canny/Depth) — Weight 0.5-1.0, stop 0.5-0.7".

### Passo 4: Corrigir FaceID no SE8 Worker

**Arquivo:** `services/se8-image-generation/app/services/worker.py`

No método `_apply_ip_adapter()` (linhas 502-519), substituir TODO por:

```python
def _apply_ip_adapter(self, pipe, faceid_embeds, faceid_weight):
    """Apply IP-Adapter FaceID conditioning to UNet cross-attention."""
    if not faceid_embeds:
        return

    try:
        from diffusers import IPAdapterFaceIDPipeline
        import torch

        # Load IP-Adapter FaceID model (lazy)
        if not hasattr(self, '_faceid_pipeline'):
            self._faceid_pipeline = IPAdapterFaceIDPipeline(
                vae=pipe.vae,
                text_encoder=pipe.text_encoder,
                tokenizer=pipe.tokenizer,
                unet=pipe.unet,
                image_encoder=None,  # Using pre-extracted embeddings
            )
            self._faceid_pipeline.load_ip_adapter(
                "h94/IP-Adapter-FaceID",
                subfolder="sdxl_models",
                weight_name="ip-adapter-faceid-plusv2_sdxl.bin",
            )

        # Apply FaceID conditioning
        embeds = torch.tensor(faceid_embeds, dtype=torch.float32)
        self._faceid_pipeline.set_ip_adapter_scale(faceid_weight)
        # Store for use during inference
        pipe._faceid_embeds = embeds
        pipe._faceid_weight = faceid_weight

    except Exception as exc:
        logger.warning("FaceID adapter failed: %s — continuing without", exc)
```

**Alternativa mais simples (fallback):** Se diffusers IP-Adapter pipeline não estiver disponível, aplicar via cross-attention injection manual:

```python
# Store embeds in pipe metadata for cross-attention injection during inference
pipe._faceid_conditioning = {
    "embeds": faceid_embeds,
    "weight": faceid_weight,
}
```

**Verificar:** Quais bibliotecas IP-Adapter estão disponíveis no container SE8.

### Passo 5: Testar Fooocus inpaint models

**Verificação:** Checar se modelos existem no SE8:
```bash
docker exec image-engine ls /app/data/models/inpaint/
# Esperado: inpaint_v26.fooocus.patch, fooocus_lama.safetensors, fooocus_inpaint_head.pth
```

**Se disponíveis:** Mudar `base_model` default para `"fooocus_inpaint"` na pipeline.
**Se não disponíveis:** Manter Juggernaut (funciona bem com denoise 0.35).

---

## ORDEM DE EXECUÇÃO

```
Passo 1 (strength 0.35) ─┐
Passo 2 (clothes_mask)  ─┼─ Rápidos (~30 min total)
Passo 3 (OpenPose)      ─┘
                          ↓
Passo 4 (FaceID SE8)    ─── Maior trabalho (~2h)
                          ↓
Passo 5 (Fooocus test)  ─── Verificação (~15 min)
                          ↓
E2E test completo
```

---

## MÉTRICAS DE SUCESSO

| Métrica | Target | Como medir |
|---|---|---|
| Pose preservation (head_pct) | < 1.0% | MediaPipe compare_poses() |
| Face preservation | Sem rosto duplo, sem derivação | Visual + InsightFace cosine sim > 0.85 |
| Clothes removal | > 80% remoção | Visual + coverage ratio |
| Processing time | < 120s | Logs do pipeline |
| No double face | 0 ocorrências | Teste com 5+ imagens |

---

## ARQUIVOS A MODIFICAR

### SE11 (Clotes Removal)
- `app/services/pipeline_nsfw_experimental_v2.py` — Passos 1, 2, 3
- `app/api/routes.py` — Passo 1 (default strength)
- `app/api/schemas.py` — Passo 1 (default strength)
- `app/infrastructure/http_client.py` — Passo 3 (suporte OpenPose no payload)

### SE8 (Image Generation)
- `app/services/worker.py` — Passo 4 (FaceID real) + Passo 5 (Fooocus check)

---

## STATUS ATUAL (pós-iterações anteriores)

### ✅ Já implementado (manter)
- Schema: +5 campos (inpaint_mode, use_faceid, faceid_weight, test_inpaint_strength, base_model)
- Routes: +5 Form params
- Models: +5 campos opcionais
- SE8 Client: `inpaint()` com suporte a `ip_adapter_faceid_embeds`, `invert_mask`
- FaceID extractor: `faceid_extractor.py` com InsightFace buffalo_l
- Pipeline v2: fluxo completo com tentativas + pose validation
- SE8 Worker: `invert_mask_checkbox` support, IP-Adapter image_prompts, ControlNet

### ❌ Corrigir (passos 1-5)
- Strength 0.45 → 0.35
- Máscara cirúrgica → clothes_mask simples
- OpenPose ControlNet ausente → adicionar
- FaceID no-op → implementar de verdade
- Fooocus models → verificar e usar se disponíveis

---

## RISCOS

| Risco | Probabilidade | Mitigação |
|---|---|---|
| FaceID IP-Adapter não carrega no SE8 | Média | Fallback: sem FaceID, denoise baixo + OpenPose preserva bastante |
| OpenPose não gera resultado adequado | Baixa | SE8 já tem suporte testado; pesar weight se necessário |
| Strength 0.35 não remove roupas suficiente | Média | Ramp para 0.47; ou aceitar remoção parcial |
| Fooocus models incompatíveis | Média | Manter Juggernaut com denoise 0.35 |
