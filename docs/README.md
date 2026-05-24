# Documentation Hub

Este arquivo e o ponto de entrada oficial da documentacao do repositorio.

## Objetivo

Use este hub para encontrar rapidamente:

- o que o sistema faz
- como ele e estruturado
- como subir e operar o ambiente
- onde esta a documentacao de cada servico
- onde estao as decisoes arquiteturais
- onde consultar historico e relatorios antigos

## Mapa da documentacao

### Reference

- [Reference index](./reference/README.md)
- [Arquitetura geral](./ARCHITECTURE.md)
- [Estrutura do projeto](./PROJECT_STRUCTURE.md)
- [Arquitetura documental](./reference/documentation-architecture.md)

### Operations

- [Operations index](./operations/README.md)
- [Development](./DEVELOPMENT.md)
- [Pre-commit hooks](./PRE_COMMIT_HOOKS.md)
- [Resumo de makefiles](./operations/makefiles-summary.md)
- [Portas e servicos](./operations/ports.md)

### Services

- [Services index](./services/README.md)
- [Orchestrator](./orchestrator/README.md)
- [Audio Normalization](./services/audio-normalization/README.md)
- [Audio Transcriber](./services/audio-transcriber/README.md)
- [Make Video](./services/make-video/README.md)
- [Video Downloader](./services/video-downloader/README.md)

### Architecture Decisions

- [Architecture index](./architecture/README.md)
- [ADR index](./architecture/adr/README.md)
- [ADRs atuais](./adr/)

### History

- [History index](./history/README.md)
- [Resumo da padronizacao de datetime](./history/datetime-standardization-summary.md)
- [Validation](./history/VALIDATION.md)
- [Final validation report](./history/FINAL_VALIDATION_REPORT.md)

## Fluxo recomendado para leitura

1. Comece por este hub para escolher a trilha correta.
2. Use `reference/` para entender o sistema e seus padroes.
3. Use `operations/` para subir, operar e manter o ambiente.
4. Use `services/` para aprofundar em um servico especifico.
5. Use `architecture/adr/` quando precisar entender decisoes de longo prazo.
6. Use `history/` apenas para contexto historico ou rastreabilidade de iniciativas concluidas.

## Regra editorial

- Documentacao viva deve ser facil de descobrir e nao competir com relatorios antigos.
- Novos documentos devem entrar ja classificados dentro da arquitetura documental.
- Quando houver duplicacao entre raiz, `docs/` e `services/*/docs/`, `docs/` deve ser tratado como fonte de navegacao oficial.