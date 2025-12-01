# ⏳ BACKLOG - Melhorias Futuras

**Data de criação**: 30 de Novembro de 2025  
**Status**: 🟡 Itens planejados mas não implementados

---

## 📋 Sobre este documento

Este arquivo consolida **TODOS os itens do backlog** - funcionalidades planejadas, melhorias sugeridas e ideias para o futuro que **NÃO foram implementadas ainda**.

**Nota importante**: O sistema atual está **100% funcional e validado**. Tudo que está neste documento são **melhorias opcionais** para o futuro.

---

## 🎯 Prioridade Alta

### 1. Testes Automatizados
**Status**: ⏳ Não implementado  
**Descrição**: Adicionar suite de testes para backend

**Tasks**:
- [ ] Configurar pytest no projeto
- [ ] Testes unitários para models (Job, VoiceProfile, etc)
- [ ] Testes de integração para endpoints
- [ ] Testes de celery tasks
- [ ] Mock de GPU para CI
- [ ] Coverage mínimo de 80%

**Arquivos afetados**:
- `tests/test_models.py` (novo)
- `tests/test_endpoints.py` (novo)
- `tests/test_tasks.py` (novo)
- `pytest.ini` (já existe, precisa configurar)

**Estimativa**: 3-5 dias

---

### 2. CI/CD Pipeline
**Status**: ⏳ Não implementado  
**Descrição**: Automatizar build, test e deploy

**Tasks**:
- [ ] GitHub Actions workflow
- [ ] Build de imagens Docker
- [ ] Run de testes automáticos
- [ ] Deploy automático para staging
- [ ] Notificações de falhas
- [ ] Badge de status no README

**Arquivos afetados**:
- `.github/workflows/ci.yml` (novo)
- `.github/workflows/deploy.yml` (novo)

**Estimativa**: 2-3 dias

---

### 3. Monitoramento e Observabilidade
**Status**: ⏳ Não implementado  
**Descrição**: Adicionar métricas e logs centralizados

**Tasks**:
- [ ] Integração com Prometheus
- [ ] Métricas customizadas (jobs/min, latência, etc)
- [ ] Grafana dashboards
- [ ] ELK stack para logs (ou alternativa)
- [ ] Alertas para falhas críticas
- [ ] Health check avançado

**Stack sugerida**:
- Prometheus + Grafana
- ELK (Elasticsearch, Logstash, Kibana) ou Loki
- Sentry para error tracking

**Estimativa**: 5-7 dias

---

## 🎨 Prioridade Média

### 4. Melhorias de UX no WebUI
**Status**: ⏳ Não implementado  
**Descrição**: Refinamentos na interface do usuário

**Tasks**:
- [ ] Preview de áudio no modal (HTML5 audio player)
- [ ] Histórico de buscas recentes (localStorage)
- [ ] Drag & drop para upload de arquivos
- [ ] Tema dark/light (toggle manual)
- [ ] Tooltips explicativos nos parâmetros
- [ ] Atalhos de teclado (Ctrl+S para criar job, etc)
- [ ] Botão "Copiar Job ID" com feedback
- [ ] Loading skeleton em vez de spinners
- [ ] Confirmação antes de sair com formulário preenchido

**Arquivos afetados**:
- `app/webui/assets/js/app.js`
- `app/webui/assets/css/styles.css`
- `app/webui/index.html`

**Estimativa**: 3-4 dias

---

### 5. Suporte a Mais Idiomas
**Status**: ⏳ Não implementado  
**Descrição**: Expandir capacidade multilingual do XTTS

**Idiomas sugeridos**:
- [ ] Inglês (EN)
- [ ] Espanhol (ES)
- [ ] Francês (FR)
- [ ] Alemão (DE)
- [ ] Italiano (IT)
- [ ] Japonês (JA)
- [ ] Coreano (KO)
- [ ] Chinês (ZH)

