# INVESTIGATE.md — Bordas Serrilhadas no Resultado Final

**Data:** 2026-06-24
**Status:** Novo erro — bordas serrilhadas na composição
**Resolução anterior:** erode_or_dilate=0 + 3% expansion ✅ (já resolvido)

---

## Problema Actual

A máscara binária do person_mask (threshold > 127) gera bordas serrilhadas no resultado final. Mesmo com dilatação 3%, o contorno segue os pixels ásperos da detecção.

**O que está correcto:**
- ✅ erode_or_dilate=0 (SE8 gera até ao limite exacto)
- ✅ body_expanded 3% (expansão correcta)
- ✅ head 100% sólido
- ✅ Sem bordas cinza (problema resolvido)

**O que falta:**
- ❌ Bordas serrilhadas na transição body→fundo

---

## Opções de Correcção

### Opção A: Suavização PÓS-compositing (RECOMENDADA)
Após colar o resultado NSFW, detectar as bordas do body_expanded e aplicar bilateral filter APENAS nesses pixels.

```
Composição → Canny edge no body_expanded → dilate 3px → bilateral filter → resultado final
```
- Não toca na máscara nem no SE8 — affecta só o output
- ~5ms de custo
- Implementação: `_cv2.bilateralFilter(composited, 5, 50, 50)[edge_mask]`

### Opção B: GaussianBlur MÍNIMO na máscara (3px)
Re-introduzir GaussianBlur com kernel mínimo (3px) na máscara antes de enviar ao SE8.

```
body_expanded → GaussianBlur(3px) → SE8
```
- SE8 vê bordas suaves → gera transições mais naturais
- Risco: efeito pode ser mínimo com kernel tão pequeno

### Opção C: Morphological Opening na máscara
Abrir a máscara (erode + dilate com ellipse 3px) para suavizar cantos serrilhados.

```
morphOpen(body_expanded, ellipse 3px) → SE8
```
- Remove pixels isolados e suaviza cantos
- Risco: encolhe ligeiramente a máscara

### Opção D: Distance Transform
Calcular distância de cada pixel à borda → criar gradient alpha na transição.

```
distanceTransform(body_expanded) → normalizar → blend
```
- Transição matemática perfeita
- Complexidade média

---

## Recomendação

**Opção A + Opção C combinadas:**
1. Morphological opening na máscara (suaviza cantos antes do SE8)
2. Após composição, bilateral filter nas bordas (suaviza transição final)

Só toca no output final — não altera máscara do SE8 nem modelo de geração.
