# Segmentação de Roupas

## Objetivo
Substituir o `frozen.h5` do Fashion-AI-segmentation que segmenta roupas muito mal.

## Modelo Oficial: Grounded-SAM-2 ✅
- **Arquitetura**: GroundingDINO (detection) + SAM2 tiny (segmentation)
- **API FastAPI** em `http://localhost:8001/segment`
- **Startup**: ~30s para carregar modelos (CPU)
- **Funciona em CPU**

## Classes Detectáveis
hat, sunglasses, shirt, blouse, jacket, sweater, blazer, cardigan, handbag, skirt, pants, dress, shoes, boots, slippers

---

## Checklist

- [x] Testar 3 candidatos (Segformer, U2NET, Grounded-SAM-2)
- [x] Selecionar Grounded-SAM-2 como modelo padrão
- [x] Criar API FastAPI com Grounded-SAM-2
- [x] Testar API HTTP com ambas as imagens
- [x] Documentar uso da API
- [x] Limpar projetos descartados

---

## Restructure Plan (production-ready)

- [x] Phase 1: Create directory structure (`src/`, `checkpoints/`, `external/`, `data/`, etc.)
- [x] Phase 2: Move external repos to `external/`
- [x] Phase 3: Copy checkpoints from `Grounded-SAM-2-clothes-extraction/weights/` to `checkpoints/`
- [x] Phase 4: Organize data folder (`data/input/`, `data/output/`) — REMOVED, API receives images via HTTP only
- [x] Phase 5: Refactor API into `src/clothes_segmentation/` package
- [x] Phase 6: Create startup scripts (`scripts/start_api.bat`)
- [x] Phase 7: Write README.md, requirements.txt
- [x] Phase 8: Create .gitignore (exclude checkpoints, __pycache__, data/output)
- [x] Phase 9: Update all paths in code to use relative/project-root paths
- [x] Phase 10: Regression test — API works with new structure ✅
- [x] Phase 11: Clean up old `api/` and `Grounded-SAM-2-clothes-extraction/`

---

## Regressão Testada (new structure)

| Test | Status | Result |
|------|--------|--------|
| `/health` | ✅ 200 | `{'status': 'ok', 'model_loaded': True}` |
| `/segment` - trucks (edge case) | ✅ 200 | 1 object: hat (10%) |
| `/segment` - cat_dog | ✅ 200 | 5 objects: sunglasses(27%), blouse(16%), blouse(14%), skirt(18%), skirt(12%) |
| `/segment` - invalid file | ✅ 200 | `{'error': 'Only JPG and PNG images accepted'}` |

## Estrutura Atual
```
src/clothes_segmentation/
├── __init__.py
├── api/server.py        # FastAPI (/segment POST, /health GET, port 8001)
├── core/segmentor.py    # ClothesSegmentor (GroundingDINO + SAM2 pipeline)
└── schemas/models.py    # Pydantic models

external/
├── GroundingDINO/       # GroundingDINO repo (.git intact)
└── segment-anything-2/  # SAM2 repo (.git intact)

checkpoints/
├── groundingdino_swint_ogc.pth  (661.8 MB)
├── sam2_hiera_tiny.pt           (148.7 MB)
└── sam2_hiera_large.pt          (856.4 MB)

scripts/
└── start_api.bat              # Windows startup script

tests/
├── test_api.py                # Regression test suite
└── test_images/               # Test images

Makefile.ps1                   # PowerShell 5.1 build controller
Makefile                       # Git Bash/WSL build controller
requirements.txt               # Exact dependency versions
.gitignore                     # Excludes checkpoints, cache, OS files
```

## Notas
- **CRÍTICO**: numpy<2 obrigatório (h5py incompatível com numpy 2.x)
- **CRÍTICO**: Usar ThreadPoolExecutor para não bloquear event loop do uvicorn
- Projetos descartados removidos: segformer-clothes-tfjs, Virtual_Try_on_FashionGenAi
