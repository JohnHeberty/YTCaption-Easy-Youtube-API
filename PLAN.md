# PLAN.md — Próximos Passos: Investigação NSFW

**Data:** 2026-06-23  
**Status:** pipe_3layers_max v5 funcional — NÃO é 100% NSFW  
**Objetivo:** Atingir remoção 100% de roupa

---

## Estado Atual

pipe_3layers_max v5: Face=1.000, Bot=72.2%, Torso=32.5%  
**Resultado: remoção PARCIAL.** O modelo gera pele mas não remove 100% da roupa.

---

## Próximos Passos (por prioridade)

### Prioridade 1: Multi-pass agressivo
- **Objetivo:** Aumentar remoção de 72% para 85%+
- **Abordagem:** 3-4 passes com denoise crescente (0.75 → 0.70 → 0.65 → 0.50)
- **Cada passo:** detecta roupa restante → inpaint → compor → próximo
- **Complexidade:** MÉDIA
- **Risco:** CUDA assertion (mas pode ser mitigado com restart entre passes)

### Prioridade 2: Denoise mais alto
- **Objetivo:** Forçar mais mudança por passagem
- **Abordagem:** Pass 1: 0.85, Pass 2: 0.55
- **Risco:** ALTO — pode degradar corpo/pele
- **Complexidade:** BAIXA (só trocar números)

### Prioridade 3: Modelo NSFW专用 melhor
- **Objetivo:** Modelo treinado para remover roupa completamente
- **Abordagem:** Baixar modelo mais agressivo (ex: AnythingDiffusion, CyberRealistic)
- **Complexidade:** ALTA (precisa pesquisar e testar compatibilidade)
- **Risco:** MÉDIO

### Prioridade 4: ControlNet + DensePose
- **Objetivo:** Guia o inpainting com pose 3D do corpo
- **Abordagem:** DensePose extrai mapa de pose → ControlNet guia geração
- **Complexidade:** MUITO ALTA
- **Risco:** ALTO (muitos componentes)

### Prioridade 5: API externa NSFW
- **Objetivo:** Usar modelo dedicado para NSFW
- **Abordagem:** Replicate/fal.ai com pipeline customizada
- **Complexidade:** MÉDIA
- **Risco:** BAIXO (mas custo e latência)

---

## O que já funciona bem

1. ✅ Preservação de rosto (100%)
2. ✅ Preservação de fundo (100%)
3. ✅ Máscaras precisas (SE10 reais)
4. ✅ Skin color reference (pele exposta como referência)
5. ✅ Debug visualization (6 máscaras salvas)
6. ✅ Pipeline documentado (TOP-MASK-CONFIG.md)

---

## O que falta

1. ❌ Remoção 100% NSFW
2. ❌ Modelo que gere pele SEM gerar roupa
3. ❌ Multi-pass sem CUDA assertion
4. ❌ GFPGAN face restore integrado
5. ❌ Real-ESRGAN para qualidade final
