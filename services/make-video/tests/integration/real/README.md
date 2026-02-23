# Tests - Integration - Real

**Testes de integração com serviços REAIS (não mocks)**

## ⚠️ Conceito

Estes testes chamam APIs e serviços em produção:
- audio-transcriber API (https://yttranscriber.loadstask.com)
- FFmpeg real
- SubtitleGenerator real
- VideoBuilder real

**Se serviço está DOWN, teste FALHA** (comportamento correto).

## 📁 Testes

- `test_real_audio_transcription.py` - Transcrição com API real
- `test_real_pipeline_complete.py` - Pipeline completo end-to-end

## 🎯 Diferença vs Mocks

```python
# ❌ Mock (outros testes):
segments = [{"start": 0, "end": 5, "text": "mock"}]  # FAKE

# ✅ Real (estes testes):
segments = await api.transcribe_audio(audio_path)  # API REAL
```

## 🚀 Como executar

```bash
# Teste individual
pytest tests/integration/real/test_real_audio_transcription.py -v
pytest tests/integration/real/test_real_pipeline_complete.py -v

# Todos os testes reais
pytest tests/integration/real/ -v

# Com coverage
pytest tests/integration/real/ --cov=app --cov-report=html
```

## 📋 Pré-requisitos

1. **API online**: https://yttranscriber.loadstask.com
2. **FFmpeg instalado**: `ffmpeg -version`
3. **Áudio de teste**: `tests/assets/TEST-.ogg`

## ⚠️ Troubleshooting

### Erro: "Connection timeout"
- API está DOWN ou rede sem conectividade
- Verificar: `curl https://yttranscriber.loadstask.com/health`

### Erro: "FFmpeg not found"
- FFmpeg não instalado
- Instalar: `sudo apt-get install ffmpeg`

### Teste demora muito
- Normal: transcrição real leva ~30-60s
- Pipeline completo: ~60-90s

## 💡 Por que não usar mocks?

- Mocks podem mentir
- Se API muda formato, mock passa mas produção falha
- Testes reais detectam problemas ANTES do deploy
- Reflete exatamente o que vai acontecer em produção
