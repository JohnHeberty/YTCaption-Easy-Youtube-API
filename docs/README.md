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
- [SE1 Orchestrator](../services/se1-orchestrator/README.md) — Coordenacao do pipeline | [API](../services/se1-orchestrator/docs/API_REFERENCE.md)
- [SE2 Video Downloader](../services/se2-video-downloader/README.md) — Download de video | [API](../services/se2-video-downloader/docs/API_REFERENCE.md)
- [SE3 Audio Normalization](../services/se3-audio-normalization/README.md) — Normalizacao de audio | [API](../services/se3-audio-normalization/docs/API_REFERENCE.md)
- [SE4 Audio Transcriber](../services/se4-audio-transcriber/README.md) — Transcricao (Whisper) | [API](../services/se4-audio-transcriber/docs/API_REFERENCE.md)
- [SE5 Make Video Clip](../services/se5-make-video-clip/README.md) — Video a partir de shorts | [API](../services/se5-make-video-clip/docs/API_REFERENCE.md)
- [SE6 YouTube Search](../services/se6-youtube-search/README.md) — Busca YouTube | [API](../services/se6-youtube-search/docs/API_REFERENCE.md)
- [SE7 Audio Generation](../services/se7-audio-generation/README.md) — Geracao de audio (Chatterbox) | [API](../services/se7-audio-generation/docs/API_REFERENCE.md)
- [SE8 Image Generation](../services/se8-image-generation/README.md) — Geracao de imagens (SDXL) | [API](../services/se8-image-generation/docs/API_REFERENCE.md)
- [SE9 Make Video IMG](../services/se9-make-video-img/README.md) — Video a partir de imagens | [API](../services/se9-make-video-img/docs/API_REFERENCE.md)
- [SE10 Clothes Segmentation](../services/se10-clothes-segmentation/README.md) — Segmentacao de roupas | [API](../services/se10-clothes-segmentation/docs/API_REFERENCE.md)

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