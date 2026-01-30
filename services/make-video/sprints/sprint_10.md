# Sprint Pack 10/12 - VAD Fallbacks + Validation

**Escopo deste pack:** Implementar fallbacks alternativos para VAD (webrtcvad, RMS), helper _convert_to_16k_wav para resample (MUST-FIX v1.6), validate_speech_gating que usa vad_ok condicional, métrica vad_fallback_rate.

## Índice

- [S-113: Implementar _convert_to_16k_wav helper (MUST-FIX)](#s-113)
- [S-114: Integrar resample no detect_speech_segments](#s-114)
- [S-115: Implementar webrtcvad fallback (estrutura)](#s-115)
- [S-116: Implementar RMS energy fallback](#s-116)
- [S-117: Criar fallback chain (silero → webrtc → RMS)](#s-117)
- [S-118: Implementar validate_speech_gating](#s-118)
- [S-119: Adicionar métrica vad_fallback_rate](#s-119)
- [S-120: Criar testes para cada fallback](#s-120)
- [S-121: Validar fallback chain funciona](#s-121)
- [S-122: Atualizar README com fallbacks](#s-122)

---

<a name="s-113"></a>
## S-113: Implementar _convert_to_16k_wav helper (MUST-FIX)

**Objetivo:** Criar helper que converte qualquer áudio para 16kHz mono WAV (MUST-FIX v1.6).

**Escopo (IN/OUT):**
- **IN:** Conversão usando FFmpeg
- **OUT:** Não implementar codec detection

**Arquivos tocados:**
- `services/make-video/app/audio_utils.py`

**Mudanças exatas:**
- Adicionar função:
  ```python
  import subprocess
  import tempfile
  import os
  import logging
  
  logger = logging.getLogger(__name__)
  
  def _convert_to_16k_wav(input_path: str) -> str:
      """
      Converte áudio para 16kHz mono WAV
      
      VAD models (silero, webrtc) requerem 16kHz
      
      Args:
          input_path: Path do áudio original
      
      Returns:
          Path do áudio convertido (arquivo temporário)
      
      Raises:
          subprocess.CalledProcessError: Se FFmpeg falha
      """
      # Criar arquivo temporário
      fd, output_path = tempfile.mkstemp(suffix='_16k.wav')
      os.close(fd)
      
      try:
          # FFmpeg: resample para 16kHz, mono, WAV
          cmd = [
              'ffmpeg',
              '-i', input_path,
              '-ar', '16000',  # sample rate
              '-ac', '1',  # mono
              '-y',  # overwrite
              output_path
          ]
          
          result = subprocess.run(
              cmd,
              capture_output=True,
              text=True,
              timeout=30,
              check=True
          )
          
          logger.info(f"audio_converted_to_16k", input=input_path, output=output_path)
          
          return output_path
      
      except subprocess.CalledProcessError as e:
          logger.error(f"FFmpeg conversion failed: {e.stderr}")
          os.unlink(output_path)
          raise
      
      except Exception as e:
          logger.error(f"Conversion failed: {e}")
          if os.path.exists(output_path):
              os.unlink(output_path)
          raise
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Converte para 16kHz mono WAV
- [ ] Usa FFmpeg
- [ ] Retorna path temporário
- [ ] Limpa arquivo se falha
- [ ] Timeout de 30s

**Testes:**
- Unit: `tests/test_audio_utils.py::test_convert_to_16k_wav_success()`
- Unit: `tests/test_audio_utils.py::test_convert_to_16k_wav_cleanup_on_error()`

**Observabilidade:**
- Log: `logger.info("audio_converted_to_16k", input=..., output=...)`
- Log: `logger.error("conversion_failed", error=...)`

**Riscos/Rollback:**
- Risco: Arquivos temporários não limpos
- Rollback: Adicionar atexit handler

**Dependências:** S-005 (audio_utils)

---

<a name="s-114"></a>
## S-114: Integrar resample no detect_speech_segments

**Objetivo:** Modificar `detect_speech_segments()` para usar `_convert_to_16k_wav()` quando sample rate != 16kHz.

**Escopo (IN/OUT):**
- **IN:** Resample automático
- **OUT:** Não cachear áudios resampleados

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Modificar método:
  ```python
  def detect_speech_segments(self, audio_path: str, min_duration: float = 0.3, merge_gap: float = 0.5) -> Tuple[List[Tuple[float, float]], bool]:
      import torchaudio
      from app.audio_utils import _convert_to_16k_wav
      
      self.load_vad_model()
      
      converted_audio = None
      
      try:
          # Carregar áudio
          waveform, sample_rate = torchaudio.load(audio_path)
          
          # Resample se necessário
          if sample_rate != 16000:
              logger.info(f"Resampling audio: {sample_rate}Hz → 16kHz")
              converted_audio = _convert_to_16k_wav(audio_path)
              waveform, sample_rate = torchaudio.load(converted_audio)
          
          # ... resto da lógica ...
      
      finally:
          # Cleanup de arquivo convertido
          if converted_audio and os.path.exists(converted_audio):
              os.unlink(converted_audio)
              logger.debug(f"Cleaned up converted audio: {converted_audio}")
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Detecta sample rate != 16kHz
- [ ] Chama _convert_to_16k_wav()
- [ ] Usa áudio convertido
- [ ] Cleanup no finally

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_detect_with_resample()`

**Observabilidade:**
- Log: `logger.info("audio_resampled", original_sr=..., target_sr=16000)`

**Riscos/Rollback:**
- Risco: Resample lento causa timeout
- Rollback: Adicionar timeout na conversão

**Dependências:** S-113, S-104

---

<a name="s-115"></a>
## S-115: Implementar webrtcvad fallback (estrutura)

**Objetivo:** Criar método alternativo de VAD usando webrtcvad (mais leve que silero).

**Escopo (IN/OUT):**
- **IN:** Estrutura base do webrtcvad
- **OUT:** Não otimizar parâmetros ainda

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`
- `services/make-video/requirements.txt`

**Mudanças exatas:**
- Em `requirements.txt`, adicionar: `webrtcvad==2.0.10`
- Em `speech_gated_subtitles.py`, adicionar método:
  ```python
  def _detect_speech_webrtcvad(self, audio_path: str) -> List[Tuple[float, float]]:
      """
      Fallback VAD usando webrtcvad (mais leve)
      
      webrtcvad é menos preciso mas mais rápido e confiável
      """
      import webrtcvad
      import wave
      import struct
      from app.audio_utils import _convert_to_16k_wav
      
      # Converter para 16kHz mono WAV
      converted = _convert_to_16k_wav(audio_path)
      
      try:
          vad = webrtcvad.Vad(mode=3)  # mode 3 = most aggressive
          
          # Abrir WAV
          with wave.open(converted, 'rb') as wf:
              sample_rate = wf.getframerate()
              
              if sample_rate != 16000:
                  raise ValueError(f"Expected 16kHz, got {sample_rate}Hz")
              
              # Processar frames de 30ms
              frame_duration_ms = 30
              frame_size = int(sample_rate * frame_duration_ms / 1000) * 2  # 2 bytes por sample
              
              segments = []
              speech_start = None
              frame_idx = 0
              
              while True:
                  frame = wf.readframes(int(sample_rate * frame_duration_ms / 1000))
                  if len(frame) < frame_size:
                      break
                  
                  is_speech = vad.is_speech(frame, sample_rate)
                  time = frame_idx * frame_duration_ms / 1000.0
                  
                  if is_speech and speech_start is None:
                      speech_start = time
                  elif not is_speech and speech_start is not None:
                      segments.append((speech_start, time))
                      speech_start = None
                  
                  frame_idx += 1
              
              # Fechar último segmento se aberto
              if speech_start is not None:
                  segments.append((speech_start, frame_idx * frame_duration_ms / 1000.0))
          
          logger.info(f"webrtcvad_detected", segments=len(segments))
          return segments
      
      finally:
          if os.path.exists(converted):
              os.unlink(converted)
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] webrtcvad instalado
- [ ] Método implementado
- [ ] Processa frames de 30ms
- [ ] Retorna lista de (start, end)
- [ ] Cleanup de arquivo convertido

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_webrtcvad_fallback()`

**Observabilidade:**
- Log: `logger.info("webrtcvad_detected", segments=...)`

**Riscos/Rollback:**
- Risco: webrtcvad menos preciso que silero
- Rollback: Ajustar mode (1-3)

**Dependências:** S-113, S-004 (requirements)

---

<a name="s-116"></a>
## S-116: Implementar RMS energy fallback

**Objetivo:** Criar método fallback baseado em energia RMS (último recurso).

**Escopo (IN/OUT):**
- **IN:** RMS simples com threshold
- **OUT:** Não implementar spectral features

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Adicionar método:
  ```python
  def _detect_speech_rms(self, audio_path: str, rms_threshold: float = 0.02) -> List[Tuple[float, float]]:
      """
      Fallback VAD usando energia RMS (último recurso)
      
      Muito simples: considera "fala" onde RMS > threshold
      """
      import torchaudio
      import torch
      
      waveform, sample_rate = torchaudio.load(audio_path)
      
      # Converter para mono
      if waveform.shape[0] > 1:
          waveform = torch.mean(waveform, dim=0, keepdim=True)
      
      # Calcular RMS em janelas de 30ms
      window_size = int(sample_rate * 0.03)  # 30ms
      hop_size = window_size // 2  # 50% overlap
      
      segments = []
      speech_start = None
      
      for i in range(0, waveform.shape[1] - window_size, hop_size):
          window = waveform[0, i:i+window_size]
          rms = torch.sqrt(torch.mean(window ** 2)).item()
          
          time = i / sample_rate
          
          if rms > rms_threshold and speech_start is None:
              speech_start = time
          elif rms <= rms_threshold and speech_start is not None:
              segments.append((speech_start, time))
              speech_start = None
      
      # Fechar último segmento
      if speech_start is not None:
          segments.append((speech_start, waveform.shape[1] / sample_rate))
      
      logger.info(f"rms_fallback_detected", segments=len(segments), threshold=rms_threshold)
      return segments
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] RMS calculado em janelas de 30ms
- [ ] Threshold configurável (default 0.02)
- [ ] Retorna segmentos
- [ ] Log indica threshold usado

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_rms_fallback()`

**Observabilidade:**
- Log: `logger.info("rms_fallback_detected", segments=..., threshold=...)`

**Riscos/Rollback:**
- Risco: RMS muito sensível a noise
- Rollback: Aumentar threshold

**Dependências:** S-101

---

<a name="s-117"></a>
## S-117: Criar fallback chain (silero → webrtc → RMS)

**Objetivo:** Implementar cadeia de fallbacks onde cada método tenta se anterior falha.

**Escopo (IN/OUT):**
- **IN:** Chain explícita com try/except
- **OUT:** Não implementar circuit breaker

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Modificar `detect_speech_segments()` para usar chain:
  ```python
  def detect_speech_segments(self, audio_path: str, min_duration: float = 0.3, merge_gap: float = 0.5) -> Tuple[List[Tuple[float, float]], bool]:
      """
      Detecta fala usando fallback chain:
      1. silero-vad (primário)
      2. webrtcvad (secundário)
      3. RMS energy (último recurso)
      """
      segments = []
      method_used = None
      
      # 1. Tentar silero-vad
      try:
          segments = self._detect_speech_silero(audio_path)
          method_used = 'silero'
          logger.info("vad_method_used", method='silero')
      except Exception as e:
          logger.warning(f"silero-vad failed: {e}, trying webrtcvad")
          
          # 2. Fallback: webrtcvad
          try:
              segments = self._detect_speech_webrtcvad(audio_path)
              method_used = 'webrtcvad'
              logger.info("vad_method_used", method='webrtcvad')
          except Exception as e2:
              logger.warning(f"webrtcvad failed: {e2}, trying RMS fallback")
              
              # 3. Último recurso: RMS
              try:
                  segments = self._detect_speech_rms(audio_path)
                  method_used = 'rms'
                  logger.info("vad_method_used", method='rms')
              except Exception as e3:
                  logger.error(f"All VAD methods failed: {e3}")
                  return [], False
      
      # Aplicar min_duration, merge_gap, clamp (código existente)
      # ...
      
      # Registrar método usado
      vad_method_used.labels(method=method_used).inc()
      
      return segments, True
  ```
- Separar lógica silero para `_detect_speech_silero()` (refactor do código existente)

**Critérios de Aceite / Definition of Done:**
- [ ] 3 métodos tentados em ordem
- [ ] Fallback automático se anterior falha
- [ ] Log indica método usado
- [ ] Retorna ([], False) se todos falharem

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_fallback_chain_silero_success()`
- Unit: `tests/test_speech_gated_subtitles.py::test_fallback_chain_webrtc_fallback()`
- Unit: `tests/test_speech_gated_subtitles.py::test_fallback_chain_rms_last_resort()`
- Unit: `tests/test_speech_gated_subtitles.py::test_fallback_chain_all_fail()`

**Observabilidade:**
- Log: `logger.info("vad_method_used", method="silero"|"webrtcvad"|"rms")`
- Log: `logger.warning("vad_fallback", from_method=..., to_method=...)`
- Métrica: `counter("vad_method_used_total", tags={"method": ...})`

**Riscos/Rollback:**
- Risco: Fallbacks adicionam latência
- Rollback: Adicionar timeout global

**Dependências:** S-104, S-115, S-116

---

<a name="s-118"></a>
## S-118: Implementar validate_speech_gating

**Objetivo:** Criar função que valida se speech gating deve ser aplicado baseado em vad_ok.

**Escopo (IN/OUT):**
- **IN:** Validação condicional com feature flag
- **OUT:** Não implementar A/B testing

**Arquivos tocados:**
- `services/make-video/app/celery_tasks.py`
- `services/make-video/app/config.py`

**Mudanças exatas:**
- Em `config.py`, adicionar:
  ```python
  # Speech gating
  ENABLE_SPEECH_GATING = os.getenv('ENABLE_SPEECH_GATING', 'true').lower() == 'true'
  REQUIRE_VAD_SUCCESS = os.getenv('REQUIRE_VAD_SUCCESS', 'false').lower() == 'true'
  ```
- Em `celery_tasks.py`, criar função:
  ```python
  from app.speech_gated_subtitles import SpeechGatedSubtitles
  from app.config import ENABLE_SPEECH_GATING, REQUIRE_VAD_SUCCESS
  
  def validate_speech_gating(subtitles: list, audio_path: str) -> list:
      """
      Valida e aplica speech gating se habilitado
      
      Args:
          subtitles: Lista de legendas
          audio_path: Path do áudio extraído
      
      Returns:
          Legendas filtradas (ou originais se VAD falha e REQUIRE_VAD_SUCCESS=false)
      """
      if not ENABLE_SPEECH_GATING:
          logger.info("speech_gating_disabled")
          return subtitles
      
      gater = SpeechGatedSubtitles()
      
      # Detectar segmentos de fala
      segments, vad_ok = gater.detect_speech_segments(audio_path)
      
      if not vad_ok:
          if REQUIRE_VAD_SUCCESS:
              logger.error("VAD failed and REQUIRE_VAD_SUCCESS=true, dropping all subtitles")
              return []
          else:
              logger.warning("VAD failed but REQUIRE_VAD_SUCCESS=false, using original subtitles")
              return subtitles
      
      # Aplicar gating
      filtered = gater.gate_subtitles(subtitles, segments)
      
      logger.info("speech_gating_applied", original=len(subtitles), filtered=len(filtered), segments=len(segments))
      
      return filtered
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Feature flag ENABLE_SPEECH_GATING
- [ ] Flag REQUIRE_VAD_SUCCESS
- [ ] Retorna originais se VAD falha e não é requerido
- [ ] Retorna [] se VAD falha e é requerido
- [ ] Aplica gating se VAD sucede

**Testes:**
- Unit: `tests/test_celery_tasks.py::test_validate_speech_gating_disabled()`
- Unit: `tests/test_celery_tasks.py::test_validate_speech_gating_vad_ok()`
- Unit: `tests/test_celery_tasks.py::test_validate_speech_gating_vad_fail_not_required()`
- Unit: `tests/test_celery_tasks.py::test_validate_speech_gating_vad_fail_required()`

**Observabilidade:**
- Log: `logger.info("speech_gating_applied", original=..., filtered=...)`
- Log: `logger.warning("vad_failed_using_original")`
- Métrica: `counter("speech_gating_applied_total", tags={"vad_ok": true|false})`

**Riscos/Rollback:**
- Risco: VAD sempre falha silenciosamente
- Rollback: REQUIRE_VAD_SUCCESS=true para detectar problemas

**Dependências:** S-117, S-110

---

<a name="s-119"></a>
## S-119: Adicionar métrica vad_fallback_rate

**Objetivo:** Criar métrica que tracking taxa de fallback de cada método VAD.

**Escopo (IN/OUT):**
- **IN:** Contador por método
- **OUT:** Não implementar dashboard

**Arquivos tocados:**
- `services/make-video/app/metrics.py`
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Em `metrics.py`, adicionar:
  ```python
  from prometheus_client import Counter
  
  vad_method_used_total = Counter(
      'make_video_vad_method_used_total',
      'Total de vezes que cada método VAD foi usado',
      ['method']  # silero, webrtcvad, rms
  )
  
  vad_fallback_rate = Counter(
      'make_video_vad_fallback_rate_total',
      'Total de fallbacks VAD',
      ['from_method', 'to_method']
  )
  ```
- Em `speech_gated_subtitles.py`, incrementar:
  ```python
  # Ao usar cada método
  vad_method_used_total.labels(method='silero').inc()
  
  # Ao fazer fallback
  vad_fallback_rate.labels(from_method='silero', to_method='webrtcvad').inc()
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Contador vad_method_used_total
- [ ] Contador vad_fallback_rate
- [ ] Incrementado corretamente

**Testes:**
- Unit: `tests/test_metrics.py::test_vad_fallback_metrics()`

**Observabilidade:**
- Métrica: `make_video_vad_method_used_total{method="silero"|"webrtcvad"|"rms"}`
- Métrica: `make_video_vad_fallback_rate_total{from_method=..., to_method=...}`

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-007 (metrics), S-117

---

<a name="s-120"></a>
## S-120: Criar testes para cada fallback

**Objetivo:** Criar testes isolados para cada método VAD.

**Escopo (IN/OUT):**
- **IN:** Testes unitários com mocks
- **OUT:** Não testar com áudio real

**Arquivos tocados:**
- `services/make-video/tests/test_speech_gated_subtitles.py`

**Mudanças exatas:**
- Adicionar testes:
  ```python
  def test_silero_vad_detection(synthetic_audio_with_speech):
      gater = SpeechGatedSubtitles()
      segments = gater._detect_speech_silero(synthetic_audio_with_speech)
      
      assert len(segments) > 0
      assert all(isinstance(s, tuple) and len(s) == 2 for s in segments)
  
  def test_webrtcvad_detection(synthetic_audio_with_speech):
      gater = SpeechGatedSubtitles()
      segments = gater._detect_speech_webrtcvad(synthetic_audio_with_speech)
      
      assert len(segments) > 0
      assert all(isinstance(s, tuple) and len(s) == 2 for s in segments)
  
  def test_rms_fallback_detection(synthetic_audio_with_speech):
      gater = SpeechGatedSubtitles()
      segments = gater._detect_speech_rms(synthetic_audio_with_speech)
      
      assert len(segments) > 0
      assert all(isinstance(s, tuple) and len(s) == 2 for s in segments)
  
  def test_rms_fallback_silent_audio(synthetic_audio_silent):
      gater = SpeechGatedSubtitles()
      segments = gater._detect_speech_rms(synthetic_audio_silent, rms_threshold=0.02)
      
      assert len(segments) == 0  # Silêncio não deve detectar fala
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Testa cada método isoladamente
- [ ] Usa fixtures de áudio sintético
- [ ] Valida formato de retorno
- [ ] Testa caso silencioso

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_silero_vad_detection()`
- Unit: `tests/test_speech_gated_subtitles.py::test_webrtcvad_detection()`
- Unit: `tests/test_speech_gated_subtitles.py::test_rms_fallback_detection()`
- Unit: `tests/test_speech_gated_subtitles.py::test_rms_fallback_silent_audio()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-115, S-116, S-111 (fixtures)

---

<a name="s-121"></a>
## S-121: Validar fallback chain funciona

**Objetivo:** Criar testes que validam cadeia de fallbacks em diferentes cenários.

**Escopo (IN/OUT):**
- **IN:** Testes com mocks de falha
- **OUT:** Não testar performance

**Arquivos tocados:**
- `services/make-video/tests/test_speech_gated_subtitles.py`

**Mudanças exatas:**
- Adicionar testes:
  ```python
  def test_fallback_chain_silero_success(monkeypatch):
      """Silero funciona, não usa fallbacks"""
      gater = SpeechGatedSubtitles()
      
      # Mock silero para funcionar
      mock_silero = Mock(return_value=[(0.0, 1.0)])
      monkeypatch.setattr(gater, '_detect_speech_silero', mock_silero)
      
      segments, vad_ok = gater.detect_speech_segments('fake.wav')
      
      assert vad_ok == True
      assert len(segments) > 0
      mock_silero.assert_called_once()
  
  def test_fallback_chain_silero_fails_uses_webrtc(monkeypatch):
      """Silero falha, usa webrtcvad"""
      gater = SpeechGatedSubtitles()
      
      # Mock silero para falhar
      mock_silero = Mock(side_effect=RuntimeError("Model not loaded"))
      monkeypatch.setattr(gater, '_detect_speech_silero', mock_silero)
      
      # Mock webrtc para funcionar
      mock_webrtc = Mock(return_value=[(0.0, 1.0)])
      monkeypatch.setattr(gater, '_detect_speech_webrtcvad', mock_webrtc)
      
      segments, vad_ok = gater.detect_speech_segments('fake.wav')
      
      assert vad_ok == True
      assert len(segments) > 0
      mock_webrtc.assert_called_once()
  
  def test_fallback_chain_all_fail(monkeypatch):
      """Todos métodos falham"""
      gater = SpeechGatedSubtitles()
      
      # Mock todos para falhar
      monkeypatch.setattr(gater, '_detect_speech_silero', Mock(side_effect=RuntimeError()))
      monkeypatch.setattr(gater, '_detect_speech_webrtcvad', Mock(side_effect=RuntimeError()))
      monkeypatch.setattr(gater, '_detect_speech_rms', Mock(side_effect=RuntimeError()))
      
      segments, vad_ok = gater.detect_speech_segments('fake.wav')
      
      assert vad_ok == False
      assert len(segments) == 0
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Testa sucesso em cada nível
- [ ] Testa fallback entre níveis
- [ ] Testa falha total
- [ ] Valida vad_ok correto

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_fallback_chain_silero_success()`
- Unit: `tests/test_speech_gated_subtitles.py::test_fallback_chain_silero_fails_uses_webrtc()`
- Unit: `tests/test_speech_gated_subtitles.py::test_fallback_chain_all_fail()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-117

---

<a name="s-122"></a>
## S-122: Atualizar README com fallbacks

**Objetivo:** Documentar sistema de fallbacks VAD no README.

**Escopo (IN/OUT):**
- **IN:** Documentação textual
- **OUT:** Não criar guia de troubleshooting

**Arquivos tocados:**
- `services/make-video/README.md`

**Mudanças exatas:**
- Adicionar seção:
  ````markdown
  ## Voice Activity Detection (VAD) Fallbacks
  
  O sistema usa múltiplos métodos de detecção de fala com fallback automático:
  
  ### Cadeia de Fallbacks
  
  1. **silero-vad** (primário)
     - Modelo neural state-of-the-art
     - Maior precisão
     - Requer PyTorch
  
  2. **webrtcvad** (secundário)
     - Algoritmo clássico do WebRTC
     - Leve e confiável
     - Funciona sem GPU
  
  3. **RMS energy** (último recurso)
     - Baseado em energia do sinal
     - Muito simples
     - Menos preciso
  
  ### Configuração
  
  ```bash
  # Habilitar/desabilitar speech gating
  ENABLE_SPEECH_GATING=true
  
  # Requer sucesso do VAD (se false, usa legendas originais em caso de falha)
  REQUIRE_VAD_SUCCESS=false
  
  # Threshold RMS para fallback
  VAD_RMS_THRESHOLD=0.02
  ```
  
  ### Monitoramento
  
  Métricas:
  - `make_video_vad_method_used_total{method="silero"|"webrtcvad"|"rms"}`
  - `make_video_vad_fallback_rate_total{from_method=..., to_method=...}`
  - `make_video_vad_segments_dropped_total{reason=...}`
  
  Logs:
  - `vad_method_used`: Indica qual método foi usado
  - `vad_fallback`: Indica quando houve fallback
  ````

**Critérios de Aceite / Definition of Done:**
- [ ] Seção adicionada ao README
- [ ] Cada método documentado
- [ ] Configuração explicada
- [ ] Métricas listadas

**Testes:**
- Manual: Revisar README

**Observabilidade:**
- N/A (documentação)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-117, S-118, S-119

---

## Mapa de Dependências (Pack 10)

```
S-113 (_convert_to_16k_wav) ← S-005
S-114 (integrar resample) ← S-113, S-104
S-115 (webrtcvad estrutura) ← S-113, S-004
S-116 (RMS fallback) ← S-101
S-117 (fallback chain) ← S-104, S-115, S-116
S-118 (validate_speech_gating) ← S-117, S-110
S-119 (vad_fallback_rate) ← S-007, S-117
S-120 (testes fallbacks) ← S-115, S-116, S-111
S-121 (validar chain) ← S-117
S-122 (README) ← S-117, S-118, S-119
```

**Próximo pack:** Sprint 11 - ASS Neon Pipeline (ASSGenerator, style_key mapping sem double underscore, 8-digit colors, FontManager, burn_subtitles com flags FFmpeg)
