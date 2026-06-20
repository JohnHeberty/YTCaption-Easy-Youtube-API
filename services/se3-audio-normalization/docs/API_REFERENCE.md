# API Reference - SE3 Audio Normalization

**Versao:** 2.0.0 | **Base URL:** http://localhost:8003 | **Auth:** `X-API-Key: se3-test-key-2026`

## Fluxo principal

1. Criar job: `POST /jobs` com arquivo de audio
2. Consultar: `GET /jobs/{job_id}` (polling)
3. Download: `GET /jobs/{job_id}/download`

---

## POST /jobs

Criar job de normalizacao de audio.

**Request:** `multipart/form-data`
- `file`: arquivo de audio (obrigatorio)
- `remove_noise`: boolean (default: true)
- `convert_to_mono`: boolean (default: true)
- `apply_highpass_filter`: boolean (default: false)
- `set_sample_rate_16k`: boolean (default: true)
- `isolate_vocals`: boolean (default: false)

**Response 201:**
```json
{
  "job_id": "norm_abc123",
  "status": "queued",
  "filename": "audio_original.wav"
}
```

**curl:**
```bash
curl -X POST "http://localhost:8003/jobs" \
  -H "X-API-Key: se3-test-key-2026" \
  -F "file=@audio.wav" \
  -F "remove_noise=true"
```

---

## GET /jobs

Listar jobs recentes.

**Query:** `limit` (opcional, default 20)

---

## GET /jobs/{job_id}

Status detalhado do job.

**Response 200:**
```json
{
  "job_id": "norm_abc123",
  "status": "completed",
  "progress": 100,
  "output_file": "norm_abc123_normalized.wav",
  "duration_seconds": 120.5
}
```

---

## GET /jobs/{job_id}/download

Download do audio normalizado.

**Response 200:** `audio/wav` binario

---

## DELETE /jobs/{job_id}

Deletar job e arquivos associados.

---

## POST /jobs/{job_id}/heartbeat

Atualizar heartbeat do job (evita timeout).

---

## GET /health

Health check profundo (Redis, disco, ffmpeg).

---

## GET /admin/stats

Estatisticas do sistema.

---

## GET /admin/queue

Info da fila Celery.

---

## POST /admin/cleanup

Limpar jobs antigos e arquivos temporarios.

---

## GET /metrics

Metricas Prometheus.

---

## GET /

Info do servico.
