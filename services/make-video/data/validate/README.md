# ✅ VALIDATE - Validação de Conteúdo

Pasta onde os vídeos de `transform/` são **validados** para detectar legendas/texto.

## 📂 Estrutura

```
validate/
├── in_progress/       # Vídeos sendo validados agora
├── test_datasets/     # Datasets de testes (ground truth)
│   ├── edge_cases/    # Casos extremos (top, left, right, center)
│   ├── h264_converted/# Vídeos convertidos H264
│   ├── low_quality/   # Baixa qualidade
│   ├── multi_resolution/ # Várias resoluções
│   ├── quick_test/    # Teste rápido
│   └── synthetic/     # Vídeos sintéticos
└── (futuro)           # Outras validações
```

## 🔄 Fluxo

```
transform/ (vídeos convertidos)
       ↓
✅ validate/ (detecção de legendas)
       ↓
approved/ (vídeos SEM legendas - próximo passo)
```

## 📝 Tipo de Validação

### 🎯 Detecção de Legendas (SubtitleDetectorV2)
- **Método**: Força Bruta (97.73% acurácia)
- **Detector**: PaddleOCR 2.7.3 GPU
- **Processa**: TODOS os frames, FULL frame
- **Resultado**: `has_text: true/false`

### ✅ Vídeo APROVADO (vai para `approved/`)
- `has_text = false` → SEM legendas detectadas
- Pronto para uso na aplicação

### ❌ Vídeo REJEITADO
- `has_text = true` → COM legendas detectadas
- Não vai para `approved/`
- Blacklist automática

## 📊 Test Datasets

### edge_cases/
Testa posições de texto:
- `top/` - Texto no topo
- `left/` - Texto à esquerda
- `right/` - Texto à direita
- `center/` - Texto centralizado
- `multi_position/` - Várias posições

### h264_converted/
Dataset principal (44 vídeos):
- `OK/` - 7 vídeos SEM legendas
- `NOT_OK/` - 37 vídeos COM legendas
- Ground truth validado

### low_quality/
Vídeos de baixa qualidade:
- Resoluções baixas
- Compressão alta
- Ruído

### multi_resolution/
Várias resoluções:
- 480p, 720p, 1080p, 4K
- Testa escala

### quick_test/
Teste rápido (subset):
- `OK/` - 2 vídeos sem legendas
- `NOT_OK/` - 2 vídeos com legendas

### synthetic/
Vídeos sintéticos gerados:
- Controle total de características
- Ground truth perfeito

## ⚠️ Importante

- **Test datasets** nunca são deletados (ground truth)
- **in_progress/** é limpo após validação
- Validação usa **SubtitleDetectorV2** (força bruta)
- Acurácia esperada: **≥90%** (atual: 97.73%)

## 🎯 Objetivo

Garantir que **apenas vídeos SEM legendas** vão para `approved/`.

---

**Criado em**: 14/02/2026  
**Versão**: 2.0.0  
**Acurácia**: 97.73%
