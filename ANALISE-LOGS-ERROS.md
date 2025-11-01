# 📊 ANÁLISE COMPLETA DE LOGS E ERROS

**Data da Análise:** 2025-11-01  
**Serviços Analisados:** audio-normalization, audio-transcriber, video-downloader, orchestrator

---

## 🔴 PROBLEMAS CRÍTICOS IDENTIFICADOS

### 1. **Circuit Breaker OPEN - Serviço Indisponível**

**Erro:**
```
"[audio-normalization] Circuit breaker is OPEN - service unavailable"
```

**Causa Raiz:**
- O Circuit Breaker do orchestrator está abrindo (bloqueando requisições) após múltiplas falhas consecutivas no serviço
- Configuração atual: após `circuit_breaker_max_failures` falhas, o serviço é marcado como indisponível por `circuit_breaker_recovery_timeout` segundos
- O problema é que mesmo após o timeout de recuperação, se a primeira tentativa falhar, o circuit breaker abre novamente

**Impacto:**
- 🔴 **CRÍTICO**: Impede que o orchestrator envie requisições ao serviço mesmo quando ele pode estar funcionando
- Bloqueia o upload de arquivos multipart
- Causa rejeição imediata de requisições sem nem tentar

**Solução Necessária:**
1. ✅ Aumentar `circuit_breaker_max_failures` para tolerar mais falhas antes de abrir
2. ✅ Diminuir `circuit_breaker_recovery_timeout` para tentar recuperação mais rápido
3. ✅ Implementar half-open state: permitir 1 requisição de teste antes de fechar completamente
4. ✅ Excluir endpoints de health check do circuit breaker (não devem contar como falhas)

---

### 2. **Inconsistência Store=processing, Celery=FAILURE**

**Erro (repetido constantemente):**
```
⚠️ Inconsistência: Store=processing, Celery=FAILURE
```

**Frequência:** Ocorreu 22+ vezes nos logs

**Causa Raiz:**
- As tasks do Celery estão falhando, mas o Redis Store ainda mantém o status como "processing"
- Indica que o tratamento de erros do Celery não está atualizando corretamente o Redis
- Workers do Celery estão morrendo ou crashando sem atualizar o status final

**Impacto:**
- 🟠 **ALTO**: Jobs ficam presos no estado "processing" eternamente
- Frontend não recebe notificação de falha
- Usuário fica esperando indefinidamente
- Sistema fica inconsistente

**Solução Necessária:**
1. ✅ Melhorar o tratamento de exceções em `celery_tasks.py`
2. ✅ Garantir que TODOS os caminhos de erro atualizam o Redis Store
3. ✅ Adicionar signal handlers do Celery para capturar crashes (`task_failure`, `task_revoked`)
4. ✅ Implementar um job de reconciliação que verifica inconsistências periodicamente
5. ✅ Adicionar timeout de "processing" - se job está processando por muito tempo, marcar como falha

---

### 3. **Arquivo Muito Grande - Validação Inconsistente**

**Erro:**
```
Arquivo muito grande: 156327441 bytes (149 MB)
Arquivo muito grande: 144173889 bytes (137 MB)
```

**Causa Raiz:**
- Arquivos estão sendo rejeitados por serem "muito grandes", mas:
  - Config atual: `max_file_size_mb = 500` (500 MB)
  - Arquivos rejeitados: ~137-149 MB (bem abaixo do limite)
- **BUG**: A validação está calculando o tamanho incorretamente ou há outro limite oculto

**Impacto:**
- 🟠 **MÉDIO**: Usuários não conseguem fazer upload de arquivos que deveriam ser aceitos
- Experiência do usuário ruim (limite anunciado não corresponde ao real)

**Solução Necessária:**
1. ✅ Investigar a validação de tamanho no endpoint de upload
2. ✅ Verificar se há limite no FastAPI/Uvicorn para multipart
3. ✅ Verificar se há limite no nginx/proxy reverso
4. ✅ Adicionar log detalhado: "Arquivo {X} MB, limite {Y} MB, calculado como {Z} bytes"
5. ✅ Corrigir a validação para aceitar até o limite configurado

---

### 4. **Limpeza Total Excessiva (FLUSHDB)**

**Padrão Observado:**
```
🔥 LIMPEZA TOTAL CONCLUÍDA: 0 jobs do Redis + 16 arquivos removidos (1607.84MB liberados)
🔥 LIMPEZA TOTAL CONCLUÍDA: 0 jobs do Redis + 7 arquivos removidos (714.19MB liberados)
```

**Causa Raiz:**
- Endpoint `/cleanup` está sendo chamado com frequência
- Está usando `FLUSHDB` que **limpa TODO o database do Redis**, não apenas jobs específicos
- Remove até jobs de outros serviços se compartilharem o mesmo Redis DB

**Impacto:**
- 🟡 **MÉDIO**: Pode estar removendo jobs válidos de outros serviços
- Risco de perda de dados se múltiplos serviços usam o mesmo Redis DB
- Não é granular - remove tudo, não apenas jobs expirados

