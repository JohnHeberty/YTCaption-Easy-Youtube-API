# PLAN-1.md — Corrigir Máscara: Clothing Exact + Dilatação 20px

**Data:** 2026-06-23
**Status:** ✅ TESTE CONCLUÍDO — RESULTADO SUPERIOR AO v15

---

## Resultado do Teste (2026-06-23)

| Métrica | v15 (body mask 16px) | PLAN-1 (clothing 20px) | Vencedor |
|---------|---------------------|----------------------|----------|
| Área inpaint | ~40% | ~25-30% | ✅ PLAN-1 |
| Seios | Correctos mas com artefactos | Mais definidos, naturais | ✅ PLAN-1 |
| Pele ombros/braços | Regenerada (inconsistências) | Preservada (original) | ✅ PLAN-1 |
| Mamilos | Ligeiramente errados | Melhor posição | ✅ PLAN-1 |
| Transição | Média (pele regenerada) | Suave (20px margem) | ✅ PLAN-1 |
| Rostos/boca | Mancha escura | Mancha escura (mantida) | Empate |
| Roupa residual | Nenhuma | Nenhuma | Empate |

**Conclusão:** PLAN-1 é **claramente superior** ao v15. Recomenda-se implementar em produção.
**Objetivo:** Voltar a clothing exact com dilatação maior para melhorar realismo

---

## Problema Actual (v15)

`body_mask` como inpaint gera ~40% de máscara — modelo regenera pele onde já existe pele (braços, ombros, pescoço), causando inconsistências e reduzindo qualidade.

A máscara ideal é a **roupa exacta** com dilatação suficiente para cobrir bordas e dar margem ao modelo gerar transição suave.

---

## Solução

Voltar a `clothing_exact` (body AND NOT exposed_skin) com dilatação **20px** (em vez de 12px antigo ou 16px do body_mask).

```
ANTES (v14): inpaint_mask = dilate(clothing_exact, 12px) → ~20% (pouco espaço)
ANTES (v15): inpaint_mask = dilate(body_mask, 16px) → ~40% (demais)
NOVO (v16):  inpaint_mask = dilate(clothing_exact, 20px) → ~25-30% (sweet spot)
```

---

## Mudanças

### Arquivo: `pipeline.py`

**Linha ~1996-1998:**
```python
# ANTES (v15):
kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (16, 16))
inpaint_mask = _cv2.dilate(body_mask, kernel, iterations=2)

# NOVO (v16):
kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (20, 20))
inpaint_mask = _cv2.dilate(clothing_exact, kernel, iterations=2)
```

### Comentário actualizado:
```python
# v16: clothing exact dilatado 20px — roupa + margem para transição
```

---

## Porquê 20px?

| Dilatação | Área | Resultado |
|-----------|------|-----------|
| 12px (v14) | ~20% | Seios errados (espaço pequeno) |
| 16px body (v15) | ~40% | Regenera pele existente |
| **20px clothing (v16)** | **~25-30%** | **Sweet spot: roupa + bordas suaves** |

- **25-30%** é mais que os 20% originais (resolve seios errados)
- **25-30%** é menos que os 40% do body_mask (não regenera pele existente)
- Bordas incluem pele circundante → transição natural

---

## Resultado Esperado

| Métrica | v15 (body mask) | v16 (clothing 20px) |
|---------|----------------|---------------------|
| Área inpaint | ~40% | ~25-30% |
| Seios | Correctos mas com inconsistências | Correctos + definidos |
| Pele existente | Regenerada (piora) | Preservada (melhora) |
| Transição | Média | Suave (20px margem) |

---

## Teste

```bash
# Comparar v15 vs v16 na mesma Test.png
docker restart se11-clothes-removal
# Testar com mode="nsfw"
# Comparar 06_inpaint_mask.png entre versões
```
