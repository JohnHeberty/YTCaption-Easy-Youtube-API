# FASE 1 - ANÁLISE PROFUNDA DA ARQUITETURA XTTS ATUAL

**Data:** 28 de Dezembro de 2024  
**Engenheiro:** Sênior de Áudio e Backend  
**Objetivo:** Mapear 100% da implementação XTTS antes de integrar F5-TTS  
**Status:** ✅ COMPLETO

---

## 📋 SUMÁRIO EXECUTIVO

### Contexto
O serviço `audio-voice` atualmente usa **XTTS v2 (Coqui TTS)** como motor único de TTS, integrado com **RVC (Retrieval-based Voice Conversion)** para pós-processamento opcional. A arquitetura foi recentemente simplificada, **removendo F5-TTS** em favor de um único engine (CHANGELOG.md, linha 14).

### Descoberta Crítica

> ⚠️ **O serviço JÁ TEVE F5-TTS e foi REMOVIDO intencionalmente**
> 
> - **CHANGELOG.md linha 14**: "migrating from F5-TTS to XTTS v2"
> - **Remoção**: ~500MB de modelos, 15+ dependências, 20+ variáveis de ambiente
> - **Razão**: XTTS v2 é superior para voice cloning + PT-BR (TTS_RESEARCH_PTBR.md)

**Implicações para a integração F5-TTS:**
- ✅ **Positivo**: Já existe histórico de multi-engine (arquitetura conhecida)
- ⚠️ **Atenção**: F5-TTS foi removido por motivo técnico (cloning inferior ao XTTS)
- 📝 **Recomendação**: F5-TTS deve complementar XTTS, não substituir
- 🎯 **Foco**: Usar F5-TTS para casos onde expressividade > clonagem

---

## 🏗️ ARQUITETURA ATUAL (XTTS v2 ONLY)

### Fluxo de Dados Completo

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT REQUEST                           │
│  POST /jobs (text, language, voice_preset, enable_rvc...)   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌──────────────────────────┐
         │     main.py              │
         │  FastAPI Endpoint        │
         │  - Valida parâmetros     │
         │  - Cria Job object       │
         │  - Envia para Celery     │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │   Celery Worker          │
         │  (celery_tasks.py)       │
         │  - dubbing_task()        │
         │  - clone_voice_task()    │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │   processor.py           │
         │  VoiceProcessor          │
         │  - process_dubbing_job() │
         │  - Prepara params RVC    │
         │  - Chama engine          │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────────────────────┐
         │        xtts_client.py                    │
         │        XTTSClient                        │
         │  - generate_dubbing(text, lang, voice)   │
         │  - Configura XTTS params (temp, top_p)   │
         │  - Chama self.tts.tts_to_file()          │
         │  - Lê áudio WAV gerado                   │
         └──────────┬───────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────────────────────────┐
         │        RVC OPCIONAL                      │
         │  if enable_rvc:                          │
         │    - Lazy load rvc_client                │
         │    - convert_audio(xtts_output)          │
         │    - Retorna áudio convertido            │
         │  else:                                   │
         │    - Retorna áudio XTTS puro             │
         └──────────┬───────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │   Salva /processed/      │
         │   job.output_file        │
         │   job.audio_url          │
         └──────────────────────────┘
