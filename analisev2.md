# Análise de Resiliência v2 - Microserviço Audio Normalization

## Data: 31/10/2025

## 1. Problemas Críticos Identificados

### 1.1 Jobs "Presos" (Stuck Jobs)
**Problema:** Quando um worker do Celery morre inesperadamente (SIGKILL, OOM, etc.), o status do job no Redis pode permanecer como "PROCESSING" indefinidamente, mesmo que a tarefa tenha falhado.

**Impacto:** Jobs ficam presos em estado inconsistente, clientes recebem status incorreto, recursos não são liberados.

**Solução:**
- Implementar detecção de jobs "stale" (presos) baseada em timestamp
- Adicionar tratamento específico para `WorkerLostError` no Celery
- Implementar lógica de reconciliação de estado entre Celery e Redis

### 1.2 Falta de Política de Retentativas
**Problema:** As tarefas do Celery não possuem retentativas automáticas para falhas transitórias (problemas de rede, picos de carga, recursos temporariamente indisponíveis).

**Impacto:** Falhas temporárias causam perda permanente de jobs, requerem intervenção manual.

**Solução:**
- Configurar `autoretry_for` para exceções recuperáveis
- Implementar backoff exponencial nas retentativas
- Definir número máximo de tentativas (3-5)
- Registrar tentativas no log e status do job

### 1.3 Timeouts Inadequados
**Problema:** Timeouts globais podem não ser suficientes para arquivos muito grandes ou operações complexas. Timeouts muito longos podem deixar workers travados.

**Impacto:** Jobs legítimos são cancelados prematuramente ou workers ficam travados indefinidamente.

**Solução:**
- Implementar timeouts adaptativos baseados no tamanho do arquivo
- Usar `soft_time_limit` e `time_limit` no nível da tarefa
- Adicionar timeouts específicos para operações individuais (ffmpeg, noisereduce, etc.)

### 1.4 Falta de Validação de Recursos
**Problema:** O sistema não verifica espaço em disco disponível antes de iniciar processamento, levando a falhas no meio da execução.

**Impacto:** Falhas inesperadas, corrupção de arquivos, jobs que falham tarde demais (após consumir recursos).

**Solução:**
- Verificar espaço em disco antes de iniciar processamento
- Estimar espaço necessário baseado no tamanho do arquivo de entrada
- Implementar margem de segurança (3x tamanho do arquivo)

### 1.5 Limpeza de Arquivos Inconsistente
**Problema:** Arquivos temporários e uploads antigos não são sempre limpos, especialmente em caso de falhas. Blocos `finally` podem não executar em certas condições.

**Impacto:** Disco enche com arquivos órfãos, degradação de performance, necessidade de limpeza manual.

**Solução:**
- Usar context managers para garantir limpeza
- Implementar cleanup em múltiplos pontos (success, failure, finally)
- Adicionar job de limpeza periódica (cron-like)
- Registrar arquivos criados para cleanup posterior

### 1.6 Falta de Controle de Concorrência
**Problema:** Não há limite no número de jobs processados simultaneamente, podendo sobrecarregar o sistema.

**Impacto:** Esgotamento de memória, CPU, disco. Multiple OOM kills.

**Solução:**
- Configurar `worker_prefetch_multiplier=1` (já configurado)
- Adicionar semáforo para limitar jobs simultâneos
- Implementar backpressure no nível da API
- Monitorar e rejeitar jobs quando recursos estão críticos

### 1.7 Falta de Idempotência
**Problema:** Reprocessar um job com mesmo ID pode causar conflitos, sobrescrever arquivos, criar estados inconsistentes.

**Impacto:** Dificuldade em implementar retentativas seguras, risco de corrupção de dados.

**Solução:**
- Verificar se job já existe antes de criar novo
- Permitir reenvio apenas se status = FAILED ou COMPLETED há muito tempo
- Usar locks distribuídos (Redis) para evitar processamento duplicado

