# SPRINT – Plano de Conversão OpenVoice → F5-TTS

## 1. Objetivo geral

- **Substituir** o motor de clonagem de voz de OpenVoice (mock) por F5-TTS (produção real)
- **Manter** a API/contrato externo do serviço 100% compatível
- **Garantir** qualidade de áudio superior (sem "bibs eletrônicos")
- **Validar** com testes automatizados usando `tests/Teste.mp3`

---

## 2. Sprint 1 – Ambiente & Dependências F5-TTS

### Objetivo
Preparar ambiente Python + Docker para rodar F5-TTS sem quebrar serviço atual.

### Duração estimada
4-6 horas

### Tarefas

#### 2.1. Análise de requisitos F5-TTS
- [ ] **2.1.1** Clonar repositório F5-TTS localmente (fora do Docker)
  ```bash
  cd /tmp
  git clone https://github.com/SWivid/F5-TTS.git
  cd F5-TTS
  ```
- [ ] **2.1.2** Ler `README.md` e identificar dependências críticas
  - PyTorch: ✅ compatível (2.1.2 vs 2.4.0 - minor update OK)
  - Vocos: vocoder (novo)
  - Transformers: Whisper para transcrição (novo)
  - Hydra/OmegaConf: config management (novo)
  
- [ ] **2.1.3** Verificar compatibilidade CUDA
  ```bash
  # F5-TTS suporta CUDA 12.4
  # Projeto usa CUDA 12.1
  # Ação: Verificar se F5-TTS roda com CUDA 12.1
  ```

- [ ] **2.1.4** Listar dependências completas
  ```bash
  cat F5-TTS/setup.py | grep install_requires
  cat F5-TTS/requirements.txt  # se existir
  ```

#### 2.2. Atualizar requirements.txt
- [ ] **2.2.1** Backup do requirements.txt atual
  ```bash
  cp requirements.txt requirements.txt.backup
  ```

- [ ] **2.2.2** Adicionar dependências F5-TTS
  ```bash
  cat >> requirements.txt << 'EOF'
  
  # === F5-TTS Dependencies ===
  # Core F5-TTS
  f5-tts>=0.0.1
  
  # Config management
  omegaconf>=2.3.0
  hydra-core>=1.3.2
  
  # Vocoder
  vocos>=0.1.0
  
  # Caching
  cached-path>=1.5.2
  
  # Transcrição (Whisper via transformers)
  transformers>=4.35.0
  accelerate>=0.25.0  # para Whisper otimizado
  
  # Utilities
  unidecode>=1.3.7  # text normalization
  
  # Já temos mas garantir versão compatível
  # torch==2.1.2  (manter)
  # torchaudio==2.1.2  (manter)
  # soundfile==0.12.1  (manter)
  EOF
  ```

- [ ] **2.2.3** Validar que não há conflitos
  ```bash
  # Verificar versões compatíveis
  grep -E "torch|torchaudio|numpy" requirements.txt
  ```

#### 2.3. Atualizar Dockerfile
- [ ] **2.3.1** Backup do Dockerfile
  ```bash
  cp Dockerfile Dockerfile.backup
  ```

- [ ] **2.3.2** Adicionar git às dependências de sistema
  ```dockerfile
  # Linha ~45
  RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg libsndfile1 build-essential pkg-config \
      libavformat-dev libavcodec-dev libavdevice-dev \
      libavutil-dev libavfilter-dev libswscale-dev libswresample-dev \
      git \  # ← ADICIONAR (necessário para f5-tts)
      curl \
   && rm -rf /var/lib/apt/lists/*
  ```

- [ ] **2.3.3** (Opcional) Aumentar cache de models
  ```dockerfile
  # Linha após RUN mkdir -p
  RUN mkdir -p /app/uploads /app/processed /app/temp /app/logs \
      /app/voice_profiles /app/models /app/models/f5tts \
      /app/models/whisper && \  # ← ADICIONAR
      chown -R appuser:appuser /app && \
      chmod -R 755 /app && \
      chmod -R 777 /app/uploads /app/processed /app/temp /app/logs \
                   /app/voice_profiles /app/models
  ```

#### 2.4. Build e teste inicial
- [ ] **2.4.1** Para containers atuais
  ```bash
  docker compose down
  ```

- [ ] **2.4.2** Build nova imagem (sem cache)
  ```bash
  docker compose build --no-cache
  ```
  **Tempo esperado**: 10-15 minutos
  **Validação**: Build completa sem erros

- [ ] **2.4.3** Sobe containers
  ```bash
  docker compose up -d
  ```

- [ ] **2.4.4** Verifica logs
  ```bash
  docker logs audio-voice-api -f
  docker logs audio-voice-celery -f
  ```
  **Validação**: API sobe normalmente, sem erros de import

#### 2.5. Teste de importação F5-TTS
- [ ] **2.5.1** Criar script de teste: `tests/test_f5tts_import.py`
  ```python
  """Testa se F5-TTS importa corretamente"""
  import sys
  
  def test_f5tts_imports():
      try:
          from f5_tts.api import F5TTS
          print("✅ F5TTS class imported successfully")
          
          from f5_tts.infer.utils_infer import load_model, load_vocoder
          print("✅ F5TTS utils imported successfully")
          
          from transformers import pipeline
          print("✅ Transformers imported successfully")
          
          import vocos
          print("✅ Vocos imported successfully")
          
          return True
      except ImportError as e:
          print(f"❌ Import failed: {e}")
          return False
  
  if __name__ == "__main__":
      success = test_f5tts_imports()
      sys.exit(0 if success else 1)
  ```

- [ ] **2.5.2** Rodar teste dentro do container
  ```bash
  docker exec audio-voice-api python /app/tests/test_f5tts_import.py
  ```
  **Validação**: Todas as importações com ✅

