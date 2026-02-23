# 📦 DATA - Estrutura de Dados da Aplicação

**Versão**: 2.0.0  
**Data**: 14/02/2026

---

## 📋 Visão Geral

Pasta centralizada contendo **TODOS os dados** da aplicação, organizados em um **pipeline claro**.

## 🔄 PIPELINE DE DADOS

```
┌─────────────────────────────────────────────────────────┐
│              PIPELINE COMPLETO DE VÍDEOS                 │
└─────────────────────────────────────────────────────────┘

  📥 data/raw/          Dados brutos (downloads)
      ├── shorts/       Vídeos baixados do YouTube
      ├── audio/        Áudios recebidos via upload
      └── cache/        Cache de downloads
             ↓
             
  🔄 data/transform/    Transformação e conversão
      ├── videos/       Vídeos convertendo para H264
      └── temp/         Temporários (limpeza 1h)
             ↓
             
  ✅ data/validate/     Validação de conteúdo
      ├── in_progress/  Vídeos validando agora
      └── test_datasets/ Datasets de teste (acurácia)
             ↓
             
  ✅ data/approved/     Vídeos aprovados (finais)
      ├── videos/       Aprovados SEM legendas
      └── output/       Processados com áudio
             ↓
             
  📊 data/logs/         Logs e debug
      ├── app/          Logs operacionais
      └── debug/        Debug artifacts
```

---

## 📂 Estrutura Detalhada

### 📥 `data/raw/` - Dados Brutos

**Arquivos originais** antes de qualquer processamento.

```
raw/
├── shorts/              # Vídeos baixados do YouTube (codec original)
│   ├── {video_id}.mp4   # Vídeo bruto
│   └── blacklist.db     # SQLite blacklist
├── audio/               # Áudios recebidos via upload
│   └── {audio_id}.mp3   # Áudio bruto
└── cache/               # Cache de downloads
    └── metadata.json    # Metadados de cache
```

**Características**:
- Arquivos **não modificados**
- Podem ter **codecs incompatíveis** (VP9, HEVC, etc)
- **Temporários** até conversão
- **Não usar diretamente** na aplicação

---

### 🔄 `data/transform/` - Transformação

**Conversão** de arquivos para formatos compatíveis.

```
transform/
├── videos/              # Vídeos sendo convertidos
│   └── {video_id}.mp4   # H264 convertido
└── temp/                # Arquivos temporários
    └── (limpo a cada 1h)
```

**Processamentos**:
1. **Conversão codec**: VP9/HEVC → H264
2. **Padronização**: Formato compatível OpenCV
3. **Correção metadados**: Timecode, rotation
4. **Normalização**: Bitrate, FPS

**Garantias**:
- Saída: Codec H264
- Compatível: OpenCV + FFmpeg
- Metadados corretos

---

### ✅ `data/validate/` - Validação

**Detecção de legendas** e validação de conteúdo.

```
validate/
├── in_progress/         # Vídeos validando agora
│   └── {video_id}.mp4   # Processando
└── test_datasets/       # Datasets de teste (APENAS TESTES)
    ├── sample_OK/       # 7 vídeos sem legendas
    ├── sample_NOT_OK/   # 37 vídeos com legendas
    ├── h264_converted/  # Dataset principal
    ├── edge_cases/      # Casos extremos
    ├── low_quality/     # Baixa qualidade
    ├── multi_resolution/# Várias resoluções
    ├── quick_test/      # Teste rápido
    └── synthetic/       # Sintéticos
```

**Validação**:
- **Detector**: SubtitleDetectorV2 (Força Bruta)
- **Acurácia**: 97.73%
- **Método**: Processa TODOS frames, FULL frame
- **Resultado**: `has_text: true/false`

**Fluxo**:
- `has_text = false` → Move para `approved/`
- `has_text = true` → Blacklist + delete

---

### ✅ `data/approved/` - Aprovados

**Vídeos finais** aprovados e prontos para uso.

```
approved/
├── videos/              # Aprovados SEM legendas
│   └── {video_id}.mp4   # Validados (97.73%)
└── output/              # Processados com áudio
    └── {final_id}.mp4   # Entregues ao usuário
```

**Critérios de Aprovação**:
1. ✅ Baixado (`raw/`)
2. ✅ Convertido H264 (`transform/`)
3. ✅ Validado sem legendas (`validate/`)
4. ✅ `has_text = false`

**Limpeza**:
- `videos/`: Cache 30 dias
- `output/`: Limpo após 24h

---

### 📊 `data/logs/` - Logs

**Logs** da aplicação e debug.

```
logs/
├── app/                 # Logs operacionais
│   ├── makevideo.log    # Log principal
│   └── (rotação automática)
└── debug/               # Debug artifacts
    ├── detection_events/ # Eventos de detecção
    └── artifacts/       # Frames, metadados
```