**Solução Necessária:**
1. ✅ **NÃO USAR `FLUSHDB`** - muito destrutivo
2. ✅ Implementar limpeza granular usando padrões de chave: `SCAN` + `DEL` com prefixo
3. ✅ Adicionar filtro de tempo: remover apenas jobs com mais de X horas
4. ✅ Separar limpeza de "jobs expirados" vs "limpeza total"
5. ✅ Usar diferentes Redis DBs para diferentes serviços (já está usando DB=2, bom!)

---

## 🟡 PROBLEMAS MÉDIOS

### 5. **Falhas Repetidas de Tasks Celery**

**Observação:**
- Muitas inconsistências indicam que tasks estão falhando com frequência
- Não há logs detalhados do **porquê** as tasks estão falhando

**Solução Necessária:**
1. ✅ Adicionar logging mais verboso em `celery_tasks.py`
2. ✅ Capturar e logar exceções com stack trace completo
3. ✅ Implementar Dead Letter Queue (DLQ) para tasks que falharam todas as tentativas

---

### 6. **Logs Não Consolidados**

**Problema:**
- Apenas `audio-normalization` tem pasta `logs/`
- Outros serviços não têm logs estruturados
- Dificulta troubleshooting

**Solução Necessária:**
1. ✅ Garantir que todos os serviços salvem logs em `./logs/`
2. ✅ Padronizar estrutura: `error.log`, `warning.log`, `info.log`, `debug.log`
3. ✅ Considerar log centralizado (ELK, Loki, ou similar)

---

## 📋 PLANO DE AÇÃO PRIORITIZADO

### 🔴 **PRIORIDADE CRÍTICA (Fazer Agora)**

1. **✅ CORRIGIDO: Circuit Breaker**
   - [x] Implementar half-open state (CLOSED → OPEN → HALF_OPEN)
   - [x] Aumentar tolerância a falhas (5 → 10 falhas)
   - [x] Diminuir timeout de recuperação (5min → 1min)
   - [x] Excluir health checks do circuit breaker (não contam como falhas)
   - [x] Adicionar contador de tentativas no estado HALF_OPEN

2. **✅ CORRIGIDO: Inconsistência Store/Celery**
   - [x] Adicionar signal handlers do Celery (`task_failure`, `task_revoked`)
   - [x] Garantir atualização do Redis em TODOS os caminhos de erro
   - [x] Aplicado em todos os 3 microserviços (audio-normalization, audio-transcriber, video-downloader)
   - [ ] TODO: Implementar job de reconciliação periódica (detecta e corrige inconsistências)

3. **✅ CORRIGIDO: Validação de Tamanho de Arquivo**
   - [x] Corrigir cálculo e log de tamanho (agora mostra MB corretamente)
   - [x] Adicionar logging detalhado: "Arquivo X MB / Y MB permitidos"
   - [ ] TODO: Verificar limites ocultos (nginx, uvicorn) se problema persistir

---

### 🟠 **PRIORIDADE ALTA (Esta Semana)**

4. **Substituir FLUSHDB por Limpeza Granular**
   - [ ] Implementar `SCAN` + `DEL` com padrão de chave
   - [ ] Adicionar filtro de tempo (remover apenas jobs antigos)

5. **Melhorar Logging**
   - [ ] Adicionar logs estruturados em todos os serviços
   - [ ] Criar pasta `logs/` para todos
   - [ ] Adicionar stack traces completos em erros

6. **Implementar Dead Letter Queue**
   - [ ] Capturar tasks que falharam todas as tentativas
   - [ ] Salvar em Redis com TTL
   - [ ] Criar endpoint para visualizar DLQ

---

### 🟡 **PRIORIDADE MÉDIA (Este Mês)**

7. **Monitoramento Proativo**
   - [ ] Adicionar métricas (Prometheus/Grafana)
   - [ ] Alertas para circuit breaker aberto
   - [ ] Alertas para inconsistências Store/Celery

8. **Testes de Resiliência**
   - [ ] Simular falhas de rede
   - [ ] Simular crashes de worker
   - [ ] Validar recuperação automática

---

## 🎯 RESULTADOS ESPERADOS APÓS CORREÇÕES

✅ Circuit breaker não bloqueará serviços funcionais  
✅ Jobs nunca ficarão presos em "processing"  
✅ Arquivos válidos serão aceitos corretamente  
✅ Limpeza será segura e granular  
✅ Logs detalhados facilitarão debugging  
✅ Sistema será mais resiliente e confiável  

---

## 📊 ESTATÍSTICAS DOS LOGS

- **Total de Inconsistências (Store/Celery):** 22+
- **Total de Limpezas Totais:** 15+
- **Total de Arquivos Removidos:** ~50+ arquivos (~6GB)
- **Arquivos Rejeitados (muito grande):** 2 (mas configuração deveria aceitar)
- **Período Analisado:** 2025-10-31 00:31 até 2025-11-01 01:10 (24h)

---

**Próximos Passos:** Implementar correções na ordem de prioridade acima.
