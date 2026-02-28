# 📖 API Reference - Audio Transcriber

**Versão**: 1.0.0  
**Base URL**: `http://localhost:8004`

---

## 🔵 Endpoints

### 1. POST `/transcribe`

Transcreve um arquivo de áudio.

#### Request

```http
POST /transcribe HTTP/1.1
Content-Type: multipart/form-data

file: (binary)
engine: faster-whisper|openai-whisper|whisperx (opcional)
language: pt|en|es|... (opcional)
model_size: tiny|base|small|medium|large (opcional)
```

#### Parameters

| Campo | Tipo | Requerido | Default | Descrição |
|-------|------|-----------|---------|-----------|
| `file` | File | ✅ | - | Arquivo de áudio (MP3, WAV, OGG, M4A) |
| `engine` | String | ❌ | `faster-whisper` | Engine de transcrição |
| `language` | String | ❌ | `None` (auto-detect) | Código ISO do idioma |
| `model_size` | String | ❌ | `base` | Tamanho do modelo |

#### Response

```json
{
  "job_id": "abc123def456",
  "status": "queued",
  "engine": "faster-whisper",
  "language": "pt",
  "model_size": "base",
  "created_at": "2026-02-21T10:00:00Z",
  "estimated_time_seconds": 15
}
```

#### Status Codes

| Code | Descrição |
|------|-----------|
| `202` | Aceito - Job criado com sucesso |
| `400` | Bad Request - Arquivo inválido ou parâmetros incorretos |
| `413` | Payload Too Large - Arquivo maior que 500MB |
| `415` | Unsupported Media Type - Formato não suportado |
| `429` | Too Many Requests - Rate limit excedido |
| `500` | Internal Server Error |

#### Exemplo

```bash
curl -X POST "http://localhost:8004/transcribe" \
  -F "file=@audio.mp3" \
  -F "engine=faster-whisper" \
  -F "language=pt" \
  -F "model_size=base"
```

```python
import requests

files = {'file': open('audio.mp3', 'rb')}
data = {
    'engine': 'faster-whisper',
    'language': 'pt',
    'model_size': 'base'
}

response = requests.post('http://localhost:8004/transcribe', 
                        files=files, data=data)
job = response.json()
```

---

### 2. GET `/status/{job_id}`

Consulta o status de um job de transcrição.

#### Request

```http
GET /status/{job_id} HTTP/1.1
```

#### Response

```json
{
  "job_id": "abc123def456",
  "status": "processing",
  "progress": 45,
  "engine": "faster-whisper",
  "language": "pt",
  "created_at": "2026-02-21T10:00:00Z",
  "started_at": "2026-02-21T10:00:05Z",
  "current_stage": "transcribing",
  "estimated_remaining_seconds": 10
}
```

#### Status Values

| Status | Descrição |
|--------|-----------|
| `queued` | Na fila aguardando processamento |
| `processing` | Processando agora |
| `completed` | Concluído com sucesso |
| `failed` | Falhou (ver `error` field) |
| `cancelled` | Cancelado pelo usuário |

#### Status Codes

| Code | Descrição |
|------|-----------|
| `200` | OK - Status retornado |
| `404` | Not Found - Job não existe |
| `500` | Internal Server Error |

#### Exemplo

```bash
curl "http://localhost:8004/status/abc123def456"
```

```python
import requests

job_id = "abc123def456"
status = requests.get(f'http://localhost:8004/status/{job_id}').json()
print(f"Status: {status['status']}")
print(f"Progress: {status.get('progress', 0)}%")
```

---

### 3. GET `/result/{job_id}`

Baixa o resultado da transcrição.

#### Request

```http
GET /result/{job_id}?format=txt HTTP/1.1
```

#### Query Parameters

| Campo | Tipo | Requerido | Default | Descrição |
|-------|------|-----------|---------|-----------|
| `format` | String | ❌ | `txt` | Formato do resultado (txt, srt, vtt, json) |

#### Response (format=txt)

```
Olá, este é um teste de transcrição.
A qualidade do áudio está boa.
Obrigado por usar o serviço.
```

#### Response (format=srt)

```srt
1
00:00:00,000 --> 00:00:02,500
Olá, este é um teste de transcrição.

2
00:00:02,500 --> 00:00:05,000
A qualidade do áudio está boa.

3
00:00:05,000 --> 00:00:07,000
Obrigado por usar o serviço.
```

#### Response (format=vtt)

```vtt
WEBVTT

00:00:00.000 --> 00:00:02.500
Olá, este é um teste de transcrição.

00:00:02.500 --> 00:00:05.000
A qualidade do áudio está boa.

00:00:05.000 --> 00:00:07.000
Obrigado por usar o serviço.
```

#### Response (format=json)

```json
{
  "text": "Olá, este é um teste de transcrição. A qualidade do áudio está boa. Obrigado por usar o serviço.",
  "language": "pt",
  "duration": 7.0,
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 2.5,
      "text": "Olá, este é um teste de transcrição.",
      "words": [
        {"word": "Olá", "start": 0.0, "end": 0.5, "probability": 0.99},
        {"word": "este", "start": 0.6, "end": 0.9, "probability": 0.98}
      ]
    },
    {
      "id": 1,
      "start": 2.5,
      "end": 5.0,
      "text": "A qualidade do áudio está boa.",
      "words": [...]
    }
  ]
}
```

#### Status Codes

| Code | Descrição |
|------|-----------|
| `200` | OK - Resultado retornado |
| `404` | Not Found - Job não existe ou não completou |
| `410` | Gone - Resultado expirou (TTL 7 dias) |
| `500` | Internal Server Error |

