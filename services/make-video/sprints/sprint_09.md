# Sprint Pack 09/12 - SpeechGatedSubtitles (VAD Pipeline)

**Escopo deste pack:** Implementar pipeline VAD (Voice Activity Detection) com silero-vad vendorizado, detect_speech_segments com clamp de audio_duration (MUST-FIX v1.6), retorno de tupla vad_ok, merge_gap para reduzir fragmentação, gate_subtitles que filtra por speech, contadores drop_count e merged_count.

## Índice

- [S-101: Criar estrutura SpeechGatedSubtitles](#s-101)
- [S-102: Vendorizar modelo silero-vad (local)](#s-102)
- [S-103: Implementar load_vad_model](#s-103)
- [S-104: Implementar detect_speech_segments (estrutura)](#s-104)
- [S-105: Implementar clamp de timestamps com audio_duration (MUST-FIX)](#s-105)
- [S-106: Implementar min_duration enforcement](#s-106)
- [S-107: Implementar merge_gap lógica](#s-107)
- [S-108: Adicionar contadores drop_count e merged_count](#s-108)
- [S-109: Implementar vad_ok return (tupla)](#s-109)
- [S-110: Implementar gate_subtitles](#s-110)
- [S-111: Criar testes com áudio sintético](#s-111)
- [S-112: Validar clamp funciona corretamente](#s-112)

---

<a name="s-101"></a>
## S-101: Criar estrutura SpeechGatedSubtitles

**Objetivo:** Criar classe base para pipeline de gating de legendas por speech detection.

**Escopo (IN/OUT):**
- **IN:** Classe e métodos skeleton
- **OUT:** Não implementar lógica ainda

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Criar arquivo:
  ```python
  import torch
  import logging
  from typing import List, Tuple
  
  logger = logging.getLogger(__name__)
  
  class SpeechGatedSubtitles:
      """
      Pipeline de legendas com gating por detecção de fala
      
      Usa silero-vad para detectar segmentos de fala e filtra legendas
      """
      
      def __init__(self, model_path: str = 'models/silero_vad.jit'):
          self.model_path = model_path
          self.model = None
          
          logger.info("speech_gated_subtitles_initialized", model_path=model_path)
      
      def load_vad_model(self):
          """Carrega modelo VAD"""
          pass
      
      def detect_speech_segments(self, audio_path: str, min_duration: float = 0.3) -> Tuple[List[Tuple[float, float]], bool]:
          """
          Detecta segmentos de fala
          
          Returns:
              (segments, vad_ok): Lista de (start, end) e flag de sucesso
          """
          pass
      
      def gate_subtitles(self, subtitles: list, speech_segments: list) -> list:
          """Filtra legendas que não têm overlap com speech"""
          pass
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Classe criada
- [ ] 3 métodos skeleton
- [ ] Docstrings adicionadas
- [ ] Logger configurado

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_class_initialization()`

**Observabilidade:**
- Log: `logger.info("speech_gated_subtitles_initialized", ...)`

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-001

---

<a name="s-102"></a>
## S-102: Vendorizar modelo silero-vad (local)

**Objetivo:** Baixar modelo silero-vad e salvar localmente para evitar download em runtime.

**Escopo (IN/OUT):**
- **IN:** Download e armazenamento local
- **OUT:** Não usar torch hub em runtime

**Arquivos tocados:**
- `services/make-video/models/silero_vad.jit`
- `services/make-video/scripts/download_vad_model.py`

**Mudanças exatas:**
- Criar script `scripts/download_vad_model.py`:
  ```python
  #!/usr/bin/env python3
  """
  Download silero-vad model para uso offline
  """
  import torch
  import os
  
  def download_vad_model():
      model, utils = torch.hub.load(
          repo_or_dir='snakers4/silero-vad',
          model='silero_vad',
          force_reload=False,
          onnx=False
      )
      
      # Salvar modelo
      os.makedirs('models', exist_ok=True)
      torch.jit.save(model, 'models/silero_vad.jit')
      
      print("✅ Modelo silero-vad baixado: models/silero_vad.jit")
  
  if __name__ == '__main__':
      download_vad_model()
  ```
- Executar script: `python scripts/download_vad_model.py`
- Adicionar `models/silero_vad.jit` ao Dockerfile: `COPY models/ /app/models/`

**Critérios de Aceite / Definition of Done:**
- [ ] Script criado
- [ ] Modelo baixado localmente
- [ ] Dockerfile copia modelo
- [ ] Não usa torch.hub em runtime

**Testes:**
- Manual: Executar script e validar arquivo existe

**Observabilidade:**
- N/A (setup)

**Riscos/Rollback:**
- Risco: Modelo muito grande (>50MB)
- Rollback: Usar torch.hub com cache

**Dependências:** S-004 (torch instalado)

---

<a name="s-103"></a>
## S-103: Implementar load_vad_model

**Objetivo:** Implementar carregamento do modelo VAD local.

**Escopo (IN/OUT):**
- **IN:** Carregamento lazy (apenas quando necessário)
- **OUT:** Não implementar fallback para outros modelos

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Implementar método:
  ```python
  def load_vad_model(self):
      """Carrega modelo VAD (lazy loading)"""
      if self.model is not None:
          return  # Já carregado
      
      import os
      if not os.path.exists(self.model_path):
          raise FileNotFoundError(f"Modelo VAD não encontrado: {self.model_path}")
      
      self.model = torch.jit.load(self.model_path)
      self.model.eval()
      
      logger.info("vad_model_loaded", model_path=self.model_path)
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Lazy loading (só carrega se necessário)
- [ ] Valida arquivo existe
- [ ] Levanta FileNotFoundError se falta
- [ ] Modo eval()

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_load_vad_model_success()`
- Unit: `tests/test_speech_gated_subtitles.py::test_load_vad_model_missing_file()`

**Observabilidade:**
- Log: `logger.info("vad_model_loaded", ...)`

**Riscos/Rollback:**
- Risco: Modelo corrompido
- Rollback: Re-download do modelo

**Dependências:** S-102

---

<a name="s-104"></a>
## S-104: Implementar detect_speech_segments (estrutura)

**Objetivo:** Implementar estrutura base de detecção de segmentos, sem clamp ainda.

**Escopo (IN/OUT):**
- **IN:** Estrutura base com carregamento de áudio
- **OUT:** Não implementar clamp ainda

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Implementar método:
  ```python
  def detect_speech_segments(self, audio_path: str, min_duration: float = 0.3) -> Tuple[List[Tuple[float, float]], bool]:
      """
      Detecta segmentos de fala usando silero-vad
      
      Args:
          audio_path: Path para áudio WAV (16kHz mono)
          min_duration: Duração mínima de segmento (segundos)
      
      Returns:
          (segments, vad_ok): Lista de (start, end) e flag de sucesso
      """
      import torchaudio
      import numpy as np
      
      # Carregar modelo
      self.load_vad_model()
      
      try:
          # Carregar áudio
          waveform, sample_rate = torchaudio.load(audio_path)
          
          # Validar sample rate
          if sample_rate != 16000:
              logger.warning(f"VAD espera 16kHz, recebeu {sample_rate}Hz")
              # Resample será implementado em sprint futura
              return [], False
          
          # Converter para mono se necessário
          if waveform.shape[0] > 1:
              waveform = torch.mean(waveform, dim=0, keepdim=True)
          
          # Detectar fala (silero-vad)
          speech_timestamps = self.model(waveform, sample_rate)
          
          # Converter para (start, end) em segundos
          segments = []
          for ts in speech_timestamps:
              start = ts['start'] / sample_rate
              end = ts['end'] / sample_rate
              
              # Clamp será implementado em S-105
              
              segments.append((start, end))
          
          logger.info("vad_speech_detected", segments_count=len(segments), audio_path=audio_path)
          
          return segments, True
      
      except Exception as e:
          logger.error(f"VAD failed: {e}", exc_info=True)
          return [], False
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Carrega áudio com torchaudio
- [ ] Valida sample rate 16kHz
- [ ] Converte para mono se necessário
- [ ] Executa silero-vad
- [ ] Retorna tupla (segments, vad_ok)
- [ ] Retorna ([], False) em caso de erro

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_detect_speech_segments_structure()`

**Observabilidade:**
- Log: `logger.info("vad_speech_detected", segments_count=...)`
- Log: `logger.error("vad_failed", error=...)`

**Riscos/Rollback:**
- Risco: Sample rate incorreto causa falha
- Rollback: Implementar resample automático

**Dependências:** S-103

---

<a name="s-105"></a>
## S-105: Implementar clamp de timestamps com audio_duration (MUST-FIX)

**Objetivo:** Implementar clamping de timestamps para evitar timestamps maiores que duração do áudio (MUST-FIX v1.6).

**Escopo (IN/OUT):**
- **IN:** Clamp usando duração real do áudio
- **OUT:** Não implementar padding

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Modificar `detect_speech_segments()`:
  ```python
  # Após converter timestamps
  # Calcular duração do áudio
  audio_duration = waveform.shape[1] / sample_rate
  
  segments = []
  for ts in speech_timestamps:
      start = ts['start'] / sample_rate
      end = ts['end'] / sample_rate
      
      # MUST-FIX v1.6: clamp com audio_duration
      start = max(0.0, min(start, audio_duration))
      end = max(0.0, min(end, audio_duration))
      
      # Validar que end > start
      if end <= start:
          logger.warning(f"Segmento inválido após clamp: start={start}, end={end}")
          continue
      
      segments.append((start, end))
  
  logger.info("vad_timestamps_clamped", audio_duration=audio_duration, segments_count=len(segments))
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] audio_duration calculado de waveform
- [ ] start e end clamped entre [0, audio_duration]
- [ ] Segmentos inválidos (end <= start) são descartados
- [ ] Log indica clamping

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_clamp_timestamps_within_duration()`
- Unit: `tests/test_speech_gated_subtitles.py::test_clamp_discards_invalid_segments()`

**Observabilidade:**
- Log: `logger.info("vad_timestamps_clamped", audio_duration=..., segments_count=...)`
- Log: `logger.warning("invalid_segment_after_clamp", start=..., end=...)`

**Riscos/Rollback:**
- Risco: Clamping muito agressivo descarta segmentos válidos
- Rollback: Adicionar margem de tolerância (ex: +0.1s)

**Dependências:** S-104

---

<a name="s-106"></a>
## S-106: Implementar min_duration enforcement

**Objetivo:** Filtrar segmentos de fala muito curtos (< min_duration).

**Escopo (IN/OUT):**
- **IN:** Filtro simples por duração
- **OUT:** Não implementar heurística de "speech quality"

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Modificar `detect_speech_segments()`:
  ```python
  # Após clamp, antes de append
  duration = end - start
  
  if duration < min_duration:
      logger.debug(f"Segmento curto descartado: {duration:.2f}s < {min_duration}s")
      continue
  
  segments.append((start, end))
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Segmentos com duração < min_duration descartados
- [ ] Log debug para cada descarte
- [ ] Default min_duration = 0.3s

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_min_duration_filtering()`

**Observabilidade:**
- Log: `logger.debug("short_segment_discarded", duration=..., min_duration=...)`
- Métrica: `counter("vad_segments_discarded_total", tags={"reason": "too_short"})`

**Riscos/Rollback:**
- Risco: min_duration alto demais descarta fala válida
- Rollback: Reduzir para 0.1s

**Dependências:** S-105

---

<a name="s-107"></a>
## S-107: Implementar merge_gap lógica

**Objetivo:** Implementar merge de segmentos próximos para reduzir fragmentação.

**Escopo (IN/OUT):**
- **IN:** Merge simples com gap configurável
- **OUT:** Não implementar merge adaptativo

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Adicionar parâmetro `merge_gap` ao método:
  ```python
  def detect_speech_segments(self, audio_path: str, min_duration: float = 0.3, merge_gap: float = 0.5) -> Tuple[List[Tuple[float, float]], bool]:
      # ... código existente ...
      
      # Após coletar todos os segmentos válidos
      if not segments:
          return segments, True
      
      # Ordenar por start
      segments.sort(key=lambda x: x[0])
      
      # Merge de segmentos próximos
      merged = []
      current_start, current_end = segments[0]
      
      for start, end in segments[1:]:
          gap = start - current_end
          
          if gap <= merge_gap:
              # Merge: estender current_end
              current_end = end
              logger.debug(f"Merged segment: gap={gap:.2f}s <= {merge_gap}s")
          else:
              # Gap grande: salvar segmento atual e iniciar novo
              merged.append((current_start, current_end))
              current_start, current_end = start, end
      
      # Adicionar último segmento
      merged.append((current_start, current_end))
      
      logger.info("vad_segments_merged", original=len(segments), merged=len(merged), merge_gap=merge_gap)
      
      return merged, True
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Segmentos ordenados por start
- [ ] Segmentos com gap <= merge_gap são unidos
- [ ] Log indica quantidade merged
- [ ] Default merge_gap = 0.5s

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_merge_gap_merges_close_segments()`
- Unit: `tests/test_speech_gated_subtitles.py::test_merge_gap_preserves_distant_segments()`

**Observabilidade:**
- Log: `logger.info("vad_segments_merged", original=..., merged=...)`
- Métrica: `histogram("vad_merge_ratio", value=merged/original)`

**Riscos/Rollback:**
- Risco: merge_gap alto demais causa over-merging
- Rollback: Reduzir para 0.3s

**Dependências:** S-106

---

<a name="s-108"></a>
## S-108: Adicionar contadores drop_count e merged_count

**Objetivo:** Adicionar contadores para tracking de segmentos descartados e merged.

**Escopo (IN/OUT):**
- **IN:** Contadores Prometheus
- **OUT:** Não implementar alertas

**Arquivos tocados:**
- `services/make-video/app/metrics.py`
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Em `metrics.py`, adicionar:
  ```python
  from prometheus_client import Counter, Histogram
  
  vad_segments_dropped_total = Counter(
      'make_video_vad_segments_dropped_total',
      'Total de segmentos VAD descartados',
      ['reason']  # too_short, invalid, etc
  )
  
  vad_segments_merged_total = Counter(
      'make_video_vad_segments_merged_total',
      'Total de merges de segmentos VAD'
  )
  
  vad_merge_ratio = Histogram(
      'make_video_vad_merge_ratio',
      'Ratio de merge (merged/original)',
      buckets=[0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
  )
  ```
- Em `speech_gated_subtitles.py`, incrementar contadores:
  ```python
  # Ao descartar por min_duration
  vad_segments_dropped_total.labels(reason='too_short').inc()
  
  # Ao merge
  merged_count = len(segments) - len(merged)
  vad_segments_merged_total.inc(merged_count)
  vad_merge_ratio.observe(len(merged) / len(segments))
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] 3 métricas criadas
- [ ] Contadores incrementados corretamente
- [ ] Labels usados para categorizar drops

**Testes:**
- Unit: `tests/test_metrics.py::test_vad_counters()`

**Observabilidade:**
- Métrica: `make_video_vad_segments_dropped_total{reason="too_short"}`
- Métrica: `make_video_vad_segments_merged_total`
- Métrica: `make_video_vad_merge_ratio`

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-007 (metrics), S-106, S-107

---

<a name="s-109"></a>
## S-109: Implementar vad_ok return (tupla)

**Objetivo:** Validar que `detect_speech_segments()` retorna tupla `(segments, vad_ok)` corretamente.

**Escopo (IN/OUT):**
- **IN:** Validação de retorno existente
- **OUT:** Não modificar assinatura

**Arquivos tocados:**
- Nenhum (validação de S-104-S-107)

**Mudanças exatas:**
- Validar que método retorna tupla em todos os casos:
  - Sucesso: `(segments, True)`
  - Falha: `([], False)`
- Adicionar docstring explicitando retorno:
  ```python
  """
  Returns:
      (segments, vad_ok):
          - segments: Lista de (start, end) em segundos
          - vad_ok: True se VAD executou com sucesso, False se falhou
  """
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Retorno é tupla em todos os casos
- [ ] vad_ok=True em caso de sucesso
- [ ] vad_ok=False em caso de erro
- [ ] Docstring explica retorno

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_vad_ok_true_on_success()`
- Unit: `tests/test_speech_gated_subtitles.py::test_vad_ok_false_on_failure()`

**Observabilidade:**
- N/A (validação de assinatura)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-104, S-105, S-106, S-107

---

<a name="s-110"></a>
## S-110: Implementar gate_subtitles

**Objetivo:** Implementar filtro de legendas que remove aquelas que não têm overlap com segmentos de fala.

**Escopo (IN/OUT):**
- **IN:** Filtro simples com overlap check
- **OUT:** Não implementar ajuste de timing

**Arquivos tocados:**
- `services/make-video/app/speech_gated_subtitles.py`

**Mudanças exatas:**
- Implementar método:
  ```python
  def gate_subtitles(self, subtitles: list, speech_segments: list) -> list:
      """
      Filtra legendas que não têm overlap com segmentos de fala
      
      Args:
          subtitles: Lista de dicts com 'start' e 'end' (segundos)
          speech_segments: Lista de (start, end) de segmentos de fala
      
      Returns:
          Lista de legendas filtradas
      """
      if not speech_segments:
          logger.warning("No speech segments, dropping all subtitles")
          return []
      
      filtered = []
      dropped = 0
      
      for sub in subtitles:
          sub_start = sub['start']
          sub_end = sub['end']
          
          # Verificar overlap com qualquer segmento de fala
          has_overlap = False
          for seg_start, seg_end in speech_segments:
              # Overlap se: sub_start < seg_end AND sub_end > seg_start
              if sub_start < seg_end and sub_end > seg_start:
                  has_overlap = True
                  break
          
          if has_overlap:
              filtered.append(sub)
          else:
              dropped += 1
              logger.debug(f"Dropped subtitle: [{sub_start:.2f}-{sub_end:.2f}] no speech")
      
      logger.info("subtitles_gated", original=len(subtitles), filtered=len(filtered), dropped=dropped)
      
      return filtered
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Verifica overlap com cada segmento de fala
- [ ] Mantém legendas com overlap
- [ ] Descarta legendas sem overlap
- [ ] Log indica quantidade dropped

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_gate_subtitles_keeps_overlapping()`
- Unit: `tests/test_speech_gated_subtitles.py::test_gate_subtitles_drops_non_overlapping()`
- Unit: `tests/test_speech_gated_subtitles.py::test_gate_subtitles_no_speech_drops_all()`

**Observabilidade:**
- Log: `logger.info("subtitles_gated", original=..., filtered=..., dropped=...)`
- Métrica: `counter("subtitles_dropped_by_vad_total")`

**Riscos/Rollback:**
- Risco: Overlap check muito rígido descarta legendas válidas
- Rollback: Adicionar margem de tolerância (ex: ±0.2s)

**Dependências:** S-109

---

<a name="s-111"></a>
## S-111: Criar testes com áudio sintético

**Objetivo:** Criar fixtures de áudio sintético para testes sem dependência de arquivos externos.

**Escopo (IN/OUT):**
- **IN:** Áudio sintético com torch
- **OUT:** Não testar com áudio real

**Arquivos tocados:**
- `services/make-video/conftest.py`
- `services/make-video/tests/test_speech_gated_subtitles.py`

**Mudanças exatas:**
- Em `conftest.py`, criar fixture:
  ```python
  import torch
  import torchaudio
  import tempfile
  import os
  
  @pytest.fixture
  def synthetic_audio_with_speech():
      """Gera áudio sintético com 'fala' simulada"""
      sample_rate = 16000
      duration = 5.0  # 5 segundos
      
      # Gerar sine wave (simula fala)
      t = torch.linspace(0, duration, int(sample_rate * duration))
      frequency = 440  # Hz (A4)
      waveform = torch.sin(2 * torch.pi * frequency * t).unsqueeze(0)
      
      # Salvar em arquivo temporário
      with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
          audio_path = f.name
      
      torchaudio.save(audio_path, waveform, sample_rate)
      
      yield audio_path
      
      # Cleanup
      os.unlink(audio_path)
  
  @pytest.fixture
  def synthetic_audio_silent():
      """Gera áudio sintético silencioso"""
      sample_rate = 16000
      duration = 5.0
      
      waveform = torch.zeros(1, int(sample_rate * duration))
      
      with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
          audio_path = f.name
      
      torchaudio.save(audio_path, waveform, sample_rate)
      
      yield audio_path
      
      os.unlink(audio_path)
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] 2 fixtures criadas: com fala e silenciosa
- [ ] Áudio gerado em runtime
- [ ] 16kHz sample rate
- [ ] Cleanup automático

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_synthetic_audio_fixtures()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Sine wave não detectado como fala por VAD
- Rollback: Usar white noise

**Dependências:** S-010 (fixtures)

---

<a name="s-112"></a>
## S-112: Validar clamp funciona corretamente

**Objetivo:** Criar testes que validam que clamping de timestamps funciona corretamente.

**Escopo (IN/OUT):**
- **IN:** Testes com casos edge
- **OUT:** Não testar com áudio real

**Arquivos tocados:**
- `services/make-video/tests/test_speech_gated_subtitles.py`

**Mudanças exatas:**
- Adicionar testes:
  ```python
  def test_clamp_timestamps_at_boundaries(monkeypatch):
      """Testa clamp nos limites"""
      gater = SpeechGatedSubtitles()
      
      # Mock VAD para retornar timestamps fora dos limites
      def mock_vad(waveform, sr):
          return [
              {'start': -1000, 'end': 8000},  # start negativo
              {'start': 16000, 'end': 100000},  # fora do áudio (5s = 80000 samples)
              {'start': 8000, 'end': 24000},  # válido
          ]
      
      monkeypatch.setattr(gater.model, '__call__', mock_vad)
      
      segments, vad_ok = gater.detect_speech_segments('fake_audio.wav')
      
      # Validar clamp
      assert vad_ok == True
      assert len(segments) == 2  # 1 descartado por invalidade
      
      # Primeiro segmento clamped para [0, 0.5]
      assert segments[0][0] == 0.0
      assert segments[0][1] <= 5.0
      
      # Segundo segmento clamped
      assert segments[1][0] >= 0.0
      assert segments[1][1] <= 5.0
  
  def test_clamp_discards_end_before_start():
      """Testa que segmentos com end <= start são descartados"""
      gater = SpeechGatedSubtitles()
      
      # Mock VAD retorna timestamps invertidos
      def mock_vad(waveform, sr):
          return [
              {'start': 24000, 'end': 8000},  # end < start
          ]
      
      monkeypatch.setattr(gater.model, '__call__', mock_vad)
      
      segments, vad_ok = gater.detect_speech_segments('fake_audio.wav')
      
      # Validar descarte
      assert vad_ok == True
      assert len(segments) == 0
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Testa timestamps negativos
- [ ] Testa timestamps maiores que duração
- [ ] Testa timestamps invertidos (end < start)
- [ ] Valida descarte de segmentos inválidos

**Testes:**
- Unit: `tests/test_speech_gated_subtitles.py::test_clamp_timestamps_at_boundaries()`
- Unit: `tests/test_speech_gated_subtitles.py::test_clamp_discards_end_before_start()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-105, S-111

---

## Mapa de Dependências (Pack 09)

```
S-101 (estrutura) ← S-001
S-102 (vendorizar modelo) ← S-004
S-103 (load_vad_model) ← S-102
S-104 (detect_speech_segments estrutura) ← S-103
S-105 (clamp MUST-FIX) ← S-104
S-106 (min_duration) ← S-105
S-107 (merge_gap) ← S-106
S-108 (contadores) ← S-007, S-106, S-107
S-109 (vad_ok tupla) ← S-104, S-105, S-106, S-107
S-110 (gate_subtitles) ← S-109
S-111 (áudio sintético) ← S-010
S-112 (validar clamp) ← S-105, S-111
```

**Próximo pack:** Sprint 10 - VAD Fallbacks (webrtcvad, _convert_to_16k_wav, RMS fallback, validate_speech_gating, vad_fallback_rate)