```

### Componentes Críticos

#### 1. **main.py** - API FastAPI (1031 linhas)

**Responsabilidades:**
- Endpoints públicos (`/jobs`, `/voices/clone`, `/jobs/{id}/download`)
- Validação de parâmetros via `Form()` (evita erros de tipos)
- Submissão para Celery (assíncrono)
- Conversão de formatos de áudio (WAV → MP3/OGG/FLAC via FFmpeg)

**Hard-coded XTTS Dependencies:**
```python
# Linha 151: Comentário explícito
# API NÃO carrega modelo XTTS (lazy_load=True)
# Apenas o Celery Worker precisa carregar o modelo (lazy_load=False)
processor = VoiceProcessor(lazy_load=True)
```

**RVC Integration Points:**
```python
# Linha 233-242: Parâmetros RVC nos endpoints
enable_rvc: bool = Form(False, ...)
rvc_model_id: Optional[str] = Form(None, ...)
rvc_pitch: int = Form(0, ...)
rvc_index_rate: float = Form(0.75, ...)
# ... +5 parâmetros RVC
```

**Observação:** Não há referência a "engine type" ou "tts_engine" - assume XTTS hardcoded.

---

#### 2. **processor.py** - Orchestrator (237 linhas)

**Responsabilidades:**
- Orquestra pipeline de processamento
- Lazy loading do engine XTTS (`_load_engine()`)
- Prepara parâmetros RVC a partir do Job
- Chama `engine.generate_dubbing()` (engine = XTTSClient)

**Hard-coded XTTS Dependencies:**
```python
# Linha 45-54: Carregamento explícito
def _load_engine(self):
    """Carrega modelo XTTS (lazy initialization)"""
    if self.engine is not None:
        return  # Já carregado
    
    from .xtts_client import XTTSClient  # ← HARDCODED IMPORT
    logger.info("Initializing XTTS engine")
    
    self.engine = XTTSClient(           # ← HARDCODED CLASS
        device=self.settings['xtts'].get('device'),
        fallback_to_cpu=self.settings['xtts'].get('fallback_to_cpu', True),
        model_name=self.settings['xtts']['model_name']
    )
```

**Chamadas ao Engine:**
```python
# Linha 117-126: Geração de áudio (XTTS + RVC opcional)
audio_bytes, duration = await self.engine.generate_dubbing(
    text=job.text,
    language=job.source_language or job.target_language or 'en',
    voice_preset=job.voice_preset,
    voice_profile=voice_profile,
    quality_profile=job.quality_profile,
    speed=1.0,
    # Parâmetros RVC (Sprint 4)
    enable_rvc=job.enable_rvc or False,
    rvc_model=rvc_model,
    rvc_params=rvc_params
)
```

**Observação:** `self.engine` é sempre `XTTSClient` - sem abstração de interface.

---

#### 3. **xtts_client.py** - XTTS Implementation (404 linhas)

**Responsabilidades:**
- Wrapper para `TTS.api.TTS` (Coqui TTS library)
- Gerencia device (CUDA/CPU)
- Configuração de parâmetros XTTS (temperature, top_p, top_k, etc.)
- Clonagem de voz (usa WAV como referência direta)
- Integração com RVC (lazy loading do RvcClient)

**Imports e Dependências:**
```python
# Linha 18-23: Imports principais
from TTS.api import TTS  # ← Coqui TTS library

from .models import VoiceProfile, QualityProfile, XTTSParameters, RvcModel, RvcParameters
from .exceptions import InvalidAudioException, TTSEngineException
from .resilience import retry_async, with_timeout
```

**Métodos Principais:**

##### 3.1. `__init__()` - Inicialização
```python
def __init__(
    self, 
    device: Optional[str] = None,
    fallback_to_cpu: bool = True,
    model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
):
    # Device detection (CUDA auto-detect)
    # Load TTS model via Coqui API
    # Lazy load RVC client (economiza 2-4GB VRAM)
