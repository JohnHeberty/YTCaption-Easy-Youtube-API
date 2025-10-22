# 🔌 API Usage

**Guia completo de uso da API - todos os endpoints, requests e responses.**

---

## 📋 Índice

1. [Base URL](#base-url)
2. [Autenticação](#autenticação)
3. [Endpoints](#endpoints)
4. [Exemplos de Uso](#exemplos-de-uso)
5. [Códigos de Erro](#códigos-de-erro)
6. [Rate Limiting](#rate-limiting)

---

## Base URL

```
http://localhost:8000
```

**Em produção** (com domínio):
```
https://seu-dominio.com
```

---

## Autenticação

❌ **Não requer autenticação** (API pública).

⚠️ **Recomendação para produção**: Configure Nginx com autenticação básica ou API key.

---

## Endpoints

### 1. POST `/api/v1/transcribe`

**Transcreve áudio de vídeo do YouTube.**

#### Request

**Headers**:
```
Content-Type: application/json
```

**Body**:
```json
{
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "format": "json"
}
```

**Parâmetros**:

| Campo | Tipo | Obrigatório | Valores | Descrição |
|-------|------|-------------|---------|-----------|
| `video_url` | string | ✅ Sim | URL do YouTube | Link do vídeo |
| `format` | string | ❌ Não | `json`, `text`, `srt`, `vtt` | Formato de saída (padrão: `json`) |
| 🆕 `enable_tor` | boolean | ❌ Não | `true`, `false` | Override: força uso do Tor (v3.0) |
| 🆕 `max_retries` | integer | ❌ Não | `1-10` | Override: número de retries (v3.0) |

#### Response Success (200 OK)

**Format: `json` (padrão)**:
```json
{
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "video_title": "Título do Vídeo",
  "duration": 125.5,
  "transcription": {
    "text": "Texto completo da transcrição...",
    "segments": [
      {
        "start": 0.0,
        "end": 5.2,
        "text": "Primeira frase transcrita."
      },
      {
        "start": 5.2,
        "end": 10.8,
        "text": "Segunda frase transcrita."
      }
    ],
    "language": "pt"
  },
  "processing_time": 42.3,
  "model_used": "base",
  "mode": "parallel"
}
```

**Format: `text`**:
```
Texto completo da transcrição em formato plano.
Cada segmento em uma linha.
```

**Format: `srt` (legendas SubRip)**:
```
1
00:00:00,000 --> 00:00:05,200
Primeira frase transcrita.

2
00:00:05,200 --> 00:00:10,800
Segunda frase transcrita.
```

**Format: `vtt` (WebVTT)**:
```
WEBVTT

00:00:00.000 --> 00:00:05.200
Primeira frase transcrita.

00:00:05.200 --> 00:00:10.800
Segunda frase transcrita.
```

#### Response Fields (JSON)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `video_url` | string | URL original do vídeo |
| `video_title` | string | Título do vídeo (do YouTube) |
| `duration` | float | Duração do áudio (segundos) |
| `transcription.text` | string | Transcrição completa |
| `transcription.segments` | array | Lista de segmentos com timestamps |
| `transcription.segments[].start` | float | Tempo inicial (segundos) |
| `transcription.segments[].end` | float | Tempo final (segundos) |
| `transcription.segments[].text` | string | Texto do segmento |
| `transcription.language` | string | Idioma detectado (ISO 639-1) |
| `processing_time` | float | Tempo de processamento (segundos) |
| `model_used` | string | Modelo Whisper usado |
| `mode` | string | Modo usado (`single-core` ou `parallel`) |

#### Response Error (4xx/5xx)

```json
{
  "detail": "Descrição do erro"
}
```

**Erros comuns**:

| Status | Error | Causa |
|--------|-------|-------|
| 400 | `Invalid YouTube URL` | URL malformada ou não é do YouTube |
| 400 | `Video duration exceeds limit` | Vídeo muito longo (>MAX_VIDEO_DURATION_SECONDS) |
| 400 | `Video size exceeds limit` | Vídeo muito grande (>MAX_VIDEO_SIZE_MB) |
| 🆕 403 | `YouTube download failed: HTTP 403` | YouTube bloqueou (habilite Tor - v3.0) |
| 404 | `Video not found` | Vídeo privado, deletado ou indisponível |
| 🆕 429 | `Rate limit exceeded` | Limite de YouTube requests/min (v3.0) |
| 429 | `Too many requests` | Limite de requisições atingido |
| 500 | `Transcription failed` | Erro interno no processamento |
| 🆕 500 | `All download strategies failed` | YouTube bloqueou todas as 7 estratégias (v3.0) |
| 503 | `Service temporarily unavailable` | Servidor sobrecarregado |

**🆕 Troubleshooting v3.0**: Para erros 403/429/500 relacionados a download, veja [Troubleshooting - YouTube Resilience](./08-TROUBLESHOOTING.md#v30---youtube-resilience-system).

---

### 2. GET `/api/v1/video-info`

**Obtém informações do vídeo sem transcrever.**

#### Request

**Query Parameters**:
```
GET /api/v1/video-info?video_url=https://www.youtube.com/watch?v=VIDEO_ID
```

**Parâmetros**:

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `video_url` | string | ✅ Sim | URL do vídeo do YouTube |

#### Response Success (200 OK)

```json
{
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "video_id": "VIDEO_ID",
  "title": "Título do Vídeo",
  "duration": 3725,
  "thumbnail": "https://i.ytimg.com/vi/VIDEO_ID/maxresdefault.jpg",
  "channel": "Nome do Canal",
  "upload_date": "20231015",
  "view_count": 152384,
  "like_count": 8432,
  "description": "Descrição do vídeo...",
  "available_formats": [
    "worstaudio",
    "bestaudio"
  ]
}
```

#### Response Fields

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `video_url` | string | URL original |
| `video_id` | string | ID do vídeo (extraído da URL) |
| `title` | string | Título do vídeo |
| `duration` | integer | Duração em segundos |
| `thumbnail` | string | URL da thumbnail |
| `channel` | string | Nome do canal |
| `upload_date` | string | Data de upload (YYYYMMDD) |
| `view_count` | integer | Número de visualizações |
| `like_count` | integer | Número de likes |
| `description` | string | Descrição completa |
| `available_formats` | array | Formatos de áudio disponíveis |

---

### 3. GET `/health`

**Verifica status da API.**

#### Request

```
GET /health
```

#### Response Success (200 OK)

```json
{
  "status": "healthy",
  "version": "1.3.3",
  "timestamp": "2025-10-19T14:30:45.123Z",
  "uptime": 3625.5,
  "model": "base",
  "device": "cpu",
  "parallel_enabled": true,
  "system": {
    "cpu_count": 4,
    "memory_available_mb": 5234,
    "disk_free_gb": 42.5
  }
}
```

#### Response Fields

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | string | `healthy` ou `unhealthy` |
| `version` | string | Versão da aplicação |
| `timestamp` | string | Timestamp ISO 8601 |
| `uptime` | float | Tempo online (segundos) |
| `model` | string | Modelo Whisper carregado |
| `device` | string | Dispositivo (`cpu` ou `cuda`) |
| `parallel_enabled` | boolean | Se transcrição paralela está ativa |
| `system.cpu_count` | integer | Número de cores CPU |
| `system.memory_available_mb` | float | RAM disponível (MB) |
| `system.disk_free_gb` | float | Disco livre (GB) |

---

## Exemplos de Uso

### 1. cURL

**Transcrição básica**:
```bash
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=VIDEO_ID"
  }'
```

**Transcrição com formato SRT**:
```bash
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "format": "srt"
  }' -o legendas.srt
```

**Informações do vídeo**:
```bash
curl "http://localhost:8000/api/v1/video-info?video_url=https://www.youtube.com/watch?v=VIDEO_ID"
```

**Health check**:
```bash
curl http://localhost:8000/health
```

---

### 2. Python (requests)

```python
import requests

# Transcrição
response = requests.post(
    "http://localhost:8000/api/v1/transcribe",
    json={
        "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
        "format": "json"
    }
)

data = response.json()
print(f"Título: {data['video_title']}")
print(f"Transcrição: {data['transcription']['text']}")

# Informações do vídeo
info = requests.get(
    "http://localhost:8000/api/v1/video-info",
    params={"video_url": "https://www.youtube.com/watch?v=VIDEO_ID"}
).json()
print(f"Duração: {info['duration']}s")
```

---

### 3. JavaScript (fetch)

```javascript
// Transcrição
const response = await fetch('http://localhost:8000/api/v1/transcribe', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    video_url: 'https://www.youtube.com/watch?v=VIDEO_ID',
    format: 'json'
  })
});

const data = await response.json();
console.log('Título:', data.video_title);
console.log('Transcrição:', data.transcription.text);

// Informações do vídeo
const info = await fetch(
  'http://localhost:8000/api/v1/video-info?video_url=https://www.youtube.com/watch?v=VIDEO_ID'
);
const videoInfo = await info.json();
console.log('Duração:', videoInfo.duration, 'segundos');
```

---

### 4. PowerShell

```powershell
# Transcrição
$body = @{
    video_url = "https://www.youtube.com/watch?v=VIDEO_ID"
    format = "json"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/transcribe" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

Write-Host "Título: $($response.video_title)"
Write-Host "Transcrição: $($response.transcription.text)"

# Health check
$health = Invoke-RestMethod -Uri "http://localhost:8000/health"
Write-Host "Status: $($health.status)"
```

---

## Códigos de Erro

### 400 Bad Request

**Causas**:
- URL do YouTube inválida
- Formato de requisição incorreto
- Vídeo muito longo ou muito grande
- Parâmetro `format` inválido

**Exemplo**:
```json
{
  "detail": "Invalid YouTube URL format"
}
```

---

### 404 Not Found

**Causas**:
- Vídeo não encontrado no YouTube
- Vídeo privado ou removido
- Endpoint inválido

**Exemplo**:
```json
{
  "detail": "Video not found or unavailable"
}
```

---

### 429 Too Many Requests

**Causas**:
- Limite de requisições simultâneas atingido (`MAX_CONCURRENT_REQUESTS`)
- Rate limiting ativado

**Exemplo**:
```json
{
  "detail": "Too many concurrent requests. Please try again later."
}
```

**Solução**: Aguarde alguns segundos e tente novamente.

---

### 500 Internal Server Error

**Causas**:
- Erro no processamento de áudio
- Falha no modelo Whisper
- Erro no FFmpeg
- Falta de RAM

**Exemplo**:
```json
{
  "detail": "Transcription failed: Out of memory"
}
```

**Solução**: 
1. Verifique logs do servidor
2. Reduza `MAX_CONCURRENT_REQUESTS`
3. Use modelo menor (`tiny` ou `base`)
4. Aumente RAM do servidor

---

### 503 Service Unavailable

**Causas**:
- Servidor sobrecarregado
- Inicialização em andamento
- Manutenção

**Exemplo**:
```json
{
  "detail": "Service temporarily unavailable"
}
```

**Solução**: Aguarde e tente novamente em alguns minutos.

---

## Rate Limiting

### Limites Padrão

**Requisições simultâneas**: Definido por `MAX_CONCURRENT_REQUESTS` (padrão: 3)

**Comportamento**:
- ✅ Request 1-3: Processado imediatamente
- ⏳ Request 4+: Aguarda na fila ou retorna 429

### Como Calcular Capacidade

```
Capacidade/hora = MAX_CONCURRENT_REQUESTS × (3600 / tempo_médio_processamento)
```

**Exemplo**:
- `MAX_CONCURRENT_REQUESTS=3`
- Tempo médio: 60 segundos/vídeo
- Capacidade: `3 × (3600 / 60)` = **180 vídeos/hora**

---

## Timeouts

### Request Timeout

**Padrão**: `REQUEST_TIMEOUT=3600` (1 hora)

**Comportamento**:
- Se transcrição demorar > 1 hora, retorna erro 504 Gateway Timeout

**Como ajustar**: Edite `.env`
```bash
REQUEST_TIMEOUT=7200  # 2 horas
```

---

## Interface Web

**URL**: `http://localhost:8000`

A API também disponibiliza interface web simples:
- Upload de URL
- Visualização de resultado
- Download em múltiplos formatos

---

## Documentação Interativa (Swagger)

**Swagger UI**: `http://localhost:8000/docs`

**ReDoc**: `http://localhost:8000/redoc`

Permite testar endpoints diretamente no navegador.

---

## Exemplos Avançados

### 1. Processar múltiplos vídeos (Python)

```python
import requests
from concurrent.futures import ThreadPoolExecutor

videos = [
    "https://www.youtube.com/watch?v=VIDEO_ID_1",
    "https://www.youtube.com/watch?v=VIDEO_ID_2",
    "https://www.youtube.com/watch?v=VIDEO_ID_3",
]

def transcribe(url):
    response = requests.post(
        "http://localhost:8000/api/v1/transcribe",
        json={"video_url": url}
    )
    return response.json()

# Processar em paralelo (máximo 3 ao mesmo tempo)
with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(transcribe, videos))

for result in results:
    print(f"{result['video_title']}: {len(result['transcription']['text'])} caracteres")
```

---

### 2. Salvar em arquivo (Bash)

```bash
#!/bin/bash

VIDEO_URL="https://www.youtube.com/watch?v=VIDEO_ID"

# Transcrever e salvar JSON
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d "{\"video_url\": \"$VIDEO_URL\"}" \
  -o transcription.json

# Transcrever e salvar SRT
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d "{\"video_url\": \"$VIDEO_URL\", \"format\": \"srt\"}" \
  -o legendas.srt

echo "Transcrição salva!"
```

---

### 3. Monitoramento (Python + loop)

```python
import requests
import time

def check_health():
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        data = response.json()
        return data['status'] == 'healthy'
    except:
        return False

while True:
    if check_health():
        print("✅ API está saudável")
    else:
        print("❌ API está com problemas!")
    
    time.sleep(60)  # Verifica a cada 1 minuto
```

---

**Próximo**: [Modelos Whisper](./05-WHISPER-MODELS.md)

**Versão**: 1.3.3+  
**Última atualização**: 19/10/2025