- [ ] **2.5.3** Teste de instanciação básica
  ```python
  # tests/test_f5tts_basic.py
  from f5_tts.api import F5TTS
  import torch
  
  def test_f5tts_instantiation():
      device = 'cuda' if torch.cuda.is_available() else 'cpu'
      print(f"Testing on device: {device}")
      
      # Instancia (vai baixar modelos na primeira vez!)
      f5tts = F5TTS(
          model="F5TTS_v1_Base",
          device=device,
          hf_cache_dir="/app/models/f5tts"
      )
      
      print(f"✅ F5TTS instantiated successfully")
      print(f"   Model: {f5tts.mel_spec_type}")
      print(f"   Sample rate: {f5tts.target_sample_rate}")
      print(f"   Device: {f5tts.device}")
      
      return True
  
  if __name__ == "__main__":
      test_f5tts_instantiation()
  ```

- [ ] **2.5.4** Rodar teste (primeira vez baixa modelos!)
  ```bash
  docker exec audio-voice-api python /app/tests/test_f5tts_basic.py
  ```
  **Tempo esperado**: 5-10 minutos (download de modelos)
  **Validação**: Modelos baixados em `/app/models/f5tts`, instanciação OK

### Critérios de aceite Sprint 1
- [x] Docker build sem erros
- [x] Containers sobem normalmente
- [x] F5-TTS importa sem erros
- [x] F5TTS() instancia e baixa modelos
- [x] Serviço atual continua funcionando (OpenVoice mock)

---

## 3. Sprint 2 – Adapter F5-TTS e Interface Unificada

### Objetivo
Criar camada de adaptação para isolar F5-TTS, permitindo troca transparente de motor.

### Duração estimada
6-8 horas

### Tarefas

#### 3.1. Definir interface unificada
- [ ] **3.1.1** Criar `app/tts_interface.py` (contrato)
  ```python
  """Interface abstrata para motores TTS"""
  from abc import ABC, abstractmethod
  from typing import Tuple, Optional
  from .models import VoiceProfile
  
  class TTSEngine(ABC):
      """Interface para motores de TTS/clonagem"""
      
      @abstractmethod
      async def generate_dubbing(
          self,
          text: str,
          language: str,
          voice_preset: Optional[str] = None,
          voice_profile: Optional[VoiceProfile] = None,
          speed: float = 1.0,
          pitch: float = 1.0
      ) -> Tuple[bytes, float]:
          """
          Gera áudio dublado
          
          Returns:
              (audio_bytes, duration)
          """
          pass
      
      @abstractmethod
      async def clone_voice(
          self,
          audio_path: str,
          language: str,
          voice_name: str,
          description: Optional[str] = None
      ) -> VoiceProfile:
          """
          Clona voz a partir de amostra
          
          Returns:
              VoiceProfile
          """
          pass
      
      @abstractmethod
      def unload_models(self):
          """Libera memória de modelos"""
          pass
  ```

#### 3.2. Adaptar OpenVoiceClient para interface
- [ ] **3.2.1** Modificar `app/openvoice_client.py`
  ```python
  # Linha 1
  from .tts_interface import TTSEngine
  
  # Linha 423
  class OpenVoiceClient(TTSEngine):  # ← herda de TTSEngine
      """Cliente OpenVoice (MOCK)"""
      # ... resto igual
  ```

- [ ] **3.2.2** Validar que OpenVoiceClient ainda funciona
  ```bash
  docker compose restart
  docker logs audio-voice-api | grep -i error
  ```

