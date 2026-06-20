# API Reference - SE2 Video Downloader

**Versao:** 3.0.0 | **Base URL:** http://localhost:8002 | **Auth:** `X-API-Key: se2-test-key-2026`

## Fluxo principal

1. Criar job: `POST /jobs` com URL do YouTube
2. Consultar: `GET /jobs/{job_id}` (polling)
3. Download: `GET /jobs/{job_id}/download`

---

## POST /jobs

Criar job de download de video.

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=xxxxx",
  "quality": "best"
}
```

**Response 201:**
```json
{
  "job_id": "dl_abc123",
  "status": "queued",
  "url": "https://www.youtube.com/watch?v=xxxxx"
}
```

**curl:**
```bash
curl -X POST "http://localhost:8002/jobs" \
  -H "X-API-Key: se2-test-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=xxxxx"}'
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
  "job_id": "dl_abc123",
  "status": "completed",
  "progress": 100,
  "file_path": "/downloads/video.mp4",
  "file_size_mb": 45.2
}
```

---

## GET /jobs/{job_id}/download

Download do arquivo de video.

**Response 200:** `video/mp4` binario

---

## DELETE /jobs/{job_id}

Deletar job e arquivo associado.

---

## GET /jobs/orphaned

Listar jobs orfaos (sem arquivo no disco).

---

## POST /jobs/orphaned/cleanup

Limpar jobs orfaos.

---

## GET /admin/stats

Estatisticas do sistema.

---

## GET /admin/queue

Info da fila Celery.

---

## POST /admin/cleanup

Limpar jobs antigos.

---

## GET /user-agents/stats

Estatisticas de user agents (rotacao).

---

## POST /user-agents/reset/{user_agent_id}

Resetar um user agent especifico.

---

## GET /metrics

Metricas Prometheus.

---

## POST /admin/fix-stuck-jobs

Corrigir jobs travados.

---

## GET /health

Health check.

---

## GET /

Info do servico.
