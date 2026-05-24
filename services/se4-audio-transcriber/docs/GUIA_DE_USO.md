# 🚀 Guia de Uso - Audio Transcriber com Word-Level Timestamps

**Versão:** 2.0.0  
**Data:** 2026-02-28

---

## 📖 VISÃO GERAL

O serviço Audio Transcriber agora suporta **timestamps palavra por palavra** (word-level timestamps) usando **faster-whisper**. Esta feature é essencial para:

- ✅ Sincronização precisa de áudio e vídeo
- ✅ Lip-sync (sincronização labial)
- ✅ Legendas com timing perfeito
- ✅ Edição granular de transcrições

---

## 🎯 COMO USAR

### 1. Listar Engines Disponíveis

```bash
curl http://localhost:8004/engines | jq '.engines[] | {id, word_timestamps: .features.word_timestamps}'
```

**Resposta:**
```json
[
  {
    "id": "faster-whisper",
    "word_timestamps": true
  },
  {
    "id": "openai-whisper",
    "word_timestamps": false
  },
  {
    "id": "whisperx",
    "word_timestamps": true
  }
]
```

### 2. Criar Job de Transcrição com Word Timestamps

```bash
curl -X POST http://localhost:8004/jobs \
  -F "file=@audio.mp3" \
  -F "language_in=auto" \
  -F "engine=faster-whisper"
```

**Resposta:**
```json
{
  "id": "abc123_transcribe_auto",
  "status": "queued",
  "engine": "faster-whisper"
}
```

### 3. Verificar Status do Job

```bash
curl http://localhost:8004/jobs/abc123_transcribe_auto | jq '{status, progress}'
```

### 4. Obter Resultado com Words

```bash
curl http://localhost:8004/jobs/abc123_transcribe_auto | jq '.transcription_segments[0].words[0:5]'
```

**Resposta:**
```json
[
  {
    "word": " Olá",
    "start": 0.0,
    "end": 0.5,
    "probability": 0.98
  },
  {
    "word": " mundo",
    "start": 0.6,
    "end": 1.2,
    "probability": 0.99
  }
]
```

---

## 🎨 USANDO O SWAGGER UI (/docs)

### 1. Acesse a documentação interativa:
```
http://localhost:8004/docs
```

### 2. Encontre o endpoint `POST /jobs`

### 3. Clique em "Try it out"

### 4. Preencha os campos:

- **file**: Selecione seu arquivo de áudio
- **language_in**: `auto` (detectar) ou código ISO (ex: `pt`, `en`)
- **language_out**: *(opcional)* Para tradução
- **engine**: Selecione no **dropdown**:
  - `faster-whisper` ← **Recomendado** (word timestamps)
  - `openai-whisper`
  - `whisperx` (se instalado)

### 5. Clique em "Execute"

---

## 💻 EXEMPLO EM PYTHON

```python
import requests
import time

# 1. Criar job
with open('audio.mp3', 'rb') as f:
    response = requests.post(
        'http://localhost:8004/jobs',
        files={'file': f},
        data={
            'language_in': 'pt',
            'engine': 'faster-whisper'
        }
    )

job = response.json()
job_id = job['id']
print(f"Job criado: {job_id}")

# 2. Aguardar processamento
while True:
    response = requests.get(f'http://localhost:8004/jobs/{job_id}')
    job = response.json()
    
    if job['status'] == 'completed':
        break
    elif job['status'] == 'failed':
        print(f"Erro: {job['error_message']}")
        exit(1)
    
    print(f"Progresso: {job['progress']:.1f}%")
    time.sleep(2)

# 3. Obter palavras transcritas
for segment in job['transcription_segments']:
    print(f"\n[{segment['start']:.1f}s - {segment['end']:.1f}s]")
    print(f"Texto: {segment['text']}")
    
    if segment.get('words'):
        print("Palavras:")
        for word in segment['words']:
            print(f"  {word['start']:.2f}s - {word['end']:.2f}s: {word['word']} ({word['probability']:.0%})")
```