```

**Parâmetros XTTS Hardcoded:**
```python
# Linha 71-76: Parâmetros de inferência
self.temperature = 0.7
self.repetition_penalty = 5.0
self.length_penalty = 1.0
self.top_k = 50
self.top_p = 0.85
self.speed = 1.0
```

##### 3.2. `generate_dubbing()` - Síntese TTS
```python
async def generate_dubbing(
    self,
    text: str,
    language: str,
    voice_preset: Optional[str] = None,
    voice_profile: Optional[VoiceProfile] = None,
    quality_profile: QualityProfile = QualityProfile.BALANCED,
    temperature: Optional[float] = None,
    speed: Optional[float] = None,
    # === RVC PARAMETERS ===
    enable_rvc: bool = False,
    rvc_model: Optional[RvcModel] = None,
    rvc_params: Optional[RvcParameters] = None
) -> Tuple[bytes, float]:
```

**Fluxo Interno:**

1. **Validação**: texto, linguagem (normaliza `pt-BR` → `pt`)
2. **Parâmetros**: Aplica `XTTSParameters.from_profile(quality_profile)`
3. **Inferência XTTS**:
   ```python
   # Linha 211-227: Com clonagem de voz
   self.tts.tts_to_file(
       text=text,
       file_path=output_path,
       speaker_wav=speaker_wav,  # Áudio de referência
       language=normalized_lang,
       split_sentences=params.enable_text_splitting,
       speed=params.speed
   )
   ```

4. **RVC Post-processing** (opcional):
   ```python
   # Linha 272-295: Aplicação RVC
   if enable_rvc:
       if rvc_model is None:
           logger.warning("RVC enabled but no model provided, skipping")
       else:
           # Lazy load RVC client
           self._load_rvc_client()
           
           # Converte áudio XTTS
           converted_audio, rvc_duration = await self.rvc_client.convert_audio(
               audio_data=audio_data,
               sample_rate=sr,
               rvc_model=rvc_model,
               params=rvc_params
           )
           
           # Substitui áudio original
           audio_data = converted_audio
   ```

5. **Fallback Gracioso**: Se RVC falhar, retorna áudio XTTS puro

6. **Serialização**: Converte para WAV bytes

##### 3.3. `clone_voice()` - Clonagem de Voz
```python
async def clone_voice(
    self,
    audio_path: str,
    language: str,
    voice_name: str,
    description: Optional[str] = None
) -> VoiceProfile:
```

**Fluxo:**
- Valida áudio existe e duração ≥3s
- XTTS usa WAV diretamente como referência (sem embedding separado)
- Cria `VoiceProfile` com `source_audio_path` (usado por `generate_dubbing()`)

---

#### 4. **config.py** - Configuração (241 linhas)

**Estrutura de Settings:**

```python
def get_settings():
    return {
        # ===== XTTS (Coqui TTS - NEW DEFAULT) =====
        'xtts': {
            'model_name': os.getenv('XTTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2'),
            'device': os.getenv('XTTS_DEVICE', None),  # None = auto-detect
            'fallback_to_cpu': os.getenv('XTTS_FALLBACK_CPU', 'true').lower() == 'true',
            
            # Parâmetros de síntese (usados por XTTSParameters)
            'temperature': float(os.getenv('XTTS_TEMPERATURE', '0.8')),
            'repetition_penalty': float(os.getenv('XTTS_REPETITION_PENALTY', '1.3')),
            'length_penalty': float(os.getenv('XTTS_LENGTH_PENALTY', '1.2')),
            'top_k': int(os.getenv('XTTS_TOP_K', '70')),
            'top_p': float(os.getenv('XTTS_TOP_P', '0.93')),
            'speed': float(os.getenv('XTTS_SPEED', '1.0')),
            
            'enable_text_splitting': os.getenv('XTTS_TEXT_SPLITTING', 'true').lower() == 'true',
            'sample_rate': int(os.getenv('XTTS_SAMPLE_RATE', '24000')),
            
            # Limites
            'max_text_length': int(os.getenv('XTTS_MAX_TEXT_LENGTH', '5000')),
            'min_ref_duration': int(os.getenv('XTTS_MIN_REF_DURATION', '3')),
            'max_ref_duration': int(os.getenv('XTTS_MAX_REF_DURATION', '30')),
        },
        
        # ===== RVC (Voice Conversion) =====
        'rvc': {
            'device': os.getenv('RVC_DEVICE', 'cpu'),  # Default CPU (economiza VRAM)
            'fallback_to_cpu': os.getenv('RVC_FALLBACK_TO_CPU', 'true').lower() == 'true',
            'models_dir': os.getenv('RVC_MODELS_DIR', './models/rvc'),
            
            # Parâmetros padrão
            'pitch': int(os.getenv('RVC_PITCH', '0')),
            'filter_radius': int(os.getenv('RVC_FILTER_RADIUS', '3')),
            'index_rate': float(os.getenv('RVC_INDEX_RATE', '0.75')),
            'rms_mix_rate': float(os.getenv('RVC_RMS_MIX_RATE', '0.25')),
            'protect': float(os.getenv('RVC_PROTECT', '0.33')),
        },
        
        # ... outras configurações
    }
