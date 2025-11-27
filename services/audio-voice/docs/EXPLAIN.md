# Explicação: Fases de Rollout (ALPHA, BETA, GA)

Guia completo sobre as fases de implantação gradual de novas features em produção.

---

## 🎯 O que é Rollout Gradual?

**Rollout gradual** (ou **phased rollout**) é uma estratégia de implantação de software onde uma nova feature é liberada progressivamente para um percentual crescente de usuários, em vez de ser ativada para 100% de uma só vez.

**Benefícios**:
- ✅ **Reduz riscos**: Problemas afetam menos usuários
- ✅ **Permite testes reais**: Validação em produção com tráfego real
- ✅ **Facilita rollback**: Mais fácil reverter se necessário
- ✅ **Coleta feedback gradual**: Aprende com usuários reais antes de escalar

---

## 📊 As 4 Fases do Rollout

### 🔒 DISABLED (Desabilitado)

**O que é**: Feature completamente desabilitada, ninguém tem acesso.

**Quando usar**:
- Antes do lançamento oficial
- Durante desenvolvimento/testes
- Após um rollback de emergência
- Para desativar uma feature permanentemente

**Configuração**:
```bash
export FEATURE_F5TTS_ENABLED=false
export FEATURE_F5TTS_PHASE=disabled
export FEATURE_F5TTS_PERCENTAGE=0
```

**Exemplo prático**:
```python
# Sistema usa apenas XTTS (engine padrão)
if is_feature_enabled('f5tts_engine', user_id='qualquer_usuario'):
    engine = 'f5tts'  # ❌ NUNCA entra aqui
else:
    engine = 'xtts'   # ✅ SEMPRE usa XTTS
```

**Usuários afetados**: 0% (nenhum usuário tem acesso)

---

### 🐛 ALPHA (10% dos usuários)

**O que é**: Fase inicial de testes com um pequeno grupo de usuários (10%).

**Quando usar**:
- Primeira validação em produção
- Testes com usuários reais (early adopters)
- Validação de bugs críticos
- Testes de performance em escala reduzida

**Configuração**:
```bash
export FEATURE_F5TTS_ENABLED=true
export FEATURE_F5TTS_PHASE=alpha
export FEATURE_F5TTS_PERCENTAGE=10
```

**Como funciona**:
```python
# Sistema usa HASH do user_id para decidir
user_id = "user_123"
hash_value = hash(user_id) % 100  # Resultado: 0-99

if hash_value < 10:  # 10% dos usuários
    engine = 'f5tts'  # ✅ Usa F5-TTS (novo)
else:
    engine = 'xtts'   # ✅ Usa XTTS (padrão)
```

**Características**:
- ✅ **Consistente**: Mesmo usuário sempre tem mesmo resultado
- ✅ **Whitelist**: Equipe interna pode ter acesso garantido
- ✅ **Blacklist**: Usuários problemáticos podem ser bloqueados
- ⏱️ **Duração**: 3-5 dias de monitoramento

**Métricas a observar**:
- Taxa de erro (deve ser < 2%)
- RTF - Real-Time Factor (deve ser < 0.25)
- Latência p95 (deve ser < 8s)
- Feedback dos usuários

**Exemplo real**:
```
Total de usuários: 1000
Usuários com acesso ao F5-TTS: ~100 (10%)
Usuários usando XTTS: ~900 (90%)
```

**Rollback**:
Se houver problemas, basta desabilitar:
```bash
./scripts/deploy_with_rollout.sh disabled
```

---

### 🧪 BETA (50% dos usuários)

**O que é**: Fase intermediária com metade dos usuários.

**Quando usar**:
- Após ALPHA bem-sucedido
- Para validação em escala maior
- A/B testing (comparar XTTS vs F5-TTS)
- Testes de carga e performance

**Configuração**:
```bash
export FEATURE_F5TTS_ENABLED=true
export FEATURE_F5TTS_PHASE=beta
export FEATURE_F5TTS_PERCENTAGE=50
```

**Como funciona**:
```python
user_id = "user_456"
hash_value = hash(user_id) % 100  # Resultado: 0-99

if hash_value < 50:  # 50% dos usuários
    engine = 'f5tts'  # ✅ Metade usa F5-TTS
else:
    engine = 'xtts'   # ✅ Metade usa XTTS
```

**Características**:
- 📊 **A/B Testing**: Ideal para comparar métricas
- 🔬 **Validação estatística**: Amostra grande o suficiente
- ⚖️ **Balanceamento**: 50/50 permite comparação justa
- ⏱️ **Duração**: 5-7 dias de monitoramento

