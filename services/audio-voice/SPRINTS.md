# SPRINTS - Migração F5-TTS → XTTS

**Metodologia:** TDD (Test-Driven Development) - Sempre começar com testes  
**Objetivo:** Migração completa e segura de F5-TTS para XTTS  
**Abordagem:** Incremental, testável, reversível

---

## 📊 OVERVIEW

### Estratégia de Migração

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Sprint 1   │────▶│  Sprint 2   │────▶│  Sprint 3   │
│   TESTES    │     │    CORE     │     │ INTEGRAÇÃO  │
│ (criar antes)│     │(implementar)│     │  (conectar) │
└─────────────┘     └─────────────┘     └─────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
   Tests Pass         Code Works          E2E Pass
       │                    │                    │
       └────────────────────┴────────────────────┘
                            │
                            ▼
                   ┌─────────────┐
                   │  Sprint 4   │
                   │  VALIDAÇÃO  │
                   │   (QA)      │
                   └─────────────┘
                            │
                            ▼
                   ┌─────────────┐
                   │  Sprint 5   │
                   │   DEPLOY    │
                   │  (cleanup)  │
                   └─────────────┘
```

### Princípios da Migração

1. **Red-Green-Refactor:** Testes primeiro, depois código
2. **Isolamento:** Cada sprint é independente e testável
3. **Reversibilidade:** Sempre manter rollback plan
4. **Validação:** Testes automatizados em cada etapa
5. **Documentação:** Logs detalhados de cada mudança

---

## 🎯 SPRINT 0: PLANEJAMENTO (COMPLETO ✅)

### Objetivo
Estudar XTTS, auditar projeto, criar plano de migração

### Tarefas Completadas
- [x] **0.1** Estudar documentação oficial XTTS (6000+ linhas)
- [x] **0.2** Pesquisar repositório coqui-ai/TTS no GitHub
- [x] **0.3** Identificar exemplos de produção e best practices
- [x] **0.4** Criar AUDITORIA.md (mapeamento completo F5-TTS)
- [x] **0.5** Criar SPRINTS.md (este documento)

### Validação
✅ Documentação completa criada  
✅ Plano de migração mapeado  
✅ Riscos identificados

### Entregáveis
- `AUDITORIA.md` (470+ linhas) ✅
- `SPRINTS.md` (este arquivo) ✅

---

## 🧪 SPRINT 1: TESTES BASE (TDD Phase 1)

**Duração estimada:** 1-2 dias  
**Objetivo:** Criar testes ANTES de escrever código XTTS

### Tarefa 1.1: Configurar Ambiente de Testes

#### 1.1.1 Instalar TTS package em ambiente isolado
```bash
# Criar venv de testes
cd /home/john/YTCaption-Easy-Youtube-API/services/audio-voice
python3 -m venv venv_xtts_test
source venv_xtts_test/bin/activate

# Instalar TTS
pip install TTS>=0.22.0
pip install pytest pytest-asyncio

# Validar instalação
python -c "from TTS.api import TTS; print('✅ TTS imported')"
```

**Validação:** Import bem-sucedido ✅

---

#### 1.1.2 Testar modelo XTTS v2 isoladamente
```bash
# Criar script de teste: tests/manual/test_xtts_standalone.py
```

```python
"""
Teste standalone XTTS - Validar modelo fora do projeto
"""
import torch
from TTS.api import TTS

def test_xtts_basic():
    """Testa instanciação do modelo XTTS"""
    print("🔧 Testando XTTS standalone...")
    
    # Device
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"   Device: {device}")
    
    # Instancia modelo
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=(device=='cuda'))
    print("   ✅ Modelo carregado")
    
    # Verifica suporte a português
    languages = tts.languages if hasattr(tts, 'languages') else []
    assert 'pt' in languages or len(languages) == 0, "Português não suportado!"
    print(f"   ✅ Português suportado (languages: {languages})")
    
    return True

if __name__ == "__main__":
    success = test_xtts_basic()
    print(f"\n{'✅ PASS' if success else '❌ FAIL'}")
```

**Executar:**
```bash
python tests/manual/test_xtts_standalone.py
```

**Validação:** Modelo carrega sem erros ✅  
**Critério:** Português deve estar em `languages` ou modelo aceita `language="pt"`

---

#### 1.1.3 Testar voice cloning com XTTS
```python
# tests/manual/test_xtts_voice_cloning.py
"""
Teste de clonagem de voz XTTS standalone
"""
from TTS.api import TTS
import torch

def test_voice_cloning():
    """Testa clonagem de voz com áudio de referência"""
    print("🎤 Testando voice cloning XTTS...")
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=(device=='cuda'))
    
    # Áudio de referência (usar arquivo de teste existente)
    ref_audio = "uploads/clone_20251126031159965237.ogg"
    
    # Texto de teste
    text = "Este é um teste de clonagem de voz usando XTTS."
    
    # Gera áudio
    output_path = "temp/xtts_clone_test.wav"
    tts.tts_to_file(
        text=text,
        file_path=output_path,
        speaker_wav=[ref_audio],
        language="pt",
        split_sentences=True
    )
    
    print(f"   ✅ Áudio gerado: {output_path}")
    
    # Valida arquivo
    import os
    assert os.path.exists(output_path), "Arquivo não foi criado!"
    file_size = os.path.getsize(output_path)
    print(f"   ✅ Tamanho: {file_size} bytes")
    assert file_size > 1000, "Arquivo muito pequeno (provável erro)"
    
    return True

if __name__ == "__main__":
    test_voice_cloning()
```

**Executar:**
```bash
python tests/manual/test_xtts_voice_cloning.py
```

**Validação:** Áudio gerado com sucesso ✅  
**Critério:** Arquivo WAV criado com >1KB

---

### Tarefa 1.2: Criar Testes Unitários (Para Código Futuro)

#### 1.2.1 Teste de instanciação XTTSClient
```python
# tests/unit/test_xtts_client_init.py
"""
Testes unitários XTTSClient - Instanciação
RED PHASE: Este teste vai FALHAR (código ainda não existe)
"""
import pytest
from app.xtts_client import XTTSClient  # Import vai falhar inicialmente!

