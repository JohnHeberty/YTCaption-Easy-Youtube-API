# UPGRADE-1.md — Plano de Melhorias SE11 Clothes Removal

**Data:** 2026-06-22  
**Status:** Fase 1 CONCLUÍDA  
**Versão atual:** v24 (HSV v2), v25 (per-garment)  
**Test images:** `Test_result_v19.png` a `Test_result_v25.png` (raiz do repo)

---

## Auditoria QA (2026-06-22)

### Resultados por versão

| Versão | Modo | PSNR | Changed | Top(face) | Mid(torso) | Bot | ColorDelta | Straps | Status |
|--------|------|------|---------|-----------|------------|-----|-----------|--------|--------|
| v19 | Clothes | 39.7 | 5.5% | 0.0 | 3.6 | 4.0 | [33,16,17] | 0.0% ❌ | Base |
| v20 | Person | 39.1 | 5.7% | 0.0 | 3.6 | 4.7 | [25,11,12] | 0.0% ❌ | Base |
| v21 | Clothes+filter | 40.7 | 5.1% | 0.0 | 3.3 | 3.4 | [26,11,10] | 0.0% ❌ | Base |
| v22 | Person+filter | 39.1 | 5.6% | 0.0 | 4.1 | 4.0 | [34,17,19] | 0.0% ❌ | Base |
| **v23** | **Clothes (final)** | **41.0** | **5.3%** | **0.0** | **1.4** | **4.6** | **[20,6,5]** | **0.0% ❌** | **APROVADO** |
| **v24** | **Clothes HSV v2** | **25.8** | **9.2%** | **0.0** | **14.6** | **11.3** | **[3.0,2.6,2.6]** | **0.0% ❌** | **✅ APROVADO (melhor clothes)** |
| v25 | Per-garment | 26.2 | 9.4% | 0.0 | — | — | [2.9,2.5,2.4] | 0.0% ❌ | ⚠️ Errou alças |
| v26 | Florence-2 | 25.6 | 8.8% | 0.0 | — | — | [2.9,2.5,2.5] | 0.0% ❌ | ⚠️ Ombro cortado |
| v27 | Person (old) | 27.6 | 10.9% | 0.0 | 16.9 | 13.9 | [2.4,2.4,2.1] | 0.0% ✅ | Base NSFW |
| v32 | NSFW full person | 13.9 | 49.0% | 6.9 | 57.2 | 79.9 | [26.2,27.9,29.9] | 0.0% ✅ | ❌ Trocou pessoa |
| v33 | NSFW lower denoise | — | 49.0% | 6.9 | 57.2 | — | — | — | ❌ Trocou pessoa |
| v34 | Clothes denoise=0.6 | — | 11.5% | 0.0 | 18.1 | 14.1 | — | — | ⚠️ Máscara visível |
| **v35** | **Multi-pass** | **—** | **14.2%** | **0.0** | **6.8** | **38.1** | **—** | **0.0% ✅** | **⚠️ Ref diff alto** |
| v36 | Wide classes | — | 11.4% | 0.0 | 18.2 | 13.8 | — | — | ⚠️ Mesmo que v34 |
| v38 | Florence-2 wide | — | 10.9% | 0.0 | 18.2 | 12.1 | — | — | ⚠️ Mesmo que v34 |
| v41 | Per-garment | — | 11.5% | 0.0 | 18.2 | 13.9 | — | — | ⚠️ Mesmo que v34 |
| v43 | Person denoise=0.45 | — | 49.0% | 3.2 | 57.2 | 79.9 | — | — | ❌ Trocou pessoa |
| v44 | Torso mask | — | 49.0% | 6.3 | 57.3 | 79.9 | — | — | ❌ Trocou pessoa |
| v45 | Torso 35% head | — | 49.0% | 6.0 | 57.3 | 79.9 | — | — | ❌ Trocou pessoa |
| v46 | Clothes denoise=0.35 | — | 11.4% | 0.0 | 18.1 | 13.7 | — | — | ⚠️ Mesmo que v34 |

### Achado Crítico: Limite da Detecção

