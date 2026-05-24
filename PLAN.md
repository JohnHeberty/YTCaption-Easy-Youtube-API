# Plano de Renomeação: Prefixo `seN-` nos serviços

## Ordem Final

| # | Atual | Novo |
|---|---|---|
| 1 | `orchestrator/` | `se1-orchestrator/` |
| 2 | `video-downloader/` | `se2-video-downloader/` |
| 3 | `audio-normalization/` | `se3-audio-normalization/` |
| 4 | `audio-transcriber/` | `se4-audio-transcriber/` |
| 5 | `make-video/` | `se5-make-video/` |
| 6 | `youtube-search/` | `se6-youtube-search/` |

## Fase 1: Renomear diretórios

```bash
git mv services/orchestrator        services/se1-orchestrator
git mv services/video-downloader    services/se2-video-downloader
git mv services/audio-normalization services/se3-audio-normalization
git mv services/audio-transcriber   services/se4-audio-transcriber
git mv services/make-video          services/se5-make-video
git mv services/youtube-search      services/se6-youtube-search
```

## Fase 2: Atualizar Dockerfiles (6 arquivos)

Cada Dockerfile dentro de `services/seN-*/` referencia `COPY services/NOME/...` — trocar para `COPY services/seN-NOME/...`.

## Fase 3: Atualizar docker-compose (7 arquivos)

- `docker-compose.yml` (raiz)
- `test-docker-compose.yml`
- `services/se1-orchestrator/docker-compose.yml`
- `services/se2-video-downloader/docker-compose.yml`
- `services/se3-audio-normalization/docker-compose.yml`
- `services/se4-audio-transcriber/docker-compose.yml`
- `services/se5-make-video/docker-compose.yml`
- `services/se6-youtube-search/docker-compose.yml`

Mudanças: `dockerfile:` paths, `build:` paths, container names, hostnames, healthcheck URLs, env vars que referenciam containers pelo nome.

## Fase 4: Atualizar código Python do orchestrator (identificadores)

Trocar strings como `"video-downloader"` por `"se2-video-downloader"` em:
- `core/constants.py` — constants enum
- `core/config.py` — default URLs
- `modules/config.py` (legado)
- `modules/orchestrator.py`
- `infrastructure/dependency_injection.py`
- `infrastructure/microservice_client.py` (docstrings)
- `api/pipeline_routes.py`
- `api/admin_routes.py`

## Fase 5: Atualizar scripts (~12 arquivos)

- `Makefile`
- `.github/workflows/ci.yml`
- `scripts/distribute_common.sh`
- `scripts/validate_structure.sh`
- `scripts/run_integration_tests.sh`
- `scripts/test_services_practical.sh`
- `scripts/test_services_real.sh`
- `scripts/test_docker_builds.sh`
- `scripts/validate_migrations.py`
- `scripts/deploy.sh`
- `services/se4-audio-transcriber/scripts/deploy-prod.sh`
- `.gitignore`

## Fase 6: Atualizar documentação (~40+ arquivos)

Substituir:
- `services/orchestrator/` → `services/se1-orchestrator/`
- `services/video-downloader/` → `services/se2-video-downloader/`
- `services/audio-normalization/` → `services/se3-audio-normalization/`
- `services/audio-transcriber/` → `services/se4-audio-transcriber/`
- `services/make-video/` → `services/se5-make-video/`
- `services/youtube-search/` → `services/se6-youtube-search/`

## Fase 7: Atualizar code references no make-video

O make-video referencia `youtube-search` internamente (URLs, logs) — trocar para `se6-youtube-search`.

## Fase 8: Validação

```bash
# Verificar resquícios
rg -n "services/se1-orchestrator" --type-not md
rg -n "services/se2-video-downloader" --type-not md
rg -n "services/se3-audio-normalization" --type-not md
rg -n "services/se4-audio-transcriber" --type-not md
rg -n "services/se5-make-video" --type-not md
rg -n "services/se6-youtube-search" --type-not md

# Build de teste
docker compose build se1-orchestrator se2-video-downloader
```