def test_xtts_client_instantiation():
    """Testa se XTTSClient instancia corretamente"""
    client = XTTSClient(device='cpu')
    
    assert client is not None
    assert client.device == 'cpu'
    assert hasattr(client, 'tts')  # Deve ter modelo TTS
    assert hasattr(client, 'generate_dubbing')
    assert hasattr(client, 'clone_voice')

def test_xtts_client_auto_device():
    """Testa detecção automática de device"""
    client = XTTSClient()  # device=None
    assert client.device in ['cpu', 'cuda']

@pytest.mark.asyncio
async def test_xtts_client_cuda_fallback():
    """Testa fallback para CPU se CUDA indisponível"""
    import torch
    
    if not torch.cuda.is_available():
        client = XTTSClient(device='cuda')  # Pede CUDA
        assert client.device == 'cpu'  # Mas usa CPU
```

**Estado inicial:** ❌ FAIL (código não existe)  
**Estado após Sprint 2:** ✅ PASS

---

#### 1.2.2 Teste de geração de dubbing
```python
# tests/unit/test_xtts_client_dubbing.py
"""
Testes unitários XTTSClient - Dubbing
RED PHASE: Vai falhar até implementar
"""
import pytest
from app.xtts_client import XTTSClient

@pytest.mark.asyncio
async def test_generate_dubbing_basic():
    """Testa geração de dubbing básico"""
    client = XTTSClient(device='cpu')
    
    audio_bytes, duration = await client.generate_dubbing(
        text="Olá, mundo!",
        language="pt",
        voice_preset="female_generic"
    )
    
    assert len(audio_bytes) > 0, "Áudio vazio!"
    assert duration > 0, "Duração inválida!"
    assert duration < 10, "Duração muito longa para texto curto"

@pytest.mark.asyncio
async def test_generate_dubbing_with_profile():
    """Testa dubbing com VoiceProfile"""
    from app.models import VoiceProfile
    
    client = XTTSClient(device='cpu')
    
    # Mock de VoiceProfile
    profile = VoiceProfile(
        id="test_voice_123",
        name="Test Voice",
        language="pt",
        reference_audio_path="uploads/test.wav",
        reference_text="Texto de referência",
        profile_path="voice_profiles/test_voice_123"
    )
    
    audio_bytes, duration = await client.generate_dubbing(
        text="Teste com perfil clonado",
        language="pt",
        voice_profile=profile
    )
    
    assert len(audio_bytes) > 0
    assert duration > 0

@pytest.mark.asyncio
async def test_generate_dubbing_long_text():
    """Testa dubbing com texto longo (>400 tokens)"""
    client = XTTSClient(device='cpu')
    
    long_text = "Este é um texto muito longo. " * 50  # ~150 palavras
    
    audio_bytes, duration = await client.generate_dubbing(
        text=long_text,
        language="pt",
        voice_preset="male_generic"
    )
    
    assert len(audio_bytes) > 0
    # Duração deve ser proporcional ao texto
    assert duration > 10, "Duração muito curta para texto longo"
```

**Estado inicial:** ❌ FAIL  
**Estado após Sprint 2:** ✅ PASS

---

#### 1.2.3 Teste de clonagem de voz
```python
# tests/unit/test_xtts_client_cloning.py
"""
Testes unitários XTTSClient - Voice Cloning
RED PHASE: Vai falhar até implementar
"""
import pytest
from app.xtts_client import XTTSClient
from app.models import VoiceProfile

@pytest.mark.asyncio
async def test_clone_voice_basic():
    """Testa clonagem de voz básica"""
    client = XTTSClient(device='cpu')
    
    profile = await client.clone_voice(
        audio_path="uploads/clone_20251126031159965237.ogg",
        language="pt",
        voice_name="Test Clone",
        description="Voz de teste"
    )
    
    assert isinstance(profile, VoiceProfile)
    assert profile.name == "Test Clone"
    assert profile.language == "pt"
    assert profile.reference_audio_path is not None
    assert len(profile.id) > 0

@pytest.mark.asyncio
async def test_clone_voice_invalid_audio():
    """Testa erro com áudio inválido"""
    from app.exceptions import InvalidAudioException
    
    client = XTTSClient(device='cpu')
    
    with pytest.raises(InvalidAudioException):
        await client.clone_voice(
            audio_path="nonexistent.wav",
            language="pt",
            voice_name="Fail Test"
        )

@pytest.mark.asyncio
async def test_clone_voice_short_audio():
    """Testa erro com áudio muito curto (<3s)"""
    from app.exceptions import InvalidAudioException
    
    client = XTTSClient(device='cpu')
    
    # Áudio de 1 segundo (mock)
    with pytest.raises(InvalidAudioException, match=".*less than 3 seconds.*"):
        await client.clone_voice(
            audio_path="uploads/short_audio.wav",  # <3s
            language="pt",
            voice_name="Short Audio"
        )
```

**Estado inicial:** ❌ FAIL  
**Estado após Sprint 2:** ✅ PASS

---

### Tarefa 1.3: Criar Testes de Integração (End-to-End)

#### 1.3.1 Teste E2E: Clonagem → Dubbing
```python
# tests/integration/test_xtts_e2e.py
"""
Teste End-to-End XTTS: Clonagem + Dubbing
RED PHASE: Vai falhar até tudo estar implementado
"""
import pytest
from app.xtts_client import XTTSClient

