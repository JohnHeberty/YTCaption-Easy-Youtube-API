# PLANO: Ativar DDD Path do SE5

**Status:** Pendente
**Criado:** 2026-07-08
**Esforço estimado:** 7-8h

---

## Problema Fundamental

O DDD path e o legacy implementam flows de negócio diferentes:
- **Legacy (produção):** Vídeos pré-aprovados em `data/approved/videos/`
- **DDD (código):** YouTube Search API → download → OCR

**Solução:** Criar `LoadApprovedVideosStage` + alinhar stages com legacy.

---

## Fase 1 — Config (~5 min)

| Arquivo | Mudança |
|---------|---------|
| `app/core/config.py` | Adicionar `use_domain_driven_architecture: bool = False` |

---

## Fase 2 — Novos Stages (~2h)

| Arquivo | Mudança |
|---------|---------|
| `app/domain/stages/load_approved_stage.py` | **NOVO** — Lê `data/approved/videos/*.mp4`, obtém `video_info`, popula `context.downloaded_shorts` |
| `app/domain/stages/validate_av_sync_stage.py` | **NOVO** — Porta `_validate_av_sync()` do legacy |
| `app/shared/domain_integration.py` | Atualizar `_create_stages()`: substituir FetchShorts+DownloadShorts por LoadApproved, inserir ValidateAVSync entre FinalComposition e TrimVideo |

---

## Fase 3 — Corrigir Stages (~2h)

| # | Stage | Arquivo | Mudança |
|---|-------|---------|---------|
| 3.1 | AnalyzeAudio | `app/domain/stages/analyze_audio_stage.py` | Limites: 5s min, 3600s max (era 10s-300s) |
| 3.2 | SelectShorts | `app/domain/stages/select_shorts_stage.py` | Warning quando `total_duration < audio_duration` |
| 3.3 | AssembleVideo | `app/domain/stages/assemble_video_stage.py` | Validação pós-concat `CONCAT_TOLERANCE=2.0` |
| 3.4 | GenerateSubtitles | `app/domain/stages/generate_subtitles_stage.py` | Retry 5x com backoff (max 300s) |
| 3.5 | GenerateSubtitles | `app/domain/stages/generate_subtitles_stage.py` | Usar `segments_to_weighted_word_cues()` |
| 3.6 | FinalComposition | `app/domain/stages/final_composition_stage.py` | Passar `subtitle_style` real (não always "dynamic") |
| 3.7 | TrimVideo | `app/domain/stages/trim_video_stage.py` | Validação pós-trim `FINAL_TOLERANCE=2.0` + audio-vs-video |
| 3.8 | DomainJobProcessor | `app/shared/domain_integration.py` | Cleanup: stale validations + orphaned files |

---

## Fase 4 — Observabilidade (~1h)

| # | Onde | Mudança |
|---|------|---------|
| 4.1 | 8 stages | `save_checkpoint()` em cada boundary |
| 4.2 | `domain_integration.py` | `update_job_status()` por stage no Redis |
| 4.3 | `domain_integration.py` | `simple_metrics` tracking (completed/failed) |

---

## Fase 5 — Testes (~2h)

| Arquivo | O que testa |
|---------|-------------|
| `tests/unit/domain/stages/test_load_approved.py` | Leitura de arquivos aprovados |
| `tests/unit/domain/stages/test_all_stages.py` | Funcionais com mocks para cada stage |
| `tests/integration/domain/test_full_chain.py` | Chain completo 8 stages |
| `tests/integration/domain/test_saga_compensation.py` | Rollback em falha de stage |

---

## Fase 6 — Ativação (~5 min)

| Arquivo | Mudança |
|---------|---------|
| `app/core/config.py` | `use_domain_driven_architecture: bool = True` + env var override |

---

## Decisões Tomadas

- **Audio limits:** Manter legacy (5s-3600s)
- **Word extraction:** Weighted (legacy `segments_to_weighted_word_cues()`)
- **Checkpoints:** Adicionar ao DDD
- **SRT:** Usar método legacy (`write_srt_from_word_cues()`)

## Ordem de Execução

```
Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6
```

## Fallback

Se DDD falhar, setar `USE_DOMAIN_DRIVEN_ARCHITECTURE=false` na env vars para voltar ao legacy.
