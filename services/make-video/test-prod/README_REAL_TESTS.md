# 🧪 Test-Prod - Testes de Produção REAIS

**Pasta para testes que CHAMAM SERVIÇOS REAIS - NÃO USA MOCKS!**

## ⚠️ CONCEITO CRÍTICO

### test-prod/ = Ambiente de Produção REAL

- ✅ Chama APIs reais (audio-transcriber em produção)
- ✅ Usa áudio real (TEST-.ogg, 75KB)
- ✅ Executa VAD real (SubtitleGenerator)
- ✅ Executa FFmpeg real (burn-in de legendas)
- ✅ **Se serviço está DOWN, teste FALHA** (comportamento correto!)
- ❌ **NÃO MOCKA NADA** - reflete EXATAMENTE o que vai acontecer em produção

### Por que NÃO usar mocks?

```python
# ❌ ERRADO (test/ com mocks):
segments = [{"start": 0, "end": 5, "text": "mock"}]  # FAKE!

# ✅ CORRETO (test-prod/ sem mocks):
segments = await api_client.transcribe_audio(audio_path)  # API REAL!
```

**Vantagens**:
- Se falha aqui, vai falhar em produção
- Detecta problemas de integração ANTES do deploy
- Valida que serviços externos estão funcionando
- Testes refletem realidade (não ilusão de mocks)

## 🎯 Objetivo

1. **Validar sistema em produção REAL** (não simulado)
2. **Detectar problemas de integração** com serviços externos
3. **Validar correções ANTES de deploy** (fail-fast)
4. **Garantir que melhorias funcionam** com serviços reais

## 📁 Estrutura

```
test-prod/
│
├── 📖 DOCUMENTAÇÃO:
│   ├── README.md                                # Este arquivo
│   └── RESUMO_COMPLETO.md                       # Correções + melhorias implementadas
│
├── 🎤 TESTES REAIS (usam serviços de produção):
│   ├── test_real_audio_transcription.py         # ✅ Transcrição com áudio real
│   ├── test_real_pipeline_complete.py           # ✅ Pipeline completo end-to-end
│   └── run_all_real_tests.py                    # Executor de todos os testes reais
│
├── 📦 TESTES ANTIGOS (deprecated - usam mocks):
│   ├── test_empty_srt.py                        # ⚠️ USA MOCKS (deprecated)
│   ├── test_normal_audio.py                     # ⚠️ USA MOCKS (deprecated)
│   └── run_all_tests.py                         # ⚠️ USA MOCKS (deprecated)
│
├── 🛠️ FERRAMENTAS:
│   └── monitor_logs.py                          # Monitoramento de logs em produção
│
├── ✨ MELHORIAS PROPOSTAS (aguardando integração):
│   └── improvements/
│       ├── m1_vad_fallback.py                   # VAD com 3 níveis de threshold
│       ├── m2_whisper_quality.py                # Quality score validator
│       ├── m3_whisper_retry.py                  # Retry com modelos diferentes
│       ├── m4_audio_preprocessing.py            # Noise reduction + normalization
│       └── m5_sync_validator.py                 # Sync A/V corrector
│
└── 📁 DADOS DE TESTE:
    ├── samples/                                 # Áudios e vídeos de entrada
    │   └── TEST-.ogg                            # Áudio real (75KB) - fala em português
    └── results/                                 # Outputs dos testes
        ├── transcription_*.json                 # Resultados de transcrição API
        ├── test_subtitles_real.srt              # SRT gerado com VAD real
        └── test_video_with_real_subtitles.mp4   # Vídeo final com legendas
```

## 🧪 Testes Implementados

### ✅ Teste 1: Transcrição com Áudio Real

**Arquivo**: `test_real_audio_transcription.py`