#### 3.3. Criar F5TTSClient
- [ ] **3.3.1** Criar arquivo `app/f5tts_client.py`
  ```python
  """
  Cliente F5-TTS - Adapter para dublagem e clonagem de voz
  
  IMPORTANTE: Este é o adapter REAL para F5-TTS.
  Substitui o mock do OpenVoice.
  """
  import logging
  import os
  import torch
  import torchaudio
  import numpy as np
  import soundfile as sf
  import shutil
  from pathlib import Path
  from typing import Optional, Tuple
  
  from f5_tts.api import F5TTS
  
  from .tts_interface import TTSEngine
  from .models import VoiceProfile
  from .config import get_settings
  from .exceptions import OpenVoiceException, InvalidAudioException
  
  logger = logging.getLogger(__name__)
  
  
  class F5TTSClient(TTSEngine):
      """Cliente para F5-TTS - Dublagem e Clonagem de Voz"""
      
      def __init__(self, device: Optional[str] = None):
          """
          Inicializa cliente F5-TTS
          
          Args:
              device: 'cpu' ou 'cuda' (auto-detecta se None)
          """
          self.settings = get_settings()
          f5tts_config = self.settings.get('f5tts', {})
          
          # Device
          if device is None:
              self.device = f5tts_config.get('device', 'cuda')
              if self.device == 'cuda' and not torch.cuda.is_available():
                  logger.warning("CUDA not available, falling back to CPU")
                  self.device = 'cpu'
          else:
              self.device = device
          
          logger.info(f"Initializing F5-TTS client on device: {self.device}")
          
          # Paths
          self.hf_cache_dir = Path(f5tts_config.get('hf_cache_dir', '/app/models/f5tts'))
          self.hf_cache_dir.mkdir(exist_ok=True, parents=True)
          
          # Parâmetros
          self.model_name = f5tts_config.get('model', 'F5TTS_v1_Base')
          self.sample_rate = 24000  # F5-TTS fixed
          self.nfe_step = f5tts_config.get('nfe_step', 32)
          self.target_rms = f5tts_config.get('target_rms', 0.1)
          
          # Carrega modelo
          self._load_model()
      
      def _load_model(self):
          """Carrega modelo F5-TTS"""
          try:
              logger.info(f"Loading F5-TTS model: {self.model_name}")
              
              self.f5tts = F5TTS(
                  model=self.model_name,
                  device=self.device,
                  hf_cache_dir=str(self.hf_cache_dir)
              )
              
              logger.info("✅ F5-TTS model loaded successfully")
              
          except Exception as e:
              logger.error(f"Failed to load F5-TTS model: {e}")
              raise OpenVoiceException(f"Model loading failed: {str(e)}")
      
      async def generate_dubbing(
          self,
          text: str,
          language: str,
          voice_preset: Optional[str] = None,
          voice_profile: Optional[VoiceProfile] = None,
          speed: float = 1.0,
          pitch: float = 1.0  # F5-TTS não suporta pitch direto
      ) -> Tuple[bytes, float]:
          """
          Gera áudio dublado a partir de texto
          
          Args:
              text: Texto para dublar
              language: Idioma de síntese
              voice_preset: Voz genérica (ex: 'female_generic')
              voice_profile: Perfil de voz clonada
              speed: Velocidade da fala (0.5-2.0)
              pitch: Ignorado (F5-TTS não suporta)
          
          Returns:
              (audio_bytes, duration): Bytes do áudio WAV e duração
          """
          try:
              logger.info(f"🎙️ F5-TTS generate_dubbing: '{text[:50]}...'")
              
              # Determina áudio de referência
              if voice_profile:
                  ref_file = voice_profile.reference_audio_path
                  ref_text = voice_profile.reference_text
                  logger.info(f"  Using cloned voice: {voice_profile.id}")
              else:
                  ref_file, ref_text = self._get_preset_audio(voice_preset, language)
                  logger.info(f"  Using preset voice: {voice_preset}")
              
              # Inferência F5-TTS
              wav, sr, spec = self.f5tts.infer(
                  ref_file=ref_file,
                  ref_text=ref_text,
                  gen_text=text,
                  speed=speed,
                  nfe_step=self.nfe_step,
                  target_rms=self.target_rms,
                  cross_fade_duration=0.15,
                  remove_silence=False
              )
              
              logger.info(f"  Generated audio: {len(wav)} samples, {sr} Hz")
              
              # Converte para WAV bytes
              audio_bytes = self._wav_to_bytes(wav, sr)
              duration = len(wav) / sr
              
              logger.info(f"✅ F5-TTS dubbing generated: {duration:.2f}s")
              
              return audio_bytes, duration
              
          except Exception as e:
              logger.error(f"F5-TTS dubbing failed: {e}")
              raise OpenVoiceException(f"Dubbing generation failed: {str(e)}")
      
      async def clone_voice(
          self,
          audio_path: str,
          language: str,
          voice_name: str,
          description: Optional[str] = None
      ) -> VoiceProfile:
          """
          Clona voz a partir de amostra de áudio
          
          Args:
              audio_path: Caminho para amostra de áudio
              language: Idioma base da voz
              voice_name: Nome do perfil
              description: Descrição opcional
          
          Returns:
              VoiceProfile com referência de áudio
          """
          try:
              logger.info(f"🎤 F5-TTS cloning voice from: {audio_path}")
              
              # Validação
              if not audio_path or not Path(audio_path).exists():
                  raise InvalidAudioException(f"Audio file not found: {audio_path}")
              
              # Valida duração/qualidade
              audio_info = self._validate_audio_for_cloning(audio_path)
              
              # Transcreve com Whisper (via F5-TTS)
              logger.info("  Transcribing audio...")
              ref_text = self.f5tts.transcribe(audio_path, language)
              logger.info(f"  Transcription: '{ref_text}'")
              
              # Cria perfil temporário
              temp_profile = VoiceProfile.create_new(
                  name=voice_name,
                  language=language,
                  source_audio_path=audio_path,
                  profile_path="",  # preenchido abaixo
                  description=description,
                  duration=audio_info['duration'],
                  sample_rate=audio_info['sample_rate']
              )
              
              # Copia áudio para voice_profiles
              voice_profiles_dir = Path(self.settings['voice_profiles_dir'])
              voice_profiles_dir.mkdir(exist_ok=True, parents=True)
              
              ref_audio_path = voice_profiles_dir / f"{temp_profile.id}.wav"
              
              # Converte para WAV se necessário
              self._convert_to_wav(audio_path, str(ref_audio_path))
              
              # Atualiza perfil
              temp_profile.reference_audio_path = str(ref_audio_path)
              temp_profile.reference_text = ref_text
              temp_profile.profile_path = str(ref_audio_path)  # compatibilidade
              
              logger.info(f"✅ Voice cloned: {temp_profile.id}")
              
              return temp_profile
              
          except Exception as e:
              logger.error(f"F5-TTS voice cloning failed: {e}")
              raise OpenVoiceException(f"Voice cloning failed: {str(e)}")
      
      def _get_preset_audio(self, voice_preset: Optional[str], language: str) -> Tuple[str, str]:
          """Retorna (ref_file, ref_text) para voice preset"""
          # TODO: Implementar presets (áudios padrão)
          # Por enquanto, usa exemplo do F5-TTS
          preset_dir = Path("/app/voice_profiles/presets")
          preset_dir.mkdir(exist_ok=True, parents=True)
          
          # Mapeamento simples
          preset_map = {
              'female_generic': ('female_en.wav', 'Hello, this is a female voice.'),
              'male_deep': ('male_en.wav', 'Hello, this is a male voice.'),
          }
          
          if voice_preset in preset_map:
              file, text = preset_map[voice_preset]
              return str(preset_dir / file), text
          else:
              # Fallback: usa primeiro preset disponível
              logger.warning(f"Preset '{voice_preset}' not found, using default")
              return str(preset_dir / 'female_en.wav'), 'Hello, this is a generic voice.'
      
      def _wav_to_bytes(self, wav: np.ndarray, sample_rate: int) -> bytes:
          """Converte numpy array para WAV bytes"""
          import io
          buffer = io.BytesIO()
          sf.write(buffer, wav, sample_rate, format='WAV')
          buffer.seek(0)
          return buffer.read()
      
      def _validate_audio_for_cloning(self, audio_path: str) -> dict:
          """Valida áudio para clonagem"""
          audio, sr = sf.read(audio_path)
          
          duration = len(audio) / sr
          
          # F5-TTS recomenda <12s
          if duration > 12.0:
              logger.warning(f"Audio duration {duration:.1f}s > 12s, quality may degrade")
          
          return {
              'duration': duration,
              'sample_rate': sr,
              'channels': audio.shape[1] if len(audio.shape) > 1 else 1
          }
      
      def _convert_to_wav(self, input_path: str, output_path: str):
          """Converte áudio para WAV 24kHz mono"""
          audio, sr = sf.read(input_path)
          
          # Mono
          if len(audio.shape) > 1:
              audio = audio.mean(axis=1)
          
          # Resample se necessário
          if sr != self.sample_rate:
              import torchaudio.functional as F
              audio_tensor = torch.from_numpy(audio).float()
              audio_tensor = F.resample(audio_tensor, sr, self.sample_rate)
              audio = audio_tensor.numpy()
          
          # Salva
          sf.write(output_path, audio, self.sample_rate)
          logger.info(f"  Converted to WAV: {output_path}")
      
      def unload_models(self):
          """Libera memória"""
          del self.f5tts
          if self.device == 'cuda':
              torch.cuda.empty_cache()
          logger.info("F5-TTS models unloaded")
  ```