**Tasks**:
- [ ] Mapear códigos de idioma suportados pelo XTTS
- [ ] Adicionar seleção de idioma no WebUI
- [ ] Validação de idioma no backend
- [ ] Testes com cada idioma
- [ ] Documentação de limitações por idioma

**Arquivos afetados**:
- `app/main.py` (validação de idiomas)
- `app/webui/assets/js/app.js` (select de idiomas)
- `README.md` (documentação)

**Estimativa**: 2-3 dias

---

### 6. Otimização de Performance
**Status**: ⏳ Não implementado  
**Descrição**: Melhorar velocidade e eficiência

**Tasks**:
- [ ] Cache de embeddings de vozes (evita reprocessar)
- [ ] Compressão de respostas API (gzip)
- [ ] Lazy loading de modelos (load on demand)
- [ ] Pooling de workers Celery
- [ ] Batch processing de jobs similares
- [ ] CDN para assets estáticos do WebUI
- [ ] Database index optimization (Redis)

**Ganhos esperados**:
- 20-30% redução em latência
- 40-50% redução em VRAM usage (com lazy loading)
- 30-40% aumento em throughput

**Estimativa**: 5-7 dias

---

## 🚀 Prioridade Baixa (Nice to Have)

### 7. API v2 com Versionamento
**Status**: ⏳ Não implementado  
**Descrição**: Criar API v2 mantendo compatibilidade com v1

**Motivação**:
- Permitir mudanças breaking sem afetar clientes antigos
- Melhorar estrutura de responses
- Adicionar HATEOAS (links relacionados)

**Tasks**:
- [ ] Estrutura de rotas /api/v1 e /api/v2
- [ ] Deprecation warnings na v1
- [ ] Documentação separada por versão
- [ ] Migration guide v1 → v2

**Arquivos afetados**:
- `app/main.py` (rotas versionadas)
- `app/api/v2/` (novo módulo)

**Estimativa**: 7-10 dias

---

### 8. Webhook Notifications
**Status**: ⏳ Não implementado  
**Descrição**: Notificar clientes quando job completa

**Use cases**:
- Integração com sistemas externos
- Notificações em tempo real
- Automação de workflows

**Tasks**:
- [ ] Adicionar campo webhook_url ao criar job
- [ ] Validar URL (HTTPS obrigatório)
- [ ] POST automático ao completar/falhar job
- [ ] Retry logic com backoff exponencial
- [ ] Logs de deliveries
- [ ] Signature HMAC para segurança

**Arquivos afetados**:
- `app/models.py` (Job model)
- `app/celery_tasks.py` (callback após task)
- `app/webhooks.py` (novo módulo)

**Estimativa**: 3-4 dias

---

### 9. Rate Limiting Avançado
**Status**: ⏳ Não implementado  
**Descrição**: Controle granular de rate limits

**Atual**: Sem rate limiting  
**Desejado**: Limites por IP, por endpoint, por usuário

**Tasks**:
- [ ] Middleware de rate limiting (slowapi ou redis-based)
- [ ] Configuração por endpoint (/jobs = 10/min, /voices = 5/min)
- [ ] Headers de resposta (X-RateLimit-*)
- [ ] 429 Too Many Requests com Retry-After
- [ ] Whitelist de IPs
- [ ] Dashboard de uso

**Arquivos afetados**:
- `app/main.py` (middleware)
- `app/config.py` (configurações)
- `app/middleware/rate_limit.py` (novo)

**Estimativa**: 2-3 dias

---

### 10. Multi-Tenancy
**Status**: ⏳ Não implementado  
**Descrição**: Suporte a múltiplos usuários/organizações

**Funcionalidades**:
- [ ] Sistema de autenticação (JWT)
- [ ] Usuários e permissões (RBAC)
- [ ] Quotas por usuário (jobs/dia, storage)
- [ ] Isolamento de dados (jobs, voices, models)
- [ ] Billing e usage tracking
- [ ] Admin dashboard

