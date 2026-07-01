# PLANO MASTER: Implementação Completa no `nsfw_test` (Isolado de Produção)

## Visão Geral da Arquitetura Atual

```
Rota /jobs (mode=nsfw)     → pipeline.py → run_nsfw()           → pipeline_nsfw.py (PRODUÇÃO)
Rota /jobs (mode=nsfw_test) → pipeline.py → run_nsfw_experimental() → pipeline_nsfw_experimental.py (TESTE - ISOLADO)
```

**✅ Zero código compartilhado entre as duas pipelines.** Podemos alterar `nsfw_test` à vontade sem risco à produção.

---

## FASE 1: Preparação - Modelos e Configuração SE8 (Pré-requisito)

### 1.1 Baixar Modelos Fooocus Inpainting no SE8

```bash
# No container SE8 ou volume compartilhado
mkdir -p /root/YTCaption-Easy-Youtube-API/services/se8-image-generation/data/models/inpaint
cd /root/YTCaption-Easy-Youtube-API/services/se8-image-generation/data/models/inpaint

# Fooocus inpaint models (do HuggingFace lllyasviel/fooocus_inpaint)
wget https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/inpaint_v26.fooocus.patch
wget https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/fooocus_lama.safetensors
wget https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/fooocus_inpaint_head.pth
```

### 1.2 Baixar IP-Adapter FaceID + InsightFace no SE8

```bash
mkdir -p /root/YTCaption-Easy-Youtube-API/services/se8-image-generation/data/models/ipadapter
mkdir -p /root/YTCaption-Easy-Youtube-API/services/se8-image-generation/data/models/clip_vision
mkdir -p /root/YTCaption-Easy-Youtube-API/services/se8-image-generation/data/models/insightface

cd /root/YTCaption-Easy-Youtube-API/services/se8-image-generation/data/models/ipadapter
wget https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sdxl.bin

cd /root/YTCaption-Easy-Youtube-API/services/se8-image-generation/data/models/clip_vision
wget https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors

cd /root/YTCaption-Easy-Youtube-API/services/se8-image-generation/data/models/insightface
wget https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip
unzip buffalo_l.zip
```

### 1.3 Atualizar `docker-compose.gpu.yml` do SE8 para montar modelos

```yaml
# Adicionar volumes para modelos
volumes:
  - ./data/models:/app/data/models
  - ./data/models/inpaint:/app/models/inpaint  # se Fooocus espera aqui
  - ./data/models/ipadapter:/app/models/ipadapter
  - ./data/models/clip_vision:/app/models/clip_vision
  - ./data/models/insightface:/app/models/insightface
```

---

## FASE 2: Schema & API - Novos Parâmetros para `nsfw_test`

### 2.1 `app/api/schemas.py` - Adicionar campos experimentais

```python
# Adicionar após face_restore_fidelity (linha ~215)

# NOVOS: Controle experimental nsfw_test
inpaint_mode: Literal["body_mask", "clothes_mask", "invert_mask"] = Field(
    default="body_mask",
    description=(
        "**Máscara de inpainting:**\n"
        "- `body_mask` (padrão v23) — pessoa menos cabeça (corpo todo)\n"
        "- `clothes_mask` — apenas roupas detectadas (Florence-2)\n"
        "- `invert_mask` — **NOVO:** mantém rosto/corpo/fundo, inpinta APENAS roupas"
    ),
    examples=["body_mask"],
)

# NOVOS: IP-Adapter FaceID
use_faceid: bool = Field(
    default=False,
    description="Ativar IP-Adapter FaceID para travar identidade facial durante inpainting.",
)
faceid_weight: float = Field(
    default=0.8,
    ge=0.0,
    le=1.5,
    description="Peso do IP-Adapter FaceID (0.7-1.0 recomendado).",
    examples=[0.8],
)

# NOVOS: Denoising strength específico para nsfw_test
test_inpaint_strength: float = Field(
    default=0.35,
    ge=0.0,
    le=1.0,
    description="Denoising strength para nsfw_test (baixo = preserva estrutura). Padrão 0.35 vs 0.65-0.75 produção.",
    examples=[0.35],
)

# NOVO: Modelo base customizado
base_model: str = Field(
    default="juggernautXL_v8Rundiffusion.safetensors",
    description="Modelo base SDXL. Use 'fooocus_inpaint' para modelos Fooocus inpainting.",
    examples=["juggernautXL_v8Rundiffusion.safetensors", "fooocus_inpaint"],
)
```