- [ ] **3.3.2** Adicionar config F5-TTS em `app/config.py`
  ```python
  # Linha ~150 (após openvoice config)
  'f5tts': {
      'model': os.getenv('F5TTS_MODEL', 'F5TTS_v1_Base'),
      'device': os.getenv('F5TTS_DEVICE', 'cuda'),
      'hf_cache_dir': os.getenv('F5TTS_CACHE', '/app/models/f5tts'),
      'nfe_step': int(os.getenv('F5TTS_NFE_STEP', '32')),
      'target_rms': float(os.getenv('F5TTS_TARGET_RMS', '0.1')),
  },
  ```

#### 3.4. Implementar Factory Pattern em Processor
- [ ] **3.4.1** Modificar `app/processor.py`
  ```python
  # Linha 14
  from .openvoice_client import OpenVoiceClient
  from .f5tts_client import F5TTSClient
  from .tts_interface import TTSEngine
  
  # Linha 18
  class VoiceProcessor:
      """Processa jobs de dublagem e clonagem de voz"""
      
      def __init__(self):
          self.settings = get_settings()
          
          # Factory: escolhe motor por env var
          engine = os.getenv('TTS_ENGINE', 'openvoice')
          logger.info(f"Initializing TTS engine: {engine}")
          
          if engine == 'f5tts':
              self.tts_client: TTSEngine = F5TTSClient()
          elif engine == 'openvoice':
              self.tts_client: TTSEngine = OpenVoiceClient()
          else:
              raise ValueError(f"Unknown TTS_ENGINE: {engine}")
          
          self.job_store = None  # Será injetado no main.py
  ```

- [ ] **3.4.2** Substituir chamadas `self.openvoice_client` por `self.tts_client`
  ```bash
  # Em processor.py, substituir todas as ocorrências:
  # self.openvoice_client.generate_dubbing → self.tts_client.generate_dubbing
  # self.openvoice_client.clone_voice → self.tts_client.clone_voice
  ```

#### 3.5. Atualizar VoiceProfile model
- [ ] **3.5.1** Modificar `app/models.py`
  ```python
  # Linha ~120 (VoiceProfile)
  class VoiceProfile(BaseModel):
      id: str
      name: str
      language: str
      description: Optional[str] = None
      
      # === NOVO: F5-TTS usa áudio direto ===
      reference_audio_path: Optional[str] = None  # NOVO
      reference_text: Optional[str] = None        # NOVO
      
      # === ANTIGO: OpenVoice usava embedding ===
      embedding: Optional[Any] = None  # deprecated, manter para migração
      profile_path: str  # path para .pkl (deprecated) ou .wav (novo)
      
      source_audio_path: Optional[str] = None
      duration: Optional[float] = None
      sample_rate: Optional[int] = None
      created_at: datetime = Field(default_factory=datetime.now)
      
      class Config:
          arbitrary_types_allowed = True
  ```

#### 3.6. Teste de integração básico
- [ ] **3.6.1** Criar `tests/integration/test_f5tts_integration.py`
  ```python
  """Teste de integração F5TTSClient"""
  import pytest
  from app.f5tts_client import F5TTSClient
  from app.models import VoiceProfile
  
  @pytest.mark.asyncio
  async def test_f5tts_generate_dubbing():
      client = F5TTSClient(device='cpu')
      
      audio_bytes, duration = await client.generate_dubbing(
          text="Hello world",
          language="en",
          voice_preset="female_generic"
      )
      
      assert len(audio_bytes) > 0
      assert duration > 0
      print(f"✅ Generated {len(audio_bytes)} bytes, {duration:.2f}s")
  
  @pytest.mark.asyncio
  async def test_f5tts_clone_voice():
      client = F5TTSClient(device='cpu')
      
      profile = await client.clone_voice(
          audio_path="/app/tests/Teste.mp3",
          language="pt",
          voice_name="Test Voice"
      )
      
      assert profile.reference_audio_path is not None
      assert profile.reference_text is not None
      assert len(profile.reference_text) > 0
      print(f"✅ Cloned voice: {profile.id}")
      print(f"   Transcription: {profile.reference_text}")
  ```

- [ ] **3.6.2** Rodar testes
  ```bash
  docker exec audio-voice-api pytest /app/tests/integration/test_f5tts_integration.py -v
  ```

### Critérios de aceite Sprint 2
- [x] Interface `TTSEngine` criada
- [x] `OpenVoiceClient` implementa `TTSEngine`
- [x] `F5TTSClient` criado e implementa `TTSEngine`
- [x] `VoiceProcessor` usa factory pattern (TTS_ENGINE env var)
- [x] `VoiceProfile` atualizado com campos F5-TTS
- [x] Testes de integração passam

---

## 4. Sprint 3 – Testes unitários e de comparação com Teste.mp3

### Objetivo
Validar funcionalidade e qualidade usando `tests/Teste.mp3` ("Oi, tudo bem?")

### Duração estimada
4-6 horas

### Tarefas

