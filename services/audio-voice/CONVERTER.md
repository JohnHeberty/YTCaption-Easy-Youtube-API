# CONVERTER – OpenVoice → F5-TTS (Motor de Clonagem)

## 1. Estado atual (OpenVoice)

### Descrição do fluxo atual de clonagem

**Arquitetura atual**:
- **Módulo principal**: `app/openvoice_client.py` (867 linhas)
- **Classe central**: `OpenVoiceClient`
- **Mock atual**: `MockOpenVoiceModel` (desenvolvimento/teste)
- **Status**: **MOCK - NÃO PRODUÇÃO REAL**

**Fluxos de processamento**:

1. **Dublagem genérica** (`generate_dubbing`)
   - Entrada: texto, idioma, voice_preset
   - Síntese: `_synthesize_with_preset()`
   - Mock: Síntese aditiva (fundamental + harmonics + formants)
   - Saída: bytes WAV + duração

2. **Dublagem com voz clonada** (`generate_dubbing` + voice_profile)
   - Entrada: texto, idioma, voice_profile (embedding)
   - Síntese: `_synthesize_with_cloned_voice()`
   - Mock: Usa embedding para modular pitch/timbre
   - Saída: bytes WAV + duração

3. **Clonagem de voz** (`clone_voice`)
   - Entrada: audio_path, idioma, voice_name
   - Extração: `_extract_voice_embedding()` → numpy array (256-dim)
   - Mock: Hash MD5 do path + random seed
   - Saída: `VoiceProfile` (embedding salvo em .pkl)

**Dependências e configs**:

```python
# requirements.txt
torch==2.1.2
torchaudio==2.1.2
numpy==1.26.4
soundfile==0.12.1
librosa==0.10.1
pydub==0.25.1

# NOTA: openvoice NÃO instalado (comentado)
# openvoice @ git+https://github.com/myshell-ai/OpenVoice.git
```

**Configuração Docker**:
- Base: `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04`
- Python: 3.11
- PyTorch: cu121
- Diretórios: `/app/voice_profiles`, `/app/models`, `/app/processed`

**Integrações**:
- **FastAPI** (`app/main.py`): Endpoints HTTP
  - `POST /jobs` - criar job de dublagem
  - `POST /voices/clone` - clonar voz
  - `GET /voices` - listar vozes
- **Celery** (`app/celery_tasks.py`): Processing assíncrono
  - `dubbing_task` - processa dublagem
  - `clone_voice_task` - processa clonagem
- **Processor** (`app/processor.py`): Lógica de negócio
  - `process_dubbing_job()` - coordena dublagem
  - `process_clone_job()` - coordena clonagem

**Formato de entrada/saída**:

```python
# Entrada (clonagem)
audio_path: str = "/app/uploads/xxx.mp3"
language: str = "pt"
voice_name: str = "João"

# Saída (clonagem)
VoiceProfile {
  id: str = "voice_abc123"
  embedding: np.ndarray = (256,)
  profile_path: str = "/app/voice_profiles/voice_abc123.pkl"
  language: str = "pt"
  duration: float = 2.44
}

# Entrada (dublagem)
text: str = "Oi, tudo bem?"
language: str = "pt"
voice_profile: VoiceProfile | None

# Saída (dublagem)
audio_bytes: bytes (WAV format, 24kHz)
duration: float = 5.42
```

---

## 2. Estado desejado (F5-TTS)

### Repositório e documentação

**Link**: https://github.com/SWivid/F5-TTS.git

**Características principais**:
- **Flow Matching TTS**: Modelo de difusão para síntese
- **Zero-Shot Voice Cloning**: Clona voz com poucos segundos de áudio
- **Multi-idioma**: Inglês + Chinês (pretrained), extensível
- **API Python**: Classe `F5TTS` com método `infer()`
- **Modelos**: F5TTS_v1_Base (1.25M steps), E2TTS_Base (alternativa)

### Como o F5-TTS será usado no contexto do serviço

**Modo de integração**: **Biblioteca Python** (não servidor separado)