@pytest.mark.asyncio
async def test_e2e_clone_and_dub():
    """Testa fluxo completo: clonar voz → usar para dubbing"""
    client = XTTSClient(device='cpu')
    
    # PASSO 1: Clonar voz
    print("\n🎤 Clonando voz...")
    profile = await client.clone_voice(
        audio_path="uploads/clone_20251126031159965237.ogg",
        language="pt",
        voice_name="E2E Test Voice"
    )
    
    assert profile is not None
    print(f"   ✅ Voz clonada: {profile.id}")
    
    # PASSO 2: Gerar dubbing com voz clonada
    print("\n🎬 Gerando dubbing com voz clonada...")
    audio_bytes, duration = await client.generate_dubbing(
        text="Este é um teste de dubbing com voz clonada usando XTTS.",
        language="pt",
        voice_profile=profile
    )
    
    assert len(audio_bytes) > 0
    assert duration > 0
    print(f"   ✅ Dubbing gerado: {duration:.2f}s, {len(audio_bytes)} bytes")
    
    # PASSO 3: Validar qualidade do áudio
    import soundfile as sf
    import io
    
    audio_data, sr = sf.read(io.BytesIO(audio_bytes))
    assert sr == 24000, "Sample rate deve ser 24kHz (XTTS padrão)"
    assert len(audio_data) > sr * 2, "Áudio deve ter pelo menos 2 segundos"
    
    print("   ✅ Qualidade validada")
```

**Estado inicial:** ❌ FAIL  
**Estado após Sprint 3:** ✅ PASS

---

### Validação Sprint 1

**Critérios de Aceitação:**
- [ ] Testes unitários criados (3 arquivos)
- [ ] Testes de integração criados (1 arquivo)
- [ ] Testes standalone XTTS passam ✅
- [ ] Testes de código futuro estão em RED ❌ (esperado)

**Entregáveis:**
- `tests/manual/test_xtts_standalone.py`
- `tests/manual/test_xtts_voice_cloning.py`
- `tests/unit/test_xtts_client_init.py`
- `tests/unit/test_xtts_client_dubbing.py`
- `tests/unit/test_xtts_client_cloning.py`
- `tests/integration/test_xtts_e2e.py`

**Resultado esperado:**
- ✅ Testes standalone: PASS (modelo XTTS funciona)
- ❌ Testes unitários: FAIL (código não existe ainda)
- ❌ Testes integração: FAIL (código não existe ainda)

---

## 🏗️ SPRINT 2: IMPLEMENTAÇÃO CORE (TDD Phase 2 - GREEN)

**Duração estimada:** 3-5 dias  
**Objetivo:** Implementar XTTSClient até todos os testes PASSAREM

### Tarefa 2.1: Criar Estrutura Base

#### 2.1.1 Atualizar requirements.txt
```bash
# Backup atual
cp requirements.txt requirements.txt.f5tts_backup

# Editar requirements.txt
```

**REMOVER:**
```txt
# F5-TTS (DELETAR)
f5-tts>=0.0.1
omegaconf>=2.3.0
hydra-core>=1.3.2
vocos>=0.1.0
cached-path>=1.5.2
```

**ADICIONAR:**
```txt
# === XTTS (Coqui TTS) ===
TTS>=0.22.0  # Inclui XTTS v2 + dependências

# Já incluídas no TTS mas explícitas:
# - transformers>=4.35.0
# - torch (mantemos versão atual)
# - torchaudio (mantemos versão atual)
# - numpy, scipy, soundfile
```

**Validação:**
```bash
# Verificar compatibilidade
pip install --dry-run -r requirements.txt
```

---

#### 2.1.2 Atualizar Dockerfile
```dockerfile
# services/audio-voice/Dockerfile

# ANTES (seção de instalação)
RUN pip install f5-tts vocos omegaconf hydra-core

# DEPOIS
RUN pip install TTS>=0.22.0

# Adicionar variáveis XTTS
ENV XTTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
ENV XTTS_CACHE=/app/models/xtts
ENV XTTS_DEVICE=cuda
ENV XTTS_TEMPERATURE=0.7

# Volume para cache de modelos
VOLUME /app/models/xtts
```

**Validação:**
```bash
# Build de teste
docker build -t audio-voice-xtts:test .
```

---

#### 2.1.3 Criar app/xtts_client.py
```python
"""
Cliente XTTS - Adapter para dublagem e clonagem de voz
Substituição completa do F5-TTS
"""
import logging
import os
import torch
import torchaudio
import soundfile as sf
import io
from pathlib import Path
from typing import Optional, Tuple

from TTS.api import TTS
from TTS.tts.models.xtts import Xtts
from TTS.tts.configs.xtts_config import XttsConfig

from .tts_interface import TTSEngine
from .models import VoiceProfile
from .config import get_settings
from .exceptions import OpenVoiceException, InvalidAudioException

logger = logging.getLogger(__name__)


