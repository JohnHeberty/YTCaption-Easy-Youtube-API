# Gradual Rollout Plan - F5-TTS Multi-Engine

Plano de rollout gradual do sistema multi-engine (XTTS + F5-TTS) em produção.

---

## 📋 Visão Geral

**Objetivo**: Migrar gradualmente de XTTS-only para sistema multi-engine com F5-TTS, minimizando riscos.

**Estratégia**: Feature flags + rollout em fases (Alpha → Beta → GA)

**Duração total**: ~2 semanas

---

## 🎯 Fases do Rollout

### Fase 0: Preparação (Completo ✅)

**Duração**: -  
**Status**: COMPLETO

**Atividades**:
- ✅ Implementação do sistema multi-engine
- ✅ Testes unitários (153 tests)
- ✅ Testes de integração
- ✅ Testes E2E
- ✅ Benchmarks PT-BR
- ✅ Documentação completa
- ✅ Sistema de feature flags

**Validação**:
- ✅ 100% backward compatible
- ✅ Zero breaking changes
- ✅ Todos os testes passando

---

### Fase 1: ALPHA (10% dos usuários)

**Duração**: 3-5 dias  
**Status**: PENDENTE  
**Início previsto**: Após deploy

**Configuração**:
```bash
# Variáveis de ambiente
export FEATURE_F5TTS_ENABLED=true
export FEATURE_F5TTS_PHASE=alpha
export FEATURE_F5TTS_PERCENTAGE=10
```

**Critérios de entrada**:
- [ ] Deploy em produção completo
- [ ] Feature flags configuradas
- [ ] Logs e métricas configurados
- [ ] Rollback plan documentado

**Atividades**:
1. **Habilitar F5-TTS para 10% dos usuários**
   - Rollout baseado em hash do user_id (consistente)
   - Whitelist para equipe interna (testes)
   
2. **Monitoramento intensivo**
   - Taxa de erro (XTTS vs F5-TTS)
   - RTF (Real-Time Factor)
   - Latência (p50, p95, p99)
   - VRAM usage
   - Qualidade de áudio (feedback manual)

3. **Coletar feedback**
   - Logs de erros
   - Métricas de performance
   - Feedback de usuários beta

**Métricas de sucesso**:
- ✅ Taxa de erro < 2% (mesmo que XTTS)
- ✅ RTF < 0.25 (GPU)
- ✅ Latência p95 < 8s
- ✅ Nenhum incidente crítico
- ✅ Feedback positivo de usuários

**Rollback**:
```bash
# Se houver problemas
export FEATURE_F5TTS_ENABLED=false
# OU
export FEATURE_F5TTS_PHASE=disabled
```

**Duração**: 3-5 dias de observação

---

### Fase 2: BETA (50% dos usuários)

**Duração**: 5-7 dias  
**Status**: PENDENTE  
**Início previsto**: Após ALPHA bem-sucedido

**Configuração**:
```bash
export FEATURE_F5TTS_ENABLED=true
export FEATURE_F5TTS_PHASE=beta
export FEATURE_F5TTS_PERCENTAGE=50
```

**Critérios de entrada**:
- [ ] ALPHA concluído com sucesso
- [ ] Métricas de sucesso atingidas
- [ ] Nenhum bug crítico
- [ ] Aprovação do tech lead

**Atividades**:
1. **Expandir para 50% dos usuários**
   - Gradual: 10% → 25% → 50% (1 dia entre cada aumento)
   
2. **A/B Testing**
   - Comparar XTTS vs F5-TTS
   - Qualidade de áudio
   - Performance
   - Satisfação do usuário

3. **Load testing**
   - Simular carga de produção
   - Validar escalabilidade
   - Testar fallback automático

**Métricas de sucesso**:
- ✅ Taxa de erro < 1.5%
- ✅ RTF < 0.20 (GPU)
- ✅ Latência p95 < 6s
- ✅ VRAM usage estável
- ✅ Nenhum incidente de downtime
- ✅ Qualidade de áudio >= XTTS

