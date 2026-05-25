# 🔍 CHECK.md — Pendências

## PENDENTES

### PRIORIDADE 2 — ALTO
- [x] 2.3. Migration script para converter jobs antigos no Redis (naive → aware)
      Executar: python scripts/migrate_redis_jobs.py --execute --host <host>

### PRIORIDADE 3 — MÉDIO
- [ ] 3.1. Error handling robusto em operações de datetime
      try/except com fallback
- [ ] 3.2. Logging quando detecta datetime naive / faz conversão automática
- [ ] 3.3. Endpoint de diagnóstico GET /debug/timezone-status

### PRIORIDADE 4 — BAIXO
- [ ] 4.1. Documentar convenções de timezone nos READMEs
- [ ] 4.3. Script de validação CI/CD (detecta datetime.now() / utcnow())

### PRÓXIMOS PASSOS (Backlog)
- [ ] P2: CI/CD lint rule para bloquear datetime.now()
- [ ] P3: Monitoring de datetime errors no Grafana
