# PLAN: Fix SE8 Inpainting + SE11 Params

## Problema

Usuário reportou que output do SE11 "não tem nada a ver com a original" — objetivo era apenas remover roupas.

## Causa Raiz (SE8)

`process_generate()` em `services/se8-image-generation/app/services/worker.py` **nunca instancia InpaintWorker**:

1. `_apply_inpaint()` (L406-416) — retorna dict de estado, **não modifica nada**
2. `_process_diffusion()` (L453-495) — cria **latent vazia** em `aspect_ratios_selection` (1152×896 landscape)
3. Difusão padrão roda — **gera imagem completamente nova**, ignorando imagem+máscara
4. `InpaintWorker` (definido em `app/services/inpaint_worker.py` e `modules/inpaint_worker.py`) — **nunca é instanciado**
5. `modules/patch.py:297-327` — patch latent-level inpainting usa `inpaint_worker.current_task` que sempre é `None`

## Causa Raiz (SE11)

`services/se11-clothes-removal/app/infrastructure/http_client.py` manda params errados pro SE8:

1. `aspect_ratios_selection` hardcoded `"1152*896"` (landscape) — imagem portrait
2. `advanced_params` só enviado quando `inpaint_strength != 1.0`
3. `inpaint_respective_field` = 0.618 default — crop apertado
4. `style_selections` inclui `Fooocus Enhance` + `Fooocus Sharp` — altera aparência drasticamente

---

## Fase 1: Fix SE8 — Wiring InpaintWorker

### Arquivo: `services/se8-image-generation/app/services/worker.py`

#### 1.1 Reescrever `_apply_inpaint()` (L406-416)

- Decodificar `inpaint_input_image["image"]` → numpy RGB (H,W,3 uint8)
- Decodificar `inpaint_input_image["mask"]` → numpy grayscale (H,W uint8, 255=masked)
- Criar `InpaintWorker` do `modules.inpaint_worker.py` (legacy correto)
- Override dims do task pro crop do InpaintWorker
- Retornar worker no state dict

#### 1.2 Modificar `process_generate()` (L498-631)

**Antes do loop de difusão (L544):**
- Se modo inpaint: encoder fill image pro latent via `pipeline.encode_vae()`
- Criar latent mask do `worker.interested_mask`
- Chamar `worker.load_latent(latent_fill, latent_mask)`
- Setar `modules.inpaint_worker.current_task = worker`
- Isso ativa `patched_KSamplerX0Inpaint_forward` que preserva latent não-mascarada

**Durante o loop (L548-580):**
- `_process_diffusion()` usa dimensões do crop (width, height do task)
- Latent vazia criada com dims do crop — OK

**Depois do loop (L582-):**
- Chamar `worker.post_process(img)` em cada imagem resultado
- Limpar `modules.inpaint_worker.current_task = None`

#### 1.3 `_process_diffusion()` (L453-495) — Sem alterações

Usa `task["width"]` e `task["height"]` que já vêm do task (agora com dims do crop).

### InpaintHead (Opcional, Melhoria)

O `InpaintHead` CNN (5ch → 320 features) melhora qualidade mas não é obrigatório.
- `worker.patch()` precisa do path pro checkpoint do InpaintHead e do model
- Pode ser adicionado depois se necessário

### Riscos

| # | Risco | Mitigação |
|---|---|---|
| 1 | Dimensões do crop < 512 | InpaintWorker faz upscale se < 1024 |
| 2 | VAE encode falha | try/except, fallback sem latent masking |
| 3 | Memória GPU | Crop menor = menos VRAM que imagem inteira |
| 4 | `modules/compatibilidade` | Usar `modules/inpaint_worker.py` (legacy) que é testado |

---

## Fase 2: Fix SE11 — Params corretos

### Arquivo: `services/se11-clothes-removal/app/infrastructure/http_client.py`

#### 2.1 Calcular aspect ratio da imagem

Decodificar image_b64 → PIL → w,h → escolher SDXL ratio mais próximo.

SDXL ratios suportados:
```
704*1408, 704*1344, 768*1344, 768*1280, 832*1216, 832*1152,
896*1152, 896*1088, 960*1088, 960*1024, 1024*1024, 1024*960,
1088*960, 1088*896, 1152*896, 1152*832, 1216*832, 1280*768,
1344*768, 1344*704, 1408*704, 1472*704, 1536*640, 1600*640,
1664*576, 1728*576
```

#### 2.2 Enviar `advanced_params` sempre

```python
payload["advanced_params"] = {
    "inpaint_engine": "v2.6",
    "inpaint_strength": inpaint_strength,
    "inpaint_respective_field": 0.8,
    "inpaint_disable_initial_latent": False,
}
```

#### 2.3 Simplificar styles

Remover `Fooocus Enhance` e `Fooocus Sharp`:
```python
"style_selections": ["Fooocus Inpaint"],
```

#### 2.4 Prompt negativo mais forte

```python
negative_prompt = "deformed, blurry, low quality, extra limbs, disfigured, poorly drawn face, watermark, text"
```

---

## Ordem de Execução

1. Criar PLAN.md (este arquivo)
2. Fase 1: Modificar `worker.py` do SE8
3. Fase 1: Testar SE8 isoladamente (POST /v1/generation/image-inpaint-outpaint)
4. Fase 2: Modificar `http_client.py` do SE11
5. E2E test: SE11 → SE10 → SE8 com Test.png
6. Rebuild Docker SE8 + SE11
7. Atualizar MEMORY.md

## Validação

- Criar máscara sintética (retângulo branco) via Python/OpenCV
- Testar SE8 direto: POST image + mask → output preserva fundo
- Testar SE11 completo: imagem → SE10 → SE8 → resultado