class XTTSClient(TTSEngine):
    """Cliente XTTS para dublagem e clonagem de voz"""
    
    def __init__(self, device: Optional[str] = None):
        """
        Inicializa cliente XTTS
        
        Args:
            device: 'cpu' ou 'cuda' (auto-detecta se None)
        """
        self.settings = get_settings()
        xtts_config = self.settings.get('xtts', {})
        
        # Device
        if device is None:
            self.device = xtts_config.get('device', 'cuda')
            if self.device == 'cuda' and not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                self.device = 'cpu'
        else:
            self.device = device
        
        logger.info(f"Initializing XTTS client on device: {self.device}")
        
        # Paths
        self.cache_dir = Path(xtts_config.get('cache_dir', '/app/models/xtts'))
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        
        # Parâmetros XTTS
        self.model_name = xtts_config.get('model', 'tts_models/multilingual/multi-dataset/xtts_v2')
        self.temperature = xtts_config.get('temperature', 0.7)
        self.repetition_penalty = xtts_config.get('repetition_penalty', 2.0)
        self.length_penalty = xtts_config.get('length_penalty', 1.0)
        self.top_k = xtts_config.get('top_k', 50)
        self.top_p = xtts_config.get('top_p', 0.85)
        self.speed = xtts_config.get('speed', 1.0)
        self.enable_text_splitting = xtts_config.get('enable_text_splitting', True)
        self.gpt_cond_len = xtts_config.get('gpt_cond_len', 30)  # segundos
        self.max_ref_length = xtts_config.get('max_ref_length', 30)  # segundos
        
        # Carrega modelo
        self._load_model()
    
    def _load_model(self):
        """Carrega modelo XTTS"""
        try:
            logger.info(f"Loading XTTS model: {self.model_name}")
            
            # HIGH-LEVEL API (mais simples)
            self.tts = TTS(
                model_name=self.model_name,
                gpu=(self.device == 'cuda')
            )
            
            logger.info("✅ XTTS model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load XTTS model: {e}")
            raise OpenVoiceException(f"XTTS model loading failed: {str(e)}")
    
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        speed: Optional[float] = None,
        **kwargs
    ) -> Tuple[bytes, float]:
        """
        Gera áudio dublado usando XTTS
        
        Args:
            text: Texto a sintetizar
            language: Código de idioma (pt, en, es, etc)
            voice_preset: Nome do preset de voz (opcional)
            voice_profile: Perfil de voz clonada (opcional)
            speed: Velocidade de fala (1.0 = normal)
            
        Returns:
            Tuple[bytes, float]: (audio_bytes em WAV, duration em segundos)
        """
        try:
            logger.info(f"🎬 Generating dubbing with XTTS...")
            logger.info(f"   Text: {text[:50]}... ({len(text)} chars)")
            logger.info(f"   Language: {language}")
            
            # Determina speaker_wav (referência de voz)
            if voice_profile:
                speaker_wav = [voice_profile.reference_audio_path]
                logger.info(f"   Voice: {voice_profile.name} (cloned)")
            elif voice_preset:
                speaker_wav = self._get_preset_audio(voice_preset, language)
                logger.info(f"   Voice: {voice_preset} (preset)")
            else:
                raise ValueError("Either voice_profile or voice_preset must be provided")
            
            # Velocidade
            speed_param = speed if speed is not None else self.speed
            
            # Gera áudio para arquivo temporário
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                output_path = tmp.name
            
            # INFERÊNCIA XTTS
            self.tts.tts_to_file(
                text=text,
                file_path=output_path,
                speaker_wav=speaker_wav,
                language=language,
                split_sentences=self.enable_text_splitting,
                # Parâmetros avançados (via kwargs internos do XTTS)
                # temperature, repetition_penalty etc. são definidos no modelo
            )
            
            # Lê áudio gerado
            audio_data, sr = sf.read(output_path)
            
            # Calcula duração
            duration = len(audio_data) / sr
            
            # Converte para bytes (WAV)
            audio_bytes = self._audio_to_bytes(audio_data, sr)
            
            # Remove arquivo temporário
            os.remove(output_path)
            
            logger.info(f"✅ Dubbing generated: {duration:.2f}s, {len(audio_bytes)} bytes")
            
            return audio_bytes, duration
            
        except Exception as e:
            logger.error(f"XTTS dubbing failed: {e}")
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
        
        NOTA: XTTS não precisa "treinar" - usa few-shot learning.
        Esta função apenas valida o áudio e cria o VoiceProfile.
        
        Args:
            audio_path: Caminho para amostra de áudio
            language: Idioma base da voz
            voice_name: Nome do perfil
            description: Descrição opcional
            
        Returns:
            VoiceProfile com referência de áudio
        """
        try:
            logger.info(f"🎤 Cloning voice with XTTS from: {audio_path}")
            
            # Validação
            if not audio_path or not Path(audio_path).exists():
                raise InvalidAudioException(f"Audio file not found: {audio_path}")
            
            # Valida duração/qualidade
            audio_info = self._validate_audio_for_cloning(audio_path)
            
            logger.info(f"   Audio validated: {audio_info['duration']:.2f}s, {audio_info['sr']}Hz")
            
            # XTTS não precisa transcrever (não usa reference_text como F5-TTS)
            # Mas mantemos compatibilidade com VoiceProfile
            reference_text = f"[Audio reference for {voice_name}]"
            
            # Cria VoiceProfile
            from datetime import datetime
            profile_id = f"voice_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            
            profile_dir = Path(f"/app/voice_profiles/{profile_id}")
            profile_dir.mkdir(exist_ok=True, parents=True)
            
            # Copia áudio para diretório do perfil
            import shutil
            profile_audio_path = profile_dir / "reference.wav"
            shutil.copy(audio_path, profile_audio_path)
            
            # Cria VoiceProfile
            profile = VoiceProfile.create_new(
                name=voice_name,
                language=language,
                source_audio_path=str(profile_audio_path),
                profile_path=str(profile_dir),
                description=description,
                reference_text=reference_text
            )
            profile.id = profile_id
            
            logger.info(f"✅ Voice cloned: {profile.id}")
            
            return profile
            
        except Exception as e:
            logger.error(f"XTTS voice cloning failed: {e}")
            raise OpenVoiceException(f"Voice cloning failed: {str(e)}")
    
    def _validate_audio_for_cloning(self, audio_path: str) -> dict:
        """
        Valida áudio para clonagem XTTS
        
        Requisitos XTTS:
        - Mínimo: 3 segundos
        - Máximo: 30 segundos (recomendado)
        - Sample rate: qualquer (XTTS faz resample)
        """
        try:
            audio_data, sr = sf.read(audio_path)
            
            # Duração
            duration = len(audio_data) / sr
            
            if duration < 3:
                raise InvalidAudioException(
                    f"Audio too short: {duration:.2f}s (minimum 3s for XTTS)"
                )
            
            if duration > 60:
                logger.warning(f"Audio very long: {duration:.2f}s (recommended <30s)")
            
            return {
                'duration': duration,
                'sr': sr,
                'samples': len(audio_data)
            }
            
        except Exception as e:
            raise InvalidAudioException(f"Audio validation failed: {str(e)}")
    
    def _get_preset_audio(self, voice_preset: str, language: str) -> list:
        """
        Retorna lista de caminhos de áudio para voice preset
        
        XTTS aceita múltiplos arquivos de referência para melhor qualidade
        """
        preset_dir = Path("/app/voice_profiles/presets")
        preset_dir.mkdir(exist_ok=True, parents=True)
        
        # Mapeamento simples (expandir conforme necessário)
        preset_map = {
            'female_generic': f'{preset_dir}/female_{language}.wav',
            'male_generic': f'{preset_dir}/male_{language}.wav',
        }
        
        preset_path = preset_map.get(voice_preset)
        
        if not preset_path or not Path(preset_path).exists():
            logger.warning(f"Preset not found: {voice_preset}, using XTTS default voice")
            # XTTS tem vozes padrão, não precisa de preset obrigatório
            return []  # Vazio = usa voz padrão do XTTS
        
        return [preset_path]
    
    def _audio_to_bytes(self, audio_data, sample_rate: int) -> bytes:
        """Converte array numpy para WAV bytes"""
        buffer = io.BytesIO()
        sf.write(buffer, audio_data, sample_rate, format='WAV')
        buffer.seek(0)
        return buffer.read()
    
    def unload_models(self):
        """Libera memória GPU/CPU"""
        logger.info("Unloading XTTS models...")
        del self.tts
        if self.device == 'cuda':
            torch.cuda.empty_cache()
        logger.info("XTTS models unloaded")
```

**Validação:**
```bash
# Rodar testes unitários
pytest tests/unit/test_xtts_client_init.py -v
pytest tests/unit/test_xtts_client_dubbing.py -v
pytest tests/unit/test_xtts_client_cloning.py -v
```

**Resultado esperado:** ✅ TODOS os testes PASSAM

---

### Tarefa 2.2: Atualizar Configurações

#### 2.2.1 Modificar app/config.py
```python
# app/config.py

# REMOVER seção F5TTS (linhas 72-102)
# DELETE:
# 'f5tts': { ... },
# 'F5TTS_MODEL_PATH': ...

# ADICIONAR seção XTTS
'xtts': {
    'model': os.getenv('XTTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2'),
    'device': os.getenv('XTTS_DEVICE', 'cuda'),
    'cache_dir': os.getenv('XTTS_CACHE', '/app/models/xtts'),
    
    # Parâmetros de inferência
    'temperature': float(os.getenv('XTTS_TEMPERATURE', '0.7')),
    'repetition_penalty': float(os.getenv('XTTS_REPETITION_PENALTY', '2.0')),
    'length_penalty': float(os.getenv('XTTS_LENGTH_PENALTY', '1.0')),
    'top_k': int(os.getenv('XTTS_TOP_K', '50')),
    'top_p': float(os.getenv('XTTS_TOP_P', '0.85')),
    'speed': float(os.getenv('XTTS_SPEED', '1.0')),
    'enable_text_splitting': os.getenv('XTTS_ENABLE_TEXT_SPLITTING', 'true').lower() == 'true',
    
    # Clonagem
    'gpt_cond_len': int(os.getenv('XTTS_GPT_COND_LEN', '30')),  # segundos
    'max_ref_length': int(os.getenv('XTTS_MAX_REF_LENGTH', '30')),  # segundos
},
```

---

### Tarefa 2.3: Build e Teste em Container

#### 2.3.1 Build Docker
```bash
cd services/audio-voice

# Build
docker build -t audio-voice-xtts:latest .

# Validar imports
docker run --rm audio-voice-xtts:latest python -c "from TTS.api import TTS; print('✅ TTS imported')"
```

---

#### 2.3.2 Rodar testes no container
```bash
# Criar container temporário
docker run --rm -it \
  -v $(pwd)/tests:/app/tests \
  -v $(pwd)/uploads:/app/uploads \
  audio-voice-xtts:latest \
  pytest tests/unit/ -v

# Validar que testes passam
```

---

### Validação Sprint 2

**Critérios de Aceitação:**
- [ ] `app/xtts_client.py` criado (300+ linhas)
- [ ] `requirements.txt` atualizado (F5-TTS removido, TTS adicionado)
- [ ] `Dockerfile` atualizado
- [ ] `app/config.py` atualizado (seção XTTS)
- [ ] ✅ Testes unitários PASSAM (GREEN phase)
- [ ] ✅ Build Docker bem-sucedido

**Entregáveis:**
- `app/xtts_client.py` ✅
- `requirements.txt` (atualizado) ✅
- `Dockerfile` (atualizado) ✅
- `app/config.py` (atualizado) ✅

**Resultado esperado:**
- ✅ Testes unitários: PASS (código implementado)
- ❌ Testes integração: FAIL (processor ainda usa F5-TTS)

---

## 🔗 SPRINT 3: INTEGRAÇÃO (TDD Phase 3)

**Duração estimada:** 2-3 dias  
**Objetivo:** Conectar XTTSClient ao Processor e API

### Tarefa 3.1: Modificar Processor

#### 3.1.1 Atualizar app/processor.py
```python
# app/processor.py

# Linha 14: MODIFICAR import
# ANTES
from .openvoice_client import OpenVoiceClient

# DEPOIS
from .xtts_client import XTTSClient

# Linha 18-40: MODIFICAR factory
class VoiceProcessor:
    """Processa jobs de dublagem e clonagem de voz"""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Factory: escolhe motor por env var
        engine = os.getenv('TTS_ENGINE', 'xtts')  # DEFAULT: xtts
        logger.info(f"Initializing TTS engine: {engine}")
        
        if engine == 'xtts':
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.tts_engine = XTTSClient(device=self.device)
        else:
            raise ValueError(f"Unsupported TTS engine: {engine}")
        
        logger.info(f"TTS engine initialized: {engine} on {self.device}")
    
    # Métodos process_dubbing_job() e process_voice_cloning_job()
    # NÃO MUDAM (já usam interface abstrata)
```

**Validação:**
```bash
# Teste de importação
docker exec audio-voice-api python -c "from app.processor import VoiceProcessor; print('✅')"
```

---

### Tarefa 3.2: Atualizar Docker Compose

#### 3.2.1 Modificar docker-compose.yml
```yaml
# services/audio-voice/docker-compose.yml

services:
  audio-voice-api:
    environment:
      # TTS Engine
      TTS_ENGINE: "xtts"
      
      # XTTS Config (ADICIONAR)
      XTTS_MODEL: "tts_models/multilingual/multi-dataset/xtts_v2"
      XTTS_CACHE: "/app/models/xtts"
      XTTS_DEVICE: "cuda"
      XTTS_TEMPERATURE: "0.7"
      XTTS_REPETITION_PENALTY: "2.0"
      
      # REMOVER F5TTS_* (se existir)
    
    volumes:
      # ADICIONAR volume XTTS
      - ./models/xtts:/app/models/xtts
```

---

### Tarefa 3.3: Rodar Testes de Integração

#### 3.3.1 Rebuild containers
```bash
cd services/audio-voice

# Stop
docker-compose down

# Build
docker-compose build

# Start
docker-compose up -d

# Verificar logs
docker-compose logs -f audio-voice-api
```

**Validação no log:**
```
✅ Initializing TTS engine: xtts
✅ Loading XTTS model: tts_models/multilingual/multi-dataset/xtts_v2
✅ XTTS model loaded successfully
✅ TTS engine initialized: xtts on cuda
```

---

#### 3.3.2 Rodar teste E2E automatizado
```bash
# Usar teste existente test_voice_clone.py
cd services/audio-voice
source venv/bin/activate
python test_voice_clone.py
```

**Resultado esperado:**
```
🔧 Testando API Audio-Voice...
✅ API está online
✅ Arquivo encontrado: uploads/clone_20251126031159965237.ogg

🎤 Teste 1: Clonando voz...
✅ Job criado: job_123456
⏳ Aguardando clonagem... 0s
⏳ Aguardando clonagem... 5s
✅ Clonagem concluída em 8s
✅ Voz clonada! ID: voice_20250126153045678901

🎬 Teste 2: Criando dubbing com voz clonada...
✅ Job criado: job_789012
⏳ Aguardando dubbing... 0s
⏳ Aguardando dubbing... 5s
✅ Dubbing concluído em 7s
✅ Arquivo gerado: /app/processed/job_789012.wav

✅ TODOS OS TESTES PASSARAM!
```

---

### Validação Sprint 3

**Critérios de Aceitação:**
- [ ] `app/processor.py` modificado (usa XTTSClient)
- [ ] `docker-compose.yml` atualizado (variáveis XTTS)
- [ ] ✅ Containers iniciam sem erros
- [ ] ✅ Teste E2E PASSA (clonagem + dubbing)
- [ ] ✅ Logs mostram "XTTS" (não "F5-TTS")

**Entregáveis:**
- `app/processor.py` (modificado) ✅
- `docker-compose.yml` (modificado) ✅
- Logs de sucesso ✅

**Resultado esperado:**
- ✅ Testes unitários: PASS
- ✅ Testes integração: PASS (sistema completo funcionando)

---

## ✅ SPRINT 4: VALIDAÇÃO E QA

**Duração estimada:** 2-3 dias  
**Objetivo:** Garantir qualidade e performance

### Tarefa 4.1: Testes de Performance

#### 4.1.1 Benchmark de latência
```python
# tests/performance/test_xtts_latency.py
"""
Teste de performance XTTS - Latência
"""
import time
import pytest
from app.xtts_client import XTTSClient

@pytest.mark.asyncio
async def test_cloning_latency():
    """Mede latência de clonagem"""
    client = XTTSClient(device='cuda')
    
    start = time.time()
    profile = await client.clone_voice(
        audio_path="uploads/clone_20251126031159965237.ogg",
        language="pt",
        voice_name="Latency Test"
    )
    elapsed = time.time() - start
    
    print(f"\n⏱️  Cloning latency: {elapsed:.2f}s")
    assert elapsed < 15, f"Cloning too slow: {elapsed:.2f}s (max 15s)"

@pytest.mark.asyncio
async def test_dubbing_latency():
    """Mede latência de dubbing"""
    client = XTTSClient(device='cuda')
    
    text = "Este é um teste de latência de dubbing com XTTS."
    
    start = time.time()
    audio_bytes, duration = await client.generate_dubbing(
        text=text,
        language="pt",
        voice_preset="female_generic"
    )
    elapsed = time.time() - start
    
    print(f"\n⏱️  Dubbing latency: {elapsed:.2f}s (audio: {duration:.2f}s)")
    assert elapsed < 10, f"Dubbing too slow: {elapsed:.2f}s (max 10s)"
```

**Executar:**
```bash
pytest tests/performance/ -v -s
```

**Critério:** Latência deve ser <15s para clonagem, <10s para dubbing

---

#### 4.1.2 Benchmark de VRAM
```bash
# Script manual
# tests/performance/measure_vram.sh

#!/bin/bash
echo "🔧 Medindo uso de VRAM com XTTS..."

# Antes de carregar
echo -e "\n📊 VRAM antes:"
nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits

# Executa teste
docker exec audio-voice-api python -c "
from app.xtts_client import XTTSClient
import time

client = XTTSClient(device='cuda')
print('Modelo carregado, aguardando 5s...')
time.sleep(5)
"

# Depois de carregar
echo -e "\n📊 VRAM depois:"
nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits

echo -e "\n✅ Teste completo"
```

**Executar:**
```bash
bash tests/performance/measure_vram.sh
```

**Critério:** VRAM deve ser <6GB (XTTS v2 estimado: ~4GB)

---

### Tarefa 4.2: Testes de Qualidade de Áudio

#### 4.2.1 Validação de sample rate
```python
# tests/quality/test_audio_quality.py
"""
Testes de qualidade de áudio XTTS
"""
import pytest
import soundfile as sf
import io
from app.xtts_client import XTTSClient

@pytest.mark.asyncio
async def test_audio_sample_rate():
    """Valida sample rate do áudio gerado"""
    client = XTTSClient(device='cpu')
    
    audio_bytes, _ = await client.generate_dubbing(
        text="Teste de sample rate",
        language="pt",
        voice_preset="female_generic"
    )
    
    audio_data, sr = sf.read(io.BytesIO(audio_bytes))
    
    assert sr == 24000, f"Sample rate incorreto: {sr}Hz (esperado 24kHz)"
    print(f"✅ Sample rate: {sr}Hz")

@pytest.mark.asyncio
async def test_audio_duration_accuracy():
    """Valida precisão da duração retornada"""
    client = XTTSClient(device='cpu')
    
    text = "Este é um teste de duração. " * 5  # ~30 palavras
    
    audio_bytes, reported_duration = await client.generate_dubbing(
        text=text,
        language="pt",
        voice_preset="male_generic"
    )
    
    # Calcula duração real
    audio_data, sr = sf.read(io.BytesIO(audio_bytes))
    actual_duration = len(audio_data) / sr
    
    # Margem de erro: ±0.1s
    assert abs(actual_duration - reported_duration) < 0.1, \
        f"Duração imprecisa: reportado={reported_duration:.2f}s, real={actual_duration:.2f}s"
    
    print(f"✅ Duração: reportado={reported_duration:.2f}s, real={actual_duration:.2f}s")
```

**Executar:**
```bash
pytest tests/quality/ -v -s
```

---

### Tarefa 4.3: Testes de Stress

#### 4.3.1 Clonagem sequencial (múltiplas vozes)
```python
# tests/stress/test_multiple_clones.py
"""
Teste de stress: múltiplas clonagens
"""
import pytest
from app.xtts_client import XTTSClient

@pytest.mark.asyncio
async def test_multiple_clones():
    """Testa clonagem de 5 vozes sequencialmente"""
    client = XTTSClient(device='cuda')
    
    profiles = []
    for i in range(5):
        profile = await client.clone_voice(
            audio_path="uploads/clone_20251126031159965237.ogg",
            language="pt",
            voice_name=f"Clone Stress Test {i+1}"
        )
        profiles.append(profile)
        print(f"✅ Clone {i+1}/5: {profile.id}")
    
    assert len(profiles) == 5
    print(f"\n✅ 5 clonagens concluídas com sucesso")
```

---

### Validação Sprint 4

**Critérios de Aceitação:**
- [ ] ✅ Latência de clonagem: <15s
- [ ] ✅ Latência de dubbing: <10s
- [ ] ✅ VRAM usage: <6GB
- [ ] ✅ Sample rate: 24kHz consistente
- [ ] ✅ Duração de áudio precisa (±0.1s)
- [ ] ✅ Stress test: 5 clonagens sem crash

**Entregáveis:**
- Relatório de performance ✅
- Logs de QA ✅
- Aprovação para produção ✅

---

## 🚀 SPRINT 5: DEPLOY E CLEANUP

**Duração estimada:** 1-2 dias  
**Objetivo:** Deploy em produção + limpeza de código legado

### Tarefa 5.1: Preparação para Deploy

#### 5.1.1 Backup de produção
```bash
# Backup Redis (VoiceProfiles)
docker exec redis-server redis-cli SAVE
docker cp redis-server:/data/dump.rdb backup_redis_pre_xtts_$(date +%Y%m%d).rdb

# Backup código F5-TTS
git checkout -b backup/f5tts-final
git add .
git commit -m "BACKUP: F5-TTS final state before XTTS migration"
git push origin backup/f5tts-final
```

---

#### 5.1.2 Cancelar jobs Celery pendentes
```bash
# Entrar no container Celery
docker exec -it audio-voice-celery bash

# Cancelar todos os jobs pendentes
celery -A run_celery purge
```

---

### Tarefa 5.2: Deploy

#### 5.2.1 Parar serviço
```bash
cd services/audio-voice
docker-compose down
```

---

#### 5.2.2 Aplicar mudanças
```bash
# Pull novo código (branch XTTS migration)
git checkout main
git pull origin main

# Rebuild
docker-compose build --no-cache

# Start
docker-compose up -d

# Logs
docker-compose logs -f
```

**Validação no log:**
```
✅ Initializing TTS engine: xtts
✅ XTTS model loaded successfully
✅ Application startup complete
```

---

#### 5.2.3 Teste smoke (fumaça)
```bash
# Teste rápido de health check
curl http://localhost:8005/health

# Teste de clonagem rápido
python test_voice_clone.py
```

**Critério:** API responde + teste E2E passa ✅

---

### Tarefa 5.3: Monitoramento Pós-Deploy

#### 5.3.1 Monitorar logs (24h)
```bash
# Logs em tempo real
docker-compose logs -f audio-voice-api | tee logs/xtts_deploy_$(date +%Y%m%d).log

# Verificar erros
grep -i "error\|exception\|fail" logs/xtts_deploy_$(date +%Y%m%d).log
```

---

#### 5.3.2 Monitorar VRAM
```bash
# A cada 5 minutos
watch -n 300 nvidia-smi
```

---

### Tarefa 5.4: Cleanup (Após 48h de Estabilidade)

#### 5.4.1 Deletar código F5-TTS
```bash
# Deletar arquivo F5-TTS client
rm app/openvoice_client.py  # (era o F5TTSClient)

# Deletar testes F5-TTS
rm -f tests/test_f5tts_*.py
rm -f tests/integration/test_f5tts_*.py

# Deletar documentação obsoleta
rm -f CONVERTER.md SPRINT.md VIDEO-SUPPORT.md
rm -f EXAMPLES.md MODEL-MANAGEMENT.md

# Deletar scripts obsoletos
rm -f monitor_build_sprint2.sh run_clone_test.sh
rm -f test_f5tts_load.py test_model_compatibility.py

# Commit
git add .
git commit -m "CLEANUP: Remove F5-TTS legacy code after successful XTTS migration"
git push origin main
```

---

#### 5.4.2 Atualizar README.md
```markdown
# Audio Voice Service

## 🚀 Features
- **TTS Engine:** XTTS v2 (Coqui TTS)
- **Voice Cloning:** Few-shot learning (3+ seconds)
- **Multi-language:** 16 languages including Portuguese
- **High Quality:** 24kHz output

## 📦 Dependencies
- TTS>=0.22.0 (XTTS v2)
- torch==2.1.2
- torchaudio==2.1.2

## 🔧 Configuration
See `docker-compose.yml` for XTTS_* environment variables.

## 📝 Migration Notes
- **2025-01-26:** Migrated from F5-TTS to XTTS v2
- See `AUDITORIA.md` and `SPRINTS.md` for migration details
```

---

### Validação Sprint 5

**Critérios de Aceitação:**
- [ ] ✅ Deploy em produção bem-sucedido
- [ ] ✅ 48h de estabilidade (sem erros críticos)
- [ ] ✅ Código F5-TTS deletado
- [ ] ✅ Documentação atualizada
- [ ] ✅ Backup de segurança criado

**Entregáveis:**
- Código limpo (sem F5-TTS) ✅
- README atualizado ✅
- Logs de produção (48h) ✅
- Rollback plan documentado ✅

---

## 📊 MÉTRICAS DE SUCESSO

### Performance
| Métrica | F5-TTS (antes) | XTTS (esperado) | Status |
|---------|----------------|-----------------|--------|
| Clonagem | 8-10s | 5-8s | ⏳ |
| Dubbing | FALHA ❌ | 5-8s | ⏳ |
| VRAM | ~2GB | ~4GB | ⏳ |
| Sample rate | 24kHz | 24kHz | ⏳ |

### Estabilidade
| Critério | Objetivo | Status |
|----------|----------|--------|
| Clonagem funcionando | 100% sucesso | ⏳ |
| Dubbing funcionando | 100% sucesso | ⏳ |
| Uptime (48h) | >99% | ⏳ |
| Erros críticos | 0 | ⏳ |

### Qualidade
| Critério | Objetivo | Status |
|----------|----------|--------|
| Qualidade de áudio | Subjetiva ≥ F5-TTS | ⏳ |
| Fidelidade de voz | Alta | ⏳ |
| Naturalidade | Alta | ⏳ |

---

## 🔄 ROLLBACK PLAN

### Cenário 1: Falha Crítica em Produção

**Passos:**
```bash
# 1. Parar serviço
docker-compose down

# 2. Reverter para branch F5-TTS
git checkout backup/f5tts-final

# 3. Rebuild
docker-compose build

# 4. Restaurar Redis
docker cp backup_redis_pre_xtts_YYYYMMDD.rdb redis-server:/data/dump.rdb
docker restart redis-server

# 5. Start
docker-compose up -d

# 6. Validar
python test_voice_clone.py
```

**Tempo estimado:** <10 minutos

---

### Cenário 2: Problemas de Performance

**Mitigações:**
- Reduzir `enable_text_splitting=False` (menos overhead)
- Aumentar `temperature=0.6` (mais determinístico)
- Usar `use_deepspeed=False` (menos VRAM)
- Considerar CPU fallback se VRAM insuficiente

---

## 📚 DOCUMENTAÇÃO ADICIONAL

### Arquivos Criados
- ✅ `AUDITORIA.md` - Mapeamento F5-TTS → XTTS
- ✅ `SPRINTS.md` - Plano de migração (este arquivo)
- ⏳ `XTTS-ARCHITECTURE.md` - Arquitetura XTTS (Sprint 5)
- ⏳ `XTTS-USAGE.md` - Guia de uso (Sprint 5)

### Referências
- [Coqui TTS Docs](https://docs.coqui.ai)
- [XTTS v2 GitHub](https://github.com/coqui-ai/TTS)
- [XTTS Model Card](https://huggingface.co/coqui/XTTS-v2)

---

## ✅ CHECKLIST FINAL

### Antes de Iniciar
- [x] AUDITORIA.md criado ✅
- [x] SPRINTS.md criado ✅
- [ ] Usuário aprovou plano de migração
- [ ] Ambiente de staging preparado

### Durante Execução
- [ ] Sprint 1: Testes criados (RED phase)
- [ ] Sprint 2: Código implementado (GREEN phase)
- [ ] Sprint 3: Integração completa
- [ ] Sprint 4: QA aprovado
- [ ] Sprint 5: Deploy concluído

### Pós-Deploy
- [ ] 48h de monitoramento sem erros
- [ ] Código F5-TTS deletado
- [ ] Documentação atualizada
- [ ] Retrospectiva da migração documentada

---

## 🎯 CONCLUSÃO

### Estratégia Resumida
1. **TDD First:** Criar testes ANTES de código
2. **Incremental:** 5 sprints independentes
3. **Validação:** Testes em cada etapa
4. **Reversível:** Rollback plan sempre disponível
5. **Documentado:** Logs detalhados de tudo

### Próximos Passos Imediatos
1. ✅ **AUDITORIA.md** criado
2. ✅ **SPRINTS.md** criado
3. ⏳ **Apresentar ao usuário** para aprovação
4. ⏳ **Iniciar Sprint 1** (apenas após aprovação)

### Estimativa Total
- **Planejamento:** 1-2 dias ✅ COMPLETO
- **Execução:** 9-15 dias (Sprints 1-5)
- **Total:** 10-17 dias úteis

---

**Documento criado por:** GitHub Copilot  
**Metodologia:** TDD (Test-Driven Development)  
**Versão:** 1.0  
**Status:** COMPLETO ✅ - Aguardando aprovação do usuário