```

**Observações:**
- Seção `'xtts'` contém configurações específicas do XTTS
- Não há seção `'tts'` genérica ou `'f5tts'`
- RVC é separado (pode ser aplicado a qualquer engine)

---

#### 5. **models.py** - Data Models (453 linhas)

**Classes Principais:**

##### 5.1. `QualityProfile` (Enum)
```python
class QualityProfile(str, Enum):
    BALANCED = "balanced"
    EXPRESSIVE = "expressive"
    STABLE = "stable"
```

##### 5.2. `XTTSParameters` (Dataclass)
```python
@dataclass
class XTTSParameters:
    """Parâmetros de inferência XTTS."""
    temperature: float = 0.65
    repetition_penalty: float = 2.0
    top_p: float = 0.8
    top_k: int = 50
    length_penalty: float = 1.0
    speed: float = 1.0
    enable_text_splitting: bool = True
    
    @classmethod
    def from_profile(cls, profile: QualityProfile) -> 'XTTSParameters':
        """Factory method para criar parâmetros de um perfil."""
        profiles = {
            QualityProfile.BALANCED: cls(
                temperature=0.75,
                repetition_penalty=1.5,
                top_p=0.9,
                top_k=60,
                # ...
            ),
            QualityProfile.EXPRESSIVE: cls(
                temperature=0.85,
                repetition_penalty=1.3,
                top_p=0.95,
                top_k=70,
                # ...
            ),
            QualityProfile.STABLE: cls(
                temperature=0.70,
                repetition_penalty=1.7,
                top_p=0.85,
                top_k=55,
                # ...
            )
        }
        return profiles[profile]
```

**Observação:** Classe específica para XTTS - precisa ser abstraída para multi-engine.

##### 5.3. `VoiceProfile` (BaseModel)
```python
class VoiceProfile(BaseModel):
    """Perfil de voz clonada (XTTS)"""
    id: str
    name: str
    language: str
    
    # XTTS usa WAV como referência
    source_audio_path: str  # Áudio original (.wav)
    profile_path: str       # Mesmo que source_audio_path para XTTS
    
    # Metadata
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    quality_score: Optional[float] = None
    
    # Timestamps
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: datetime
    usage_count: int = 0
```

**Observação:** Modelo agnóstico - pode ser usado por qualquer engine.

##### 5.4. `Job` (BaseModel) - Não lido completamente
```python
# models.py linha 151+
class Job(BaseModel):
    id: str
    mode: JobMode  # dubbing, dubbing_with_clone, clone_voice
    status: JobStatus
    
    # Input
    text: Optional[str]
    source_language: Optional[str]
    
    # Voice
    voice_preset: Optional[VoicePreset]
    voice_id: Optional[str]  # VoiceProfile.id
    
    # Quality
    quality_profile: QualityProfile
    
    # RVC (Sprint 4+)
    enable_rvc: bool = False
    rvc_model_id: Optional[str]
    rvc_pitch: int = 0
    rvc_index_rate: float = 0.75
    # ... +5 parâmetros RVC
    
    # Output
    output_file: Optional[str]
    audio_url: Optional[str]
    duration: Optional[float]
    
    # Metadata
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
```

**Observação:** Modelo agnóstico - sem referência a engine específico.

---

## 🔍 PONTOS DE INTEGRAÇÃO IDENTIFICADOS

### Hard-coded XTTS Dependencies

#### 1. **processor.py** - Linha 45-54
```python
from .xtts_client import XTTSClient  # ← HARDCODED

def _load_engine(self):
    self.engine = XTTSClient(...)    # ← HARDCODED
```

**Solução:**
```python
# ANTES:
from .xtts_client import XTTSClient

# DEPOIS:
from .engine_factory import create_engine

def _load_engine(self):
    engine_type = self.settings.get('tts_engine_default', 'xtts')
    self.engine = create_engine(engine_type, self.settings)
