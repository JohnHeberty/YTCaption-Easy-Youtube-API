# YTCaption Easy YouTube API

Repositorio de microservicos para busca, download, normalizacao, transcricao e composicao de videos a partir de conteudo do YouTube.

## Visao geral

O projeto e organizado em torno de servicos especializados em `services/` e uma biblioteca compartilhada em `shared/`.

Principais componentes:

| Service | Descricao | Porta |
|---------|-----------|-------|
| [SE1 Orchestrator](services/se1-orchestrator/) | Coordenacao do pipeline | 8001 |
| [SE2 Video Downloader](services/se2-video-downloader/) | Download de video e extracao de audio | 8002 |
| [SE3 Audio Normalization](services/se3-audio-normalization/) | Processamento e normalizacao de audio | 8003 |
| [SE4 Audio Transcriber](services/se4-audio-transcriber/) | Transcricao de audio (Whisper) | 8004 |
| [SE5 Make Video Clip](services/se5-make-video-clip/) | Composicao de video a partir de shorts | 8005 |
| [SE6 YouTube Search](services/se6-youtube-search/) | Busca e consulta de dados do YouTube | 8006 |
| [SE7 Audio Generation](services/se7-audio-generation/) | Geracao de audio (Chatterbox TTS) | 8007 |
| [SE8 Image Generation](services/se8-image-generation/) | Geracao de imagens (Stable Diffusion) | 8008 |
| [SE9 Make Video IMG](services/se9-make-video-img/) | Geracao de video a partir de imagens + narração | 8009 |
| [SE10 Clothes Segmentation](services/se10-clothes-segmentation/) | Segmentacao de roupas (SAM-2) | 8010 |

Biblioteca compartilhada: [shared/](shared/)

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
- Cada servico deve ter um `README.md` padronizado e `docs/` com documentacao detalhada.
