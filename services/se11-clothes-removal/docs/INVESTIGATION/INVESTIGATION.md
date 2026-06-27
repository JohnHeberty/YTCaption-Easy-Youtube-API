# INVESTIGATION.md — Transformação SE11: Roupa → Pessoa

## Objetivo

Transformar o SE11 (clothes-removal) em um serviço de **remoção de pessoa inteira** — detectar e remover a pessoa completa (cabelo, cabeça, corpo, braços) de uma imagem, preservando o fundo.

---

## Dados de Teste

| Arquivo | Descrição | Dimensões |
|---------|-----------|-----------|
| `Test.png` | Imagem original (mulher com top floral rosa, sunglasses, cortina amarela) | 482×789 RGBA |
| `Test_Selected.png` | Máscara vermelha (#ED1C24) cobrindo a pessoa inteira | 482×789 RGBA |
| `Test_Selected.txt` | Cor exata da seleção: `#ED1C24` | — |

### Análise da Máscara Vermelha (Ground Truth)
- **Cobertura**: 44.1% da imagem (167.838 pixels vermelhos / 380.298 total)
- **Bounding box**: x=[67, 446], y=[188, 788]
- **Centroide**: (250, 537)
- **Região**: Pessoa inteira de cabeça (y=188) até cintura/quadris (y=788)

---

## Arquitetura Atual (SE11 → SE10 → SE8)

```
SE11 (port 8011)
  │
  │ POST /v1/segment (multipart: file + classes)
  ▼
SE10 (port 8010)
  │
  ├─ GroundingDINO: predict_with_classes(image, classes=["shirt","pants",...])
  │  → sv.Detections (xyxy, confidence, class_id)
  │
  ├─ Filtering: area < 29%, nesting, max 50 objects
  │
  ├─ SAM2: predict(box=...) por objeto → binary masks
  │
  ▼
Retorna: {objects[], masks[]}
  │
  │ SE11 combina masks (bitwise_or → 1 mask única)
  ▼
SE8 (port 8008)
  │
  │ POST /v1/generation/image-inpaint-outpaint
  │ image + mask + prompt → resultado
  ▼
  PNG resultado
```

### Problemas da Arquitetura Atual para Remoção de Pessoa

1. **Classes erradas**: SE10 detecta 15 classes de roupa, não pessoas
2. **Máscara fragmentada**: Cada peça de roupa gera uma máscara separada; união pode deixar gaps (pele entre roupas)
3. **Prompt errado**: SE11 envia prompt "nude, naked body, smooth skin" — queremos remover a pessoa, não gerar nudez
4. **SE8 params inadequados**: `inpaint_respective_field=0.8` é para roupas; pessoa inteira (44% da imagem) precisa de ajuste
5. **Area filter**: 29% max area pode cortar detecção de pessoa grande (44% da imagem)

---

## Pesquisa: Capacidades dos Modelos (Fontes Oficiais)

### GroundingDINO — Detecção de Pessoas

**Fontes**: [GitHub IDEA-Research/GroundingDINO](https://github.com/IDEA-Research/GroundingDINO) (10.3k stars), [Paper ECCV 2024](https://arxiv.org/abs/2303.05499)

GroundingDINO é um detector **open-set** — aceita qualquer conceito expresso em linguagem natural. Treinado em O365 (Object365), GoldG, e 4M imagens captionadas.

**Métricas oficiais**:
| Variante | Backbone | Dados | COCO zero-shot AP | COCO fine-tune AP |
|----------|----------|-------|-------------------|-------------------|
| GroundingDINO-T (SwinT) | Swin-T | O365, GoldG, Cap4M | **48.4** | 57.2 |
| GroundingDINO-B (SwinB) | Swin-B | COCO, O365, GoldG, Cap4M, OpenImage, ODinW-35, RefCOCO | **56.7** | — |

**O SE10 usa SwinT** (48.4 AP zero-shot) — suficiente para detecção de pessoas.

#### Formato de Text Prompt (Oficial)

```python
# Do README oficial: "We suggest separating different category names with '.'"
TEXT_PROMPT = "chair . person . dog ."
BOX_THRESHOLD = 0.35
TEXT_THRESHOLD = 0.25

# Como o SE10 joga classes internamente (inference.py:219):
caption = ". ".join(classes)  # "person. woman. man."
```

**Regras oficiais**:
1. Separar categorias com `.` (ponto)
2. Texto em **minúsculas**
3. Terminar com `.` (ponto final)
4. Cada palavra pode ser splitada em múltiplos tokens pelo tokenizer
5. `box_threshold` filtra boxes pela similaridade máxima
6. `text_threshold` extrai palavras com similaridade > threshold como labels

#### Thresholds Recomendados (oficiais)

| Uso | box_threshold | text_threshold | Fonte |
|-----|---------------|----------------|-------|
| **Geral (oficial)** | 0.35 | 0.25 | README GroundingDINO |
| **Pessoa (robusto)** | 0.30 | 0.25 | Grounded-SAM-2 demo |
| **Alta recall (mínimo)** | 0.25 | 0.20 | Prática comum |
| **Alta precisão** | 0.45 | 0.35 | Evita falsos positivos |

**Problema atual do SE10**: Usa `box_threshold=0.10` e `text_threshold=0.10` — muito baixos, causando falsos positivos (ex: detectando "blouse" na posição errada).

#### Como Funciona Internamente

```
Input: (image_BGR, "person. woman. man.")
  │
  ├─ Caption: "person. woman. man."
  ├─ Preprocess: BGR→RGB PIL → RandomResize([800], max_size=1333) → ToTensor → Normalize(ImageNet)
  │
  ├─ Model Forward: pred_logits (nq, 256), pred_boxes (nq, 4 cxcywh)
  │
  ├─ Filter: pred_logits.max(dim=1)[0] > box_threshold
  │
  ├─ Post-process: cxcywh→xyxy, scale to source image dimensions
  │
  └─ Class assignment: phrases2classes() — substring matching
     ex: detection phrase "a person" → class "person" found in phrase → class_id=0
```

**Resultado**: Não precisa de modelo novo. Basta mudar `classes=["person","woman","man"]` no request ao SE10. Porém, precisa ajustar thresholds e area filter.

#### Comparação: GroundingDINO vs Alternativas

| Modelo | Tipo | Precisão | Velocidade | Custo | Melhor para |
|--------|------|----------|------------|-------|-------------|
| **GroundingDINO SwinT** (atual) | Open-set, local | ⭐⭐⭐ Boa | ⭐⭐ Rápido | Grátis | Multi-classe |
| **GroundingDINO SwinB** | Open-set, local | ⭐⭐⭐⭐ Melhor | ⭐ Mais lento | Grátis | Maior precisão |
| **GroundingDINO 1.5** | Open-set, API | ⭐⭐⭐⭐⭐ Excelente | ⭐⭐ Bom | Pago (API) | Estado da arte |
| **DINO-X** | Open-set, API | ⭐⭐⭐⭐⭐+ | ⭐⭐ Bom | Pago (API) |最强 open-world |
| **Florence-2** | Vision-language, local | ⭐⭐⭐⭐ Boa | ⭐⭐ Bom | Grátis | Multi-tarefa |
| **YOLO11-seg** | Instance seg, local | ⭐⭐⭐ Boa | ⭐⭐⭐⭐ Muito rápido | Grátis | Real-time |

**Recomendação**: GroundingDINO SwinT (atual) é suficiente. Upgrade para SwinB se precisar de mais precisão.

---

### SAM2 — Segment Anything Model 2

**Fontes**: [GitHub facebookresearch/sam2](https://github.com/facebookresearch/sam2) (19.4k stars), [Paper arXiv 2024](https://arxiv.org/abs/2408.00714)

SAM2 é um modelo fundação para segmentação visual em imagens e vídeos. Estende SAM para vídeo com streaming memory.

#### Checkpoints Disponíveis

| Modelo | Params | FPS (A100) | SA-V test J&F | MOSE val J&F | Nosso uso |
|--------|--------|------------|---------------|--------------|-----------|
| sam2_hiera_tiny | 38.9M | 91.5 | 75.0 | 70.9 | **✅ ATUAL** |
| sam2_hiera_small | 46M | 85.6 | 74.9 | 71.5 | |
| sam2_hiera_base_plus | 80.8M | 64.8 | 74.7 | 72.8 | |
| sam2_hiera_large | 224.4M | 39.7 | 76.0 | 74.6 | |

**SAM 2.1** (set/2024) — versão melhorada:

| Modelo | Params | FPS | SA-V test J&F | Melhoria vs SAM2 |
|--------|--------|-----|---------------|------------------|
| sam2.1_hiera_tiny | 38.9M | 91.2 | 76.5 | +1.5 |
| sam2.1_hiera_large | 224.4M | 39.5 | **79.5** | +3.5 |

**O SE10 usa sam2_hiera_tiny** — mais rápido, menor, mas menos preciso. Para pessoa, pode ser suficiente.

#### Prompt Types Suportados

SAM2 suporta **4 tipos de prompt** (confirmado no código fonte `sam2_image_predictor.py:237-303`):

```python
def predict(
    self,
    point_coords: Optional[np.ndarray] = None,     # Nx2, cada ponto em (X,Y) pixels
    point_labels: Optional[np.ndarray] = None,      # N: 0=bg, 1=fg, 2=box_TL, 3=box_BR
    box: Optional[np.ndarray] = None,               # length-4, formato XYXY
    mask_input: Optional[np.ndarray] = None,        # 1xHxW low-res mask (256x256)
    multimask_output: bool = True,                  # retorna 3 candidatos
    return_logits: bool = False,
    normalize_coords=True,                          # normaliza para [0,1]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Retorna: (masks CxHxW), (iou_predictions C), (low_res_masks CxHxW)
```

| Tipo de Prompt | Suportado? | Uso Atual no SE10 | Descrição |
|---------------|-----------|-------------------|-----------|
| Box (XYXY) | ✅ | ✅ Usado | Bounding box do GroundingDINO |
| Point (X,Y) + label | ✅ | ❌ Não usado | Pontos positivos/negativos |
| Box + Points combinados | ✅ | ❌ Não usado | Refinamento com pontos dentro do box |
| Mask input (iterativo) | ✅ | ❌ Não usado | Refinamento com máscara anterior |

#### Label Codes do Prompt Encoder

| Label | Significado | Embedding |
|-------|-------------|-----------|
| `0` | Negative click (background) | `point_embeddings[0]` |
| `1` | Positive click (foreground) | `point_embeddings[1]` |
| `2` | Box corner top-left | `point_embeddings[2]` |
| `3` | Box corner bottom-right | `point_embeddings[3]` |
| `-1` | Padding (não é ponto) | `not_a_point_embed` |

**Como boxes são internamente codificados como pontos**:
```python
# Em _predict(), boxes são convertidos:
box_coords = boxes.reshape(-1, 2, 2)           # shape: Bx2x2
box_labels = torch.tensor([[2, 3]])             # labels 2,3 para os dois cantos
```

#### Padrão Oficial do Grounded-SAM-2

Do demo oficial `grounded_sam2_local_demo.py`:

```python
# Hyper parameters
TEXT_PROMPT = "car. tire."
BOX_THRESHOLD = 0.35
TEXT_THRESHOLD = 0.25
MULTIMASK_OUTPUT = False  # IMPORTANTE: False para tracking stability

# GroundingDINO detecta
boxes, confidences, labels = predict(
    model=grounding_model,
    image=image,
    caption=text,
    box_threshold=BOX_THRESHOLD,
    text_threshold=TEXT_THRESHOLD,
)

# Converte boxes para SAM2
h, w, _ = image_source.shape
boxes = boxes * torch.Tensor([w, h, w, h])  # normaliza para pixels
input_boxes = box_convert(boxes=boxes, in_fmt="cxcywh", out_fmt="xyxy")

# SAM2 segmenta
masks, scores, logits = sam2_predictor.predict(
    point_coords=None,
    point_labels=None,
    box=input_boxes,
    multimask_output=MULTIMASK_OUTPUT,
)
```

**Padrão de point prompts para tracking** (Grounded-SAM-2):
```python
# "uniformly sample points from the prediction mask as point prompts
#  for SAM 2 video predictor"
# Ou seja: primeiro roda SAM2 com box, depois usa pontos da máscara
# como point prompts para refinamento/tracking
```

#### Performance do SE10 (Métricas Reais)

Do teste com `Test.png` (482×789):
```
Detected 3 objects:
  sunglasses: conf=0.774, bbox=[161,192,300,237], area=0.5%
  skirt:      conf=0.179, bbox=[119,699,365,788], area=2.8%
  blouse:     conf=0.107, bbox=[110,570,372,788], area=12.3%  ← WRONG POSITION
Processing time: 13203ms
```

**Problema**: blouse detectada em y=570-788 (fundo), deveria ser y=200-500 (torso). GroundingDINO confundiu a blusa com a cortina amarela.

#### Latência SAM2: N chamadas sequenciais

O SE10 executa SAM2 **N vezes sequencialmente** (uma por objeto detectado), não em batch:

```python
# segmentor.py:209-216 — loop individual
for box in final_detections.xyxy:
    masks, scores, _ = self._sam2_predictor.predict(
        point_coords=None, point_labels=None, box=box[None, :], multimask_output=True,
    )
    result_masks.append(masks[np.argmax(scores)])
```

O `SAM2ImagePredictor` tem `predict_batch()` disponível mas **não é usado**. Para 3 objetos, são 3 forward passes independentes (~1s cada em CPU). Para pessoa (1 objeto), latência é ~1s.

#### Estimates de Performance por Etapa

| Etapa | Modelo | Latência estimada (CPU) | Notas |
|-------|--------|------------------------|-------|
| GroundingDINO detect | SwinT | ~2-4s | Inclui pre + forward + post |
| SAM2 predict (1 obj) | Hiera Tiny | ~0.5-1s | 1 box prompt |
| SAM2 predict (N objs) | Hiera Tiny | ~N × 0.5-1s | Sequencial, não batch |
| SE8 inpaint (SDXL) | JuggernautXL | ~10-20s | 20-30 steps, 1024 scale |
| **Total (1 pessoa)** | — | **~15-25s** | GDINO + SAM2 + SE8 |
| **Total (3 roupas)** | — | **~20-35s** | 3×SAM2 + SE8 |

#### Resilience: Retry Pattern do SE11

O SE11 usa retry com exponential backoff para chamadas ao SE10/SE8:

```python
# http_client.py:41-65 — 3 retries, wait = 2^attempt segundos
for attempt in range(max_retries):
    try:
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
```

**Timeouts**: SE10=60s, SE8=300s. Para persona (1 objeto), timeout SE10 é mais que suficiente.

#### Parâmetro `k` (inpaint_respective_field)

O InpaintWorker tem `k=0.618` como default, mas o SE11 envia `inpaint_respective_field=0.8`:

```python
# SE11 http_client.py:173
"advanced_params": {"inpaint_respective_field": 0.8, ...}

# SE8 worker.py:459
k = async_task.inpaint_respective_field or 0.618  # SE11 envia 0.8
```

Para **remoção de pessoa** (44% da máscara), recomenda-se `k=1.0` (crop = imagem inteira) para maximizar contexto. O valor 0.8 é um meio-termo — cobre 80% da imagem ao redor da máscara.

---

### Color-Based Masking (#ED1C24)

HSV para vermelho #ED1C24: H=177, S=226, V=237

```python
# Red wraps H=0/180 boundary → 2 ranges necessários
lower_red1, upper_red1 = [165, 80, 80], [180, 255, 255]
lower_red2, upper_red2 = [0, 80, 80], [10, 255, 255]
```

**Abordagem híbrida (recomendada pelo Grounded-SAM-2)**: Usar cor para gerar seed points → alimentar SAM2 com point prompts.

**Fluxo híbrido**:
```
1. HSV color detection → binary mask (rápido, ~5ms)
2. Contour detection → centroid + bounding box
3. SAM2 point prompt: centroid=foreground, corners=background
4. SAM2 refine → máscara precisa
```

**Quando usar cada abordagem**:

| Cenário | Só cor | Cor + SAM2 | Só GroundingDINO |
|---------|--------|------------|-------------------|
| Máscara vermelha em fundo neutro | ⭐ Excelente | Overkill | Funciona |
| Máscara vermelha em fundo colorido | ⚠️ Falsos positivos | ⭐ Excelente | Funciona |
| Pessoa sem máscara vermelha | ❌ N/A | ❌ N/A | ⭐ Excelente |
| Múltiplas pessoas | ❌ Não distingue | ❌ Não distingue | ⭐ Excelente |

---

### SE8 Inpainting — Máscaras Grandes

A máscara de pessoa cobre **44.1%** da imagem. Impacto no InpaintWorker:

**Como funciona o parâmetro `k` (inpaint_respective_field)**:

```python
# solve_abcd() expande o bounding box até cobrir k% da área total
# k=0.618 (default): crop cobre ~61.8% da imagem
# k=1.0: crop = imagem inteira (sem recorte)
# k=0.3: crop apertado ao redor da máscara
```

| Cobertura da Máscara | Comportamento do Crop | Qualidade Esperada | VRAM |
|---------------------|----------------------|-------------------|------|
| < 30% | Crop apertado, bom contexto ao redor | ⭐ Excelente | Baixa |
| 30-60% | Crop médio, contexto moderado | ⭐ Boa | Média |
| 60-80% | Crop grande, pouco contexto | ⚠️ Razoável | Média-Alta |
| 80-100% | Quase imagem inteira | ❌ Ruim (artefatos) | Alta |

**44.1% está na faixa "Boa"** — mas para pessoa inteira, recomenda-se `k=1.0` (imagem inteira) para maximizar contexto.

#### Parâmetros SE8 Recomendados para Pessoa

```python
# Parâmetros para remoção de PESSOA (não roupa)
inpaint_respective_field = 1.0   # crop = imagem inteira (pessoa = 44%)
inpaint_strength = 1.0           # denoising completo
inpaint_engine = "v2.6"
prompt = "background, wall, curtain, environment, scenery"  # descrever FUNDO
negative_prompt = "person, human, body, skin, clothing, face, hair, limbs"
style_selections = ["Fooocus V2"]  # SEM Enhance/Sharp (alteram aparência)
```

---

## Plano Mestre: 3 Fases

### Fase 1 — SE10: Modo Pessoa (Mínimo)

**Objetivo**: SE10 aceita `classes="person,woman,man"` e retorna máscara da pessoa inteira.

**Arquivos a modificar**:

| Arquivo | Mudança | Complexidade |
|---------|---------|-------------|
| `se10/.../constants.py` | Adicionar `PERSON_CLASSES = ["person", "woman", "man"]` | ⭐ Baixa |
| `se10/.../segmentor.py` | Relaxar area filter para 80% (pessoa pode ser grande) | ⭐ Baixa |
| `se10/.../routes/segment.py` | Aceitar `mode` param (`"clothes"` ou `"person"`) | ⭐ Baixa |
| `se10/.../models.py` | Adicionar `mode` ao `SegmentResult` | ⭐ Baixa |

**Fluxo novo**:
```
POST /v1/segment?mode=person
  → GroundingDINO: classes=["person","woman","man"]
  → Filtering: area < 80% (pessoa pode ser grande), sem nesting filter
  → SAM2: box prompts (manter)
  → Retorna: 1-2 máscaras da pessoa inteira
```

**Decisão chave**: Não criar serviço novo. Modificar SE10 para aceitar `mode=person` via parâmetro.

**Por que não mudar só o SE11?** Porque o SE10 precisa de ajustes no area filter (29% → 80%) e possivelmente thresholds diferentes para pessoa.

### Fase 2 — SE11: Pipeline de Remoção de Pessoa

**Objetivo**: SE11 orquestra SE10 (modo pessoa) → SE8 (inpainting de pessoa).

**Arquivos a modificar**:

| Arquivo | Mudança | Complexidade |
|---------|---------|-------------|
| `se11/.../config.py` | Novos defaults para modo pessoa | ⭐ Baixa |
| `se11/.../http_client.py` | `SE10Client.segment()` aceita `mode="person"`, `SE8Client.inpaint()` usa params para pessoa | ⭐⭐ Média |
| `se11/.../pipeline.py` | `run_person_removal()` — fluxo dedicado | ⭐⭐ Média |
| `se11/.../routes.py` | Novo endpoint ou `mode` field no POST /jobs | ⭐ Baixa |

**Fluxo novo**:
```
SE11: POST /jobs {image, mode="person"}
  │
  ├─ SE10: segment(image, mode="person") → 1-2 masks da pessoa
  │
  ├─ combine_masks() → 1 mask binária da pessoa
  │
  ├─ SE8: inpaint(image, mask, prompt="background", negative="person")
  │  → inpaint_respective_field=1.0 (full image crop)
  │
  ▼
  Resultado: pessoa removida, fundo preservado
```

### Fase 3 — Validação e Testes

**Estratégia de teste**:

1. **Teste SE10 isolado**: Enviar `Test.png` com `classes="person,woman,man"` → verificar se detecta 1 pessoa
2. **Comparação com ground truth**: Comparar máscara do SE10 com `Test_Selected.png` (máscara vermelha)
3. **Teste SE11 completo**: `Test.png` → SE11 → resultado → verificar se pessoa foi removida
4. **Métricas de qualidade**:
   - IoU (Intersection over Union) entre máscara prevista e ground truth
   - Cobertura da máscara (% de pixels da pessoa detectados)
   - Falsos positivos (% de fundo incorretamente mascarado)

**Critérios de aceitação**:
- SE10 detecta ≥1 pessoa com confiança > 0.3
- IoU entre máscara prevista e vermelha > 0.7
- Resultado SE8: pessoa removida, fundo coerente, sem artefatos visíveis
- Tempo total < 60s

---

## Decisões Técnicas

### 1. Color-based vs AI Detection?

| Abordagem | Prós | Contras | Recomendação |
|-----------|------|---------|-------------|
| **Apenas GroundingDINO** | Sem setup extra, funciona para qualquer imagem | Pode falhar em poses incomuns | ✅ Fase 1 |
| **Apenas Color-based** | Rápido, preciso para máscara vermelha | Só funciona com máscara fornecida | ❌ Limitado |
| **Híbrido (Cor + SAM2 points)** | Melhor qualidade, usa ground truth | Mais complexo | ✅ Fase 2 |
| **GroundingDINO + SAM2 points** | Precisão refinada | Mais chamadas | ✅ Fase 2 |

**Decisão**: Começar com **GroundingDINO simples** (Fase 1), depois adicionar **color-based + SAM2 points** (Fase 2).

### 2. Criar novo serviço ou modificar SE10/SE11?

**Decisão**: Modificar SE10 e SE11 existentes. Motivos:
- SE10 já tem toda a infraestrutura (GroundingDINO + SAM2 + API)
- Basta adicionar `mode="person"` como parâmetro
- SE11 já orquestra SE10→SE8
- Evita duplicação de código e manutenção

### 3. Um endpoint SE11 ou dois?

**Decisão**: Um único endpoint `POST /jobs` com campo `mode`:
- `mode="clothes"` (atual, default)
- `mode="person"` (novo)

Isso mantém backward compatibility.

### 4. Prompt do SE8 — O que descrever?

Para remoção de pessoa, o prompt deve descrever o **fundo** que será gerado no lugar:
- `"background, wall, curtain, environment, scenery"`
- Negative: `"person, human, body, skin, clothing, face, hair"`

---

## Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| GroundingDINO não detecta pessoa em poses incomuns | Alto | Testar com múltiplas imagens; usar point prompts como fallback |
| Máscara de pessoa muito grande (>60% imagem) | Médio | Ajustar `inpaint_respective_field=1.0`, usar prompt de fundo descritivo |
| SE8 gera fundo incoerente | Médio | Testar com prompts diferentes; ajustar styles |
| Tempo de processamento alto (>60s) | Baixo | SAM2 com batch prediction; cache de image embedding |
| Breaking change no SE10 API | Baixo | `mode` é opcional, default="clothes" mantém compatibilidade |
| GroundingDINO confunde pessoa com fundo colorido | Médio | Aumentar box_threshold para 0.30-0.35; usar point prompts |

---

## Referências

### Repositórios Oficiais

| Repositório | Stars | Descrição | Link |
|-------------|-------|-----------|------|
| GroundingDINO | 10.3k | Open-set object detection (ECCV 2024) | https://github.com/IDEA-Research/GroundingDINO |
| SAM2 | 19.4k | Segment Anything in Images and Videos | https://github.com/facebookresearch/sam2 |
| Grounded-SAM-2 | 3.6k | Ground + Track Anything (GDINO + SAM2) | https://github.com/IDEA-Research/Grounded-SAM-2 |
| Florence-2 | — | Microsoft vision foundation model | https://huggingface.co/microsoft/Florence-2-large |

### Papers

| Paper | Ano | Contribuição |
|-------|-----|-------------|
| Grounding DINO (arXiv:2303.05499) | 2023/ECCV 2024 | Marrying DINO with Grounded Pre-Training |
| SAM 2 (arXiv:2408.00714) | 2024 | Segment Anything in Images and Videos |
| Grounded SAM (arXiv:2401.14159) | 2024 | Assembling Open-World Models |
| Grounding DINO 1.5 (arXiv:2405.10300) | 2024 | Most Capable Open-World Detector |

### Arquivos do Projeto Referenciados

| Arquivo | Caminho Absoluto |
|---------|-----------------|
| SE10 segmentor | `/root/YTCaption-Easy-Youtube-API/services/se10-clothes-segmentation/app/services/segmentor.py` |
| SE10 constants | `/root/YTCaption-Easy-Youtube-API/services/se10-clothes-segmentation/app/core/constants.py` |
| SE10 routes | `/root/YTCaption-Easy-Youtube-API/services/se10-clothes-segmentation/app/api/routes/segment.py` |
| SE10 models | `/root/YTCaption-Easy-Youtube-API/services/se10-clothes-segmentation/app/domain/models.py` |
| SE11 pipeline | `/root/YTCaption-Easy-Youtube-API/services/se11-clothes-removal/app/services/pipeline.py` |
| SE11 http_client | `/root/YTCaption-Easy-Youtube-API/services/se11-clothes-removal/app/infrastructure/http_client.py` |
| SE11 models | `/root/YTCaption-Easy-Youtube-API/services/se11-clothes-removal/app/core/models.py` |
| SE11 config | `/root/YTCaption-Easy-Youtube-API/services/se11-clothes-removal/app/core/config.py` |
| SE8 worker | `/root/YTCaption-Easy-Youtube-API/services/se8-image-generation/app/services/worker.py` |
| SE8 InpaintWorker | `/root/YTCaption-Easy-Youtube-API/services/se8-image-generation/modules/inpaint_worker.py` |
| SAM2 predictor | `/root/YTCaption-Easy-Youtube-API/services/se10-clothes-segmentation/external/segment-anything-2/sam2/sam2_image_predictor.py` |
| GroundingDINO inference | `/root/YTCaption-Easy-Youtube-API/services/se10-clothes-segmentation/external/GroundingDINO/groundingdino/util/inference.py` |

---

## Próximos Passos (pós-aprovação do plano)

1. **Fase 1**: Modificar SE10 — adicionar `PERSON_CLASSES`, `mode` param, area filter 80%
2. **Fase 1**: Testar SE10 com `Test.png` + `classes="person"` → comparar com `Test_Selected.png`
3. **Fase 2**: Modificar SE11 — `mode="person"`, novos prompts, `inpaint_respective_field=1.0`
4. **Fase 2**: Testar SE11 completo com `Test.png` → verificar remoção de pessoa
5. **Fase 3**: Validação qualitativa + IoU com ground truth
6. **Docker rebuild** de SE10 e SE11 com mudanças persistidas
7. **Atualizar MEMORY.md** com resultados
