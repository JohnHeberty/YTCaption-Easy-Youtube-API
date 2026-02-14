# 🗺️ Roadmap: Sprints para ≥90% Precisão em OCR Detection

**Objetivo estratégico**: Alcançar precisão ≥90% mantendo viabilidade em produção

**Versão**: 2.0  
**Data**: 2026-02-13  
**Status**: Em planejamento

> **ATUALIZAÇÃO v2.0**: Roadmap expandido para incluir Sprint 00 (baseline/dataset) como **BLOQUEADOR CRÍTICO**, e Sprints 09-10 como **Fase 2** (continuous training + features avançadas).

---

## 📊 Diagnóstico Baseline

| Métrica | Status Atual | Alvo | Gap |
|---------|-------------|------|-----|
| **Precisão** | ~70-75% | ≥90% | +15-20% |
| **Recall** | ~65% | ≥85% | +20% |
| **FPR (False Positive Rate)** | ~5-8% | <3% | -2-5% |
| **Latência (50º percentil)** | ~5-10s | <8s | -0-2s |
| **Temporal consistency** | ❌ Inexistente | ✅ Implementado | - |
| **Dynamic resolution** | ❌ Fixo 1080p | ✅ Dinâmico | - |
| **ROI optimization** | ❌ Full frame | ✅ Bottom 70% | - |

---

## 🎯 Mapa de Sprints (Ordem de Impacto)

### 📦 FASE 0: Infraestrutura (BLOQUEADOR)

### Sprint 00: Baseline + Dataset + Evaluation Harness ⭐⭐⭐⭐⭐
**Impacto esperado**: Foundation (baseline + dataset + CI/CD gates) | Criticidade: **CRÍTICO BLOQUEADOR**  
**Status**: **DEVE SER EXECUTADA PRIMEIRO**  
**Dependências**: Nenhuma

Problema: Sem dataset + baseline + harness, não há como provar "sem regressão" ou validar impacto  
Solução: Criar holdout test set (200 vídeos), medir baseline, implementar gates CI/CD  
Esforço: ~1-2 semanas (anotação + scripts)  
Risco: ALTO se não fizer (data leakage, overfit, sem fonte de verdade)  

> **⚠️ CRÍTICO**: Sprint 00 é **BLOQUEADOR** para Sprints 06-07 (treino/calibração) e **recomendada** para todas as outras (validação de impacto).

---

### 📦 FASE 1: Core Improvements (Sprints 01-08)

### Sprint 01: Dynamic Resolution Fix ⭐⭐⭐⭐⭐
**Impacto esperado**: +8-12% (precision) | Criticidade: ALTO  
**Status**: Planejado  
**Dependências**: Nenhuma

Problema: Código assume 1080p fixo, quebra em 720p/4K/vertical/cropped  
Solução: Calcular bottom_threshold dinamicamente a partir da resolução real  
Esforço: ~4h  
Risco: BAIXO (não quebra lógica existente)  

---

### Sprint 02: ROI Dynamic Implementation ⭐⭐⭐⭐⭐
**Impacto esperado**: +10-15% (precision/recall) | Criticidade: ALTO  
**Status**: Pendente Sprint 01  
**Dependências**: Sprint 01

Problema: OCR processa frame inteiro (títulos, logos, HUD, créditos geram FP)  
Solução: Processar apenas bottom 70-100% da altura antes de OCR  
Esforço: ~6h  
Risco: MÉDIO (pode perder legendas no top em raros casos)  

---

### Sprint 03: Preprocessing Optimization ⭐⭐⭐⭐
**Impacto esperado**: +5-10% (recall) | Criticidade: ALTO  
**Status**: Pendente Sprint 02  
**Dependências**: Sprint 02

Problema: Binarização agressiva prejudica PaddleOCR (treinado em imagens naturais)  
Solução: Remover binarização ou usar CLAHE somente com grayscale  
Esforço: ~5h  
Risco: MÉDIO (precisa testing com múltiplas resoluções)  