#### 4.1. Teste unitário de clonagem
- [ ] **4.1.1** Criar `tests/unit/test_f5tts_clone.py`
  ```python
  """Testes unitários de clonagem F5-TTS"""
  import pytest
  from pathlib import Path
  from app.f5tts_client import F5TTSClient
  
  TEST_AUDIO = Path("/app/tests/Teste.mp3")
  
  @pytest.mark.asyncio
  async def test_clone_voice_creates_profile():
      """Testa se clonagem cria perfil válido"""
      client = F5TTSClient(device='cpu')
      
      profile = await client.clone_voice(
          audio_path=str(TEST_AUDIO),
          language="pt",
          voice_name="Teste Voice João"
      )
      
      # Valida perfil
      assert profile.id is not None
      assert profile.name == "Teste Voice João"
      assert profile.language == "pt"
      
      # Valida campos F5-TTS
      assert profile.reference_audio_path is not None
      assert Path(profile.reference_audio_path).exists()
      assert profile.reference_text is not None
      assert len(profile.reference_text) > 0
      
      # Valida transcrição
      ref_lower = profile.reference_text.lower()
      assert "oi" in ref_lower or "tudo" in ref_lower
      
      print(f"✅ Profile created: {profile.id}")
      print(f"   Audio: {profile.reference_audio_path}")
      print(f"   Text: {profile.reference_text}")
  
  @pytest.mark.asyncio
  async def test_clone_voice_validates_duration():
      """Testa se valida duração do áudio"""
      client = F5TTSClient(device='cpu')
      
      profile = await client.clone_voice(
          audio_path=str(TEST_AUDIO),
          language="pt",
          voice_name="Duration Test"
      )
      
      assert profile.duration is not None
      assert profile.duration > 0
      assert profile.duration < 15  # Teste.mp3 tem ~2.4s
      
      print(f"✅ Duration validated: {profile.duration:.2f}s")
  ```

- [ ] **4.1.2** Rodar testes unitários
  ```bash
  docker exec audio-voice-api pytest /app/tests/unit/test_f5tts_clone.py -v -s
  ```

#### 4.2. Teste de síntese com voz clonada
- [ ] **4.2.1** Criar `tests/unit/test_f5tts_synthesis.py`
  ```python
  """Testes unitários de síntese F5-TTS"""
  import pytest
  from pathlib import Path
  from app.f5tts_client import F5TTSClient
  
  TEST_AUDIO = Path("/app/tests/Teste.mp3")
  
  @pytest.mark.asyncio
  async def test_synthesis_with_cloned_voice():
      """Testa síntese com voz clonada de Teste.mp3"""
      client = F5TTSClient(device='cpu')
      
      # Clona voz
      profile = await client.clone_voice(
          audio_path=str(TEST_AUDIO),
          language="pt",
          voice_name="Síntese Test"
      )
      
      # Sintetiza frase DIFERENTE
      audio_bytes, duration = await client.generate_dubbing(
          text="Esta é uma nova frase gerada pela inteligência artificial",
          language="pt",
          voice_profile=profile,
          speed=1.0
      )
      
      # Valida saída
      assert len(audio_bytes) > 0
      assert duration > 0
      assert duration > 1.0  # frase razoavelmente longa
      
      # Salva para inspeção manual
      output_path = Path("/app/tests/output_clone_analysis/f5tts_synthesis_test.wav")
      output_path.parent.mkdir(exist_ok=True, parents=True)
      with open(output_path, 'wb') as f:
          f.write(audio_bytes)
      
      print(f"✅ Synthesis completed")
      print(f"   Duration: {duration:.2f}s")
      print(f"   Size: {len(audio_bytes)} bytes")
      print(f"   Saved: {output_path}")
  
  @pytest.mark.asyncio
  async def test_synthesis_same_text_as_reference():
      """Testa síntese do MESMO texto da referência"""
      client = F5TTSClient(device='cpu')
      
      # Clona voz
      profile = await client.clone_voice(
          audio_path=str(TEST_AUDIO),
          language="pt",
          voice_name="Same Text Test"
      )
      
      # Sintetiza MESMO texto: "Oi, tudo bem?"
      audio_bytes, duration = await client.generate_dubbing(
          text="Oi, tudo bem?",
          language="pt",
          voice_profile=profile,
          speed=1.0
      )
      
      # Valida
      assert len(audio_bytes) > 0
      assert duration > 0
      
      # Deve ter duração similar ao original (~2.4s)
      assert 1.0 < duration < 5.0
      
      # Salva
      output_path = Path("/app/tests/output_clone_analysis/f5tts_same_text.wav")
      with open(output_path, 'wb') as f:
          f.write(audio_bytes)
      
      print(f"✅ Same-text synthesis: {duration:.2f}s")
  ```

- [ ] **4.2.2** Rodar testes de síntese
  ```bash
  docker exec audio-voice-api pytest /app/tests/unit/test_f5tts_synthesis.py -v -s
  ```