### 1.8 Logging Insuficiente para Debugging
**Problema:** Logs não capturam informações suficientes para debug de falhas, especialmente em produção.

**Impacto:** Dificuldade em diagnosticar problemas, tempo longo de resolução.

**Solução:**
- Adicionar logs estruturados com contexto (job_id, arquivo, operações)
- Registrar métricas de performance (tempo, memória, CPU)
- Implementar correlation IDs para rastrear fluxo completo
- Logs de erro devem incluir stack trace completo

### 1.9 Tratamento de Exceções Genérico
**Problema:** Muitos blocos `except Exception` capturam todas as exceções, dificultando identificação de problemas específicos.

**Impacto:** Perda de informação sobre causa raiz, dificuldade em implementar estratégias de recuperação específicas.

**Solução:**
- Capturar exceções específicas primeiro (MemoryError, IOError, etc.)
- Permitir que exceções críticas propaguem (SystemExit, KeyboardInterrupt)
- Logar tipo de exceção específico
- Implementar estratégias de recuperação por tipo de erro

### 1.10 Falta de Health Checks Profundos
**Problema:** Health check apenas verifica se serviço está respondendo, não valida recursos críticos (Redis, disco, ffmpeg).

**Impacto:** Serviço reporta "healthy" mas não consegue processar jobs.

**Solução:**
- Verificar conectividade com Redis
- Verificar espaço em disco
- Verificar disponibilidade de ffmpeg/ffprobe
- Verificar se workers do Celery estão rodando
- Retornar status detalhado (200 OK vs 503 Service Unavailable)

## 2. Melhorias Implementadas

### 2.1 Processamento via Streaming
✅ **Implementado:** Sistema agora detecta arquivos grandes e usa processamento em chunks do disco, evitando carregar arquivo inteiro na memória.

**Benefícios:**
- Elimina OOM em arquivos grandes
- Uso de memória constante e previsível
- Suporta arquivos de qualquer tamanho

### 2.2 Diretório Temporário Configurável
✅ **Implementado:** Chunks temporários agora são salvos em `services/audio-normalization/temp` conforme configuração.

**Benefícios:**
- Melhor organização de arquivos
- Facilita limpeza e monitoramento
- Permite configurar volumes separados

## 3. Próximos Passos

1. **Implementar todas as correções listadas acima**
2. **Aplicar melhorias similares nos outros microserviços:**
   - audio-transcriber
   - video-downloader
   - orchestrator
3. **Realizar auditoria de integração (analisev3.md)**
4. **Implementar testes de resiliência (chaos testing)**
5. **Adicionar métricas e alertas (Prometheus/Grafana)**

## 4. Considerações de Arquitetura

### 4.1 Padrão Circuit Breaker
Considerar implementar circuit breaker para dependências externas (Redis, outros serviços).

### 4.2 Dead Letter Queue
Implementar DLQ para jobs que falharam todas as tentativas, permitindo análise posterior.

### 4.3 Graceful Shutdown
Garantir que workers do Celery finalizam jobs em andamento antes de desligar.

### 4.4 Rate Limiting
Implementar rate limiting na API para evitar sobrecarga.

### 4.5 Monitoramento Proativo
- Métricas de jobs (taxa de sucesso, tempo médio, falhas)
- Alertas para condições anormais
- Dashboard de saúde do sistema

## 5. Conclusão

O microserviço `audio-normalization` possui uma base sólida, mas necessita de melhorias significativas em resiliência, especialmente em:
- **Tratamento de falhas** (retries, error handling)
- **Gerenciamento de recursos** (disk space, memory, concurrency)
- **Observabilidade** (logging, metrics, health checks)
- **Recuperação automática** (stuck jobs, cleanup)

A implementação das melhorias propostas tornará o serviço production-ready, capaz de lidar com cenários adversos sem intervenção manual.
