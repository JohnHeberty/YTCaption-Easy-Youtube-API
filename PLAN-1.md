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

## Próximos passos

- **PLAN-2:** Detecção adaptativa de cabeça (substituir 40% fixo por haarcascade)
- **Promoção para produção:** quando PLAN-2 estiver pronto, unificar nsfw_test → nsfw
- **Testing com mais imagens:** diferentes poses, roupas, resoluções