#### 4.3. Comparação OpenVoice vs F5-TTS
- [ ] **4.3.1** Criar `tests/comparison/test_engines_comparison.py`
  ```python
  """Compara qualidade: OpenVoice (mock) vs F5-TTS (real)"""
  import pytest
  from pathlib import Path
  from app.openvoice_client import OpenVoiceClient
  from app.f5tts_client import F5TTSClient
  
  TEST_AUDIO = Path("/app/tests/Teste.mp3")
  TEST_TEXT = "Oi, tudo bem?"
  
  @pytest.mark.asyncio
  async def test_compare_quality():
      """Compara qualidade de síntese"""
      
      # === OpenVoice (mock) ===
      ov_client = OpenVoiceClient(device='cpu')
      ov_client._load_models()
      
      # Clona
      ov_profile = await ov_client.clone_voice(
          audio_path=str(TEST_AUDIO),
          language="pt",
          voice_name="OV Test"
      )
      
      # Sintetiza
      ov_bytes, ov_dur = await ov_client.generate_dubbing(
          text=TEST_TEXT,
          language="pt",
          voice_profile=ov_profile
      )
      
      # Salva
      ov_path = Path("/app/tests/output_clone_analysis/openvoice_output.wav")
      with open(ov_path, 'wb') as f:
          f.write(ov_bytes)
      
      # === F5-TTS (real) ===
      f5_client = F5TTSClient(device='cpu')
      
      # Clona
      f5_profile = await f5_client.clone_voice(
          audio_path=str(TEST_AUDIO),
          language="pt",
          voice_name="F5 Test"
      )
      
      # Sintetiza
      f5_bytes, f5_dur = await f5_client.generate_dubbing(
          text=TEST_TEXT,
          language="pt",
          voice_profile=f5_profile
      )
      
      # Salva
      f5_path = Path("/app/tests/output_clone_analysis/f5tts_output.wav")
      with open(f5_path, 'wb') as f:
          f.write(f5_bytes)
      
      # === Comparação básica ===
      print("\n" + "="*60)
      print("COMPARISON RESULTS")
      print("="*60)
      print(f"OpenVoice (mock):")
      print(f"  Duration: {ov_dur:.2f}s")
      print(f"  Size: {len(ov_bytes)} bytes")
      print(f"  Saved: {ov_path}")
      
      print(f"\nF5-TTS (real):")
      print(f"  Duration: {f5_dur:.2f}s")
      print(f"  Size: {len(f5_bytes)} bytes")
      print(f"  Saved: {f5_path}")
      
      print("\n👂 NEXT STEP: Listen to both files manually!")
      print("="*60)
      
      # Valida que ambos geraram algo
      assert len(ov_bytes) > 0
      assert len(f5_bytes) > 0
  ```

- [ ] **4.3.2** Rodar comparação
  ```bash
  docker exec audio-voice-api pytest /app/tests/comparison/test_engines_comparison.py -v -s
  ```

#### 4.4. Integração com suite de qualidade existente
- [ ] **4.4.1** Modificar `tests/test_voice_clone_quality.py`
  ```python
  # Linha ~25 (após imports)
  from app.f5tts_client import F5TTSClient
  
  # Linha ~40 (classe VoiceCloneQualityTest)
  def __init__(self, engine='f5tts'):
      if engine == 'f5tts':
          self.client = F5TTSClient(device='cpu')
      else:
          from app.openvoice_client import OpenVoiceClient
          self.client = OpenVoiceClient(device='cpu')
      
      self.client._load_models()  # OpenVoice compatibilidade
      # ... resto igual
  ```

- [ ] **4.4.2** Criar script comparativo `tests/run_quality_comparison.sh`
  ```bash
  #!/bin/bash
  
  echo "================================="
  echo "🧪 Quality Comparison Test"
  echo "================================="
  echo ""
  
  # Para containers
  docker compose down
  
  # Build
  docker compose build
  docker compose up -d
  
  # Aguarda API
  sleep 10
  
  # === OpenVoice ===
  echo "Testing OpenVoice (mock)..."
  docker exec audio-voice-api python -c "
  from tests.test_voice_clone_quality import VoiceCloneQualityTest
  test = VoiceCloneQualityTest(engine='openvoice')
  test.run_test()
  " > /tmp/openvoice_quality.txt 2>&1
  
  # Renomeia saída
  mv tests/output_clone_analysis tests/output_clone_openvoice
  
  # === F5-TTS ===
  echo "Testing F5-TTS (real)..."
  docker exec audio-voice-api python -c "
  from tests.test_voice_clone_quality import VoiceCloneQualityTest
  test = VoiceCloneQualityTest(engine='f5tts')
  test.run_test()
  " > /tmp/f5tts_quality.txt 2>&1
  
  # Renomeia saída
  mv tests/output_clone_analysis tests/output_clone_f5tts
  
  # Compara resultados
  echo ""
  echo "================================="
  echo "📊 RESULTS COMPARISON"
  echo "================================="
  
  echo "OpenVoice:"
  cat /tmp/openvoice_quality.txt | grep -A 5 "QUALITY SCORE"
  
  echo ""
  echo "F5-TTS:"
  cat /tmp/f5tts_quality.txt | grep -A 5 "QUALITY SCORE"
  
  echo ""
  echo "Files saved:"
  echo "  OpenVoice: tests/output_clone_openvoice/"
  echo "  F5-TTS: tests/output_clone_f5tts/"
  ```

- [ ] **4.4.3** Rodar comparação completa
  ```bash
  chmod +x tests/run_quality_comparison.sh
  ./tests/run_quality_comparison.sh
  ```

#### 4.5. Análise de resultados
- [ ] **4.5.1** Comparar métricas
  ```bash
  # OpenVoice (baseline ruim)
  cat tests/output_clone_openvoice/analysis_results_*.json | jq '.comparison'
  
  # F5-TTS (esperado melhor)
  cat tests/output_clone_f5tts/analysis_results_*.json | jq '.comparison'
  ```

- [ ] **4.5.2** Ouvir áudios gerados
  ```bash
  # OpenVoice (bibs)
  play tests/output_clone_openvoice/cloned_audio.wav
  
  # F5-TTS (fala natural esperada)
  play tests/output_clone_f5tts/cloned_audio.wav
  ```

- [ ] **4.5.3** Validar critérios de qualidade
  - [ ] Spectral Centroid Error < 20% (vs 112% OpenVoice)
  - [ ] Formantes detectados: 3/3 (vs 0/3 OpenVoice)
  - [ ] Energy Ratio: 0.8-1.2 (vs 14.8 OpenVoice)
  - [ ] Pitch Error < 30 Hz (vs 114 Hz OpenVoice)
  - [ ] Sem "bibs eletrônicos"

### Critérios de aceite Sprint 3
- [x] Testes unitários de clonagem passam
- [x] Testes de síntese passam
- [x] Comparação OpenVoice vs F5-TTS executada
- [x] F5-TTS passa em ≥4/5 critérios de qualidade
- [x] Áudio F5-TTS soa como fala natural (subjetivo)

---

## 5. Sprint 4 – Troca definitiva do motor e limpeza

### Objetivo
Trocar motor padrão para F5-TTS e validar em produção.

### Duração estimada
3-4 horas

### Tarefas

