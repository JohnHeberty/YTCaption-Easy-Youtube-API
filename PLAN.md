# PLAN.md — Migração Fooocus → SE8/SE11

**Data:** 2026-06-28
**Objetivo:** Elevar qualidade do inpainting SE11 ao nível Fooocus nativo

---

## Visão Geral

O SE8 é um wrapper do Fooocus. Após análise profunda do código Fooocus, identificamos 3 gaps CRÍTICos que explicam a diferença de qualidade entre Fooocus nativo e o pipeline SE11.

---

## Gaps Críticos Identificados

### GAP 1: Inpaint Patch Model NÃO é carregado (CRÍTICO)
- **Fooocus:** Baixa `inpaint_v26.fooocus.patch` e adiciona como LoRA (weight 1.0)
- **SE8:** Apenas carrega `InpaintHead` CNN, NÃO carrega o patch file
- **Impacto:** O patch contém pesos treinados especificamente para inpainting. Sem ele, o InpaintHead sozinho é insuficiente
- **Fix:** Download + carregar via `base_model_additional_loras`

### GAP 2: Dual Latent Encoding ausente (HIGH)
- **Fooocus:** Codifica 2 latents separados: `latent_inpaint` (imagem mascarada + cinza) e `latent_fill` (imagem preenchida)
- **SE8:** Apenas 1 VAE encode de imagem blendada
- **Impacto:** O modelo precisa ver "o que deveria estar lá" (fill) e "o que realmente está lá" (inpaint)

### GAP 3: IP-Adapter / Referência Visual ausente (HIGH)
- **Fooocus:** Suporta IP-Adapter para forçar composição da imagem de referência
- **SE8:** IP-Adapter code existe mas não é usado pelo SE11
- **Impacto:** Sem referência, o modelo gera corpo "genérico" ignorando proporções originais

---

## Prioridades de Implementação

| # | Feature | Effort | Impact | Arquivos |
|---|---------|--------|--------|----------|
| P0 | Load inpaint patch model | Pequeno | CRÍTICO | SE8 worker.py |
| P1 | Dual latent encoding | Médio | HIGH | SE8 worker.py |
| P1 | use_fill condicional | Trivial | MÉDIO | SE8 worker.py |
| P2 | IP-Adapter com original | Médio | HIGH | SE11 pipeline_nsfw.py + http_client.py |
| P2 | Campo menor 0.45 | Trivial | MÉDIO | SE11 pipeline_nsfw.py |
| P2 | CFG 7.0 + morphological fix | Pequeno | MÉDIO | SE8 |
| P3 | fooocus_fill kernel match | Pequeno | BAIXO | SE8 inpaint_worker.py |

---

## Detalhes Técnicos por Feature

### P0: Inpaint Patch Model (Fooocus: async_worker.py:899-901)
```python
# Fooocus faz:
base_model_additional_loras += [(inpaint_patch_model_path, 1.0)]
# SE8 deve fazer o mesmo em _apply_inpaint()
```
Arquivos: `inpaint_v26.fooocus.patch` (download de huggingface.co/lllyasviel/fooocus_inpaint)

### P1: Dual Latent (Fooocus: async_worker.py:500-528)
```python
# Fooocus faz:
latent_inpaint = core.encode_vae_inpaint(vae, pixels, mask)  # blend 0.5 + mask
latent_fill = core.encode_vae(vae, fill_image)              # fooocus_fill result
# SE8 deve implementar encode_vae_inpaint e usar ambos
```

### P2: IP-Adapter (SE11 → SE8)
```python
# SE11 deve enviar original como IP-Adapter ref:
image_prompts = [{
    "cn_img": base64_of_original,
    "cn_stop": 0.5,
    "cn_weight": 0.6,
    "cn_type": "ImagePrompt"
}]
```

### P2: Campo menor
```python
# Reduzir de 0.62 para 0.45:
inpaint_respective_field = 0.45
# Menos crop = menos resize distortion
```

---

## Status

| Item | Status |
|------|--------|
| Análise Fooocus | ✅ Completa |
| Mapeamento de features | ✅ Completo |
| Implementação P0 | 🔄 Em andamento |
| Implementação P1 | ⏳ Pendente |
| Implementação P2 | ⏳ Pendente |
| Testes E2E | ⏳ Pendente |

---

## Referências

| Arquivo Fooocus | Caminho |
|-----------------|---------|
| InpaintWorker | `Fooocus/modules/inpaint_worker.py` |
| Patch (sampling) | `Fooocus/modules/patch.py` |
| Async Worker | `Fooocus/modules/async_worker.py` |
| Pipeline | `Fooocus/modules/default_pipeline.py` |
| Config | `Fooocus/config.py` |
| Models | HuggingFace: lllyasviel/fooocus_inpaint |