---

### Sprint 04: Feature Extraction (Structured) ⭐⭐⭐⭐
**Impacto esperado**: +3-5% (preparação para classifier) | Criticidade: MÉDIO  
**Status**: Pendente Sprint 03  
**Dependências**: Sprint 03

Problema: Heurísticas fixas não exploram características do dataset  
Solução: Extrair features por frame (avg_conf, position, density, text_length)  
Esforço: ~8h  
Risco: BAIXO (features adicionais não quebram pipeline)  

---

### Sprint 05: Temporal Aggregation (2-Frame Window) ⭐⭐⭐⭐⭐
**Impacto esperado**: +8-15% (recall + precision) | Criticidade: CRÍTICO  
**Status**: Pendente Sprint 04  
**Dependências**: Sprint 04

Problema: Sem modelagem temporal; legendas reais persistem 1-3s (múltiplos frames)  
Solução: Aggregar confiança em janela de 2-3 frames; rastrear consistência textual  
Esforço: ~10h  
Risco: MÉDIO (aumenta latência ~20-30%)  

---

### Sprint 06: Lightweight Classifier (LogReg/XGBoost) ⭐⭐⭐⭐
**Impacto esperado**: +5-12% (melhor uso de features) | Criticidade: ALTO  
**Status**: Pendente Sprint 05  
**Dependências**: Sprint 05

Problema: Multiplicadores arbitrários (1.3x, 1.1x) não calibrados; saturação artificial  
Solução: Treinar regressão logística leve em features extraídas (treino: ~100 amostras)  
Esforço: ~12h  
Risco: MÉDIO (necessário dataset de validação)  

---

### Sprint 07: ROC Calibration & Threshold Tuning ⭐⭐⭐⭐
**Impacto esperado**: +2-5% (threshold ótimo) | Criticidade: MÉDIO  
**Status**: Pendente Sprint 06  
**Dependências**: Sprint 06

Problema: Threshold 0.85 não é calibrado; pode ser subótimo  
Solução: Gerar curva ROC; encontrar threshold que maximize F1/precision em dataset  
Esforço: ~6h  
Risco: BAIXO (apenas tuning, lógica não muda)  

---

### Sprint 08: Validation, Regression Testing & Production ⭐⭐⭐⭐
**Impacto esperado**: 0% (validação) | Criticidade: CRÍTICO  
**Status**: Pendente Sprint 07  
**Dependências**: Sprint 07

Problema: Sem validação formal; sem teste de regressão  
Solução: Teste em dataset hold-out; comparar baseline vs novo; AB test em produção  
Esforço: ~8h  
Risco: ALTO se não fizer bem (regressão em produção)  

---

## 📈 Impacto Cumulativo Estimado

### Fase 1 (Core - Sprints 00-08)

| Sprint | Delta Est. | Acumulado | Baseline Esperado |
|--------|-----------|-----------|------------------|
| Baseline | - | 72% | 72% |
| **Sprint 00** | **Foundation** | **72%** | **Baseline medido** ✅ |
| Sprint 01 | +10% | 82% | 82% |
| Sprint 02 | +5% | 87% | 87% |
| Sprint 03 | +2% | 89% | 89% |
| Sprint 04 | +1% | 90% | 90% ✅ |
| Sprint 05 | +2% | 92% | 92% |
| Sprint 06 | +1% | 93% | 93% |
| Sprint 07 | +0.5% | 93.5% | 93.5% |
| Sprint 08 | 0% | 93.5% | 93.5% ✅ |

### Fase 2 (Advanced - Sprints 09-10) - OPCIONAL

| Sprint | Delta Est. | Acumulado | Baseline Esperado |
|--------|-----------|-----------|------------------|
| Sprint 09 | 0% (ops) | 93.5% | Retreino automático |
| Sprint 10 | +1-2% | 94-95% | Edge cases (stretch) |

