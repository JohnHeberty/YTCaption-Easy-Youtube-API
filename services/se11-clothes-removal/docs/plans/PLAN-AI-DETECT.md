# PLAN-AI-DETECT.md — Detecção Real vs IA (Anti-Fotos Reais)

**Data:** 2026-07-05
**Status:** Planejado
**Prioridade:** Alta (proteção ética/legal)

---

## Objetivo
Impedir que fotos de pessoas reais entrem na pipeline NSFW. Rejeitar com erro 400 antes de qualquer processamento.

## Modelo: Bombek1/ai-image-detector-siglip-dinov2

| Atributo | Valor |
|----------|-------|
| Acurácia | 99.10% (AUC 0.9997) |
| Params | ~740M |
| Cobertura | SDXL, SD 1.5/2.1/3.5, Midjourney, DALL-E 3, Flux, GPT-Image-1 + mais 19 geradores |
| Robusto | Treinado com compressão JPEG, blur, noise |
| Performance | ~5-15s por imagem (CPU) |
| HF URL | `https://huggingface.co/Bombek1/ai-image-detector-siglip-dinov2` |

---

## Arquivos a criar/modificar

### 1. NOVO: `app/services/ai_image_detector.py`
- Lazy-loader singleton (mesmo padrão do InsightFace/Haarcascade)
- `async def check_image_is_ai_generated(image_bytes: bytes) -> bool`
- Carrega modelo na primeira chamada, reutiliza nas seguintes
- Retorna `True` se imagem é gerada por IA (OK para NSFW), `False` se é foto real (REJEITAR)
- Log: confidence score em cada chamada

### 2. MODIFICAR: `app/api/routes.py`
- `create_nsfw_job()` (linha ~398): Após validação de tipo/tamanho, ANTES de criar o job
- `create_nsfw_test_job()` (linha ~556): Mesmo ponto
- `create_job()` (linha ~273): NÃO modificar (rota geral não é NSFW)
- Se `check_image_is_ai_generated(content) == False` → `HTTPException(400, "Real person photo detected. NSFW processing is only allowed for AI-generated images.")`

### 3. MODIFICAR: `requirements.txt`
- Adicionar: `timm`, `peft` (Bombek1 dependencies)

### 4. MODIFICAR: `docker/Dockerfile`
- Adicionar `timm` e `peft` ao pip install

---

## Fluxo alterado

```
POST /jobs/nsfw
  │
  ├─ Validar tipo (PNG/JPEG/WebP)          ← existente
  ├─ Validar tamanho (max 20MB)             ← existente
  ├─ 🆕 check_image_is_ai_generated()       ← NOVO
  │   └─ Se REAL → 400 "Real person photo detected"
  ├─ Criar job, salvar Redis                ← existente
  └─ Worker start                           ← existente
```

---

## Performance

- **Primeira chamada:** ~10-20s (download do modelo + inferência)
- **Chamadas seguintes:** ~5-15s (inferência apenas)
- **Aceitável:** Pre-check antes do pipeline principal (que leva 300-600s)

## Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Falso positivo (IA → real) | Usuário não processa imagem válida | 99.1% acurácia minimiza |
| Falso negativo (real → IA) | Foto real passa para pipeline | 99.1% acurácia minimiza |
| Modelo grande (740M) | Lentidão no pre-check | Aceitável: 5-15s vs 300-600s do pipeline |

## Validação

1. Testar com imagem gerada por SE8 (deve retornar True/OK)
2. Testar com foto real de pessoa (deve retornar False/rejeitar)
3. Testar com imagem comprimida de rede social (deve funcionar)
4. Verificar que pipeline normal não é afetada

---

## Referências

| Arquivo | Caminho |
|---------|---------|
| Roadmap | `services/se11-clothes-removal/docs/ROADMAP.md` |
| Lições NSFW | `services/se11-clothes-removal/docs/LICOES-NSFW.md` |
| Detector module | `app/services/ai_image_detector.py` (a criar) |
| Routes | `app/api/routes.py` |
