# API Reference - SE7 Audio Generation

**Versao:** 1.0.0 | **Base URL:** http://localhost:8007 | **Auth:** `X-API-Key: se7-test-key-2026`

## Fluxo principal

1. Criar job: `POST /jobs` com texto e voice_id
2. Consultar: `GET /jobs/{job_id}` (polling)
3. Download: `GET /jobs/{job_id}/download`

---

## POST /jobs

Criar job de geracao de audio (TTS).

**Request:** `multipart/form-data`
- `text`: texto para narra (obrigatorio)
- `voice_id`: ID do perfil de voz (default: builtin_feminino)
- `exaggeration`: float 0.0-2.0 (default: 0.5)
- `cfg_weight`: float 0.0-1.0 (default: 0.5)
- `temperature`: float 0.0-2.0 (default: 0.8)
- `normalize_text`: boolean (default: true)

**Response 201:**
```json
{
  "success": true,
  "job_id": "ag_abc123def456_7890abcd",
  "status": "queued",
  "message": "Audio generation job created"
}
```

**curl:**
```bash
curl -X POST "http://localhost:8007/jobs" \
  -H "X-API-Key: se7-test-key-2026" \
  -F "text=Ola, este e um teste de geracao de audio." \
  -F "voice_id=builtin_feminino"
```

---

## GET /jobs

Listar jobs recentes.

**Query:** `limit` (opcional, default 20, max 100)

---

## GET /jobs/{job_id}

Status detalhado do job.

**Response 200:**
```json
{
  "id": "ag_abc123def456_7890abcd",
  "status": "completed",
  "progress": 100,
  "stages": {
    "model_loading": {"status": "completed"},
    "text_chunking": {"status": "completed"},
    "audio_generation": {"status": "completed"},
    "audio_assembly": {"status": "completed"}
  },
  "output_duration_seconds": 4.2
}
```

---

## GET /jobs/{job_id}/download

Download do audio gerado.

**Response 200:** `audio/wav` binario

---

## DELETE /jobs/{job_id}

Deletar job e arquivo de audio.

---

## POST /voices

Criar perfil de voz (upload de amostra de audio).

**Request:** `multipart/form-data`
- `name`: nome do perfil (obrigatorio)
- `file`: arquivo de audio WAV/MP3 (obrigatorio)
- `description`: descricao (opcional)

**Response 201:**
```json
{
  "id": "vc_abc123",
  "name": "Minha Voz",
  "description": "Descricao da voz",
  "created_at": "2026-06-19T12:00:00Z",
  "duration_seconds": 8.5,
  "sample_rate": 22050,
  "status": "active",
  "message": "Voice profile created"
}
```

---

## GET /voices

Listar todos os perfis de voz.

---

## GET /voices/{voice_id}

Detalhes de um perfil de voz.

---

## GET /voices/{voice_id}/sample

Download do audio de amostra do perfil.

---

## DELETE /voices/{voice_id}

Deletar perfil de voz.

---

## GET /health

Health check (Redis, modelo, disco).

---

## GET /admin/stats

Estatisticas do sistema.

---

## POST /admin/cleanup

Limpar jobs antigos.

---

## GET /

Info do servico.
