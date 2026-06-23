# PLAN-1.md — nsfw_test: Clothing Exact + Collage + Adaptive Dilation

**Data:** 2026-06-23
**Status:** ✅ TESTE CONCLUÍDO — RESULTADO SUPERIOR AO v15 (não em produção)

---

## Resultado Final do Teste

| Métrica | v15 (produção) | nsfw_test (teste) | Vencedor |
|---------|----------------|-------------------|----------|
| Área inpaint | ~40% (body mask) | ~25-30% (clothing 7%) | ✅ nsfw_test |
| Seios | Correctos mas com artefactos | Mais definidos, naturais | ✅ nsfw_test |
| Pele ombros/braços | Regenerada (inconsistências) | Preservada (original) | ✅ nsfw_test |
| Fundo | Manchado pelo SE8 | 100% preservado (collage) | ✅ nsfw_test |
| Bordas | Color_transfer artifacts | Suave (blur duplo 31+15px) | ✅ nsfw_test |
| Mamilos | Ligeiramente errados | Correctos | ✅ nsfw_test |
| Rostos | Mancha escura (40% fixo) | Mancha escura (mantida) | Empate |
| Tempo | ~60s (1 pass) | ~90s (1 pass + collage) | v15 mais rápido |

---

## O que o nsfw_test faz de diferente

### 1. Clothing exact + 7% adaptive dilation
```python
# Em vez de body_mask (40%):
clothing_exact = body AND NOT exposed_skin  # só roupa (~15%)
dilation_px = int(min(cw, ch) * 0.07)       # 7% da bbox da roupa
inpaint_mask = dilate(clothing_exact, kernel(dilation_px))
# Resultado: ~25-30% da imagem
```

### 2. Collage composition
```python
# Em vez de inpaint_soft blend + color_transfer:
person_soft = GaussianBlur(person_binary, 31px)  # blur grande
person_soft = GaussianBlur(person_soft, 15px)     # blur duplo
composited = inpainted * person_soft + original * (1 - person_soft)
# Resultado: fundo 100% original, pessoa NSFW com bordas suaves
```

### 3. Sem color_transfer, sem edge morphological blend
- Color_transfer degradava as cores da pele gerada
- Edge blend criava artefactos cinza/azul
- Collage com blur duplo resolve tudo

---

## Evolução dos testes nsfw_test

| Iteração | Mudança | Resultado |
|----------|---------|-----------|
| v1 (clothing 20px fixo) | dilate(clothing, 20px) | Seios correctos mas bordas duras |
| v2 (10% adaptive) | 10% da bbox | Dilation 31px — bom mas muito |
| v3 (7% adaptive) | 7% da bbox | Sweet spot — 22px dilation |
| v4 (+ collage) | paste NSFW on original | Fundo 100% preservado ✅ |
| v5 (+ blur duplo) | 31px + 15px Gaussian | Bordas suaves perfeitas ✅ |

---

## Próximos passos — Bordas + Tonalidade

### Problema actual
1. **Bordas visíveis** — GaussianBlur(31+15px) cria transição suave mas ainda visível
2. **Tonalidade diferente** — pele gerada vs pele original (braços, pescoço) tem cor/HSL diferente

### Lições aprendidas (NÃO repetir)
- ❌ 2-pass (denoise 0.50) — regenera conteúdo, causa blobs
- ❌ HSV color correction — causa artefactos vermelhos mesmo com feathering
- ✅ 1 pass (0.75) + collage + blur duplo — melhor combinação actual

### Soluções propostas

#### A. `cv2.seamlessClone` (Poisson blending) — resolve BORDAS
- Poisson equation garante continuidade de gradiente na máscara
- Usa `MIXED_CLONE` — preserva textura interior + adapta cor nas bordas
- Resolution matemática: zero costura visível
- **Cuidado:** falha se máscara toca borda da imagem → fallback Laplacian

#### B. Reinhard Color Transfer (LAB) — resolve TONALIDADE
- Em vez de HSV (só H/S), usa LAB (Luminância + Chroma + cor)
- Match de média + desvio padrão por canal
- Resolve brightness mismatch que HSV ignora
- Aplica ANTES do seamlessClone para melhorar resultado

#### C. Distance Transform Feathering — bordas MAIS precisas
- Em vez de GaussianBlur (transição uniforme), usa distância do boundary
- Feather de 20px EXACTO (não probabilístico)
- Erosão de 5px impede background de vazar para dentro da pessoa

### Pipeline proposto v3
```
1. SE8 Pass 1 (0.75) — gera NSFW
2. Force head = original
3. Reinhard color transfer (LAB) — matching pele NSFW → pele original
4. cv2.seamlessClone MIXED_CLONE — colar pessoa com Poisson blending
5. Force head = original (garantia dupla)
6. Debug masks 00-07
```

### Comparação

| Aspecto | Actual (v2) | Proposto (v3) |
|---------|------------|---------------|
| Bordas | GaussianBlur visível | **seamlessClone invisível** ✅ |
| Tonalidade | Diferente (HSV ignora L) | **Matching exacto (LAB)** ✅ |
| Complexidade | 1 blur | seamlessClone + Reinhard |
| Risco | Nenhum | seamlessClone falha se mask toca borda |

### Referências técnicas
- Perez et al. (SIGGRAPH 2003) — Poisson Image Editing
- Reinhard et al. (SIGGRAPH 2001) — Color Transfer between Images
- OpenCV 4.13.0: `cv2.seamlessClone`, `cv2.cvtColor(BGR2LAB)` — tudo built-in