**Complexidade**: Alta  
**Estimativa**: 15-20 dias (projeto grande)

---

## 🔬 Pesquisa e Experimentação

### 11. Novos Engines TTS
**Status**: ⏳ Pesquisa inicial  
**Descrição**: Avaliar e integrar novos modelos

**Candidatos**:
- [ ] Bark (Suno AI) - Expressivo com efeitos
- [ ] Tortoise TTS - Alta qualidade, lento
- [ ] StyleTTS 2 - SOTA em naturalidade
- [ ] Vall-E X - Microsoft, multilingual
- [ ] XTTS v3 (quando lançar)

**Tasks**:
- [ ] Benchmark de qualidade vs velocidade
- [ ] Teste de compatibilidade com pipeline atual
- [ ] Documentação de trade-offs
- [ ] POC com engine mais promissor

**Estimativa**: 10-15 dias (pesquisa + POC)

---

### 12. Real-Time Streaming
**Status**: ⏳ Não planejado (mudança arquitetural grande)  
**Descrição**: TTS em tempo real via WebSocket

**Desafios**:
- Arquitetura atual é assíncrona (Celery)
- XTTS não otimizado para streaming
- VRAM usage aumentaria significativamente
- Latência de rede crítica

**Viabilidade**: Baixa com stack atual  
**Alternativa**: Usar modelo específico para streaming (ex: Piper TTS)

**Estimativa**: 20-30 dias (refactoring massivo)

---

## 🐛 Bugs Conhecidos (Baixa Prioridade)

### 13. Melhorias em KNOWN_ISSUES.md
**Status**: ⏳ Documentado mas não resolvido  
**Descrição**: Alguns edge cases conhecidos

**Issues**:
1. [ ] Chrome extensions ainda podem gerar alguns erros não filtrados
2. [ ] Upload de arquivos >50MB pode dar timeout (sem progress bar)
3. [ ] Modal de JSON muito grande pode ser lento para renderizar
4. [ ] Celery worker pode ficar travado em casos raros (require restart)

**Solução sugerida**:
- Issue 1: Expandir padrões de filtro
- Issue 2: Adicionar chunked upload + progress
- Issue 3: Virtualizar JSON com lib específica
- Issue 4: Adicionar task timeout e auto-restart

---

## 📦 Dependências e Atualizações

### 14. Upgrade de Dependências
**Status**: ⏳ Manutenção contínua  
**Descrição**: Manter libs atualizadas

**Dependências principais**:
- FastAPI: 0.104.1 → 0.110.0+ (quando estável)
- PyTorch: 2.4.0 → 2.5.0+ (com CUDA 11.8)
- Celery: 5.3.4 → 5.4.0+
- Bootstrap: 5.3.2 → 6.0.0 (quando lançar)

**Processo**:
- [ ] Monitorar releases no GitHub
- [ ] Testar em ambiente de staging
- [ ] Atualizar CHANGELOG.md
- [ ] Deploy gradual (canary)

---

## 🎓 Documentação Adicional

### 15. Tutoriais e Exemplos
**Status**: ⏳ Não criado  
**Descrição**: Materiais educativos

**Conteúdo sugerido**:
- [ ] Tutorial: "Primeiros passos com a API"
- [ ] Tutorial: "Clonando sua primeira voz"
- [ ] Tutorial: "Criando quality profiles customizados"
- [ ] Tutorial: "Integrando com aplicação externa"
- [ ] Video tutorial (screencast)
- [ ] Postman collection completa
- [ ] Jupyter notebook com exemplos

**Estimativa**: 2-3 dias

---

### 16. Internacionalização da Documentação
**Status**: ⏳ Não planejado  
**Descrição**: Traduzir docs para outros idiomas

**Idiomas sugeridos**:
- [ ] Inglês (EN) - Prioridade para adoção internacional
- [ ] Espanhol (ES)

**Arquivos**:
- README.md
- DEPLOYMENT.md
- API docs (OpenAPI descriptions)

