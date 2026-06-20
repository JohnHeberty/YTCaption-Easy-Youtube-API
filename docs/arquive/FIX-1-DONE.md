# AUDITORIA QA SENIOR — SE10 Clothes Segmentation

**Arquivos auditados:** 49 | **Testes:** 47 pass, 1 skipped, 0 fail | **Linhas de código:** ~800

---

## P0 — BUGS QUEBRA FUNCIONALIDADE

| # | Bug | Arquivo:Linha | Evidência |
|---|-----|---------------|-----------|
| **P0.1** | **Route collision: `/jobs/stats` INEXISTENTE** | `jobs.py:43` vs `jobs.py:93` | `GET /jobs/stats` → 404 `"Job stats not found"`. O `/{job_id}` registrado ANTES captura `"stats"` como job_id. Endpoint `/stats` é **morto**. |
| **P0.2** | **`docker-compose.yml` env_file path errado** | `docker-compose.yml:19` | `env_file: - .env` resolve para `docker/.env` (não existe). Todos os outros serviços usam `../.env`. **Docker não carrega variáveis.** |
| **P0.3** | **Docker network name inconsistente** | `docker-compose.yml:31,37` | Usa `ytcaption-net` mas se1/se4/se9 usam `ytcaption-network`. Containers ficam em **redes diferentes** e não se comunicam. |

---

## P1 — PROBLEMAS SIGNIFICATIVOS

| # | Bug | Arquivo:Linha | Impacto |
|---|-----|---------------|---------|
| **P1.1** | **Zero CORS middleware** | `main.py:60` | `create_service_app()` sem `cors_options` e `settings` sem config `cors`. **Browser clients não conseguem chamar a API.** |
| **P1.2** | **`deps.py` é dead code** | `deps.py` inteiro | `require_segmentor()` definido mas **nunca importado**. `segment.py` faz check inline. |
| **P1.3** | **Acessa atributo privado `seg._device`** | `health.py:22,33,55` | Health routes expõem `str(seg._device)` — atributo privado. Deveria ser property pública. |
| **P1.4** | **Sem validação de conteúdo do arquivo** | `segment.py:42` | Só valida extensão + tamanho. Arquivo `.jpg` que não é imagem causa 500 não tratado no `Image.open()`. |
| **P1.5** | **`_get_job_manager()` não é thread-safe** | `jobs.py:22` | Variável global `_job_manager` pode ser escrita por múltiplas threads simultaneamente na primeira requisição. Race condition. |
| **P1.6** | **`.env` usa `${DIVISOR}` — example não tem DIVISOR** | `.env.example` | Fresh install sem DIVISOR definido: `PORT=80${DIVISOR}` falha na validação pydantic. |

---

## P2 — QUALIDADE / MANTENIBILIDADE

| # | Issue | Arquivo:Linha |
|---|-------|---------------|
| **P2.1** | Jobs endpoints sem `response_model` — OpenAPI docs genéricos | `jobs.py` |
| **P2.2** | Makefile usa `python` em vez de `python3` | `Makefile:58` |
| **P2.3** | `test_segmentor.py` sem `@pytest.mark.unit` — `pytest -m unit` não inclui | `test_segmentor.py:19` |
| **P2.4** | `Dockerfile.gpu` CMD é uvicorn, não Celery (plan diz GPU worker) | `Dockerfile.gpu:54` |
| **P2.5** | `_start_time` é module-level, não server start time | `health.py:13` |
| **P2.6** | `.env.example` tem `SE10_API_KEY=se10-test-key-2026` — example não deveria ter key real | `.env.example:27` |
| **P2.7** | `CHECKPOINT_SAM2_LARGE` definido em constants mas nunca usado | `constants.py:37` |

---

## P3 — ESTILO / MENOR

| # | Issue | Arquivo |
|---|-------|---------|
| **P3.1** | `pyproject.toml` coverage omit `tests/*` redundante (source já é `["app"]`) | `pyproject.toml:12` |
| **P3.2** | `Dockerfile` COPY shared/ + volume mount sobrescreve — COPY redundante | `Dockerfile:12-13` |
| **P3.3** | `app/domain/enums.py` não criado (plan pedia) — ClothingClass em constants.py | OK, mas diverge do plan |

---

## GAPS vs PLAN (`NEW-PLAN.md`)

| Plan Item | Implementado? | Nota |
|-----------|---------------|------|
| `app/domain/enums.py` | ❌ | ClothingClass ficou em constants.py |
| `app/services/checkpoint.py` | ❌ | Checkpoint checking inline no lifespan |
| `app/infrastructure/model_loader.py` | ❌ | Lazy loading inline no segmentor |
| `tests/api/test_auth.py` | ❌ | Auth testado em test_segment.py |
| Dockerfile.gpu como Celery worker | ❌ | Roda uvicorn (não Celery) |

---

## Evidências Testadas

```
# Route collision confirmado:
GET /jobs/stats → 404 {"error": "JOB_NOT_FOUND", "message": "Job stats not found"}
GET /jobs/abc123 → 404 {"error": "JOB_NOT_FOUND", "message": "Job abc123 not found"}

# CORS confirmado:
OPTIONS /v1/segment → 405 (no ACAO headers, no CORS middleware)

# DIVISOR expansion test:
PORT=80${DIVISOR} via os.environ → ValidationError: "unable to parse string as an integer"
(via python-dotenv interpolation: funciona se DIVISOR definido no mesmo .env)

# Network name mismatch:
se10: ytcaption-net | se1/se4/se9: ytcaption-network → containers em redes diferentes
```