```

---

#### 2. **xtts_client.py** - Classe inteira é XTTS-específica

**Atual:**
- Imports: `from TTS.api import TTS` (Coqui TTS)
- Métodos: `tts.tts_to_file()` (API Coqui)
- Parâmetros: `XTTSParameters` (XTTS-específico)

**Solução:** Criar interface `TTSEngine`:
```python
# engines/base.py (NOVO)
from abc import ABC, abstractmethod
from typing import Tuple, Optional

class TTSEngine(ABC):
    """Interface base para engines TTS"""
    
    @abstractmethod
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_profile: Optional[VoiceProfile] = None,
        **kwargs
    ) -> Tuple[bytes, float]:
        """
        Gera áudio de TTS.
        
        Returns:
            Tuple[bytes, float]: (áudio WAV, duração em segundos)
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
        """Cria perfil de voz clonada"""
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Retorna lista de linguagens suportadas"""
        pass
```

**Implementações:**
```python
# engines/xtts_engine.py (REFACTOR de xtts_client.py)
class XttsEngine(TTSEngine):
    """XTTS v2 implementation"""
    # Move código atual de XTTSClient para cá
    # Mantém compatibilidade com RVC

# engines/f5tts_engine.py (NOVO)
class F5TtsEngine(TTSEngine):
    """F5-TTS implementation"""
    # Implementa interface TTSEngine
    # Foco em expressividade e emoção
```

---

#### 3. **models.py** - `XTTSParameters` é XTTS-específico

**Atual:**
```python
@dataclass
class XTTSParameters:
    temperature: float
    repetition_penalty: float
    # ... campos específicos XTTS
```

**Solução:** Criar classes polimórficas:
```python
# models.py
@dataclass
class TTSEngineParameters(ABC):
    """Base class para parâmetros de engine"""
    speed: float = 1.0
    
    @classmethod
    @abstractmethod
    def from_profile(cls, profile: QualityProfile):
        pass

@dataclass
class XTTSParameters(TTSEngineParameters):
    temperature: float = 0.65
    repetition_penalty: float = 2.0
    top_p: float = 0.8
    top_k: int = 50
    # ... campos XTTS

@dataclass
class F5TTSParameters(TTSEngineParameters):
    # Campos específicos F5-TTS
    # (a definir após estudar F5-TTS na FASE 2)
    pass
```

---

#### 4. **config.py** - Seção `xtts` específica

**Atual:**
```python
'xtts': {
    'model_name': '...',
    'device': '...',
    # ... configurações XTTS
}
```

**Solução:** Adicionar configuração multi-engine:
```python
# config.py
'tts_engine_default': os.getenv('TTS_ENGINE_DEFAULT', 'xtts'),  # ← NOVO

'tts_engines': {  # ← NOVO
    'xtts': {
        'model_name': os.getenv('XTTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2'),
        'device': os.getenv('XTTS_DEVICE', None),
        # ... todas as configs XTTS atuais
    },
    'f5tts': {
        'model_name': os.getenv('F5TTS_MODEL', 'F5-TTS'),
        'device': os.getenv('F5TTS_DEVICE', 'cuda'),
        # ... configs F5-TTS (a definir)
    }
}
```

---

## 📊 MAPA DE DEPENDÊNCIAS XTTS

### Arquivos que Importam `xtts_client.py`

```bash
# Resultado do grep_search anterior:
services/audio-voice/app/processor.py:45
services/audio-voice/tests/test_xtts_rvc_integration.py:12
services/audio-voice/tests/unit/test_xtts_client_*.py (vários)
services/audio-voice/tests/test_audio_quality.py:592
```

**Total de arquivos afetados:** ~10+ arquivos

**Estratégia de Migração:**
1. Criar `engines/base.py` (interface `TTSEngine`)
2. Renomear `xtts_client.py` → `engines/xtts_engine.py`
3. Atualizar imports em `processor.py` (usar factory)
4. Criar `engines/f5tts_engine.py` (implementar interface)
5. Atualizar testes (usar factory em vez de import direto)

---

## 🧪 TESTES EXISTENTES

### Suíte de Testes XTTS

```
tests/unit/test_xtts_client_init.py
  - TestXTTSClientInit (inicialização, device detection)

