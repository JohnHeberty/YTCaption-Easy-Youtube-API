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

## Lições Aprendidas (NÃO repetir)

### ❌ O que NÃO funciona
1. **2-pass (denoise 0.50)** — regenera conteúdo em vez de refinar, causa blobs cinza
2. **HSV color correction** — causa artefactos vermelhos mesmo com feathering, muito agressivo
3. **cv2.seamlessClone MIXED_CLONE** — traz roupa de volta porque preserva gradientes do destino
4. **2-pass (denoise 0.30-0.35)** — mesmo problema, regenera em vez de polir
5. **head_mask 40% fixo** — protege alças no ombro que deveriam ser inpaintadas

### ✅ O que FUNCIONA
1. **1 pass (0.75)** — gera NSFW com enough quality
2. **GaussianBlur collage (31+15px)** — colagem suave, fundo preservado
3. **Reinhard LAB color transfer** — matching de tonalidade em Luminance+Chroma (melhor que HSV)
4. **7% adaptive dilation** — clothing exact + dilatação proporcional
5. **Prompt NSFW×5** — força geração explícita
6. **NsfwPov 0.2** (não 0.7) — peso baixo funciona melhor
7. **clothing_all = person AND clothes** — inclui alças no head zone
8. **face_only = head MINUS clothes** — protege só a face real, não alças

### 🔬 Porquê cada falha
- **2-pass 0.50:** O sigma schedule a 50% significa que o modelo começa com 50% noise — gera conteúdo novo em vez de refinar o existente
- **HSV correction:** Apenas ajusta Hue e Saturation, ignora Luminance — causa desequilíbrio de brilho
- **seamlessClone:** resolve gradientes (bordas) mas adapta a cor do source ao destination — como destination tem roupa, os gradientes da roupa são preservados
- **HSV feathered:** O delta acumula ao longo de toda a máscara, causando oversaturation nas bordas

### 📏 Parâmetros óptimos descobertos
| Parâmetro | Valor óptimo | Porquê |
|-----------|-------------|--------|
| denoise | 0.75 | Balance entre criatividade e preservação |
| dilatação | 7% da bbox | Adapta a qualquer resolução |
| GaussianBlur | 31px + 15px | Duplo blur = transição suave |
| NsfwPov weight | 0.2 | 0.7+ causa CUDA assertion |
| CFG | 4.0 | Default Fooocus funciona melhor |
| sharpness | 2.0 | Default Fooocus funciona melhor |
| base model | juggernautXL | Melhor que lustify para NSFW |

---

## V3 Mask Logic (implementado, não testado)

### Problema que resolve
As alças da roupa ficam no ombro (zona head 40%) → excluídas do clothing_exact → ficam na imagem final.

### Nova lógica
```python
# ANTES:
clothing_exact = body AND NOT exposed_skin  # alças excluídas!
head_force = head_mask (40%)                # protege alças!

# V3:
clothes_on_person = person AND clothes      # TODA roupa (body + head zone)
face_only = head_mask AND NOT clothes       # só face (não alças!)
inpaint = clothes_on_person                 # alças incluídas!
head_force = face_only                      # protege só face
```

### Resultado esperado
| | Actual | V3 |
|---|---|---|
| Clothing exact | 15.5% (body only) | **19.6% (all clothing)** |
| Face protegida | 10.6% (full head) | **6.5% (face only)** |
| Alças no ombro | ❌ Excluídas | ✅ **Incluídas no inpaint** |
| Straps in head zone | 0% | **4.1%** |
