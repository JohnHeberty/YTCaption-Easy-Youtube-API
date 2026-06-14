# JobStateUpdater Extraction — processor.py SRP (MELHORE 1.2)

## Problema resolvido
`processor.py` continha lógica espalhada de persistência de estado do job (~30 linhas duplicadas em blocos try/except/finally), com `_safe_update_job()` repetindo timestamp injection, processing-time calculation e error suppression. Violação clara de SRP: o processador não deveria saber como persistir jobs.

## Arquivos alterados
- **Criado:** `app/shared/job_state_updater.py` (119 linhas) — classe `JobStateUpdater` com métodos: `safe_update()`, `mark_processing()`, `set_progress()`, `mark_completed()` e `mark_failed()`. Encapsula toda a lógica de persistência segura, timestamp injection (`updated_at`, `started_at`, `completed_at`) e cálculo de processing-time.
- **Modificado:** `app/services/processor.py` (875 linhas) — removido `_safe_update_job()` method (~10 lines). Call sites atualizados: mark_processing → `self.state.mark_processing()`, progress updates → `self.state.set_progress()`, completion → `self.state.mark_completed(...)`, failure → `self.state.mark_failed(job, str(e))`.

## Como validar
```bash
# AST parse local
python3 -c "import ast; ast.parse(open('services/se4-audio-transcriber/app/shared/job_state_updater.py').read())"
python3 -c "import ast; ast.parse(open('services/se4-audio-transcriber/app/services/processor.py').read())"

# Import no container Docker
docker exec ytcaption-se4-audio-transcriber-api python3 -c "from app.shared.job_state_updater import JobStateUpdater; print('OK')"
```

## Riscos e observações
- `transcription_service.py` ainda tem inline job state updates (~10 call sites) que podem ser migrados para usar `JobStateUpdater`.
- `_now_brazil()` helper em `job_state_updater.py` é uma duplicação do `now_brazil()` já existente no processor — considerar consolidar.