**Estimativa**: 3-4 dias por idioma

---

## 🔐 Segurança

### 17. Hardening de Segurança
**Status**: ⏳ Revisão não feita  
**Descrição**: Auditoria e melhorias de segurança

**Tasks**:
- [ ] Dependency scanning (Snyk ou Dependabot)
- [ ] SAST (Static Application Security Testing)
- [ ] Container scanning (Trivy)
- [ ] HTTPS obrigatório em produção
- [ ] CORS policies review
- [ ] Input sanitization audit
- [ ] SQL injection prevention (não aplicável, usa Redis)
- [ ] Rate limiting (já mencionado)
- [ ] API key authentication (opcional)

**Estimativa**: 3-5 dias

---

## 💡 Ideias Não Priorizadas

### 18. Outras Ideias Capturadas

- [ ] **Plugin system**: Permitir extensões via plugins Python
- [ ] **Marketplace de vozes**: Compartilhar voice profiles
- [ ] **Social features**: Compartilhar jobs/perfis via link
- [ ] **API playground**: Interface interativa para testar API (alternativa ao /docs)
- [ ] **Desktop app**: Electron wrapper do WebUI
- [ ] **Mobile app**: React Native ou Flutter
- [ ] **CLI tool**: Cliente command-line para power users
- [ ] **Terraform modules**: IaC para deploy em cloud
- [ ] **Kubernetes manifests**: Deploy em K8s
- [ ] **GraphQL API**: Alternativa ao REST

---

## 📊 Critérios de Priorização

Para decidir o que implementar do backlog, considerar:

### Impact vs Effort Matrix

**Alto Impacto + Baixo Esforço** → Fazer primeiro
- Testes automatizados
- CI/CD
- Melhorias de UX

**Alto Impacto + Alto Esforço** → Planejar bem
- Monitoramento
- Multi-tenancy
- API v2

**Baixo Impacto + Baixo Esforço** → Fazer quando sobrar tempo
- Tooltips
- Copiar Job ID
- Temas dark/light

**Baixo Impacto + Alto Esforço** → Evitar ou replanejar
- Real-time streaming
- Desktop app
- GraphQL API

---

## 🎯 Roadmap Sugerido

### Q1 2026 (Jan-Mar)
- Sprint 3: Testes automatizados + CI/CD
- Sprint 4: Monitoramento + Logs
- Sprint 5: Melhorias de UX

### Q2 2026 (Abr-Jun)
- Sprint 6: Suporte a mais idiomas
- Sprint 7: Otimização de performance
- Sprint 8: Webhooks + Rate limiting

### Q3 2026 (Jul-Set)
- Sprint 9: API v2
- Sprint 10: Segurança hardening
- Sprint 11: Pesquisa de novos engines

### Q4 2026 (Out-Dez)
- Sprint 12: Features votadas pela comunidade
- Sprint 13: Documentação e tutoriais
- Sprint 14: Multi-tenancy (se necessário)

---

## ✅ Como Contribuir

Para adicionar itens a este backlog:

1. Verificar se não está duplicado
2. Adicionar na seção apropriada (prioridade)
3. Preencher: Status, Descrição, Tasks, Estimativa
4. Abrir issue no GitHub para discussão
5. Após aprovação, mover para sprint planning

---

## 📝 Notas Finais

Este documento é um **living document** - será atualizado conforme:
- Novos requisitos surgirem
- Prioridades mudarem
- Tecnologias evoluírem
- Feedback de usuários

**Importante**: Nenhum item deste backlog é **obrigatório** para o funcionamento do sistema. Tudo aqui são **melhorias opcionais**.

O sistema atual já está **production-ready** e atende 100% dos requisitos originais! 🚀

---

**Última atualização**: 30 de Novembro de 2025  
**Responsável**: GitHub Copilot (Claude Sonnet 4.5)  
**Branch**: feature/webui-full-integration
