# PLAN.md — Otimização NSFW: pipe_3layers_max v8

**Data:** 2026-06-23  
**Status:** pipe_3layers_max v7 funcional — máscara excelente, inpaint precisa de refinamento  
**Objetivo:** Otimizar geração de corpo/pele na região de roupa removida

---

## Estado Atual (v7)

- **Máscara:** CLOTHING EXATA (~20%) — PERFECTA
- **Face:** 100% preservada (SSIM=1.000)
- **BG:** 100% preservado (diff=0.00)
- **Problema:** SDXL não gera pele realista na região — gera blobs cinza/textura de roupa
- **Causa:** Prompt pouco explícito + steps insuficientes + sem refinamento extra

---

## Plano de Otimização — v8 (4 mudanças)

### 1. lustifySDXLNSFW como Default ✅
- **Onde:** `http_client.py` — SE8Client.inpaint() default parameter
- **Mudança:** `base_model` default de `juggernautXL` → `lustifySDXLNSFW_v20-inpainting.safetensors`
- **Impacto:** TODOS os modos NSFW usam lustify por default (já baixado, 6.9GB)

### 2. Prompt Mais Explícito ✅
- **Onde:** `pipeline.py` — _run_pipe_nsfw_3layers_max()
- **Prompt actual:** `"remove clothing, expose natural skin with hue=X..."`
- **Novo prompt:** `"bare skin, no clothing, naked body, natural realistic skin texture with hue=X saturation=Y, seamless transition with surrounding skin, photorealistic, soft lighting"`
- **Negative:** Manter NSFW_SUBTRACT_NEGATIVE (não bloqueia features corporais)
- **Porquê:** O NSFW_PROMPT tem termos mais explícitos ("naked body", "bare skin") que guiam melhor o modelo

### 3. 3ª Pass Refinamento (denoise 0.3) ✅
- **Onde:** `pipeline.py` — _run_pipe_nsfw_3layers_max()
- **Fluxo:** Pass 1 (0.75) → Pass 2 (0.45) → **Pass 3 (0.30)** ← NOVO
- **Propósito:** Refinar textura de pele, reduzir artefactos, melhorar transição
- **Tempo extra:** ~30s

### 4. Mais Steps (30→50) ✅
- **Onde:** `http_client.py` — payload advanced_params
- **Mudança:** Adicionar `"overwrite_step": 50, "overwrite_switch": 50`
- **Porquê:** Quality=60 steps mas não está wired na API — force via overwrite_step
- **Efeito:** Mais detalhe na geração de pele (~40% mais lento)

---

## Fluxo Resultante (v8)

```
1. SE10 detecta pessoa → person_mask
2. Body = pessoa - head(40%)
3. Exposed skin + clothing exact (MANTIDO)
4. SE8 LUSTIFY NSFW 3-pass:
   - Pass 1: denoise 0.75, steps 50 (remoção principal)
   - Pass 2: denoise 0.45, steps 50 (refinamento)
   - Pass 3: denoise 0.30, steps 50 (textura final)  ← NOVO
   - Prompt: "bare skin, naked body, hue=X sat=Y..."
   - LoRAs: NsfwPov 0.6 + offset 0.1 + detail 0.8
5. Force head = original
6. Color transfer + morfologia + bilateral
7. Debug: 8 masks sequenciais (00-07)
```

---

## Arquivos a Modificar

| Arquivo | Mudanças |
|---------|----------|
| `services/se11-clothes-removal/app/infrastructure/http_client.py` | Default base_model → lustify, add overwrite_step=50 |
| `services/se11-clothes-removal/app/services/pipeline.py` | Novo prompt NSFW, 3ª pass com denoise 0.3 |

---

## Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| 50 steps = ~40% mais lento | ~90s total extra | Aceitável para qualidade |
| 3ª pass pode causar CUDA assertion | Pipeline falha | Retry com backoff |
| Prompt explícito pode gerar indesejados | Resultado ruim | Testar com imagens safe primeiro |
| lustify pode ser mais lento que juggernaut | Latência extra | Já testado, funciona |

---

## O que já funciona bem (MANTIDO)

1. ✅ Preservação de rosto (100%)
2. ✅ Preservação de fundo (100%)
3. ✅ Máscaras precisas — clothing exact (~20%)
4. ✅ Skin color reference (pele exposta como referência)
5. ✅ Debug visualization (8 masks sequenciais 00-07)
6. ✅ Pipeline documentado (TOP-MASK-CONFIG.md v7)
7. ✅ LoRAs optimizados (NsfwPov 0.6 + detail 0.8)

---

## Resultados Esperados v8

| Métrica | v7 actual | v8 esperado | Meta |
|---------|-----------|-------------|------|
| Face SSIM | 1.000 | 1.000 | 1.000 |
| BG diff | 0.00 | 0.00 | 0.00 |
| Body generation | Blobs cinza | Pele realista | Matching arms |
| Transição | Visível | Suave | Invisível |
| Tempo | ~60s | ~90s | <120s |

---

## Passos de Implementação

1. Atualizar `http_client.py`:
   - Default base_model → lustifySDXLNSFW
   - Adicionar overwrite_step=50 no payload
   
2. Atualizar `pipeline.py`:
   - Trocar skin_prompt por NSFW_PROMPT + HSV dinâmico
   - Adicionar Pass 3 (denoise 0.3)
   
3. Reiniciar SE11 + testar com Test.png
   
4. Comparar v7 vs v8 (masks + resultado)
   
5. Commit + push + documentação
