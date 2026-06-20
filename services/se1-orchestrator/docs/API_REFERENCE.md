# API Reference - SE1 Orchestrator

**Versao:** 1.0.0 | **Base URL:** http://localhost:8001 | **Auth:** `X-API-Key: se1-test-key-2026`

## Fluxo principal

1. Enviar video: `POST /process` com URL do YouTube
2. Consultar: `GET /jobs/{job_id}` (polling ou SSE)
3. resultado: transcricao + normalizacao

---

## POST /process

Iniciar pipeline de processamento de video.

**Request:**
```json
{
  "video_url": "https://www.youtube.com/watch?v=xxxxx",
  "language": "auto",
  "remove_noise": true,
  "convert_to_mono": true,
  "language_out": "pt",
  "apply_highpass_filter": false,
  "set_sample_rate_16k": true
}
```

**Response 200:**
```json
{
  "job_id": "job_abc123",
  "status": "queued",
  "message": "Pipeline started"
}
```

**curl:**
```bash
curl -X POST "http://localhost:8001/process" \
  -H "X-API-Key: se1-test-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=xxxxx"}'
```

---

## GET /jobs

Listar jobs.

**Query:** `limit` (opcional, default 20)

---

## GET /jobs/{job_id}

Status detalhado do job com progresso por estagio.

**Response 200:**
```json
{
  "job_id": "job_abc123",
  "status": "processing",
  "progress": 45,
  "stages": {
    "download": {"status": "completed", "progress": 100},
    "normalize": {"status": "processing", "progress": 30},
    "transcribe": {"status": "pending", "progress": 0}
  }
}
```

---

## GET /jobs/{job_id}/wait

Long-poll aguardando conclusao do job.

---

## GET /jobs/{job_id}/stream

SSE stream com progresso em tempo real.

---

## GET /admin/stats

Estatisticas do sistema (jobs por status, uso de disco).

---

## POST /admin/cleanup

Limpar jobs antigos.

---

## POST /admin/factory-reset

Reset completo de todos os services.

---

## GET /health

Health check (Redis, microservicos, disco).

---

## GET /

Info do servico.
