# Stack Standardization

Este documento consolida os padroes tecnicos estaveis promovidos a partir da auditoria historica de compatibilidade da stack.

## Objetivo

Usar uma referencia unica para responder:

- quais baselines tecnicos os servicos devem perseguir
- qual estrutura de diretorios e esperada para servicos maduros
- quais templates servem como direcao para configuracao, bootstrap e containerizacao

## Escopo

Este arquivo registra apenas regras e modelos reutilizaveis.

Ele nao registra status de execucao de uma iniciativa, gaps temporarios de conformidade ou progresso de migracao por servico. Esse material continua em `docs/history/UPGRADE_COMPATIBILITY.md`.

## Baseline da stack

### Framework e configuracao

- FastAPI como framework HTTP principal
- `pydantic-settings` para configuracao baseada em ambiente
- `lifespan` no lugar de `@app.on_event` para startup e shutdown
- `prometheus-client` para `/metrics`
- `tenacity` para retries em chamadas externas

### Dependencias core alvo

```txt
fastapi==0.115.12
uvicorn[standard]==0.34.2
pydantic==2.11.3
pydantic-settings==2.7.1
python-multipart==0.0.20
redis==5.2.1
celery==5.5.0
tenacity==9.0.0
prometheus-client==0.21.1
httpx==0.28.1
```

### Regra pratica

- Cada servico pode ter dependencias especificas adicionais.
- O baseline core deve permanecer consistente entre os servicos quando houver upgrade coordenado.
- Alteracoes nesses padroes devem ser refletidas nesta referencia e, quando estruturalmente relevantes, em ADRs.

## Estrutura alvo de servico

Um servico maduro tende a convergir para esta organizacao:

```text
services/<nome-do-servico>/
├── .dockerignore
├── .env.example
├── .gitignore
├── constraints.txt
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pytest.ini
├── README.md
├── requirements.txt
├── requirements-docker.txt
├── run.py
├── app/
│   ├── api/
│   ├── core/
│   ├── domain/
│   ├── infrastructure/
│   └── services/
├── common/
└── tests/
```

## Regras arquiteturais recorrentes

- `config.py` deve centralizar configuracao via `BaseSettings` e cache com `@lru_cache`
- `main.py` deve ser enxuto e focado em bootstrap, middlewares, routers e lifecycle
- `exceptions.py` deve oferecer mapeamento consistente entre excecoes de dominio e respostas HTTP
- `Dockerfile` deve privilegiar usuario nao-root, dependencias minimas e `HEALTHCHECK`
- `run.py` deve ler configuracao do ambiente e evitar valores magicamente hardcoded

## Templates de direcao

Os modelos abaixo sao diretrizes, nao contratos literais:

- `config.py` com `BaseSettings`, validadores e `get_settings()` cacheado
- `main.py` curto com `lifespan`, setup de logs, exception handlers e montagem de routers
- `exceptions.py` com hierarquia de dominio e JSON de erro consistente
- `Dockerfile` com `PYTHONPATH=/app`, usuario nao-root e `HEALTHCHECK`
- `run.py` como bootstrap fino chamando `uvicorn.run(...)`

## Como usar esta referencia

- Em auditorias: compare o servico contra estes padroes e registre desvios no historico
- Em refactors: use esta pagina como baseline para aproximar servicos legados
- Em novos servicos: comece por aqui antes de detalhar documentacao local do servico

## Relacao com o historico

O contexto de execucao, a matriz de conformidade de marco e as decisoes temporais da migracao permanecem em [docs/history/UPGRADE_COMPATIBILITY.md](../history/UPGRADE_COMPATIBILITY.md).