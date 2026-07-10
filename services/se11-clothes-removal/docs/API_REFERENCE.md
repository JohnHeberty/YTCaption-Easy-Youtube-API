# API Reference — SE11 Clothes Removal

**Version:** 1.0.0  
**Base URL:** `http://localhost:8011`  
**Auth:** `X-API-Key` header  
**Job ID prefix:** `cr_`  
**Upstream:** SE10 (detection, port 8010) → SE8 (inpainting, port 8008)

---

## Fluxo Principal

```
1. POST /jobs          → Criar job (clothes/person)
2. GET  /jobs/{id}     → Polling de status (5-10s)
3. GET  /jobs/{id}/download → Baixar resultado (PNG)
```

Pipeline NSFW (produção):
```
1. POST /jobs/nsfw     → Criar job NSFW (5 tentativas, pose validation)
2. GET  /jobs/{id}     → Polling de status
3. GET  /jobs/{id}/download → Baixar resultado
```

---

## Modos de Processamento

| Modo | Descrição | Uso |
|------|-----------|-----|
| `clothes` | Detecta e remove peças de roupa específicas | **Default** |
| `person` | Remove toda a região do torso (preserva cabeça) | Remoção completa |
| `nsfw` | Pipeline produção: body-mask + 5 tentativas + pose validation + FaceID | **Produção** |
| `nsfw_test` | Alias para `nsfw` | Testes |

---

## Detectors

| Detector | Descrição | Recomendado |
|----------|-----------|-------------|
| `groundingdino` | Detecção por texto (default) | ✅ Geral |
| `segformer` | Segmentação pixel-level (18 classes de roupa) | Clothes mode |
| `ensemble` | Consenso multi-detector (GD+YOLO+BiRefNet+SegFormer) | Máxima precisão |

---

## Endpoints — Health

### `GET /`

Service info.

```bash
curl http://localhost:8011/
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `service` | `str` | Nome do serviço |
| `version` | `str` | Versão |
| `description` | `str` | Descrição |
| `endpoints` | `dict` | Endpoints disponíveis |

---

### `GET /health`

Liveness probe. NÃO verifica upstreams.

```bash
curl http://localhost:8011/health
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | `"ok"` |
| `service` | `str` | `"clothes-removal"` |
| `version` | `str` | Versão |

---

### `GET /health/deep`

Deep health check. Verifica conectividade com SE10 e SE8.

```bash
curl http://localhost:8011/health/deep
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | `ok` (todos reachable) ou `degraded` |
| `checks` | `dict` | Status por serviço upstream |

Cada check:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | `ok` / `unreachable` / `unknown` |
| `latency_ms` | `float\|null` | Latência em ms |

---

### `GET /ping`

```bash
curl http://localhost:8011/ping
```

```json
{"pong": true}
```

---

## Endpoints — Metadata

### `GET /modes`

Lista modos de processamento disponíveis.

```bash
curl http://localhost:8011/modes
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `modes` | `list[ModeInfo]` | Lista de modos |
| `default` | `str` | Modo default (`"clothes"`) |

`ModeInfo`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `name` | `str` | Nome do modo |
| `description` | `str` | Descrição |
| `recommended` | `bool` | É o recomendado? |

---

### `GET /detectors`

Lista engines de detecção disponíveis.

```bash
curl http://localhost:8011/detectors
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `detectors` | `list[DetectorInfo]` | Lista de detectors |
| `default` | `str` | Detector default (`"groundingdino"`) |

`DetectorInfo`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `name` | `str` | Nome do engine |
| `description` | `str` | Descrição |
| `recommended` | `bool` | É o recomendado? |

---

### `GET /config`

Configuração atual do serviço (sem segredos).

```bash
curl http://localhost:8011/config
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `service` | `str` | Nome do serviço |
| `version` | `str` | Versão |
| `supported_modes` | `list[str]` | Modos suportados |
| `supported_detectors` | `list[str]` | Detectors suportados |
| `output_dir` | `str` | Diretório de output |
| `upstream` | `dict` | URLs dos serviços upstream |

