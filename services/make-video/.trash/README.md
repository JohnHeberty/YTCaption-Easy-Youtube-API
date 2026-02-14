# 🗑️ Arquivos Arquivados - Make-Video Service

**Propósito**: Documentos e scripts obsoletos que foram concluídos, consolidados ou substituídos.  
**Data de Consolidação**: 2026-02-12  
**Total de Arquivos**: 29

---

## 📋 Inventário Completo

### 📄 Documentação Antiga de OCR (8 arquivos)
| Arquivo | Motivo do Arquivamento | Substituído Por |
|---------|------------------------|-----------------|
| `NEW_OCR.md` | Análise inicial de problemas OCR | [OCR_ACCURACY.md](../OCR_ACCURACY.md) |
| `UNION_OPTIMIZE.md` | Proposta de otimizações | [RESILIENCE_IMPLEMENTED.md](../RESILIENCE_IMPLEMENTED.md) |
| `UNION_OPTIMIZE_docs.md` | Duplicata em docs/ | Removida |
| `OPTIMIZE.md` | Otimizações antigas | Consolidado em RESILIENCE |
| `FIXES_SUMMARY.md` | Resumo de fixes aplicados | [FIXES_APPLIED.md](../FIXES_APPLIED.md) |
| `INVESTIGATION.md` | Investigação de bugs | Problema resolvido |
| `INVESTIGATION_CONCLUSION.md` | Conclusão da investigação | Problema resolvido |
| `INVESTIGATION_old.md` | Versão antiga | Obsoleta |

### 🧪 Scripts de Teste Temporários (7 arquivos)
| Arquivo | Motivo do Arquivamento | Status |
|---------|------------------------|--------|
| `test_easyocr_simple.py` | Teste simples de EasyOCR | ✅ Validado e removido |
| `test_manual_detection.py` | Teste manual de detecção | ✅ Validado e removido |
| `test_simple.py` | Teste básico do sistema | ✅ Validado e removido |
| `validate_fixes.py` | Validação de fixes | ✅ Todos os fixes aplicados |
| `fire_test.py` | Teste de fire library | ✅ Não mais necessário |
| `fix_dataset_codec.sh` | Script de conversão AV1→H.264 | ✅ 11 vídeos convertidos |
| `start_calibration.sh` | Script de calibração antigo | Substituído por Makefile |

### 📊 Logs de Calibração (5 arquivos)
| Arquivo | Conteúdo | Data |
|---------|----------|------|
| `calibration.log` | Logs de calibração inicial | 2026-02-10 |
| `calibration_output.log` | Output completo de calibração | 2026-02-10 |
| `manual_test_full.log` | Testes manuais completos | 2026-02-11 |
| `manual_test_output.log` | Output de testes manuais | 2026-02-11 |
| `test_results.log` | Resultados de testes | 2026-02-11 |

### 📚 Documentação de Sprints (4 arquivos)
| Arquivo | Motivo do Arquivamento | Substituído Por |
|---------|------------------------|-----------------|
| `RESILIENCE.md` | Plano inicial de resiliência | [RESILIENCE_SPRINTS.md](../RESILIENCE_SPRINTS.md) |
| `RESILIENCE-IMPLEMENTATION.md` | Guia de implementação antigo | [RESILIENCE_IMPLEMENTED.md](../RESILIENCE_IMPLEMENTED.md) |
| `TEST-SPRINT-01.md` | Testes da Sprint-01 | Testes integrados em tests/ |
| `ACTION_PLAN.md` | Plano de ação antigo | ✅ Concluído |

### 📋 Outros (5 arquivos)
| Arquivo | Motivo do Arquivamento | Notas |
|---------|------------------------|-------|
| `BUG.md` | Relatório de bug | ✅ Bug corrigido |
| `CALIBRATION_GUIDE.md` | Guia de calibração antigo | Consolidado em OPTUNA_OPTIMIZATION.md |
| `EXECUTIVE_SUMMARY.md` | Resumo executivo | Obsoleto |
| `TEST.ogg` | Arquivo de teste de áudio | Teste concluído |
| `README.md` (este arquivo) | Inventário | Atualizado |

---

## 🎯 Resumo do Progresso

### Problemas Resolvidos
1. ✅ **OCR Accuracy**: 19.4% → 75-80% (thresholds ajustados)
2. ✅ **Codec Issues**: 11 vídeos AV1 convertidos para H.264
3. ✅ **Resiliência**: 4 sprints implementadas (Sprint-02, 03, 04, 07)
4. ✅ **Testes**: 13/13 testes passando (100%)
5. ✅ **Documentação**: Consolidada e organizada

### Sprints Implementadas
- ✅ Sprint-01: Auto-Recovery System (já existia)
- ✅ Sprint-02: Granular Checkpoints (checkpoint_manager.py)
- ✅ Sprint-03: Smart Timeout (timeout_manager.py)
- ✅ Sprint-04: Circuit Breaker (circuit_breaker.py)
- ✅ Sprint-07: Health Checks (health_checker.py)

### Documentação Nova
- [INDEX.md](../INDEX.md) - Índice centralizado
- [RESILIENCE_IMPLEMENTED.md](../RESILIENCE_IMPLEMENTED.md) - Guia de uso
- [RESILIENCE_SPRINTS.md](../RESILIENCE_SPRINTS.md) - Referência técnica
- [FUTURE_SPRINTS.md](../FUTURE_SPRINTS.md) - Roadmap futuro

---

## 🔍 Quando Recuperar Arquivos Deste Diretório

**Casos de uso para recuperação:**
1. 📖 **Histórico**: Entender evolução de decisões técnicas
2. 🐛 **Debugging**: Referência de bugs passados
3. 📊 **Comparação**: Ver estado anterior do sistema
4. 🎓 **Aprendizado**: Estudar abordagens que não funcionaram

**Como recuperar:**
```bash
# Ver conteúdo de um arquivo
cat .trash/NEW_OCR.md

# Copiar de volta
cp .trash/INVESTIGATION.md ./INVESTIGATION_recovered.md
```

---

## 🧹 Política de Limpeza

### O que vai para .trash/?
- ✅ Documentos consolidados em versões novas
- ✅ Scripts de teste após validação completa
- ✅ Logs de calibração/testes após conclusão
- ✅ Arquivos temporários de debugging

### O que NÃO vai para .trash/?
- ❌ Código de produção em uso
- ❌ Documentação ativa (README, guides)
- ❌ Testes unitários permanentes
- ❌ Configurações do sistema

### Quando deletar definitivamente?
- ⏰ Após 6 meses sem acesso
- ⏰ Após validação de que nenhum documento referencia
- ⏰ Após backup externo (se necessário)

---

## 📊 Estatísticas

| Métrica | Valor |
|---------|-------|
| **Total de Arquivos** | 29 |
| **Documentos** | 12 |
| **Scripts** | 7 |
| **Logs** | 5 |
| **Outros** | 5 |
| **Tamanho Total** | ~500KB |
| **Data de Criação** | 2026-02-10 a 2026-02-12 |

---

## 🔗 Links Úteis

- [Voltar ao Índice Principal](../INDEX.md)
- [Documentação de Resiliência](../RESILIENCE_IMPLEMENTED.md)
- [Guia de Calibração OCR](../OPTUNA_OPTIMIZATION.md)
- [README do Serviço](../README.md)

---

**Última Atualização**: 2026-02-12  
**Status**: 🗑️ Arquivado mas preservado para referência histórica  
**Próxima Revisão**: 2026-08-12 (6 meses)
