# API Reference - SE5 Make Video Clip

**Versao:** 2.0.0 | **Base URL:** http://localhost:8005 | **Auth:** `X-API-Key: se5-test-key-2026`

## Fluxo principal

1. Buscar shorts: `POST /download` com keyword
2. Montar video: `POST /make-video` com audio + shorts
3. Consultar: `GET /jobs/{job_id}` (polling)
4. Download: `GET /download/{job_id}`

---

## POST /download

Buscar e baixar shorts do YouTube.

**Request:** `multipart/form-data`

| Campo | Tipo | Obrigatório | Default | Descrição |
|-------|------|-------------|---------|-----------|
| `query` | string | Sim | — | Termo de busca no YouTube |
| `max_shorts` | int | Não | 10 | Máximo de shorts para baixar |

**Response 200:**
```json
{
  "status": "queued",
  "message": "Download iniciado",
  "job_id": "dl_abc123",
  "query": "cats being cute",
  "max_shorts": 10
}
```

**curl:**
```bash
curl -X POST "http://localhost:8005/download" \
  -H "X-API-Key: se5-test-key-2026" \
  -F "query=cats being cute" \
  -F "max_shorts=10"
```

---

## POST /make-video

Montar video a partir de audio + shorts.

**Request:** `multipart/form-data`

| Campo | Tipo | Obrigatório | Default | Descrição |
|-------|------|-------------|---------|-----------|
| `audio_file` | UploadFile | Sim | — | Arquivo de áudio (narração) |
| `max_shorts` | int | Não | 10 | Máximo de shorts para usar |
| `subtitle_language` | string | Não | "pt" | Idioma das legendas |
| `aspect_ratio` | string | Não | "9:16" | Proporção do vídeo final |
| `crop_position` | string | Não | "center" | Posição do corte |
| `hook_text` | string | Não | — | Texto de hook (opcional) |
| `burn_subtitles` | boolean | Não | true | Gravar legendas no vídeo |

**Response 200:**
```json
{
  "job_id": "vid_abc123",
  "status": "queued"
}
```

---

## GET /jobs

Listar jobs recentes.

---

## GET /jobs/{job_id}

Status detalhado do job com progresso.

---

## GET /download/{job_id}

Download do video final.

**Response 200:** `video/mp4` binario

---

## DELETE /jobs/{job_id}

Deletar job e arquivos associados.

---

## GET /cache/stats

Estatisticas do cache de shorts.

---

## GET /health

Health check.

---

## GET /

Info do servico com lista de endpoints.

---

## GET /metrics

Metricas Prometheus.

---

## GET /admin/stats

Estatisticas do sistema.

---

## POST /admin/cleanup

Limpar jobs antigos.