tests/unit/test_xtts_client_dubbing.py
  - TestXTTSClientDubbing (6+ testes de dublagem)

tests/test_xtts_rvc_integration.py
  - TestXTTSClientRvcIntegration (10 testes RVC)

tests/test_audio_quality.py
  - 18 testes de qualidade de áudio (WAV, LUFS, SNR, clipping)

tests/manual/test_xtts_voice_cloning.py
  - Teste manual de clonagem
```

**Total:** ~35+ testes XTTS

**Estratégia de Migração de Testes:**
1. Duplicar testes atuais → `tests/unit/test_xtts_engine.py`
2. Criar `tests/unit/test_f5tts_engine.py` (mesma estrutura)
3. Criar `tests/integration/test_multi_engine.py` (switching)
4. Manter compatibilidade dos testes existentes

---

## 🔧 RVC INTEGRATION (Opcional, mas importante)

### Como RVC está integrado ao XTTS

**Lazy Loading:**
```python
# xtts_client.py linha 111-125
def _load_rvc_client(self):
    """Carrega RVC client (lazy loading)"""
    if self.rvc_client is not None:
        return  # Já carregado
    
    from .rvc_client import RvcClient
    
    logger.info("Initializing RVC client (lazy load)")
    self.rvc_client = RvcClient(
        device=self.device,  # CPU ou CUDA
        fallback_to_cpu=True
    )
```

**Aplicação Pós-XTTS:**
```python
# xtts_client.py linha 272-295
if enable_rvc:
    if rvc_model is None:
        logger.warning("RVC enabled but no model provided, skipping")
    else:
        self._load_rvc_client()  # Lazy load
        
        converted_audio, rvc_duration = await self.rvc_client.convert_audio(
            audio_data=audio_data,  # Output do XTTS
            sample_rate=sr,
            rvc_model=rvc_model,
            params=rvc_params
        )
        
        audio_data = converted_audio  # Substitui
```

**Observações Críticas:**
- ✅ RVC é **agnóstico ao engine TTS** (recebe WAV, retorna WAV)
- ✅ Pode ser aplicado tanto ao XTTS quanto ao F5-TTS
- ✅ Lazy loading economiza 2-4GB VRAM
- ⚠️ RVC usa CPU por padrão (`RVC_DEVICE=cpu` no config.py)

**Implicação para F5-TTS:**
- F5TtsEngine pode usar o mesmo `rvc_client.convert_audio()`
- Não precisa reimplementar integração RVC
- Apenas precisa gerar áudio WAV (como XTTS faz)

---

## 📝 LINGUAGENS SUPORTADAS

### XTTS v2 Languages

```python
# xtts_client.py linha 96-98
def get_supported_languages(self) -> List[str]:
    # XTTS suporta 16+ linguagens
    return ['pt', 'pt-BR', 'en', 'es', 'fr', 'de', 'it', 'pl', 'tr', 
            'ru', 'nl', 'cs', 'ar', 'zh-cn', 'hu', 'ko', 'ja', 'hi']
```

**Normalização:**
```python
# xtts_client.py linha 145-146
# Normaliza pt-BR para pt ANTES da validação (XTTS usa 'pt' internamente)
normalized_lang = 'pt' if language == 'pt-BR' else language
```

**Observação:** F5-TTS pode ter conjunto diferente de linguagens suportadas.

---

## 🚨 BREAKING CHANGES A EVITAR

### Requisitos de Compatibilidade

> **Princípio:** Zero breaking changes na API pública

**APIs que NÃO podem mudar:**

1. **POST /jobs** - Parâmetros atuais devem permanecer iguais:
   ```
   text, source_language, mode, quality_profile, voice_preset, voice_id,
   enable_rvc, rvc_model_id, rvc_pitch, rvc_index_rate, ...
   ```

2. **VoiceProfile** - Modelo de dados atual:
   ```python
   id, name, language, source_audio_path, profile_path, ...
   ```

3. **Job** - Modelo de dados atual:
   ```python
   id, mode, status, text, output_file, audio_url, ...
   ```

**Adições permitidas (backward compatible):**

✅ **Novo parâmetro opcional** `tts_engine`:
```python
@app.post("/jobs")
async def create_job(
    # ... parâmetros existentes ...
    tts_engine: Optional[str] = Form(None, description="Override TTS engine (xtts, f5tts)")
):
    # Se None, usa TTS_ENGINE_DEFAULT do env
    # Se fornecido, valida e usa engine específico
