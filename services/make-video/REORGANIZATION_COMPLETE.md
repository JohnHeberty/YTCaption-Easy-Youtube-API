# 🔄 REORGANIZAÇÃO COMPLETA - Estrutura data/

**Data**: 14/02/2026  
**Versão**: 2.0.0  
**Status**: ✅ COMPLETO

---

## 📋 Resumo

Reorganização completa com **TODOS os dados dentro de `data/`** para máxima organização.

### 🎯 Estrutura Final

```
services/make-video/
├── app/              # Código da aplicação
├── tests/            # Testes ativos
├── common/           # Biblioteca compartilhada
├── docs/             # Documentação
├── sprints/          # Sprints (com OBSOLETE/)
│
├── data/             # ⭐ TODOS OS DADOS AQUI
│   ├── raw/          # 📥 Dados brutos (downloads)
│   ├── transform/    # 🔄 Conversão H264
│   ├── validate/     # ✅ Validação legendas
│   ├── approved/     # ✅ Vídeos finais
│   └── logs/         # 📊 Logs e debug
│
├── .trash/           # 🗑️ Arquivos removidos (28)
└── [configs]         # Docker, requirements, etc
```

---

## 🔄 PIPELINE (Dentro de data/)

```
data/raw/              📥 Downloads originais
    ↓
data/transform/        🔄 Conversão H264
    ↓
data/validate/         ✅ Detecção legendas (97.73%)
    ↓
data/approved/         ✅ Vídeos finais
    ↓
ENTREGA AO USUÁRIO
```

---

## 📂 Estrutura Detalhada

### 📦 `data/` - Pasta Central

```
data/
├── raw/                    # Dados brutos
│   ├── shorts/             # Vídeos baixados
│   │   ├── {video_id}.mp4
│   │   └── blacklist.db    # SQLite blacklist
│   ├── audio/              # Áudios recebidos
│   └── cache/              # Cache downloads
│
├── transform/              # Transformação
│   ├── videos/             # Convertendo H264
│   └── temp/               # Temporários (limpa 1h)
│
├── validate/               # Validação
│   ├── in_progress/        # Validando agora
│   └── test_datasets/      # Datasets (APENAS TESTES)
│       ├── sample_OK/      # 7 vídeos sem legendas
│       ├── sample_NOT_OK/  # 37 vídeos com legendas
│       ├── h264_converted/ # Dataset principal
│       ├── edge_cases/     # Casos extremos
│       ├── low_quality/    # Baixa qualidade
│       ├── multi_resolution/ # Várias resoluções
│       ├── quick_test/     # Teste rápido
│       └── synthetic/      # Sintéticos
│
├── approved/               # Aprovados
│   ├── videos/             # SEM legendas (validados)
│   └── output/             # COM áudio (finais)
│
└── logs/                   # Logs
    ├── app/                # Operacionais
    │   └── makevideo.log
    └── debug/              # Debug artifacts
        ├── detection_events/
        └── artifacts/
```

---

## 🔧 PATHS ATUALIZADOS

### Arquivos Modificados (7)

#### 1️⃣ `app/core/config.py`
```python
# Storage Paths
audio_upload_dir: str = "./data/raw/audio"
shorts_cache_dir: str = "./data/raw/shorts"
temp_dir: str = "./data/transform/temp"
output_dir: str = "./data/approved/output"
sqlite_db_path: str = "./data/raw/shorts/blacklist.db"
```

#### 2️⃣ `app/infrastructure/file_logger.py`
```python
LOGS_DIR = Path("/app/data/logs/app")
```

#### 3️⃣ `app/infrastructure/telemetry.py`
```python
events_dir = Path('data/logs/debug/detection_events')
base_dir: str = 'data/logs/debug/artifacts'
```

#### 4️⃣ `app/video_processing/video_validator.py`
```python
base_dir='data/logs/debug/artifacts'
```

#### 5️⃣ `app/services/blacklist_factory.py`
```python
db_path = "./data/raw/shorts/blacklist.db"
```

#### 6️⃣ `tests/test_accuracy_official.py`
```python
base_path = Path('data/validate/test_datasets')
```

#### 7️⃣ `app/video_processing/subtitle_detector_v2.py`
```python
test_video = "data/validate/test_datasets/sample_OK/5Bc-aOe4pC4.mp4"
```

---

## 🗑️ LIMPEZA (28 arquivos → .trash/)

### Total Removido
- **7 docs obsoletos** → `.trash/docs/`
- **3 logs antigos** (770KB) → `.trash/logs/`
- **4 scripts calibração** → `.trash/old_calibration/`
- **5 testes avulsos** → `.trash/tests/`
- **9 scripts datasets** → `.trash/scripts_datasets/`

**Pode deletar**: `rm -rf .trash/`

---

## 📚 DOCUMENTAÇÃO (8 READMEs)

1. ✅ `data/README.md` - Estrutura completa (principal)
2. ✅ `data/raw/README.md` - Dados brutos
3. ✅ `data/transform/README.md` - Transformação
4. ✅ `data/validate/README.md` - Validação
5. ✅ `data/approved/README.md` - Aprovados
6. ✅ `data/validate/test_datasets/README.md` - Datasets
7. ✅ `.trash/README.md` - Arquivos removidos
8. ✅ Este arquivo - Resumo completo

**Total**: ~2000 linhas de documentação

---

## 🎯 BENEFÍCIOS

### 1️⃣ Organização Total
```
ANTES ❌: storage/ + logs/ + raw/ + transform/ + etc (espalhado)
DEPOIS ✅: data/ (tudo em um lugar)
```

### 2️⃣ Backup Simples
```bash
# Backup de TUDO
tar -czf backup.tar.gz data/

# Restore
tar -xzf backup.tar.gz
```

