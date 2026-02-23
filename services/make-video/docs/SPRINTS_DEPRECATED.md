# ⚠️ SPRINTS 00-07: DESCONTINUADAS

## 🚨 AVISO IMPORTANTE

**TODAS as Sprints de 00 a 07 foram DESCONTINUADAS em Fevereiro de 2026.**

### Por quê?
- **Baixa acurácia**: 24-33% com otimizações complexas (ROI, Multi-ROI, Sampling)
- **Alta complexidade**: 640+ linhas de código difícil de manter
- **Abordagem errada**: Otimizações PREJUDICAVAM a detecção

### Nova Abordagem: FORÇA BRUTA
- **97.73% de acurácia** ✅ (vs 24.44% das Sprints)
- **200 linhas de código** simples e direto
- **Processa TODOS os frames**, frame COMPLETO
- **Sem otimizações**, sem ROI, sem sampling

---

## 📊 Comparação de Resultados

| Abordagem | Acurácia | Código | Manutenção |
|-----------|----------|--------|------------|
| **Sprints 00-07** | 24.44% ❌ | 640 linhas | Difícil ⚠️ |
| **Força Bruta** | 97.73% ✅ | 200 linhas | Fácil ✅ |

**Melhoria: +304% de acurácia, -69% de código**

---

## 🗂️ Sprints Antigas (Histórico)

### Sprint 00: Baseline
- **Objetivo**: Detecção simples com ROI bottom
- **Resultado**: ~24% acurácia
- **Status**: ❌ Descontinuada

### Sprint 01: Refinamento ROI
- **Objetivo**: Ajustar ROI para diferentes resoluções
- **Resultado**: ~25% acurácia
- **Status**: ❌ Descontinuada

### Sprint 02: Preprocessing
- **Objetivo**: CLAHE, noise reduction, sharpening
- **Resultado**: ~26% acurácia
- **Status**: ❌ Descontinuada

### Sprint 03: Temporal Sampling
- **Objetivo**: Amostrar 6 frames estratégicos
- **Resultado**: ~27% acurácia
- **Status**: ❌ Descontinuada

### Sprint 04: Multi-ROI Fallback
- **Objetivo**: Tentar bottom→top→left→right→center
- **Resultado**: ~28% acurácia
- **Status**: ❌ Descontinuada

### Sprint 05: Resolution-Aware
- **Objetivo**: Adaptar processamento por resolução
- **Resultado**: ~29% acurácia
- **Status**: ❌ Descontinuada

### Sprint 06: Ensemble Voting
- **Objetivo**: Usar múltiplos detectores (Paddle, CLIP, Tesseract)
- **Resultado**: ~30% acurácia (segfaults com EasyOCR)
- **Status**: ❌ Descontinuada

### Sprint 07: Weighted Voting
- **Objetivo**: Votação ponderada + uncertainty estimation
- **Resultado**: ~33% acurácia
- **Status**: ❌ Descontinuada

---

## ✅ Solução Atual: Força Bruta

### Documentação
- **Arquitetura**: [`docs/NEW_ARCHITECTURE_BRUTE_FORCE.md`](NEW_ARCHITECTURE_BRUTE_FORCE.md)
- **Código**: [`app/video_processing/subtitle_detector_v2.py`](../app/video_processing/subtitle_detector_v2.py)
- **Teste**: [`tests/test_accuracy_official.py`](../tests/test_accuracy_official.py)

### Resultado Comprovado
```
🎯 Confusion Matrix:
   TP: 37 | TN: 6 | FP: 1 | FN: 0

📈 Métricas:
   Acurácia:  97.73% ✅
   Precisão:  97.37% ✅
   Recall:   100.00% 🎯
   F1-Score:  98.67% ✅
```

---

## 🗑️ Código Obsoleto

### Arquivos Removidos/Arquivados
- `subtitle_detector_v2_OLD_SPRINTS.py.bak` (640 linhas)
- `frame_preprocessor_OLD_SPRINTS.py.bak` (300 linhas)

### Testes Obsoletos
- `test_accuracy_measurement.py` (Sprints antigas)
- `test_paddle_threshold_08.py` (threshold tuning)
- `test_paddle_tesseract.py` (ensemble voting)
- `test_vote_or_logic.py` (voting strategies)

**Estes testes foram mantidos apenas para histórico, mas não devem ser executados.**

---

## 💡 Lição Principal

> **"A solução mais simples geralmente é a melhor"**

Gastamos meses implementando otimizações complexas que **PREJUDICAVAM** a acurácia.

Quando testamos a abordagem mais simples (força bruta):
- ✅ 97.73% de acurácia
- ✅ Código mais limpo
- ✅ Mais fácil de manter
- ✅ Mais rápido de implementar

### Por Que as Otimizações Falharam?

1. **ROI limitada**: Texto pode estar em qualquer lugar (não só no bottom)
2. **Frame sampling**: Texto pode aparecer entre frames amostrados
3. **Preprocessing**: OCR moderno já é robusto, não precisa
4. **Multi-ROI**: Adiciona complexidade sem ganho de acurácia

### Por Que Força Bruta Funciona?

1. **Captura TUDO**: Não perde texto em nenhuma posição
2. **Captura SEMPRE**: Não perde texto em frames não amostrados
3. **Simples = Confiável**: Menos código = menos bugs
4. **OCR é bom**: PaddleOCR GPU é rápido e preciso

---

## 🚀 Próximos Passos

### ✅ Fazer
1. Usar `SubtitleDetectorV2` (força bruta) em produção
2. Monitorar acurácia em casos reais
3. Documentar edge cases que surgirem

### ❌ NÃO Fazer
1. ~~Voltar para ROI/Multi-ROI~~
2. ~~Adicionar frame sampling~~
3. ~~Adicionar preprocessing complexo~~
4. ~~Tentar "otimizar" sem medir impacto~~

**Se funciona bem (97.73%), não mexa!**

---

## 📚 Referências

- **Nova Arquitetura**: [NEW_ARCHITECTURE_BRUTE_FORCE.md](NEW_ARCHITECTURE_BRUTE_FORCE.md)
- **Teste Oficial**: [test_accuracy_official.py](../tests/test_accuracy_official.py)
- **Código Força Bruta**: [subtitle_detector_v2.py](../app/video_processing/subtitle_detector_v2.py)
- **Histórico Sprints**: [README.md](README.md) (este arquivo)

---

**Data de Descontinuação**: Fevereiro 2026  
**Motivo**: Baixa acurácia (24-33%) vs Força Bruta (97.73%)  
**Status**: ❌ Obsoleto - Não usar mais  
**Substituto**: ✅ SubtitleDetectorV2 (Força Bruta)
