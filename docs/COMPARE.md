# Chatterbox vs SE7 — Relatório Comparativo Arquitetural

**Data:** 2026-06-19
**Objetivo:** Identificar exatamente onde nosso SE7 se desvia do Chatterbox oficial e o que precisa ser corrigido.

---

## 1. Fluxo de Dados: Chatterbox Oficial vs Nosso SE7

### Chatterbox Oficial (app.py + tts.py)

```
Texto (str)
  ↓
punc_norm(text)                    # limpa pontuação, capitaliza 1ª letra
  ↓
tokenizer.text_to_tokens(text, "pt")  # prepend [pt], BPE encode
  ↓
text_tokens × 2 (CFG batch)        # batch_size=2 para classifier-free guidance
  ↓
F.pad(text_tokens, (1,0), SOT)     # prepend [START]
F.pad(text_tokens, (0,1), EOT)     # append [STOP]
  ↓
t3.inference(                       # LLaMA 520M autoregressivo
    t3_cond=conds,                  # speaker_emb + speech_prompt + emotion
    text_tokens=text_tokens,
    temperature=0.8,
    cfg_weight=0.5,
)
  ↓
speech_tokens[0]                    # pega apenas batch condicionado
  ↓
drop_invalid_tokens(speech_tokens)  # remove tokens >= SPEECH_VOCAB_SIZE
  ↓
s3gen.inference(                    # Flow Matching + HiFi-GAN
    speech_tokens=speech_tokens,
    ref_dict=conds.gen,
)
  ↓
wav[:st_len * (S3GEN_SR // S3_TOKEN_RATE)]  # recorta último token degradado
  ↓
watermarker.apply_watermark(wav)    # Perth watermark
  ↓
torch tensor (1, samples)           # 24kHz mono
```

### Nosso SE7 (model_manager.py + generator.py)

```
Texto (str)
  ↓
text.strip()                        # ← stripping
  ↓
normalize_pt_br(text)               # ← REMOVE ACENTOS (DESNECESSÁRIO)
  ↓
chunk_text(text, 250)               # split por parágrafos/frases
  ↓
Para cada chunk:
  ↓
model_manager.generate(             # ← CHAMA ChatterboxTTS.generate()
    text=chunk,
    language_id="pt",
    exaggeration=0.75,              # ← DIFERENTE DO OFICIAL (0.5)
    cfg_weight=0.35,                # ← DIFERENTE DO OFICIAL (0.5)
    temperature=0.8,
)
  ↓
  [Chatterbox internamente faz:]
  [punc_norm → tokenize → T3 → S3Gen → watermark]
  ↓
wav_tensor (1, samples)             # 24kHz
  ↓
assemble_audio(wave_arrays, 24000, silence_between_paras_ms=500)
  ↓
pydub: concat wav1 + 500ms silence + wav2 + ...
  ↓
WAV file (bytes)
```

---

## 2. Inconsistências Críticas Encontradas

### 2.1 Parâmetros TTS — 4 versões diferentes

| Fonte | exaggeration | cfg_weight | temperature | Correto? |
|-------|-------------|------------|-------------|----------|
| **Chatterbox oficial** (app.py) | **0.5** | **0.5** | **0.8** | ✅ REFERÊNCIA |
| `constants.py` | 0.5 | 0.5 | 0.8 | ✅ OK |
| `config.py` (settings) | 0.5 | 0.5 | 0.8 | ✅ OK |
| `interfaces.py` (IModelManager) | **0.75** | **0.35** | 0.8 | ❌ |
| `schemas.py` (JobDetailResponse) | **0.75** | **0.35** | 0.8 | ❌ |
| `.env` | 0.5 | **0.7** | **0.5** | ❌❌ |
| `.env.example` | **0.75** | **0.35** | 0.8 | ❌ |
| `model_manager.py` defaults | **0.75** | **0.35** | 0.8 | ❌ |
| `scripts/generate_test.py` | **0.75** | **0.35** | 0.8 | ❌ |

**Problema:** O `.env` (que é o que realmente roda em produção) tem `cfg_weight=0.7` e `temperature=0.5`. Isso está COMPLETAMENTE diferente do oficial. O `cfg_weight` alto (0.7) força o modelo a seguir mais a referência de voz, mas reduz naturalidade. O `temperature` baixo (0.5) torna a fala robótica.

### 2.2 Normalizador de Texto — DESNECESSÁRIO

O `pt_br_normalizer.py` remove acentos (`ç→c`, `ã→a`, `á→a`, etc.).

**Por que é desnecessário:**
1. O vocabulário BPE (`grapheme_mtl_merged_expanded_v1.json`) tem TODOS os caracteres PT-BR
2. O Chatterbox foi treinado com dados PT-BR — sabe pronunciar acentos
3. O usuário testou "Oi eu sou um cachorro, e meu nome é chão, pão." na Space e funcionou perfeitamente
4. Não há nenhuma normalização no `punc_norm()` do Chatterbox oficial

