# 🗑️ Testes Obsoletos

Esta pasta contém **testes descontinuados** das Sprints 00-07.

## ⚠️ IMPORTANTE

**ESTES TESTES NÃO DEVEM SER EXECUTADOS**

Foram movidos para cá após a implementação da nova arquitetura Força Bruta (97.73% acurácia).

## 📋 Conteúdo

### Testes de Acurácia Obsoletos
- `test_accuracy_measurement.py` - Testes das Sprints antigas
- `test_accuracy_2detectors.py` - Ensemble com 2 detectores
- `test_accuracy_serialized.py` - Testes serializados
- `test_accuracy_final_clean.py` - Teste final (24.44%)
- `test_accuracy_brute_force.py` - Primeira versão força bruta

### Testes de Detectores Individuais
- `test_clip_only.py` - CLIP isolado
- `test_paddle_only.py` - PaddleOCR isolado
- `test_paddle_tesseract.py` - Paddle + Tesseract
- `test_paddle_threshold_08.py` - Ajuste de threshold

### Testes de Voting
- `test_vote_or_logic.py` - Lógica OR
- `test_weighted_voting.py` - Votação ponderada
- `test_sprint07_advanced_voting.py` - Sprint 07 voting
- `test_validate_ensemble_accuracy.py` - Validação ensemble

### Outros
- `test_clip_paddle_only.py` - Clip + Paddle
- `test_quick_accuracy_check.py` - Checagem rápida
- `test_ground_truth_clean.py` - Validação ground truth
- `debug_paddle_detection.py` - Debug PaddleOCR
- `results_clip_only.json` - Resultados JSON
- `subtitle_detector_v3.py` - Versão experimental

## 📊 Por Que Foram Descontinuados?

| Abordagem | Acurácia | Motivo |
|-----------|----------|--------|
| Sprints 00-07 | 24-33% | ❌ Baixa acurácia |
| Força Bruta | 97.73% | ✅ Atual |

## 📚 Documentação

- **Nova Arquitetura**: [../docs/NEW_ARCHITECTURE_BRUTE_FORCE.md](../docs/NEW_ARCHITECTURE_BRUTE_FORCE.md)
- **Sprints Obsoletas**: [../docs/SPRINTS_DEPRECATED.md](../docs/SPRINTS_DEPRECATED.md)

## ✅ Teste Atual

Use apenas: `pytest tests/test_accuracy_official.py -v -s`

---

**Movidos para OBSOLETE**: 14/02/2026  
**Motivo**: Implementação da arquitetura Força Bruta (97.73% acurácia)
