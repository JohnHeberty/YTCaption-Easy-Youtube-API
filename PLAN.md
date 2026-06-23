# PLAN.md — Pipeline NSFW 3-Camadas: Roupas → Pele Preservando Pessoa

**Data:** 2026-06-23  
**Status:** pipe_3layers_max funcional — Investigação de skin color reference  
**Objetivo:** Remoção 100% de roupa com preservação ABSOLUTA de rosto, cabeça, cabelo e fundo + pele realista

---

## Estado Atual — pipe_3layers_max v4

| Métrica | Resultado |
|---------|-----------|
| Face SSIM | **1.000** ✅ |
| Face diff | **0.00** ✅ |
| BG diff | **0.00** ✅ |
| Torso | 32.4% |
| Bot | 72.1% |
| Head cutoff | 40% (com dilatação para cabelo) |

**Rota:** `POST /jobs {"image": "<base64>", "mode": "pipe_3layers_max"}`

### Pipeline atual
```
1. SE10 detecta pessoa → person_mask
2. Body = pessoa - head(40%) com dilatação para cabelo
3. SE8 LUSTIFY NSFW 2-pass no corpo inteiro
4. Force head+cabeça = original
5. HSV color transfer + morfologia + bilateral
```

---

## Próximo: Skin Color Reference (Pele como Referência)

### Problema
O modelo NSFW gera pele genérica — pode ter tom diferente da pessoa original porque não sabe qual cor de pele gerar. O prompt "natural skin" é genérico demais.

### Solução: Usar pele exposta como referência

#### Diagrama
```
IMAGEM ORIGINAL
    │
    ├── person_mask (pessoa inteira)
    ├── head_mask (rosto + cabeça + cabelo)
    ├── body_mask = person - head (corpo)
    ├── clothes_mask (Florence-2 detecta roupa)
    │
    ├── exposed_skin = body_mask AND NOT clothes_mask
    │   → braços, pernas, pescoço = PELE EXPOSTA
    │
    └── effective_mask = clothes_mask AND body_mask
        → onde vai发生 INPAINTING
```

#### O que a pele exposta diz ao modelo
- **Tom exato** da pele (HSV mediana da pele exposta)
- **Textura** da pele (poros, brilho, sombreamento)
- **Iluminação** (onde a luz bate na pele)
- **Transição** entre pele existente e área mascarada

#### Implementação

**Etapa extra: Extrair cor da pele exposta**
```python
exposed_skin = bitwise_and(body_mask, not clothes_mask)
skin_pixels = original_hsv[exposed_skin > 0]
median_h = np.median(skin_pixels[:, 0])
median_s = np.median(sin_pixels[:, 1])
median_v = np.median(skin_pixels[:, 2])
```

**Usar no prompt do SE8**
```python
prompt = f"natural skin tone hue={median_h:.0f} saturation={median_s:.0f}, " \
         f"matching the skin on the person's arms and body, seamless blend"
```

**Usar no color transfer pós-inpainting**
```python
# Em vez de border do mask, usar exposed_skin como referência
_color_transfer_with_reference(result, original, exposed_skin_mask)
```

### Mudanças no pipeline

| Etapa | Atual | **Novo** |
|-------|-------|---------|
| Detectar pele exposta | ❌ Não faz | **✅ exposed_skin = body AND NOT clothes** |
| Extrair cor da pele | ❌ Não faz | **✅ median HSV de exposed_skin** |
| Prompt do SE8 | Genérico ("natural skin") | **Específico ("hue=X, sat=Y")** |
| Color transfer | Border do mask | **Referência de exposed_skin** |

### Arquivos a modificar

| Arquivo | Mudança |
|---------|---------|
| `pipeline.py` | Nova etapa: extrair exposed_skin + cor → prompt + color_transfer |

### Ordem de implementação

1. Adicionar extração de exposed_skin no pipeline
2. Calcular mediana HSV da pele exposta
3. Incluir no prompt do SE8
4. Usar exposed_skin como referência para color_transfer
5. Testar e comparar com pipe_3layers_max v4
6. Commit + push

### Risco
- **BAIXO** — é adição de cor ao prompt (não muda lógica)
- **BAIXO** — color transfer mais preciso (referência real vs border genérica)
- **MÉDIO** — se exposed_skin é pequeno (pessoa sem pele exposta), referência fraca