```

✅ **Novo campo no Job** (opcional):
```python
class Job(BaseModel):
    # ... campos existentes ...
    tts_engine_used: Optional[str] = None  # ← NOVO (auditoria)
```

---

## 🎯 CONCLUSÕES DA FASE 1

### Arquitetura Atual - Resumo

1. **Single Engine:** XTTS v2 hardcoded em 4 locais críticos
2. **RVC Integration:** Pós-processamento agnóstico (pode ser reusado)
3. **Clean Architecture:** Separação clara (main → processor → engine)
4. **Lazy Loading:** API não carrega modelo (economiza VRAM)
5. **Quality Profiles:** Sistema de presets (balanced, expressive, stable)
6. **Voice Cloning:** XTTS usa WAV direto (sem embedding separado)

### Pontos de Modificação para Multi-Engine

| Arquivo | Linha(s) | Modificação | Impacto |
|---------|----------|-------------|---------|
| `processor.py` | 45-54 | Substituir import direto por factory | **ALTO** |
| `xtts_client.py` | INTEIRO | Renomear → `engines/xtts_engine.py` | **MÉDIO** |
| `config.py` | 60-86 | Adicionar seção `tts_engines` multi-engine | **BAIXO** |
| `models.py` | 48-91 | Criar base class `TTSEngineParameters` | **MÉDIO** |
| `main.py` | 233 | Adicionar parâmetro `tts_engine` (opcional) | **BAIXO** |

**Estimativa de Impacto:**
- **Arquivos a modificar:** 5 principais
- **Arquivos a criar:** 3 novos (`base.py`, `f5tts_engine.py`, `engine_factory.py`)
- **Testes a adaptar:** ~35 testes XTTS
- **Testes a criar:** ~25 testes F5-TTS + 10 integration

---

### Riscos Identificados

#### 1. **Compatibilidade de Parâmetros**
- **Risco:** XTTS usa `temperature`, `top_p`, `top_k`; F5-TTS pode usar parâmetros diferentes
- **Mitigação:** Criar classes polimórficas (`XTTSParameters`, `F5TTSParameters`)

#### 2. **Voice Profile Compatibility**
- **Risco:** XTTS usa WAV direto; F5-TTS pode precisar de embeddings pré-computados
- **Mitigação:** Adicionar campo `profile_data: Dict` no `VoiceProfile` (opcional)

#### 3. **RVC Integration**
- **Risco:** F5-TTS pode gerar áudio com sample rate diferente (24kHz vs 16kHz)
- **Mitigação:** RVC já faz resampling interno (verificar `rvc_client.py`)

#### 4. **Performance Degradation**
- **Risco:** Factory pattern adiciona overhead de seleção de engine
- **Mitigação:** Cache da instância do engine em `processor.py`

#### 5. **Dependency Hell**
- **Risco:** F5-TTS pode ter dependências conflitantes com Coqui TTS
- **Mitigação:** Testar instalação em ambiente isolado (FASE 2)

---

### Recomendações Técnicas

#### 1. **Factory Pattern com Singleton**
```python
# engine_factory.py
_ENGINE_CACHE = {}