### 3️⃣ Docker Simplificado
```yaml
volumes:
  - ./data:/app/data  # Uma linha = tudo
```

### 4️⃣ Gitignore Limpo
```gitignore
data/*              # Ignora todos os dados
!data/**/.gitkeep   # Mantém estrutura
!data/validate/test_datasets/  # Mantém datasets
```

---

## 📊 ESTATÍSTICAS

| Métrica | Valor |
|---------|-------|
| **Pasta central** | `data/` ✅ |
| **Subpastas** | 5 (raw, transform, validate, approved, logs) |
| **Arquivos movidos** | 28 → `.trash/` |
| **Arquivos atualizados** | 7 Python |
| **READMEs criados** | 8 (~2000 linhas) |
| **Pipeline** | data/raw → transform → validate → approved |

---

## 🔄 FLUXO OPERACIONAL

```python
# 1. DOWNLOAD → data/raw/
video = download_youtube(video_id)
save('data/raw/shorts/{video_id}.mp4')

# 2. CONVERSÃO → data/transform/
h264_video = convert_to_h264(video)
save('data/transform/videos/{video_id}.mp4')

# 3. VALIDAÇÃO → data/validate/
detector = SubtitleDetectorV2()
has_text, conf, text, meta = detector.detect(h264_video)

# 4. DECISÃO
if not has_text:
    # SEM legendas (97.73% acurácia)
    move_to('data/approved/videos/{video_id}.mp4')
    
    # 5. PROCESSAR → data/approved/output/
    final = add_audio(video_id)
    save('data/approved/output/{final_id}.mp4')
    
    # 6. ENTREGAR
    return final
else:
    # COM legendas
    blacklist(video_id)
    delete_all(video_id)
```

---

## 🚀 AMBIENTE (Environment Variables)

```bash
# Atualizar .env com novos paths

# Storage
AUDIO_UPLOAD_DIR=./data/raw/audio
SHORTS_CACHE_DIR=./data/raw/shorts
TEMP_DIR=./data/transform/temp
OUTPUT_DIR=./data/approved/output
SQLITE_DB_PATH=./data/raw/shorts/blacklist.db

# Logs
LOG_DIR=./data/logs/app
```

---

## 🗑️ LIMPEZA AUTOMÁTICA

### Temporários (1h)
```
data/transform/temp/ → Limpo a cada 1h
```

### Output (24h)
```
data/approved/output/ → Limpo após 24h
(usuário já recebeu vídeo)
```

### Cache (30 dias)
```
data/raw/shorts/ → Cache 30 dias
data/approved/videos/ → Cache 30 dias
```

---

## ✅ CHECKLIST

### Estrutura
- [x] `data/` criada
- [x] `data/raw/` criada (shorts, audio, cache)
- [x] `data/transform/` criada (videos, temp)
- [x] `data/validate/` criada (in_progress, test_datasets)
- [x] `data/approved/` criada (videos, output)
- [x] `data/logs/` criada (app, debug)

### Código
- [x] `app/core/config.py` atualizado
- [x] `app/infrastructure/file_logger.py` atualizado
- [x] `app/infrastructure/telemetry.py` atualizado
- [x] `app/video_processing/video_validator.py` atualizado
- [x] `app/services/blacklist_factory.py` atualizado
- [x] `tests/test_accuracy_official.py` atualizado
- [x] `app/video_processing/subtitle_detector_v2.py` atualizado

### Documentação
- [x] `data/README.md` criado (principal)
- [x] `data/raw/README.md` criado
- [x] `data/transform/README.md` criado
- [x] `data/validate/README.md` criado
- [x] `data/approved/README.md` criado
- [x] `data/validate/test_datasets/README.md` criado
- [x] `.trash/README.md` criado
- [x] Este arquivo criado

### Limpeza
- [x] 28 arquivos movidos para `.trash/`
- [x] storage/ deletada
- [x] Raiz limpa

---

## 📚 REFERÊNCIAS

### Documentação Principal
- **Estrutura completa**: [data/README.md](data/README.md) ⭐
- **Pipeline**: data/raw → transform → validate → approved

### Documentação Específica
- **Raw**: [data/raw/README.md](data/raw/README.md)
- **Transform**: [data/transform/README.md](data/transform/README.md)
- **Validate**: [data/validate/README.md](data/validate/README.md)
- **Approved**: [data/approved/README.md](data/approved/README.md)
- **Test Datasets**: [data/validate/test_datasets/README.md](data/validate/test_datasets/README.md)
- **Removidos**: [.trash/README.md](.trash/README.md)

### Arquitetura
- **Detector**: SubtitleDetectorV2 (força bruta)
- **Acurácia**: 97.73%
- **Docs**: docs/NEW_ARCHITECTURE_BRUTE_FORCE.md

---

## 🎉 RESULTADO FINAL

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│    ✅ REORGANIZAÇÃO COMPLETA ✅                        │
│                                                         │
│    Estrutura:     data/ (tudo organizado)              │
│    Pipeline:      raw → transform → validate → approved│
│    Arquivos:      28 movidos para .trash/             │
│    Paths:         7 arquivos atualizados               │
│    Documentação:  8 READMEs (~2000 linhas)             │
│                                                         │
│    ANTES: storage/ bagunçada + arquivos soltos ❌      │
│    DEPOIS: data/ organizada + raiz limpa ✅            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

**Reorganizado em**: 14/02/2026  
**Versão**: 2.0.0  
**Estrutura**: `data/` (centralizada) ✅  
**Pipeline**: data/raw → transform → validate → approved ✅  
**Documentação**: 8 READMEs completos ✅
