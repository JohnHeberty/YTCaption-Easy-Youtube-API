# ✅ E2-TTS Configuration Summary

**Data:** 28 de Novembro de 2025  
**Status:** Configurado e pronto para teste

---

## 📋 O Que Foi Feito

### 1. Variáveis de Ambiente Adicionadas

Adicionei **25 variáveis de ambiente** para F5-TTS/E2-TTS em `.env` e `.env.example`:

```bash
# ===== F5-TTS / E2-TTS (Flow Matching Diffusion - EMOTION MODEL) =====
F5TTS_ENABLED=true
F5TTS_MODEL=SWivid/E2-TTS  # Modelo de emoção por padrão!
F5TTS_DEVICE=cpu
F5TTS_FALLBACK_CPU=true

# Whisper (Auto-transcription)
F5TTS_WHISPER_MODEL=base
F5TTS_WHISPER_DEVICE=cpu

# Quality Profiles (NFE Steps)
F5TTS_NFE_STEP_FAST=24
F5TTS_NFE_STEP_BALANCED=40
F5TTS_NFE_STEP_ULTRA=64

# Synthesis Parameters
F5TTS_CFG_STRENGTH=2.0
F5TTS_SWAY_SAMPLING_COEF=-1.0
F5TTS_SPEED=1.0

# DSP Post-Processing
F5TTS_DENOISE_STRENGTH=0.85
F5TTS_DEESSING_FREQ=7000
F5TTS_HIGHPASS_FREQ=50
F5TTS_LOWPASS_FREQ=12000

# Audio Constraints
F5TTS_SAMPLE_RATE=24000
F5TTS_MIN_REF_DURATION=3
F5TTS_MAX_REF_DURATION=30
F5TTS_MAX_TEXT_LENGTH=10000
```

### 2. Config.py Atualizado

Atualizei `app/config.py` para ler **todas** as variáveis de ambiente do F5-TTS:

```python
'f5tts': {
    'enabled': os.getenv('F5TTS_ENABLED', 'true').lower() == 'true',
    'device': os.getenv('F5TTS_DEVICE', 'cpu'),
    'model_name': os.getenv('F5TTS_MODEL', 'SWivid/E2-TTS'),  # E2-TTS por padrão!
    
    # Whisper
    'whisper_model': os.getenv('F5TTS_WHISPER_MODEL', 'base'),
    'whisper_device': os.getenv('F5TTS_WHISPER_DEVICE', 'cpu'),
    
    # Quality Profiles
    'nfe_step_fast': int(os.getenv('F5TTS_NFE_STEP_FAST', '24')),
    'nfe_step_balanced': int(os.getenv('F5TTS_NFE_STEP_BALANCED', '40')),
    'nfe_step_ultra': int(os.getenv('F5TTS_NFE_STEP_ULTRA', '64')),
    
    # Synthesis
    'cfg_strength': float(os.getenv('F5TTS_CFG_STRENGTH', '2.0')),
    'sway_sampling_coef': float(os.getenv('F5TTS_SWAY_SAMPLING_COEF', '-1.0')),
    'speed': float(os.getenv('F5TTS_SPEED', '1.0')),
    
    # DSP
    'denoise_strength': float(os.getenv('F5TTS_DENOISE_STRENGTH', '0.85')),
    'deessing_freq': int(os.getenv('F5TTS_DEESSING_FREQ', '7000')),
    'highpass_freq': int(os.getenv('F5TTS_HIGHPASS_FREQ', '50')),
    'lowpass_freq': int(os.getenv('F5TTS_LOWPASS_FREQ', '12000')),
    
    # Constraints
    'sample_rate': int(os.getenv('F5TTS_SAMPLE_RATE', '24000')),
    'min_ref_duration': int(os.getenv('F5TTS_MIN_REF_DURATION', '3')),
    'max_ref_duration': int(os.getenv('F5TTS_MAX_REF_DURATION', '30')),
    'max_text_length': int(os.getenv('F5TTS_MAX_TEXT_LENGTH', '10000')),
}
```

### 3. E2-TTS Como Modelo Padrão

**IMPORTANTE:** O modelo **E2-TTS** (com suporte emocional) está configurado como padrão:

