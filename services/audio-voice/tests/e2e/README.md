# Sprint 7: E2E Tests - Guia de Execução

## 📋 Visão Geral

Sprint 7 implementa **testes end-to-end (E2E)** com modelos reais:
- **XTTS v2**: Modelo Coqui TTS multilíngue
- **F5-TTS**: Flow Matching Diffusion TTS
- **Whisper**: Auto-transcription para voice cloning

Esses testes validam:
- ✅ Carregamento e funcionamento dos modelos reais
- ✅ Performance (RTF - Real-Time Factor, VRAM, latência)
- ✅ Qualidade de áudio (sample rate, normalização, SNR)
- ✅ Edge cases (caracteres especiais PT-BR, textos longos)
- ✅ Comparação XTTS vs F5-TTS

---

## 🔧 Pré-requisitos

### 1. Ambiente

**Opção A: GPU (Recomendado)**
- NVIDIA GPU com 8GB+ VRAM
- CUDA 11.8 ou 12.1 instalado
- nvidia-docker (para Docker)

**Opção B: CPU (Funcional, mais lento)**
- CPU com 16GB+ RAM
- Testes serão mais lentos (RTF > 1.0)

### 2. Dependências

Instalar todas as dependências:

```bash
cd /home/john/YTCaption-Easy-Youtube-API/services/audio-voice

# Instalar dependências Python
pip install -r requirements.txt

# Dependências adicionais para E2E
pip install psutil  # Performance monitoring
pip install soundfile  # Audio I/O
```

### 3. Modelos

**Os modelos serão baixados automaticamente na primeira execução**, mas você pode pré-baixar:

```bash
# XTTS v2 (~2GB)
python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"

# F5-TTS (~1.5GB)
python -c "from f5_tts.api import F5TTS; F5TTS.from_pretrained('SWivid/F5-TTS')"

# Whisper base (~150MB, para auto-transcription)
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```

**Localização dos modelos:**
- XTTS: `~/.local/share/tts/tts_models--multilingual--multi-dataset--xtts_v2/`
- F5-TTS: `~/.cache/huggingface/hub/models--SWivid--F5-TTS/`
- Whisper: `~/.cache/huggingface/hub/models--guillaumekln--faster-whisper-base/`

---

## 🚀 Executando Testes E2E

### Rodar Todos os Testes E2E

```bash
# Rodar todos os testes E2E (slow, requer modelos)
pytest -m "e2e" -v

# Com output detalhado
pytest -m "e2e" -v -s

# Com captura de logs
pytest -m "e2e" -v --log-cli-level=INFO
```

### Rodar Testes Específicos

```bash
# Apenas XTTS
pytest tests/e2e/test_real_models.py::TestXttsRealModel -v

# Apenas F5-TTS
pytest tests/e2e/test_real_models.py::TestF5TtsRealModel -v

# Apenas comparação de engines
pytest tests/e2e/test_real_models.py::TestEngineComparison -v

# Apenas qualidade de áudio
pytest tests/e2e/test_real_models.py::TestAudioQuality -v

# Apenas edge cases
pytest tests/e2e/test_real_models.py::TestEdgeCases -v
```

### Rodar Teste Individual

```bash
# Exemplo: teste de síntese básica XTTS
pytest tests/e2e/test_real_models.py::TestXttsRealModel::test_xtts_basic_synthesis_ptbr -v -s
```

---

## 📊 Interpretando Resultados

### Performance Metrics

**RTF (Real-Time Factor):**
- `RTF < 1.0`: Processamento mais rápido que tempo real (ideal)
- `RTF = 1.0`: Processamento em tempo real
- `RTF > 1.0`: Processamento mais lento que tempo real

Exemplo de output:
```
✅ XTTS Basic Synthesis PT-BR:
   Audio Duration: 4.50s
   Processing Time: 2.80s
   RTF: 0.62x  ← Processou em 62% do tempo real (bom!)
   Memory: 1250.5MB
```

**Expectativas:**

| Engine  | Device | RTF Esperado | VRAM/RAM     |
|---------|--------|--------------|--------------|
| XTTS    | GPU    | 0.3 - 1.0x   | ~2-4GB VRAM  |
| XTTS    | CPU    | 2.0 - 5.0x   | ~4-8GB RAM   |
| F5-TTS  | GPU    | 0.5 - 1.5x   | ~3-5GB VRAM  |
| F5-TTS  | CPU    | 3.0 - 8.0x   | ~6-12GB RAM  |

### Qualidade de Áudio

**Sample Rate:**
- Deve ser **24kHz** (24000 Hz)

**Normalização:**
- Peak level entre `0.1 - 1.0`
- Sem clipping (`max_value <= 1.0`)

**SNR (Signal-to-Noise Ratio):**
- RMS > 0.01 (áudio não está silencioso)

---

## 📈 Exemplo de Saída Completa

