# YTCaption v2.0 - Micro-serviços Resilientes

**Status**: Arquitetura v2.0 - Pronto para Implementação  
**Target**: 99.9% uptime | 50ms latency | 10k+ requests/second

## 🏗️ Estrutura

```
projeto_v2/
├── services/                      # 7 Micro-serviços independentes
│   ├── api-gateway/
│   ├── job-manager/
│   ├── downloader/
│   ├── transcriber/
│   ├── storage/
│   ├── notifier/
│   └── admin/
├── shared/                        # Bibliotecas compartilhadas
│   ├── models/
│   ├── events/
│   └── utils/
├── infra/                         # Infraestrutura
│   ├── docker/
│   ├── kubernetes/
│   ├── monitoring/
│   └── backup/
├── docs/                          # Documentação
└── tests/                         # Testes compartilhados
```

## 🚀 Quick Start

1. **Leia primeiro**: `ARQUITETURA.md`
2. **Setup local**: `infra/docker/README.md`
3. **Código**: Cada serviço tem `README.md` próprio
4. **Deploy**: `infra/kubernetes/README.md`

## 📊 Stack Tecnológico

| Camada | Tecnologia |
|--------|-----------|
| Language | Python 3.11+ |
| Framework | FastAPI + AsyncIO |
| Message Broker | RabbitMQ (Queue), gRPC (Sync) |
| Database | PostgreSQL 15+ |
| Cache | Redis (Sentinel HA) |
| Storage | S3-compatible (MinIO/AWS) |
| Container | Docker + Docker Compose |
| Orchestration | Kubernetes |
| Monitoring | Prometheus + Grafana + Jaeger |

## 🎯 Princípios de Design

- **Resiliência First**: Circuit Breaker, Retry, Timeout, Graceful Shutdown
- **Observabilidade**: Distributed Tracing, Structured Logging, Metrics
- **Escalabilidade**: Horizontal, Stateless, Message-driven
- **Segurança**: JWT, RBAC, Secrets management
- **Testing**: Unit, Integration, Contract, E2E

## 📖 Documentação

```
ARQUITETURA.md                  # Design decisions e patterns
ESPECIFICACAO_SERVICOS.md       # Cada serviço detalhado
CONFIGURACAO_RESILIENCIA.md     # Circuit breaker, retry, etc
DEPLOYMENT.md                   # Kubernetes + produção
MONITORAMENTO.md                # Prometheus + alertas
TESTES.md                        # Estratégia de testes
```

---

**Próximo passo**: Leia `ARQUITETURA.md`