---

## Endpoints — Jobs

### `POST /jobs`

Cria job de remoção de roupa (clothes/person).

```bash
curl -X POST "http://localhost:8011/jobs" \
  -H "X-API-Key: se11-test-key-2026" \
  -F "file=@imagem.png" \
  -F "mode=clothes" \
  -F "detector=groundingdino"
```

**Content-Type:** `multipart/form-data`

| Campo | Tipo | Obrigatório | Default | Valores | Descrição |
|-------|------|-------------|---------|---------|-----------|
| `file` | `UploadFile` | ✅ | — | PNG, JPEG, WebP | Imagem AI-generated |
| `mode` | `enum` | ❌ | `clothes` | `clothes` / `person` | Modo de processamento |
| `classes` | `str\|null` | ❌ | `"spaghetti strap, camisole, top, blouse"` | — | Classes de roupa (separado por vírgula) |
| `prompt` | `str` | ❌ | `"bare skin, realistic skin texture, photorealistic"` | max 2000 | Prompt de inpainting |
| `negative_prompt` | `str` | ❌ | `"deformed, blurry, cartoon, low quality"` | max 2000 | Negative prompt |
| `box_threshold` | `float` | ❌ | `0.10` | 0.0–1.0 | Threshold de detecção SE10 |
| `text_threshold` | `float` | ❌ | `0.10` | 0.0–1.0 | Threshold de texto SE10 |
| `inpaint_strength` | `float` | ❌ | `0.70` | 0.0–1.0 | Força de denoise SE8 |
| `per_garment` | `bool` | ❌ | `false` | — | Inpaint cada peça separadamente |
| `webhook_url` | `str\|null` | ❌ | `null` | — | URL para notificação de conclusão |
| `detector` | `enum` | ❌ | `groundingdino` | `groundingdino` / `segformer` / `ensemble` | Engine de detecção |
| `face_restore` | `bool` | ❌ | `false` | — | Aplicar face restoration |
| `face_restore_model` | `str` | ❌ | `"CodeFormer"` | `CodeFormer` / `GFPGAN` | Modelo de face restoration |
| `face_restore_fidelity` | `float` | ❌ | `0.5` | 0.0–1.0 | Fidelidade CodeFormer |
| `upscale` | `bool` | ❌ | `true` | — | Aplicar upscale 4x ESRGAN |

**Response 201:**

```json
{
  "job_id": "cr_c6ce6b176755",
  "status": "queued",
  "message": "Job created successfully"
}
```

---

### `POST /jobs/nsfw`

Pipeline NSFW de produção. Qualidade fixa — sem parâmetros ajustáveis.

- 5 tentativas com strength progressivo (0.86→0.98)
- Modelo LustifyNSFW
- Pose validation (MediaPipe)
- FaceID preservation
- AI image detection (bloqueia fotos reais)

```bash
curl -X POST "http://localhost:8011/jobs/nsfw" \
  -H "X-API-Key: se11-test-key-2026" \
  -F "file=@imagem.png" \
  -F "detector=groundingdino"
```

| Campo | Tipo | Obrigatório | Default | Valores | Descrição |
|-------|------|-------------|---------|---------|-----------|
| `file` | `UploadFile` | ✅ | — | PNG, JPEG, WebP | Imagem AI-generated |
| `prompt` | `str` | ❌ | *(prompt NSFW longo)* | max 2000 | Prompt de inpainting |
| `negative_prompt` | `str` | ❌ | *(negative longo)* | max 2000 | Negative prompt |
| `box_threshold` | `float` | ❌ | `0.10` | 0.0–1.0 | Threshold de detecção |
| `text_threshold` | `float` | ❌ | `0.10` | 0.0–1.0 | Threshold de texto |
| `webhook_url` | `str\|null` | ❌ | `null` | — | Webhook URL |
| `detector` | `enum` | ❌ | `groundingdino` | `groundingdino` / `segformer` / `ensemble` | Engine de detecção |
| `face_restore` | `bool` | ❌ | `false` | — | Face restoration |
| `face_restore_model` | `str` | ❌ | `"CodeFormer"` | `CodeFormer` / `GFPGAN` | Modelo |
| `face_restore_fidelity` | `float` | ❌ | `0.5` | 0.0–1.0 | Fidelidade |
| `upscale` | `bool` | ❌ | `true` | — | Upscale ESRGAN |

