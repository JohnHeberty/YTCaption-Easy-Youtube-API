# INVESTIGATE.md — Análise Técnica: Bordas nos Ombros

**Data:** 2026-06-24
**Pipeline:** `_run_nsfw_test()`
**Problema:** Bordas cinza/brancas visíveis nos ombros + roupa antiga a aparecer

---

## Fluxo Actual do Pipeline

```
1. person_mask → person_binary (> 127 threshold)
2. head_mask → top 40% bbox AND person_binary → dilate(15px, 2 iter) → AND person_binary
3. body_mask = person_binary AND NOT head_mask
4. clothes_combined → exposed_skin = body AND NOT clothes
5. body_closed = body_mask (copy)
6. head_mask = close + floodFill (100% sólido)
7. inpaint_mask = body_closed (binary)
8. head_adjusted = head_mask AND NOT body_closed
9. SE8 inpaint (erode_or_dilate=-8, field=0.85, strength=0.80)
10. head_adjusted force → original
11. Reinhard LAB color transfer
12. Compositing: orig_img[body_bin] = color_corrected[body_bin]
13. head_adjusted force → original (final)
```

---

## Causas Identificadas

### Causa 1: `inpaint_erode_or_dilate=-8` (CRÍTICO)

**Linha 2307:**
```python
result1 = await se8.inpaint(
    ...
    inpaint_erode_or_dilate=-8,
    ...
)
```

**O que faz:** O SE8 aplica erosão de 8px na máscara ANTES de gerar. Isto significa que o SE8 **não gera NSFW** numa faixa de 8px em todo o contorno da body_mask. Nessa faixa, a imagem original fica — incluindo roupa antiga, bordas cinza.

**Efeito visual:** Bordas cinza/brancas em todo o contorno da máscara.

**Correcção:** Trocar para `0` (sem erosão) ou `-2` (mínimo).

---

### Causa 2: head_mask dilatado 15px (IMPORTANTE)

**Linha 2212:**
```python
head_mask = _cv2.dilate(head_mask, _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15)), iterations=2)
```

**O que faz:** O head_mask é dilatado com kernel 15px, 2 iterações = ~30px para todos os lados. Isto empurra o limite da cabeça para baixo, sobrepondo-se aos ombros.

**Efeito visual:** O body_mask exclui a zona onde head_mask sobrepõe → gap nos ombros → roupa antiga visível.

**Correcção:** Reduzir dilatação para `(7,7)` ou `(5,5)` ou remover entirely.

---

### Causa 3: Boundary head/body nos ombros

**O que acontece:**
```
head_mask (dilatado 30px)
    └→ sobrepõe ombro (dilatação empurra para baixo)
        └→ body_mask = person AND NOT head (exclui essa zona)
            └→ SE8 não gera NSFW nessa faixa (erode -8px)
                └→ result: roupa original aparece nos ombros
```

**Correcção:** Resolvida com correcções #1 e #2.

---

## Código Afectado

| Linha | Código Actual | Correcção |
|-------|---------------|-----------|
| 2212 | `dilate(head_mask, (15,15), 2 iter)` | `(7,7)` ou `(5,5)` |
| 2307 | `inpaint_erode_or_dilate=-8` | `0` ou `-2` |

---

## Prioridade

1. **CRÍTICO:** `inpaint_erode_or_dilate=-8` → `0` (causa directa das bordas)
2. **IMPORTANTE:** head_mask dilation `(15,15)` → `(7,7)` (causa gaps nos ombros)
3. **MENOS:** boundary head/body (resolve-se com #2)

---

## Resultado Esperado

Com estas correcções:
- Sem bordas cinza/brancas no contorno da máscara
- Sem gaps nos ombros (head/body boundary mais limpo)
- Roupa antiga não aparece nas bordas
- SE8 gera NSFW exactamente até ao limite da máscara
