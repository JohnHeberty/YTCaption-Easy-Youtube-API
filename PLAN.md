# PLAN.md — Otimização NSFW: pipe_3layers_max v10

**Data:** 2026-06-23  
**Status:** v10 funcional — `inpaint_additional_prompt` ativo, pele gerada no peito mas cor inconsistente  
**Objetivo:** Usar parâmetros corretos do Fooocus para gerar pele realista

---

## Estado Actual (v9)

- **Máscara:** CLOTHING EXATA (~20%) — PERFEITA ✅
- **Face:** 100% preservada (SSIM=1.000) ✅
- **BG:** 100% preservado (diff=0.00) ✅
- **Bordas:** Suaves (bilateral + Gaussian blend) ✅
- **Problema:** Textura da roupa ainda visível — padrão floral parcialmente mantido
- **Causa raiz:** Configurações Fooocus incorrectas (descobertas em pesquisa profunda)

---

## Descoberta Crítica: Configurações Fooocus

### Como o Fooocus Inpaint funciona internamente

```
1. fooocus_fill() → blur multi-escala preenche máscara com cor média
2. InpaintHead CNN → 5 canais (4 latent + 1 mask) → 320 features ao UNet
3. patched_KSampler → mistura latent fill + noise na máscara durante sampling
4. post_process() → alpha blend + color correction nas bordas
```

### Parâmetros que NÃO estávamos a usar correctamente

| Parâmetro | O que faz | Actual | Correcto |
|-----------|-----------|--------|----------|
| `inpaint_additional_prompt` | Guia ESPECÍFICO para a região mascarada | **VAZIO!** | `"bare skin, naked body..."` |
| `inpaint_respective_field` | Tamanho do crop (0=apenas máscara, 1=imagem toda) | **0.85-0.90** | **0.618** (default) |
| `inpaint_strength` pass 3 | Denoising da 3ª pass | **0.35** (muito baixo) | **0.50** |
| `prompt` (principal) | Guia geral da imagem | NSFW explícito | `"natural photo, soft lighting"` |

### Porquê o `inpaint_additional_prompt` é CRÍTICO

O Fooocus tem **DOIS** prompts separados:
1. **`prompt`** — guia o CLIP encoding para a imagem **inteira** (contexto geral)
2. **`inpaint_additional_prompt`** — guia **específico** para o que gerar **dentro da máscara**

Nós mandamos tudo no `prompt` principal. O `inpaint_additional_prompt` está VAZIO.
Isto significa que o modelo sabe onde está a máscara mas **não sabe o que queremos gerar ali**.

### Porquê `inpaint_respective_field=0.85-0.90` é mau

- 85-90% da imagem entra no crop → modelo vê **toda** a imagem
- Modelo pode "copiar" conteúdo de outras áreas em vez de gerar pele nova
- Default Fooocus é 0.618 (golden ratio) — foco adequado na máscara
- Com clothing mask ~20%, 0.618 dá contexto suficiente sem distrair

---

## Plano de Optimização — v10 (5 mudanças)

### 1. `inpaint_additional_prompt` ← O MAIS IMPORTANTE
- **Onde:** `http_client.py` — payload
- **Mudança:** Adicionar campo `inpaint_additional_prompt` com NSFW explícito
- **Prompt:** `"bare skin, no clothing, naked body, natural realistic skin texture, seamless transition with surrounding skin"`
- **Porquê:** Diz ao Fooocus EXATAMENTE o que gerar na máscara

### 2. Separar prompts: geral vs inpaint
- **`prompt`** (principal): `"natural photo, soft lighting, professional photography"` — contexto geral
- **`inpaint_additional_prompt`**: `"bare skin, naked body, hue=X sat=Y..."` — guia para a máscara
- **Porquê:** Cada prompt serve para um propósito diferente no Fooocus

### 3. `inpaint_respective_field` de 0.85→0.618
- **Onde:** `http_client.py` — payload
- **Mudança:** Todos os passes usam 0.618 em vez de 0.85-0.90
- **Porquê:** Foco na máscara, menos distração do contexto

### 4. `inpaint_strength` ajustado
- **Pass 1:** 0.75 → manter (remoção principal)
- **Pass 2:** 0.45 → **0.50** (mais creative freedom)
- **Pass 3:** 0.35 → **0.50** (mais tempo para gerar textura)
- **Porquê:** 0.35 é tão baixo que o modelo mal gera nada novo

### 5. Prompt principal não-NSFW
- **Actual:** `"bare skin, naked body..."` (NSFW no prompt geral)
- **Novo:** `"natural photo, soft lighting, professional photography"`
- **Porquê:** O prompt geral guia o CLIP para toda a imagem — não precisa de NSFW

---

## Fluxo Resultante (v10)

```
1. SE10 detecta pessoa → person_mask
2. Body = pessoa - head(40%)
3. Exposed skin + clothing exact (MANTIDO)
4. SE8 LUSTIFY NSFW 3-pass:
   - Pass 1: denoise 0.75, field=0.618
   - Pass 2: denoise 0.50, field=0.618
   - Pass 3: denoise 0.50, field=0.618
   - prompt: "natural photo, soft lighting"
   - inpaint_additional_prompt: "bare skin, naked body, hue=X sat=Y..."
   - LoRAs: NsfwPov 0.7 + offset 0.1 + detail 0.8
   - GPU cooldown: 5s entre passes
5. Force head = original
6. Color transfer + morfologia + bilateral + Gaussian blend
7. Debug: 8 masks sequenciais (00-07)
```

---

## Arquivos a Modificar

| Arquivo | Mudanças |
|---------|----------|
| `http_client.py` | Adicionar `inpaint_additional_prompt` ao payload |
| `pipeline.py` | Separar prompts, ajustar denoise, ajustar field |

---

## Referência Técnica Fooocus

| Parâmetro | Default | Nós (v9) | Nós (v10) |
|-----------|---------|----------|-----------|
| inpaint_engine | v2.6 | v2.6 ✅ | v2.6 ✅ |
| inpaint_strength | 1.0 | 0.75/0.45/0.35 | 0.75/0.50/0.50 |
| inpaint_respective_field | 0.618 | 0.85/0.90 | **0.618** |
| inpaint_disable_initial_latent | False | False ✅ | False ✅ |
| inpaint_erode_or_dilate | 0 | -8/-5/-3 | -8/-5/-3 |
| use_fill | True | True ✅ | True ✅ |
| inpaint_additional_prompt | "" | **VAZIO ❌** | **"bare skin..." ✅** |
| overwrite_step | 30 | 30 | 30 |

---

## Resultados Esperados v10

| Métrica | v9 actual | v10 esperado | Meta |
|---------|-----------|-------------|------|
| Face SSIM | 1.000 | 1.000 | 1.000 |
| BG diff | 0.00 | 0.00 | 0.00 |
| Body generation | Padrão floral visível | Pele realista | Matching arms |
| Transição | Bordas laranja | Invisível | Perfeita |
| Tempo | ~120s | ~120s | <120s |

---

## Passos de Implementação

1. Atualizar `http_client.py`:
   - Adicionar `inpaint_additional_prompt` ao payload
   
2. Atualizar `pipeline.py`:
   - Separar prompt geral (não-NSFW) do inpaint_additional_prompt (NSFW)
   - Ajustar denoise passes 2 e 3 para 0.50
   - Manter field=0.618 em todos os passes
   
3. Reiniciar SE11 + SE8 + testar com Test.png
   
4. Comparar v9 vs v10
   
5. Commit + push + documentação