### 2.2 `app/api/routes.py` - Passar novos parâmetros no request_data

```python
# No create_job(), adicionar ao request_data (após linha ~348):
"inpaint_mode": inpaint_mode,
"use_faceid": use_faceid,
"faceid_weight": faceid_weight,
"test_inpaint_strength": test_inpaint_strength,
"base_model": base_model,
```

### 2.3 `app/core/models.py` - Adicionar campos no ClothesRemovalJob

```python
# Adicionar campos opcionais (com default None para compatibilidade)
inpaint_mode: str | None = None
use_faceid: bool | None = None
faceid_weight: float | None = None
test_inpaint_strength: float | None = None
base_model: str | None = None
```

---

## FASE 3: SE8 Client - Suporte a IP-Adapter FaceID e Invert Mask

### 3.1 `app/infrastructure/http_client.py` - Estender `SE8Client.inpaint()`

**Novos parâmetros no método `inpaint()`:**

```python
async def inpaint(
    self,
    # ... parâmetros existentes ...
    # NOVOS:
    ip_adapter_faceid_embeds: list | None = None,  # embeddings InsightFace
    ip_adapter_faceid_weight: float = 0.8,
    use_inpaint_model: bool = False,  # True = usa Fooocus inpaint models
    invert_mask: bool = False,  # NOVO: inverte máscara no SE8 (mantém área branca)
) -> dict[str, Any]:
```

**Modificações no payload:**

```python
# Modelo base
if use_inpaint_model:
    payload["base_model_name"] = "fooocus_inpaint"  # ou modelo customizado

# IP-Adapter FaceID embeddings
if ip_adapter_faceid_embeds:
    payload["ip_adapter_faceid_embeds"] = ip_adapter_faceid_embeds
    payload["ip_adapter_faceid_weight"] = ip_adapter_faceid_weight

# Invert mask - SE8 precisa suportar isso
if invert_mask:
    payload["invert_mask"] = True  # ou param equivalente no Fooocus
```

### 3.2 Verificar suporte SE8 para `invert_mask` e `ip_adapter_faceid_embeds`

- Verificar em `services/se8-image-generation/app/api/generate_v2_routes.py` ou `generate_routes.py`
- Se não existir, adicionar no SE8 (Fase 5)

---

## FASE 4: Nova Pipeline Experimental - `pipeline_nsfw_experimental_v2.py`

### 4.1 Estratégia: Criar arquivo NOVO (não modificar o atual)

```
pipeline_nsfw_experimental.py        ← MANTER (versão atual v23.4 para comparação)
pipeline_nsfw_experimental_v2.py     ← NOVA (todas as melhorias)
```

### 4.2 Pipeline `run_nsfw_experimental_v2()` - Fluxo Completo

```python
async def run_nsfw_experimental_v2(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """
    NSFW Experimental v2 — Invert Mask + Low Denoise + FaceID
    
    FLUXO:
    1. SE10: Person detection (já existe)
    2. SE10: Clothes detection (Florence-2) → máscara ROUPAS
    3. INVERT: máscara final = pessoa - roupas = "manter rosto/corpo/fundo"
    4. InsightFace: extrair embedding facial da imagem original
    5. SE8: Inpaint com:
       - mask = clothes_mask (área a regenerar)
       - invert_mask = True (SE8 inpinta onde máscara=branco)
       - inpaint_strength = 0.35 (baixo)
       - ip_adapter_faceid_embeds = embedding do rosto original
       - ip_adapter_faceid_weight = 0.8
       - base_model = fooocus_inpaint
       - ControlNet OpenPose (opcional, weight 0.5)
    6. SEM face crop/paste (FaceID preserva identidade nativamente)
    7. OPCIONAL: SE8 face restore (CodeFormer) para unificar textura
    8. OPCIONAL: Laplacian blend apenas na borda roupa/corpo se necessário
    9. Pose validation (já existe)
    """
```

