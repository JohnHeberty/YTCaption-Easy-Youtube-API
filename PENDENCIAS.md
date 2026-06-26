# PENDENCIAS.md — Items Pendentes

**Data:** 2026-06-26
**Última atualização:** Consolidação de todos os .md files

---

## NSFW Pipeline

### 1. Haarcascade adaptive head detection
- **Problema:** Top 40% fixo funciona para close-up mas não para full body
- **Solução:** OpenCV Haarcascade (CPU, ~10ms, zero dependências novas)
- **Spec completa:** `docs/archived/PLAN-2.md`
- **Impacto:** Melhoria na proteção facial
- **Status:** PENDENTE

### 2. GFPGAN/CodeFormer face restore
- **O que:** Face restore pós-inpainting
- **Modelos:** Já baixados em `data/models/face_restore/`
- **Complexidade:** MÉDIA
- **Status:** PENDENTE

### 3. Testar dilatação 5-10%
- **Problema:** 3.5% pode ser pouco para certas imagens
- **Solução:** Testar 5%, 7%, 10% e comparar
- **Status:** PENDENTE

---

## SE8 Image Engine

### 4. SE8 CUDA assertion mitigation
- **Problema:** CUDA assertion intermitente (RTX 3090)
- **Solução:** Investigar GPU driver ou adicionar restart gracioso
- **Status:** PENDENTE

### 5. Color matching improvement
- **O que:** Testar `inpaint_disable_initial_latent` ou color correction pós-processamento
- **Status:** PENDENTE

---

## Integração

### 6. Integração SE11 ao SE1 ou APIs externas
- **O que:** SE1 não chama SE11 automaticamente
- **Pré-requisito:** SE1 precisa de fix (atualmente unhealthy)
- **Status:** PENDENTE

---

## SE10 Detection

### 7. SAHI high-res tiling
- **O que:** Para imagens >1024px, GroundingDINO pode perder objetos pequenos
- **Dependência:** `sahi` pip package
- **Status:** PENDENTE (não testado)

---

## SE9 Make Video

### 8. Ken Burns animation improvement (5 camadas)
- **Camada 1:** Ken Burns com Easing (substitui zoom linear)
- **Camada 2:** Vignette Animado
- **Camada 3:** Brilho/Saturação Dinâmica
- **Camada 4:** Focal Point Zoom
- **Camada 5:** Variação de Velocidade por Cena
- **Spec completa:** `SE9-UP.md`
- **Status:** PENDENTE (planejado, não implementado)

---

## Referências

| Arquivo | Caminho |
|---------|---------|
| Pipeline NSFW | `docs/archived/PLAN.md` |
| Spec haarcascade | `docs/archived/PLAN-2.md` |
| Spec SE9 animação | `services/se9-make-video-img/docs/SE9-UP.md` |
| Lições aprendidas | `LIÇÕES.md` |
