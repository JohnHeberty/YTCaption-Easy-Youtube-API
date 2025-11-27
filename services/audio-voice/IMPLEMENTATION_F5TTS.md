# IMPLEMENTATION F5-TTS - Relatório Técnico de Implementação

**Data:** 27 de Novembro de 2025  
**Engenheiro:** Sênior de Áudio e Backend  
**Versão:** 1.0  
**Status:** PLANEJAMENTO APROVADO

---

## 📋 SUMÁRIO EXECUTIVO

### Objetivo
Integrar **F5-TTS** como segundo motor TTS no serviço `audio-voice`, mantendo **XTTS v2** como engine primário, com seleção via variável de ambiente `TTS_ENGINE_DEFAULT`.

### Motivação
- **Expressividade Máxima:** F5-TTS oferece emoção e entonação superiores
- **Naturalidade:** Flow Matching Diffusion produz áudio mais natural
- **Casos Premium:** Audiobooks, narrações profissionais, marketing
- **Complementaridade:** XTTS (performance + cloning) + F5-TTS (expressividade)

### Escopo
**IN-SCOPE:**
- ✅ Arquitetura multi-engine com interface `TTSEngine`
- ✅ Implementação `F5TtsEngine` (novo)
- ✅ Refatoração `XttsEngine` (de `xtts_client.py`)
- ✅ Factory pattern com singleton cache
- ✅ Seleção via `TTS_ENGINE_DEFAULT` env var
- ✅ Override per-request (opcional)
- ✅ Graceful fallback (F5-TTS → XTTS)
- ✅ RVC compatível com ambos engines
- ✅ Testes TDD para F5-TTS
- ✅ Quality profiles mapeados

**OUT-OF-SCOPE:**
- ❌ Remoção do XTTS (mantém como default)
- ❌ Substituição de bibliotecas existentes
- ❌ Breaking changes na API pública
- ❌ Fine-tuning de modelos

---

## 📊 PARTE 1: ANÁLISE COMPARATIVA

### 1.1. Arquiteturas TTS

#### XTTS v2 (Atual)
```
Architecture: GPT Autoregressive
├── Input: Text + Reference Audio (WAV)
├── Encoder: GPT-based text encoder
├── Decoder: Autoregressive audio decoder
├── Vocoder: HiFi-GAN (built-in)
└── Output: 24kHz WAV

Parameters: ~500M
Training: Tortoise-based, multi-dataset
Strength: Voice cloning, multilingual
```

#### F5-TTS (Novo)
```
Architecture: Flow Matching Diffusion
├── Input: Text + Reference Audio (WAV) + Reference Text (transcription)
├── Encoder: ConvNeXt V2 blocks
├── Flow: Conditional Flow Matching (ODE solver)
├── Vocoder: Vocos (24kHz) or BigVGAN
└── Output: 24kHz WAV

Parameters: 450M (base) / 1.2B (large)
Training: Emilia dataset (EN/ZH), flow-based
Strength: Expressiveness, emotion, naturalness
```

### 1.2. Comparação Técnica Completa

| Aspecto | XTTS v2 | F5-TTS | Impacto |
|---------|---------|--------|---------|
| **Arquitetura** | GPT Autoregressive | Flow Matching Diffusion | F5-TTS: mais natural, mais lento |
| **Parâmetros** | ~500M | 450M-1.2B | F5-TTS: base similar, large maior |
| **VRAM (FP16)** | 2-4GB | 3-8GB | F5-TTS: +50-100% uso VRAM |
| **Velocidade (RTF)** | 0.3-0.5 | 0.5-2.0 | F5-TTS: 2-4x mais lento |
| **Linguagens** | 16 otimizadas | 100+ zero-shot | XTTS: PT-BR otimizado |
| **PT-BR Qualidade** | ⭐⭐⭐⭐⭐ Excelente | ⭐⭐⭐ A testar | XTTS superior (confirmado) |
| **Voice Cloning** | ✅ Alta qualidade | ✅ Expressivo | Ambos suportam |
| **Ref Audio Needed** | ✅ Sim (WAV) | ✅ Sim (WAV) | Ambos precisam |
| **Ref Text Needed** | ❌ Não | ⚠️ Sim (melhora qualidade) | **GAP CRÍTICO** |
| **Expressividade** | ⭐⭐⭐ Boa | ⭐⭐⭐⭐⭐ Excelente | F5-TTS superior |
| **Emoção** | ⭐⭐⭐ Boa | ⭐⭐⭐⭐⭐ Excelente | F5-TTS superior |
| **Naturalidade** | ⭐⭐⭐⭐ Muito boa | ⭐⭐⭐⭐⭐ Excelente | F5-TTS superior |
| **Estabilidade** | ⭐⭐⭐⭐⭐ Excelente | ⭐⭐⭐ Boa | XTTS superior |
| **Library** | Coqui TTS | Standalone (pip) | F5-TTS: instalação simples |
| **Maturidade** | Alta (2+ anos) | Média (2024) | XTTS mais maduro |
| **Comunidade** | Grande (ativa) | Crescente | XTTS mais suporte |
| **Licença** | Apache 2.0 | CC-BY-NC-4.0 | F5-TTS: não comercial* |

\* Modelos pré-treinados são CC-BY-NC devido ao dataset Emilia. Código é MIT.

### 1.3. Casos de Uso Recomendados

#### XTTS v2 (Default - 90% dos casos)
```
✅ USE PARA:
- Voice cloning de alta qualidade
- Dublagem genérica rápida
- PT-BR otimizado
- Casos que exigem performance (RTF <0.5)
- Produção estável e confiável
- Workflow simples (só áudio ref)

📊 MÉTRICAS:
- RTF: 0.3-0.5 (RÁPIDO)
- VRAM: 2-4GB (ECONÔMICO)
- Latência: 2-3s para 6-8s de áudio
- PT-BR: Qualidade excelente (⭐⭐⭐⭐⭐)
```

