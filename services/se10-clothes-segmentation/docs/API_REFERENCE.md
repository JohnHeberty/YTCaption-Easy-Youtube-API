# API Reference - SE10 Clothes Segmentation

**Versao:** 1.0.0 | **Base URL:** http://localhost:8010 | **Auth:** `X-API-Key: se10-test-key-2026`

## Fluxo principal

1. Enviar imagem: `POST /v1/segment`
2. Receber resultado com mascaras e bounding boxes

---

## POST /v1/segment

Segmentar roupas em uma imagem.

**Request:** `multipart/form-data`

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `file` | File | Sim | Imagem (JPG, JPEG, PNG) |
| `classes` | str | Nao | Classes separadas por virgula (ex: "shirt,pants,dress") |
| `box_threshold` | float | Nao | Threshold de confianca da deteccao (default: 0.10) |
| `text_threshold` | float | Nao | Threshold de matching de texto (default: 0.10) |

**Response 200:**
```json
{
  "success": true,
  "objects": [
    {
      "class": "shirt",
      "confidence": 0.85,
      "bbox": [120, 50, 300, 200],
      "area_pct": 0.15
    }
  ],
  "masks_base64": ["base64_encoded_mask..."],
  "processing_time_ms": 1250
}
```

**Response 400:** Arquivo invalido
```json
{
  "success": false,
  "message": "Invalid file type: .gif. Allowed: .jpg, .jpeg, .png",
  "error": "INVALID_FILE_TYPE"
}
```

**Classes disponiveis:** hat, sunglasses, shirt, blouse, jacket, sweater, blazer, cardigan, handbag, skirt, pants, dress, shoes, boots, slippers

**curl example:**
```bash
curl -X POST http://localhost:8010/v1/segment \
  -H "X-API-Key: se10-test-key-2026" \
  -F "file=@foto.jpg" \
  -F "classes=shirt,pants,shoes"
```

---

## GET /health

**Response 200:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "device": "cuda",
  "version": "1.0.0"
}
```

---

## GET /health/deep

**Response 200:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "device": "cuda",
  "version": "1.0.0",
  "checkpoints": {
    "groundingdino_swint_ogc.pth": {"exists": true, "size_mb": 694.0},
    "sam2_hiera_tiny.pt": {"exists": true, "size_mb": 38.0},
    "sam2_hiera_large.pt": {"exists": false, "size_mb": 0}
  },
  "uptime_s": 3600.0
}
```

---

## GET /ping

**Response 200:** `{"pong": true}`

---

## GET /jobs

Listar jobs.

**Query params:** `status` (filtro), `limit` (default 50), `offset` (default 0)

**Response 200:**
```json
{
  "jobs": [],
  "total": 0,
  "page": 1,
  "page_size": 50
}
```

---

## GET /jobs/stats

**Response 200:** Estatisticas de jobs por status.

---

## GET /jobs/{job_id}

**Response 200:** Detalhe do job.
**Response 404:** Job nao encontrado.
**Response 410:** Job expirado.

---

## DELETE /jobs/{job_id}

**Response 200:** `{"message": "Job ... deleted", "job_id": "..."}`
**Response 404:** Job nao encontrado.