#### Exemplo

```bash
# Texto puro
curl "http://localhost:8004/result/abc123?format=txt" > transcription.txt

# SRT
curl "http://localhost:8004/result/abc123?format=srt" > subtitles.srt

# JSON
curl "http://localhost:8004/result/abc123?format=json" > result.json
```

```python
import requests

job_id = "abc123def456"

# Texto
txt = requests.get(f'http://localhost:8004/result/{job_id}?format=txt').text

# JSON
data = requests.get(f'http://localhost:8004/result/{job_id}?format=json').json()
print(f"Texto: {data['text']}")
print(f"Duração: {data['duration']}s")
```

---

### 4. DELETE `/job/{job_id}`

Cancela um job em processamento.

#### Request

```http
DELETE /job/{job_id} HTTP/1.1
```

#### Response

```json
{
  "job_id": "abc123def456",
  "status": "cancelled",
  "cancelled_at": "2026-02-21T10:05:00Z"
}
```

#### Status Codes

| Code | Descrição |
|------|-----------|
| `200` | OK - Job cancelado |
| `404` | Not Found - Job não existe |
| `409` | Conflict - Job já completou/falhou |
| `500` | Internal Server Error |

#### Exemplo

```bash
curl -X DELETE "http://localhost:8004/job/abc123def456"
```

---

### 5. GET `/health`

Health check do serviço.

#### Request

```http
GET /health HTTP/1.1
```

#### Response

```json
{
  "status": "healthy",
  "service": "audio-transcriber",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "redis": {
    "connected": true,
    "ping_ms": 1.2
  },
  "gpu": {
    "available": true,
    "device": "NVIDIA GeForce RTX 3090",
    "utilization": 45
  },
  "workers": {
    "active": 2,
    "busy": 1,
    "idle": 1
  }
}
```

#### Status Codes

| Code | Descrição |
|------|-----------|
| `200` | Healthy |
| `503` | Unhealthy |

---

## 🔐 Rate Limiting

O serviço implementa rate limiting distribuído via Redis.

### Limites

| Endpoint | Limite |
|----------|--------|
| `/transcribe` | 100 requests / hora |
| `/status/*` | 1000 requests / hora |
| `/result/*` | 500 requests / hora |

### Headers de Resposta

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1645432800
```

### Resposta quando excedido

```json
{
  "error": "Rate limit exceeded",
  "limit": 100,
  "reset_at": "2026-02-21T11:00:00Z",
  "retry_after_seconds": 300
}
```

---

## ⚠️ Error Responses

Todos os erros seguem o formato:

```json
{
  "error": "Error message",
  "error_code": "ERROR_CODE",
  "details": {
    "field": "Additional details"
  },
  "timestamp": "2026-02-21T10:00:00Z"
}
```

### Error Codes

| Code | HTTP Status | Descrição |
|------|-------------|-----------|
| `INVALID_FILE` | 400 | Arquivo inválido ou corrompido |
| `UNSUPPORTED_FORMAT` | 415 | Formato não suportado |
| `FILE_TOO_LARGE` | 413 | Arquivo maior que 500MB |
| `AUDIO_TOO_LONG` | 400 | Áudio maior que 4 horas |
| `INVALID_ENGINE` | 400 | Engine não existe |
| `INVALID_LANGUAGE` | 400 | Código de idioma inválido |
| `JOB_NOT_FOUND` | 404 | Job não existe |
| `RESULT_EXPIRED` | 410 | Resultado expirou (>7 dias) |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit excedido |
| `PROCESSING_ERROR` | 500 | Erro durante processamento |
| `REDIS_ERROR` | 503 | Redis indisponível |

---

## 📊 Webhooks (Opcional)

Configure webhooks para receber notificações quando jobs completarem.

### Configuração

```bash
# .env
WEBHOOK_URL=https://your-app.com/webhook
WEBHOOK_SECRET=your-secret-key
```

### Payload

```json
{
  "event": "job.completed",
  "job_id": "abc123def456",
  "status": "completed",
  "result_url": "http://localhost:8004/result/abc123def456",
  "duration_seconds": 15,
  "timestamp": "2026-02-21T10:05:00Z"
}
```

### Signature

```http
X-Webhook-Signature: sha256=abc123...
```

Verifique com HMAC-SHA256 usando `WEBHOOK_SECRET`.

---

## 🧪 SDKs e Exemplos

### Python

```python
from audio_transcriber_client import AudioTranscriber

client = AudioTranscriber(base_url='http://localhost:8004')

# Transcrever
job = client.transcribe(
    file_path='audio.mp3',
    engine='faster-whisper',
    language='pt'
)

# Aguardar conclusão
result = client.wait_for_completion(job['job_id'], timeout=300)

# Baixar resultado
transcript = client.get_result(job['job_id'], format='txt')
print(transcript)
```

### JavaScript

```javascript
const AudioTranscriber = require('audio-transcriber-client');

const client = new AudioTranscriber('http://localhost:8004');

// Transcrever
const job = await client.transcribe({
  filePath: 'audio.mp3',
  engine: 'faster-whisper',
  language: 'pt'
});

// Aguardar
const result = await client.waitForCompletion(job.job_id);

// Resultado
const transcript = await client.getResult(job.job_id, 'txt');
console.log(transcript);
```

---

## 📚 Links Relacionados

- **[Quickstart](QUICKSTART.md)** - Início rápido
- **[Engines Guide](ENGINES.md)** - Comparação de engines
- **[Data Pipeline](DATA_PIPELINE.md)** - Fluxo de dados interno
- **[Deployment](DEPLOYMENT.md)** - Deploy em produção
