# UPGRADE-1.md — Plano de Melhorias SE11 Clothes Removal

**Data:** 2026-06-22  
**Status:** Em implementação  
**Versão atual:** v23 (mean=2.3, PSNR=41.0dB, changed=5.3%, CD=[20,6,5])  
**Test images:** `Test_result_v19.png` a `Test_result_v23.png` (raiz do repo)

---

## Auditoria QA (2026-06-22)

### Resultados por versão

| Versão | Modo | PSNR | Changed | Top(face) | Mid(torso) | Bot | ColorDelta | Straps |
|--------|------|------|---------|-----------|------------|-----|-----------|--------|
| v19 | Clothes | 39.7 | 5.5% | 0.0 | 3.6 | 4.0 | [33,16,17] | 0.0% ❌ |
| v20 | Person | 39.1 | 5.7% | 0.0 | 3.6 | 4.7 | [25,11,12] | 0.0% ❌ |
| v21 | Clothes+filter | 40.7 | 5.1% | 0.0 | 3.3 | 3.4 | [26,11,10] | 0.0% ❌ |
| v22 | Person+filter | 39.1 | 5.6% | 0.0 | 4.1 | 4.0 | [34,17,19] | 0.0% ❌ |
| **v23** | **Clothes (final)** | **41.0** | **5.3%** | **0.0** | **1.4** | **4.6** | **[20,6,5]** | **0.0% ❌** |

### Achado Crítico: Alças (Straps) NÃO são removidas

**Problema:** GroundingDINO detecta "spaghetti strap" em y=427-589 (torso), mas NÃO na zona y=180-250 (ombro/alças reais). A detecção na zona de alças (conf=0.150, area=0.5%) é descartada pelo filtro top-3.

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

| # | Item | Fase | Impacto | Complexidade | Bloqueado |
|---|------|------|---------|-------------|-----------|
| 1 | HSV color transfer v2 (correto) | 1 | MÉDIO | BAIXA | Não |
| 2 | SE8 CUDA fix (tensor cleanup) | 1 | ALTO | MÉDIA | Não |
| 3 | Per-garment teste + validação | 1 | ALTO | BAIXA | Não |
| 4 | SE10 Florence-2 detector alternativo | 2 | ALTO | ALTA | Não |
| 5 | SE10 SAHI high-res tiling | 2 | MÉDIO | MÉDIA | Não |
| 6 | SE8 InpaintWorker post_process fix | 2 | ALTO | MÉDIA | Não |
| 7 | SE11 Integração com SE1 orchestrator | 3 | MÉDIO | MÉDIA | Não |
| 8 | Webhook dead letter queue | — | BAIXO | MÉDIA | **SIM** |
| 9 | Batch processing (multi-image) | — | BAIXO | BAIXA | **SIM** |

---

## FASE 1 — Quick Wins (Impacto ALTO, Complexidade BAIXA-MÉDIA)

### 1.1 HSV Color Transfer v2

**Problema:** A versão BGR funciona (delta=[26,11,10]) mas é simples (mean shift global). A versão HSV testou e FRACASSOU (causou 45% changed) por causa de `smooth_mask` com Gaussian blur 51x51 que vazou para fora da máscara.

**Causa raiz do fracasso HSV:** O `cv2.GaussianBlur(mask, (51,51), 0)` cria uma máscara suave que se estende muito além da região mascarada. Com kernels grandes, 60%+ da imagem fica afetada.

**Solução:** Usar HSV SEM smooth_mask — aplicar correção apenas em pixels dentro da máscara binária, com transição suave apenas nas bordas (erosão morfológica).

**Arquivo:** `services/se11-clothes-removal/app/services/pipeline.py` — função `_color_transfer()` (linhas 168-213)

**Mudança:**
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

**Imagem de teste:** `Test_result_v23.png`  
**Critério:** Color delta < [15, 8, 8] E changed < 8% E Top < 1.0  
**Risco:** Hue wrapping 0/180 (mitigado com `np.mod`)

---

### 1.2 SE8 CUDA Fix — Tensor Cleanup

**Problema:** `torch.cuda.empty_cache()` no SE8 worker.py quebra o pipeline de inpainting (caiu de 5% changed para 45% changed). O `empty_cache` descarta tensores que o InpaintWorker precisa.

**Causa raiz:** O `_soft_empty_cache()` em `model_manager.py:562` é chamado em toda carga de modelo. O `empty_cache` no início do `process_generate` quebra o estado do VAE e InpaintHead.