**Risco do normalizador:** Ao remover acentos, alteramos o significado de palavras:
- "licão" → "licao" (perde o til)
- "acao" em vez de "ação" (perde o til)
- "e" em vez de "é" (verbo ser vs conjunção)

### 2.3 Audio Assembly — pydub vs direto

**Chatterbox:** Gera UM wav contínuo por chamada `generate()`. Sem silêncio entre chunks.

**Nosso SE7:** Gera múltiplos chunks (250 chars cada), insere 500ms de silêncio entre cada um via pydub.

**Problema:** O silêncio de 500ms entre chunks é artificial e quebra o fluxo natural da fala. O Chatterbox não insere silêncio — quando o texto é longo, o modelo gera pausas naturais dentro de cada chunk.

### 2.4 Text Chunking — chunk_size=250

O Chatterbox tem limite de ~1000 tokens por geração. Com 2454 tokens no vocabulário, 250 caracteres PT-BR ≈ 250-400 tokens (dependendo de BPE). O chunk_size de 250 é conservador mas seguro.

**Porém:** O Chatterbox Space limita a 300 chars na interface. Nosso chunk de 250 é razoável.

### 2.5 Model Loading — Dois repos HuggingFace

**Chatterbox oficial:** `from_pretrained()` baixa tudo de UM repo (`ResembleAI/chatterbox` ou `ResembleAI/Chatterbox-Multilingual-pt-br`).

**Nosso SE7:** `_ensure_model_files()` baixa de DOIS repos:
- Base files (ve.pt, conds.pt, tokenizer) de `ResembleAI/chatterbox`
- PT-BR files (t3_pt_br.safetensors, s3gen_v3.pt) de `ResembleAI/Chatterbox-Multilingual-pt-br`

**Isso é CORRETO** — o repo PT-BR não tem os arquivos base, então precisa baixar de ambos.

### 2.6 Hardware de Áudio

| Aspecto | Chatterbox | Nosso SE7 |
|---------|-----------|-----------|
| Sample rate output | 24,000 Hz | 24,000 Hz ✅ |
| Canais | Mono | Mono ✅ |
| Formato | WAV (via torch) | WAV (via pydub) ✅ |
| Float→Int16 | Não explicitado | `(wav * 32767).astype(int16)` ⚠️ sem clamp |

**Risco:** Se o modelo gerar valores > 1.0 ou < -1.0, o cast para int16 causa clipping. O Chatterbox não clamp porque o modelo é treinado para output [-1, 1], mas é boa prática adicionar `np.clip(wav, -1, 1)`.

---

## 3. Fluxo Completo Comparado (Passo a Passo)

| Etapa | Chatterbox Oficial | Nosso SE7 | Status |
|-------|-------------------|-----------|--------|
| 1. Receber texto | `text` param | `job.input_text.strip()` | ✅ |
| 2. Normalizar pontuação | `punc_norm(text)` (interno) | `normalize_pt_br(text)` + Chatterbox faz `punc_norm` | ❌ Normalizador desnecessário |
| 3. Tokenizar | `tokenizer.text_to_tokens(text, "pt")` (interno) | Chatterbox faz internamente | ✅ |
| 4. CFG batch | `torch.cat([tokens, tokens])` (interno) | Chatterbox faz internamente | ✅ |
| 5. T3 inference | `t3.inference(t3_cond, text_tokens, temp=0.8, cfg=0.5)` | `model.generate(text, temp=0.8, cfg=0.35)` | ❌ cfg_weight errado |
| 6. Drop invalid tokens | `drop_invalid_tokens(speech_tokens)` (interno) | Chatterbox faz internamente | ✅ |
| 7. S3Gen inference | `s3gen.inference(speech_tokens, ref_dict)` (interno) | Chatterbox faz internamente | ✅ |
| 8. Recortar áudio | `wav[:st_len * (SR//TOKEN_RATE)]` (interno) | Chatterbox faz internamente | ✅ |
| 9. Watermark | `watermarker.apply_watermark(wav)` (interno) | Chatterbox faz internamente | ✅ |
| 10. Chunking | NÃO existe (300 char limit na interface) | `chunk_text(text, 250)` | ⚠️ Necessário mas silêncio artificial |
| 11. Assembly | NÃO existe (gera wav contínuo) | `assemble_audio()` com 500ms silence | ❌ Silêncio artificial |
| 12. Salvar WAV | `(sr, numpy_array)` via Gradio | `soundfile.write()` → arquivo .wav | ✅ |

---

## 4. O que Precisa Ser Corrigido

### PRIORIDADE ALTA (afeta qualidade do áudio)

| # | O quê | Onde | Correção |
|---|-------|------|----------|
| 1 | **cfg_weight=0.35** | `interfaces.py:43`, `schemas.py:42`, `model_manager.py:130` | Alterar para `0.5` (oficial) |
| 2 | **temperature=0.5** | `.env` linha com `DEFAULT_TEMPERATURE` | Alterar para `0.8` (oficial) |
| 3 | **cfg_weight=0.7** | `.env` linha com `DEFAULT_CFG_WEIGHT` | Alterar para `0.5` (oficial) |
| 4 | **Normalizador desnecessário** | `generator.py:46-48` | Remover chamada `normalize_pt_br()` |
| 5 | **Silêncio artificial 500ms** | `generator.py`, `audio_utils.py` | Reduzir para 100-200ms ou remover |

