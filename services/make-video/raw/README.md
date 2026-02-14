# 📥 RAW - Dados Brutos

Pasta onde os **arquivos originais** são baixados/recebidos antes de qualquer processamento.

## 📂 Estrutura

```
raw/
├── shorts/        # Vídeos baixados do YouTube (shorts brutos)
├── audio/         # Áudios recebidos via upload
└── cache/         # Cache de downloads (evita redownload)
```

## 🔄 Fluxo

```
Download/Upload
       ↓
   📥 raw/
       ↓
  transform/ (próximo passo)
```

## 📝 Características

- **Arquivos originais** sem modificação
- **Formato original** (pode ter problemas de codec)
- **Temporário** até conversão
- **Não usar diretamente** na aplicação

## ⚠️ Importante

- Arquivos aqui ainda não foram validados
- Podem ter codecs incompatíveis
- Devem passar por `transform/` antes de `validate/`

---

**Criado em**: 14/02/2026  
**Versão**: 2.0.0