**Parâmetros hardcoded internamente (NÃO expostos):**
- `mode = "nsfw"`
- `inpaint_strength = 0.86→0.98` (progressivo)
- `base_model = "lustifySDXLNSFW_v20-inpainting.safetensors"`
- `use_faceid = true`
- `faceid_weight = 0.8`
- `inpaint_mode = "invert_mask"`
- `face_blend_mode = "laplacian"`

---

### `POST /jobs/nsfw-test`

Pipeline NSFW experimental com controle total de parâmetros.

```bash
curl -X POST "http://localhost:8011/jobs/nsfw-test" \
  -H "X-API-Key: se11-test-key-2026" \
  -F "file=@imagem.png" \
  -F "inpaint_strength=0.90" \
  -F "use_faceid=true" \
  -F "faceid_weight=0.85" \
  -F "base_model=lustifySDXLNSFW_v20-inpainting.safetensors"
```

| Campo | Tipo | Obrigatório | Default | Valores | Descrição |
|-------|------|-------------|---------|---------|-----------|
| `file` | `UploadFile` | ✅ | — | PNG, JPEG, WebP | Imagem AI-generated |
| `classes` | `str\|null` | ❌ | `"spaghetti strap, camisole, top, blouse"` | — | Classes de roupa |
| `prompt` | `str` | ❌ | *(prompt NSFW)* | max 2000 | Prompt de inpainting |
| `negative_prompt` | `str` | ❌ | *(negative)* | max 2000 | Negative prompt |
| `box_threshold` | `float` | ❌ | `0.10` | 0.0–1.0 | Threshold de detecção |
| `text_threshold` | `float` | ❌ | `0.10` | 0.0–1.0 | Threshold de texto |
| `inpaint_strength` | `float` | ❌ | `1.0` | 0.0–1.0 | Força de denoise |
| `per_garment` | `bool` | ❌ | `false` | — | Inpaint por peça |
| `webhook_url` | `str\|null` | ❌ | `null` | — | Webhook URL |
| `detector` | `enum` | ❌ | `groundingdino` | `groundingdino` / `segformer` / `ensemble` | Engine de detecção |
| `inpaint_mode` | `enum` | ❌ | `invert_mask` | `body_mask` / `clothes_mask` / `invert_mask` | Estratégia de máscara |
| `use_faceid` | `bool` | ❌ | `true` | — | Habilitar IP-Adapter FaceID |
| `faceid_weight` | `float` | ❌ | `0.8` | 0.0–1.5 | Peso do FaceID (recomendado: 0.7-1.0) |
| `test_inpaint_strength` | `float` | ❌ | `0.86` | 0.0–1.0 | Strength base (5 tentativas a partir deste valor) |
| `base_model` | `str` | ❌ | `"lustifySDXLNSFW_v20-inpainting.safetensors"` | — | Checkpoint SDXL |
| `face_blend_mode` | `enum` | ❌ | `laplacian` | `laplacian` / `alpha` | Modo de blend face-corpo |
| `face_restore` | `bool` | ❌ | `false` | — | Face restoration |
| `face_restore_model` | `str` | ❌ | `"CodeFormer"` | `CodeFormer` / `GFPGAN` | Modelo |
| `face_restore_fidelity` | `float` | ❌ | `0.5` | 0.0–1.0 | Fidelidade |
| `upscale` | `bool` | ❌ | `true` | — | Upscale ESRGAN |