**Rollback**:
```bash
# Rollback para 10%
export FEATURE_F5TTS_PERCENTAGE=10

# OU rollback completo
export FEATURE_F5TTS_PHASE=disabled
```

**Duração**: 5-7 dias

---

### Fase 3: GA (100% - General Availability)

**Duração**: Permanente  
**Status**: PENDENTE  
**Início previsto**: Após BETA bem-sucedido

**Configuração**:
```bash
export FEATURE_F5TTS_ENABLED=true
export FEATURE_F5TTS_PHASE=ga
export FEATURE_F5TTS_PERCENTAGE=100
```

**Critérios de entrada**:
- [ ] BETA concluído com sucesso
- [ ] Todas as métricas de sucesso atingidas
- [ ] Aprovação final do product owner
- [ ] Documentação atualizada

**Atividades**:
1. **Habilitar para 100% dos usuários**
   - Gradual: 50% → 75% → 100% (1 dia entre cada)
   
2. **Atualizar documentação**
   - README.md com F5-TTS como opção padrão
   - API docs completos
   - Guias de uso

3. **Comunicação**
   - Anunciar novo engine disponível
   - Tutorial de como usar F5-TTS
   - Comparação XTTS vs F5-TTS

**Métricas de sucesso**:
- ✅ Taxa de erro < 1%
- ✅ RTF < 0.15 (GPU)
- ✅ Latência p95 < 5s
- ✅ Satisfação do usuário >= 90%
- ✅ Sistema estável por 7+ dias

**Rollback**:
```bash
# Rollback para BETA (50%)
export FEATURE_F5TTS_PERCENTAGE=50

# OU rollback completo
export FEATURE_F5TTS_PHASE=disabled
```

---

## 📊 Métricas e KPIs

### Performance

| Métrica | Target ALPHA | Target BETA | Target GA |
|---------|--------------|-------------|-----------|
| **RTF (GPU)** | < 0.25 | < 0.20 | < 0.15 |
| **Latência p50** | < 3s | < 2.5s | < 2s |
| **Latência p95** | < 8s | < 6s | < 5s |
| **Latência p99** | < 12s | < 10s | < 8s |

### Confiabilidade

| Métrica | Target ALPHA | Target BETA | Target GA |
|---------|--------------|-------------|-----------|
| **Taxa de erro** | < 2% | < 1.5% | < 1% |
| **Uptime** | > 99.5% | > 99.7% | > 99.9% |
| **Taxa de fallback** | < 5% | < 3% | < 1% |

### Qualidade

| Métrica | Target ALPHA | Target BETA | Target GA |
|---------|--------------|-------------|-----------|
| **MOS (Mean Opinion Score)** | > 4.0 | > 4.2 | > 4.5 |
| **SNR** | > 20 dB | > 22 dB | > 25 dB |
| **Naturalidade** | >= XTTS | > XTTS | >> XTTS |

---

## 🔧 Feature Flags

### Configuração via Environment Variables

```bash
# F5-TTS Engine
FEATURE_F5TTS_ENABLED=true|false
FEATURE_F5TTS_PHASE=disabled|alpha|beta|ga
FEATURE_F5TTS_PERCENTAGE=0-100

# Auto-transcription (F5-TTS)
FEATURE_AUTO_TRANSCRIPTION_ENABLED=true|false
FEATURE_AUTO_TRANSCRIPTION_PHASE=disabled|alpha|beta|ga

# Quality Profiles
FEATURE_QUALITY_PROFILES_ENABLED=true|false
```

### Uso no código

```python
from app.feature_flags import is_feature_enabled

# Verificar se F5-TTS está habilitado para este usuário
if is_feature_enabled('f5tts_engine', user_id=user_id):
    engine = 'f5tts'
else:
    engine = 'xtts'

# Processar com engine escolhido
result = await processor.process_tts(text, engine=engine, ...)
```

### Whitelist (Acesso antecipado)

