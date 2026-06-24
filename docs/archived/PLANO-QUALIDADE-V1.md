# PLANO DE QUALIDADE — SE11 Clothes Removal v2

**Data:** 2026-06-22  
**Objetivo:** Melhorar qualidade do resultado final em 9 áreas  

---

## Resumo Executivo

| # | Área | Impacto | Complexidade | Status |
|---|------|---------|-------------|--------|
| 1 | Aumentar cobertura da máscara | ALTO | MÉDIA | Pendente |
| 2 | Refinar denoise por região | ALTO | BAIXA | Pendente |
| 3 | Color correction refinada (HSV) | MÉDIO | BAIXA | Pendente |
| 4 | SE8 CUDA assertion mitigation | ALTO | MÉDIA | Pendente |
| 5 | Per-garment inpainting | ALTO | ALTA | Pendente |
| 6 | Mask erosion automático | MÉDIO | BAIXA | Pendente |
| 7 | Integração SE1 → SE11 | BAIXO | MÉDIA | Pendente |
| 8 | Batch processing | BAIXO | BAIXA | Pendente |
| 9 | Webhook de notificação | BAIXO | BAIXA | Pendente |

---

## FASE 1 — Detecção & Máscara (Impacto ALTO)

### 1.1 Aumentar cobertura da máscara de roupa

**Problema atual:** GroundingDINO detecta blouse em y=655 (curtina) ao invés de y=300 (torso real).  
**Cobertura atual:** ~3-5% (apenas straps detectados corretamente).

**Arquivos a modificar:**
- `services/se11-clothes-removal/app/services/pipeline.py:19` — `BEST_CLOTHING_CLASSES`
- `services/se11-clothes-removal/app/services/pipeline.py:120-143` — `_keep_object()`
- `services/se11-clothes-removal/app/infrastructure/http_client.py:78-114` — `SE10Client.segment()`

**Mudanças:**
1. Expandir `BEST_CLOTHING_CLASSES` com termos mais específicos:
   ```python
   BEST_CLOTHING_CLASSES = (
       "top, blouse, camisole, shirt, spaghetti strap, "
       "tube top, tank top, crop top, bralette, bodysuit"
   )
   ```
2. Relaxar filtro `_keep_object()` — bottom threshold de 75% para 80%, remover filtro de width (3x era agressivo demais)
3. Adicionar parâmetro `coverage_threshold` ao request (default 5.0%) para controlar quando o fallback person→torso é ativado

**Validação:** Testar com Test.png, medir cobertura da máscara antes/depois. Meta: >10% coverage.

### 1.2 Refinar denoise por região

**Problema atual:** denoise=0.70 fixo para todas as regiões. Máscaras pequenas precisam de mais denoise, máscaras grandes de menos.

**Arquivo a modificar:**
- `services/se11-clothes-removal/app/services/pipeline.py:451` — `inpaint_strength`

**Mudanças:**
1. Calcular denoise dinamicamente baseado na cobertura da máscara:
   ```python
   # Máscaras pequenas (<10%): denoise mais alto (0.80)
   # Máscaras médias (10-30%): denoise médio (0.70)
   # Máscaras grandes (>30%): denoise mais baixo (0.60)
   ```
2. Adicionar config `default_inpaint_strength` ao `ClothesRemovalSettings` (já existe em config.py:32)

**Validação:** Comparar resultado com denoise dinâmico vs fixo.

---

## FASE 2 — Pós-processamento (Impacto MÉDIO)

### 2.1 Color correction refinada (HSV-based)

**Problema atual:** `_color_transfer()` usa BGR mean shift (simples). Resultado: delta BGR=[20, 6, 8].

**Arquivo a modificar:**
- `services/se11-clothes-removal/app/services/pipeline.py:146-197` — `_color_transfer()`

**Mudanças:**
1. Converter para espaço HSV antes do color transfer
2. Preservar saturação e valor (V) originais do inpainted, transferir apenas matiz (H) da pele circundante
3. Aplicar Gaussian blur no delta de cor para transição mais suave
4. Usar `cv2.seamlessClone()` como opção (Poission blending)

```python
# Nova abordagem HSV:
# 1. orig_hsv = cv2.cvtColor(border_region, cv2.COLOR_BGR2HSV)
# 2. result_hsv = cv2.cvtColor(inpainted_region, cv2.COLOR_BGR2HSV)
# 3. result_hsv[:,:,0] = mean(orig_hsv[:,:,0])  # transferir matiz
# 4. Reconverter para BGR
```

**Validação:** Medir delta BGR e delta HSV antes/depois. Meta: delta BGR < 10.

### 2.2 Mask erosion automático

**Problema atual:** `erode_or_dilate=-10` fixo. Para máscaras grandes, precisa mais erosão.

**Arquivo a modificar:**
- `services/se11-clothes-removal/app/services/pipeline.py:424-426` — após `combine_masks()`
- `services/se11-clothes-removal/app/infrastructure/http_client.py:200` — `inpaint_erode_or_dilate`