**Valores de `inpaint_mode`:**

| Valor | Descrição |
|-------|-----------|
| `body_mask` | Inpaint corpo inteiro menos cabeça (legado) |
| `clothes_mask` | Inpaint apenas regiões de roupa detectada |
| `invert_mask` | **Default.** Mantém rosto/corpo/fundo, regenera apenas roupa |

**Valores de `face_blend_mode`:**

| Valor | Descrição |
|-------|-----------|
| `laplacian` | Blend Laplacian pyramid multi-escala (transições suaves) |
| `alpha` | Blend alpha/feather simples (legado v23.4) |

**Modelos SDXL disponíveis (`base_model`):**

| Modelo | Descrição |
|--------|-----------|
| `lustifySDXLNSFW_v20-inpainting.safetensors` | **Default.** LustifyNSFW v2.0 inpainting |
| JuggernautXL | Alternativa genérica |

---

### `GET /jobs`

Lista todos os jobs.

```bash
curl "http://localhost:8011/jobs?limit=20&offset=0" \
  -H "X-API-Key: se11-test-key-2026"
```

| Query Param | Tipo | Obrigatório | Default | Constraints | Descrição |
|-------------|------|-------------|---------|-------------|-----------|
| `limit` | `int` | ❌ | `50` | 1–200 | Máximo de jobs |
| `offset` | `int` | ❌ | `0` | >= 0 | Paginação |

**Response 200:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `jobs` | `list[JobListItem]` | Jobs (mais recente primeiro) |
| `total` | `int` | Total de jobs |

`JobListItem`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_id` | `str` | ID do job |
| `status` | `enum` | Status atual |
| `progress` | `float` | Progresso (0–100) |
| `objects_detected` | `int\|null` | Objetos detectados |
| `created_at` | `str\|null` | Timestamp ISO 8601 |

---

### `GET /jobs/{job_id}`

Status detalhado do job. Poll a cada 5-10 segundos.

```bash
curl "http://localhost:8011/jobs/cr_c6ce6b176755" \
  -H "X-API-Key: se11-test-key-2026"
```

**Status codes:** 200, 404

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_id` | `str` | ID do job |
| `status` | `enum` | `queued` → `detecting` → `inpainting` → `completed` / `failed` |
| `progress` | `float` | Progresso (0–100) |
| `stages` | `dict` | Detalhes por estágio |
| `objects_detected` | `int\|null` | Objetos detectados pelo SE10 |
| `created_at` | `str` | Timestamp ISO 8601 |
| `error` | `str\|null` | Mensagem de erro (se falhou) |
| `result_path` | `str\|null` | Path interno do resultado |

`JobStageInfo` (cada estágio em `stages`):

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `enum` | `pending` / `processing` / `completed` / `failed` |
| `progress` | `float` | Progresso (0–100) |
| `error` | `str\|null` | Erro (se falhou) |
| `started_at` | `str\|null` | Timestamp ISO 8601 |
| `completed_at` | `str\|null` | Timestamp ISO 8601 |

**Status do job:**

| Status | Descrição |
|--------|-----------|
| `queued` | Na fila |
| `detecting` | SE10 detectando objetos |
| `inpainting` | SE8 gerando inpainting |
| `completed` | Concluído |
| `failed` | Falhou |

---

### `DELETE /jobs/{job_id}`

Deleta job e arquivos. Irreversível.

```bash
curl -X DELETE "http://localhost:8011/jobs/cr_c6ce6b176755" \
  -H "X-API-Key: se11-test-key-2026"
```

**Status codes:** 200, 404

```json
{
  "message": "Job deleted successfully",
  "job_id": "cr_c6ce6b176755"
}
```

---

### `GET /jobs/{job_id}/download`

Baixa imagem resultado (PNG).

```bash
curl "http://localhost:8011/jobs/cr_c6ce6b176755/download" \
  -H "X-API-Key: se11-test-key-2026" \
  -o resultado.png
```

