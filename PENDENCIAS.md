# PENDENCIAS.md — Items Pendentes

**Data:** 2026-06-28
**Última atualização:** NSFW quality cycle + Fooocus params

---

## NSFW Pipeline

### 1. Haarcascade adaptive head detection
- **Status:** ✅ IMPLEMENTADO

### 2. Face ghost no pescoço (PRÓXIMO)
- **Problema:** SE8 gera segundo rosto onde máscara de roupa encontra face protegida
- **Causa:** Prompt NSFW força anatomia em regiões de transição
- **Solução:** Ajustar prompt para ser específico por região, ou usar inpaint em 2 passes (corpo primeiro, depois pele do pescoço com prompt neutro)
- **Status:** PENDENTE

### 3. Artefatos de borda (PRÓXIMO)
- **Problema:** Restos de roupa nas laterais quando detecção não cobre 100%
- **Causa:** Dilatação ainda insuficiente para bordas onde rouca se encontra com background
- **Solução:** Dilatação adaptativa baseada na complexidade da máscara ou multi-pass mask refinement
- **Status:** PENDENTE

### 4. SE8 CUDA assertion com 60 steps (PRÓXIMO)
- **Problema:** 60 steps x 3 tries causa CUDA assertion na RTX 3090
- **Causa:** GPU memory overflow com tentativas sequenciais de alta qualidade
- **Solução:** Reduzir steps para 40 ou adicionar delay/restart entre tries
- **Status:** PENDENTE

### 5. GFPGAN/CodeFormer face restore
- **O que:** Face restore pós-inpainting
- **Modelos:** Já baixados em `data/models/face_restore/`
- **Complexidade:** MÉDIA
- **Status:** PENDENTE

### 6. Pose validation fix
- **Problema:** pose_validator retorna vazio, todos os scores = 0.0
- **Causa:** JSON parse error no subprocess
- **Status:** PENDENTE

---

## ✅ Implementados nesta sessão

| Item | Status |
|------|--------|
| Haarcascade adaptive head detection | ✅ |
| Debug grid 3x3 (8 painéis) | ✅ |
| Masks individuais (00-07) | ✅ |
| Person mask hole fill (floodFill) | ✅ |
| Head mask bottom clip (não cresce para corpo) | ✅ |
| CFG Scale 4.0 → 7.0 (Fooocus match) | ✅ |
| Steps 40 → 60 (Fooocus Quality) | ✅ |
| Sampler → dpmpp_2m_sde_gpu | ✅ |
| Strength 0.65 → 0.85/0.90/1.00 | ✅ |
| Clothes-only inpaint mask strategy | ✅ |
| LAB color transfer (skin tone match) | ✅ |
| Face-only protection (haarcascade small) | ✅ |
| Clothes classes expanded (skirt, pants, etc.) | ✅ |
| Pipeline separation (prod vs test) | ✅ |
| SE11 API refactoring (15→23 schemas) | ✅ |
| Swagger: file upload + dropdowns + auth | ✅ |
| POLITICA-USO.md + README.md | ✅ |
| SE4 field name fix (transcription bug) | ✅ |

---

## Referências

| Arquivo | Caminho |
|---------|---------|
| Pipeline NSFW | `docs/archived/PLAN.md` |
| Spec haarcascade | `docs/archived/PLAN-2.md` |
| Spec SE9 animação | `services/se9-make-video-img/docs/SE9-UP.md` |
| Lições aprendidas | `LIÇÕES.md` |
| Política de uso | `services/se11-clothes-removal/POLITICA-USO.md` |
