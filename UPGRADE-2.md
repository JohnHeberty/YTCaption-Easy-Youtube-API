# UPGRADE-2.md — NSFW Pendências Activas

**Data:** 2026-06-23
**Status:** v15 em produção + nsfw_test V4 implementado (não testado)

---

## Pendências activas

### 1. TESTAR nsfw_test V4 mask logic
- **O que:** executar `mode="nsfw_test"` com Test.png
- **O que validar:** alças no ombro são removidas? face preservada? fundo intacto?
- **Quando:** pedido pelo utilizador — aguarda confirmação

### 2. PLAN-2: Detecção adaptativa de cabeça
- **O que:** substituir 40% fixo por haarcascade (OpenCV)
- **Porquê:** funciona para close-up mas não para full body (40% é muito)
- **Referência:** `PLAN-2.md`

### 3. Promover nsfw_test para produção
- **O que:** unificar `_run_nsfw_test()` → `_run_pipe_nsfw_3layers_max()`
- **Condição:** só após teste V4 e PLAN-2 aprovados

### 4. GFPGAN/CodeFormer face restore
- **O que:** integrar face restore pós-inpainting para melhorar rostos
- **Modelos:** já baixados em `data/models/face_restore/`
- **Complexidade:** MÉDIA