```python
from app.feature_flags import get_feature_flag_manager

manager = get_feature_flag_manager()

# Dar acesso antecipado para equipe interna
manager.add_to_whitelist('f5tts_engine', 'team_member_1')
manager.add_to_whitelist('f5tts_engine', 'team_member_2')

# Beta testers
manager.add_to_whitelist('f5tts_engine', 'beta_tester_1')
```

### Blacklist (Bloqueio)

```python
# Bloquear usuários com problemas
manager.add_to_blacklist('f5tts_engine', 'problematic_user')
```

---

## 🚨 Rollback Plan

### Níveis de Rollback

**Nível 1: Reduzir porcentagem**
```bash
# Reduzir de 50% para 25%
export FEATURE_F5TTS_PERCENTAGE=25
```

**Nível 2: Voltar fase anterior**
```bash
# Voltar de BETA para ALPHA
export FEATURE_F5TTS_PHASE=alpha
export FEATURE_F5TTS_PERCENTAGE=10
```

**Nível 3: Desabilitar completamente**
```bash
# Rollback completo
export FEATURE_F5TTS_ENABLED=false
# OU
export FEATURE_F5TTS_PHASE=disabled
```

### Triggers de Rollback

**Automático** (se configurado):
- Taxa de erro > 5%
- Latência p99 > 20s
- VRAM out of memory > 10 ocorrências/hora

**Manual**:
- Bugs críticos descobertos
- Feedback negativo massivo
- Problemas de performance graves

---

## 📅 Timeline Estimado

```
Semana 1:
├─ Dia 1-2: ALPHA 10% + Monitoramento
├─ Dia 3-4: Análise de métricas ALPHA
└─ Dia 5: Decisão GO/NO-GO para BETA

Semana 2:
├─ Dia 1: BETA 25%
├─ Dia 2: BETA 50%
├─ Dia 3-5: Monitoramento + A/B testing
├─ Dia 6: Análise de métricas BETA
└─ Dia 7: Decisão GO/NO-GO para GA

Semana 3 (opcional):
├─ Dia 1: GA 75%
├─ Dia 2: GA 100%
└─ Dia 3-7: Monitoramento GA + Estabilização
```

**Total**: 2-3 semanas

---

## ✅ Checklist de Deploy

### Pré-deploy
- [ ] Código em produção (Sprint 10)
- [ ] Feature flags implementadas
- [ ] Testes passando (153 tests)
- [ ] Documentação atualizada
- [ ] Rollback plan documentado
- [ ] Aprovação do tech lead

### Deploy
- [ ] Deploy em staging primeiro
- [ ] Testes de fumaça (smoke tests)
- [ ] Deploy em produção
- [ ] Verificar health check
- [ ] Configurar feature flags (DISABLED)

### Pós-deploy
- [ ] Logs funcionando
- [ ] Métricas disponíveis
- [ ] Alertas configurados
- [ ] Equipe notificada

### ALPHA
- [ ] Habilitar ALPHA (10%)
- [ ] Adicionar whitelist (equipe)
- [ ] Monitorar por 3-5 dias
- [ ] Coletar feedback
- [ ] Análise de métricas

### BETA
- [ ] Habilitar BETA (50%)
- [ ] A/B testing configurado
- [ ] Monitorar por 5-7 dias
- [ ] Load testing
- [ ] Análise comparativa

### GA
- [ ] Habilitar GA (100%)
- [ ] Atualizar documentação
- [ ] Comunicação aos usuários
- [ ] Monitorar por 7+ dias
- [ ] Celebrar! 🎉

---

## 📚 Recursos

- [Feature Flags Code](../app/feature_flags.py)
- [Feature Flags Tests](../tests/unit/test_feature_flags.py)
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deploy em produção
- [MIGRATION.md](MIGRATION.md) - Guia de migração

---

**Rollout plan criado**: 2025-11-27  
**Última atualização**: 2025-11-27  
**Status**: Pronto para execução
