# YTCaption Easy YouTube API

Repositorio de microservicos para busca, download, normalizacao, transcricao e composicao de videos a partir de conteudo do YouTube.

## Visao geral

O projeto e organizado em torno de um `orchestrator/` e de servicos especializados em `services/`.

Principais componentes:

- `orchestrator/` para coordenacao do pipeline
- `services/se6-youtube-search/` para busca e consulta de dados do YouTube
- `services/se2-video-downloader/` para download de video e extracao de audio
- `services/se3-audio-normalization/` para processamento de audio
- `services/se4-audio-transcriber/` para transcricao
- `services/se5-make-video/` para composicao do video final
- `common/` para codigo compartilhado

## Documentacao

A navegacao oficial da documentacao vive em [docs/README.md](docs/README.md).

Trilhas principais:

- [Referencia](docs/reference/README.md)
- [Operacao](docs/operations/README.md)
- [Servicos](docs/services/README.md)
- [Arquitetura](docs/architecture/README.md)
- [Historico](docs/history/README.md)

## Comandos rapidos

```bash
make validate
make dev-setup
make build
make up
make status
```

## Regras praticas

- Documentacao viva deve ser descoberta por `docs/`.
- `AGENTS.md` permanece na raiz como excecao tecnica para tooling.
- Documentos historicos e operacionais devem sair da raiz e ser classificados em `docs/`.