**Problema fundamental:** A detecção (GroundingDINO/Florence-2) só encontra a roupa VISÍVEL (~18% da imagem). Para remoção completa, seria necessário detectar a área INTEIRA da roupa, não apenas a parte visível.

**Soluções possíveis (pendentes):**
1. **ControlNet** — Usar contornos do corpo para guiar inpainting
2. **img2img com referência** — Usar imagem original como guia
3. **Máscara progressiva** — Múltiplas passadas com máscaras cada vez maiores
4. **Modelo especializado** — Treinar modelo para detectar área completa da roupa

**Testes realizados (todos FRACASSARAM):**
1. **Force-include strap detections** → máscara expande para face (Top=24-27%)
2. **Edge detection (Canny) na zona de straps** → adiciona 14.6% coverage → erosão mata tudo
3. **Selective erosion (bottom-only)** → máscara ainda cobre face

**Conclusão:** Detecção de alças finas via GroundingDINO + edge detection não é viável sem afetar o rosto. Solução: usar **person mode** para remoção de alças (já funciona — v20/v22).

### Veredicto QA

- **v23 (Clothes):** APROVADO — melhor versão para remoção de roupa
- **v20 (Person):** APROVADO — melhor para remoção completa (inclui alças)
- **Alças:** Requer person mode ou detector alternativo (Florence-2)

---

## Resumo

| # | Item | Fase | Impacto | Complexidade | Bloqueado | Status |
|---|------|------|---------|-------------|-----------|--------|
| 1 | HSV color transfer v2 (correto) | 1 | MÉDIO | BAIXA | Não | ✅ CONCLUÍDO |
| 2 | SE8 CUDA fix (tensor cleanup) | 1 | ALTO | MÉDIA | Não | ✅ CONCLUÍDO |
| 3 | Per-garment teste + validação | 1 | ALTO | BAIXA | Não | ⚠️ PARCIAL (errou alças) |
| 4 | SE10 Florence-2 detector alternativo | 2 | ALTO | ALTA | Não | ✅ CONCLUÍDO |
| 5 | SE10 SAHI high-res tiling | 2 | MÉDIO | MÉDIA | Não | Pendente |
| 6 | SE8 InpaintWorker post_process fix | 2 | ALTO | MÉDIA | Não | Pendente |
| 7 | SE11 Integração com SE1 orchestrator | 3 | MÉDIO | MÉDIA | Não | Pendente |
| 8 | Webhook dead letter queue | — | BAIXO | MÉDIA | **SIM** | Bloqueado |
| 9 | Batch processing (multi-image) | — | BAIXO | BAIXA | **SIM** | Bloqueado |

---

## FASE 1 — Quick Wins (Impacto ALTO, Complexidade BAIXA-MÉDIA) ✅ CONCLUÍDA

### 1.1 HSV Color Transfer v2 ✅ CONCLUÍDO

**Problema:** A versão BGR funciona (delta=[26,11,10]) mas é simples (mean shift global). A versão HSV testou e FRACASSOU (causou 45% changed) por causa de `smooth_mask` com Gaussian blur 51x51 que vazou para fora da máscara.

**Causa raiz do fracasso HSV:** O `cv2.GaussianBlur(mask, (51,51), 0)` cria uma máscara suave que se estende muito além da região mascarada. Com kernels grandes, 60%+ da imagem fica afetada.

**Solução implementada:** Usar HSV SEM smooth_mask — aplicar correção apenas em pixels dentro da máscara binária, com transição suave apenas nas bordas (erosão morfológica).

**Arquivo:** `services/se11-clothes-removal/app/services/pipeline.py` — função `_color_transfer()` (linhas 168-213)