---

## 🎬 INTEGRAÇÃO COM MAKE-VIDEO

O serviço **make-video** detecta automaticamente word-level timestamps!

**Código (já existe):** `celery_tasks.py:806`
```python
has_word_timestamps = any(segment.get('words') for segment in segments)

if has_word_timestamps:
    logger.info("✅ Using word-level timestamps from Whisper")
    # Usa timestamps precisos
else:
    # Fallback: ponderação por comprimento
```

**Nada a fazer!** A integração é automática. 🎉

---

## 📊 ESTRUTURA DO RESULTADO

### Segment (Tradicional)
```json
{
  "text": "Olá mundo, como vai?",
  "start": 0.0,
  "end": 2.5,
  "duration": 2.5
}
```

### Segment com Words (Novo!)
```json
{
  "text": "Olá mundo, como vai?",
  "start": 0.0,
  "end": 2.5,
  "duration": 2.5,
  "words": [
    {"word": " Olá", "start": 0.0, "end": 0.5, "probability": 0.98},
    {"word": " mundo,", "start": 0.6, "end": 1.2, "probability": 0.99},
    {"word": " como", "start": 1.3, "end": 1.7, "probability": 0.97},
    {"word": " vai?", "start": 1.8, "end": 2.5, "probability": 0.96}
  ]
}
```

---

## ⚙️ CONFIGURAÇÃO

### Variáveis de Ambiente (.env)

```bash
# Engine de transcrição (padrão)
WHISPER_ENGINE=faster-whisper

# Modelo Whisper
WHISPER_MODEL=small  # tiny, base, small, medium, large

# Device
WHISPER_DEVICE=cpu  # cpu ou cuda

# Word-level timestamps (sempre habilitado no faster-whisper)
WHISPER_WORD_TIMESTAMPS=true
```

---

## 🔍 TROUBLESHOOTING

### Problema: Words vem null
**Solução:** Certifique-se de usar `engine=faster-whisper`

```bash
# ✅ Correto
curl -X POST http://localhost:8004/jobs \
  -F "file=@audio.mp3" \
  -F "engine=faster-whisper"

# ❌ Errado (openai-whisper não suporta words)
curl -X POST http://localhost:8004/jobs \
  -F "file=@audio.mp3" \
  -F "engine=openai-whisper"
```

### Problema: Dropdown não aparece no /docs
**Causa:** Versão antiga ou cache do browser

**Solução:**
1. Limpar cache do navegador (Ctrl+Shift+Del)
2. Abrir em modo anônimo
3. Verificar OpenAPI schema:
   ```bash
   curl http://localhost:8004/openapi.json | jq '.components.schemas.WhisperEngine'
   ```

### Problema: Confidence muito baixo
**Causa:** Modelo pequeno ou áudio com ruído

**Solução:**
- Usar modelo maior: `WHISPER_MODEL=medium` ou `large`
- Pré-processar áudio (remover ruído)
- Usar WhisperX (forced alignment mais preciso)

---

## 📚 REFERÊNCIAS

- **FastAPI Docs:** http://localhost:8004/docs
- **Engines:** http://localhost:8004/engines
- **Healthcheck:** http://localhost:8004/health
- **Checklist:** [CHECKLIST.md](./CHECKLIST.md)
- **Implementação:** [IMPLEMENTACAO_COMPLETA_FINAL.md](./IMPLEMENTACAO_COMPLETA_FINAL.md)

---

## 🆘 SUPORTE

**Logs:**
```bash
# API
docker logs audio-transcriber-api --tail 100 -f

# Celery Worker
docker logs audio-transcriber-celery --tail 100 -f
```

**Restart:**
```bash
docker restart audio-transcriber-api audio-transcriber-celery
```

**Testes:**
```bash
cd /root/YTCaption-Easy-Youtube-API/services/se4-audio-transcriber
bash test_e2e_complete.sh
```

---

**🎉 Pronto para usar!**