### 4.3 Mudanças Críticas vs Pipeline Atual

| Atual (`pipeline_nsfw_experimental.py`) | Novo v2 |
|---|---|
| `body_mask = person - head` (inpinta corpo todo) | `clothes_mask` do Florence-2 (inpinta SÓ roupas) |
| `inpaint_strength = 0.65-0.75` | `inpaint_strength = 0.35` |
| Face protection: `head_mask` + `face_protect_mask` + crop/paste | **Invert mask** + **IP-Adapter FaceID** (sem crop/paste) |
| IP-Adapter: clothes-neutral ref (pose/body) | IP-Adapter FaceID (rosto) + clothes-neutral ref (pose/body) |
| Modelo: `juggernautXL_v8Rundiffusion` | Modelo: `fooocus_inpaint` |
| Blend: Laplacian/alpha (pós-hoc) | Blend mínimo (só borda roupa/corpo se necessário) |

### 4.4 Código: Detecção de Roupas → Máscara Invertida

```python
# Stage 3: SE10 Clothes Detection (Florence-2) - JÁ EXISTE
clothes_seg = await se10.segment(
    image_bytes=image_bytes,
    filename=f"{job.job_id}_clothes.jpg",
    classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, coat, hoodie, t-shirt",
    box_threshold=0.06, text_threshold=0.04,
    mode="clothes", detector="florence2",
)

# Combinar todas as máscaras de roupa
clothes_mask = combine_clothes_masks(clothes_seg)  # helper novo

# INVERT: máscara final = pessoa - roupas (área a MANTER)
# SE8 inpinta onde máscara=BRANCO, então passamos clothes_mask diretamente
# OU usamos invert_mask=True no SE8 se ele suportar

# Máscara para SE8 = clothes_mask (região a regenerar)
inpaint_mask = clothes_mask.copy()

# Expansão leve para cobrir bordas
inpaint_mask = dilate_mask(inpaint_mask, kernel_size=15, iterations=1)
```

### 4.5 Código: InsightFace Embedding Extraction

```python
# NOVA FUNÇÃO (adicionar no pipeline ou head_detector)
def extract_faceid_embedding(orig_img, person_binary):
    """Extrai embedding InsightFace (512-d) para IP-Adapter FaceID."""
    import insightface
    import numpy as np
    
    app = insightface.app.FaceAnalysis(name='buffalo_l', root='/app/models/insightface')
    app.prepare(ctx_id=0, det_size=(640, 640))
    
    # Detectar faces na imagem original
    faces = app.get(orig_img)
    if not faces:
        logger.warning("InsightFace: nenhuma face detectada")
        return None
    
    # Pegar maior face dentro da pessoa
    best_face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
    
    # Embedding normalizado (512-d)
    embedding = best_face.normed_embedding  # shape (512,)
    return embedding.astype(np.float32).tolist()
```

### 4.6 Chamada SE8 com FaceID