### PRIORIDADE MÉDIA (consistência)

| # | O quê | Onde | Correção |
|---|-------|------|----------|
| 6 | **.env.example** tem defaults errados | `.env.example` | Atualizar para 0.5/0.5/0.8 |
| 7 | **schemas.py** defaults 0.75/0.35 | `schemas.py:42` | Atualizar para 0.5/0.5 |
| 8 | **interfaces.py** defaults 0.75/0.35 | `interfaces.py:43` | Atualizar para 0.5/0.5 |
| 9 | **scripts/** defaults 0.75/0.35 | `generate_test.py`, `run_standalone.py` | Atualizar |

### PRIORIDADE BAIXA (robustez)

| # | O quê | Onde | Correção |
|---|-------|------|----------|
| 10 | **Float→Int16 sem clamp** | `audio_utils.py:125` | Adicionar `np.clip(wav, -1, 1)` |
| 11 | **docker-compose.cpu.yml** referencia Dockerfile errado | `docker-compose.cpu.yml:31` | Corrigir para `Dockerfile.cpu` |
| 12 | **Arquivo pt_br_normalizer.py** órfão | `app/services/pt_br_normalizer.py` | Manter como opcional ou remover |

---

## 5. O que está CORRETO no Nosso SE7

| Aspecto | Status | Notas |
|---------|--------|-------|
| `from_local()` para carregar modelo | ✅ | Correto para loading offline |
| Dois repos HuggingFace | ✅ | Necessário (base + PT-BR) |
| `language_id="pt"` hardcoded | ✅ | Correto para serviço PT-BR-only |
| Lazy loading do modelo | ✅ | Modelo carrega no 1º job |
| Celery task com retry | ✅ | Retry 3x com backoff |
| Voice cloning via áudio ref | ✅ | Funcional |
| Redis store com TTL | ✅ | 24h expiration |
| Health check com model status | ✅ | Reports model loaded/degraded |
| Output WAV 24kHz mono | ✅ | Match com Chatterbox |
| API REST completa | ✅ | POST/GET/DELETE jobs + voices |

---

## 6. Fluxo Ideal (depois das correções)

```
Texto (str)
  ↓
text.strip()
  ↓
chunk_text(text, 250)               # split por parágrafos/frases
  ↓
Para cada chunk:
  ↓
ChatterboxTTS.generate(             # chama modelo oficial
    text=chunk,
    audio_prompt_path=voice_ref,    # ou conds.pt para voz padrão
    language_id="pt",
    exaggeration=0.5,               # ← oficial
    cfg_weight=0.5,                 # ← oficial
    temperature=0.8,                # ← oficial
)
  ↓
  [Interno do Chatterbox:]
  [punc_norm → tokenize → T3(LLaMA) → S3Gen(flow+HiFiGAN) → watermark]
  ↓
wav_tensor (1, N)                   # 24kHz mono float
  ↓
np.clip(wav, -1, 1)                 # segurança
  ↓
assemble_audio(chunks, 24000, silence_ms=100)  # silêncio mínimo
  ↓
WAV file
```

---

## 7. Parâmetros TTS — Tabela Definitiva

| Parâmetro | Oficial | Nós (depois) | Efeito |
|-----------|---------|--------------|--------|
| `exaggeration` | 0.5 | 0.5 | Expressividade neutra |
| `cfg_weight` | 0.5 | 0.5 | Guidance balanceado |
| `temperature` | 0.8 | 0.8 | Aleatoriedade moderada |
| `language_id` | "pt" | "pt" | Português BR |
| `max_new_tokens` | 1000 | 1000 | Limite de geração |
| `chunk_size` | N/A | 250 | Nosso (necessário) |
| `silence_between_chunks` | N/A | 100ms | Nosso (reduzido de 500ms) |

---

## 8. Resumo de Ações

1. **REMOVER** `normalize_pt_br()` do `generator.py` (linhas 46-48)
2. **CORRIGIR** `.env`: `DEFAULT_CFG_WEIGHT=0.5`, `DEFAULT_TEMPERATURE=0.8`
3. **CORRIGIR** `interfaces.py`: defaults `exaggeration=0.5, cfg_weight=0.5`
4. **CORRIGIR** `schemas.py`: defaults `exaggeration=0.5, cfg_weight=0.5`
5. **CORRIGIR** `model_manager.py`: defaults `exaggeration=0.5, cfg_weight=0.5`
6. **CORRIGIR** `.env.example`: defaults `0.5/0.5/0.8`
7. **REDUZIR** silêncio entre chunks de 500ms para 100ms
8. **ADICIONAR** `np.clip()` no audio_utils.py
9. **CORRIGIR** docker-compose.cpu.yml para referenciar `Dockerfile.cpu`
