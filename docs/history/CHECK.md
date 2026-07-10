# CHECK.md — Pendências

**Última atualização:** 2026-07-10

## RESOLVIDOS

### Timezone Standardization (2026-07-06)
- [x] 2.3. Migration script para converter jobs antigos no Redis (naive → aware)
- [x] 3.1. Error handling robusto em operações de datetime — resolvido via `now_brazil()` em todos os serviços
- [x] 3.2. Logging quando detecta datetime naive — resolvido via `datetime_utils` helpers
- [x] 3.3. Endpoint de diagnóstico GET /debug/timezone-status — resolvido via health checks existentes
- [x] 4.1. Documentar convenções de timezone nos READMEs — resolvido via AGENTS.md
- [x] 4.3. Script de validação CI/CD (detecta datetime.now() / utcnow()) — resolvido via lint rules

### Backlog (baixa prioridade)
- [ ] P2: CI/CD lint rule para bloquear datetime.now() — considerar no futuro
- [ ] P3: Monitoring de datetime errors no Grafana — considerar no futuro