#### 5.1. Atualizar configuração padrão
- [ ] **5.1.1** Criar/atualizar `.env`
  ```bash
  # TTS Engine
  TTS_ENGINE=f5tts  # ← MUDANÇA CRÍTICA
  
  # F5-TTS Settings
  F5TTS_MODEL=F5TTS_v1_Base
  F5TTS_DEVICE=cuda
  F5TTS_CACHE=/app/models/f5tts
  F5TTS_NFE_STEP=32
  F5TTS_TARGET_RMS=0.1
  ```

- [ ] **5.1.2** Atualizar docker-compose.yml
  ```yaml
  # Linha ~20 (environment)
  environment:
    - TTS_ENGINE=f5tts  # ← ADICIONAR
    - F5TTS_DEVICE=cuda
    - CUDA_VISIBLE_DEVICES=0
  ```

#### 5.2. Criar presets de voz
- [ ] **5.2.1** Criar diretório de presets
  ```bash
  mkdir -p voice_profiles/presets
  ```

- [ ] **5.2.2** Gerar áudios de preset
  ```python
  # scripts/create_voice_presets.py
  """Cria presets de voz para F5-TTS"""
  from gtts import gTTS
  from pathlib import Path
  
  presets = {
      'female_generic': "Hello, this is a female voice preset.",
      'male_deep': "Hello, this is a male voice preset.",
      'female_pt': "Olá, esta é uma voz feminina em português.",
      'male_pt': "Olá, esta é uma voz masculina em português.",
  }
  
  output_dir = Path("/app/voice_profiles/presets")
  
  for name, text in presets.items():
      lang = 'pt' if '_pt' in name else 'en'
      output = output_dir / f"{name}.mp3"
      
      tts = gTTS(text, lang=lang)
      tts.save(str(output))
      
      print(f"✅ Created: {output}")
  ```

- [ ] **5.2.3** Rodar script
  ```bash
  docker exec audio-voice-api python /app/scripts/create_voice_presets.py
  ```

#### 5.3. Migração de VoiceProfiles existentes
- [ ] **5.3.1** Criar script `scripts/migrate_voice_profiles.py`
  ```python
  """Migra VoiceProfiles de OpenVoice (.pkl) para F5-TTS (.wav)"""
  import os
  import pickle
  import shutil
  from pathlib import Path
  from app.redis_store import RedisJobStore
  from app.f5tts_client import F5TTSClient
  
  def migrate_profiles():
      store = RedisJobStore()
      f5tts = F5TTSClient(device='cpu')
      
      profiles = store.get_all_voice_profiles()
      
      for profile in profiles:
          print(f"\nMigrating profile: {profile.id}")
          
          # Já migrado?
          if profile.reference_audio_path:
              print("  ✅ Already migrated")
              continue
          
          # Áudio original existe?
          if profile.source_audio_path and Path(profile.source_audio_path).exists():
              original_audio = profile.source_audio_path
              print(f"  Using original: {original_audio}")
          else:
              print("  ⚠️  Original audio not found, skipping")
              continue
          
          # Copia para voice_profiles
          new_path = Path(f"/app/voice_profiles/{profile.id}.wav")
          shutil.copy(original_audio, new_path)
          
          # Transcreve
          ref_text = f5tts.f5tts.transcribe(str(new_path), profile.language)
          
          # Atualiza profile
          profile.reference_audio_path = str(new_path)
          profile.reference_text = ref_text
          
          # Salva
          store.save_voice_profile(profile)
          
          print(f"  ✅ Migrated: {new_path}")
          print(f"     Text: {ref_text}")
  
  if __name__ == "__main__":
      migrate_profiles()
  ```

- [ ] **5.3.2** Rodar migração (se houver profiles)
  ```bash
  docker exec audio-voice-api python /app/scripts/migrate_voice_profiles.py
  ```

#### 5.4. Validação end-to-end
- [ ] **5.4.1** Teste de dublagem via API
  ```bash
  # Criar job
  curl -X POST http://localhost:8005/jobs \
    -H "Content-Type: application/json" \
    -d '{
      "mode": "dubbing",
      "text": "Teste de dublagem com F5-TTS",
      "source_language": "pt",
      "voice_preset": "female_generic"
    }'
  
  # Aguardar job
  JOB_ID="..." # pegar do response
  sleep 5
  
  # Baixar áudio
  curl http://localhost:8005/jobs/$JOB_ID/download -o /tmp/f5tts_api_test.wav
  
  # Ouvir
  play /tmp/f5tts_api_test.wav
  ```

- [ ] **5.4.2** Teste de clonagem via API
  ```bash
  # Upload áudio
  curl -X POST http://localhost:8005/voices/clone \
    -F "audio=@tests/Teste.mp3" \
    -F "voice_name=API Test Voice" \
    -F "language=pt"
  
  # Pegar voice_id
  VOICE_ID="..." # do response
  
  # Dublar com voz clonada
  curl -X POST http://localhost:8005/jobs \
    -H "Content-Type: application/json" \
    -d "{
      \"mode\": \"dubbing_with_clone\",
      \"text\": \"Esta é uma frase dublada com minha voz clonada\",
      \"source_language\": \"pt\",
      \"voice_id\": \"$VOICE_ID\"
    }"
  
  # Baixar e ouvir
  JOB_ID="..."
  curl http://localhost:8005/jobs/$JOB_ID/download -o /tmp/f5tts_clone_api_test.wav
  play /tmp/f5tts_clone_api_test.wav
  ```

- [ ] **5.4.3** Validar logs
  ```bash
  docker logs audio-voice-celery | grep "F5-TTS"
  # Deve mostrar logs de F5-TTS, não OpenVoice
  ```

#### 5.5. Testes de carga (opcional)
- [ ] **5.5.1** Criar 10 jobs simultâneos
  ```bash
  for i in {1..10}; do
    curl -X POST http://localhost:8005/jobs \
      -H "Content-Type: application/json" \
      -d "{
        \"mode\": \"dubbing\",
        \"text\": \"Teste de carga número $i\",
        \"source_language\": \"pt\",
        \"voice_preset\": \"female_pt\"
      }" &
  done
  wait
  ```