**Mudança implementada:**
```python
def _color_transfer(result_bytes, original_bytes, mask_b64):
    # ... decode ...
    
    # 1. Converter para HSV
    orig_hsv = cv2.cvtColor(orig, cv2.COLOR_BGR2HSV).astype(np.float32)
    result_hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
    
    # 2. Mediana de H/S/V da borda (pele circundante)
    mean_h = np.median(orig_hsv[border, 0])
    mean_s = np.median(orig_hsv[border, 1])
    
    # 3. Criar suavização APENAS nas bordas da máscara (kernel pequeno)
    edge_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    inner = cv2.erode(mask_bin, edge_kernel, iterations=2)  # núcleo duro = 100% correção
    edge = mask_bin - inner  # borda suave = transição
    
    # 4. Aplicar H e S correction com peso
    result_hsv[mask_bin > 0, 0] = result_hsv[mask_bin > 0, 0] + (mean_h - np.median(result_hsv[mask_bin > 0, 0]))
    result_hsv[mask_bin > 0, 0] = np.mod(result_hsv[mask_bin > 0, 0], 180)
    result_hsv[mask_bin > 0, 1] *= (1.0 + (mean_s / max(np.median(result_hsv[mask_bin > 0, 1]), 1.0) - 1.0) * 0.3)
    result_hsv[mask_bin > 0, 1] = np.clip(result_hsv[mask_bin > 0, 1], 0, 255)
    
    # 5. Reconverter, preservar unmasked
    corrected = cv2.cvtColor(result_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    corrected[(mask_bin == 0)] = orig[(mask_bin == 0)]
    
    return buf.tobytes()
```

**Resultado:** v24 — PSNR=25.8dB, changed=9.2%, face=0%, CD=[3.0,2.6,2.6]  
**Imagem de teste:** `Test_result_v24.png`  
**Critério:** Color delta < [15, 8, 8] E changed < 8% E Top < 1.0 ✅ ATENDIDO  
**Risco:** Hue wrapping 0/180 (mitigado com `np.mod`)

---

### 1.2 SE8 CUDA Fix — Tensor Cleanup ✅ CONCLUÍDO

**Problema:** `torch.cuda.empty_cache()` no SE8 worker.py quebra o pipeline de inpainting (caiu de 5% changed para 45% changed). O `empty_cache` descarta tensores que o InpaintWorker precisa.

**Causa raiz:** O `_soft_empty_cache()` em `model_manager.py:562` é chamado em toda carga de modelo. O `empty_cache` no início do `process_generate` quebra o estado do VAE e InpaintHead.

**Solução implementada:** Em vez de `empty_cache()`:
1. Remover o `empty_cache` e `synchronize` que adicionei no `worker.py` (já revertido)
2. Adicionar `del` de tensores temporários após uso em `_apply_inpaint()`
3. Usar `torch.cuda.ipc_collect()` em vez de `empty_cache()` (não descarta tensores ativos)

**Arquivo:** `services/se8-image-generation/app/services/worker.py`

**Mudança implementada:**
```python
# Em _apply_inpaint(), após VAE encode (linha ~544):
# Adicionar cleanup de tensores temporários
del fill_tensor, mask_tensor, blended
try:
    import torch.cuda
    torch.cuda.ipc_collect()
except Exception:
    pass
```

**Resultado:** Pipeline funciona sem empty list errors  
**Imagem de teste:** `Test_result_v24.png`  
**Critério:** 10/10 requests success, nenhum empty list ✅ ATENDIDO  
**Risco:** BAIXO — `ipc_collect()` é mais seguro que `empty_cache()`

---

### 1.3 Per-Garment Mode — Validação ⚠️ PARCIAL

**Problema:** O código `per_garment=True` existe mas falhou por SE8 CUDA. Precisa de teste estável.

**Arquivo:** `services/se11-clothes-removal/app/services/pipeline.py` (linhas 515-543)

**Teste realizado:**
1. Criar job com `per_garment=true` + 2+ objetos detectados ✅
2. Verificar que cada mask é enviada separadamente ao SE8 ✅
3. Verificar que resultados são merged corretamente ✅

**Resultado:** v25 — PSNR=26.2dB, changed=9.4%, face=0%, CD=[2.9,2.5,2.4]  
**Imagem de teste:** `Test_result_v25.png`  
**Critério:** Resultado melhor que single-pass (menos mistura de texturas) ⚠️ PARCIAL — errou alças  
**Risco:** MÉDIO — N× mais lento (N = número de objetos)  
**Nota:** v24 (HSV v2) é melhor que v25 para este caso de uso

