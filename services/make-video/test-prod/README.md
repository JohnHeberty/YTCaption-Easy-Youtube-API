# 🧪 Test-Prod - Testes de Produção

Pasta temporária para testes de validação em produção. **Arquivos aqui serão movidos para `.trash/` após validação.**

## Estrutura

```
test-prod/
├── README.md                          # Este arquivo
├── test_empty_srt.py                  # Testa SRT vazio (deve FALHAR)
├── test_low_quality_audio.py          # Testa áudio com baixa qualidade
├── test_high_noise_audio.py           # Testa áudio com ruído alto (VAD filtra tudo)
├── test_normal_audio.py               # Testa áudio normal (deve PASSAR)
├── test_vad_fallback.py               # Testa fallback VAD (Melhoria M1)
├── test_whisper_quality_score.py     # Testa quality score Whisper (M2)
├── monitor_logs.py                    # Script de monitoramento de logs
├── samples/                           # Amostras de áudio para teste
│   ├── empty_audio.mp3               # Áudio sem fala (silêncio)
│   ├── noisy_audio.mp3               # Áudio com ruído alto
│   └── normal_audio.mp3              # Áudio com fala clara
└── results/                          # Resultados dos testes
    └── .gitkeep
```

## Testes Implementados

### ✅ Validação de Bug Fix (SRT Vazio)

**Teste**: `test_empty_srt.py`
- **Objetivo**: Validar que job FALHA quando SRT está vazio
- **Entrada**: Áudio sem fala (silêncio total)
- **Expectativa**: `SubtitleGenerationException` lançada
- **Status**: ❌ DEVE FALHAR (fail-safe correto)

### 🎯 Teste de Áudio com Ruído

**Teste**: `test_high_noise_audio.py`
- **Objetivo**: Validar que VAD filtra ruídos corretamente
- **Entrada**: Áudio com ruído alto mas sem fala
- **Expectativa**: `final_cues == []` → Exception
- **Status**: ❌ DEVE FALHAR (VAD correto)

### ✅ Teste de Áudio Normal

**Teste**: `test_normal_audio.py`
- **Objetivo**: Validar pipeline completo com áudio válido
- **Entrada**: Áudio com fala clara
- **Expectativa**: Vídeo gerado COM legendas
- **Status**: ✅ DEVE PASSAR

## Melhorias Implementadas (M1-M5)

### M1: Fallback VAD com Threshold Dinâmico
**Arquivo**: `improvements/m1_vad_fallback.py`
- Se `len(final_cues) == 0` após VAD, tenta threshold mais baixo (0.3 → 0.1)
- Previne falsos negativos em áudios com baixo volume

### M2: Validação de Quality Score (Whisper)
**Arquivo**: `improvements/m2_whisper_quality.py`
- Adiciona check de `no_speech_prob` (rejeita se > 0.6)
- Previne transcrições de baixa confiança

### M3: Retry com Modelo Diferente
**Arquivo**: `improvements/m3_whisper_retry.py`
- Em caso de falha com `whisper-1`, tenta `whisper-large-v3`
- Melhoria para áudios com sotaque forte

### M4: Pre-processing de Áudio
**Arquivo**: `improvements/m4_audio_preprocessing.py`
- Adiciona noise reduction com FFmpeg (`afftdn` filter)
- Normalização de volume antes de transcrever

### M5: Validação de Sync A/V Aprimorada
**Arquivo**: `improvements/m5_sync_validator.py`
- Usa `SyncValidator` existente com tolerância ajustável
- Detecta drift e aplica correção automática

## Como Executar

### Teste Individual
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video
python test-prod/test_empty_srt.py
```

### Todos os Testes
```bash
python test-prod/run_all_tests.py
```

### Monitoramento de Logs
```bash
python test-prod/monitor_logs.py --job-id <job_id> --follow
```

## Critérios de Aprovação

**Para mover teste para pasta oficial** (`tests/`):
1. ✅ Teste passa consistentemente (100% success rate em 10 execuções)
2. ✅ Teste cobre cenário real de produção
3. ✅ Teste é determinístico (não depende de condições externas)
4. ✅ Teste tem assertions claras e documentadas
5. ✅ Teste não tem dependências de arquivos temporários

**Para mover para lixeira** (`.trash/`):
1. ❌ Teste falha consistentemente (bug no teste)
2. ❌ Teste não adiciona valor (duplicado de teste existente)
3. ❌ Teste dependente de condições externas (não reproduzível)

## Status dos Testes

| Teste | Status | Validação | Destino |
|-------|--------|-----------|---------|
| `test_empty_srt.py` | 🟡 Em execução | Pendente | TBD |
| `test_low_quality_audio.py` | 🟡 Em execução | Pendente | TBD |
| `test_high_noise_audio.py` | 🟡 Em execução | Pendente | TBD |
| `test_normal_audio.py` | 🟡 Em execução | Pendente | TBD |
| M1: VAD Fallback | 📝 Implementando | N/A | TBD |
| M2: Whisper Quality | 📝 Implementando | N/A | TBD |
| M3: Whisper Retry | 📝 Implementando | N/A | TBD |
| M4: Audio Preprocessing | 📝 Implementando | N/A | TBD |
| M5: Sync Validator | 📝 Implementando | N/A | TBD |

---

**Nota**: Esta pasta é **TEMPORÁRIA**. Após validação, arquivos serão movidos para:
- `tests/` (se aprovado)
- `.trash/test-prod-YYYY-MM-DD/` (se descartado)
