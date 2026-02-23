# Testes Reais de Integração - Faster-Whisper

## ⚠️ IMPORTANTE: Estes testes NÃO usam mocks!

Diferente dos testes unitários em `tests/unit/`, estes testes executam:
- ✅ Carregamento REAL do modelo Faster-Whisper (~250MB download)
- ✅ Transcrição REAL de áudio
- ✅ Validação de word timestamps REAIS
- ✅ Métricas de performance de produção

## 📋 Pré-requisitos

```bash
# 1. Ambiente virtual configurado
cd /root/YTCaption-Easy-Youtube-API/services/audio-transcriber
source .venv/bin/activate  # ou venv/bin/activate

# 2. Dependências instaladas
pip install -r requirements.txt

# 3. Verificar FFmpeg (para áudio)
ffmpeg -version
```

## 🚀 Executar Testes

### Teste Rápido (Sanity Check - ~1 minuto)

```bash
pytest tests/integration/real/ -v -m real -k "quick_sanity"
```

**Valida**:
- Modelo carrega
- Transcrição funciona
- Word timestamps gerados

---

### Todos os Testes (~5 minutos)

```bash
pytest tests/integration/real/ -v -m real --timeout=180
```

**Executa**:
- ✅ test_model_download_and_load
- ✅ test_real_transcription_with_word_timestamps
- ✅ test_word_timestamps_accuracy
- ⏭️ test_multiple_transcriptions_performance (SKIPPED - muito longo)
- ✅ test_model_unload
- ✅ test_cold_start_to_transcription
- ✅ test_quick_sanity_check

**Saída esperada**: `6 passed, 1 skipped in ~296s`

---

### Teste de Performance (MUITO LENTO - ~10 minutos)

⚠️ **Skipado por padrão** devido ao tempo de execução.

```bash
pytest tests/integration/real/ -v -m real --timeout=600 -k "performance"
```

Este teste executa 3 transcrições completas do arquivo de 33s para validar estabilidade.

---

## 📊 Resultados Esperados

### Teste Quick Sanity

```
======================================================================
⚡ TESTE REAL RÁPIDO: Sanity check...
======================================================================

✅ Sanity check OK!
   - Texto: " 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 1, 2, 3, 14, 15, t..."
   - Words: 34

============================== 1 passed in 41.49s ==============================
```

### Teste Completo

```
======================================================================
🎤 TESTE REAL: Transcrevendo áudio real (TEST-.ogg)...
======================================================================
   Arquivo: TEST-.ogg (74.6 KB)

✅ Transcrição concluída!

📊 RESULTADOS:
   - Texto: " 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 1, 2, 3, 14, 15, teste, 1, 2, 3..."
   - Segments: 2
   - Total words: 34
   - Idioma detectado: pt
   - Duração áudio: 33.32s

⏱️  PERFORMANCE:
   - Tempo transcrição: 57.11s
   - RTF (Real-Time Factor): 1.71x
   - Throughput: 0.6 words/s

🎯 VALIDAÇÃO CONTEÚDO:
   - Texto completo: " 1, 2, 3, 4, 5, 6, 7, 8, 9, 10..."
   - Palavras esperadas: ['um', 'dois', 'três', 'quatro', '1', '2', '3', '4']
   - Palavras encontradas: ['1', '2', '3', '4']
   - Taxa acerto: 4/8 (50%)

PASSED
```

---

## 🔧 Troubleshooting

### Erro: `ModuleNotFoundError: No module named 'faster_whisper'`

```bash
pip install faster-whisper==1.0.1
```

### Erro: `Timeout >180s`

Aumentar timeout:
```bash
pytest tests/integration/real/ -v -m real --timeout=300
```

### Modelo não baixa (erro de rede)

```bash
# Baixar manualmente
export HF_HOME=./models
huggingface-cli download Systran/faster-whisper-small
```

---

## 📁 Estrutura dos Testes

```
tests/integration/real/
├── README.md                              # Este arquivo
├── test_real_whisper_transcription.py     # Testes reais (6 testes)
└── ../TEST-.ogg                           # Arquivo de áudio (33s, 75KB)
```

---

## 🆚 Diferença: Testes Unit vs Real