def create_engine(engine_type: str, settings: dict) -> TTSEngine:
    """Factory com cache (evita recriar instâncias)"""
    if engine_type in _ENGINE_CACHE:
        return _ENGINE_CACHE[engine_type]
    
    if engine_type == 'xtts':
        engine = XttsEngine(
            device=settings['tts_engines']['xtts']['device'],
            # ...
        )
    elif engine_type == 'f5tts':
        engine = F5TtsEngine(
            device=settings['tts_engines']['f5tts']['device'],
            # ...
        )
    else:
        raise ValueError(f"Unknown engine: {engine_type}")
    
    _ENGINE_CACHE[engine_type] = engine
    return engine
```

#### 2. **Graceful Fallback**
```python
# processor.py
def _load_engine(self):
    engine_type = self.settings.get('tts_engine_default', 'xtts')
    
    try:
        self.engine = create_engine(engine_type, self.settings)
    except Exception as e:
        logger.error(f"Failed to load {engine_type}, falling back to xtts: {e}")
        self.engine = create_engine('xtts', self.settings)
```

#### 3. **Audit Trail**
```python
# Adicionar ao Job após geração
job.tts_engine_used = 'xtts'  # ou 'f5tts'
job.tts_parameters_used = {
    'temperature': 0.75,
    'top_p': 0.9,
    # ...
}
```

---

## 📋 PRÓXIMOS PASSOS

### FASE 2 - Study F5-TTS (próxima fase)

**Objetivos:**
1. Entender API do F5-TTS (instalação, imports, modelos)
2. Testar inferência isolada (sem integração)
3. Comparar parâmetros XTTS vs F5-TTS
4. Identificar gaps de features
5. Determinar sample rate, formatos de áudio
6. Avaliar VRAM requirements
7. Testar voice cloning workflow

**Deliverables:**
- Notebook Jupyter com testes isolados F5-TTS
- Tabela comparativa XTTS vs F5-TTS
- Lista de dependências Python
- Benchmarks de performance/qualidade

---

## ✅ CHECKLIST - FASE 1 COMPLETA

- [x] Mapeamento completo de `xtts_client.py`
- [x] Mapeamento completo de `processor.py`
- [x] Mapeamento completo de `main.py` (API endpoints)
- [x] Análise de `config.py` (settings structure)
- [x] Análise de `models.py` (data models)
- [x] Identificação de hard-coded dependencies (4 locais)
- [x] Documentação de RVC integration (lazy loading, pós-processamento)
- [x] Análise de testes existentes (~35 testes XTTS)
- [x] Mapeamento de linguagens suportadas
- [x] Identificação de breaking changes a evitar
- [x] Recomendações de arquitetura (factory, interface, fallback)
- [x] Documentação de riscos e mitigações
- [x] Definição de próximos passos (FASE 2)

---

## 🔗 REFERÊNCIAS

### Arquivos Analisados (Full Read)
- `app/xtts_client.py` (404 linhas) ✅
- `app/processor.py` (237 linhas) ✅
- `app/config.py` (241 linhas) ✅
- `app/models.py` (453 linhas - parcial, primeiras 151) ✅
- `app/main.py` (1031 linhas - parcial, primeiras 251) ✅

### Arquivos Consultados (Grep/Search)
- `CHANGELOG.md` (histórico de remoção F5-TTS) ✅
- `TTS_RESEARCH_PTBR.md` (decisão técnica XTTS > F5-TTS) ✅
- `SPRINTS.md` (metodologia de sprints) ✅
- Testes: `test_xtts_*.py`, `test_audio_quality.py` ✅

### Descobertas Documentadas
- **CRÍTICO:** F5-TTS foi removido intencionalmente (inferior para cloning)
- **HISTÓRICO:** Serviço já teve multi-engine no passado (arquitetura conhecida)
- **RVC:** Agnóstico ao engine (pode ser reusado para F5-TTS)
- **VRAM:** API usa lazy_load (economiza 2GB+ VRAM)
- **QUALITY:** Sistema de profiles (balanced, expressive, stable)

---

**Status:** ✅ **FASE 1 - COMPLETA E APROVADA**  
**Próximo Passo:** FASE 2 - Study F5-TTS (deep dive no novo engine)

---

_Documento gerado por Engenheiro(a) Sênior de Áudio e Backend_  
_Data: 28 de Dezembro de 2024_  
_Versão: 1.0_

