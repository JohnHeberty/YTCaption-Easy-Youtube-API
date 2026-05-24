# Makefiles e Comandos

Este documento resume os comandos operacionais principais do repositório a partir do `Makefile` da raiz.

## Objetivo

Use esta pagina para descobrir rapidamente:

- como validar o projeto sem subir servicos
- como instalar dependencias de desenvolvimento
- como buildar, subir, parar e inspecionar servicos
- como operar um servico especifico pelo padrao `comando-servico`

## Fluxo recomendado

```bash
make validate
make dev-setup
make build
make up
make status
```

## Comandos globais da raiz

### Setup e validacao

- `make help` - lista os targets documentados
- `make install` - cria venv e instala dependencias
- `make create-venv` - cria o ambiente virtual local
- `make install-requirements` - instala os `requirements.txt` dos servicos
- `make validate` - roda a validacao completa sem subir servicos
- `make dev-setup` - instala dependencias e valida o projeto
- `make lint` - executa black, isort, flake8, mypy e bandit
- `make test-ci` - executa a bateria rapida pensada para CI

### Operacao global

- `make build` - builda o compose da raiz e os composes de servico
- `make up` - sobe o ambiente da raiz e os servicos com compose proprio
- `make down` - derruba todos os servicos
- `make restart` - reinicia tudo
- `make logs` - mostra logs agregados dos servicos
- `make status` - mostra status dos containers
- `make healthcheck` - consulta os health endpoints disponiveis

### Limpeza e diagnostico

- `make clean` - remove containers, volumes e imagens nao utilizadas
- `make clean-venv` - remove o ambiente virtual local
- `make clean-all` - limpeza completa de containers e venv
- `make list-services` - lista os servicos conhecidos pelo Makefile
- `make check-ports` - mostra portas em uso
- `make check-port-conflicts` - ajuda a diagnosticar conflitos de porta
- `make docker-info` - resume informacoes do Docker local

## Padrao por servico

O Makefile da raiz expõe comandos no formato `comando-servico`.

Servicos suportados:

- `audio-normalization`
- `audio-transcriber`
- `make-video`
- `video-downloader`
- `youtube-search`

Exemplos:

```bash
make build-youtube-search
make up-audio-normalization
make down-video-downloader
make restart-audio-transcriber
make logs-make-video
make status-youtube-search
make validate-audio-normalization
make build-only-make-video
```

## Quando usar o Makefile do servico

Quando precisar de comandos especificos de um servico, entre no diretorio dele e rode `make help`.

Exemplos de comandos que costumam existir apenas localmente:

- targets de teste especializados
- utilitarios de shell no container
- comandos de calibracao do `make-video`
- comandos de busca ou smoke tests do `youtube-search`
- operacao local do `orchestrator`

## Observacoes

- Esta pagina evita listar todos os comandos locais de cada servico, porque isso envelhece rapido.
- A referencia estavel aqui e o fluxo operacional da raiz.
- Para portas e health endpoints, use [ports.md](./ports.md).