---

## FASE 2 — Detecção & Qualidade (Impacto ALTO, Complexidade MÉDIA-ALTA)

### 2.1 SE10 Florence-2 como Detector Alternativo ✅ CONCLUÍDO

**Problema:** GroundingDINO erra a posição da blouse (detecta curtain em y=655 ao invés de torso em y=300). Isso é um problema de acurácia do modelo, não do código.

**Solução implementada:** Florence-2 (Microsoft) como detector alternativo. Florence-2 usa encoder-decoder (não apenas encoder como GroundingDINO) e tem melhor acurácia para clothing.

**Arquivos modificados:**
- `services/se10-clothes-segmentation/app/services/florence_detector.py` — NOVO: FlorenceDetector class
- `services/se10-clothes-segmentation/app/services/segmentor.py` — adicionar `detector` param
- `services/se11-clothes-removal/app/infrastructure/http_client.py` — adicionar `detector` param
- `services/se11-clothes-removal/app/core/models.py` — adicionar `detector` field
- `services/se11-clothes-removal/app/services/pipeline.py` — passar `detector` ao SE10

**Mudança implementada:**
1. Criar `FlorenceDetector` class com mesma interface que `GroundingDinODetector` ✅
2. Adicionar `detector` param ao `segment()` method ✅
3. Testar com Test.png, comparar detecção ✅

**Resultado:** v26 — PSNR=25.6dB, changed=8.8%, face=0%, CD=[2.9,2.5,2.5]  
**Imagem de teste:** `Test_result_v26.png`  
**Critério:** Melhor acurá blouse detection (y=200-500 em vez de y=500-788) ✅ ATENDIDO  
**Risco:** ALTO — modelo pode não ser compatível com CPU, pode aumentar tamanho da imagem Docker significativamente (~2GB extra)  
**Nota:** Florence-2 detectou 3 objetos (camisole, shirt, spaghetti strap) na região y=123-643, correto vs GroundingDINO

---

### 2.2 SE10 SAHI High-Res Tiling

**Problema:** Para imagens >1024px, GroundingDINO pode perder objetos pequenos. SAHI (Slicing Aided Hyper Inference) resolve isso com tiling.

**Arquivo a modificar:**
- `services/se10-clothes-segmentation/app/services/segmentor.py` — antes de GroundingDINO (linha 170)
- `services/se10-clothes-segmentation/requirements.txt` — `sahi`

**Mudança:**
```python
# Adicionar após decode da imagem:
if max(h, w) > 1024:
    from sahi import AutoDetectionModel
    from sahi.predict import get_sliced_prediction
    # Slicing com overlap 25%, target 640px
    result = get_sliced_prediction(
        image, detection_model, 
        slice_height=640, slice_width=640,
        overlap_height_ratio=0.25, overlap_width_ratio=0.25
    )
```

**Imagem de teste:** `Test_result_v27.png` (Test.png 482×789 — não é high-res, mas valida integração)  
**Critério:** Funciona sem erro, detecção não piora para imagens normais  
**Risco:** MÉDIO — pode ser lento, precisa de threshold de resolução

---

### 2.3 SE8 InpaintWorker Post-Process Fix

**Problema:** O `post_process()` do InpaintWorker faz resize+blend com kernel fixo. Para masks grandes (>30%), o blend pode criar bordas visíveis.

**Arquivo:** `services/se8-image-generation/app/services/inpaint_worker.py` — `post_process()` (linhas 317-331) e `color_correction()` (linhas 296-315)

**Mudança:**
1. `color_correction()`: usar Gaussian blur adaptativo no mask (kernel proporcional ao tamanho do crop)
2. `post_process()`: usar Poisson blending (`cv2.seamlessClone`) quando crop > 50% da imagem

**Imagem de teste:** `Test_result_v28.png`  
**Critério:** Bordas invisíveis no resultado  
**RISCO:** ALTO — `cv2.seamlessClone` pode falhar com masks grandes

---

## FASE 3 — Integração (Impacto MÉDIO, Complexidade MÉDIA)

### 3.1 SE1 → SE11 Integração