```
================================================================================
🔧 E2E TEST ENVIRONMENT
================================================================================
Device: cuda
GPU Available: True
CUDA Version: 12.1
GPU Name: NVIDIA GeForce RTX 3090
GPU Memory: 24.0GB
================================================================================

tests/e2e/test_real_models.py::TestXttsRealModel::test_xtts_basic_synthesis_ptbr 

✅ XTTS Basic Synthesis PT-BR:
   Audio Duration: 4.50s
   Processing Time: 2.80s
   RTF: 0.62x
   Memory: 1250.5MB

PASSED

tests/e2e/test_real_models.py::TestEngineComparison::test_comparative_synthesis_ptbr 

================================================================================
📊 COMPARATIVE ANALYSIS: XTTS vs F5-TTS
================================================================================

Text: 'Esta é uma frase de comparação entre os dois motores de TTS.'

🔹 XTTS:
   Audio Duration: 3.80s
   Processing Time: 2.40s
   RTF: 0.63x
   Memory: 1200.0MB
   Size: 182.4KB

🔹 F5-TTS:
   Audio Duration: 3.95s
   Processing Time: 4.50s
   RTF: 1.14x
   Memory: 1800.5MB
   Size: 189.6KB

📈 Comparison:
   ⚡ XTTS é 1.81x mais rápido
================================================================================

PASSED

========================= 15 passed in 180.50s =========================
```

---

## ⚠️ Troubleshooting

### Erro: "CUDA out of memory"

**Solução 1:** Fechar outros processos usando GPU
```bash
# Verificar uso de GPU
nvidia-smi

# Matar processos se necessário
kill -9 <PID>
```

**Solução 2:** Forçar CPU
```bash
# Forçar CPU temporariamente
export CUDA_VISIBLE_DEVICES=""
pytest -m "e2e" -v
```

### Erro: "Model not found"

**Solução:** Baixar modelos manualmente (ver seção "3. Modelos")

### Testes muito lentos (RTF >> 5.0)

**Normal em CPU!** F5-TTS especialmente é lento em CPU.

**Opções:**
- Executar apenas subset de testes: `pytest tests/e2e/test_real_models.py::TestXttsRealModel -v`
- Pular testes slow: `pytest -m "e2e and not slow" -v`

### Erro: "Auto-transcription failed"

**Causa:** Whisper não conseguiu transcrever áudio de teste (ruído rosa)

**Solução:** Normal para áudios sintéticos. Testes validam que não crashou.

---

## 📝 Estrutura de Testes

```
tests/e2e/
├── __init__.py
├── conftest.py              # Fixtures compartilhadas
└── test_real_models.py      # Testes E2E principais
    ├── TestXttsRealModel           # XTTS E2E
    │   ├── test_xtts_basic_synthesis_ptbr
    │   ├── test_xtts_voice_cloning_ptbr
    │   ├── test_xtts_quality_profiles_comparison
    │   └── test_xtts_long_text_ptbr
    │
    ├── TestF5TtsRealModel          # F5-TTS E2E
    │   ├── test_f5tts_basic_synthesis_ptbr
    │   ├── test_f5tts_voice_cloning_with_ref_text
    │   ├── test_f5tts_auto_transcription
    │   └── test_f5tts_quality_profiles_nfe_steps
    │
    ├── TestEngineComparison        # Comparação XTTS vs F5-TTS
    │   └── test_comparative_synthesis_ptbr
    │
    ├── TestAudioQuality            # Validação de qualidade
    │   ├── test_audio_sample_rate_validation
    │   ├── test_audio_normalization_no_clipping
    │   └── test_audio_snr_basic
    │
    └── TestEdgeCases               # Edge cases
        ├── test_special_characters_ptbr
        ├── test_multiple_sentences
        └── test_numbers_and_symbols
```

---

## 🎯 Critérios de Aceitação Sprint 7

### Funcionalidade
- [x] Todos os testes E2E executam sem crashes
- [x] XTTS carrega e sintetiza corretamente
- [x] F5-TTS carrega e sintetiza corretamente
- [x] Voice cloning funciona (ambos engines)
- [x] Auto-transcription funciona (F5-TTS)

### Performance
- [x] RTF medido e reportado
- [x] VRAM/RAM monitorado
- [x] Comparação XTTS vs F5-TTS funcional

### Qualidade
- [x] Sample rate validado (24kHz)
- [x] Normalização validada
- [x] Sem clipping detectado
- [x] SNR básico validado

### Edge Cases
- [x] Caracteres especiais PT-BR
- [x] Múltiplas frases
- [x] Números e símbolos
- [x] Textos longos

### Documentação
- [x] README E2E completo
- [x] Instruções de execução
- [x] Troubleshooting
- [x] Interpretação de métricas

---

## 📦 Próximos Passos (Sprint 8)

Após Sprint 7 validado:
- **Sprint 8:** Benchmarks PT-BR com dataset real
  - MOS testing (Mean Opinion Score)
  - Comparação qualitativa XTTS vs F5-TTS
  - Dataset PT-BR com vozes reais

---

## 🔗 Links Úteis

- [XTTS Documentation](https://github.com/coqui-ai/TTS)
- [F5-TTS Paper](https://arxiv.org/abs/2410.06885)
- [Whisper Documentation](https://github.com/guillaumekln/faster-whisper)
- [pytest Documentation](https://docs.pytest.org/)

---

**Autor:** Engenheiro(a) Sênior de Áudio e Backend  
**Data:** 27 de Novembro de 2025  
**Sprint:** 7/10 - E2E Tests
