# Sprint Pack 01/12 - Setup & Infraestrutura Base

**Escopo deste pack:** Preparação do ambiente, feature flags, estrutura de pastas, scripts de diagnóstico, observabilidade P0 inicial, e configurações base. Este é o alicerce para todas as sprints seguintes, garantindo que o projeto está estruturado para rollout seguro e monitoramento desde o início.

## Índice

- [S-001: Criar estrutura de pastas e módulos base](#s-001)
- [S-002: Adicionar feature flags ao config.py](#s-002)
- [S-003: Configurar logging estruturado base](#s-003)
- [S-004: Adicionar imports e dependências ao requirements.txt](#s-004)
- [S-005: Criar script de diagnóstico de sincronismo (esqueleto)](#s-005)
- [S-006: Configurar timeouts globais](#s-006)
- [S-007: Criar helpers de extração de áudio](#s-007)
- [S-008: Adicionar métricas base (contadores/histogramas)](#s-008)
- [S-009: Criar script de validação de ambiente](#s-009)
- [S-010: Configurar pytest com fixtures base](#s-010)
- [S-011: Criar README para módulos novos](#s-011)
- [S-012: Adicionar detector de flags FFmpeg suspeitas](#s-012)

---

<a name="s-001"></a>
## S-001: Criar estrutura de pastas e módulos base

**Objetivo:** Criar a estrutura de diretórios e arquivos `__init__.py` necessários para os novos módulos, garantindo que o Python os reconheça como packages válidos.

**Escopo (IN/OUT):**
- **IN:** Criar `app/video_validator.py`, `app/blacklist_backend.py`, `app/shorts_blacklist.py`, `app/subtitle_postprocessor.py`, `app/ass_generator.py`, `app/audio_utils.py`, `app/vad_utils.py`, `scripts/diagnose_subtitle_sync.py`, `scripts/validate_ocr_accuracy.py`
- **OUT:** Não implementar lógica interna dos módulos ainda, apenas criar arquivos vazios com docstring

**Arquivos tocados:**
- `services/make-video/app/video_validator.py` (novo)
- `services/make-video/app/blacklist_backend.py` (novo)
- `services/make-video/app/shorts_blacklist.py` (novo)
- `services/make-video/app/subtitle_postprocessor.py` (novo)
- `services/make-video/app/ass_generator.py` (novo)
- `services/make-video/app/audio_utils.py` (novo)
- `services/make-video/app/vad_utils.py` (novo)
- `services/make-video/scripts/diagnose_subtitle_sync.py` (novo)
- `services/make-video/scripts/validate_ocr_accuracy.py` (novo)

**Mudanças exatas:**
- Criar pasta `services/make-video/scripts/` se não existir
- Criar cada arquivo .py com header docstring descrevendo propósito
- Adicionar import logging em cada módulo
- Adicionar `logger = logging.getLogger(__name__)` em cada módulo

**Critérios de Aceite / Definition of Done:**
- [ ] Todos os arquivos criados existem no filesystem
- [ ] Cada arquivo tem docstring de módulo
- [ ] `from app.video_validator import VideoValidator` não gera ImportError
- [ ] Estrutura de pastas validada com `find app/ -name "*.py"`

**Testes:**
- Manual: `python -c "from app import video_validator"` não falha
- Unit: `tests/test_imports.py::test_all_modules_importable()`

**Observabilidade:**
- Log de inicialização: "Module {name} loaded"

**Riscos/Rollback:**
- Risco: Conflito de nomes com módulos existentes
- Rollback: `git rm` dos arquivos criados

**Dependências:** Nenhuma

---

<a name="s-002"></a>
## S-002: Adicionar feature flags ao config.py

**Objetivo:** Implementar todas as feature flags necessárias para rollout seguro e configurabilidade, permitindo habilitar/desabilitar funcionalidades via env vars.

**Escopo (IN/OUT):**
- **IN:** Adicionar flags: ENABLE_VIDEO_VALIDATION, VIDEO_VALIDATION_MONITOR_ONLY, OCR_CONFIDENCE_HIGH_THRESHOLD (0.75), OCR_CONFIDENCE_LOW_THRESHOLD (0.40), DOWNLOAD_TIMEOUT (30), OCR_TIMEOUT (10), FFPROBE_TIMEOUT (5), JOB_TIMEOUT (900), BLACKLIST_TTL_DAYS (90), ENABLE_WORD_TIMESTAMPS, SUBTITLE_TIMING_OFFSET (0.0), AUTO_DETECT_TIMING_OFFSET, MULTI_HOST_MODE, REDIS_URL
- **OUT:** Não implementar lógica que usa as flags ainda

**Arquivos tocados:**
- `services/make-video/app/config.py`

**Mudanças exatas:**
- Adicionar seção "# Video Validation Settings"
- Adicionar `ENABLE_VIDEO_VALIDATION = os.getenv("ENABLE_VIDEO_VALIDATION", "true").lower() == "true"`
- Adicionar `VIDEO_VALIDATION_MONITOR_ONLY = os.getenv("VIDEO_VALIDATION_MONITOR_ONLY", "false").lower() == "true"`
- Adicionar `OCR_CONFIDENCE_HIGH_THRESHOLD = float(os.getenv("OCR_CONFIDENCE_HIGH_THRESHOLD", "0.75"))`
- Adicionar `OCR_CONFIDENCE_LOW_THRESHOLD = float(os.getenv("OCR_CONFIDENCE_LOW_THRESHOLD", "0.40"))`
- Adicionar seção "# Timeouts (seconds)"
- Adicionar `DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "30"))`
- Adicionar `OCR_TIMEOUT = int(os.getenv("OCR_TIMEOUT", "10"))`
- Adicionar `FFPROBE_TIMEOUT = int(os.getenv("FFPROBE_TIMEOUT", "5"))`
- Adicionar `JOB_TIMEOUT = int(os.getenv("JOB_TIMEOUT", "900"))`
- Adicionar seção "# Blacklist Settings"
- Adicionar `BLACKLIST_TTL_DAYS = int(os.getenv("BLACKLIST_TTL_DAYS", "90"))`
- Adicionar `MULTI_HOST_MODE = os.getenv("MULTI_HOST_MODE", "false").lower() == "true"`
- Adicionar `REDIS_URL = os.getenv("REDIS_URL", "")`
- Adicionar seção "# Subtitle Sync Settings"
- Adicionar `ENABLE_WORD_TIMESTAMPS = os.getenv("ENABLE_WORD_TIMESTAMPS", "false").lower() == "true"`
- Adicionar `SUBTITLE_TIMING_OFFSET = float(os.getenv("SUBTITLE_TIMING_OFFSET", "0.0"))`
- Adicionar `AUTO_DETECT_TIMING_OFFSET = os.getenv("AUTO_DETECT_TIMING_OFFSET", "true").lower() == "true"`

**Critérios de Aceite / Definition of Done:**
- [ ] Todas as 16 flags listadas existem em config.py
- [ ] Defaults corretos (MONITOR_ONLY=false, thresholds 0.75/0.40, timeouts em segundos)
- [ ] Type casting correto (int/float/bool)
- [ ] Comentários de seção adicionados

**Testes:**
- Unit: `tests/test_config.py::test_feature_flags_defaults()`
- Unit: `tests/test_config.py::test_feature_flags_from_env()`
- Manual: Verificar que `from app.config import ENABLE_VIDEO_VALIDATION` retorna True por padrão

**Observabilidade:**
- Log no startup: "Feature flags loaded: VIDEO_VALIDATION={val}, MONITOR_ONLY={val}, ..."

**Riscos/Rollback:**
- Risco: Valores padrão incorretos causam comportamento inesperado
- Rollback: Reverter config.py, ajustar defaults

**Dependências:** S-001

---

<a name="s-003"></a>
## S-003: Configurar logging estruturado base

**Objetivo:** Configurar logging estruturado para facilitar parsing de logs em produção, seguindo formato JSON quando possível.

**Escopo (IN/OUT):**
- **IN:** Configurar logger root com formato estruturado, adicionar helpers de logging
- **OUT:** Não implementar logs específicos de cada feature ainda

**Arquivos tocados:**
- `services/make-video/app/log_utils.py` (novo ou modificar existente)
- `services/make-video/app/main.py` ou `run.py` (setup de logging)

**Mudanças exatas:**
- Criar função `setup_structured_logging()` em log_utils.py
- Configurar formato: `{"timestamp": "...", "level": "...", "module": "...", "message": "...", "extra": {...}}`
- Adicionar helper `log_with_context(logger, level, msg, **kwargs)`
- Chamar `setup_structured_logging()` no startup da aplicação

**Critérios de Aceite / Definition of Done:**
- [ ] Logs em formato JSON estruturado
- [ ] Timestamp em ISO 8601 UTC
- [ ] Helper `log_with_context` disponível
- [ ] Logs de teste funcionam

**Testes:**
- Unit: `tests/test_log_utils.py::test_structured_logging_format()`
- Manual: Executar app e verificar formato do log

**Observabilidade:**
- Log de teste: `logger.info("structured_logging_test", test_field="value")`

**Riscos/Rollback:**
- Risco: Logs quebram parsing de ferramentas existentes
- Rollback: Reverter para formato texto simples

**Dependências:** S-001

---

<a name="s-004"></a>
## S-004: Adicionar imports e dependências ao requirements.txt

**Objetivo:** Adicionar todas as bibliotecas necessárias para as novas features no requirements.txt e requirements-docker.txt.

**Escopo (IN/OUT):**
- **IN:** Adicionar pytesseract, opencv-python, Pillow, torch, torchaudio, librosa, soundfile, redis, webrtcvad
- **OUT:** Não instalar ainda, apenas documentar

**Arquivos tocados:**
- `services/make-video/requirements.txt`
- `services/make-video/requirements-docker.txt`

**Mudanças exatas:**
- Adicionar `pytesseract>=0.3.10` (OCR)
- Adicionar `opencv-python>=4.8.0` (frame extraction)
- Adicionar `Pillow>=10.0.0` (image processing)
- Adicionar `torch>=2.0.0` (VAD - silero)
- Adicionar `torchaudio>=2.0.0` (VAD)
- Adicionar `librosa>=0.10.0` (audio analysis)
- Adicionar `soundfile>=0.12.0` (audio I/O)
- Adicionar `redis>=5.0.0` (blacklist backend)
- Adicionar `webrtcvad>=2.0.10` (fallback VAD)
- Adicionar `numpy>=1.24.0` (se não existir)
- Adicionar comentários: `# OCR & Video Validation`, `# Speech Detection (VAD)`, `# Blacklist Multi-Host`

**Critérios de Aceite / Definition of Done:**
- [ ] Todas as 9 bibliotecas listadas adicionadas
- [ ] Versões mínimas especificadas
- [ ] Comentários de seção adicionados
- [ ] Arquivo validado com `pip check`

**Testes:**
- Manual: `pip install -r requirements.txt --dry-run` sem erros
- CI: Build de container Docker com novas deps

**Observabilidade:**
- N/A (dependencies)

**Riscos/Rollback:**
- Risco: Conflitos de versão com deps existentes
- Rollback: Remover linhas adicionadas, testar build

**Dependências:** Nenhuma

---

<a name="s-005"></a>
## S-005: Criar script de diagnóstico de sincronismo (esqueleto)

**Objetivo:** Criar estrutura básica do script `diagnose_subtitle_sync.py` que será usado na FASE 0 obrigatória antes de implementar correção de sincronismo.

**Escopo (IN/OUT):**
- **IN:** Estrutura do script, argumentos CLI, imports, esqueleto de funções
- **OUT:** Lógica real de VAD/diagnóstico (será implementada em sprint futura)

**Arquivos tocados:**
- `services/make-video/scripts/diagnose_subtitle_sync.py`

**Mudanças exatas:**
- Adicionar shebang `#!/usr/bin/env python3`
- Adicionar imports: `import argparse`, `import sys`, `import logging`, `from pathlib import Path`
- Criar função `def extract_audio(video_path: str) -> str: pass`
- Criar função `def detect_first_speech(audio_path: str, use_vad: bool) -> float: pass`
- Criar função `def read_first_subtitle(srt_path: str) -> float: pass`
- Criar função `def diagnose_sync_issue(video_path: str, srt_path: str, use_vad: bool) -> tuple: pass`
- Criar `main()` com argparse: `--video`, `--srt`, `--use-vad`, `--output-json`
- Adicionar docstring de módulo explicando propósito FASE 0

**Critérios de Aceite / Definition of Done:**
- [ ] Script executável: `chmod +x scripts/diagnose_subtitle_sync.py`
- [ ] Help funciona: `python scripts/diagnose_subtitle_sync.py --help`
- [ ] Estrutura de funções criada com docstrings
- [ ] Não implementado ainda (apenas `pass`)

**Testes:**
- Manual: `python scripts/diagnose_subtitle_sync.py --help` mostra ajuda
- Manual: Executar sem args mostra erro de argumentos obrigatórios

**Observabilidade:**
- Log: "Diagnose script initialized (skeleton mode)"

**Riscos/Rollback:**
- Risco: Nenhum (apenas estrutura)
- Rollback: Remover arquivo

**Dependências:** S-001

---

<a name="s-006"></a>
## S-006: Configurar timeouts globais

**Objetivo:** Implementar aplicação de timeouts em todas operações críticas (download, OCR, ffprobe, job total) usando as flags do config.

**Escopo (IN/OUT):**
- **IN:** Adicionar wrapper de timeout, aplicar em pontos críticos identificados
- **OUT:** Não refatorar lógica de negócio, apenas adicionar timeouts

**Arquivos tocados:**
- `services/make-video/app/timeout_utils.py` (novo)
- `services/make-video/app/api_client.py`
- `services/make-video/app/celery_tasks.py`

**Mudanças exatas:**
- Criar `timeout_utils.py` com `async def with_timeout(coro, timeout: int, error_msg: str)`
- Em `api_client.py`, envolver `download_video()` com `asyncio.wait_for(..., timeout=DOWNLOAD_TIMEOUT)`
- Em `celery_tasks.py`, adicionar timeout ao job total com `@task(time_limit=JOB_TIMEOUT)`
- Adicionar try/except `asyncio.TimeoutError` com log estruturado

**Critérios de Aceite / Definition of Done:**
- [ ] `with_timeout` helper criado e testado
- [ ] Download tem timeout de 30s (default)
- [ ] Job tem limite de 15min (900s default)
- [ ] TimeoutError é logado com contexto

**Testes:**
- Unit: `tests/test_timeout_utils.py::test_timeout_triggers()`
- Unit: `tests/test_timeout_utils.py::test_no_timeout_if_fast()`
- Integration: Simular download lento e verificar timeout

**Observabilidade:**
- Log: `logger.warning("timeout_triggered", operation="download", video_id="...", timeout_sec=30)`
- Métrica: `counter("timeouts_total", tags={"operation": "download"})`

**Riscos/Rollback:**
- Risco: Timeout muito curto causa falhas legítimas
- Rollback: Aumentar valor do timeout via env var

**Dependências:** S-002

---

<a name="s-007"></a>
## S-007: Criar helpers de extração de áudio

**Objetivo:** Implementar funções utilitárias para extrair áudio de vídeo usando FFmpeg, necessário para VAD e diagnóstico.

**Escopo (IN/OUT):**
- **IN:** Função `extract_audio(video_path) -> audio_path`, `get_audio_duration(audio_path) -> float`
- **OUT:** Não implementar VAD ainda

**Arquivos tocados:**
- `services/make-video/app/audio_utils.py`

**Mudanças exatas:**
- Criar função `async def extract_audio(video_path: str, output_path: str = None) -> str`
- Usar FFmpeg: `ffmpeg -i {video} -vn -acodec pcm_s16le -ar 16000 -ac 1 {output}.wav`
- Criar função `def get_audio_duration(audio_path: str) -> float` usando ffprobe
- Adicionar tratamento de erro se FFmpeg falhar
- Retornar path do áudio extraído em `/tmp/` ou pasta temp configurável

**Critérios de Aceite / Definition of Done:**
- [ ] `extract_audio()` cria arquivo WAV 16kHz mono
- [ ] `get_audio_duration()` retorna float correto
- [ ] Erros de FFmpeg são capturados e logados
- [ ] Arquivos temporários são nomeados unicamente (uuid)

**Testes:**
- Unit: `tests/test_audio_utils.py::test_extract_audio_creates_wav()`
- Unit: `tests/test_audio_utils.py::test_get_audio_duration_accurate()`
- Manual: Extrair áudio de vídeo de teste e validar duração

**Observabilidade:**
- Log: `logger.info("audio_extracted", video_path="...", audio_path="...", duration_sec=10.5)`

**Riscos/Rollback:**
- Risco: FFmpeg não instalado no ambiente
- Rollback: Adicionar validação de dependência no startup

**Dependências:** S-001

---

<a name="s-008"></a>
## S-008: Adicionar métricas base (contadores/histogramas)

**Objetivo:** Configurar infraestrutura de métricas (Prometheus-style) para observabilidade P0, preparando para KPIs do plano.

**Escopo (IN/OUT):**
- **IN:** Setup de prometheus_client ou similar, criar helpers de métrica
- **OUT:** Não adicionar métricas específicas ainda, apenas infra

**Arquivos tocados:**
- `services/make-video/app/metrics.py` (novo)
- `services/make-video/requirements.txt`

**Mudanças exatas:**
- Adicionar `prometheus-client>=0.19.0` ao requirements.txt
- Criar `metrics.py` com wrappers: `counter(name, value, tags)`, `histogram(name, value, tags)`, `gauge(name, value, tags)`
- Inicializar `CollectorRegistry` global
- Adicionar validação de cardinalidade (rejeitar se tag tem >1000 valores únicos)
- Exportar endpoint `/metrics` se aplicável

**Critérios de Aceite / Definition of Done:**
- [ ] prometheus_client instalado
- [ ] Helpers `counter`, `histogram`, `gauge` funcionais
- [ ] Validação de cardinalidade implementada
- [ ] Métricas de teste podem ser coletadas

**Testes:**
- Unit: `tests/test_metrics.py::test_counter_increments()`
- Unit: `tests/test_metrics.py::test_high_cardinality_rejected()`
- Manual: Chamar `counter("test", 1, {"tag": "value"})` e verificar em /metrics

**Observabilidade:**
- Métricas de teste: `test_counter_total`, `test_histogram_seconds`

**Riscos/Rollback:**
- Risco: Alta cardinalidade explode memória
- Rollback: Desabilitar métricas via flag

**Dependências:** S-004

---

<a name="s-009"></a>
## S-009: Criar script de validação de ambiente

**Objetivo:** Criar script que valida todas as dependências do sistema (FFmpeg, tesseract, fontes, bibliotecas Python) antes de iniciar o serviço.

**Escopo (IN/OUT):**
- **IN:** Validar FFmpeg com libass, tesseract instalado, bibliotecas Python importáveis, fontes disponíveis
- **OUT:** Não corrigir problemas automaticamente, apenas reportar

**Arquivos tocados:**
- `services/make-video/scripts/validate_environment.py` (novo)

**Mudanças exatas:**
- Criar função `check_ffmpeg_libass() -> bool` (executa `ffmpeg -version` e busca `--enable-libass`)
- Criar função `check_tesseract() -> bool` (executa `tesseract --version`)
- Criar função `check_python_deps() -> list[str]` (tenta importar: cv2, pytesseract, torch, redis, etc)
- Criar função `check_fonts() -> bool` (verifica se `/app/fonts/` existe)
- Criar `main()` que executa todos checks e retorna exit code 0 (OK) ou 1 (FAIL)
- Adicionar output colorido: ✅ PASS, ❌ FAIL

**Critérios de Aceite / Definition of Done:**
- [ ] Script executável e retorna exit codes corretos
- [ ] Todos os 4 checks implementados
- [ ] Output legível com ícones
- [ ] Pode ser usado em health check de container

**Testes:**
- Manual: `python scripts/validate_environment.py` em ambiente completo (0) e incompleto (1)
- CI: Executar no build de Docker

**Observabilidade:**
- Log: Cada check com resultado (pass/fail)

**Riscos/Rollback:**
- Risco: Falso negativo (reporta problema quando não há)
- Rollback: Ajustar lógica de detecção

**Dependências:** S-001, S-004

---

<a name="s-010"></a>
## S-010: Configurar pytest com fixtures base

**Objetivo:** Configurar pytest.ini e criar fixtures reutilizáveis para testes (vídeos de teste, áudios de teste, mocks).

**Escopo (IN/OUT):**
- **IN:** `pytest.ini`, `conftest.py` com fixtures: `sample_video`, `sample_audio`, `temp_dir`, `mock_redis`
- **OUT:** Não criar testes específicos ainda

**Arquivos tocados:**
- `services/make-video/pytest.ini`
- `services/make-video/conftest.py`
- `services/make-video/tests/fixtures/` (pasta para assets)

**Mudanças exatas:**
- Criar/atualizar `pytest.ini` com: `testpaths = tests`, `python_files = test_*.py`, `python_functions = test_*`
- Em `conftest.py`, criar fixture `@pytest.fixture def sample_video(tmp_path) -> Path` (gera vídeo 5s)
- Criar fixture `@pytest.fixture def sample_audio(tmp_path) -> Path` (gera áudio 5s)
- Criar fixture `@pytest.fixture def temp_dir(tmp_path) -> Path` (diretório temporário limpo)
- Criar fixture `@pytest.fixture def mock_redis()` usando `fakeredis` ou mock
- Adicionar `fakeredis>=2.20.0` ao requirements.txt

**Critérios de Aceite / Definition of Done:**
- [ ] pytest.ini configurado
- [ ] 4 fixtures criadas e documentadas
- [ ] Fixtures funcionam: `pytest tests/test_fixtures.py -v`
- [ ] Assets de teste criados em fixtures/

**Testes:**
- Unit: `tests/test_fixtures.py::test_sample_video_exists(sample_video)`
- Unit: `tests/test_fixtures.py::test_mock_redis_works(mock_redis)`

**Observabilidade:**
- N/A (testing infra)

**Riscos/Rollback:**
- Risco: Fixtures lentas atrasam testes
- Rollback: Otimizar geração de assets (cache)

**Dependências:** S-004

---

<a name="s-011"></a>
## S-011: Criar README para módulos novos

**Objetivo:** Documentar propósito e uso básico de cada módulo novo (video_validator, blacklist, subtitle_postprocessor, ass_generator).

**Escopo (IN/OUT):**
- **IN:** README.md em `app/video_validator/`, `app/blacklist/`, etc. com: propósito, exemplo de uso, configuração
- **OUT:** Não documentar implementação interna ainda

**Arquivos tocados:**
- `services/make-video/app/README_VIDEO_VALIDATOR.md` (novo)
- `services/make-video/app/README_BLACKLIST.md` (novo)
- `services/make-video/app/README_SUBTITLE_POSTPROCESSOR.md` (novo)
- `services/make-video/app/README_ASS_GENERATOR.md` (novo)

**Mudanças exatas:**
- Cada README com seções: "## Purpose", "## Quick Start", "## Configuration", "## API Reference" (vazia por enquanto)
- VIDEO_VALIDATOR: explicar detecção de legendas embutidas, ROI, OCR
- BLACKLIST: explicar TTL, Redis vs JSON, overfetch
- SUBTITLE_POSTPROCESSOR: explicar VAD, gating, clamp/merge
- ASS_GENERATOR: explicar presets neon/classic, 2 camadas, fontes

**Critérios de Aceite / Definition of Done:**
- [ ] 4 READMEs criados
- [ ] Cada README tem ao menos 3 seções
- [ ] Exemplos de código (placeholder) incluídos
- [ ] Referência ao PLAN.md para detalhes completos

**Testes:**
- Manual: Ler READMEs e verificar clareza

**Observabilidade:**
- N/A (documentation)

**Riscos/Rollback:**
- Risco: Documentação desatualizada
- Rollback: N/A (sem risco técnico)

**Dependências:** S-001

---

<a name="s-012"></a>
## S-012: Adicionar detector de flags FFmpeg suspeitas

**Objetivo:** Implementar função que analisa comandos FFmpeg e detecta flags que podem introduzir offset de sincronismo.

**Escopo (IN/OUT):**
- **IN:** Função `detect_suspicious_flags(cmd: List[str]) -> List[str]` em módulo utils
- **OUT:** Não modificar comandos FFmpeg ainda, apenas detectar

**Arquivos tocados:**
- `services/make-video/app/ffmpeg_utils.py` (novo)

**Mudanças exatas:**
- Criar `ffmpeg_utils.py`
- Implementar `def detect_suspicious_flags(cmd: List[str]) -> List[str]`
- Lista de flags suspeitas: `itsoffset`, `adelay`, `asetpts`, `setpts`, `-async`, `aresample=async`, `-vsync`
- Retornar lista de flags detectadas
- Adicionar docstring explicando por que cada flag é suspeita

**Critérios de Aceite / Definition of Done:**
- [ ] Função criada e testada
- [ ] Detecta ao menos 7 flags suspeitas
- [ ] Retorna lista vazia se comando limpo
- [ ] Docstring completa

**Testes:**
- Unit: `tests/test_ffmpeg_utils.py::test_detect_itsoffset()`
- Unit: `tests/test_ffmpeg_utils.py::test_no_suspicious_flags()`
- Unit: `tests/test_ffmpeg_utils.py::test_multiple_suspicious()`

**Observabilidade:**
- Log: Será usado em sprints futuras quando chamado

**Riscos/Rollback:**
- Risco: Falsos positivos (flags legítimas marcadas como suspeitas)
- Rollback: Refinar lista de flags

**Dependências:** S-001

---

## Mapa de Dependências (Pack 01)

```
S-001 (estrutura) → S-002, S-003, S-005, S-007, S-011, S-012
S-002 (flags) → S-006
S-004 (deps) → S-008, S-009, S-010
S-006 (timeouts) ← S-002
S-008 (métricas) ← S-004
S-009 (validação env) ← S-001, S-004
S-010 (pytest) ← S-004
S-011 (docs) ← S-001
S-012 (detector) ← S-001
```

**Próximo pack:** Sprint 02 - Correção de posicionamento (Alignment=5)
