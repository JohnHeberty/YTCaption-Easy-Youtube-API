# 📂 Estrutura do Projeto - Make-Video Service

**Versão**: 2.0.0 (Força Bruta)  
**Última Atualização**: 14/02/2026  
**Status**: ✅ Produção

---

## 🎯 Arquivos Principais

### 🔥 Core (Nova Arquitetura)
```
app/video_processing/
├── subtitle_detector_v2.py          # ✅ Detector Força Bruta (97.73%)
├── subtitle_detector_v2_OLD_SPRINTS.py.bak  # 📦 Backup ROI/Multi-ROI
└── frame_preprocessor_OLD_SPRINTS.py.bak    # 📦 Backup preprocessing
```

### 📊 Testes
```
tests/
├── test_accuracy_official.py        # ✅ Teste oficial (97.73%)
├── OBSOLETE/                         # 🗑️ Testes das Sprints 00-07
│   ├── test_accuracy_*.py            #    17 arquivos obsoletos
│   └── README.md                     #    Documentação dos obsoletos
├── test_sprint0X_*.py                # 📚 Testes das sprints (mantidos)
└── unit/                             # 🧪 Testes unitários
```

### 📖 Documentação
```
docs/
├── NEW_ARCHITECTURE_BRUTE_FORCE.md  # ✅ Arquitetura atual (400+ linhas)
├── SPRINTS_DEPRECATED.md             # ⚠️ Sprints obsoletas (300+ linhas)
├── OBSOLETE/                         # 📦 Docs antigas
├── QUICKSTART.md                     # 🚀 Início rápido
└── MAKEFILE_GUIDE.md                 # 📋 Guia do Makefile
```

### 📝 Sprints
```
sprints/
├── OK_sprint_00_*.md                 # ✅ Sprint 00 completa
├── OK_sprint_01_*.md                 # ✅ Sprint 01 completa
├── OK_sprint_02_*.md                 # ✅ Sprint 02 completa
├── OK_sprint_03_*.md                 # ✅ Sprint 03 completa
├── OK_sprint_04_*.md                 # ✅ Sprint 04 completa
├── OK_sprint_06_*.md                 # ✅ Sprint 06 completa
├── OK_sprint_07_*.md                 # ✅ Sprint 07 completa
├── OBSOLETE/                         # 🗑️ Análises antigas (12 arquivos)
│   ├── CRITICAL_ANALYSIS_*.md
│   ├── SPRINT_07_*.md
│   └── README.md
├── ROADMAP.md                        # 📍 Roadmap geral
└── sprint_0X_*.md                    # 📋 Sprints planejadas
```

---

## 📁 Estrutura Completa

```
services/make-video/
│
├── 📄 README.md                      # ✅ README principal (v2.0.0)
├── 📄 IMPLEMENTATION_COMPLETE.md     # ✅ Resumo implementação
├── 📄 requirements.txt               # 📦 Dependências
├── 📄 pytest.ini                     # 🧪 Configuração pytest
├── 📄 Dockerfile                     # 🐳 Container config
├── 📄 docker-compose.yml             # 🐳 Compose config
│
├── 📁 app/                           # 🎯 Código principal
│   ├── main.py                       # Entrypoint FastAPI
│   ├── config.py                     # Configurações
│   │
│   └── video_processing/             # 🎬 Processamento de vídeo
│       ├── subtitle_detector_v2.py   # ✅ FORÇA BRUTA (97.73%)
│       ├── ensemble_detector.py      # Ensemble (obsoleto)
│       ├── frame_extractor.py        # Extração de frames
│       ├── video_validator.py        # Validação de vídeos
│       ├── visual_features.py        # Features visuais
│       │
│       ├── detectors/                # 🔍 Engines OCR
│       │   ├── paddle_detector.py    # PaddleOCR (usado)
│       │   ├── clip_classifier.py    # CLIP (disponível)
│       │   ├── tesseract_detector.py # Tesseract (disponível)
│       │   └── easyocr_detector.py   # EasyOCR (⚠️ segfaults)
│       │
│       └── voting/                   # 🗳️ Sistemas de votação
│           ├── advanced_voting.py    # Sprint 07 voting
│           ├── conflict_detector.py  # Detecção conflitos
│           └── uncertainty_estimator.py  # Estimação incerteza
│
├── 📁 tests/                         # 🧪 Testes
│   ├── test_accuracy_official.py     # ✅ TESTE OFICIAL (97.73%)
│   ├── OBSOLETE/                     # 🗑️ 17 testes obsoletos
│   ├── test_sprint0X_*.py            # Testes das sprints
│   ├── unit/                         # Testes unitários
│   └── integration/                  # Testes integração
│
├── 📁 docs/                          # 📖 Documentação
│   ├── NEW_ARCHITECTURE_BRUTE_FORCE.md  # ✅ PRINCIPAL
│   ├── SPRINTS_DEPRECATED.md         # Histórico
│   ├── OBSOLETE/                     # Docs antigas
│   ├── QUICKSTART.md                 # Guia rápido
│   └── MAKEFILE_GUIDE.md             # Guia Makefile
│
├── 📁 sprints/                       # 📝 Documentação Sprints
│   ├── OK_sprint_*.md                # Sprints completas
│   ├── OBSOLETE/                     # 12 docs obsoletos
│   ├── ROADMAP.md                    # Roadmap
│   └── sprint_*.md                   # Sprints planejadas
│
├── 📁 storage/                       # 💾 Armazenamento
│   └── validation/                   # Dataset validação
│       ├── sample_OK/                # 7 vídeos SEM texto
│       │   ├── *.mp4
│       │   └── ground_truth.json
│       └── sample_NOT_OK/            # 37 vídeos COM texto
│           ├── *.mp4
│           └── ground_truth.json
│
├── 📁 scripts/                       # 🔧 Scripts auxiliares
│   ├── fix_video_codecs.py          # Converter para H264
│   ├── download_missing_videos.sh   # Download vídeos
│   └── ...
│
└── 📁 common/                        # 📦 Módulos compartilhados
    ├── config_utils/
    ├── log_utils/
    ├── models/
    └── redis_utils/
```