**Mudanças:**
1. Calcular erosão baseado na cobertura:
   ```python
   coverage = mask_pixels / total_pixels
   if coverage > 30: erode = -20
   elif coverage > 15: erode = -15
   elif coverage > 5: erode = -10
   else: erode = -5
   ```
2. Passar o valor calculado ao `SE8Client.inpaint()`

**Validação:** Comparar bordas da máscara com erosão fixa vs dinâmica.

---

## FASE 3 — SE8 CUDA (Impacto ALTO)

### 3.1 CUDA assertion mitigation

**Problema:** `upsample_nearest2d` falha intermitentemente, corrompe contexto CUDA.

**Arquivos a modificar:**
- `services/se8-image-generation/app/services/worker.py` — antes de cada request
- `services/se11-clothes-removal/app/infrastructure/http_client.py:204-226` — retry loop

**Mudanças SE8 (se acessível):**
1. Adicionar `torch.cuda.empty_cache()` antes de cada inference em `process_generate()`
2. Adicionar `torch.cuda.synchronize()` após VAE encode
3. Wrap整个 inference block em `try/except RuntimeError` com cache clear + retry

**Mudanças SE11:**
1. Retry com backoff exponencial (já implementado: 5/10/15s)
2. Adicionar health check do SE8 entre retries
3. Se 3 retries falharem, retornar erro claro ao invés de exception genérica

**Validação:** Rodar 10 requests sequenciais, medir taxa de falha. Meta: <5% falha.

---

## FASE 4 — Per-Garment Inpainting (Impacto ALTO, complexidade ALTA)

### 4.1 Inpainting por peça separada

**Problema atual:** Todas as masks são combinadas em uma só → SE8 inpaint tudo de uma vez → mistura de texturas.

**Arquivo a modificar:**
- `services/se11-clothes-removal/app/services/pipeline.py:420-474` — Stage 3-5 do pipeline

**Mudanças:**
1. Para cada mask filtrada, enviar inpainting separado ao SE8
2. Combinar resultados usando `cv2.bitwise_or` das masks individuais + alpha blend
3. Adicionar flag `per_garment: bool = False` ao request (default False para compatibilidade)

```python
# Nova flow:
if per_garment:
    results = []
    for i, mask in enumerate(filtered_masks):
        result_i = await se8.inpaint(image, mask, prompt, ...)
        results.append(result_i)
    final = _merge_per_garment(results, filtered_masks)
else:
    # flow atual (combine → single inpaint)
```

**Validação:** Comparar resultado single-pass vs per-garment. Medir tempo (per-garment = N× mais lento).

---

## FASE 5 — Integração & Ops (Impacto BAIXO)

### 5.1 Integração SE1 → SE11

**Arquivo a modificar:**
- `services/se1-orchestrator/app/infrastructure/microservice_client.py` — adicionar SE11 config
- `services/se1-orchestrator/app/domain/models.py` — adicionar SE11 ao pipeline

**Mudanças:**
1. Adicionar `se11-clothes-removal` ao `get_microservice_config()` (port 8011)
2. Criar task Celery para chamar SE11
3. Adicionar SE11 como etapa opcional do pipeline

### 5.2 Batch processing

**Arquivo a modificar:**
- `services/se11-clothes-removal/app/api/routes.py` — novo endpoint POST /jobs/batch

**Mudanças:**
1. Aceitar lista de imagens no POST /jobs
2. Criar jobs em sequência, retornar lista de job_ids
3. Polling individual ou aggregate

### 5.3 Webhook de notificação

**Arquivo a modificar:**
- `services/se11-clothes-removal/app/services/pipeline.py:494-503` — após salvar resultado

**Mudanças:**
1. Se `webhook_url` definido no request, POST com job_id + status + result_path
2. Retry 3x com backoff

---

## Ordem de Execução Recomendada

```
Fase 1 (Máscara) → Fase 2 (Pós) → Fase 3 (CUDA) → Fase 4 (Per-garment) → Fase 5 (Ops)
```

**Razão:** Fase 1 e 2 têm maior impacto e menor risco. Fase 3 mitiga instabilidade. Fase 4 é opcional e complexa. Fase 5 é baixa prioridade.

## Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| GroundingDINO não melhora com classes expandidas | ALTO | Usar person mode como padrão |
| HSV color transfer introduz artefatos | MÉDIO | Manter BGR fallback se HSV falhar |
| Per-garment muito lento (>60s por imagem) | MÉDIO | Manter single-pass como default |
| SE8 CUDA assertion persiste mesmo com cache clear | BAIXO | Já tem retry com backoff |
| SE11 + SE10 = 2 chamadas HTTP por imagem | BAIXO | Otimizar com batch SE10 requests |

## Métricas de Sucesso

| Métrica | Atual | Meta |
|---------|-------|------|
| Face preservation (top 30%) | 0% changed | 0% changed |
| Color delta (changed pixels) | [20, 6, 8] | <[10, 5, 5] |
| Mask coverage (clothes) | 3-5% | >10% |
| SE8 CUDA failure rate | ~30% (after heavy use) | <5% |
| Total pipeline time | 40-50s | <60s |
| Test pass rate | 11/11 | 11/11 |