#### F5-TTS (Premium - 10% dos casos)
```
✅ USE PARA:
- Narrações profissionais com emoção
- Audiobooks expressivos
- Conteúdo de marketing (anúncios, trailers)
- Casos onde expressividade > performance
- Máxima naturalidade e entonação
- Linguagens EN/ZH (treinadas)

⚠️ EVITE PARA:
- PT-BR crítico (qualidade não validada)
- Baixa latência requerida (RTF >1.0)
- VRAM limitada (<6GB)
- Produção em massa (lento)

📊 MÉTRICAS:
- RTF: 0.5-2.0 (LENTO)
- VRAM: 3-8GB (ALTO)
- Latência: 4-12s para 6-8s de áudio
- PT-BR: Qualidade desconhecida (⭐⭐⭐?)
```

### 1.4. Gap Crítico: Reference Text

#### Problema
- **XTTS:** `clone_voice(audio_path)` → VoiceProfile
- **F5-TTS:** `infer(text, ref_audio, ref_text)` → Audio

F5-TTS **requer transcrição do áudio de referência** para melhor qualidade.

#### Soluções

**Opção A: Campo opcional em VoiceProfile** (RECOMENDADO)
```python
class VoiceProfile(BaseModel):
    # ... campos existentes ...
    ref_text: Optional[str] = None  # ← NOVO
    
    # XTTS: ref_text = None (não usa)
    # F5-TTS: ref_text = "transcrição do áudio" (usa)
```

**Opção B: Auto-transcrição com Whisper**
```python
async def clone_voice(...):
    if engine == 'f5tts' and ref_text is None:
        # Auto-transcrever com Whisper
        ref_text = await whisper_client.transcribe(audio_path)
    # Continua com clonagem
```

**Opção C: Exigir ref_text do usuário**
```python
# API endpoint
@app.post("/voices/clone")
async def clone_voice(
    ref_text: Optional[str] = Form(None, description="Transcrição do áudio (recomendado para F5-TTS)")
):
    # Valida: se F5-TTS, avisa se ref_text=None
```

**Decisão:** Implementar **Opção A + B** (campo opcional + fallback Whisper).

---

## 🏗️ PARTE 2: ARQUITETURA MULTI-ENGINE

### 2.1. Visão Geral

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT REQUEST                           │
│  POST /jobs (text, tts_engine=None, enable_rvc=False, ...)  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌──────────────────────────────────────────┐
         │         main.py (FastAPI)                │
         │  - Valida parâmetros                     │
         │  - tts_engine = request or ENV default   │
         │  - Cria Job object                       │
         │  - Envia para Celery                     │
         └──────────┬───────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────────────────────────┐
         │      Celery Worker (celery_tasks.py)     │
         │  - Deserializa Job                       │
         │  - Chama processor.process_dubbing_job() │
         └──────────┬───────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────────────────────────┐
         │         processor.py (VoiceProcessor)    │
         │  ┌────────────────────────────────────┐  │
         │  │ _load_engine()                     │  │
         │  │   engine_type = job.tts_engine     │  │
         │  │   self.engine = create_engine(     │  │
         │  │       engine_type, settings        │  │
         │  │   )                                │  │
         │  └────────────────────────────────────┘  │
         │  - Prepara parâmetros RVC (se enable)    │
         │  - Chama engine.generate_dubbing(...)    │
         └──────────┬───────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────────────────────────┐
         │    engine_factory.py (Factory Pattern)   │
         │  ┌────────────────────────────────────┐  │
         │  │ create_engine(type, settings):     │  │
         │  │   if type == 'xtts':               │  │
         │  │     return XttsEngine(...)         │  │
         │  │   elif type == 'f5tts':            │  │
         │  │     return F5TtsEngine(...)        │  │
         │  │   else:                            │  │
         │  │     raise ValueError()             │  │
         │  └────────────────────────────────────┘  │
         │  - Singleton cache (evita recriar)       │
         │  - Graceful fallback (f5tts → xtts)      │
         └──────────┬───────────────────────────────┘
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│  XttsEngine     │  │  F5TtsEngine    │
│  (xtts_engine)  │  │  (f5tts_engine) │
├─────────────────┤  ├─────────────────┤
│ + generate_     │  │ + generate_     │
│   dubbing()     │  │   dubbing()     │
│ + clone_voice() │  │ + clone_voice() │
│ + get_supported │  │ + get_supported │
│   _languages()  │  │   _languages()  │
└────────┬────────┘  └────────┬────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│  Coqui TTS API  │  │  F5-TTS API     │
│  self.tts.      │  │  infer_batch()  │
│  tts_to_file()  │  │  infer()        │
└────────┬────────┘  └────────┬────────┘
         │                    │
         │  Áudio WAV         │  Áudio WAV
         │  (24kHz)           │  (24kHz)
         │                    │
         └─────────┬──────────┘
                   ▼
         ┌──────────────────────┐
         │  RVC (Opcional)      │
         │  if enable_rvc:      │
         │    convert_audio()   │
         │  else:               │
         │    return audio      │
         └─────────┬────────────┘
                   │
                   ▼
         ┌──────────────────────┐
         │  Salva /processed/   │
         │  job.output_file     │
         │  job.audio_url       │
         └──────────────────────┘
