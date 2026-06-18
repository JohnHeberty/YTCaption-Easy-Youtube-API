# PLANO DE ISOLAMENTO TOTAL: SE9 vs FOOOCUS

## Objetivo

Eliminar 100% das dependências externas do FOOOCUS. Tudo deve residir dentro de `services/se8-image-generation/`.

## Contexto Atual

SE9 tem 8,903 linhas próprias (42 arquivos) mas faz 81 imports de 3 pacotes FOOOCUS:

| Pacote FOOOCUS | Import Sites | Submodulos Únicos | Arquivos Fonte |
|---|---|---|---|
| `ldm_patched.*` | 48 | 28 subpaths | 143 arquivos |
| `modules.*` | 25 | 7 submodules | 30 arquivos + JSONs |
| `extras.*` | 7 | 6 submodules | 52+ arquivos |
| `fooocusapi.*` | 1 | 1 | 1 (2 funções utilitárias) |
| **TOTAL** | **81** | **42** | **~225 arquivos** |

## Estratégia: Vendor no Root do SE9

Copiar os 3 pacotes FOOOCUS como pacotes irmãos na raiz de `services/se8-image-generation/`. Isso garante ZERO import changes no código FOOOCUS e ZERO import changes nos 12 arquivos SE9 que consomem FOOOCUS.

## Estrutura Final

```
services/se8-image-generation/
├── app/                    # CÓDIGO SE9 (INALTERADO)
├── ldm_patched/            # 🆕 VENDORED (143 arquivos, 3.3MB)
├── modules/                # 🆕 VENDORED (18 arquivos + sdxl_styles/)
├── sdxl_styles/            # 🆕 JSONs de estilos (6 arquivos)
├── args_manager.py         # 🆕 CLI args do FOOOCUS root
├── extras/                 # 🆕 VENDORED (~53 arquivos, 1.2MB)
├── tests/                  # Inalterado
├── docker/                 # Atualizar Dockerfiles
├── data/                   # Inalterado (12GB models)
└── pyproject.toml          # Atualizar
```

## Fases de Implementação

### Fase 1: Copiar ldm_patched/
- Origem: `FOOOCUS/Fooocus/ldm_patched/`
- Destino: `services/se8-image-generation/ldm_patched/`
- Método: `cp -r` integral, zero modificações

### Fase 2: Copiar modules/ (18 arquivos) + sdxl_styles/
- Origem: `FOOOCUS/Fooocus/modules/` (apenas 18 arquivos necessários)
- Origem: `FOOOCUS/Fooocus/sdxl_styles/` (apenas 6 JSONs, sem samples/)
- Destino: `services/se8-image-generation/modules/` + `sdxl_styles/`
- Pós: Adaptar paths em `modules/config.py` (12 linhas)

### Fase 3: Copiar extras/
- Origem: `FOOOCUS/Fooocus/extras/` (diretório inteiro)
- Destino: `services/se8-image-generation/extras/`

### Fase 4: Copiar args_manager.py
- Origem: `FOOOCUS/Fooocus/args_manager.py`
- Destino: `services/se8-image-generation/args_manager.py`

### Fase 5: Adaptar modules/config.py paths
- Trocar 12 linhas de paths relativos para paths baseados em `MODEL_DIR`

### Fase 6: Fix tools_routes.py fooocusapi import
- Substituir 2 funções importadas de `fooocusapi.utils.img_utils` com inline code

### Fase 7: Atualizar Dockerfile.gpu-api
- Adicionar 5 COPY statements para os novos pacotes

### Fase 8: Atualizar pyproject.toml

### Fase 9-12: Build, Test, Validate, Commit

## Critérios de Aceite

```
✅ Zero imports de "FOOOCUS/" ou "../FOOOCUS/" em app/
✅ Zero imports de "fooocusapi" em app/
✅ docker compose build → sucesso
✅ docker compose up → /health → 200
✅ POST /v1/generation/text-to-image → 200 + imagem real
✅ pytest → 104+ tests passing
✅ VALID.md atualizado
✅ Git commit
```

## Arquivos modules/ NÃO Copiar (UI-only)
- gradio_hijack.py, style_sorter.py, ui_gradio_extensions.py
- meta_parser.py, auth.py, localization.py, html.py
- launch_util.py, async_worker.py, private_logger.py, hash_cache.py