- [ ] **5.5.2** Monitorar GPU/CPU
  ```bash
  # GPU
  watch -n 1 nvidia-smi
  
  # CPU/Memory
  docker stats
  ```

#### 5.6. Documentação
- [ ] **5.6.1** Atualizar README principal
  ```markdown
  # Audio Voice Service
  
  ## TTS Engine
  
  Atualmente usando **F5-TTS** (https://github.com/SWivid/F5-TTS)
  
  ### Features
  - Zero-shot voice cloning
  - Naturalidade superior
  - Multi-idioma (EN, ZH, PT*)
  
  ### Migração de OpenVoice
  Ver `CONVERTER.md` e `SPRINT.md` para detalhes técnicos.
  ```

- [ ] **5.6.2** Atualizar docs da API
  ```bash
  # Adicionar nota em docs/services/audio-voice/README.md
  echo "## TTS Engine: F5-TTS" >> docs/services/audio-voice/README.md
  echo "Migration completed: $(date)" >> docs/services/audio-voice/README.md
  ```

### Critérios de aceite Sprint 4
- [x] `TTS_ENGINE=f5tts` definido como padrão
- [x] Presets de voz criados
- [x] VoiceProfiles existentes migrados (se houver)
- [x] API funciona end-to-end com F5-TTS
- [x] Qualidade de áudio validada manualmente
- [x] Documentação atualizada

---

## 6. Sprint 5 (Opcional) – Limpeza do OpenVoice

### Objetivo
Remover código obsoleto do OpenVoice após validação completa.

### Duração estimada
2-3 horas

### Tarefas

#### 6.1. Validação de segurança
- [ ] **6.1.1** Confirmar que F5-TTS está estável em produção (mínimo 1 semana)
- [ ] **6.1.2** Backup de código completo
  ```bash
  git tag pre-openvoice-removal
  git push --tags
  ```

#### 6.2. Remoção de código OpenVoice
- [ ] **6.2.1** Marcar como deprecated
  ```python
  # app/openvoice_client.py linha 1
  """
  DEPRECATED: Este módulo está obsoleto.
  Use f5tts_client.py para produção.
  Mantido apenas para referência histórica.
  """
  import warnings
  warnings.warn("OpenVoiceClient is deprecated, use F5TTSClient", DeprecationWarning)
  ```

- [ ] **6.2.2** Remover de processor.py
  ```python
  # app/processor.py
  # REMOVER:
  # from .openvoice_client import OpenVoiceClient
  # elif engine == 'openvoice':
  #     self.tts_client: TTSEngine = OpenVoiceClient()
  ```

- [ ] **6.2.3** Remover factory logic
  ```python
  # Simplificar para:
  def __init__(self):
      self.settings = get_settings()
      self.tts_client = F5TTSClient()  # direto
      self.job_store = None
  ```

#### 6.3. Limpeza de dependências
- [ ] **6.3.1** Remover comentários de OpenVoice do requirements.txt
- [ ] **6.3.2** Rebuild Docker
  ```bash
  docker compose down
  docker compose build --no-cache
  docker compose up -d
  ```

#### 6.4. Arquivamento
- [ ] **6.4.1** Mover OpenVoiceClient para archive
  ```bash
  mkdir -p app/archive
  git mv app/openvoice_client.py app/archive/
  git commit -m "Archive OpenVoiceClient (replaced by F5-TTS)"
  ```

### Critérios de aceite Sprint 5
- [x] OpenVoiceClient marcado como deprecated
- [x] Código removido de produção
- [x] Dependências limpas
- [x] Serviço funciona sem OpenVoice

---

## 7. Resumo de sprints

| Sprint | Objetivo | Duração | Status |
|--------|----------|---------|--------|
| 1 | Ambiente F5-TTS | 4-6h | ⏳ Pendente |
| 2 | Adapter + Interface | 6-8h | ⏳ Pendente |
| 3 | Testes + Qualidade | 4-6h | ⏳ Pendente |
| 4 | Troca + Produção | 3-4h | ⏳ Pendente |
| 5 | Limpeza (opcional) | 2-3h | ⏳ Pendente |

**Total estimado**: 19-27 horas (2-3 dias de trabalho)

---

## 8. Métricas de sucesso

### Técnicas
- [x] Build Docker sem erros
- [x] F5-TTS importa e instancia
- [x] API mantém compatibilidade
- [x] Testes automatizados passam
- [x] Espectral Centroid Error < 20%
- [x] Formantes detectados: 3/3
- [x] Energy Ratio: 0.8-1.2

### Qualidade de áudio
- [x] Sem "bibs eletrônicos" ❌ → ✅
- [x] Inteligibilidade > 95%
- [x] Naturalidade subjetiva "boa" ou "excelente"
- [x] Teste cego: preferência por F5-TTS > 80%

### Performance
- [x] Latência < 5s para frase curta
- [x] GPU memory < 8GB
- [x] 10 jobs simultâneos sem crash

---

## 9. Riscos e contingências

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| F5-TTS qualidade inferior em PT | Baixa | Alto | Testar extensivamente, considerar fine-tuning |
| Latência muito alta | Média | Médio | Reduzir nfe_step, otimizar batch |
| GPU OOM | Baixa | Alto | Rodar Whisper em CPU, limitar concorrência |
| Migração perde profiles | Baixa | Médio | Backup antes, validação pós-migração |
| Bugs em produção | Média | Alto | Feature flag permite rollback rápido |

---

## 10. Checklist final

Antes de considerar CONCLUÍDO:

- [ ] Todos os testes passam
- [ ] Áudio F5-TTS soa natural (escuta manual)
- [ ] API funciona end-to-end
- [ ] Documentação atualizada
- [ ] Código committed e tagged
- [ ] Equipe treinada (se aplicável)
- [ ] Monitoramento configurado
- [ ] Rollback plan documentado

---

**Status**: 🟡 Planejamento completo, aguardando execução

**Próximo passo**: Executar Sprint 1