```

### 2.2. Componentes Novos

#### 2.2.1. Interface Base: `engines/base.py` (NOVO)

```python
"""
Base interface for TTS engines
All engines must implement this interface for compatibility
"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional, List
from ..models import VoiceProfile, QualityProfile


class TTSEngine(ABC):
    """Abstract base class for TTS engines"""
    
    @abstractmethod
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_profile: Optional[VoiceProfile] = None,
        quality_profile: QualityProfile = QualityProfile.BALANCED,
        speed: float = 1.0,
        **kwargs
    ) -> Tuple[bytes, float]:
        """
        Generate dubbed audio from text.
        
        Args:
            text: Text to synthesize
            language: Language code (pt, pt-BR, en, es, etc.)
            voice_profile: Optional voice profile for cloning
            quality_profile: Quality preset (balanced, expressive, stable)
            speed: Speech speed (0.5-2.0)
            **kwargs: Engine-specific parameters
        
        Returns:
            Tuple[bytes, float]: (WAV audio bytes, duration in seconds)
        
        Raises:
            ValueError: If invalid parameters
            TTSEngineException: If synthesis fails
        """
        pass
    
    @abstractmethod
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None,
        ref_text: Optional[str] = None
    ) -> VoiceProfile:
        """
        Create voice profile from reference audio.
        
        Args:
            audio_path: Path to reference audio (WAV)
            language: Language code
            voice_name: Name for voice profile
            description: Optional description
            ref_text: Optional transcription (F5-TTS uses this)
        
        Returns:
            VoiceProfile: Created voice profile
        
        Raises:
            FileNotFoundError: If audio not found
            InvalidAudioException: If audio invalid (<3s, wrong format)
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List[str]: Language codes (e.g. ['en', 'pt', 'pt-BR', ...])
        """
        pass
    
    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Engine identifier (e.g. 'xtts', 'f5tts')"""
        pass
    
    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output sample rate (e.g. 24000)"""
        pass
```

#### 2.2.2. Factory Pattern: `engines/factory.py` (NOVO)

```python
"""
Factory for creating TTS engines with singleton caching
"""
import logging
from typing import Dict, Optional
from .base import TTSEngine
from .xtts_engine import XttsEngine
from .f5tts_engine import F5TtsEngine
from ..exceptions import TTSEngineException

logger = logging.getLogger(__name__)

# Singleton cache to avoid recreating engines
_ENGINE_CACHE: Dict[str, TTSEngine] = {}


def create_engine(
    engine_type: str,
    settings: dict,
    force_recreate: bool = False
) -> TTSEngine:
    """
    Factory method to create TTS engines with caching.
    
    Args:
        engine_type: Engine identifier ('xtts', 'f5tts')
        settings: Application settings dict
        force_recreate: If True, recreate even if cached
    
    Returns:
        TTSEngine: Engine instance (cached or new)
    
    Raises:
        ValueError: If engine_type unknown
        TTSEngineException: If engine initialization fails
    
    Example:
        >>> engine = create_engine('xtts', settings)
        >>> audio, duration = await engine.generate_dubbing(text="Hello", language="en")
    """
    # Check cache
    if not force_recreate and engine_type in _ENGINE_CACHE:
        logger.info(f"Using cached engine: {engine_type}")
        return _ENGINE_CACHE[engine_type]
    
    logger.info(f"Creating new engine: {engine_type}")
    
    try:
        if engine_type == 'xtts':
            engine = XttsEngine(
                device=settings['tts_engines']['xtts'].get('device'),
                fallback_to_cpu=settings['tts_engines']['xtts'].get('fallback_to_cpu', True),
                model_name=settings['tts_engines']['xtts']['model_name']
            )
        elif engine_type == 'f5tts':
            engine = F5TtsEngine(
                device=settings['tts_engines']['f5tts'].get('device'),
                fallback_to_cpu=settings['tts_engines']['f5tts'].get('fallback_to_cpu', True),
                model_name=settings['tts_engines']['f5tts']['model_name']
            )
        else:
            raise ValueError(f"Unknown engine type: {engine_type}. Supported: xtts, f5tts")
        
        # Cache engine
        _ENGINE_CACHE[engine_type] = engine
        logger.info(f"✅ Engine {engine_type} created and cached")
        
        return engine
    
    except Exception as e:
        logger.error(f"Failed to create engine {engine_type}: {e}")
        raise TTSEngineException(f"Engine initialization failed: {engine_type}") from e


def create_engine_with_fallback(
    engine_type: str,
    settings: dict,
    fallback_engine: str = 'xtts'
) -> TTSEngine:
    """
    Create engine with graceful fallback to default.
    
    Args:
        engine_type: Desired engine type
        settings: Application settings
        fallback_engine: Fallback engine if primary fails (default: xtts)
    
    Returns:
        TTSEngine: Primary or fallback engine
    
    Example:
        >>> engine = create_engine_with_fallback('f5tts', settings)
        >>> # If F5-TTS fails, falls back to XTTS automatically
    """
    try:
        return create_engine(engine_type, settings)
    except Exception as e:
        if engine_type != fallback_engine:
            logger.warning(
                f"Failed to load {engine_type}, falling back to {fallback_engine}: {e}"
            )
            try:
                return create_engine(fallback_engine, settings)
            except Exception as fallback_error:
                logger.error(f"Fallback engine {fallback_engine} also failed: {fallback_error}")
                raise TTSEngineException("All engines failed to initialize") from fallback_error
        else:
            raise TTSEngineException(f"Primary engine {engine_type} failed") from e


def clear_engine_cache(engine_type: Optional[str] = None):
    """
    Clear engine cache (useful for testing or reloading).
    
    Args:
        engine_type: Specific engine to clear, or None for all
    """
    global _ENGINE_CACHE
    
    if engine_type:
        if engine_type in _ENGINE_CACHE:
            del _ENGINE_CACHE[engine_type]
            logger.info(f"Cleared cache for engine: {engine_type}")
    else:
        _ENGINE_CACHE.clear()
        logger.info("Cleared all engine cache")
```

#### 2.2.3. XTTS Engine: `engines/xtts_engine.py` (REFACTOR)

```python
"""
XTTS v2 Engine Implementation
Refactored from xtts_client.py to implement TTSEngine interface
"""
# Move código completo de xtts_client.py para cá
# Classe renomeada: XTTSClient → XttsEngine
# Herda de TTSEngine
# Implementa métodos da interface
# Mantém integração RVC existente

from .base import TTSEngine

class XttsEngine(TTSEngine):
    """XTTS v2 TTS engine implementation"""
    
    @property
    def engine_name(self) -> str:
        return 'xtts'
    
    @property
    def sample_rate(self) -> int:
        return 24000
    
    # ... resto do código de xtts_client.py ...
    # (ver PHASE-1-XTTS-ANALYSIS.md para código completo)
```

#### 2.2.4. F5-TTS Engine: `engines/f5tts_engine.py` (NOVO)

```python
"""
F5-TTS Engine Implementation
Flow Matching Diffusion TTS for maximum expressiveness
"""
import logging
import os
import torch
import soundfile as sf
import io
import asyncio
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import datetime

from .base import TTSEngine
from ..models import VoiceProfile, QualityProfile
from ..exceptions import InvalidAudioException, TTSEngineException
from ..resilience import retry_async, with_timeout

logger = logging.getLogger(__name__)


class F5TtsEngine(TTSEngine):
    """F5-TTS engine for expressive TTS"""
    
    def __init__(
        self,
        device: Optional[str] = None,
        fallback_to_cpu: bool = True,
        model_name: str = "F5-TTS"
    ):
        """
        Initialize F5-TTS engine.
        
        Args:
            device: 'cpu' or 'cuda' (auto-detect if None)
            fallback_to_cpu: If True, use CPU when CUDA unavailable
            model_name: F5-TTS model variant (F5-TTS, F5-TTS_v1_Base)
        """
        # Device detection
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
            if device == 'cuda' and not torch.cuda.is_available():
                if fallback_to_cpu:
                    logger.warning("CUDA requested but not available, falling back to CPU")
                    self.device = 'cpu'
                else:
                    raise RuntimeError("CUDA requested but not available")
        
        logger.info(f"Initializing F5-TTS engine on device: {self.device}")
        
        # Model configuration
        self.model_name = model_name
        self._sample_rate = 24000  # F5-TTS uses 24kHz
        
        # F5-TTS parameters (defaults)
        self.nfe_step = 32  # Number of function evaluations (quality vs speed)
        self.cfg_strength = 2.0  # Classifier-free guidance strength
        self.sway_sampling_coef = -1  # Sway sampling coefficient (auto)
        
        # Load model
        self._load_model()
        
        logger.info(f"F5-TTS model loaded: {self.model_name}")
        
        # RVC client (lazy load)
        self.rvc_client = None
        
        # Whisper for auto-transcription (lazy load)
        self.whisper_client = None
    
    def _load_model(self):
        """Load F5-TTS model from HuggingFace or local"""
        try:
            from f5_tts.api import F5TTS
            
            self.tts = F5TTS(
                model_type=self.model_name,
                device=self.device
            )
            
            logger.info(f"F5-TTS loaded: {self.model_name} on {self.device}")
        except ImportError:
            raise TTSEngineException(
                "F5-TTS not installed. Run: pip install f5-tts"
            )
        except Exception as e:
            raise TTSEngineException(f"Failed to load F5-TTS model: {e}") from e
    
    @property
    def engine_name(self) -> str:
        return 'f5tts'
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate
    
    def get_supported_languages(self) -> List[str]:
        """
        F5-TTS supports 100+ languages via zero-shot.
        Best quality: EN, ZH (trained).
        PT-BR: zero-shot (quality to be tested).
        """
        # F5-TTS é multilíngue genérico via zero-shot
        # Lista principais linguagens (não exhaustiva)
        return [
            'en', 'en-US', 'en-GB',  # Inglês (treinado)
            'zh', 'zh-CN', 'zh-TW',  # Chinês (treinado)
            'pt', 'pt-BR', 'pt-PT',  # Português (zero-shot)
            'es', 'es-ES', 'es-MX',  # Espanhol (zero-shot)
            'fr', 'fr-FR',           # Francês (zero-shot)
            'de', 'de-DE',           # Alemão (zero-shot)
            'it', 'it-IT',           # Italiano (zero-shot)
            'ja', 'ja-JP',           # Japonês (zero-shot)
            'ko', 'ko-KR',           # Coreano (zero-shot)
            # + ~90 outras linguagens via zero-shot
        ]
    
    def _map_quality_profile(self, profile: QualityProfile) -> dict:
        """
        Map QualityProfile to F5-TTS parameters.
        
        XTTS params:              F5-TTS params:
        - temperature         →   nfe_step
        - top_p               →   cfg_strength
        - repetition_penalty  →   sway_sampling_coef
        """
        profiles = {
            QualityProfile.BALANCED: {
                'nfe_step': 32,  # Medium quality/speed
                'cfg_strength': 2.0,
                'sway_sampling_coef': -1,
            },
            QualityProfile.EXPRESSIVE: {
                'nfe_step': 50,  # High quality (slower)
                'cfg_strength': 2.5,  # More adherence to text
                'sway_sampling_coef': 0.3,  # More variation
            },
            QualityProfile.STABLE: {
                'nfe_step': 16,  # Fast (lower quality)
                'cfg_strength': 1.5,  # Less strict
                'sway_sampling_coef': -1,  # Auto
            },
        }
        return profiles[profile]
    
    def _load_rvc_client(self):
        """Lazy load RVC client (same as XTTS)"""
        if self.rvc_client is not None:
            return
        
        from ..rvc_client import RvcClient
        
        logger.info("Initializing RVC client (lazy load)")
        self.rvc_client = RvcClient(
            device=self.device,
            fallback_to_cpu=True
        )
        logger.info("RVC client ready")
    
    def _load_whisper_client(self):
        """Lazy load Whisper for auto-transcription"""
        if self.whisper_client is not None:
            return
        
        try:
            from faster_whisper import WhisperModel
            
            logger.info("Loading Whisper model for auto-transcription")
            self.whisper_client = WhisperModel(
                "base",  # Modelo leve (sufficient for ref transcription)
                device=self.device,
                compute_type="float16" if self.device == "cuda" else "int8"
            )
            logger.info("Whisper model loaded")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")
            self.whisper_client = None
    
    async def _auto_transcribe(self, audio_path: str) -> str:
        """
        Auto-transcribe audio using Whisper (fallback).
        
        Args:
            audio_path: Path to audio file
        
        Returns:
            Transcribed text
        """
        self._load_whisper_client()
        
        if self.whisper_client is None:
            raise TTSEngineException("Whisper not available for auto-transcription")
        
        logger.info(f"Auto-transcribing: {audio_path}")
        
        loop = asyncio.get_event_loop()
        segments, info = await loop.run_in_executor(
            None,
            lambda: self.whisper_client.transcribe(audio_path, beam_size=5)
        )
        
        transcription = " ".join([segment.text for segment in segments])
        logger.info(f"Transcription: {transcription[:100]}...")
        
        return transcription.strip()
    
    @retry_async(max_attempts=3, delay_seconds=5, backoff_multiplier=2.0)
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_profile: Optional[VoiceProfile] = None,
        quality_profile: QualityProfile = QualityProfile.BALANCED,
        speed: float = 1.0,
        # RVC parameters (compatible with XTTS)
        enable_rvc: bool = False,
        rvc_model = None,
        rvc_params = None,
        **kwargs
    ) -> Tuple[bytes, float]:
        """
        Generate dubbed audio using F5-TTS.
        
        Args:
            text: Text to synthesize
            language: Language code (pt, en, etc.)
            voice_profile: Optional voice profile for cloning
            quality_profile: Quality preset
            speed: Speech speed (0.5-2.0)
            enable_rvc: Apply RVC post-processing
            rvc_model: RVC model (if enable_rvc=True)
            rvc_params: RVC parameters
        
        Returns:
            Tuple[bytes, float]: (WAV audio, duration)
        
        Note:
            F5-TTS works best with ref_text (transcription).
            If voice_profile.ref_text is None, will auto-transcribe (slower).
        """
        # Validations
        if not text or text.strip() == "":
            raise ValueError("Empty text")
        
        # Map quality profile to F5-TTS params
        params = self._map_quality_profile(quality_profile)
        
        logger.info(f"Generating audio with F5-TTS: profile={quality_profile.value}")
        logger.debug(f"F5-TTS params: nfe_step={params['nfe_step']}, "
                    f"cfg_strength={params['cfg_strength']}")
        
        # Prepare reference audio and text
        ref_audio = None
        ref_text = None
        
        if voice_profile is not None:
            ref_audio = voice_profile.source_audio_path
            
            if not os.path.exists(ref_audio):
                raise InvalidAudioException(f"Reference audio not found: {ref_audio}")
            
            # Get ref_text from profile or auto-transcribe
            if hasattr(voice_profile, 'ref_text') and voice_profile.ref_text:
                ref_text = voice_profile.ref_text
                logger.info("Using ref_text from VoiceProfile")
            else:
                logger.warning("No ref_text in VoiceProfile, auto-transcribing (slower)")
                ref_text = await self._auto_transcribe(ref_audio)
        
        # Run inference
        loop = asyncio.get_event_loop()
        
        try:
            audio = await with_timeout(
                loop.run_in_executor(
                    None,
                    lambda: self.tts.infer(
                        gen_text=text,
                        ref_file=ref_audio,
                        ref_text=ref_text,
                        nfe_step=params['nfe_step'],
                        cfg_strength=params['cfg_strength'],
                        sway_sampling_coef=params['sway_sampling_coef'],
                        speed=speed
                    )
                ),
                timeout_seconds=300
            )
            
            # audio is numpy array
            sr = self.sample_rate
            
            # Apply RVC if enabled (same as XTTS)
            if enable_rvc:
                if rvc_model is None:
                    logger.warning("RVC enabled but no model provided, skipping")
                else:
                    try:
                        logger.info(f"Applying RVC conversion with model: {rvc_model.name}")
                        self._load_rvc_client()
                        
                        if rvc_params is None:
                            from ..models import RvcParameters
                            rvc_params = RvcParameters()
                        
                        converted_audio, rvc_duration = await self.rvc_client.convert_audio(
                            audio_data=audio,
                            sample_rate=sr,
                            rvc_model=rvc_model,
                            params=rvc_params
                        )
                        
                        audio = converted_audio
                        logger.info(f"RVC conversion successful: {rvc_duration:.2f}s")
                    except Exception as e:
                        logger.error(f"RVC failed, using F5-TTS audio: {e}")
            
            # Convert to bytes (WAV)
            buffer = io.BytesIO()
            sf.write(buffer, audio, sr, format='WAV')
            audio_bytes = buffer.getvalue()
            
            # Duration
            duration = len(audio) / sr
            
            logger.info(f"Generated audio: {duration:.2f}s, {len(audio_bytes)} bytes")
            
            return audio_bytes, duration
        
        except Exception as e:
            logger.error(f"F5-TTS inference failed: {e}")
            raise TTSEngineException(f"F5-TTS synthesis error: {str(e)}") from e
    
    @retry_async(max_attempts=2, delay_seconds=3, backoff_multiplier=2.0)
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None,
        ref_text: Optional[str] = None
    ) -> VoiceProfile:
        """
        Create voice profile for F5-TTS.
        
        Args:
            audio_path: Reference audio path
            language: Language code
            voice_name: Profile name
            description: Optional description
            ref_text: Transcription (if None, auto-transcribe)
        
        Returns:
            VoiceProfile with ref_text field
        """
        # Validate audio
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio not found: {audio_path}")
        
        try:
            audio_data, sr = sf.read(audio_path)
            duration = len(audio_data) / sr
            
            if duration < 3.0:
                raise InvalidAudioException(
                    f"Audio too short: {duration:.2f}s (minimum 3s for cloning)"
                )
            
            # Auto-transcribe if ref_text not provided
            if ref_text is None:
                logger.warning("No ref_text provided, auto-transcribing (recommended for F5-TTS)")
                ref_text = await self._auto_transcribe(audio_path)
            
            # Create VoiceProfile with ref_text
            profile = VoiceProfile.create_new(
                name=voice_name,
                language=language,
                source_audio_path=audio_path,
                profile_path=audio_path,  # F5-TTS uses audio directly
                description=description,
                duration=duration,
                sample_rate=sr,
                ttl_days=30
            )
            
            # Add ref_text (F5-TTS specific)
            profile.ref_text = ref_text
            
            logger.info(f"Voice profile created: {profile.id} ({voice_name}) with ref_text")
            
            return profile
        
        except Exception as e:
            logger.error(f"Failed to create voice profile: {e}")
            raise InvalidAudioException(f"Voice cloning error: {str(e)}") from e
```

---

## 🔧 PARTE 3: MODIFICAÇÕES EM ARQUIVOS EXISTENTES

### 3.1. `config.py` - Adicionar Multi-Engine Config

```python
# ANTES (linha 60-86):
'xtts': {
    'model_name': os.getenv('XTTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2'),
    # ... configs XTTS
},

# DEPOIS:
# ===== TTS ENGINE SELECTION =====
'tts_engine_default': os.getenv('TTS_ENGINE_DEFAULT', 'xtts'),  # ← NOVO

'tts_engines': {  # ← NOVO (wrapper)
    'xtts': {
        'model_name': os.getenv('XTTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2'),
        'device': os.getenv('XTTS_DEVICE', None),
        'fallback_to_cpu': os.getenv('XTTS_FALLBACK_CPU', 'true').lower() == 'true',
        # ... todas as configs XTTS atuais (sem mudanças)
    },
    'f5tts': {  # ← NOVO
        'model_name': os.getenv('F5TTS_MODEL', 'F5-TTS'),
        'device': os.getenv('F5TTS_DEVICE', 'cuda'),
        'fallback_to_cpu': os.getenv('F5TTS_FALLBACK_CPU', 'true').lower() == 'true',
        
        # F5-TTS specific parameters
        'nfe_step': int(os.getenv('F5TTS_NFE_STEP', '32')),
        'cfg_strength': float(os.getenv('F5TTS_CFG_STRENGTH', '2.0')),
        'sway_sampling_coef': float(os.getenv('F5TTS_SWAY_COEF', '-1')),
        
        # Sample rate
        'sample_rate': int(os.getenv('F5TTS_SAMPLE_RATE', '24000')),
    },
},
```

### 3.2. `models.py` - Adicionar `ref_text` ao VoiceProfile

```python
# ANTES (linha ~120):
class VoiceProfile(BaseModel):
    """Perfil de voz clonada"""
    id: str
    name: str
    language: str
    source_audio_path: str
    profile_path: str
    # ... outros campos

# DEPOIS:
class VoiceProfile(BaseModel):
    """Perfil de voz clonada (multi-engine)"""
    id: str
    name: str
    language: str
    source_audio_path: str
    profile_path: str
    
    # F5-TTS specific (optional for XTTS)
    ref_text: Optional[str] = None  # ← NOVO: Transcrição do áudio de referência
    
    # ... outros campos (sem mudanças)
```

### 3.3. `models.py` - Adicionar `tts_engine` ao Job

```python
# ANTES (linha ~200+):
class Job(BaseModel):
    id: str
    mode: JobMode
    status: JobStatus
    # ... campos

# DEPOIS:
class Job(BaseModel):
    id: str
    mode: JobMode
    status: JobStatus
    
    # TTS Engine selection
    tts_engine: Optional[str] = None  # ← NOVO: 'xtts', 'f5tts', or None (uses default)
    tts_engine_used: Optional[str] = None  # ← NOVO: Audit trail (qual engine foi usado)
    
    # ... outros campos (sem mudanças)
```

### 3.4. `processor.py` - Usar Factory Pattern

```python
# ANTES (linha 45-54):
def _load_engine(self):
    """Carrega modelo XTTS (lazy initialization)"""
    if self.engine is not None:
        return
    
    from .xtts_client import XTTSClient  # ← HARDCODED
    logger.info("Initializing XTTS engine")
    
    self.engine = XTTSClient(...)  # ← HARDCODED

# DEPOIS:
def _load_engine(self, engine_type: Optional[str] = None):
    """
    Carrega modelo TTS via factory (lazy initialization).
    
    Args:
        engine_type: 'xtts', 'f5tts', or None (uses default from settings)
    """
    if self.engine is not None and engine_type is None:
        return  # Já carregado e sem override
    
    if engine_type is None:
        engine_type = self.settings.get('tts_engine_default', 'xtts')
    
    logger.info(f"Initializing TTS engine: {engine_type}")
    
    from .engines.factory import create_engine_with_fallback
    
    self.engine = create_engine_with_fallback(
        engine_type=engine_type,
        settings=self.settings,
        fallback_engine='xtts'  # Graceful fallback
    )
    
    logger.info(f"✅ Engine {self.engine.engine_name} loaded")
```

```python
# ANTES (linha ~60+):
async def process_dubbing_job(self, job: Job, voice_profile: Optional[VoiceProfile] = None) -> Job:
    # Garante que engine esteja carregado (lazy load)
    if self.engine is None:
        self._load_engine()

# DEPOIS:
async def process_dubbing_job(self, job: Job, voice_profile: Optional[VoiceProfile] = None) -> Job:
    # Determina engine a usar
    engine_type = job.tts_engine or self.settings.get('tts_engine_default', 'xtts')
    
    # Carrega engine (lazy load com cache)
    self._load_engine(engine_type)
    
    # Audit trail
    job.tts_engine_used = self.engine.engine_name
    
    # ... resto do código (sem mudanças significativas)
```

### 3.5. `main.py` - Adicionar Parâmetro `tts_engine`

```python
# ANTES (linha 233+):
@app.post("/jobs", response_model=Job)
async def create_job(
    text: str = Form(...),
    source_language: str = Form(...),
    mode: JobMode = Form(...),
    # ... outros parâmetros

# DEPOIS:
@app.post("/jobs", response_model=Job)
async def create_job(
    text: str = Form(...),
    source_language: str = Form(...),
    mode: JobMode = Form(...),
    # ... outros parâmetros
    
    # TTS Engine selection (NEW - optional override)
    tts_engine: Optional[str] = Form(
        None,
        description="TTS engine override ('xtts', 'f5tts'). If None, uses TTS_ENGINE_DEFAULT env var."
    ),
) -> Job:
    """
    Create TTS job with optional engine selection.
    
    New Parameters:
        tts_engine: Override default TTS engine ('xtts', 'f5tts', or None)
                   If None, uses TTS_ENGINE_DEFAULT from environment.
    """
    # Validate tts_engine if provided
    if tts_engine is not None:
        valid_engines = ['xtts', 'f5tts']
        if tts_engine not in valid_engines:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tts_engine: {tts_engine}. Valid: {valid_engines}"
            )
    
    # ... resto do código (cria job com job.tts_engine = tts_engine)
```

### 3.6. `main.py` - Adicionar `ref_text` em Clone Endpoint

```python
# ANTES:
@app.post("/voices/clone")
async def clone_voice(
    audio_file: UploadFile = File(...),
    voice_name: str = Form(...),
    language: str = Form(...),
    # ...

# DEPOIS:
@app.post("/voices/clone")
async def clone_voice(
    audio_file: UploadFile = File(...),
    voice_name: str = Form(...),
    language: str = Form(...),
    description: Optional[str] = Form(None),
    
    # F5-TTS specific (optional, but recommended for better quality)
    ref_text: Optional[str] = Form(
        None,
        description="Transcription of reference audio (recommended for F5-TTS). If None, will auto-transcribe (slower)."
    ),
) -> VoiceProfile:
    """
    Clone voice with optional transcription.
    
    New Parameters:
        ref_text: Transcription of reference audio.
                 - XTTS: Ignored (not needed)
                 - F5-TTS: Used for better cloning (or auto-transcribed if None)
    """
    # ... salva arquivo, depois:
    
    voice_profile = await processor.engine.clone_voice(
        audio_path=audio_path,
        language=language,
        voice_name=voice_name,
        description=description,
        ref_text=ref_text  # ← NOVO (passa para engine)
    )
    
    # ... resto
```

---

## 📋 PARTE 4: ESTRATÉGIA DE TESTES (TDD)

### 4.1. Estrutura de Testes

```
tests/
├── unit/
│   ├── engines/
│   │   ├── test_xtts_engine.py (refactor de test_xtts_client_*.py)
│   │   ├── test_f5tts_engine.py (NOVO - testes F5-TTS)
│   │   └── test_engine_factory.py (NOVO - testes factory)
│   ├── test_processor_multi_engine.py (NOVO - processor com multi-engine)
│   └── ... (testes existentes mantidos)
├── integration/
│   ├── test_multi_engine_switching.py (NOVO - troca de engines)
│   └── test_engine_fallback.py (NOVO - graceful degradation)
└── ... (e2e, performance mantidos)
```

### 4.2. Testes Prioritários (TDD Order)

#### Sprint 1: Interface e Factory
```python
# tests/unit/engines/test_engine_factory.py
def test_create_xtts_engine():
    """Factory cria XTTS com sucesso"""
    engine = create_engine('xtts', settings)
    assert engine.engine_name == 'xtts'
    assert isinstance(engine, XttsEngine)

def test_create_f5tts_engine():
    """Factory cria F5-TTS com sucesso"""
    engine = create_engine('f5tts', settings)
    assert engine.engine_name == 'f5tts'
    assert isinstance(engine, F5TtsEngine)

def test_engine_caching():
    """Factory cacheia engines (singleton)"""
    engine1 = create_engine('xtts', settings)
    engine2 = create_engine('xtts', settings)
    assert engine1 is engine2  # Mesma instância

def test_fallback_to_xtts():
    """Fallback para XTTS quando F5-TTS falha"""
    # Mock F5-TTS para falhar
    with patch('...F5TtsEngine', side_effect=Exception("F5-TTS error")):
        engine = create_engine_with_fallback('f5tts', settings)
        assert engine.engine_name == 'xtts'  # Fallback

def test_invalid_engine_type():
    """Erro ao criar engine inválido"""
    with pytest.raises(ValueError, match="Unknown engine type"):
        create_engine('invalid_engine', settings)
```

#### Sprint 2: F5-TTS Engine Implementation
```python
# tests/unit/engines/test_f5tts_engine.py
@pytest.mark.asyncio
async def test_f5tts_basic_synthesis():
    """F5-TTS gera áudio básico"""
    engine = F5TtsEngine(device='cpu')
    audio, duration = await engine.generate_dubbing(
        text="Hello world",
        language="en"
    )
    assert len(audio) > 0
    assert duration > 0

@pytest.mark.asyncio
async def test_f5tts_voice_cloning_with_ref_text():
    """F5-TTS clona voz com ref_text fornecido"""
    engine = F5TtsEngine(device='cpu')
    profile = await engine.clone_voice(
        audio_path="tests/fixtures/sample_voice.wav",
        language="en",
        voice_name="Test Voice",
        ref_text="This is a test audio for voice cloning."
    )
    assert profile.ref_text == "This is a test audio for voice cloning."

@pytest.mark.asyncio
async def test_f5tts_auto_transcribe():
    """F5-TTS auto-transcreve quando ref_text=None"""
    engine = F5TtsEngine(device='cpu')
    profile = await engine.clone_voice(
        audio_path="tests/fixtures/sample_voice.wav",
        language="en",
        voice_name="Test Voice",
        ref_text=None  # Trigger auto-transcription
    )
    assert profile.ref_text is not None
    assert len(profile.ref_text) > 0

@pytest.mark.asyncio
async def test_f5tts_quality_profiles():
    """F5-TTS mapeia quality profiles corretamente"""
    engine = F5TtsEngine(device='cpu')
    
    # Balanced
    params = engine._map_quality_profile(QualityProfile.BALANCED)
    assert params['nfe_step'] == 32
    
    # Expressive
    params = engine._map_quality_profile(QualityProfile.EXPRESSIVE)
    assert params['nfe_step'] == 50  # Higher quality
    
    # Stable
    params = engine._map_quality_profile(QualityProfile.STABLE)
    assert params['nfe_step'] == 16  # Faster

@pytest.mark.asyncio
async def test_f5tts_rvc_integration():
    """F5-TTS integra com RVC (pós-processamento)"""
    engine = F5TtsEngine(device='cpu')
    
    # Mock RVC
    with patch.object(engine, 'rvc_client') as mock_rvc:
        mock_rvc.convert_audio = AsyncMock(return_value=(np.zeros(48000), 2.0))
        
        audio, duration = await engine.generate_dubbing(
            text="Test",
            language="en",
            enable_rvc=True,
            rvc_model=MagicMock()
        )
        
        # RVC foi chamado
        assert mock_rvc.convert_audio.called
```

#### Sprint 3: Multi-Engine Integration
```python
# tests/integration/test_multi_engine_switching.py
@pytest.mark.asyncio
async def test_switch_engine_via_job():
    """Job pode especificar engine diferente do default"""
    processor = VoiceProcessor()
    
    # Job com XTTS
    job_xtts = Job(tts_engine='xtts', ...)
    await processor.process_dubbing_job(job_xtts)
    assert job_xtts.tts_engine_used == 'xtts'
    
    # Job com F5-TTS
    job_f5tts = Job(tts_engine='f5tts', ...)
    await processor.process_dubbing_job(job_f5tts)
    assert job_f5tts.tts_engine_used == 'f5tts'

@pytest.mark.asyncio
async def test_default_engine_from_settings():
    """Usa engine default quando job.tts_engine=None"""
    processor = VoiceProcessor()
    processor.settings['tts_engine_default'] = 'f5tts'
    
    job = Job(tts_engine=None, ...)
    await processor.process_dubbing_job(job)
    
    assert job.tts_engine_used == 'f5tts'
```

### 4.3. Coverage Target

- **Engines:** 90%+ coverage
- **Factory:** 95%+ coverage (crítico)
- **Integration:** 80%+ coverage
- **E2E:** Smoke tests para ambos engines

---

## ⚠️ PARTE 5: RISCOS E MITIGAÇÕES

### 5.1. Riscos Técnicos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| **F5-TTS PT-BR inferior ao XTTS** | Alta | Médio | Testes extensivos antes de recomendar. Manter XTTS como default. |
| **F5-TTS performance inaceitável** | Média | Alto | Benchmarks antes de deploy. Documentar RTF claramente. |
| **Dependency conflicts (Coqui vs F5-TTS)** | Baixa | Alto | Testar instalação em ambiente limpo. Isolar imports. |
| **VRAM OOM com ambos engines carregados** | Média | Alto | Factory cache limpa engine não usado. Lazy loading. |
| **RVC incompatibilidade com F5-TTS** | Baixa | Médio | RVC já é agnóstico (WAV→WAV). Testar em Sprint 2. |
| **Whisper auto-transcription latência** | Alta | Baixo | Exigir ref_text no frontend. Whisper só fallback. |
| **Breaking changes na API** | Baixa | Crítico | Testes de regressão. Parâmetros opcionais apenas. |

### 5.2. Riscos de Negócio

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| **Usuários confusos com escolha de engine** | Média | Médio | Documentação clara. Default inteligente (XTTS). |
| **Licença CC-BY-NC limita uso comercial** | Baixa | Alto | Avisar usuários. Considerar fine-tuning com dados próprios. |
| **F5-TTS abandonado pelo desenvolvedor** | Baixa | Médio | XTTS sempre disponível como fallback. |

### 5.3. Plano de Rollback

Se F5-TTS causar problemas em produção:

1. **Fase 1 (Imediato - 5min):**
   ```bash
   # Desabilitar F5-TTS via env var
   export TTS_ENGINE_DEFAULT=xtts
   # Restart API + workers
   ```

2. **Fase 2 (Se necessário - 1h):**
   ```python
   # Bloquear F5-TTS no factory
   def create_engine(engine_type, settings):
       if engine_type == 'f5tts':
           logger.error("F5-TTS disabled due to production issue")
           engine_type = 'xtts'  # Force fallback
       # ...
   ```

3. **Fase 3 (Último recurso - 1 dia):**
   ```bash
   # Reverter para commit anterior (pré-F5-TTS)
   git revert <commits>
   # Redeploy
   ```

---

## 📅 PARTE 6: PRÓXIMOS PASSOS

### Fase Atual: FASE 2 COMPLETA ✅

- ✅ Pesquisa F5-TTS completa
- ✅ Comparação XTTS vs F5-TTS
- ✅ Identificação de gaps
- ✅ Arquitetura multi-engine definida
- ✅ Implementação detalhada documentada

### Próxima Fase: FASE 3 - Criar SPRINTS.md

**Objetivo:** Detalhar sprint-by-sprint o plano de implementação.

**Conteúdo SPRINTS.md:**
1. Sprint 1: Interface Base + Factory Pattern (2-3 dias)
2. Sprint 2: Implementação F5TtsEngine (3-4 dias)
3. Sprint 3: Refatoração XttsEngine (2 dias)
4. Sprint 4: Integração Processor + API (2-3 dias)
5. Sprint 5: Testes Unitários Completos (3 dias)
6. Sprint 6: Testes de Integração (2 dias)
7. Sprint 7: Testes E2E (2 dias)
8. Sprint 8: Benchmarks PT-BR (2 dias)
9. Sprint 9: Documentação Final (1 dia)
10. Sprint 10: Deploy Gradual (2 semanas)

**Estimativa Total:** ~4-6 semanas

---

## ✅ CHECKLIST - IMPLEMENTATION F5TTS.MD

- [x] Sumário executivo com objetivo e escopo
- [x] Comparação técnica XTTS vs F5-TTS
- [x] Casos de uso recomendados
- [x] Gap crítico (ref_text) identificado e soluções propostas
- [x] Arquitetura multi-engine com diagrama
- [x] Componentes novos (interface, factory, engines) especificados
- [x] Modificações em arquivos existentes detalhadas
- [x] Estratégia de testes (TDD) com exemplos
- [x] Riscos e mitigações documentados
- [x] Plano de rollback definido
- [x] Próximos passos (SPRINTS.md) planejados

---

**Status:** ✅ **IMPLEMENTATION F5TTS.MD - COMPLETO**  
**Próximo:** Criar **SPRINTS.md** (FASE 4)

---

_Documento gerado por Engenheiro(a) Sênior de Áudio e Backend_  
_Data: 27 de Novembro de 2025_  
_Versão: 1.0_

