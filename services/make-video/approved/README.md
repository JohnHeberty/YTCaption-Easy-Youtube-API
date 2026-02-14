# ✅ APPROVED - Vídeos Aprovados

Pasta **FINAL** onde ficam os vídeos validados e **aprovados** para uso.

## 📂 Estrutura

```
approved/
├── videos/        # Vídeos aprovados (SEM legendas)
├── output/        # Vídeos finais processados (com áudio/edições)
└── (futuro)       # Outras categorias de aprovados
```

## 🔄 Fluxo

```
validate/ (detecção de legendas)
       ↓
  has_text = false? (SEM legendas)
       ↓
✅ approved/ (vídeos prontos para uso)
       ↓
  Aplicação usa esses vídeos
```

## 📝 Características

### videos/
- **Vídeos aprovados** sem legendas
- Formato: H264 (convertido)
- Validados pelo SubtitleDetectorV2 (97.73% acurácia)
- **Apenas vídeos SEM legendas**

### output/
- **Vídeos finais processados**
- Com áudio adicionado
- Com edições/efeitos
- Prontos para entrega ao usuário
- Tempo de vida: 24h (depois são limpos)

## ✅ Critérios de Aprovação

Para um vídeo chegar aqui:
1. ✅ Baixado com sucesso (`raw/`)
2. ✅ Convertido para H264 (`transform/`)
3. ✅ Validado sem legendas (`validate/`)
4. ✅ `has_text = false` (SubtitleDetectorV2)

## 🎯 Garantias

Vídeos em `approved/videos/`:
- ✅ **SEM legendas** detectadas
- ✅ Codec H264 compatível
- ✅ Metadados corretos
- ✅ Processáveis por OpenCV/FFmpeg
- ✅ Prontos para uso imediato

## 🔄 Uso na Aplicação

A aplicação **APENAS** usa vídeos de `approved/videos/`:

```python
# Sistema pega vídeos aprovados
video_path = approved/videos/{video_id}.mp4

# Adiciona áudio/edições
process_video(video_path)

# Salva resultado final
output_path = approved/output/{final_video_id}.mp4
```

## 🗑️ Limpeza Automática

- **videos/**: Mantidos (cache de 30 dias)
- **output/**: Limpos após 24h (vídeos processados)

## ⚠️ Importante

- Esta é a **pasta de produção**
- Vídeos aqui passaram por **todas as validações**
- **Não manipular** manualmente
- Gerenciado automaticamente pelo sistema

## 📊 Estatísticas Esperadas

Com SubtitleDetectorV2 (97.73% acurácia):
- **True Negatives**: ~97% dos vídeos SEM legendas aprovados corretamente
- **False Positives**: ~3% (vídeos sem legendas rejeitados incorretamente)
- **False Negatives**: ~0% (vídeos com legendas aprovados - MUITO RARO)

---

**Criado em**: 14/02/2026  
**Versão**: 2.0.0  
**Pipeline**: raw → transform → validate → approved
