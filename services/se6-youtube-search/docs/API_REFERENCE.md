# API Reference - SE6 YouTube Search

**Versao:** 1.0.0 | **Base URL:** http://localhost:8006 | **Auth:** `X-API-Key: se6-test-key-2026`

## Fluxo principal

1. Buscar videos: `GET /search/videos?query=...`
2. Obter info: `GET /search/video-info?video_id=...`
3. Consultar jobs: `GET /jobs/{job_id}`

---

## GET /search/videos

Buscar videos no YouTube.

**Request:** Query strings na URL.

| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| query | string | sim | Palavra-chave de busca |
| max_results | int | nao | Limite de resultados (default: 10) |

**Response 200:**
```json
{
  "results": [
    {
      "video_id": "xxxxx",
      "title": "Cats Being Cute Compilation",
      "channel": "CatLovers",
      "duration": 45,
      "view_count": 1200000,
      "url": "https://www.youtube.com/watch?v=xxxxx"
    }
  ],
  "total": 8
}
```

**curl:**
```bash
curl "http://localhost:8006/search/videos?query=cats%20being%20cute&max_results=10" \
  -H "X-API-Key: se6-test-key-2026"
```

---

## GET /search/shorts

Buscar YouTube Shorts (<=60s).

**Request:** Query strings na URL (mesmos params de `/search/videos`).

| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| query | string | sim | Palavra-chave de busca |
| max_results | int | nao | Limite de resultados (default: 10) |

**curl:**
```bash
curl "http://localhost:8006/search/shorts?query=cats&max_results=10" \
  -H "X-API-Key: se6-test-key-2026"
```

---

## GET /search/video-info

Obter informacoes detalhadas de um video.

**Request:** Query string na URL.

| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| video_id | string | sim | ID do video ou URL completa do YouTube |

**curl:**
```bash
curl "http://localhost:8006/search/video-info?video_id=xxxxx" \
  -H "X-API-Key: se6-test-key-2026"
```

---

## GET /search/channel-info

Obter informacoes de um canal.

**Request:** Query string na URL.

| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| channel_id | string | sim | ID do canal |

**curl:**
```bash
curl "http://localhost:8006/search/channel-info?channel_id=UCxxxxx" \
  -H "X-API-Key: se6-test-key-2026"
```

---

## GET /search/playlist-info

Obter informacoes de uma playlist.

**Request:** Query string na URL.

| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| playlist_id | string | sim | ID da playlist |

**curl:**
```bash
curl "http://localhost:8006/search/playlist-info?playlist_id=PLxxxxx" \
  -H "X-API-Key: se6-test-key-2026"
```

---

## GET /search/related-videos

Buscar videos relacionados.

**Request:** Query strings na URL.

| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| video_id | string | sim | ID do video de referencia |
| max_results | int | nao | Limite de resultados (default: 10) |

**curl:**
```bash
curl "http://localhost:8006/search/related-videos?video_id=xxxxx&max_results=10" \
  -H "X-API-Key: se6-test-key-2026"
```

---

## GET /jobs

Listar jobs de busca recentes.

---

## GET /jobs/{job_id}

Status do job de busca.

---

## GET /jobs/{job_id}/wait

Aguardar job completar (bloqueia ate finalizar ou timeout).

---

## GET /jobs/{job_id}/download

Baixar resultado do job (video/audio).

---

## DELETE /jobs/{job_id}

Deletar job de busca.

---

## GET /admin/stats

Estatisticas do sistema.

---

## GET /admin/queue

Info da fila Celery.

---

## GET /admin/metrics

Metricas detalhadas do sistema.

---

## POST /admin/cleanup

Limpar jobs antigos.

---

## GET /health

Health check (Redis, disco, Celery, ytbpy).

---

## GET /

Info do servico.
