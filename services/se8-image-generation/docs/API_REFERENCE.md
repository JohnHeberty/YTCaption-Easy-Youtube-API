# API Reference - SE8 Image Generation

**Versao:** 1.0.0 | **Base URL:** http://localhost:8008 | **Auth:** `X-API-Key: se8-test-key-2026`

## Fluxo principal

1. Gerar imagem: `POST /v1/generation/text-to-image` com prompt
2. Consultar: `GET /v1/generation/query-job?job_id={id}` (polling)
3. Download: `GET /files/{date}/{filename}`

---

## POST /v1/generation/text-to-image

Gerar imagem a partir de texto (sincrono).

**Request:**
```json
{
  "prompt": "A beautiful sunset over the ocean, cinematic lighting",
  "negative_prompt": "blurry, low quality",
  "width": 1024,
  "height": 1024,
  "steps": 30,
  "performance": "Quality",
  "seed": null
}
```

**Response 200:**
```json
[
  {
    "base64": null,
    "url": "/files/2026-06-19/abc123.png",
    "seed": "12345678",
    "finish_reason": "SUCCESS"
  }
]
```

**curl:**
```bash
curl -X POST "http://localhost:8008/v1/generation/text-to-image" \
  -H "X-API-Key: se8-test-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A beautiful sunset", "width": 1024, "height": 1024}'
```

---

## GET /v1/generation/query-job

Consultar status de um job de geracao.

**Query:** `job_id` (obrigatorio)

---

## GET /v1/generation/job-queue

Verificar tamanho da fila de jobs.

---

## GET /v1/generation/job-history

Historico de jobs de um usuario.

**Params:** `job_id` (filtro por job especifico), `page` (pagina, default 1), `page_size` (itens por pagina, default 20)

---

## GET /v1/generation/outputs

Listar outputs gerados.

---

## GET /v1/engines/all-models

Listar todos os modelos disponiveis.

---

## GET /v1/engines/styles

Listar estilos disponiveis.

---

## GET /v1/engines/styles-detail

Detalhes dos estilos.

---

## GET /v1/engines/cleanup

Limpar VRAM/memoria (descarrega modelo GPU).

---

## GET /v1/engines/clean_vram

Limpar VRAM explicitamente.

---

## POST /v1/generation/image-upscale-vary

Upscale ou variacao de imagem existente.

---

## POST /v1/generation/image-inpaint-outpaint

Inpaint/outpaint de imagem existente.

---

## POST /v1/generation/image-prompt

Gerar imagem com prompt customizado.

---

## POST /v1/generation/image-enhance

Melhorar qualidade de imagem.

---

## POST /v2/generation/text-to-image-with-ip

Text-to-image com IP adapter.

---

## POST /v2/generation/image-upscale-vary

V2 upscale/vary de imagem.

---

## POST /v2/generation/image-inpaint-outpaint

V2 inpaint/outpaint de imagem.

---

## POST /v2/generation/image-prompt

V2 gerar imagem com prompt customizado.

---

## POST /v2/generation/image-enhance

V2 melhorar qualidade de imagem.

---

## POST /v1/tools/describe-image

Descrever imagem com IA.

---

## POST /v1/tools/generate_mask

Gerar mascara para inpainting.

---

## GET /files/{date}/{file_name}

Download de um arquivo gerado.

**Response 200:** `image/png` binario

---

## GET /health

Health check (Redis, GPU, modelo).

---

## GET /health/deep

Health check profundo.

---

## GET /ping

Ping simples.

---

## GET /

Info do servico.

---

## GET /admin/stats

Estatisticas do sistema.

---

## POST /admin/cleanup

Limpar jobs antigos.