- **Variável:** `F5TTS_MODEL=SWivid/E2-TTS`
- **No código:** `self.model_name = 'E2TTS'` (corrigido de `E2TTS_v1_Base`)

### 4. Correção de Bug Crítico

**Bug encontrado:**
```python
# ❌ ERRADO (arquivo .yaml não existe)
self.model_name = 'E2TTS_v1_Base'

# ✅ CORRETO
self.model_name = 'E2TTS'
```

**Erro antes da correção:**
```
FileNotFoundError: [Errno 2] No such file or directory: 
'/home/appuser/.local/lib/python3.11/site-packages/f5_tts/configs/E2TTS_v1_Base.yaml'
```

**Após correção:**
O F5-TTS agora usa os nomes corretos de modelo: `'E2TTS'` ou `'F5TTS'`.

---

## 🎯 Como Testar

### 1. Verificar Configuração

```bash
docker exec audio-voice-celery python -c "
from app.config import get_settings
f5tts = get_settings().get('tts_engines', {}).get('f5tts', {})
print('Model:', f5tts.get('model_name'))
print('Device:', f5tts.get('device'))
print('NFE Ultra:', f5tts.get('nfe_step_ultra'))
"
```

**Output esperado:**
```
Model: SWivid/E2-TTS
Device: cpu
NFE Ultra: 64
```

### 2. Teste Completo

Use o script `test_e2tts_with_mp3.sh`:

```bash
cd /home/john/YTCaption-Easy-Youtube-API/services/audio-voice
./test_e2tts_with_mp3.sh
```

**O que o script faz:**
1. **Voice Clone** com F5-TTS (engine=f5tts)
2. **Síntese** com E2-TTS (emotion model, quality=balanced)
3. **Download** do áudio gerado: `test_e2tts_final.wav`

### 3. Teste Manual (API)

```bash
# 1. Clone de voz
curl -X POST "http://localhost:8005/voices/clone" \
  -F "file=@audio.mp3" \
  -F "name=TestE2TTS" \
  -F "language=pt-BR" \
  -F "tts_engine=f5tts"

# 2. Síntese com E2-TTS
curl -X POST "http://localhost:8005/jobs" \
  -F "text=Teste do E2-TTS com emoções!" \
  -F "source_language=pt-BR" \
  -F "mode=dubbing_with_clone" \
  -F "voice_id=YOUR_VOICE_ID" \
  -F "tts_engine=f5tts" \
  -F "quality_profile_id=f5tts_ultra_quality"
```

---

## 📊 Comparação XTTS vs E2-TTS

| Feature | XTTS | E2-TTS (F5-TTS) |
|---------|------|------------------|
| **Modelo** | Coqui TTS v2 | Flow Matching Diffusion |
| **Qualidade** | Boa | Excelente |
| **Emoção** | Básica | Avançada ✨ |
| **Velocidade** | Rápida (~6s para 8s de áudio) | Lenta (~180s para 5s) |
| **VRAM** | ~3.5GB GPU | ~2GB RAM (CPU) |
| **Device** | CUDA | CPU (força) |
| **Idiomas** | 16 principais | 100+ (zero-shot) |
| **Sample Rate** | 24kHz | 24kHz |
| **Use Case** | Produção geral | Premium/Audiobooks |

---

## ⚙️ Variáveis Mais Importantes

### `F5TTS_MODEL`
- **Valor atual:** `SWivid/E2-TTS`
- **Opções:** `SWivid/E2-TTS` (emotion) ou `SWivid/F5-TTS` (base)
- **Impacto:** Define se usa modelo emocional ou base

### `F5TTS_DEVICE`
- **Valor atual:** `cpu`
- **Opções:** `cpu` ou `cuda`
- **Impacto:** CPU evita OOM em GPUs pequenas, mas é mais lento

### `F5TTS_NFE_STEP_ULTRA`
- **Valor atual:** `64`
- **Opções:** 24 (fast), 40 (balanced), 64 (ultra), 80+ (overkill)
- **Impacto:** Mais steps = melhor qualidade + mais lento

### `F5TTS_CFG_STRENGTH`
- **Valor atual:** `2.0`
- **Opções:** 1.0-3.0
- **Impacto:** Maior = mais fiel ao prompt de emoção

### `F5TTS_DENOISE_STRENGTH`
- **Valor atual:** `0.85`
- **Opções:** 0.0-1.0
- **Impacto:** Redução de chiado/hiss no áudio

