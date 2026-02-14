# 🔄 TRANSFORM - Transformação e Conversão

Pasta onde os arquivos de `raw/` são **convertidos e transformados** para formatos compatíveis.

## 📂 Estrutura

```
transform/
├── videos/        # Vídeos sendo convertidos para H264
├── temp/          # Arquivos temporários durante transformação
└── (em breve)     # Outras transformações futuras
```

## 🔄 Fluxo

```
raw/ (arquivos originais)
       ↓
🔄 transform/ (conversão H264, resize, etc)
       ↓
validate/ (próximo passo)
```

## 📝 Processamentos Realizados

1. **Conversão de codec**: VP9 → H264, HEVC → H264, etc
2. **Padronização**: Garantir formato compatível com OpenCV
3. **Correção de metadados**: Fixing timecode, rotation, etc
4. **Normalização**: Bitrate, resolução, FPS

## ⚠️ Importante

- Arquivos aqui estão **em processamento**
- Após transformação, movem para `validate/`
- Pasta `temp/` é limpa periodicamente (1h)
- Conversões pesadas (GPU se disponível)

## 🎯 Objetivo

Garantir que **todos os vídeos** que saem daqui:
- ✅ Funcionam com OpenCV
- ✅ Codec H264 compatível
- ✅ Metadados corretos
- ✅ Prontos para validação

---

**Criado em**: 14/02/2026  
**Versão**: 2.0.0