**Métricas a observar**:
- Comparação XTTS vs F5-TTS (qualidade, performance)
- Taxa de erro (deve ser < 1.5%)
- Latência p95 (deve ser < 6s)
- Satisfação do usuário

**Exemplo de A/B Testing**:
```
Grupo A (XTTS): 500 usuários
  - RTF médio: 0.08
  - Taxa de erro: 0.5%
  - Satisfação: 85%

Grupo B (F5-TTS): 500 usuários
  - RTF médio: 0.12
  - Taxa de erro: 0.8%
  - Satisfação: 92%

Conclusão: F5-TTS tem melhor satisfação, mas RTF um pouco maior
```

**Rollback**:
```bash
# Voltar para 10%
./scripts/deploy_with_rollout.sh alpha

# OU desabilitar completamente
./scripts/deploy_with_rollout.sh disabled
```

---

### 🎉 GA (100% - General Availability)

**O que é**: Feature disponível para TODOS os usuários (100%).

**Quando usar**:
- Após BETA bem-sucedido
- Quando todas as métricas estão OK
- Feature estável e validada
- Pronta para uso geral

**Configuração**:
```bash
export FEATURE_F5TTS_ENABLED=true
export FEATURE_F5TTS_PHASE=ga
export FEATURE_F5TTS_PERCENTAGE=100
```

**Como funciona**:
```python
# TODOS os usuários têm acesso
if is_feature_enabled('f5tts_engine', user_id='qualquer_usuario'):
    engine = 'f5tts'  # ✅ SEMPRE entra aqui (exceto blacklist)
else:
    engine = 'xtts'   # ❌ Nunca usa (a menos que F5-TTS falhe)
```

**Características**:
- 🌍 **Universal**: Todos os usuários têm acesso
- 🎯 **Feature oficial**: Considerada "lançada"
- 📈 **Monitoramento contínuo**: Observar por 7+ dias
- ⏱️ **Duração**: Permanente (até próxima feature)

**Métricas de sucesso**:
- Taxa de erro < 1%
- RTF < 0.15 (GPU)
- Latência p95 < 5s
- Sistema estável por 7+ dias
- Satisfação do usuário >= 90%

**Exemplo real**:
```
Total de usuários: 1000
Usuários com acesso ao F5-TTS: 1000 (100%)
Usuários usando XTTS: 0 (apenas como fallback)
```

**Rollback** (se necessário):
```bash
# Voltar para 50%
./scripts/deploy_with_rollout.sh beta

# OU desabilitar completamente
./scripts/deploy_with_rollout.sh disabled
```

---

## 🔄 Timeline Completo do Rollout

```
Semana 1:
├─ Dia 1-2: ALPHA 10%
│   └─ Monitoramento intensivo
├─ Dia 3-4: Análise de métricas ALPHA
│   └─ Decisão: Continuar para BETA?
└─ Dia 5: GO/NO-GO para BETA

Semana 2:
├─ Dia 1: BETA 25% (gradual)
├─ Dia 2: BETA 50%
│   └─ A/B testing ativo
├─ Dia 3-5: Monitoramento + Análise
├─ Dia 6: Análise de métricas BETA
│   └─ Decisão: Continuar para GA?
└─ Dia 7: GO/NO-GO para GA

Semana 3:
├─ Dia 1: GA 75% (gradual)
├─ Dia 2: GA 100%
│   └─ Feature totalmente ativada
└─ Dia 3-7: Monitoramento GA
    └─ Estabilização + Celebração 🎉
```

**Duração total**: 2-3 semanas

---

## 🎮 Como Usar na Prática

### 1. Deploy Inicial (DISABLED)

```bash
cd services/audio-voice
./scripts/deploy_with_rollout.sh disabled
```

**Resultado**: Sistema funcionando com XTTS apenas (estado atual).

---

### 2. Ativar ALPHA (10%)

```bash
./scripts/deploy_with_rollout.sh alpha
```

**O que acontece**:
- 10% dos usuários começam a usar F5-TTS
- 90% continuam usando XTTS
- Logs mostram qual engine foi usado em cada request

**Monitoramento**:
```bash
# Ver logs em tempo real
docker-compose logs -f audio-voice | grep "f5tts"

# Verificar feature flags
curl http://localhost:8000/feature-flags

# Verificar para usuário específico
curl "http://localhost:8000/feature-flags/f5tts_engine?user_id=user_123"
```

**Após 3-5 dias**: Analisar métricas e decidir continuar.

---

### 3. Promover para BETA (50%)

```bash
./scripts/deploy_with_rollout.sh beta
```

**O que acontece**:
- 50% dos usuários usam F5-TTS
- 50% usam XTTS
- Ideal para A/B testing

