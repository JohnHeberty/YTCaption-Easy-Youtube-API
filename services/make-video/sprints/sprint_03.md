# Sprint Pack 03/12 - Validação de Integridade de Vídeo

**Escopo deste pack:** Implementar `validate_video_integrity()` com ffprobe para metadados e decode real de frame para garantir que vídeos baixados não estão corrompidos/truncados. Inclui timeouts, logs estruturados, e fail-close com overfetch.

## Índice

- [S-025: Implementar validação ffprobe de metadados](#s-025)
- [S-026: Adicionar decode real de 1 frame](#s-026)
- [S-027: Implementar timeout de 5s na validação](#s-027)
- [S-028: Adicionar logs estruturados na validação](#s-028)
- [S-029: Implementar fail-close (descartar se inválido)](#s-029)
- [S-030: Integrar validação no download_short](#s-030)
- [S-031: Adicionar métrica validation_time_ms](#s-031)
- [S-032: Criar testes com vídeo corrompido](#s-032)
- [S-033: Criar testes com vídeo truncado](#s-033)
- [S-034: Criar testes com vídeo válido](#s-034)
- [S-035: Validar timeout funciona corretamente](#s-035)
- [S-036: Documentar validação no README](#s-036)

---

<a name="s-025"></a>
## S-025: Implementar validação ffprobe de metadados

**Objetivo:** Criar função que usa ffprobe para verificar metadados básicos: arquivo existe, não está vazio, tem streams de vídeo, duração >0.

**Escopo (IN/OUT):**
- **IN:** Função `validate_video_integrity()` com ffprobe básico
- **OUT:** Não fazer decode de frame ainda (próxima sprint)

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Adicionar imports: `import os`, `import logging`, `import asyncio`, `import subprocess`, `import json`
- Criar `logger = logging.getLogger(__name__)`
- Criar função `async def validate_video_integrity(video_path: str, timeout: int = 5) -> bool:`
- Validar: `os.path.exists(video_path)` e `os.path.getsize(video_path) > 0`
- Executar ffprobe: `ffprobe -v error -hide_banner -nostdin -select_streams v:0 -show_entries stream=duration,codec_name,width,height -of json {video_path}`
- Usar `asyncio.create_subprocess_exec()` para execução assíncrona
- Parsear JSON retornado
- Validar: `streams` não vazio, `duration > 0`
- Retornar `True` se válido, `False` caso contrário

**Critérios de Aceite / Definition of Done:**
- [ ] Função criada e assíncrona
- [ ] ffprobe executado corretamente
- [ ] Retorna False se arquivo não existe
- [ ] Retorna False se duração <= 0
- [ ] Retorna False se sem stream de vídeo

**Testes:**
- Unit: `tests/test_video_validator.py::test_valid_video_passes()`
- Unit: `tests/test_video_validator.py::test_nonexistent_file_fails()`
- Unit: `tests/test_video_validator.py::test_empty_file_fails()`

**Observabilidade:**
- Log: `logger.info("video_integrity_check", video_path="...", has_video_stream=True/False, duration_sec=...)`

**Riscos/Rollback:**
- Risco: ffprobe não instalado
- Rollback: Adicionar validação de dependência no S-009

**Dependências:** S-001, S-003 (logging)

---

<a name="s-026"></a>
## S-026: Adicionar decode real de 1 frame

**Objetivo:** Adicionar validação crítica que tenta decodificar 1 frame do vídeo para pegar arquivos corrompidos/truncados que ffprobe não detecta.

**Escopo (IN/OUT):**
- **IN:** Adicionar comando ffmpeg que decodifica 1 frame
- **OUT:** Não salvar frame, apenas testar decode

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Após validação ffprobe em `validate_video_integrity()`, adicionar:
- Comando: `ffmpeg -v error -hide_banner -nostdin -i {video_path} -frames:v 1 -f null -`
- Executar com `asyncio.create_subprocess_exec()`
- Capturar stderr
- Se `returncode != 0`, retornar `False`
- Se stderr contém "error" ou "corrupt", retornar `False`
- Adicionar comentário: `# CRÍTICO: decode real pega MP4 truncado/corrompido que ffprobe não detecta`

**Critérios de Aceite / Definition of Done:**
- [ ] Decode de 1 frame implementado
- [ ] Retorna False se decode falha
- [ ] Stderr capturado e logado
- [ ] Comentário explicativo adicionado

**Testes:**
- Unit: `tests/test_video_validator.py::test_corrupted_video_fails_decode()`
- Unit: `tests/test_video_validator.py::test_truncated_video_fails_decode()`

**Observabilidade:**
- Log: `logger.warning("video_decode_failed", video_path="...", returncode=..., stderr_preview="...")`

**Riscos/Rollback:**
- Risco: Decode lento para vídeos grandes
- Rollback: Apenas 1 frame é rápido (<1s), aceitável

**Dependências:** S-025

---

<a name="s-027"></a>
## S-027: Implementar timeout de 5s na validação

**Objetivo:** Adicionar timeout de 5s em ambas as etapas (ffprobe e decode) para evitar travamento em vídeos problemáticos.

**Escopo (IN/OUT):**
- **IN:** Envolver ffprobe e ffmpeg com `asyncio.wait_for(..., timeout=5)`
- **OUT:** Não modificar lógica de validação

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Envolver `proc.communicate()` do ffprobe com: `stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)`
- Envolver `proc_decode.communicate()` do ffmpeg com mesmo timeout
- Adicionar `try/except asyncio.TimeoutError`
- Em except, logar e retornar `False`

**Critérios de Aceite / Definition of Done:**
- [ ] Timeout de 5s aplicado em ffprobe
- [ ] Timeout de 5s aplicado em ffmpeg decode
- [ ] TimeoutError capturado e logado
- [ ] Função retorna False em caso de timeout

**Testes:**
- Unit: `tests/test_video_validator.py::test_timeout_triggers_on_slow_file()`
- Mock: Simular processo que demora >5s

**Observabilidade:**
- Log: `logger.error("video_validation_timeout", video_path="...", timeout_sec=5)`
- Métrica: `counter("video_validation_timeouts_total")`

**Riscos/Rollback:**
- Risco: Timeout muito curto descarta vídeos grandes válidos
- Rollback: Aumentar timeout para 10s via config

**Dependências:** S-026, S-006 (timeout utils)

---

<a name="s-028"></a>
## S-028: Adicionar logs estruturados na validação

**Objetivo:** Adicionar logs estruturados em cada etapa da validação para debugging e observabilidade.

**Escopo (IN/OUT):**
- **IN:** Logs no início, durante, e ao final da validação
- **OUT:** Não adicionar métricas ainda (próxima sprint)

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- No início de `validate_video_integrity()`: `logger.info("video_validation_started", video_path=video_path)`
- Após ffprobe: `logger.debug("ffprobe_completed", duration=duration, codec=codec_name, width=width, height=height)`
- Após decode: `logger.debug("decode_completed", success=True/False)`
- Ao retornar False: `logger.warning("video_validation_failed", video_path=video_path, reason="...")`
- Ao retornar True: `logger.info("video_validation_passed", video_path=video_path)`

**Critérios de Aceite / Definition of Done:**
- [ ] 5 logs adicionados (start, ffprobe, decode, fail, pass)
- [ ] Formato estruturado (JSON)
- [ ] Campo `reason` indica por que falhou
- [ ] Logs visíveis em teste manual

**Testes:**
- Unit: `tests/test_video_validator.py::test_logs_generated(caplog)`
- Assert: verificar que caplog contém "video_validation_started"

**Observabilidade:**
- Logs: Todos os logs listados acima

**Riscos/Rollback:**
- Risco: Logs muito verbosos
- Rollback: Mudar nível para DEBUG

**Dependências:** S-027, S-003 (logging estruturado)

---

<a name="s-029"></a>
## S-029: Implementar fail-close (descartar se inválido)

**Objetivo:** Garantir que vídeos que falham na validação sejam descartados (removidos do filesystem) e não adicionados ao cache.

**Escopo (IN/OUT):**
- **IN:** Remover arquivo inválido, NÃO adicionar ao cache
- **OUT:** Não implementar overfetch ainda (sprint 08)

**Arquivos tocados:**
- `services/make-video/app/celery_tasks.py` (preparação para integração)

**Mudanças exatas:**
- Criar lógica de descarte (será integrada em S-030):
- `if not await validate_video_integrity(output_path): os.remove(output_path); return None`
- Adicionar comentário: `# Fail-close: descarta vídeo inválido + overfetch substituirá (implementado em S-030)`

**Critérios de Aceite / Definition of Done:**
- [ ] Vídeo inválido é removido do filesystem
- [ ] Função retorna None (indica falha)
- [ ] Comentário explicativo adicionado
- [ ] Não adiciona ao cache se None

**Testes:**
- Integration: `tests/test_celery_tasks.py::test_invalid_video_not_cached()`

**Observabilidade:**
- Log: `logger.warning("video_discarded", video_path="...", reason="integrity_validation_failed")`
- Métrica: `counter("videos_discarded_total", tags={"reason": "integrity"})`

**Riscos/Rollback:**
- Risco: Descartar vídeos válidos por engano (falso negativo)
- Rollback: Desabilitar validação via flag ENABLE_VIDEO_VALIDATION=false

**Dependências:** S-028

---

<a name="s-030"></a>
## S-030: Integrar validação no download_short

**Objetivo:** Integrar `validate_video_integrity()` no fluxo de download de vídeos, após download e antes de adicionar ao cache.

**Escopo (IN/OUT):**
- **IN:** Chamar validação, descartar se falhar, logar resultado
- **OUT:** Não implementar overfetch ainda (sprint 08)

**Arquivos tocados:**
- `services/make-video/app/celery_tasks.py`

**Mudanças exatas:**
- Localizar função `download_short()` ou equivalente
- Após `api_client.download_video(video_id, output_path)`, adicionar:
  ```python
  # 2. NOVO: Validar integridade (ffprobe + decode real)
  from app.video_validator import validate_video_integrity
  if not await validate_video_integrity(output_path, timeout=5):
      logger.warning(f"⚠️ Vídeo {video_id} corrompido/inválido - descartando")
      os.remove(output_path)
      return None
  ```
- Garantir que se retorna None, não adiciona ao cache

**Critérios de Aceite / Definition of Done:**
- [ ] Validação chamada após download
- [ ] Vídeo inválido descartado
- [ ] Return None se inválido
- [ ] Vídeo válido continua normalmente

**Testes:**
- Integration: `tests/test_celery_tasks.py::test_corrupted_video_discarded()`
- Integration: `tests/test_celery_tasks.py::test_valid_video_cached()`

**Observabilidade:**
- Log: `logger.info("video_validation_in_pipeline", video_id="...", valid=True/False)`

**Riscos/Rollback:**
- Risco: Pipeline quebra se validação falha sempre
- Rollback: Flag ENABLE_VIDEO_VALIDATION=false

**Dependências:** S-029

---

<a name="s-031"></a>
## S-031: Adicionar métrica validation_time_ms

**Objetivo:** Adicionar métrica histogram para medir tempo de validação de vídeo, permitindo detectar lentidão.

**Escopo (IN/OUT):**
- **IN:** Histogram `validation_time_ms` com buckets
- **OUT:** Não adicionar outras métricas de vídeo ainda

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Adicionar import: `import time` ou `from time import perf_counter`
- No início de `validate_video_integrity()`: `start_time = perf_counter()`
- No final (antes de return): `duration_ms = (perf_counter() - start_time) * 1000`
- Adicionar: `metrics.histogram("validation_time_ms", duration_ms, {"valid": str(result).lower()})`
- Importar: `from app.metrics import histogram`

**Critérios de Aceite / Definition of Done:**
- [ ] Métrica registrada ao final da validação
- [ ] Tag `valid=true/false` adicionada
- [ ] Valor em milissegundos
- [ ] Visível em `/metrics`

**Testes:**
- Unit: `tests/test_video_validator.py::test_validation_time_metric_recorded()`

**Observabilidade:**
- Métrica: `validation_time_ms_bucket{valid="true",le="1000"}`, `validation_time_ms_bucket{valid="false",le="1000"}`, etc.
- Target: P95 < 3000ms (3s)

**Riscos/Rollback:**
- Risco: Métrica não registra (bug)
- Rollback: Verificar import e chamada

**Dependências:** S-030, S-008 (infra métricas)

---

<a name="s-032"></a>
## S-032: Criar testes com vídeo corrompido

**Objetivo:** Criar fixture de vídeo corrompido (bytes aleatórios) e validar que `validate_video_integrity()` retorna False.

**Escopo (IN/OUT):**
- **IN:** Fixture `corrupted_video`, teste que valida falha
- **OUT:** Não testar outros tipos de corrupção ainda

**Arquivos tocados:**
- `services/make-video/conftest.py`
- `services/make-video/tests/test_video_validator.py`

**Mudanças exatas:**
- Em `conftest.py`, criar fixture:
  ```python
  @pytest.fixture
  def corrupted_video(tmp_path):
      video_path = tmp_path / "corrupted.mp4"
      video_path.write_bytes(b"RANDOM INVALID DATA" * 1000)
      return str(video_path)
  ```
- Em `test_video_validator.py`, criar teste:
  ```python
  async def test_corrupted_video_fails_validation(corrupted_video):
      result = await validate_video_integrity(corrupted_video)
      assert result == False
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Fixture cria arquivo com bytes inválidos
- [ ] Teste passa (retorna False)
- [ ] Stderr capturado no log
- [ ] Teste executa em <1s

**Testes:**
- Self-test: `pytest tests/test_video_validator.py::test_corrupted_video_fails_validation -v`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Teste flaky
- Rollback: Ajustar tamanho do arquivo corrompido

**Dependências:** S-030, S-010 (fixtures)

---

<a name="s-033"></a>
## S-033: Criar testes com vídeo truncado

**Objetivo:** Criar fixture de vídeo truncado (MP4 válido cortado no meio) e validar que decode falha.

**Escopo (IN/OUT):**
- **IN:** Fixture `truncated_video`, teste que valida falha no decode
- **OUT:** Não testar vídeos parcialmente corrompidos

**Arquivos tocados:**
- `services/make-video/conftest.py`
- `services/make-video/tests/test_video_validator.py`

**Mudanças exatas:**
- Em `conftest.py`, criar fixture:
  ```python
  @pytest.fixture
  def truncated_video(tmp_path, sample_video):
      # Ler vídeo válido e cortar no meio
      with open(sample_video, 'rb') as f:
          data = f.read()
      truncated_data = data[:len(data)//2]  # 50% do vídeo
      
      truncated_path = tmp_path / "truncated.mp4"
      truncated_path.write_bytes(truncated_data)
      return str(truncated_path)
  ```
- Teste: `async def test_truncated_video_fails_decode(truncated_video):`

**Critérios de Aceite / Definition of Done:**
- [ ] Fixture cria vídeo truncado
- [ ] ffprobe pode passar (metadados intactos)
- [ ] Decode falha (frame não completo)
- [ ] Teste passa (False)

**Testes:**
- Self-test: `pytest tests/test_video_validator.py::test_truncated_video_fails_decode -v`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Truncado ainda decodifica (alguns codecs são resilientes)
- Rollback: Truncar mais agressivamente (10% do arquivo)

**Dependências:** S-032

---

<a name="s-034"></a>
## S-034: Criar testes com vídeo válido

**Objetivo:** Validar que vídeos completamente válidos passam na validação.

**Escopo (IN/OUT):**
- **IN:** Teste com `sample_video` fixture, valida retorna True
- **OUT:** Não testar edge cases de codecs raros

**Arquivos tocados:**
- `services/make-video/tests/test_video_validator.py`

**Mudanças exatas:**
- Criar teste:
  ```python
  async def test_valid_video_passes_validation(sample_video):
      result = await validate_video_integrity(sample_video)
      assert result == True
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Teste passa com vídeo válido
- [ ] Nenhum log de erro
- [ ] Validation_time_ms < 3s

**Testes:**
- Self-test: `pytest tests/test_video_validator.py::test_valid_video_passes_validation -v`

**Observabilidade:**
- Métrica: validation_time_ms com valid=true

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-033

---

<a name="s-035"></a>
## S-035: Validar timeout funciona corretamente

**Objetivo:** Criar teste que simula vídeo que demora >5s para validar e verifica que timeout dispara.

**Escopo (IN/OUT):**
- **IN:** Mock que simula delay, valida TimeoutError
- **OUT:** Não testar com vídeos reais lentos

**Arquivos tocados:**
- `services/make-video/tests/test_video_validator.py`

**Mudanças exatas:**
- Criar teste com mock:
  ```python
  async def test_timeout_triggers_after_5s(monkeypatch):
      async def slow_subprocess(*args, **kwargs):
          await asyncio.sleep(10)  # Simula processo lento
          raise asyncio.TimeoutError
      
      monkeypatch.setattr(asyncio, "create_subprocess_exec", slow_subprocess)
      
      result = await validate_video_integrity("dummy.mp4", timeout=5)
      assert result == False
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Teste passa (retorna False)
- [ ] Timeout de 5s respeitado
- [ ] Log de timeout gerado
- [ ] Métrica de timeout incrementada

**Testes:**
- Self-test: `pytest tests/test_video_validator.py::test_timeout_triggers_after_5s -v`

**Observabilidade:**
- Métrica: `counter("video_validation_timeouts_total")`

**Riscos/Rollback:**
- Risco: Mock não funciona como esperado
- Rollback: Usar fixture de vídeo sintético lento

**Dependências:** S-034

---

<a name="s-036"></a>
## S-036: Documentar validação no README

**Objetivo:** Adicionar seção no README explicando validação de integridade e como desabilitar se necessário.

**Escopo (IN/OUT):**
- **IN:** Seção "Video Integrity Validation" no README
- **OUT:** Não documentar detalhes internos de ffprobe

**Arquivos tocados:**
- `services/make-video/README.md`

**Mudanças exatas:**
- Adicionar seção:
  ```markdown
  ## Video Integrity Validation
  
  All downloaded videos are validated for integrity before processing:
  - **ffprobe check:** Validates metadata (duration, streams, codec)
  - **Decode check:** Attempts to decode 1 frame to catch corrupted/truncated files
  - **Timeout:** 5 seconds maximum per validation
  
  If validation fails, the video is discarded and replaced via overfetch.
  
  ### Configuration
  - Disable: `export ENABLE_VIDEO_VALIDATION=false`
  - Adjust timeout: `export FFPROBE_TIMEOUT=10`
  
  ### Metrics
  - `validation_time_ms`: Histogram of validation duration
  - `videos_discarded_total{reason="integrity"}`: Count of discarded videos
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Seção adicionada ao README
- [ ] Flags de configuração documentadas
- [ ] Métricas listadas
- [ ] Exemplo de desabilitação incluído

**Testes:**
- Manual: Ler README e verificar clareza

**Observabilidade:**
- N/A (documentation)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-030

---

## Mapa de Dependências (Pack 03)

```
S-025 (ffprobe) → S-026
S-026 (decode) → S-027
S-027 (timeout) → S-028
S-028 (logs) → S-029
S-029 (fail-close) → S-030
S-030 (integração) → S-031, S-032, S-036
S-031 (métrica) ← S-030, S-008
S-032 (teste corrompido) → S-033
S-033 (teste truncado) → S-034
S-034 (teste válido) → S-035
S-035 (teste timeout) ← S-034
S-036 (README) ← S-030
```

**Próximo pack:** Sprint 04 - VideoValidator base (frame extraction, downscale, ROI, OCR)