```python
from f5_tts.api import F5TTS

# Inicialização
f5tts = F5TTS(
    model="F5TTS_v1_Base",  # ou E2TTS_Base
    device="cuda",          # ou "cpu"
    hf_cache_dir="/app/models"  # cache de modelos
)

# Inferência (clonagem + síntese)
wav, sr, spec = f5tts.infer(
    ref_file="/app/uploads/voice_sample.wav",     # Áudio de referência
    ref_text="Oi, tudo bem?",                     # Transcrição do ref
    gen_text="Esta é uma frase gerada por IA",   # Texto a sintetizar
    target_rms=0.1,                               # Normalização
    nfe_step=32,                                  # Steps de inferência
    speed=1.0                                     # Velocidade
)

# Salvar
f5tts.export_wav(wav, "/app/processed/output.wav")
```

### Formato esperado

**Entrada**:
- `ref_file` (str): Caminho para áudio de referência (WAV, MP3)
- `ref_text` (str): Transcrição do áudio (opcional, usa Whisper se vazio)
- `gen_text` (str): Texto para sintetizar com voz clonada
- Parâmetros: `speed`, `nfe_step`, `target_rms`, `cross_fade_duration`

**Saída**:
- `wav` (np.ndarray): Áudio gerado (float32, mono)
- `sr` (int): Sample rate (24000 Hz)
- `spec` (np.ndarray): Espectrograma (opcional)

**Diferenças importantes**:
- F5-TTS **NÃO** separa extração de embedding e síntese
- F5-TTS faz **tudo em um método** (`infer`)
- F5-TTS usa **áudio de referência direto** (não embedding pré-extraído)
- F5-TTS tem **transcrição automática** (Whisper) se ref_text vazio

---

## 3. Mapeamento OpenVoice → F5-TTS

### Comparação de funções

| OpenVoice (Mock) | F5-TTS (Real) | Equivalência |
|------------------|---------------|--------------|
| `clone_voice(audio_path, language, voice_name)` | `N/A` | ❌ F5-TTS NÃO armazena embeddings |
| `_extract_voice_embedding(audio_path, language)` | `N/A` | ❌ Embedding implícito no modelo |
| `generate_dubbing(text, language, voice_profile)` | `infer(ref_file, ref_text, gen_text)` | ✅ Direto, com ref_file |
| `_synthesize_with_cloned_voice(text, voice_profile)` | `infer(ref_file, ref_text, gen_text)` | ✅ Mesmo método |
| `_synthesize_with_preset(text, speaker, language)` | `infer(ref_file, ref_text, gen_text)` | ⚠️ Precisa ref_file padrão |

### Parâmetros equivalentes

| OpenVoice | F5-TTS | Conversão |
|-----------|--------|-----------|
| `text: str` | `gen_text: str` | Direto |
| `language: str` | `ref_text: str` (transcrição) | Usa Whisper se vazio |
| `voice_profile.embedding: ndarray` | `ref_file: str` | **MUDA**: arquivo em vez de embedding |
| `speed: float (0.5-2.0)` | `speed: float (0.5-2.0)` | Direto |
| `pitch: float` | ❌ Não suportado | Remover |
| `sample_rate: 24000` | `target_sample_rate: 24000` | Compatível |

### Diferenças importantes

**1. Paradigma de clonagem**:
- **OpenVoice**: Extrai embedding → Armazena .pkl → Usa embedding na síntese
- **F5-TTS**: Usa arquivo de áudio direto a cada inferência

**Impacto**: Precisamos adaptar o conceito de `VoiceProfile`:
- **Antes**: `VoiceProfile.embedding` (numpy array)
- **Depois**: `VoiceProfile.reference_audio_path` (caminho do arquivo)
- **Migração**: Converter .pkl existentes para manter áudio original

**2. Sample rate**:
- **OpenVoice mock**: 24000 Hz ✅
- **F5-TTS**: 24000 Hz ✅
- **Compatível!**

**3. Qualidade de áudio de referência**:
- **F5-TTS recomenda**: <12s, mono, limpo
- **Precisamos**: Validação de duração + pré-processamento

**4. Transcrição automática**:
- **F5-TTS**: Usa Whisper se `ref_text=""` (GPU extra!)
- **Estratégia**: Sempre fornecer `ref_text` para economizar GPU

---

## 4. Impactos no código e no Docker