**A/B Testing**:
```python
# Coletar métricas de ambos os grupos
metrics_xtts = collect_metrics(engine='xtts')
metrics_f5tts = collect_metrics(engine='f5tts')

# Comparar
compare(metrics_xtts, metrics_f5tts)
```

**Após 5-7 dias**: Se tudo OK, promover para GA.

---

### 4. Lançar GA (100%)

```bash
./scripts/deploy_with_rollout.sh ga
```

**O que acontece**:
- 100% dos usuários usam F5-TTS
- XTTS fica como fallback (se F5-TTS falhar)
- Feature oficialmente lançada

**Celebrar**: 🎉 Feature em produção!

---

## 🚨 Cenários de Rollback

### Cenário 1: Bug Crítico no ALPHA

**Problema**: Taxa de erro de 15% no ALPHA.

**Solução**:
```bash
# Rollback imediato para DISABLED
./scripts/deploy_with_rollout.sh disabled

# Investigar logs
docker-compose logs audio-voice | grep ERROR

# Corrigir bug, fazer novo deploy
git commit -m "fix: corrigir bug crítico F5-TTS"
./scripts/deploy_with_rollout.sh alpha  # Tentar novamente
```

---

### Cenário 2: Performance Ruim no BETA

**Problema**: Latência p95 de 15s (muito alto).

**Solução**:
```bash
# Rollback para ALPHA (10%)
./scripts/deploy_with_rollout.sh alpha

# Otimizar performance
# - Reduzir batch size
# - Usar FP16
# - Otimizar cache

# Testar novamente
./scripts/deploy_with_rollout.sh beta
```

---

### Cenário 3: Feedback Negativo no GA

**Problema**: Usuários reclamando de qualidade de áudio.

**Solução**:
```bash
# Rollback para BETA (50%)
./scripts/deploy_with_rollout.sh beta

# Investigar problema de qualidade
# Ajustar quality profiles
# Coletar mais feedback

# Relançar GA quando resolvido
./scripts/deploy_with_rollout.sh ga
```

---

## 📊 Métricas por Fase

| Métrica | ALPHA | BETA | GA |
|---------|-------|------|-----|
| **Usuários** | 10% | 50% | 100% |
| **Taxa de erro** | < 2% | < 1.5% | < 1% |
| **RTF (GPU)** | < 0.25 | < 0.20 | < 0.15 |
| **Latência p95** | < 8s | < 6s | < 5s |
| **Duração** | 3-5 dias | 5-7 dias | Permanente |
| **Rollback** | Para DISABLED | Para ALPHA | Para BETA |

---

## 💡 Boas Práticas

### 1. Sempre monitore

```bash
# Logs em tempo real
docker-compose logs -f audio-voice

# Métricas de feature flags
curl http://localhost:8000/feature-flags
```

### 2. Use whitelist para equipe

```python
from app.feature_flags import get_feature_flag_manager

manager = get_feature_flag_manager()
manager.add_to_whitelist('f5tts_engine', 'team_member@company.com')
```

### 3. Documente decisões

```markdown
## Rollout Log

### 2025-11-27: ALPHA iniciado
- 10% dos usuários
- Métricas: RTF 0.12, erro 0.5%
- Feedback: Positivo

### 2025-12-01: Promovido para BETA
- 50% dos usuários
- Razão: ALPHA bem-sucedido
```

### 4. Tenha plano de rollback

Sempre saiba como reverter rapidamente:
```bash
# Sempre tenha esse comando pronto
./scripts/deploy_with_rollout.sh disabled
```

---

## ❓ FAQ

**Q: Por que não ir direto para 100%?**  
A: Risco muito alto. Se houver bug, afeta TODOS os usuários.

**Q: Posso pular fases?**  
A: Tecnicamente sim, mas não recomendado. Cada fase serve para validar aspectos diferentes.

**Q: Quanto tempo devo manter cada fase?**  
A: ALPHA: 3-5 dias, BETA: 5-7 dias, GA: permanente (monitorar por 7+ dias).

**Q: E se houver bugs no GA?**  
A: Rollback para BETA ou DISABLED, corrigir, relançar.

**Q: Como sei se estou pronto para próxima fase?**  
A: Todas as métricas de sucesso da fase atual foram atingidas.

**Q: Posso ter múltiplas features em rollout?**  
A: Sim, mas gerencie cada uma independentemente.

---

## 📚 Recursos Adicionais

- [ROLLOUT_PLAN.md](ROLLOUT_PLAN.md) - Plano detalhado de rollout
- [DEPLOYMENT.md](DEPLOYMENT.md) - Guia de deploy
- [Feature Flags Code](../app/feature_flags.py) - Implementação

---

**Rollout gradual = Deploy seguro e controlado** ✅