**Nota**: Estimativa conservadora. Impacto real pode variar ±5% conforme dataset.

---

## 🗓️ Timeline Estimado

### Fase 0 (Bloqueador)
```
Sprint 00: 1-2 semanas (anotação dataset + baseline + harness) **PRIMEIRO!**
```

### Fase 1 (Core)
```
Sprint 01: 1 semana  (4h trabalho + review)
Sprint 02: 1 semana  (6h trabalho + testing)
Sprint 03: 1 semana  (5h trabalho + comparação visual)
Sprint 04: 1.5 semanas (8h trabalho + validação)
Sprint 05: 1.5 semanas (10h trabalho + latency testing)
Sprint 06: 2 semanas (12h trabalho + dataset prep)
Sprint 07: 1 semana  (6h trabalho + ROC curves)
Sprint 08: 2 semanas (8h trabalho + production validation)

FASE 1 TOTAL: 11-14 semanas (incluindo Sprint 00)
```

### Fase 2 (Opcional)
```
Sprint 09: 1 semana (4-5 dias pipeline CI/CD)
Sprint 10: 1 semana (4-5 dias features visuais avançadas)

FASE 2 TOTAL: 2 semanas (se necessário)
```

---

## ⚠️ Riscos Globais & Mitigação

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|--------|-----------|
| Sprint 01 quebra resposta em 4K | 15% | Alto | Teste com samples 4K, 720p, crop antes |
| Sprint 02 perde legendas no top | 5% | Médio | Validar em dataset; ajustar ROI se necessário |
| Sprint 03 piora OCR em backgrounds complexos | 10% | Médio | Teste A/B preprocessing; fallback se pior |
| Sprint 05 adiciona latência excessiva | 20% | Médio | Implementar em paralelo; batching |
| Sprint 06 requer dataset maior que 100 amostras | 30% | Médio | Usar data augmentation; cross-validation |

---

---

### 📦 FASE 2: Advanced & Continuous (Sprints 09-10) - **OPCIONAL**

### Sprint 09: Continuous Training Pipeline ⭐⭐⭐
**Impacto esperado**: Manutenção (retreino automático) | Criticidade: MÉDIO  
**Status**: Opcional (pós-produção)  
**Dependências**: Sprint 08

Problema: Modelo degrada ao longo do tempo (drift), retreino manual custoso  
Solução: Pipeline automatizado de retreino ativado por drift detection  
Esforço: ~4-5 dias  
Risco: BAIXO (não afeta core, apenas operação)  

---

### Sprint 10: Feature Engineering V2 (Visual Avançado) ⭐⭐
**Impacto esperado**: +1-2% (edge cases) | Criticidade: BAIXO  
**Status**: Opcional (stretch goal)  
**Dependências**: Sprint 04

Problema: Edge cases (top subs, low contrast, stylized text) ainda falham  
Solução: Features visuais avançadas (não audio/metadata, apenas OCR melhorado)  
Esforço: ~4-5 dias  
Risco: BAIXO (features adicionais, não quebra baseline)  

---

## 🎯 Critério de Sucesso Global

Ao final da **Fase 1** (Sprints 00-08), o sistema deve:

✅ **Precisão ≥ 90%** em dataset hold-out (>200 vídeos)  
✅ **Recall ≥ 85%** (minimizar falsos negativos)  
✅ **FPR < 3%** (minimizar falsos positivos)  
✅ **Latência p50 < 8 segundos** (viável em produção)  
✅ **Temporal consistency** modelada (2-3 frame window)  
✅ **Dynamic resolution** corrigido (suporta qualquer resolução)  
✅ **Zero regressão** em baseline atual (não piorar)  

---

## 🚀 Próximos Passos

1. ✅ Reviewar roadmap
2. ⏳ Aprovar Sprint 01
3. 📝 Executar Sprint 01
4. 🔄 Validar impacto
5. ➡️ Proceder Sprint 02