```python
# Extrair embedding ANTES do loop de tentativas
faceid_embedding = extract_faceid_embedding(orig_img, person_binary)

for attempt in range(1, max_attempts + 1):
    # Config progressiva (menor denoise = mais preservação)
    strength = job.request.test_inpaint_strength or 0.35
    if attempt > 1:
        strength += 0.05 * (attempt - 1)  # 0.35 → 0.40 → 0.45
    
    result = await se8.inpaint(
        image_b64=image_b64,
        mask_b64=mask_b64,
        prompt=final_prompt,
        negative_prompt=final_negative,
        inpaint_strength=strength,
        inpaint_respective_field=0.55,  # crop mais apertado
        inpaint_erode_or_dilate=0,
        loras=nsfw_loras,
        image_prompts=[
            # IP-Adapter 1: Clothes-neutral ref (pose/body preservação)
            {"cn_img": ip_ref_b64, "cn_stop": 0.5, "cn_weight": 0.8, "cn_type": "ImagePrompt"},
            # IP-Adapter 2: OpenPose ControlNet (estrutura corporal)
            {"cn_img": pose_cn_b64, "cn_stop": 0.6, "cn_weight": 0.5, "cn_type": "OpenPose"},
            # IP-Adapter 3: FaceID (IDENTIDADE FACIAL) - NOVO
            {"cn_img": None, "cn_stop": 1.0, "cn_weight": faceid_weight, "cn_type": "FaceID"},
        ],
        base_model="fooocus_inpaint",  # NOVO
        # NOVOS PARÂMETROS:
        ip_adapter_faceid_embeds=[faceid_embedding] if faceid_embedding else None,
        ip_adapter_faceid_weight=job.request.faceid_weight or 0.8,
        invert_mask=True,  # NOVO: máscara = roupas (branco = regenerar)
    )
```

---

## FASE 5: Mudanças no SE8 (Backend de Geração)

### 5.1 SE8: Suportar `invert_mask` e `ip_adapter_faceid_embeds`

**Arquivos a modificar no SE8:**
- `app/api/generate_v2_routes.py` ou `generate_routes.py` - endpoint `/image-inpaint-outpaint`
- `app/api/api_utils.py` - processamento do payload
- `app/services/worker.py` - `_apply_inpaint()` e `InpaintWorker`
- `modules/inpaint_worker.py` - lógica de máscara

### 5.2 SE8: Carregar Modelos Fooocus Inpainting + IP-Adapter FaceID

**Em `app/main.py` ou módulo de inicialização:**

```python
# Carregar Fooocus inpaint models
fooocus_inpaint_model = load_fooocus_inpaint(
    patch_path="data/models/inpaint/inpaint_v26.fooocus.patch",
    lama_path="data/models/inpaint/fooocus_lama.safetensors",
    head_path="data/models/inpaint/fooocus_inpaint_head.pth",
)

# Carregar IP-Adapter FaceID
ip_adapter_faceid = load_ip_adapter_faceid(
    model_path="data/models/ipadapter/ip-adapter-faceid-plusv2_sdxl.bin",
    clip_vision_path="data/models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    insightface_root="data/models/insightface",
)
```

### 5.3 SE8: InpaintWorker - Aplicar FaceID Embeddings

No `InpaintWorker.__init__` ou método de processamento:

```python
# Se ip_adapter_faceid_embeds fornecido:
if ip_adapter_faceid_embeds:
    # Aplicar FaceID conditioning via IP-Adapter
    # Usar insightface embeddings diretamente no cross-attention
    self.apply_faceid_conditioning(ip_adapter_faceid_embeds, weight)
```

### 5.4 SE8: Invert Mask Logic

No processamento de máscara (antes de passar para InpaintWorker):

```python
if invert_mask:
    # Máscara original: branco = roupas (área a regenerar)
    # Fooocus espera: branco = manter, preto = regenerar
    # ENTÃO invertemos: mask = 255 - mask
    mask = 255 - mask
```

---

## FASE 6: Integração no Dispatcher (`pipeline.py`)

### 6.1 Adicionar nova rota experimental

```python
# Em pipeline.py, no dispatcher run_clothes_removal():

elif mode == "nsfw_test":
    # Verificar se quer v2 (pode ser via parâmetro ou feature flag)
    if job.request.get("use_experimental_v2", False):
        from app.services.pipeline_nsfw_experimental_v2 import run_nsfw_experimental_v2
        await run_nsfw_experimental_v2(job, store)
    else:
        from app.services.pipeline_nsfw_experimental import run_nsfw_experimental
        await run_nsfw_experimental(job, store)
```