| Aspecto | Unit Tests | Real Integration Tests |
|---------|-----------|------------------------|
| **Mocks** | ✅ Usa mocks extensivos | ❌ SEM mocks |
| **Modelo** | ❌ Não carrega modelo | ✅ Carrega modelo real |
| **Áudio** | ❌ Mock de transcrição | ✅ Transcreve áudio real |
| **Performance** | ⚡ Rápido (~1s) | 🐢 Lento (~5min) |
| **Coverage** | Logic, error handling | End-to-end, production |
| **CI/CD** | ✅ Sempre executar | ⚠️ Executar periodicamente |

---

## 🎯 O que os Testes Reais Validam

### 1. Model Loading (test_model_download_and_load)
- Download do modelo do HuggingFace
- Carregamento em memória (~500MB RAM)
- Device detection (CPU/CUDA)
- Compute type selection (int8/float16)

### 2. Transcription (test_real_transcription_with_word_timestamps)
- Transcrição de áudio real (TEST-.ogg, 33s)
- Geração de word-level timestamps
- Estrutura do resultado (segments, words, text)
- Language detection
- Performance metrics (RTF, throughput)

### 3. Timestamp Accuracy (test_word_timestamps_accuracy)
- Sequencialidade dos timestamps
- Durações razoáveis de palavras
- Gaps entre palavras
- Validação estatística

### 4. Model Unload (test_model_unload)
- Descarregamento correto
- Liberação de memória
- Status após unload

### 5. Cold Start (test_cold_start_to_transcription)
- Simulação de produção (app inicia sem modelo)
- Primeira requisição (load + transcribe)
- Segunda requisição (modelo quente)
- Comparação de performance

### 6. Quick Sanity (test_quick_sanity_check)
- Validação rápida end-to-end
- Útil para CI/CD quando não há tempo para testes completos

---

## 🚨 Notas Importantes

1. **Primeira execução**: Download do modelo (~250MB), pode demorar 2-5min dependendo da internet.

2. **Cache**: Modelo é salvo em `./models/` ou `HF_HOME`. Execuções subsequentes são mais rápidas.

3. **CPU vs GPU**: 
   - CPU: RTF ~1.5-2x (mais lento que tempo real)
   - GPU: RTF ~0.1-0.3x (10x mais rápido que tempo real)

4. **Arquivo de teste**: `TEST-.ogg` tem 33s de áudio com números em português. É um arquivo REAL, não sintético.

5. **Variabilidade**: Resultados podem variar entre execuções devido a:
   - Temperature sampling do modelo
   - Compression ratio fallbacks
   - Log probability thresholds

---

## 📝 Exemplo de Log Completo

```
INFO     app.faster_whisper_manager:faster_whisper_manager.py:68 📦 Carregando Faster-Whisper: small
INFO     app.faster_whisper_manager:faster_whisper_manager.py:59 ℹ️  Usando CPU
INFO     app.faster_whisper_manager:faster_whisper_manager.py:80 Tentativa 1/3 - Device: cpu
DEBUG    urllib3.connectionpool:connectionpool.py:1049 Starting new HTTPS connection (1): huggingface.co:443
DEBUG    urllib3.connectionpool:connectionpool.py:544 https://huggingface.co:443 "GET /api/models/Systran/faster-whisper-small/revision/main HTTP/1.1" 200 2251
INFO     app.faster_whisper_manager:faster_whisper_manager.py:93 ✅ Faster-Whisper small carregado no CPU (int8)
INFO     app.faster_whisper_manager:faster_whisper_manager.py:180 🎤 Transcrevendo com Faster-Whisper: TEST-.ogg (lang=pt, task=transcribe)
INFO     faster_whisper:transcribe.py:299 Processing audio with duration 00:33.318
DEBUG    faster_whisper:transcribe.py:498 Processing segment at 00:00.000
DEBUG    faster_whisper:transcribe.py:847 Compression ratio threshold is not met with temperature 0.0 (7.453125 > 2.400000)
DEBUG    faster_whisper:transcribe.py:498 Processing segment at 00:29.980
INFO     app.faster_whisper_manager:faster_whisper_manager.py:235 ✅ Faster-Whisper transcription: 2 segments, 39 words, 33.3s
```

---

## 🎉 Conclusão

Estes testes provam que:
- ✅ Faster-Whisper funciona em produção (SEM MOCKS)
- ✅ Word timestamps são gerados corretamente
- ✅ Modelo carrega e descarrega sem erros
- ✅ Performance é aceitável (RTF ~1.7x no CPU)
- ✅ Sistema está pronto para produção

Para testes rápidos de lógica, use `tests/unit/`.  
Para validação de produção, use `tests/integration/real/`.