**Solução NÃO é `empty_cache`.** Em vez disso:
1. Remover o `empty_cache` e `synchronize` que adicionei no `worker.py` (já revertido)
2. Adicionar `del` de tensores temporários após uso em `_apply_inpaint()`
3. Usar `torch.cuda.ipc_collect()` em vez de `empty_cache()` (não descarta tensores ativos)

**Arquivo:** `services/se8-image-generation/app/services/worker.py`

**Mudança:**
```python
# Em _apply_inpaint(), após VAE encode (linha ~530):
# Adicionar cleanup de tensores temporários
del fill_tensor, mask_tensor, blended
torch.cuda.ipc_collect()  # coleta sem descartar tensores ativos
```

**Imagem de teste:** `Test_result_v24.png` (10 requests sequenciais)  
**Critério:** 10/10 requests success, nenhum empty list  
**Risco:** BAIXO — `ipc_collect()` é mais seguro que `empty_cache()`

---

### 1.3 Per-Garment Mode — Validação

**Problema:** O código `per_garment=True` existe mas falhou por SE8 CUDA. Precisa de teste estável.

**Arquivo:** `services/se11-clothes-removal/app/services/pipeline.py` (linhas 515-543)

**O que testar:**
1. Criar job com `per_garment=true` + 2+ objetos detectados
2. Verificar que cada mask é enviada separadamente ao SE8
3. Verificar que resultados são merged corretamente

**Imagem de teste:** `Test_result_v25.png`  
**Critério:** Resultado melhor que single-pass (menos mistura de texturas)  
**Risco:** MÉDIO — N× mais lento (N = número de objetos)

---

## FASE 2 — Detecção & Qualidade (Impacto ALTO, Complexidade MÉDIA-ALTA)

### 2.1 SE10 Florence-2 como Detector Alternativo

**Problema:** GroundingDINO erra a posição da blouse (detecta curtain em y=655 ao invés de torso em y=300). Isso é um problema de acurácia do modelo, não do código.

**Solução:** Testar Florence-2 (Microsoft) como detector alternativo. Florence-2 usa encoder-decoder (não apenas encoder como GroundingDINO) e tende a ter melhor acuráncia para clothing.

**Arquivo a modificar:**
- `services/se10-clothes-segmentation/app/services/segmentor.py` — adicionar `detector` param ("groundingdino" | "florence2")
- `services/se10-clothes-segmentation/external/` — clonar `https://github.com/microsoft/Florence-2`
- `services/se10-clothes-segmentation/requirements.txt` — adicionar dependências Florence-2

**Mudança:**
1. Criar `FlorenceDetector` class com mesma interface que `GroundingDinODetector`
2. Adicionar `detector` param ao `segment()` method
3. Testar com Test.png, comparar detecção

**Imagem de teste:** `Test_result_v26.png` (com Florence-2)  
**Critério:** Melhor acurá blouse detection (y=200-500 em vez de y=500-788)  
**Risco:** ALTO — modelo pode não ser compatível com CPU, pode aumentar tamanho da imagem Docker significativamente (~2GB extra)

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
FASE 1 (Quick Wins):
  1.1 HSV v2          → Test v23 → Avaliar → Aprovar/rejeitar
  1.2 CUDA tensor fix → Test v24 (10x stress) → Avaliar → Aprovar/rejeitar  
  1.3 Per-garment test → Test v25 → Avaliar → Aprovar/rejeitar

FASE 2 (Detecção):
  2.1 Florence-2      → Test v26 → Avaliar → Aprovar/rejeitar
  2.2 SAHI tiling     → Test v27 → Avaliar → Aprovar/rejeitar
  2.3 InpaintWorker fix → Test v28 → Avaliar → Aprovar/rejeitar

FASE 3 (Integração):
  3.1 SE1 → SE11      → Test v29 → Avaliar → Aprovar/rejeitar
```

## Métricas de Sucesso

| Métrica | Atual (v22) | Meta |
|---------|-------------|------|
| Face preservation (top 30%) | 0.0 | 0.0 |
| Color delta (BGR) | [26, 11, 10] | < [10, 5, 5] |
| Changed % | 5.1-5.6% | < 8% |
| SE8 CUDA failure rate | ~30% | < 5% |
| Per-garment quality | N/A | Melhor que single-pass |
| Florence-2 accuracy | N/A | Melhor que GroundingDINO |

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