**Características**:
- Rotação automática
- JSON structured logging
- Separado da estrutura de dados

---

## 🔄 Fluxo Operacional Completo

```python
# 1. DOWNLOAD → data/raw/
video_path = download_youtube_short(video_id)
save_to('data/raw/shorts/{video_id}.mp4')

# 2. CONVERSÃO → data/transform/
converted = convert_to_h264(video_path)
save_to('data/transform/videos/{video_id}.mp4')

# 3. VALIDAÇÃO → data/validate/
detector = SubtitleDetectorV2()
has_text, conf, text, meta = detector.detect(converted)

# 4. APROVAÇÃO → data/approved/
if not has_text:  # SEM legendas (97.73% acurácia)
    move_to('data/approved/videos/{video_id}.mp4')
    
    # 5. PROCESSAR (adicionar áudio)
    final = process_video(video_id)
    save_to('data/approved/output/{final_id}.mp4')
    
    # 6. ENTREGAR
    return final
else:  # COM legendas
    blacklist(video_id)
    delete_all(video_id)
```

---

## 📊 Configuração (Environment Variables)

```bash
# Paths principais (app/core/config.py)
AUDIO_UPLOAD_DIR=./data/raw/audio
SHORTS_CACHE_DIR=./data/raw/shorts
TEMP_DIR=./data/transform/temp
OUTPUT_DIR=./data/approved/output
SQLITE_DB_PATH=./data/raw/shorts/blacklist.db

# Logs
LOG_DIR=./data/logs/app
```

---

## 🎯 Vantagens da Estrutura

### 1️⃣ Organização
- **Tudo em um lugar**: `/data/`
- **Pipeline claro**: raw → transform → validate → approved
- **Fácil backup**: Apenas `/data/`

### 2️⃣ Separação de Responsabilidades
```
raw/       → Apenas downloads
transform/ → Apenas conversões
validate/  → Apenas validações
approved/  → Apenas finais
logs/      → Apenas logs
```

### 3️⃣ Manutenibilidade
- Fácil adicionar estágios
- Fácil debugar (logs separados)
- Fácil limpar (temp automático)

### 4️⃣ Portabilidade
- Uma pasta para mover tudo
- Fácil backup/restore
- Docker volume mount simples

---

## 🗑️ Limpeza Automática

### Temporários (1h)
```bash
# data/transform/temp/
Limpo automaticamente após 1h
```

### Output (24h)
```bash
# data/approved/output/
Vídeos finais limpos após 24h
(usuário já recebeu)
```

### Cache (30 dias)
```bash
# data/raw/shorts/
# data/approved/videos/
Cache mantido por 30 dias
```

---

## 📝 Arquivos de Configuração

### `.gitignore`
```gitignore
# Ignorar dados
data/raw/*
data/transform/*
data/validate/in_progress/*
data/approved/*
data/logs/*

# Manter estrutura e test datasets
!data/raw/.gitkeep
!data/validate/test_datasets/
```

### `.dockerignore`
```dockerignore
data/raw/
data/transform/
data/validate/in_progress/
data/approved/
data/logs/
```

---

## 🚀 Inicialização

### Criação Automática
As pastas são criadas automaticamente pelo código:

```python
# app/core/config.py
def ensure_directories():
    dirs = [
        'data/raw/shorts',
        'data/raw/audio',
        'data/raw/cache',
        'data/transform/videos',
        'data/transform/temp',
        'data/validate/in_progress',
        'data/approved/videos',
        'data/approved/output',
        'data/logs/app',
        'data/logs/debug'
    ]
    for dir in dirs:
        Path(dir).mkdir(parents=True, exist_ok=True)
```

### Docker Volume
```yaml
volumes:
  - ./data:/app/data
```

---

## 📚 Documentação Adicional

- **raw/**: Ver [raw/README.md](raw/README.md)
- **transform/**: Ver [transform/README.md](transform/README.md)
- **validate/**: Ver [validate/README.md](validate/README.md)
- **approved/**: Ver [approved/README.md](approved/README.md)
- **Test datasets**: Ver [validate/test_datasets/README.md](validate/test_datasets/README.md)

---

## ⚠️ Importante

1. **Não modificar** arquivos em `raw/` (originais)
2. **Não usar** vídeos de `test_datasets/` em produção
3. **Não deletar** pastas (apenas conteúdo)
4. **Seguir pipeline**: raw → transform → validate → approved

---

**Criado em**: 14/02/2026  
**Versão**: 2.0.0  
**Pipeline**: data/raw → data/transform → data/validate → data/approved  
**Acurácia**: 97.73% (SubtitleDetectorV2)
