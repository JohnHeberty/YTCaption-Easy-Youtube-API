# Sprint Pack 04/12 - VideoValidator Base (Frame Extraction & OCR)

**Escopo deste pack:** Implementar fundação do `VideoValidator`: extração de frames, downscale para 360p, definição de ROI (region of interest), integração com pytesseract OCR. Este pack NÃO inclui heurísticas de confidence (pack 05).

## Índice

- [S-037: Criar classe VideoValidator (esqueleto)](#s-037)
- [S-038: Implementar extração de frames com FFmpeg](#s-038)
- [S-039: Implementar downscale para 360p](#s-039)
- [S-040: Definir ROIs (bottom 70-95%, center 40-60%)](#s-040)
- [S-041: Implementar crop de ROI em frame](#s-041)
- [S-042: Integrar pytesseract OCR](#s-042)
- [S-043: Implementar conversão para grayscale](#s-043)
- [S-044: Implementar threshold adaptativo](#s-044)
- [S-045: Criar função has_embedded_subtitles (esqueleto)](#s-045)
- [S-046: Implementar sample_interval de 2s](#s-046)
- [S-047: Implementar max_frames de 6 frames](#s-047)
- [S-048: Adicionar teste de extração de frame](#s-048)

---

<a name="s-037"></a>
## S-037: Criar classe VideoValidator (esqueleto)

**Objetivo:** Criar estrutura da classe `VideoValidator` com docstring completa e atributos de configuração.

**Escopo (IN/OUT):**
- **IN:** Classe, `__init__`, docstring, atributos de config
- **OUT:** Não implementar métodos ainda

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Adicionar imports: `import cv2`, `import numpy as np`, `import pytesseract`, `from PIL import Image`
- Criar classe:
  ```python
  class VideoValidator:
      """
      Valida vídeos quanto a LEGENDAS embutidas (não texto genérico)
      
      Estratégia:
      - ROI (region of interest): faixa inferior/central onde legendas aparecem
      - Persistência temporal: texto em múltiplos frames na mesma posição
      - Heurística de bbox: texto centralizado horizontalmente
      - Confidence determinístico: weighted_sum de 4 features (implementado em pack 05)
      """
      
      def __init__(self, monitor_only: bool = False):
          self.ocr = pytesseract
          self.min_text_threshold = 5  # Mínimo de caracteres
          self.sample_interval = 2.0  # Segundos entre amostras
          self.max_frames = 6  # Máximo de frames
          self.monitor_only = monitor_only
          
          # ROI: onde legendas costumam aparecer
          self.roi_bottom = (0.70, 0.95)  # 70-95% da altura
          self.roi_center = (0.40, 0.60)  # 40-60% da altura
          self.roi_horizontal = (0.10, 0.90)  # 10-90% da largura
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Classe criada com docstring completa
- [ ] 7 atributos definidos em `__init__`
- [ ] Valores default corretos (sample_interval=2.0, max_frames=6)
- [ ] ROIs definidos como tuplas

**Testes:**
- Unit: `tests/test_video_validator.py::test_validator_initialization()`
- Assert: `validator.sample_interval == 2.0`

**Observabilidade:**
- N/A (estrutura)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-004 (deps instaladas)

---

<a name="s-038"></a>
## S-038: Implementar extração de frames com FFmpeg

**Objetivo:** Criar método que extrai frames de vídeo em intervalos regulares usando FFmpeg.

**Escopo (IN/OUT):**
- **IN:** Método `_extract_frames(video_path, max_frames, interval) -> List[np.ndarray]`
- **OUT:** Não aplicar ROI ainda

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _extract_frames(self, video_path: str) -> List[np.ndarray]:
      """Extrai frames em intervalos regulares"""
      frames = []
      
      # Obter duração do vídeo
      duration = self._get_video_duration(video_path)
      
      # Calcular timestamps
      num_samples = min(self.max_frames, int(duration / self.sample_interval) + 1)
      timestamps = [i * self.sample_interval for i in range(num_samples)]
      
      for ts in timestamps:
          frame = self._extract_frame_at(video_path, ts)
          if frame is not None:
              frames.append(frame)
          
          if len(frames) >= self.max_frames:
              break  # Early exit
      
      return frames
  ```
- Criar helper: `def _get_video_duration(self, video_path: str) -> float` (usar ffprobe)
- Criar helper: `def _extract_frame_at(self, video_path: str, timestamp: float) -> np.ndarray` (usar FFmpeg)

**Critérios de Aceite / Definition of Done:**
- [ ] Extrai até max_frames (6) frames
- [ ] Respeita sample_interval (2s)
- [ ] Early exit funciona
- [ ] Retorna lista de np.ndarray

**Testes:**
- Unit: `tests/test_video_validator.py::test_extract_frames_count()`
- Unit: `tests/test_video_validator.py::test_extract_frames_interval()`

**Observabilidade:**
- Log: `logger.debug("frames_extracted", count=len(frames), duration=duration)`

**Riscos/Rollback:**
- Risco: FFmpeg falha em vídeos raros
- Rollback: Try/except e continuar com frames disponíveis

**Dependências:** S-037

---

<a name="s-039"></a>
## S-039: Implementar downscale para 360p

**Objetivo:** Adicionar downscale de frames para 360p (640x360) para reduzir custo de OCR.

**Escopo (IN/OUT):**
- **IN:** Downscale após extração, antes de ROI
- **OUT:** Não aplicar filtros de qualidade ainda

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _downscale_frame(self, frame: np.ndarray, target_height: int = 360) -> np.ndarray:
      """Downscale frame para reduzir custo de OCR"""
      height, width = frame.shape[:2]
      
      if height <= target_height:
          return frame  # Já pequeno
      
      scale = target_height / height
      new_width = int(width * scale)
      
      resized = cv2.resize(frame, (new_width, target_height), interpolation=cv2.INTER_AREA)
      return resized
  ```
- Em `_extract_frames()`, adicionar após extrair: `frame = self._downscale_frame(frame)`

**Critérios de Aceite / Definition of Done:**
- [ ] Frames downscaled para 360p altura
- [ ] Aspect ratio preservado
- [ ] Interpolação INTER_AREA usada (melhor qualidade)
- [ ] Frames já pequenos não são redimensionados

**Testes:**
- Unit: `tests/test_video_validator.py::test_downscale_to_360p()`
- Assert: `downscaled.shape[0] == 360`

**Observabilidade:**
- Log: `logger.debug("frame_downscaled", original_size=(h,w), new_size=(new_h,new_w))`

**Riscos/Rollback:**
- Risco: Downscale degrada OCR
- Rollback: Aumentar target para 480p ou 720p

**Dependências:** S-038

---

<a name="s-040"></a>
## S-040: Definir ROIs (bottom 70-95%, center 40-60%)

**Objetivo:** Documentar e validar definição de ROIs onde legendas tipicamente aparecem.

**Escopo (IN/OUT):**
- **IN:** Comentários e docstring explicando ROIs
- **OUT:** Não implementar crop ainda (próxima sprint)

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Atualizar docstring de `__init__` com explicação de ROIs:
  ```python
  # ROI: onde legendas costumam aparecer
  # Bottom: 70-95% da altura (legendas inferiores - comum em YouTube)
  # Center: 40-60% da altura (legendas centralizadas - menos comum)
  # Horizontal: 10-90% da largura (centralizado, ignora bordas)
  self.roi_bottom = (0.70, 0.95)
  self.roi_center = (0.40, 0.60)
  self.roi_horizontal = (0.10, 0.90)
  ```
- Adicionar comentário: `# ROIs são frações da altura/largura do frame`

**Critérios de Aceite / Definition of Done:**
- [ ] ROIs documentados com comentários
- [ ] Valores em fração (0.0-1.0)
- [ ] Bottom e center definidos
- [ ] Horizontal definido

**Testes:**
- Unit: `tests/test_video_validator.py::test_rois_are_fractions()`
- Assert: `0 < validator.roi_bottom[0] < 1`

**Observabilidade:**
- N/A (configuração)

**Riscos/Rollback:**
- Risco: ROIs não cobrem todas posições de legendas
- Rollback: Ajustar valores baseado em análise de vídeos reais

**Dependências:** S-037

---

<a name="s-041"></a>
## S-041: Implementar crop de ROI em frame

**Objetivo:** Criar método que recorta frame em ROI específico.

**Escopo (IN/OUT):**
- **IN:** Método `_crop_roi(frame, roi_vertical, roi_horizontal) -> np.ndarray`
- **OUT:** Não aplicar a múltiplos ROIs ainda

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _crop_roi(self, frame: np.ndarray, roi_vertical: tuple, roi_horizontal: tuple) -> np.ndarray:
      """Crop frame em ROI específico"""
      height, width = frame.shape[:2]
      
      # Calcular coordenadas
      y1 = int(height * roi_vertical[0])
      y2 = int(height * roi_vertical[1])
      x1 = int(width * roi_horizontal[0])
      x2 = int(width * roi_horizontal[1])
      
      # Crop
      cropped = frame[y1:y2, x1:x2]
      return cropped
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Crop funciona corretamente
- [ ] Coordenadas calculadas de frações
- [ ] Retorna sub-array do frame
- [ ] Não falha com frames pequenos

**Testes:**
- Unit: `tests/test_video_validator.py::test_crop_roi_dimensions()`
- Assert: `cropped.shape[0] < original.shape[0]`

**Observabilidade:**
- Log: `logger.debug("roi_cropped", original_size=(h,w), cropped_size=(ch,cw))`

**Riscos/Rollback:**
- Risco: Coordenadas fora de bounds
- Rollback: Adicionar clamp (min/max)

**Dependências:** S-040

---

<a name="s-042"></a>
## S-042: Integrar pytesseract OCR

**Objetivo:** Criar método que executa OCR em frame/ROI usando pytesseract.

**Escopo (IN/OUT):**
- **IN:** Método `_run_ocr(frame) -> tuple[str, float]` (texto, confidence)
- **OUT:** Não filtrar resultados ainda

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _run_ocr(self, frame: np.ndarray) -> tuple[str, float]:
      """Executa OCR e retorna texto + confidence média"""
      try:
          # pytesseract retorna dict com info detalhada
          data = pytesseract.image_to_data(frame, output_type=pytesseract.Output.DICT, lang='por+eng')
          
          # Filtrar palavras com confidence >0
          texts = []
          confidences = []
          for i, conf in enumerate(data['conf']):
              if conf > 0:
                  texts.append(data['text'][i])
                  confidences.append(conf)
          
          text = ' '.join(texts).strip()
          avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
          
          return text, avg_conf
      except Exception as e:
          logger.error(f"OCR failed: {e}")
          return "", 0.0
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] OCR executa sem travar
- [ ] Retorna tupla (texto, confidence)
- [ ] Confidence é média dos valores válidos
- [ ] Erros capturados e logados

**Testes:**
- Unit: `tests/test_video_validator.py::test_ocr_on_text_frame()`
- Unit: `tests/test_video_validator.py::test_ocr_on_empty_frame()`

**Observabilidade:**
- Log: `logger.debug("ocr_completed", text_length=len(text), confidence=avg_conf)`

**Riscos/Rollback:**
- Risco: OCR muito lento
- Rollback: Adicionar timeout de 2s por frame

**Dependências:** S-041

---

<a name="s-043"></a>
## S-043: Implementar conversão para grayscale

**Objetivo:** Adicionar conversão de frame para grayscale antes de OCR, melhorando acurácia.

**Escopo (IN/OUT):**
- **IN:** Converter frame RGB para grayscale
- **OUT:** Não aplicar outros filtros ainda

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _to_grayscale(self, frame: np.ndarray) -> np.ndarray:
      """Converte frame para grayscale"""
      if len(frame.shape) == 2:
          return frame  # Já é grayscale
      
      gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
      return gray
  ```
- Em `_run_ocr()`, adicionar antes de pytesseract: `frame = self._to_grayscale(frame)`

**Critérios de Aceite / Definition of Done:**
- [ ] Frame convertido para 1 canal (grayscale)
- [ ] Frames já grayscale não são reprocessados
- [ ] OCR funciona com frame grayscale

**Testes:**
- Unit: `tests/test_video_validator.py::test_to_grayscale_conversion()`
- Assert: `len(gray.shape) == 2`

**Observabilidade:**
- N/A (preprocessing)

**Riscos/Rollback:**
- Risco: Grayscale piora OCR em alguns casos
- Rollback: Testar com RGB também

**Dependências:** S-042

---

<a name="s-044"></a>
## S-044: Implementar threshold adaptativo

**Objetivo:** Adicionar threshold adaptativo para melhorar contraste antes de OCR.

**Escopo (IN/OUT):**
- **IN:** Aplicar `cv2.adaptiveThreshold` em frame grayscale
- **OUT:** Não testar múltiplos métodos de threshold

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _apply_threshold(self, gray_frame: np.ndarray) -> np.ndarray:
      """Aplica threshold adaptativo para melhorar contraste"""
      # Threshold adaptativo: melhor para iluminação variável
      binary = cv2.adaptiveThreshold(
          gray_frame,
          255,
          cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
          cv2.THRESH_BINARY,
          blockSize=11,
          C=2
      )
      return binary
  ```
- Em `_run_ocr()`, adicionar após grayscale: `frame = self._apply_threshold(frame)`

**Critérios de Aceite / Definition of Done:**
- [ ] Threshold aplicado em frame grayscale
- [ ] Resultado é frame binário (0 ou 255)
- [ ] OCR funciona com frame binarizado

**Testes:**
- Unit: `tests/test_video_validator.py::test_apply_threshold_creates_binary()`
- Assert: `np.all(np.isin(binary, [0, 255]))`

**Observabilidade:**
- N/A (preprocessing)

**Riscos/Rollback:**
- Risco: Threshold pode remover texto tênue
- Rollback: Testar sem threshold também

**Dependências:** S-043

---

<a name="s-045"></a>
## S-045: Criar função has_embedded_subtitles (esqueleto)

**Objetivo:** Criar estrutura da função principal que detecta legendas, sem implementar lógica completa ainda.

**Escopo (IN/OUT):**
- **IN:** Assinatura da função, docstring, estrutura básica
- **OUT:** Não implementar detecção completa (pack 05)

**Arquivos tocados:**
- `services/make-video/app/video_validator.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def has_embedded_subtitles(self, video_path: str) -> tuple[bool, dict, float]:
      """
      Detecta se vídeo possui LEGENDAS embutidas (sync - CPU-bound)
      
      Returns:
          (has_subtitles: bool, detection_info: dict, confidence: float)
          
      Confidence levels:
          >0.75: Alta confiança (bloquear + blacklist)
          0.40-0.75: Zona cinza (soft-block, não cacheia)
          <0.40: Baixa confiança (permitir)
      """
      logger.info("subtitle_detection_started", video_path=video_path)
      
      # 1. Extrair frames
      frames = self._extract_frames(video_path)
      
      # 2. Analisar cada frame em ROI (implementado em pack 05)
      detection_results = []
      for frame in frames:
          # TODO: implementar análise completa
          pass
      
      # 3. Calcular confidence (implementado em pack 05)
      confidence = 0.0  # Placeholder
      
      has_subtitles = confidence > 0.40
      
      detection_info = {
          'frames_analyzed': len(frames),
          'confidence': confidence
      }
      
      return has_subtitles, detection_info, confidence
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Função criada com docstring completa
- [ ] Extrai frames
- [ ] Retorna tupla (bool, dict, float)
- [ ] Placeholder para lógica futura

**Testes:**
- Unit: `tests/test_video_validator.py::test_has_embedded_subtitles_structure()`
- Assert: retorno é tupla de 3 elementos

**Observabilidade:**
- Log: `logger.info("subtitle_detection_started", video_path="...")`

**Riscos/Rollback:**
- Risco: Nenhum (apenas estrutura)
- Rollback: N/A

**Dependências:** S-038, S-039, S-041, S-042, S-043, S-044

---

<a name="s-046"></a>
## S-046: Implementar sample_interval de 2s

**Objetivo:** Garantir que frames são extraídos a cada 2 segundos, conforme configurado.

**Escopo (IN/OUT):**
- **IN:** Validar que sample_interval é respeitado
- **OUT:** Não ajustar intervalo dinamicamente

**Arquivos tocados:**
- `services/make-video/app/video_validator.py` (já implementado em S-038, validar)

**Mudanças exatas:**
- Verificar que em `_extract_frames()`, timestamps são calculados como: `[0, 2, 4, 6, 8, 10]` para vídeo 12s
- Adicionar assert: `assert timestamps[i+1] - timestamps[i] == self.sample_interval`

**Critérios de Aceite / Definition of Done:**
- [ ] Intervalo de 2s entre frames
- [ ] Primeiro frame em 0s
- [ ] Último frame não excede duração do vídeo

**Testes:**
- Unit: `tests/test_video_validator.py::test_sample_interval_respected()`

**Observabilidade:**
- Log: `logger.debug("frame_timestamps", timestamps=timestamps)`

**Riscos/Rollback:**
- Risco: Intervalo muito largo perde legendas breves
- Rollback: Reduzir para 1s via config

**Dependências:** S-038

---

<a name="s-047"></a>
## S-047: Implementar max_frames de 6 frames

**Objetivo:** Garantir early exit após 6 frames para evitar processamento excessivo.

**Escopo (IN/OUT):**
- **IN:** Validar que nunca extrai >6 frames
- **OUT:** Não ajustar max_frames dinamicamente

**Arquivos tocados:**
- `services/make-video/app/video_validator.py` (já implementado em S-038, validar)

**Mudanças exatas:**
- Verificar que em `_extract_frames()`, loop tem: `if len(frames) >= self.max_frames: break`
- Adicionar teste que fornece vídeo 60s e valida que só extrai 6 frames

**Critérios de Aceite / Definition of Done:**
- [ ] Máximo 6 frames extraídos
- [ ] Early exit funciona
- [ ] Performance aceitável (<2s para 6 frames)

**Testes:**
- Unit: `tests/test_video_validator.py::test_max_frames_enforced()`

**Observabilidade:**
- Log: `logger.debug("frames_extracted", count=len(frames), max_frames=self.max_frames)`

**Riscos/Rollback:**
- Risco: 6 frames insuficientes para vídeos longos
- Rollback: Aumentar para 10 frames

**Dependências:** S-038

---

<a name="s-048"></a>
## S-048: Adicionar teste de extração de frame

**Objetivo:** Criar teste end-to-end que valida pipeline completo de extração até OCR.

**Escopo (IN/OUT):**
- **IN:** Teste que extrai frame, aplica ROI, roda OCR
- **OUT:** Não testar detecção completa ainda

**Arquivos tocados:**
- `services/make-video/tests/test_video_validator.py`

**Mudanças exatas:**
- Criar teste:
  ```python
  def test_frame_extraction_pipeline(sample_video):
      validator = VideoValidator()
      
      # Extrair frames
      frames = validator._extract_frames(sample_video)
      assert len(frames) > 0
      
      # Pegar primeiro frame
      frame = frames[0]
      
      # Downscale
      downscaled = validator._downscale_frame(frame)
      assert downscaled.shape[0] == 360
      
      # Crop ROI
      roi = validator._crop_roi(downscaled, validator.roi_bottom, validator.roi_horizontal)
      assert roi.shape[0] < downscaled.shape[0]
      
      # Grayscale
      gray = validator._to_grayscale(roi)
      assert len(gray.shape) == 2
      
      # Threshold
      binary = validator._apply_threshold(gray)
      
      # OCR
      text, conf = validator._run_ocr(binary)
      # Não validar conteúdo, apenas que não falha
      assert isinstance(text, str)
      assert isinstance(conf, float)
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Pipeline completo executado
- [ ] Cada etapa validada
- [ ] Teste passa com sample_video
- [ ] Não falha com exceção

**Testes:**
- Self-test: `pytest tests/test_video_validator.py::test_frame_extraction_pipeline -v`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Teste lento (>5s)
- Rollback: Usar vídeo menor

**Dependências:** S-038 a S-045

---

## Mapa de Dependências (Pack 04)

```
S-037 (classe) → S-038, S-040
S-038 (extract frames) → S-039, S-046, S-047
S-039 (downscale) → S-041
S-040 (definir ROI) → S-041
S-041 (crop ROI) → S-042
S-042 (OCR) → S-043
S-043 (grayscale) → S-044
S-044 (threshold) → S-045
S-045 (has_embedded esqueleto) ← S-038, S-039, S-041, S-042, S-043, S-044
S-046 (sample_interval) ← S-038
S-047 (max_frames) ← S-038
S-048 (teste pipeline) ← S-038 a S-045
```

**Próximo pack:** Sprint 05 - VideoValidator heurísticas & confidence determinístico
