# ⚠️ Test Datasets - Vídeos Removidos

**Status**: Estrutura criada, vídeos removidos (pesados)

## 📊 Datasets Disponíveis

Esta pasta conteria os datasets de teste para validação da acurácia do **SubtitleDetectorV2**.

### 📁 Estrutura

```
test_datasets/
├── sample_OK/          # 7 vídeos SEM legendas
├── sample_NOT_OK/      # 37 vídeos COM legendas  
├── h264_converted/     # Dataset principal H264 (44 vídeos)
│   ├── OK/             # 7 vídeos sem legendas
│   └── NOT_OK/         # 37 vídeos com legendas
├── edge_cases/         # Casos extremos (top, left, right, center)
├── low_quality/        # Baixa qualidade
├── multi_resolution/   # Várias resoluções
├── quick_test/         # Teste rápido (4 vídeos)
│   ├── OK/             # 2 sem legendas
│   └── NOT_OK/         # 2 com legendas
└── synthetic/          # Vídeos sintéticos
```

## ⚠️ Vídeos Removidos

Os vídeos foram **removidos** desta pasta pois:
- São muito pesados (~500MB+)
- Não são necessários para **operação da aplicação**
- Apenas para **testes de acurácia** (desenvolvimento)

## 🔄 Como Regenerar (se necessário)

Se precisar rodar testes de acurácia novamente:

### Opção 1: Baixar Dataset (se disponível)
```bash
# Baixar dataset de backup (se existe)
wget https://[URL_BACKUP]/test_datasets.tar.gz
tar -xzf test_datasets.tar.gz -C validate/test_datasets/
```

### Opção 2: Gerar Sintéticos
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video

# Gerar vídeos sintéticos
python scripts/generate_synthetic_dataset.py --output validate/test_datasets/synthetic

# Gerar edge cases
python scripts/generate_edge_case_dataset.py --output validate/test_datasets/edge_cases

# Gerar multi-resolução
python scripts/generate_multi_resolution_dataset.py --output validate/test_datasets/multi_resolution

# Gerar baixa qualidade
python scripts/generate_low_quality_dataset.py --output validate/test_datasets/low_quality
```

### Opção 3: Usar Vídeos Reais
```bash
# Baixar shorts do YouTube
# Rotular manualmente (has_subtitles: true/false)
# Criar ground_truth.json
```

## 📊 Ground Truth Format

Cada dataset precisa de um `ground_truth.json`:

```json
{
  "dataset": "sample_OK",
  "description": "Vídeos sem legendas",
  "videos": [
    {
      "filename": "video_id.mp4",
      "has_subtitles": false,
      "video_id": "video_id",
      "title": "Título do vídeo"
    }
  ]
}
```

## 🎯 Acurácia Atual

**SubtitleDetectorV2** (Força Bruta):
- **Acurácia**: 97.73%
- **Precision**: 97.37%
- **Recall**: 100%
- **F1-Score**: 98.67%

Testado com:
- 44 vídeos (7 OK + 37 NOT_OK)
- 50 frames por vídeo
- Dataset: h264_converted

## ⚠️ Nota Importante

Esta pasta é **apenas para testes**. A aplicação em **produção** NÃO usa esses datasets.

Pipeline de produção:
```
raw/ → transform/ → validate/ → approved/
```

Os vídeos de teste são independentes do pipeline de produção.

---

**Criado em**: 14/02/2026  
**Vídeos removidos**: 14/02/2026  
**Acurácia validada**: 97.73%