### Arquivos Python a serem modificados/criados

#### A. Modificar: `app/models.py`

```python
# ANTES
class VoiceProfile(BaseModel):
    id: str
    embedding: Optional[np.ndarray] = None  # ← REMOVER
    profile_path: str  # path para .pkl
    ...

# DEPOIS
class VoiceProfile(BaseModel):
    id: str
    reference_audio_path: str  # ← NOVO: path para .wav/.mp3
    reference_text: str        # ← NOVO: transcrição
    profile_path: str          # mantém para compatibilidade
    ...
```

#### B. Criar: `app/f5tts_client.py` (novo arquivo!)

```python
"""
Cliente F5-TTS - Adapter para clonagem de voz
"""
from f5_tts.api import F5TTS
from .models import VoiceProfile
from .config import get_settings

class F5TTSClient:
    def __init__(self, device='cuda'):
        self.settings = get_settings()
        self.f5tts = F5TTS(
            model="F5TTS_v1_Base",
            device=device,
            hf_cache_dir=str(self.settings['model_path'])
        )
    
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        speed: float = 1.0,
        **kwargs
    ) -> Tuple[bytes, float]:
        # Determina ref_file
        if voice_profile:
            ref_file = voice_profile.reference_audio_path
            ref_text = voice_profile.reference_text
        else:
            # Usa preset (áudio padrão)
            ref_file = self._get_preset_audio(voice_preset, language)
            ref_text = self._get_preset_text(voice_preset, language)
        
        # Inferência
        wav, sr, _ = self.f5tts.infer(
            ref_file=ref_file,
            ref_text=ref_text,
            gen_text=text,
            speed=speed,
            nfe_step=32,
            target_rms=0.1
        )
        
        # Converte para WAV bytes
        audio_bytes = self._wav_to_bytes(wav, sr)
        duration = len(wav) / sr
        
        return audio_bytes, duration
    
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None
    ) -> VoiceProfile:
        # F5-TTS não extrai embedding separadamente
        # Apenas valida e copia áudio
        
        # Valida áudio
        audio_info = self._validate_audio(audio_path)
        
        # Transcreve com Whisper
        ref_text = self.f5tts.transcribe(audio_path, language)
        
        # Copia áudio para voice_profiles
        voice_profiles_dir = Path(self.settings['voice_profiles_dir'])
        temp_profile = VoiceProfile.create_new(...)
        ref_audio_copy = voice_profiles_dir / f"{temp_profile.id}.wav"
        shutil.copy(audio_path, ref_audio_copy)
        
        # Cria profile
        temp_profile.reference_audio_path = str(ref_audio_copy)
        temp_profile.reference_text = ref_text
        
        return temp_profile
```

#### C. Modificar: `app/processor.py`

```python
# ANTES
from .openvoice_client import OpenVoiceClient

class VoiceProcessor:
    def __init__(self):
        self.openvoice_client = OpenVoiceClient()

# DEPOIS
from .f5tts_client import F5TTSClient
from .openvoice_client import OpenVoiceClient  # manter temporariamente

class VoiceProcessor:
    def __init__(self):
        engine = os.getenv('TTS_ENGINE', 'f5tts')  # ← feature flag
        
        if engine == 'f5tts':
            self.tts_client = F5TTSClient()
        else:
            self.tts_client = OpenVoiceClient()
```

#### D. Modificar: `app/config.py`

```python
# Adicionar configuração F5-TTS
'f5tts': {
    'model': os.getenv('F5TTS_MODEL', 'F5TTS_v1_Base'),
    'device': os.getenv('F5TTS_DEVICE', 'cuda'),
    'hf_cache_dir': os.getenv('F5TTS_CACHE', '/app/models/f5tts'),
    'nfe_step': int(os.getenv('F5TTS_NFE_STEP', '32')),
    'target_rms': float(os.getenv('F5TTS_TARGET_RMS', '0.1')),
}
```

### Arquivos Docker a serem atualizados

#### A. `requirements.txt`

