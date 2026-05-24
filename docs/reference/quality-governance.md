# Quality and Governance

Este documento consolida os padroes duraveis de qualidade e governanca promovidos a partir do plano historico de execucao do repositório.

## Objetivo

Usar uma referencia unica para responder:

- quais padroes de qualidade o repositório considera obrigatorios
- quais capacidades de teste, observabilidade e manutencao devem existir nos servicos
- quais checks de governanca devem ser preservados ao evoluir a stack

## Escopo

Este arquivo registra regras e expectativas permanentes.

Sequenciamento de tarefas, checklists de marco e backlog de execucao permanecem em `docs/history/PLAN.md`.

## Pilares

### Dependency injection

- Servicos devem evitar acesso direto a globais de `app.main` nas rotas.
- Dependencias de infraestrutura devem ser expostas por factories ou providers dedicados.
- Overrides de teste devem existir quando a infraestrutura precisar ser substituida em testes.

### Testabilidade

- Testes devem convergir para estrutura previsivel em `tests/unit/`, `tests/integration/` e `tests/e2e/`.
- Fixtures e doubles compartilhados devem preferir `common/test_utils/`.
- Para Redis, o baseline de teste favorece `fakeredis` em vez de mocks genéricos.
- Para HTTP clients, o baseline de teste favorece `respx` ou equivalentes deterministas.
- Testes legados podem ser marcados como deprecated, mas nao devem continuar sendo a referencia principal.

### Robustez operacional

- Serializacao no Redis deve ser versionada quando houver risco de evolucao de schema.
- Health checks devem seguir um formato consistente entre servicos.
- Clients entre microservicos devem usar retry com backoff em falhas transitórias.
- Logging estruturado deve ser preferido a configuracoes ad hoc por servico.

### Governanca do repositório

- O repositório deve manter pipeline CI/CD verificando lint e testes rapidos.
- O Makefile da raiz deve expor targets consistentes para lint e execucao de testes rapidos de CI.
- Padrões estruturais de longo prazo devem ser capturados em ADRs quando deixarem de ser apenas convencoes locais.
- Configuracoes duplicadas e conflitantes, como `pytest.ini` redundantes, devem ser eliminadas.

### Contratos de API

- Endpoints publicos devem manter `summary`, `description` e `response_model` consistentes.
- Schemas OpenAPI devem refletir contratos tipados, nao respostas genericas baseadas em `dict` quando houver modelo conhecido.

## Sinais de conformidade

Um servico caminha na direcao certa quando:

- routers usam dependencias explicitamente injetadas
- testes estao classificados por tipo e usam utilitarios compartilhados quando cabivel
- health, logging e retry seguem padroes previsiveis
- lint, CI rapido e documentacao de padroes estao integrados ao fluxo do repositório
- OpenAPI ajuda consumo humano e integracao automatizada

## Como usar esta referencia

- Em refactors: use esta pagina para decidir o que aproximar do baseline
- Em code review: use estes pilares como lente de avaliacao
- Em novos servicos: trate estes pontos como expectativa minima de maturidade

## Relacao com o historico

O plano de execucao, seus itens numerados e seus criterios de validacao detalhados permanecem em [docs/history/PLAN.md](../history/PLAN.md).