### 6.2 Adicionar parâmetro `use_experimental_v2` no schema (opcional)

```python
# Em schemas.py
use_experimental_v2: bool = Field(
    default=False,
    description="Usar pipeline experimental v2 (invert mask + FaceID).",
)
```

---

## FASE 7: Debug & Validação

### 7.1 Salvar Máscaras de Debug (já faz, verificar)

```python
# Em pipeline_nsfw_experimental_v2.py
cv2.imwrite(f"{try_dir}/01_person.png", person_binary)
cv2.imwrite(f"{try_dir}/02_clothes_mask.png", clothes_mask)
cv2.imwrite(f"{try_dir}/03_inpaint_mask.png", inpaint_mask)
cv2.imwrite(f"{try_dir}/04_faceid_embedding.npy", faceid_embedding)  # se tiver
```

### 7.2 Grid de Comparação Automatizado

```python
# No final, gerar grid comparativo:
panels = [
    ("original", orig_img, "1. Original"),
    ("clothes_mask", clothes_mask, "2. Clothes Mask (Florence-2)"),
    ("inpaint_mask", inpaint_mask, "3. Inpaint Mask (invertido)"),
    ("result", result, f"4. Result (strength={strength}, FaceID={faceid_weight})"),
]
if has_face_restore:
    panels.append(("restored", restored, "5. Face Restored"))
grid = build_debug_grid(panels)
cv2.imwrite(f"{output_dir}/{job_id}_comparison.png", grid)
```

---

## FASE 8: Testes e Critérios de Sucesso

### 8.1 Testes Automatizados (script)

```bash
# test_nsfw_test_v2.sh
#!/bin/bash
curl -X POST http://localhost:8011/jobs \
  -H "X-API-Key: se11-test-key-2026" \
  -F "file=@test_images/model1.jpg" \
  -F "mode=nsfw_test" \
  -F "inpaint_mode=invert_mask" \
  -F "use_faceid=true" \
  -F "faceid_weight=0.8" \
  -F "test_inpaint_strength=0.35" \
  -F "base_model=fooocus_inpaint" \
  -F "face_restore=true" \
  -F "face_restore_model=CodeFormer" \
  -F "face_restore_fidelity=0.5"
```

### 8.2 Métricas de Validação

| Métrica | Threshold Sucesso |
|---|---|
| Pose validation score (MediaPipe) | < 5.0 (atual ~11.8 v23.4) |
| Face identity (InsightFace cosine sim original vs result) | > 0.85 |
| Clothes removal completeness (visual) | 100% sem resíduos |
| Skin tone consistency (face vs body) | ΔE < 10 em LAB |
| No face displacement | Verificação visual + landmarks |

### 8.3 Comparação Side-by-Side

```bash
# Rodar mesma imagem em 3 configs:
1. nsfw (produção atual) → baseline
2. nsfw_test (v1 atual) → intermediário  
3. nsfw_test (v2 novo) → target

# Copiar resultados para show/
cp /data/outputs/cr_*/result.png /root/YTCaption-Easy-Youtube-API/show/v24_nsfw_prod.png
cp /data/outputs/cr_*/result.png /root/YTCaption-Easy-Youtube-API/show/v24_nsfw_test_v1.png
cp /data/outputs/cr_*/result.png /root/YTCaption-Easy-Youtube-API/show/v24_nsfw_test_v2.png
```

---

## CRONOGRAMA ESTIMADO