```diff
# === AUDIO PROCESSING ===
torch==2.1.2
torchaudio==2.1.2
numpy==1.26.4
soundfile==0.12.1
librosa==0.10.1
pydub==0.25.1

-# === OPENVOICE (placeholder - ajustar conforme instalação real) ===
-# openvoice @ git+https://github.com/myshell-ai/OpenVoice.git

+# === F5-TTS ===
+f5-tts>=0.0.1
+cached-path>=1.5.2
+omegaconf>=2.3.0
+hydra-core>=1.3.2
+vocos>=0.1.0
+transformers>=4.35.0  # para Whisper (transcrição)
```

#### B. `Dockerfile`

```diff
# Dependências de sistema (ffmpeg etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 build-essential pkg-config \
    libavformat-dev libavcodec-dev libavdevice-dev \
    libavutil-dev libavfilter-dev libswscale-dev libswresample-dev \
+   git \  # ← necessário para f5-tts
    curl \
 && rm -rf /var/lib/apt/lists/*
```

#### C. `.env` (novo arquivo ou atualização)

```bash
# TTS Engine
TTS_ENGINE=f5tts  # ou 'openvoice' para fallback

# F5-TTS Settings
F5TTS_MODEL=F5TTS_v1_Base  # ou E2TTS_Base
F5TTS_DEVICE=cuda
F5TTS_CACHE=/app/models/f5tts
F5TTS_NFE_STEP=32
F5TTS_TARGET_RMS=0.1

# GPU
CUDA_VISIBLE_DEVICES=0
```

---

## 5. Estratégia de migração

### Opção escolhida: **Feature Flag** (convivência temporária)

**Razões**:
1. Permite testes A/B (comparar qualidade)
2. Rollback rápido se houver problemas
3. Migração gradual de VoiceProfiles existentes

**Implementação**:

```python
# app/processor.py
engine = os.getenv('TTS_ENGINE', 'f5tts')

if engine == 'f5tts':
    self.tts_client = F5TTSClient()
elif engine == 'openvoice':
    self.tts_client = OpenVoiceClient()
else:
    raise ValueError(f"Unknown TTS_ENGINE: {engine}")
```

**Timeline**:
1. **Sprint 1-3**: Implementar F5TTSClient, rodar em paralelo
2. **Sprint 4**: Migrar profiles, trocar flag para f5tts
3. **Sprint 5**: Remover OpenVoiceClient após validação

### Migração de VoiceProfiles

**Problema**: Profiles existentes têm `.pkl` (embedding), mas F5-TTS precisa de `.wav` (áudio)

**Solução**:

```python
# Script de migração: scripts/migrate_voices_to_f5tts.py
def migrate_voice_profile(old_profile: VoiceProfile) -> VoiceProfile:
    # 1. Carrega .pkl (se existir)
    embedding = load_embedding(old_profile.profile_path)
    
    # 2. Busca áudio original (fonte)
    original_audio = find_original_audio(old_profile.source_audio_path)
    
    # 3. Se não encontrar, gera aviso
    if not original_audio:
        logger.warning(f"Profile {old_profile.id}: áudio original não encontrado!")
        # Pode usar TTS genérico para criar sample
        original_audio = generate_fallback_audio(old_profile)
    
    # 4. Copia áudio para voice_profiles
    new_path = f"/app/voice_profiles/{old_profile.id}.wav"
    shutil.copy(original_audio, new_path)
    
    # 5. Transcreve
    ref_text = f5tts.transcribe(new_path, old_profile.language)
    
    # 6. Atualiza profile
    old_profile.reference_audio_path = new_path
    old_profile.reference_text = ref_text
    
    return old_profile
```

---

## 6. Testes planejados

### Como o áudio `tests/Teste.mp3` será usado

**Áudio de teste**:
- Path: `services/audio-voice/tests/Teste.mp3`
- Conteúdo: "Oi, tudo bem?" (2.44s, português)
- Uso: Referência para clonagem

**Cenários de teste**:

#### A. Teste unitário de clonagem

```python
def test_clone_voice_f5tts():
    client = F5TTSClient(device='cpu')
    
    # Clona voz
    profile = await client.clone_voice(
        audio_path="tests/Teste.mp3",
        language="pt",
        voice_name="Teste Voice"
    )
    
    # Valida
    assert profile.reference_audio_path.exists()
    assert len(profile.reference_text) > 0
    assert "oi" in profile.reference_text.lower()
```

