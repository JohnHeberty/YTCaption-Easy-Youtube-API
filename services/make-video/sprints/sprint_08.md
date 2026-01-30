# Sprint Pack 08/12 - Pipeline Integration + Deduplication

**Escopo deste pack:** Integrar blacklist no pipeline, implementar validação no download_short, overfetch no fetch_shorts com dedupe usando set(), remover duplicate return (MUST-FIX v1.6), adicionar contadores skipped_blacklist e skipped_duplicate, política de decisão por confidence.

## Índice

- [S-089: Integrar blacklist em download_short()](#s-089)
- [S-090: Adicionar contadores skipped_blacklist e skipped_duplicate](#s-090)
- [S-091: Implementar overfetch no fetch_shorts (overfetch_factor)](#s-091)
- [S-092: Implementar deduplicação com seen=set()](#s-092)
- [S-093: Remover duplicate return (MUST-FIX v1.6)](#s-093)
- [S-094: Implementar política de decisão por confidence](#s-094)
- [S-095: Adicionar logs estruturados na política](#s-095)
- [S-096: Criar testes de integração pipeline completo](#s-096)
- [S-097: Validar overfetch realmente busca quantidade correta](#s-097)
- [S-098: Validar dedupe remove duplicados](#s-098)
- [S-099: Validar política aplica regras corretas](#s-099)
- [S-100: Atualizar README com documentação do pipeline](#s-100)

---

<a name="s-089"></a>
## S-089: Integrar blacklist em download_short()

**Objetivo:** Modificar `download_short()` para checar blacklist antes de fazer download.

**Escopo (IN/OUT):**
- **IN:** Verificar blacklist no início
- **OUT:** Não modificar lógica de download

**Arquivos tocados:**
- `services/make-video/app/celery_tasks.py`

**Mudanças exatas:**
- No início de `download_short()`, adicionar:
  ```python
  from app.blacklist_backend import BlacklistManager
  
  # Inicializar gerenciador
  blacklist = BlacklistManager()
  
  def download_short(video_id: str):
      # Verificar blacklist ANTES de qualquer processamento
      if blacklist.is_blacklisted(video_id):
          logger.info(f"⏭️  Skipping {video_id}: blacklisted")
          return {'status': 'skipped', 'reason': 'blacklisted', 'video_id': video_id}
      
      # ... resto da lógica de download
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Verificação no início da função
- [ ] Retorna status='skipped' se blacklisted
- [ ] Log indica skip por blacklist
- [ ] Não tenta download/processamento

**Testes:**
- Unit: `tests/test_celery_tasks.py::test_download_short_skips_blacklisted()`

**Observabilidade:**
- Log: `logger.info("download_skipped", reason="blacklisted", video_id=...)`
- Métrica: `counter("downloads_skipped_total", tags={"reason": "blacklisted"})`

**Riscos/Rollback:**
- Risco: Blacklist check lento causa latência
- Rollback: Adicionar timeout de 500ms

**Dependências:** S-086 (BlacklistManager)

---

<a name="s-090"></a>
## S-090: Adicionar contadores skipped_blacklist e skipped_duplicate

**Objetivo:** Criar métricas Prometheus para tracking de skips.

**Escopo (IN/OUT):**
- **IN:** Contadores globais
- **OUT:** Não implementar histogramas

**Arquivos tocados:**
- `services/make-video/app/metrics.py`
- `services/make-video/app/celery_tasks.py`

**Mudanças exatas:**
- Em `metrics.py`, adicionar:
  ```python
  from prometheus_client import Counter
  
  downloads_skipped_total = Counter(
      'make_video_downloads_skipped_total',
      'Total de downloads pulados',
      ['reason']  # blacklisted, duplicate, etc
  )
  ```
- Em `celery_tasks.py`, após skip:
  ```python
  if blacklist.is_blacklisted(video_id):
      downloads_skipped_total.labels(reason='blacklisted').inc()
      # ...
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Contador criado
- [ ] Label 'reason' com valores: blacklisted, duplicate
- [ ] Incrementado corretamente

**Testes:**
- Unit: `tests/test_metrics.py::test_downloads_skipped_counter()`

**Observabilidade:**
- Métrica: `make_video_downloads_skipped_total{reason="blacklisted"}`, `{reason="duplicate"}`

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-007 (metrics), S-089

---

<a name="s-091"></a>
## S-091: Implementar overfetch no fetch_shorts (overfetch_factor)

**Objetivo:** Modificar `fetch_shorts()` para buscar mais vídeos do que necessário, assumindo filtros posteriores.

**Escopo (IN/OUT):**
- **IN:** Overfetch com fator configurável
- **OUT:** Não implementar pré-filtro de shorts

**Arquivos tocados:**
- `services/make-video/app/celery_tasks.py`
- `services/make-video/app/config.py`

**Mudanças exatas:**
- Em `config.py`, adicionar:
  ```python
  # Overfetch para compensar blacklist/dedupe
  OVERFETCH_FACTOR = float(os.getenv('OVERFETCH_FACTOR', '2.0'))  # Buscar 2x mais
  ```
- Em `celery_tasks.py`, modificar `fetch_shorts()`:
  ```python
  def fetch_shorts(count: int) -> list:
      # Calcular quantidade com overfetch
      fetch_count = int(count * OVERFETCH_FACTOR)
      
      logger.info(f"fetch_shorts_overfetch", requested=count, fetching=fetch_count, factor=OVERFETCH_FACTOR)
      
      # Chamar API do youtube-search com fetch_count
      results = youtube_search_api.search(query='shorts', max_results=fetch_count)
      
      # Retornar todos (dedupe será feito depois)
      return results
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] fetch_count = count * OVERFETCH_FACTOR
- [ ] Log indica overfetch
- [ ] Default: 2.0 (buscar 2x mais)
- [ ] Configurável via env

**Testes:**
- Unit: `tests/test_celery_tasks.py::test_fetch_shorts_overfetch()`

**Observabilidade:**
- Log: `logger.info("fetch_shorts_overfetch", requested=..., fetching=...)`

**Riscos/Rollback:**
- Risco: Overfetch alto causa rate limit
- Rollback: Reduzir para 1.5

**Dependências:** S-001 (config)

---

<a name="s-092"></a>
## S-092: Implementar deduplicação com seen=set()

**Objetivo:** Adicionar lógica de dedupe usando set para tracking de vídeos já vistos.

**Escopo (IN/OUT):**
- **IN:** Dedupe simples com set()
- **OUT:** Não implementar dedupe persistente entre execuções

**Arquivos tocados:**
- `services/make-video/app/celery_tasks.py`

**Mudanças exatas:**
- Em `fetch_shorts()`, adicionar:
  ```python
  def fetch_shorts(count: int) -> list:
      fetch_count = int(count * OVERFETCH_FACTOR)
      results = youtube_search_api.search(query='shorts', max_results=fetch_count)
      
      # Dedupe usando set (in-memory)
      seen = set()
      unique_results = []
      
      for video in results:
          video_id = video['video_id']
          
          if video_id in seen:
              logger.debug(f"⏭️  Duplicate: {video_id}")
              downloads_skipped_total.labels(reason='duplicate').inc()
              continue
          
          seen.add(video_id)
          unique_results.append(video)
      
      logger.info(f"fetch_shorts_dedupe", fetched=len(results), unique=len(unique_results), duplicates=len(results)-len(unique_results))
      
      # Limitar ao count original
      return unique_results[:count]
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Set usado para tracking
- [ ] Duplicados pulados
- [ ] Contador incrementado
- [ ] Log mostra stats de dedupe
- [ ] Retorna apenas count vídeos únicos

**Testes:**
- Unit: `tests/test_celery_tasks.py::test_fetch_shorts_dedupe()`

**Observabilidade:**
- Log: `logger.info("fetch_shorts_dedupe", fetched=..., unique=..., duplicates=...)`
- Métrica: `downloads_skipped_total{reason="duplicate"}`

**Riscos/Rollback:**
- Risco: Set cresce indefinidamente se função chamada repetidamente
- Rollback: Usar LRU cache ou persistir seen no Redis

**Dependências:** S-091, S-090 (contadores)

---

<a name="s-093"></a>
## S-093: Remover duplicate return (MUST-FIX v1.6)

**Objetivo:** Identificar e remover declarações de return duplicadas no código.

**Escopo (IN/OUT):**
- **IN:** Scan de código e remoção
- **OUT:** Não refatorar lógica

**Arquivos tocados:**
- Todos os arquivos Python (grep)

**Mudanças exatas:**
- Executar: `grep -rn "return\|return" services/make-video/app/ --include="*.py"`
- Identificar casos com 2 returns consecutivos (ex: auto-merge mal feito)
- Remover duplicados mantendo apenas 1
- Exemplo:
  ```python
  # ANTES (errado)
  def func():
      result = calculate()
      return result
      return result  # DUPLICADO
  
  # DEPOIS (correto)
  def func():
      result = calculate()
      return result
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Grep executado em todo o código
- [ ] Duplicados identificados
- [ ] Duplicados removidos
- [ ] Código mantém lógica original

**Testes:**
- Manual: Executar suite completa e validar que nada quebrou

**Observabilidade:**
- N/A (limpeza de código)

**Riscos/Rollback:**
- Risco: Remover return errado
- Rollback: Git revert da sprint

**Dependências:** S-001

---

<a name="s-094"></a>
## S-094: Implementar política de decisão por confidence

**Objetivo:** Implementar lógica que decide ação com base no nível de confidence da detecção.

**Escopo (IN/OUT):**
- **IN:** Política simples: high=blacklist, medium=log, low=ignore
- **OUT:** Não implementar machine learning

**Arquivos tocados:**
- `services/make-video/app/celery_tasks.py`

**Mudanças exatas:**
- Após detecção de subtítulos embedded, adicionar política:
  ```python
  def process_video_policy(video_id: str, has_embedded: bool, confidence: float):
      """
      Política de decisão por confidence:
      - high (>0.75): blacklist
      - medium (0.40-0.75): log warning
      - low (<0.40): ignore
      """
      from app.blacklist_backend import BlacklistManager
      
      blacklist = BlacklistManager()
      
      if not has_embedded:
          return 'proceed'
      
      # Classificar confidence
      if confidence > 0.75:
          # HIGH: blacklist
          blacklist.add(
              video_id,
              reason='embedded_subtitles',
              detection_info={'confidence': confidence, 'policy': 'high'},
              confidence=confidence
          )
          logger.warning(f"🚫 BLACKLIST: {video_id} (conf={confidence:.2f})")
          return 'blacklisted'
      
      elif confidence >= 0.40:
          # MEDIUM: log warning (não bloqueia)
          logger.warning(f"⚠️  MEDIUM confidence: {video_id} (conf={confidence:.2f}) - procede com cautela")
          return 'proceed_caution'
      
      else:
          # LOW: ignora detecção (falso positivo provável)
          logger.info(f"✅ LOW confidence: {video_id} (conf={confidence:.2f}) - ignoring detection")
          return 'proceed'
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] 3 buckets: high, medium, low
- [ ] Apenas high causa blacklist
- [ ] Medium gera warning
- [ ] Low é ignorado
- [ ] Logs indicam ação tomada

**Testes:**
- Unit: `tests/test_celery_tasks.py::test_policy_high_confidence_blacklists()`
- Unit: `tests/test_celery_tasks.py::test_policy_medium_proceeds_with_warning()`
- Unit: `tests/test_celery_tasks.py::test_policy_low_ignores()`

**Observabilidade:**
- Log: `logger.warning("policy_decision", action="blacklisted"|"proceed_caution"|"proceed", confidence=...)`
- Métrica: `counter("policy_decisions_total", tags={"action": ...})`

**Riscos/Rollback:**
- Risco: Thresholds incorretos causam muitos FP ou FN
- Rollback: Ajustar thresholds via config

**Dependências:** S-062 (confidence heuristics), S-086 (BlacklistManager)

---

<a name="s-095"></a>
## S-095: Adicionar logs estruturados na política

**Objetivo:** Adicionar logs estruturados que facilitam debug e análise da política.

**Escopo (IN/OUT):**
- **IN:** Logs com todos os parâmetros relevantes
- **OUT:** Não implementar tracing distribuído

**Arquivos tocados:**
- `services/make-video/app/celery_tasks.py`

**Mudanças exatas:**
- Modificar logs na política:
  ```python
  logger.info(
      "policy_evaluation",
      video_id=video_id,
      has_embedded=has_embedded,
      confidence=round(confidence, 3),
      bucket='high'|'medium'|'low',
      action='blacklisted'|'proceed_caution'|'proceed',
      threshold_high=0.75,
      threshold_medium=0.40
  )
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Log estruturado com todos parâmetros
- [ ] Thresholds explícitos no log
- [ ] Ação tomada explícita

**Testes:**
- Unit: `tests/test_celery_tasks.py::test_policy_logs_structured()`

**Observabilidade:**
- Log: Estruturado com todos campos

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-094, S-002 (structured logging)

---

<a name="s-096"></a>
## S-096: Criar testes de integração pipeline completo

**Objetivo:** Criar testes que validam pipeline end-to-end: fetch → validate → detect → policy → download.

**Escopo (IN/OUT):**
- **IN:** Teste completo com todos componentes
- **OUT:** Não testar com API real do YouTube

**Arquivos tocados:**
- `services/make-video/tests/test_integration_pipeline.py`

**Mudanças exatas:**
- Criar arquivo:
  ```python
  import pytest
  from app.celery_tasks import fetch_shorts, download_short
  from app.blacklist_backend import BlacklistManager
  
  @pytest.fixture
  def clean_blacklist():
      """Limpa blacklist antes do teste"""
      blacklist = BlacklistManager()
      # TODO: implementar clear() ou usar mock
      yield blacklist
  
  def test_pipeline_full_flow(clean_blacklist, mock_youtube_api, mock_video_validator):
      """
      Testa fluxo completo:
      1. fetch_shorts busca vídeos
      2. dedupe remove duplicados
      3. download_short valida cada um
      4. detecção de embedded subtitles
      5. política decide ação
      6. blacklist atualizada
      """
      # Setup mocks
      mock_youtube_api.return_value = [
          {'video_id': 'video1'},
          {'video_id': 'video2'},
          {'video_id': 'video1'},  # duplicado
      ]
      
      mock_video_validator.has_embedded_subtitles.side_effect = [
          (True, 0.85),  # video1: high confidence → blacklist
          (False, 0.0),  # video2: sem subtítulos → procede
      ]
      
      # Executar
      videos = fetch_shorts(count=2)
      
      # Validar
      assert len(videos) == 2  # dedupe funcionou
      assert videos[0]['video_id'] == 'video1'
      assert videos[1]['video_id'] == 'video2'
      
      # Processar cada vídeo
      result1 = download_short('video1')
      result2 = download_short('video2')
      
      # Validar resultados
      assert result1['status'] == 'blacklisted'
      assert result2['status'] == 'success'
      
      # Validar blacklist
      assert clean_blacklist.is_blacklisted('video1') == True
      assert clean_blacklist.is_blacklisted('video2') == False
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Teste cobre fluxo completo
- [ ] Usa mocks para dependências externas
- [ ] Valida cada etapa do pipeline
- [ ] Passa com sucesso

**Testes:**
- Integration: `tests/test_integration_pipeline.py::test_pipeline_full_flow()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Testes acoplados
- Rollback: Separar em testes menores

**Dependências:** S-089, S-092, S-094, S-010 (fixtures)

---

<a name="s-097"></a>
## S-097: Validar overfetch realmente busca quantidade correta

**Objetivo:** Criar testes que validam que overfetch está funcionando corretamente.

**Escopo (IN/OUT):**
- **IN:** Testes unitários
- **OUT:** Não testar com API real

**Arquivos tocados:**
- `services/make-video/tests/test_celery_tasks.py`

**Mudanças exatas:**
- Adicionar testes:
  ```python
  def test_overfetch_calculates_correctly(monkeypatch):
      monkeypatch.setenv('OVERFETCH_FACTOR', '2.5')
      
      # Mock API
      mock_api = Mock()
      mock_api.search.return_value = [{'video_id': f'v{i}'} for i in range(25)]
      
      monkeypatch.setattr('app.celery_tasks.youtube_search_api', mock_api)
      
      # Executar
      fetch_shorts(count=10)
      
      # Validar que API foi chamada com 10 * 2.5 = 25
      mock_api.search.assert_called_once()
      args, kwargs = mock_api.search.call_args
      assert kwargs['max_results'] == 25
  
  def test_overfetch_returns_limited_count():
      # Mock retorna 50 vídeos
      mock_api = Mock()
      mock_api.search.return_value = [{'video_id': f'v{i}'} for i in range(50)]
      
      # Pedir 10
      result = fetch_shorts(count=10)
      
      # Validar que retorna apenas 10
      assert len(result) == 10
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Testa cálculo de fetch_count
- [ ] Testa limitação ao count original
- [ ] Testa configurabilidade via env

**Testes:**
- Unit: `tests/test_celery_tasks.py::test_overfetch_calculates_correctly()`
- Unit: `tests/test_celery_tasks.py::test_overfetch_returns_limited_count()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-091

---

<a name="s-098"></a>
## S-098: Validar dedupe remove duplicados

**Objetivo:** Criar testes que validam que deduplicação está funcionando corretamente.

**Escopo (IN/OUT):**
- **IN:** Testes com duplicados
- **OUT:** Não testar persistência

**Arquivos tocados:**
- `services/make-video/tests/test_celery_tasks.py`

**Mudanças exatas:**
- Adicionar testes:
  ```python
  def test_dedupe_removes_duplicates():
      # Mock retorna duplicados
      mock_api = Mock()
      mock_api.search.return_value = [
          {'video_id': 'v1'},
          {'video_id': 'v2'},
          {'video_id': 'v1'},  # duplicado
          {'video_id': 'v3'},
          {'video_id': 'v2'},  # duplicado
      ]
      
      monkeypatch.setattr('app.celery_tasks.youtube_search_api', mock_api)
      
      # Executar
      result = fetch_shorts(count=10)
      
      # Validar
      assert len(result) == 3  # apenas únicos
      assert [v['video_id'] for v in result] == ['v1', 'v2', 'v3']
  
  def test_dedupe_increments_counter(monkeypatch):
      # Mock retorna duplicados
      mock_api = Mock()
      mock_api.search.return_value = [
          {'video_id': 'v1'},
          {'video_id': 'v1'},
          {'video_id': 'v1'},
      ]
      
      # Executar
      fetch_shorts(count=10)
      
      # Validar contador
      metric = get_metric_value('make_video_downloads_skipped_total', reason='duplicate')
      assert metric >= 2  # 2 duplicados
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Testa remoção de duplicados
- [ ] Valida contador incrementado
- [ ] Valida ordem preservada

**Testes:**
- Unit: `tests/test_celery_tasks.py::test_dedupe_removes_duplicates()`
- Unit: `tests/test_celery_tasks.py::test_dedupe_increments_counter()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-092

---

<a name="s-099"></a>
## S-099: Validar política aplica regras corretas

**Objetivo:** Criar testes que validam comportamento da política de decisão.

**Escopo (IN/OUT):**
- **IN:** Testes para cada bucket de confidence
- **OUT:** Não testar edge cases extremos

**Arquivos tocados:**
- `services/make-video/tests/test_celery_tasks.py`

**Mudanças exatas:**
- Adicionar testes:
  ```python
  @pytest.mark.parametrize('confidence,expected_action', [
      (0.90, 'blacklisted'),  # high
      (0.76, 'blacklisted'),  # high (boundary)
      (0.75, 'proceed_caution'),  # medium (boundary)
      (0.60, 'proceed_caution'),  # medium
      (0.40, 'proceed_caution'),  # medium (boundary)
      (0.39, 'proceed'),  # low
      (0.10, 'proceed'),  # low
  ])
  def test_policy_confidence_buckets(confidence, expected_action):
      action = process_video_policy('video1', has_embedded=True, confidence=confidence)
      assert action == expected_action
  
  def test_policy_no_embedded_always_proceeds():
      action = process_video_policy('video1', has_embedded=False, confidence=0.99)
      assert action == 'proceed'
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Testa todos buckets
- [ ] Testa boundaries (0.75, 0.40)
- [ ] Testa caso sem embedded subtitles

**Testes:**
- Unit: `tests/test_celery_tasks.py::test_policy_confidence_buckets()`
- Unit: `tests/test_celery_tasks.py::test_policy_no_embedded_always_proceeds()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-094

---

<a name="s-100"></a>
## S-100: Atualizar README com documentação do pipeline

**Objetivo:** Documentar pipeline completo no README com fluxograma e decisões.

**Escopo (IN/OUT):**
- **IN:** Documentação textual e fluxograma
- **OUT:** Não criar diagramas visuais complexos

**Arquivos tocados:**
- `services/make-video/README.md`

**Mudanças exatas:**
- Adicionar seção:
  ````markdown
  ## Pipeline de Processamento
  
  ### Fluxo Completo
  
  ```
  fetch_shorts(count=10)
      ↓
  Overfetch (10 * 2.0 = 20 vídeos)
      ↓
  Dedupe (remover duplicados)
      ↓
  Limitar a 10 únicos
      ↓
  Para cada vídeo:
      ↓
  download_short(video_id)
      ↓
  Verificar blacklist → skip se bloqueado
      ↓
  validate_video_integrity → skip se corrompido
      ↓
  VideoValidator.has_embedded_subtitles
      ↓
  Calcular confidence (0-1)
      ↓
  Política de decisão:
      - confidence > 0.75: BLACKLIST + skip
      - confidence 0.40-0.75: WARNING + procede
      - confidence < 0.40: IGNORE + procede
      ↓
  Download e processamento
  ```
  
  ### Configuração
  
  - `OVERFETCH_FACTOR` (default: 2.0): Multiplicador de overfetch
  - `MULTI_HOST_MODE` (default: false): Usar Redis para blacklist
  - `BLACKLIST_TTL_DAYS` (default: 90): TTL das entradas
  
  ### Monitoramento
  
  Métricas:
  - `make_video_downloads_skipped_total{reason="blacklisted"|"duplicate"}`
  - `make_video_policy_decisions_total{action="blacklisted"|"proceed_caution"|"proceed"}`
  
  Logs estruturados:
  - `fetch_shorts_overfetch`: Quantidade buscada vs solicitada
  - `fetch_shorts_dedupe`: Stats de deduplicação
  - `policy_evaluation`: Decisão da política
  ````

**Critérios de Aceite / Definition of Done:**
- [ ] Seção adicionada ao README
- [ ] Fluxograma ASCII claro
- [ ] Configurações documentadas
- [ ] Métricas listadas

**Testes:**
- Manual: Revisar README

**Observabilidade:**
- N/A (documentação)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-089, S-091, S-092, S-094

---

## Mapa de Dependências (Pack 08)

```
S-089 (integrar blacklist) ← S-086
S-090 (contadores) ← S-007, S-089
S-091 (overfetch) ← S-001
S-092 (dedupe) ← S-091, S-090
S-093 (remover duplicate return) ← S-001
S-094 (política decisão) ← S-062, S-086
S-095 (logs estruturados) ← S-094, S-002
S-096 (teste integração) ← S-089, S-092, S-094, S-010
S-097 (validar overfetch) ← S-091
S-098 (validar dedupe) ← S-092
S-099 (validar política) ← S-094
S-100 (README) ← S-089, S-091, S-092, S-094
```

**Próximo pack:** Sprint 09 - SpeechGatedSubtitles (silero-vad, detect_speech_segments, clamp com audio_duration, gate_subtitles)