| Fase | Atividade | Tempo | Dependência |
|---|---|---|---|
| 1 | Baixar/configurar modelos SE8 | 30 min | - |
| 2 | Schema + Routes + Models (SE11) | 1 hora | - |
| 3 | SE8 Client updates | 1 hora | Fase 1 |
| 4 | Pipeline v2 (core logic) | 3-4 horas | Fases 2,3 |
| 5 | SE8 backend changes | 2-3 horas | Fase 1 |
| 6 | Dispatcher integration | 30 min | Fase 4 |
| 7 | Debug grids + testes | 1-2 horas | Fase 6 |
| 8 | Validação + iteração | 2-4 horas | Fase 7 |
| **TOTAL** | | **~12-16 horas** | |

---

## ARQUIVOS A CRIAR/MODIFICAR

### SE11 (Clothes Removal) - NOVOS
- `app/services/pipeline_nsfw_experimental_v2.py` — **NOVO** (pipeline completo v2)
- `app/services/faceid_extractor.py` — **NOVO** (InsightFace embedding extraction)

### SE11 - MODIFICAÇÕES
- `app/api/schemas.py` — +5 campos novos
- `app/api/routes.py` — passar novos campos
- `app/core/models.py` — +5 campos opcionais
- `app/infrastructure/http_client.py` — SE8Client.inpaint() estendido
- `app/services/pipeline.py` — dispatcher para v2

### SE8 (Image Generation) - MODIFICAÇÕES
- `app/api/generate_v2_routes.py` — suporte `invert_mask`, `ip_adapter_faceid_embeds`
- `app/services/worker.py` — passar parâmetros para InpaintWorker
- `modules/inpaint_worker.py` — aplicar FaceID conditioning + invert mask
- `app/main.py` — carregar modelos Fooocus + IP-Adapter FaceID no startup
- `docker/docker-compose.gpu.yml` — volumes para modelos

---

## RISCOS E MITIGAÇÕES

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| SE8 não suporta `invert_mask` nativamente | Alta | Alto | Implementar no SE8 worker (inversão simples: `mask = 255 - mask`) |
| IP-Adapter FaceID não carrega no SE8 | Média | Alto | Testar carregamento isolado antes; fallback para pipeline sem FaceID |
| Fooocus inpaint models incompatíveis com pipeline SE8 | Média | Médio | Verificar API SE8; se não funcionar, manter Juggernaut + denoise baixo |
| InsightFace não detecta face em algumas imagens | Baixa | Médio | Fallback: usar Haar cascade bbox para FaceID embedding aproximado |
| Memória GPU insuficiente (Fooocus + FaceID + InsightFace) | Média | Alto | Carregar modelos lazy; quantizar se necessário; RTX 3090 24GB deve aguentar |

---

## PRÓXIMO PASSO IMEDIATO

**Quer que eu comece pela Fase 1 (modelos SE8) + Fase 2 (schema/routes)?**

Ou prefere que eu inicie pela **Fase 4 (pipeline_nsfw_experimental_v2.py)** assumindo que os modelos já estão no lugar? A Fase 4 é o coração da mudança e pode ser desenvolvida/testada com mock do SE8 client primeiro.

**Decisão necessária:**
1. Começar do backend (SE8 modelos + API) → depois pipeline SE11
2. Começar do pipeline SE11 (mockando SE8) → depois backend SE8
3. Paralelo: eu faço pipeline SE11, você/outro agente faz SE8

---

## DECISÕES PENDENTES (Preciso da Sua Opinião)

1. **Nome do modelo base no schema**: `"fooocus_inpaint"` vs `"fooocus_inpaint_v26"` vs custom string?
2. **FaceID weight default**: 0.8 (conservador) ou 1.0 (máximo travamento)?
3. **Test_inpaint_strength**: 0.35 fixo ou range 0.3-0.4 progressivo?
4. **Manter clothes-neutral IP-Adapter ref?** Sim (preserva pose/corpo) + FaceID (preserva rosto) = dual conditioning
5. **ControlNet OpenPose**: manter weight 0.5 stop 0.6 ou ajustar?
6. **Face restore obrigatório no v2?** Default `false`, opcional `true` para comparação