#### B. Teste de síntese com voz clonada

```python
def test_generate_with_cloned_voice():
    client = F5TTSClient(device='cpu')
    
    # Clona
    profile = await client.clone_voice("tests/Teste.mp3", "pt", "Test")
    
    # Sintetiza
    audio_bytes, duration = await client.generate_dubbing(
        text="Esta é uma frase nova gerada por IA",
        language="pt",
        voice_profile=profile
    )
    
    # Valida
    assert len(audio_bytes) > 0
    assert duration > 0
    assert duration < 10  # razoável para essa frase
```

#### C. Comparação OpenVoice vs F5-TTS

```python
def test_compare_engines():
    # OpenVoice
    openvoice = OpenVoiceClient()
    ov_bytes, ov_dur = await openvoice.generate_dubbing(
        text="Oi, tudo bem?",
        language="pt",
        voice_preset="male_deep"
    )
    
    # F5-TTS
    f5tts = F5TTSClient()
    f5_bytes, f5_dur = await f5tts.generate_dubbing(
        text="Oi, tudo bem?",
        language="pt",
        voice_preset="male_deep"  # usa preset padrão
    )
    
    # Compara qualidade (usa suite existente)
    from tests.test_voice_clone_quality import VoiceCloneQualityTest
    
    quality_ov = analyze_audio(ov_bytes)
    quality_f5 = analyze_audio(f5_bytes)
    
    # F5-TTS deve ter MENOS "bibs" (formants não dominantes)
    assert quality_f5['formants_detected'] >= 3
    assert quality_f5['spectral_centroid_error'] < quality_ov['spectral_centroid_error']
```

### Critérios subjetivos/objetivos esperados de qualidade

**Objetivos** (via `test_voice_clone_quality.py`):
- ✅ Spectral Centroid Error < 20% (OpenVoice tinha 112%)
- ✅ Formantes detectados: 3/3 (OpenVoice tinha 0/3)
- ✅ Energy Ratio: 0.8-1.2 (OpenVoice tinha 14.8)
- ✅ Pitch Error < 30 Hz (OpenVoice tinha 114 Hz)

**Subjetivos** (escuta manual):
- ✅ Não soa como beep eletrônico
- ✅ Inteligibilidade alta ("Oi, tudo bem?" reconhecível)
- ✅ Prosódia natural (entonação)
- ✅ Sem artefatos de distorção

**Meta**: F5-TTS deve passar em TODOS os critérios onde OpenVoice falhou.

---

## 7. Riscos e mitigações

### Riscos identificados

1. **GPU Memory**: F5-TTS + Whisper podem consumir muita VRAM
   - **Mitigação**: Opção de rodar Whisper em CPU, ou desabilitar transcrição automática
   
2. **Latência**: Inferência pode ser mais lenta que síntese simples
   - **Mitigação**: Benchmark e otimização (nfe_step reduzido para produção)

3. **Compatibilidade de VoiceProfiles**: Migração pode falhar se áudio original perdido
   - **Mitigação**: Script de backup + validação antes de deletar .pkl

4. **Multi-idioma**: F5-TTS pretrained é EN+ZH, português pode ter qualidade inferior
   - **Mitigação**: Testar extensivamente, considerar fine-tuning futuro

---

## 8. Resumo técnico

| Aspecto | OpenVoice (Mock) | F5-TTS (Produção) |
|---------|------------------|-------------------|
| **Status** | Mock não-funcional | Real, produção |
| **Arquitetura** | Síntese aditiva manual | Flow Matching (ML) |
| **Clonagem** | Embedding separado | Áudio direto |
| **Sample Rate** | 24kHz | 24kHz ✅ |
| **GPU** | CUDA 12.1 | CUDA ✅ compatível |
| **Idiomas** | Mock qualquer | EN+ZH (extensível) |
| **Qualidade** | Bibs eletrônicos ❌ | Fala natural ✅ |
| **Integração** | Classe Python | Classe Python ✅ |

**Conclusão**: Migração viável, com ganhos significativos de qualidade.

---

**Próximo passo**: Criar `SPRINT.md` com tarefas detalhadas.