---

## 🎯 Arquivos por Categoria

### ✅ ATIVOS (Em Uso)

#### Código Principal
- `app/video_processing/subtitle_detector_v2.py` - **Detector Força Bruta**
- `app/video_processing/detectors/paddle_detector.py` - PaddleOCR
- `tests/test_accuracy_official.py` - **Teste oficial**

#### Documentação
- `docs/NEW_ARCHITECTURE_BRUTE_FORCE.md` - **Arquitetura atual**
- `docs/SPRINTS_DEPRECATED.md` - Histórico sprints
- `README.md` - README principal
- `IMPLEMENTATION_COMPLETE.md` - Resumo implementação

#### Dataset
- `storage/validation/sample_OK/` - 7 vídeos sem texto
- `storage/validation/sample_NOT_OK/` - 37 vídeos com texto

---

### 📦 BACKUP (Histórico)

#### Código Antigo
- `app/video_processing/subtitle_detector_v2_OLD_SPRINTS.py.bak` - ROI/Multi-ROI
- `app/video_processing/frame_preprocessor_OLD_SPRINTS.py.bak` - Preprocessing

---

### 🗑️ OBSOLETO (Não Usar)

#### Testes (17 arquivos em `tests/OBSOLETE/`)
- `test_accuracy_measurement.py`
- `test_accuracy_2detectors.py`
- `test_accuracy_serialized.py`
- `test_accuracy_final_clean.py`
- `test_accuracy_brute_force.py`
- E mais 12 arquivos...

#### Documentação (12 arquivos em `sprints/OBSOLETE/`)
- `CRITICAL_ANALYSIS_24_PERCENT_ACCURACY.md`
- `SPRINT_07_ACCURACY_STATUS.md`
- `SPRINT_07_FINAL_REPORT.md`
- E mais 9 arquivos...

---

### 📚 REFERÊNCIA (Mantidos)

#### Sprints Completas
- `sprints/OK_sprint_00_*.md` - Sprint 00 (Baseline)
- `sprints/OK_sprint_01_*.md` - Sprint 01 (Resolution)
- `sprints/OK_sprint_02_*.md` - Sprint 02 (Preprocessing)
- `sprints/OK_sprint_03_*.md` - Sprint 03 (Features)
- `sprints/OK_sprint_04_*.md` - Sprint 04 (Multi-ROI)
- `sprints/OK_sprint_06_*.md` - Sprint 06 (Ensemble)
- `sprints/OK_sprint_07_*.md` - Sprint 07 (Weighted Voting)

**Nota**: Mantidos para referência histórica, mas abordagem descontinuada.

---

## 🔍 Navegação Rápida

| Preciso de... | Arquivo |
|---------------|---------|
| **Usar detector** | [subtitle_detector_v2.py](app/video_processing/subtitle_detector_v2.py) |
| **Testar acurácia** | [test_accuracy_official.py](tests/test_accuracy_official.py) |
| **Entender arquitetura** | [NEW_ARCHITECTURE_BRUTE_FORCE.md](docs/NEW_ARCHITECTURE_BRUTE_FORCE.md) |
| **Ver histórico sprints** | [SPRINTS_DEPRECATED.md](docs/SPRINTS_DEPRECATED.md) |
| **Iniciar projeto** | [README.md](README.md) |
| **Scripts auxiliares** | [scripts/](scripts/) |

---

## 📊 Estatísticas

### Arquivos
- **Código ativo**: 1 arquivo principal (subtitle_detector_v2.py)
- **Testes ativos**: 1 principal (test_accuracy_official.py)
- **Testes obsoletos**: 17 arquivos (movidos para OBSOLETE/)
- **Docs obsoletos**: 12 arquivos (movidos para OBSOLETE/)
- **Backups**: 2 arquivos (.bak)

### Linhas de Código
- **Detector atual**: 230 linhas (força bruta)
- **Detector antigo**: 640 linhas (ROI/Multi-ROI)
- **Redução**: -64% de código

### Documentação
- **Nova arquitetura**: 400+ linhas
- **Sprints deprecated**: 300+ linhas
- **READMEs OBSOLETE**: 100+ linhas
- **Total**: 1000+ linhas de documentação

---

## 🎯 Próximos Passos

### Manutenção
1. ✅ Monitorar `test_accuracy_official.py` (deve manter 97.73%)
2. ✅ NÃO modificar `subtitle_detector_v2.py` (funciona perfeitamente)
3. ✅ Documentar novos edge cases se surgirem

### Limpeza Futura (Opcional)
1. Considerar remover testes das sprints antigas (test_sprint0X_*.py)
2. Considerar remover docs das sprints (OK_sprint_*.md)
3. **MAS**: Manter por enquanto para referência histórica

---

**Organizado em**: 14/02/2026  
**Versão**: 2.0.0 (Força Bruta)  
**Status**: ✅ Limpo e Organizado