**O que faz**:
1. Envia `TEST-.ogg` para audio-transcriber API (https://yttranscriber.loadstask.com)
2. Polling de status até job completar
3. Baixa transcrição (segments com start, end, text)
4. Valida formato de resposta

**API chamada**:
```bash
POST https://yttranscriber.loadstask.com/jobs
  - file: TEST-.ogg
  - language_in: "pt"

GET https://yttranscriber.loadstask.com/jobs/{job_id}
  - Polling até status="completed"

GET https://yttranscriber.loadstask.com/jobs/{job_id}/transcription
  - Retorna segments[]
```

**Validações**:
- ✅ segments[] não está vazio
- ✅ Cada segment tem: start, end, text
- ✅ duration > 0
- ✅ language_detected válido (pt, en, etc)
- ✅ processing_time < 5min

**Expectativa**: ✅ **DEVE PASSAR** (se API está online)

**Execução**:
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video/test-prod
python test_real_audio_transcription.py
```

---

### ✅ Teste 2: Pipeline Completo End-to-End

**Arquivo**: `test_real_pipeline_complete.py`

**O que faz** (simula exatamente `celery_tasks.py`):

1. **Transcrição REAL**: Chama audio-transcriber API com `TEST-.ogg`
2. **Cria vídeo de teste**: FFmpeg gera vídeo 1280x720 com áudio
3. **VAD processing REAL**: SubtitleGenerator processa segments com VAD
4. **Gera SRT**: Cria arquivo SRT (valida que não está vazio)
5. **Burn-in REAL**: VideoBuilder aplica legendas com FFmpeg
6. **Valida vídeo final**: FFprobe verifica que vídeo é válido

**Serviços chamados**:
- ✅ audio-transcriber API (HTTPS)
- ✅ SubtitleGenerator (VAD local)
- ✅ VideoBuilder (FFmpeg local)
- ✅ FFprobe (validação)

**Validações**:
- ✅ Transcrição retornou segments (não vazios)
- ✅ SRT gerado tem conteúdo (> 0 bytes)
- ✅ Vídeo final criado (> 100KB)
- ✅ FFprobe valida vídeo (não corrompido)

**Expectativa**: ✅ **DEVE PASSAR** (se todos os serviços estão funcionando)

**Possíveis falhas esperadas**:
- ❌ audio-transcriber está DOWN → Erro de conexão
- ❌ FFmpeg não instalado → Comando não encontrado
- ❌ Áudio sem fala clara → SRT vazio → SubtitleGenerationException

**Execução**:
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video/test-prod
python test_real_pipeline_complete.py
```

---

## 🚀 Como Executar Todos os Testes

### Executor Automático

```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video/test-prod
python run_all_real_tests.py
```

**O que faz**:
1. Executa `test_real_audio_transcription.py`
2. Executa `test_real_pipeline_complete.py`
3. Gera relatório JSON em `results/report_real_tests_*.json`
4. Exit code 0 se todos passaram, 1 se algum falhou

**Output esperado**:
```
🚀 TEST-PROD - Executando Testes REAIS
════════════════════════════════════════

✅ Transcrição com Áudio Real: PASSED (45.2s)
✅ Pipeline Completo End-to-End: PASSED (62.8s)

📊 RELATÓRIO FINAL
════════════════════════════════════════
Total: 2 testes
✅ Passaram: 2
❌ Falharam: 0
⏱️  Duração: 108.0s

🎉 TODOS OS TESTES PASSARAM
💡 Sistema PRONTO para deploy!
```

---

## 🛠️ Pré-requisitos

### 1. Áudio de Teste

```bash
# Copiar áudio real para test-prod/samples/
cp /root/YTCaption-Easy-Youtube-API/services/make-video/tests/TEST-.ogg \
   /root/YTCaption-Easy-Youtube-API/services/make-video/test-prod/samples/
```

### 2. Serviços Externos

- ✅ audio-transcriber API: `https://yttranscriber.loadstask.com`
  - Deve estar **ONLINE** e acessível
  - Testar: `curl https://yttranscriber.loadstask.com/health`

### 3. Dependências Locais

```bash
# FFmpeg (para burn-in)
ffmpeg -version

# FFprobe (para validação)
ffprobe -version

# Python packages
pip install httpx asyncio
```

---

## ⚠️ Troubleshooting

### Erro: "Connection timeout"

**Causa**: audio-transcriber API está DOWN ou rede sem conectividade

**Solução**:
```bash
# Verificar se API está online
curl https://yttranscriber.loadstask.com/health

# Se retornar 200, API está OK
# Se timeout/erro, API está DOWN
```

### Erro: "FFmpeg command not found"

**Causa**: FFmpeg não está instalado

**Solução**:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# Mac
brew install ffmpeg

# Verificar
ffmpeg -version
```

### Erro: "SubtitleGenerationException: SRT vazio"

**Causa**: VAD filtrou todos os segments (áudio sem fala detectável)

**Comportamento**: ✅ **CORRETO** - Em produção, job seria marcado como FAILED

**Validação**: Se TEST-.ogg tem fala clara, pode ser:
- VAD threshold muito alto (> 0.5)
- Whisper retornou segments vazios
- Áudio corrompido

### Erro: "Job failed" na API

**Causa**: audio-transcriber processou mas retornou erro

**Solução**:
```bash
# Ver logs da API (se tiver acesso)
# Ou verificar se áudio é válido:
ffprobe samples/TEST-.ogg
```

---

## 📊 Resultados Salvos

Após executar testes, arquivos são salvos em `results/`:

```
results/
├── transcription_20260220_153045.json        # Resposta da API (segments)
├── test_subtitles_real.srt                   # SRT gerado com VAD
├── test_video_with_real_subtitles.mp4        # Vídeo final com legendas
└── report_real_tests_20260220_153120.json    # Relatório dos testes
```

**Relatório JSON**:
```json
{
  "timestamp": "2026-02-20T15:31:20",
  "total_tests": 2,
  "passed": 2,
  "failed": 0,
  "total_duration_seconds": 108.0,
  "tests": [
    {
      "test": "Transcrição com Áudio Real",
      "status": "PASSED",
      "duration_seconds": 45.2,
      "output": "..."
    },
    {
      "test": "Pipeline Completo End-to-End",
      "status": "PASSED",
      "duration_seconds": 62.8,
      "output": "..."
    }
  ]
}
```

---

## 🎯 Próximos Passos

Após validação dos testes reais:

### 1. ✅ Se todos os testes PASSARAM:

- Sistema está funcional em produção
- Correções validadas
- Melhorias M1-M5 prontas para integração

**Ações**:
```bash
# 1. Integrar melhorias no código principal
cd /root/YTCaption-Easy-Youtube-API/services/make-video

# 2. Mover testes para tests/ (se necessário)
# 3. Deploy em produção
# 4. Mover test-prod/ para .trash/
```

### 2. ❌ Se algum teste FALHOU:

**Investigar causa**:
1. Verificar logs do teste
2. Verificar se serviços estão online
3. Validar áudio TEST-.ogg
4. Testar manualmente API

**Não deploy em produção até resolver!**

---

## 📖 Documentação Adicional

- **Bug fix crítico**: [RESUMO_COMPLETO.md](RESUMO_COMPLETO.md)
- **Melhorias M1-M5**: [improvements/](improvements/)
- **Monitoramento**: [monitor_logs.py](monitor_logs.py)
- **Código principal**: [../app/](../app/)

---

## 💡 FAQ

### Q: Por que não usar mocks nos testes?

**A**: Mocks podem mentir. Se API muda formato de resposta ou serviço está DOWN, mock passa mas produção falha. Testes reais detectam isso.

### Q: Quanto tempo levam os testes?

**A**: ~1-2 minutos por teste (depende da API):
- Transcrição REAL: ~30-60s (depende do áudio)
- Pipeline completo: ~60-90s (transcrição + burn-in)

### Q: Posso rodar em CI/CD?

**A**: Sim, mas:
- Precisa de conectividade com audio-transcriber API
- FFmpeg instalado no runner
- Considere timeout de 5min por teste

### Q: E se API está DOWN?

**A**: Testes vão FALHAR. Isso é CORRETO - reflete o que vai acontecer em produção. Não deploy até resolver.

---

**Desenvolvido por**: GitHub Copilot + Claude Sonnet 4.5  
**Data**: 2026-02-20  
**Status**: ✅ PRONTO PARA VALIDAÇÃO