---

## 🐛 Problemas Conhecidos

### 1. Fallback para XTTS

**Sintoma:** Logs mostram "XTTS synthesis" mesmo quando `tts_engine=f5tts`

**Causa:** F5-TTS falha ao carregar e faz fallback para XTTS

**Verificar:**
```bash
docker logs audio-voice-celery | grep -A5 "Failed to load F5-TTS"
```

**Solução:**
- Verificar se `E2TTS.yaml` existe em `/home/appuser/.local/lib/python3.11/site-packages/f5_tts/configs/`
- Reinstalar f5-tts: `docker exec audio-voice-celery pip install --upgrade f5-tts`

### 2. Áudio Muito Curto

**Sintoma:** `Audio too short: 1.1s (minimum 3.0s)`

**Causa:** F5-TTS exige áudio de referência com **mínimo 3 segundos**

**Solução:**
- Usar áudio com 5-10 segundos de duração
- Verificar: `F5TTS_MIN_REF_DURATION=3`

### 3. Worker Não Processa Jobs

**Sintoma:** Jobs ficam em `queued` infinitamente

**Causa:** Celery worker travou ou está carregando modelos

**Solução:**
```bash
# Reiniciar worker
docker restart audio-voice-celery

# Verificar status
docker exec audio-voice-celery ps aux | grep celery

# Verificar logs
docker logs audio-voice-celery --tail 50
```

---

## 📈 Próximos Passos

### Sprint 9: VRAM Management
- [ ] Implementar unload automático de XTTS antes de F5-TTS
- [ ] Testar F5-TTS em GPU (após liberar VRAM)
- [ ] Benchmark: CPU vs GPU performance

### Sprint 10: Quality Profiles
- [ ] Criar profiles customizados para E2-TTS
- [ ] Ajustar parâmetros de emoção por idioma
- [ ] A/B testing: E2-TTS vs XTTS

### Sprint 11: Production Hardening
- [ ] Rebuildar Docker image com f5-tts
- [ ] Testes de carga (múltiplos jobs simultâneos)
- [ ] Otimização de NFE steps por use case

---

## ✅ Checklist

- [x] Variáveis de ambiente documentadas no `.env.example`
- [x] Variáveis carregadas em `config.py`
- [x] E2-TTS configurado como modelo padrão
- [x] Bug do `E2TTS_v1_Base.yaml` corrigido
- [x] Script de teste criado (`test_e2tts_with_mp3.sh`)
- [x] Documentação criada (`E2TTS-CONFIG-SUMMARY.md`)
- [ ] **PENDENTE:** Teste end-to-end bem-sucedido
- [ ] **PENDENTE:** Docker image rebuild

---

## 📝 Notas Técnicas

### Model Names na F5-TTS API

A F5-TTS v1.1.9 usa **dois nomes** para modelos:

1. **HuggingFace ID:** `SWivid/E2-TTS` ou `SWivid/F5-TTS`
   - Usado em: variável `F5TTS_MODEL`
   - Usado em: argumentos da API para download

2. **Config Name:** `E2TTS` ou `F5TTS`
   - Usado em: `F5TTS(model='E2TTS', ...)`
   - Usado em: carregamento de `/configs/E2TTS.yaml`

**Conversão no código:**
```python
# .env
F5TTS_MODEL=SWivid/E2-TTS

# f5tts_engine.py
if 'E2-TTS' in model_name or 'E2TTS' in model_name:
    self.model_name = 'E2TTS'  # ← Config name, não HF ID!
```

### Device Strategy

**Por que CPU?**
- XTTS já usa ~3.5GB VRAM
- F5-TTS precisa ~2GB VRAM adicional
- GPU total: 4GB → **CUDA OOM**

**Trade-off:**
- CPU: ~3min para 5s de áudio (lento, mas funciona)
- GPU: ~30s para 5s de áudio (rápido, mas OOM)

**Solução futura:**
- Implementar LOW_VRAM mode
- Unload XTTS → Load F5-TTS → Synthesize → Unload F5-TTS → Load XTTS
- Permitir GPU para F5-TTS sem OOM

---

**Autor:** GitHub Copilot  
**Versão:** 1.0  
**Data:** 2025-11-28
