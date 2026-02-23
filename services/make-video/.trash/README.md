# 🗑️ .trash - Arquivos Removidos

**Data**: 14/02/2026  
**Motivo**: Limpeza e organização do projeto

---

## 📋 O que está aqui?

Arquivos que foram **removidos da raiz** do projeto por não serem necessários para **operação da aplicação**.

## 📂 Estrutura

```
.trash/
├── docs/                  # Documentação obsoleta
│   ├── AUDIO_LEGEND_SYNC.md
│   ├── CLEANUP_COMPLETE.md
│   ├── FIX_OCR.md
│   ├── IMPLEMENTATION_COMPLETE.md
│   ├── MAKEFILE_COMANDOS.md
│   ├── OCR_DETECTION.md
│   └── PROJECT_STRUCTURE.md
│
├── logs/                  # Logs antigos de testes
│   ├── baseline_paddleocr.log
│   ├── baseline_paddleocr_v2.log
│   └── pytest_output.log
│
├── old_calibration/       # Scripts de calibração antiga
│   ├── calibrate_trsd_optuna.py
│   ├── demo_calibration.sh
│   ├── monitor_calibration.sh
│   └── baseline_results_synthetic.json
│
├── tests/                 # Testes avulsos da raiz
│   ├── test_accuracy.py
│   ├── test_manual_thresholds.py
│   ├── test_paddleocr_simple.py
│   ├── test_sprint01_baseline.py
│   └── reevaluate_blacklist.py
│
└── scripts_datasets/      # Scripts de geração de datasets
    ├── generate_synthetic_dataset.py
    ├── generate_edge_case_dataset.py
    ├── generate_multi_resolution_dataset.py
    ├── generate_low_quality_dataset.py
    ├── fix_video_codecs.py
    ├── measure_baseline.py
    ├── measure_baseline_simple.py
    ├── download_missing_videos.sh
    └── monitor_baseline.sh
```

---

## 🎯 Critério de Movimentação

Arquivos movidos para `.trash/` se:
- ✅ Não são usados pela aplicação em **produção**
- ✅ São de **desenvolvimento/teste**
- ✅ São **documentação obsoleta**
- ✅ São **logs antigos**
- ✅ São **scripts de calibração/teste**

Arquivos **MANTIDOS** na raiz:
- ✅ Código da aplicação (`app/`)
- ✅ Testes ativos (`tests/`)
- ✅ Configuração (`requirements.txt`, `Dockerfile`, etc)
- ✅ Documentação principal (`README.md`)
- ✅ Biblioteca compartilhada (`common/`)
- ✅ Nova estrutura de dados (`raw/`, `transform/`, `validate/`, `approved/`)

---

## 📝 Arquivos Removidos por Categoria

### 📄 Documentação Obsoleta (7 arquivos)
- `AUDIO_LEGEND_SYNC.md` - Doc sobre sincronização
- `CLEANUP_COMPLETE.md` - Doc de limpeza anterior
- `FIX_OCR.md` - Doc sobre fix de OCR
- `IMPLEMENTATION_COMPLETE.md` - Doc de implementação
- `MAKEFILE_COMANDOS.md` - Comandos do Makefile
- `OCR_DETECTION.md` - Doc de detecção OCR
- `PROJECT_STRUCTURE.md` - Estrutura antiga

### 📊 Logs Antigos (3 arquivos)
- `baseline_paddleocr.log` - Log de baseline (~770KB)
- `baseline_paddleocr_v2.log` - Log v2
- `pytest_output.log` - Output de pytest

### 🔧 Calibração Antiga (4 arquivos)
- `calibrate_trsd_optuna.py` - Script Optuna
- `demo_calibration.sh` - Demo de calibração
- `monitor_calibration.sh` - Monitor
- `baseline_results_synthetic.json` - Resultados

### 🧪 Testes Avulsos (5 arquivos)
- `test_accuracy.py` - Teste de acurácia
- `test_manual_thresholds.py` - Thresholds manuais
- `test_paddleocr_simple.py` - Teste simples PaddleOCR
- `test_sprint01_baseline.py` - Baseline Sprint 01
- `reevaluate_blacklist.py` - Reavaliar blacklist

### 📦 Scripts de Datasets (9 arquivos)
- `generate_synthetic_dataset.py`
- `generate_edge_case_dataset.py`
- `generate_multi_resolution_dataset.py`
- `generate_low_quality_dataset.py`
- `fix_video_codecs.py`
- `measure_baseline.py`
- `measure_baseline_simple.py`
- `download_missing_videos.sh`
- `monitor_baseline.sh`

**Total removido**: 28 arquivos

---

## ⚠️ Posso Deletar .trash/?

**Sim**, pode deletar esta pasta inteira se quiser:

```bash
rm -rf .trash/
```

Todos os arquivos aqui são:
- Não necessários para operação
- Documentação obsoleta
- Logs antigos
- Testes de desenvolvimento

---

## 🔄 Estrutura Nova do Projeto

Após limpeza, a estrutura ficou:

```
services/make-video/
├── app/              # Código da aplicação ✅
├── tests/            # Testes ativos ✅
├── common/           # Biblioteca compartilhada ✅
├── docs/             # Documentação atual ✅
├── sprints/          # Sprints (com OBSOLETE/) ✅
├── logs/             # Logs da aplicação ✅
│   ├── app/          # Logs operacionais
│   └── debug/        # Debug artifacts
├── raw/              # 📥 Dados brutos (downloads) ✅
├── transform/        # 🔄 Transformação (conversão) ✅
├── validate/         # ✅ Validação (detecção) ✅
├── approved/         # ✅ Aprovados (finais) ✅
├── .trash/           # 🗑️ Arquivos removidos
└── [configs]         # Dockerfile, requirements, etc ✅
```

---

## 📚 Referências

- **Nova estrutura**: `raw/` → `transform/` → `validate/` → `approved/`
- **Pipeline**: Download → Conversão → Validação → Aprovação
- **Detector**: SubtitleDetectorV2 (97.73% acurácia)
- **Arquitetura**: docs/NEW_ARCHITECTURE_BRUTE_FORCE.md

---

**Movido em**: 14/02/2026  
**Total**: 28 arquivos  
**Pode deletar**: Sim, sem problemas