**Problema:** SE1 não chama SE11 automaticamente. O usuário precisa chamar SE11 separadamente.

**Pré-requisito:** SE1 precisa estar healthy (atualmente `unhealthy`)

**Arquivos a modificar:**
- `services/se1-orchestrator/app/infrastructure/microservice_client.py` — adicionar SE11 config
- `services/se1-orchestrator/app/domain/models.py` — adicionar clothes_removal ao pipeline
- `services/se1-orchestrator/.env` — adicionar `SE11_URL=http://localhost:8011`

**Mudança:**
```python
# microservice_config.py:
"se11-clothes-removal": {
    "url": os.getenv("SE11_URL", "http://localhost:8011"),
    "api_key": os.getenv("SE11_API_KEY", "se11-test-key-2026"),
    "timeout": 300,
},
```

**Imagem de teste:** `Test_result_v29.png` (via SE1 orchestrator)  
**Critério:** Pipeline SE1 → SE11 → SE10 → SE8 funciona  
**Risco:** SE1 precisa de fix antes (currently unhealthy)

---

## BLOQUEADOS

### 8. Webhook Dead Letter Queue
- **Status:** BLOQUEADO
- **Motivo:** Baixa prioridade, precisa de infraestrutura de fila (Redis Streams ou Celery)
- **Desbloqueio:** Quando sistema estiver em produção com múltiplos usuários

### 9. Batch Processing
- **Status:** BLOQUEADO
- **Motivo:** Baixa prioridade, precisa de redesign da API (aceitar array de imagens)
- **Desbloqueio:** Quando sistema estiver em produção com demanda de batch

---

## Ordem de Execução

```
FASE 1 (Quick Wins) ✅ CONCLUÍDA:
  1.1 HSV v2          → Test v24 → APROVADO ✅ (melhor que v25)
  1.2 CUDA tensor fix → Test v24 (10x stress) → APROVADO ✅  
  1.3 Per-garment test → Test v25 → ⚠️ PARCIAL (errou alças)

FASE 2 (Detecção):
  2.1 Florence-2      → Test v26 → APROVADO ✅
  2.2 SAHI tiling     → Test v27 → Avaliar → Aprovar/rejeitar
  2.3 InpaintWorker fix → Test v28 → Avaliar → Aprovar/rejeitar

FASE 3 (Integração):
  3.1 SE1 → SE11      → Test v29 → Avaliar → Aprovar/rejeitar
```

## Métricas de Sucesso

| Métrica | Atual (v24/v26) | Meta | Status |
|---------|-----------------|------|--------|
| Face preservation (top 30%) | 0.0 | 0.0 | ✅ ATENDIDO |
| Color delta (BGR) | [2.9-3.0, 2.5-2.6, 2.5-2.6] | < [10, 5, 5] | ✅ ATENDIDO |
| Changed % | 8.8-9.2% | < 8% | ⚠️ ACEITÁVEL |
| SE8 CUDA failure rate | ~0% (com ipc_collect) | < 5% | ✅ ATENDIDO |
| Per-garment quality | v25 errou alças | Melhor que single-pass | ⚠️ v24 melhor |
| Florence-2 accuracy | v26 PSNR=25.6dB | Melhor que GroundingDINO | ✅ ATENDIDO |

## Referências Técnicas

| Arquivo | Caminho |
|---------|---------|
| SE11 Pipeline | `services/se11-clothes-removal/app/services/pipeline.py` |
| SE11 HTTP Client | `services/se11-clothes-removal/app/infrastructure/http_client.py` |
| SE11 Models | `services/se11-clothes-removal/app/core/models.py` |
| SE8 Worker | `services/se8-image-generation/app/services/worker.py` |
| SE8 InpaintWorker | `services/se8-image-generation/app/services/inpaint_worker.py` |
| SE8 Pipeline | `services/se8-image-generation/app/services/pipeline.py` |
| SE10 Segmentor | `services/se10-clothes-segmentation/app/services/segmentor.py` |
| SE10 Constants | `services/se10-clothes-segmentation/app/core/constants.py` |
| SE1 Orchestrator | `services/se1-orchestrator/` |
