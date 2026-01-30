# Sprint Pack 05/12 - VideoValidator Heurísticas & Confidence Determinístico

**Escopo deste pack:** Implementar sistema de confidence determinístico com 4 features (persistence, bbox, char_count, ocr_quality), heurísticas de detecção de legendas, early exit, e buckets de confiança (high/medium/low).

## Índice

- [S-049: Implementar persistence_score (% frames com texto)](#s-049)
- [S-050: Implementar bbox_score (centralizado + altura típica)](#s-050)
- [S-051: Implementar char_count_score (>= 5 chars)](#s-051)
- [S-052: Implementar ocr_quality_score (conf média)](#s-052)
- [S-053: Implementar weighted_sum de confidence](#s-053)
- [S-054: Definir pesos (0.35/0.25/0.20/0.20)](#s-054)
- [S-055: Implementar early exit ao detectar legenda](#s-055)
- [S-056: Implementar buckets (high >0.75, medium 0.40-0.75, low <0.40)](#s-056)
- [S-057: Implementar análise completa de frame em ROI](#s-057)
- [S-058: Adicionar filtro de min_text_threshold (5 chars)](#s-058)
- [S-059: Implementar confidence_breakdown para debug](#s-059)
- [S-060: Criar testes com vídeo COM legendas](#s-060)
- [S-061: Criar testes com vídeo SEM legendas](#s-061)
- [S-062: Criar testes de confidence calculation](#s-062)

---

<a name="s-049"></a>
## S-049: Implementar persistence_score (% frames com texto)

**Objetivo:** Criar feature que mede persistência de texto (quantos % dos frames analisados têm texto na ROI).

**Escopo (IN/OUT):**
- **IN:** Função que calcula % de frames com texto detectado
- **OUT:** Não aplicar peso ainda (próxima sprint)

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _calculate_persistence_score(self, detection_results: List[Dict]) -> float:
      """
      Feature 1: Persistence score
      
      Calcula % de frames que têm texto em ROI.
      Legendas embutidas aparecem em múltiplos frames consecutivos.
      
      Returns: 0.0-1.0
      """
      if not detection_results:
          return 0.0
      
      frames_with_text = sum(1 for r in detection_results if r.get('has_text', False))
      persistence = frames_with_text / len(detection_results)
      
      return persistence
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna 0.0 se nenhum frame com texto
- [ ] Retorna 1.0 se todos frames têm texto
- [ ] Retorna 0.5 se metade dos frames têm texto
- [ ] Range: 0.0-1.0

**Testes:**
- Unit: `tests/test_video_validator.py::test_persistence_score_calculation()`

**Observabilidade:**
- Log: `logger.debug("persistence_score", score=persistence, frames_with_text=count)`

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-045

---

<a name="s-050"></a>
## S-050: Implementar bbox_score (centralizado + altura típica)

**Objetivo:** Criar feature que valida se bbox do texto está centralizado horizontalmente e tem altura típica de legenda (5-15% da altura do frame).

**Escopo (IN/OUT):**
- **IN:** Função que analisa bbox do texto detectado
- **OUT:** Não aplicar em todas ROIs ainda

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _score_bbox(self, bbox: Dict, frame_width: int, frame_height: int) -> float:
      """
      Feature 2: Bbox score
      
      Score alto se:
      - Texto centralizado horizontalmente (offset < 20% do centro)
      - Altura típica de legenda (5-15% da altura do frame)
      
      Returns: 0.0-1.0
      """
      # Verificar centralização horizontal
      center_x = (bbox['x'] + bbox['x2']) / 2
      frame_center_x = frame_width / 2
      horizontal_offset = abs(center_x - frame_center_x) / frame_center_x
      
      # Verificar altura típica (5-15% da altura do frame)
      bbox_height = bbox['y2'] - bbox['y']
      height_ratio = bbox_height / frame_height
      height_score = 1.0 if 0.05 <= height_ratio <= 0.15 else 0.5
      
      # Score final
      horizontal_score = max(0.0, 1.0 - horizontal_offset)
      return (horizontal_score * 0.6 + height_score * 0.4)
  ```
- Criar helper: `def _get_text_bbox(self, ocr_data) -> Dict` que extrai bbox dos dados do pytesseract

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna alto (>0.8) se centralizado e altura típica
- [ ] Retorna médio (~0.5) se apenas 1 critério atendido
- [ ] Retorna baixo (<0.3) se nenhum critério
- [ ] Range: 0.0-1.0

**Testes:**
- Unit: `tests/test_video_validator.py::test_bbox_score_centered()`
- Unit: `tests/test_video_validator.py::test_bbox_score_off_center()`

**Observabilidade:**
- Log: `logger.debug("bbox_score", score=..., horizontal_offset=..., height_ratio=...)`

**Riscos/Rollback:**
- Risco: Thresholds (5-15%) podem não cobrir todas legendas
- Rollback: Ajustar para 3-20%

**Dependências:** S-049

---

<a name="s-051"></a>
## S-051: Implementar char_count_score (>= 5 chars)

**Objetivo:** Criar feature que valida quantidade de caracteres (texto >=5 chars é mais provável de ser legenda).

**Escopo (IN/OUT):**
- **IN:** Função que pontua baseado em char count
- **OUT:** Não filtrar por idioma ainda

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _calculate_char_count_score(self, detection_results: List[Dict]) -> float:
      """
      Feature 3: Char count score
      
      Texto >= 5 chars é mais provável de ser legenda (não artefato/ruído).
      
      Returns: 0.0-1.0
      """
      if not detection_results:
          return 0.0
      
      char_counts = [r.get('char_count', 0) for r in detection_results if r.get('has_text', False)]
      
      if not char_counts:
          return 0.0
      
      avg_char_count = sum(char_counts) / len(char_counts)
      
      # Normalizar: 10 chars = score 1.0
      score = min(1.0, avg_char_count / 10.0)
      
      return score
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna 0.0 se nenhum char
- [ ] Retorna 0.5 se média de 5 chars
- [ ] Retorna 1.0 se média >=10 chars
- [ ] Range: 0.0-1.0

**Testes:**
- Unit: `tests/test_video_validator.py::test_char_count_score_calculation()`

**Observabilidade:**
- Log: `logger.debug("char_count_score", score=..., avg_chars=...)`

**Riscos/Rollback:**
- Risco: Threshold de 10 chars pode ser alto demais
- Rollback: Ajustar para 7 chars

**Dependências:** S-050

---

<a name="s-052"></a>
## S-052: Implementar ocr_quality_score (conf média)

**Objetivo:** Criar feature que usa confidence média do tesseract como indicador de qualidade do OCR.

**Escopo (IN/OUT):**
- **IN:** Função que calcula média de confidence
- **OUT:** Não ajustar por idioma

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _calculate_ocr_quality_score(self, detection_results: List[Dict]) -> float:
      """
      Feature 4: OCR quality score
      
      Usa confidence média do tesseract. OCR confiante indica texto real (não ruído).
      
      Returns: 0.0-1.0
      """
      if not detection_results:
          return 0.0
      
      ocr_confs = [r.get('ocr_conf', 0) for r in detection_results if r.get('has_text', False)]
      
      if not ocr_confs:
          return 0.0
      
      avg_conf = sum(ocr_confs) / len(ocr_confs)
      
      # Tesseract retorna 0-100, normalizar para 0-1
      score = avg_conf / 100.0
      
      return score
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna 0.0 se conf=0
- [ ] Retorna 0.5 se conf=50
- [ ] Retorna 1.0 se conf=100
- [ ] Range: 0.0-1.0

**Testes:**
- Unit: `tests/test_video_validator.py::test_ocr_quality_score_calculation()`

**Observabilidade:**
- Log: `logger.debug("ocr_quality_score", score=..., avg_conf=...)`

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-051

---

<a name="s-053"></a>
## S-053: Implementar weighted_sum de confidence

**Objetivo:** Implementar cálculo final de confidence como weighted sum das 4 features.

**Escopo (IN/OUT):**
- **IN:** Função `_calculate_confidence(detection_results) -> float`
- **OUT:** Não adicionar novas features

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _calculate_confidence(self, detection_results: List[Dict]) -> float:
      """
      Calcula confidence de forma determinística
      
      Formula: weighted_sum de 4 features
      - persistence: % frames com texto
      - bbox: centralizado + altura típica
      - char_count: texto >= 5 chars
      - ocr_quality: conf média tesseract
      
      Returns: 0.0-1.0
      """
      if not detection_results:
          return 0.0
      
      # Feature 1: Persistence
      persistence_score = self._calculate_persistence_score(detection_results)
      
      # Feature 2: Bbox (média dos scores de cada frame)
      bbox_scores = [
          self._score_bbox(r['bbox'], r['frame_width'], r['frame_height'])
          for r in detection_results if r.get('has_text', False)
      ]
      bbox_score = sum(bbox_scores) / len(bbox_scores) if bbox_scores else 0.0
      
      # Feature 3: Char count
      char_count_score = self._calculate_char_count_score(detection_results)
      
      # Feature 4: OCR quality
      ocr_quality_score = self._calculate_ocr_quality_score(detection_results)
      
      # Weighted sum (pesos definidos em S-054)
      confidence = (
          persistence_score * self.confidence_weights['persistence'] +
          bbox_score * self.confidence_weights['bbox'] +
          char_count_score * self.confidence_weights['char_count'] +
          ocr_quality_score * self.confidence_weights['ocr_quality']
      )
      
      return confidence
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Calcula as 4 features
- [ ] Aplica pesos
- [ ] Retorna 0.0-1.0
- [ ] Determinístico (mesmos inputs = mesmo output)

**Testes:**
- Unit: `tests/test_video_validator.py::test_confidence_calculation_deterministic()`

**Observabilidade:**
- Log: `logger.info("confidence_calculated", confidence=..., persistence=..., bbox=..., char_count=..., ocr_quality=...)`

**Riscos/Rollback:**
- Risco: Pesos incorretos causam falsos positivos/negativos
- Rollback: Ajustar pesos baseado em validação

**Dependências:** S-049, S-050, S-051, S-052

---

<a name="s-054"></a>
## S-054: Definir pesos (0.35/0.25/0.20/0.20)

**Objetivo:** Definir pesos das features conforme especificado no plano (somam 1.0).

**Escopo (IN/OUT):**
- **IN:** Adicionar atributo `confidence_weights` no `__init__`
- **OUT:** Não ajustar pesos ainda (tuning em S-060+)

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Em `__init__`, adicionar:
  ```python
  # Pesos para cálculo de confidence (somam 1.0)
  self.confidence_weights = {
      'persistence': 0.35,  # % frames com texto em ROI
      'bbox': 0.25,         # Bbox centralizado + altura típica
      'char_count': 0.20,   # Texto >= 5 chars
      'ocr_quality': 0.20   # Conf média tesseract
  }
  ```
- Adicionar assert: `assert sum(self.confidence_weights.values()) == 1.0`

**Critérios de Aceite / Definition of Done:**
- [ ] Pesos somam 1.0
- [ ] Persistence tem maior peso (0.35)
- [ ] Assert valida soma

**Testes:**
- Unit: `tests/test_video_validator.py::test_confidence_weights_sum_to_one()`

**Observabilidade:**
- N/A (configuração)

**Riscos/Rollback:**
- Risco: Pesos subótimos
- Rollback: Ajustar baseado em métricas de precision/recall

**Dependências:** S-053

---

<a name="s-055"></a>
## S-055: Implementar early exit ao detectar legenda

**Objetivo:** Adicionar lógica de early exit: se confiança >0.75 em 3 frames, parar análise (otimização).

**Escopo (IN/OUT):**
- **IN:** Early exit no loop de frames
- **OUT:** Não implementar early exit parcial (apenas completo)

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Em `has_embedded_subtitles()`, no loop de análise de frames, adicionar:
  ```python
  # Early exit: se 3 frames consecutivos têm high confidence, parar
  if len(detection_results) >= 3:
      recent_confs = [r.get('frame_confidence', 0) for r in detection_results[-3:]]
      if all(c > 0.75 for c in recent_confs):
          logger.info("early_exit_triggered", frames_analyzed=len(detection_results))
          break
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Early exit funciona se 3 frames têm conf >0.75
- [ ] Não para se apenas 1-2 frames
- [ ] Log indica early exit
- [ ] Performance melhora (~50% mais rápido em casos positivos)

**Testes:**
- Unit: `tests/test_video_validator.py::test_early_exit_on_high_confidence()`

**Observabilidade:**
- Log: `logger.info("early_exit_triggered", frames_analyzed=3)`
- Métrica: `counter("early_exits_total")`

**Riscos/Rollback:**
- Risco: Early exit perde casos edge
- Rollback: Aumentar threshold para 4 frames ou conf >0.85

**Dependências:** S-054

---

<a name="s-056"></a>
## S-056: Implementar buckets (high >0.75, medium 0.40-0.75, low <0.40)

**Objetivo:** Implementar classificação de confidence em buckets para políticas de decisão.

**Escopo (IN/OUT):**
- **IN:** Função que retorna bucket de confidence
- **OUT:** Não implementar políticas de decisão ainda (sprint 08)

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _get_confidence_bucket(self, confidence: float) -> str:
      """
      Classifica confidence em buckets
      
      - high: >0.75 (bloquear + blacklist)
      - medium: 0.40-0.75 (soft-block, zona cinza)
      - low: <0.40 (permitir)
      """
      if confidence > 0.75:
          return "high"
      elif confidence >= 0.40:
          return "medium"
      else:
          return "low"
  ```
- Em `has_embedded_subtitles()`, adicionar ao detection_info: `'confidence_bucket': self._get_confidence_bucket(confidence)`

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna "high" se >0.75
- [ ] Retorna "medium" se 0.40-0.75
- [ ] Retorna "low" se <0.40
- [ ] Bucket adicionado ao detection_info

**Testes:**
- Unit: `tests/test_video_validator.py::test_confidence_buckets()`

**Observabilidade:**
- Log: `logger.info("confidence_bucket", bucket="...", confidence=...)`

**Riscos/Rollback:**
- Risco: Thresholds incorretos
- Rollback: Ajustar thresholds via config

**Dependências:** S-055

---

<a name="s-057"></a>
## S-057: Implementar análise completa de frame em ROI

**Objetivo:** Completar implementação do loop de análise de frames em `has_embedded_subtitles()`.

**Escopo (IN/OUT):**
- **IN:** Análise frame-by-frame com OCR em ROI
- **OUT:** Não otimizar com paralelização ainda

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Substituir `# TODO` em `has_embedded_subtitles()` por:
  ```python
  for frame in frames:
      # Downscale
      frame = self._downscale_frame(frame)
      
      # Analisar ROI bottom (legendas inferiores)
      roi = self._crop_roi(frame, self.roi_bottom, self.roi_horizontal)
      gray = self._to_grayscale(roi)
      binary = self._apply_threshold(gray)
      
      # OCR
      text, ocr_conf = self._run_ocr(binary)
      
      # Filtrar ruído
      has_text = len(text) >= self.min_text_threshold
      
      if has_text:
          # Extrair bbox do texto
          bbox = self._get_text_bbox_from_text(binary)  # Helper a criar
          
          frame_result = {
              'has_text': True,
              'text': text,
              'char_count': len(text),
              'ocr_conf': ocr_conf,
              'bbox': bbox,
              'frame_width': frame.shape[1],
              'frame_height': frame.shape[0],
              'frame_confidence': self._score_bbox(bbox, frame.shape[1], frame.shape[0])
          }
      else:
          frame_result = {'has_text': False}
      
      detection_results.append(frame_result)
      
      # Early exit check (S-055)
      # ...
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Loop completo implementado
- [ ] OCR executado em cada frame
- [ ] Resultados armazenados em detection_results
- [ ] Filtro de min_text_threshold aplicado

**Testes:**
- Integration: `tests/test_video_validator.py::test_analysis_loop_completes()`

**Observabilidade:**
- Log: `logger.debug("frame_analyzed", frame_index=i, has_text=..., char_count=...)`

**Riscos/Rollback:**
- Risco: Loop lento (>10s)
- Rollback: Adicionar timeout de 10s total

**Dependências:** S-045, S-049-S-056

---

<a name="s-058"></a>
## S-058: Adicionar filtro de min_text_threshold (5 chars)

**Objetivo:** Garantir que texto com <5 caracteres é ignorado (provavelmente ruído/artefato).

**Escopo (IN/OUT):**
- **IN:** Validar que filtro é aplicado antes de marcar has_text=True
- **OUT:** Não ajustar threshold dinamicamente

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Verificar em `has_embedded_subtitles()` que: `has_text = len(text) >= self.min_text_threshold` (já implementado em S-057)
- Adicionar teste que valida filtro funciona

**Critérios de Aceite / Definition of Done:**
- [ ] Texto "abc" (3 chars) não marca has_text=True
- [ ] Texto "abcde" (5 chars) marca has_text=True
- [ ] Threshold configurável (5 por padrão)

**Testes:**
- Unit: `tests/test_video_validator.py::test_min_text_threshold_filters_noise()`

**Observabilidade:**
- Log: `logger.debug("text_filtered", text_length=len(text), threshold=self.min_text_threshold)`

**Riscos/Rollback:**
- Risco: Threshold 5 pode ser alto (perde legendas curtas)
- Rollback: Reduzir para 3 chars

**Dependências:** S-057

---

<a name="s-059"></a>
## S-059: Implementar confidence_breakdown para debug

**Objetivo:** Criar função que retorna breakdown detalhado dos scores para debugging.

**Escopo (IN/OUT):**
- **IN:** Função que retorna dict com scores individuais
- **OUT:** Não adicionar ao detection_info em produção (apenas debug)

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _get_confidence_breakdown(self, detection_results: List[Dict]) -> Dict:
      """Retorna breakdown dos scores para debug"""
      if not detection_results:
          return {}
      
      return {
          'persistence_score': self._calculate_persistence_score(detection_results),
          'bbox_score': sum([
              self._score_bbox(r['bbox'], r['frame_width'], r['frame_height'])
              for r in detection_results if r.get('has_text', False)
          ]) / max(1, sum(1 for r in detection_results if r.get('has_text', False))),
          'char_count_score': self._calculate_char_count_score(detection_results),
          'ocr_quality_score': self._calculate_ocr_quality_score(detection_results),
          'weights': self.confidence_weights
      }
  ```
- Em `has_embedded_subtitles()`, adicionar a detection_info: `'confidence_breakdown': self._get_confidence_breakdown(detection_results)`

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna dict com 5 keys (4 scores + weights)
- [ ] Scores estão no range 0.0-1.0
- [ ] Adicionado ao detection_info

**Testes:**
- Unit: `tests/test_video_validator.py::test_confidence_breakdown_structure()`

**Observabilidade:**
- Log: `logger.debug("confidence_breakdown", breakdown=...)`

**Riscos/Rollback:**
- Risco: Aumenta verbosidade dos logs
- Rollback: Remover de detection_info, disponibilizar apenas via debug flag

**Dependências:** S-053

---

<a name="s-060"></a>
## S-060: Criar testes com vídeo COM legendas

**Objetivo:** Criar fixture de vídeo com legendas embutidas e validar que detector retorna True com confidence >0.75.

**Escopo (IN/OUT):**
- **IN:** Fixture `video_with_subtitles`, teste de detecção
- **OUT:** Não usar vídeos reais (sintéticos)

**Arquivos tocados:**
- `services/make-video/conftest.py`
- `services/make-video/tests/test_video_validator.py`

**Mudanças exatas:**
- Em `conftest.py`, criar fixture:
  ```python
  @pytest.fixture
  def video_with_subtitles(tmp_path):
      # Gerar vídeo com texto embutido usando FFmpeg drawtext
      output = tmp_path / "with_subs.mp4"
      cmd = [
          'ffmpeg', '-f', 'lavfi', '-i', 'color=c=black:s=1280x720:d=10',
          '-vf', "drawtext=text='TEST SUBTITLE':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=h*0.8",
          '-pix_fmt', 'yuv420p', str(output)
      ]
      subprocess.run(cmd, check=True, capture_output=True)
      return str(output)
  ```
- Teste:
  ```python
  def test_detects_embedded_subtitles(video_with_subtitles):
      validator = VideoValidator()
      has_subs, info, confidence = validator.has_embedded_subtitles(video_with_subtitles)
      
      assert has_subs == True
      assert confidence > 0.75
      assert info['confidence_bucket'] == 'high'
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Fixture gera vídeo com texto
- [ ] Detector retorna True
- [ ] Confidence >0.75
- [ ] Teste passa

**Testes:**
- Self-test: `pytest tests/test_video_validator.py::test_detects_embedded_subtitles -v`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: FFmpeg drawtext não disponível
- Rollback: Usar vídeo pré-gerado commitado

**Dependências:** S-057, S-053

---

<a name="s-061"></a>
## S-061: Criar testes com vídeo SEM legendas

**Objetivo:** Criar fixture de vídeo limpo (sem texto) e validar que detector retorna False.

**Escopo (IN/OUT):**
- **IN:** Fixture `video_without_subtitles`, teste de não-detecção
- **OUT:** Não testar vídeos com texto não-legenda (logo, etc)

**Arquivos tocados:**
- `services/make-video/conftest.py`
- `services/make-video/tests/test_video_validator.py`

**Mudanças exatas:**
- Em `conftest.py`, criar fixture:
  ```python
  @pytest.fixture
  def video_without_subtitles(tmp_path):
      # Gerar vídeo sem texto
      output = tmp_path / "without_subs.mp4"
      cmd = [
          'ffmpeg', '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720:d=10',
          '-pix_fmt', 'yuv420p', str(output)
      ]
      subprocess.run(cmd, check=True, capture_output=True)
      return str(output)
  ```
- Teste:
  ```python
  def test_does_not_detect_on_clean_video(video_without_subtitles):
      validator = VideoValidator()
      has_subs, info, confidence = validator.has_embedded_subtitles(video_without_subtitles)
      
      assert has_subs == False
      assert confidence < 0.40
      assert info['confidence_bucket'] == 'low'
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Fixture gera vídeo limpo
- [ ] Detector retorna False
- [ ] Confidence <0.40
- [ ] Teste passa

**Testes:**
- Self-test: `pytest tests/test_video_validator.py::test_does_not_detect_on_clean_video -v`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: OCR detecta ruído como texto (falso positivo)
- Rollback: Ajustar min_text_threshold

**Dependências:** S-060

---

<a name="s-062"></a>
## S-062: Criar testes de confidence calculation

**Objetivo:** Criar testes unitários que validam cálculo de confidence com inputs sintéticos.

**Escopo (IN/OUT):**
- **IN:** Testes com detection_results mock
- **OUT:** Não testar com vídeos reais

**Arquivos tocados:**
- `services/make-video/tests/test_video_validator.py`

**Mudanças exatas:**
- Teste 1: Todos scores altos
  ```python
  def test_confidence_high_when_all_features_high():
      validator = VideoValidator()
      
      # Mock: 5 frames, todos com texto bom
      detection_results = [
          {
              'has_text': True,
              'char_count': 15,
              'ocr_conf': 90,
              'bbox': {'x': 400, 'x2': 600, 'y': 500, 'y2': 550},
              'frame_width': 1000,
              'frame_height': 720
          }
      ] * 5
      
      confidence = validator._calculate_confidence(detection_results)
      assert confidence > 0.75
  ```
- Teste 2: Scores médios
- Teste 3: Scores baixos

**Critérios de Aceite / Definition of Done:**
- [ ] 3 testes criados (high/medium/low)
- [ ] Todos passam
- [ ] Validam ranges de confidence

**Testes:**
- Self-test: `pytest tests/test_video_validator.py::test_confidence_* -v`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-053, S-059

---

## Mapa de Dependências (Pack 05)

```
S-049 (persistence) → S-053
S-050 (bbox) → S-053
S-051 (char_count) → S-053
S-052 (ocr_quality) → S-053
S-053 (weighted_sum) → S-054, S-059, S-062
S-054 (pesos) → S-055
S-055 (early exit) → S-056
S-056 (buckets) → S-057
S-057 (análise completa) → S-058, S-060
S-058 (filtro threshold) ← S-057
S-059 (breakdown) ← S-053
S-060 (teste COM legendas) ← S-057, S-053
S-061 (teste SEM legendas) ← S-060
S-062 (teste confidence) ← S-053, S-059
```

**Próximo pack:** Sprint 06 - ShortsBlacklist JSON (locking, atomic write, TTL, mtime, retry)