**Status codes:** 200 (PNG), 400 (job não completou), 404 (job/arquivo não encontrado)

Response: Binary PNG com `Content-Disposition: attachment; filename="{job_id}_result.png"`

---

## Endpoints — Admin

### `GET /admin/stats`

Estatísticas do sistema.

```bash
curl "http://localhost:8011/admin/stats" \
  -H "X-API-Key: se11-test-key-2026"
```

| Campo | Tipo | Exemplo |
|-------|------|---------|
| `jobs` | `dict` | `{"total": 38, "by_status": {"completed": 30, "failed": 5}}` |
| `storage` | `dict` | `{"output_dir": "./data/outputs", "total_files": 150, "total_size_mb": 219.5}` |

---

### `POST /admin/cleanup`

Remove jobs concluídos/falhados e seus arquivos.

```bash
curl -X POST "http://localhost:8011/admin/cleanup" \
  -H "X-API-Key: se11-test-key-2026"
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cleaned` | `int` | Jobs removidos |

---

## Error Response

Todos os endpoints retornam este formato em caso de erro:

```json
{
  "error": "NOT_FOUND",
  "message": "Job not found",
  "details": null
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `error` | `str` | ✅ | Tipo do erro |
| `message` | `str` | ✅ | Mensagem legível |
| `details` | `dict\|null` | ❌ | Detalhes adicionais |

---

## Variáveis de Ambiente

### SE11-específicas

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `SE10_URL` | `str` | `http://localhost:8010` | URL do SE10 |
| `SE10_API_KEY` | `str` | `se10-test-key-2026` | API key do SE10 |
| `SE10_TIMEOUT` | `int` | `60` | Timeout SE10 (segundos) |
| `SE8_URL` | `str` | `http://localhost:8008` | URL do SE8 |
| `SE8_API_KEY` | `str` | `se8-test-key-2026` | API key do SE8 |
| `SE8_TIMEOUT` | `int` | `300` | Timeout SE8 (segundos) |
| `SE10_POLL_INTERVAL` | `int` | `3` | Polling interval SE10 (s) |
| `SE8_POLL_INTERVAL` | `int` | `5` | Polling interval SE8 (s) |
| `MAX_CONCURRENT_JOBS` | `int` | `2` | Jobs concorrentes |
| `AI_DETECTION_ENABLED` | `bool` | `true` | Bloquear fotos reais (NSFW) |

### Herdadas de BaseServiceSettings

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| `APP_NAME` | `str` | *(obrigatório)* | Nome da aplicação |
| `REDIS_URL` | `str` | *(obrigatório)* | URL do Redis |
| `API_KEY` | `str\|null` | `null` | API key de autenticação |
| `PORT` | `int` | `8011` | Porta do servidor |
| `OUTPUT_DIR` | `str` | `./data/outputs` | Diretório de output |
| `LOG_LEVEL` | `str` | `INFO` | Nível de log |
| `MAX_FILE_SIZE_MB` | `int` | `500` | Tamanho máximo de upload (MB) |
| `JOB_TIMEOUT_MINUTES` | `int` | `60` | Timeout do job (minutos) |

---

## Exemplo Completo — E2E

```bash
# 1. Criar job
curl -X POST "http://localhost:8011/jobs" \
  -H "X-API-Key: se11-test-key-2026" \
  -F "file=@foto.png" \
  -F "mode=clothes" \
  -F "detector=segformer" \
  -F "face_restore=true"

# Response: {"job_id": "cr_abc123", "status": "queued", "message": "..."}

# 2. Poll status
while true; do
  STATUS=$(curl -s "http://localhost:8011/jobs/cr_abc123" \
    -H "X-API-Key: se11-test-key-2026" | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] && break
  sleep 5
done

# 3. Download resultado
curl "http://localhost:8011/jobs/cr_abc123/download" \
  -H "X-API-Key: se11-test-key-2026" \
  -o resultado.png
```
