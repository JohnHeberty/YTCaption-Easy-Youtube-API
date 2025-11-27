# SPRINTS - Integração F5-TTS Multi-Engine

**Data:** 27 de Novembro de 2025  
**Autor:** Engenheiro(a) Sênior de Áudio e Backend  
**Baseado em:** IMPLEMENTATION_F5TTS.md, PHASE-1-XTTS-ANALYSIS.md  
**Status:** PLANEJAMENTO APROVADO

---

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Metodologia TDD](#metodologia-tdd)
3. [Sprint 1: Interface Base + Factory Pattern](#sprint-1-interface-base--factory-pattern)
4. [Sprint 2: Implementação F5TtsEngine](#sprint-2-implementação-f5ttsengine)
5. [Sprint 3: Refatoração XttsEngine](#sprint-3-refatoração-xttsengine)
6. [Sprint 4: Integração Processor + API](#sprint-4-integração-processor--api)
7. [Sprint 5: Testes Unitários Completos](#sprint-5-testes-unitários-completos)
8. [Sprint 6: Testes de Integração](#sprint-6-testes-de-integração)
9. [Sprint 7: Testes E2E](#sprint-7-testes-e2e)
10. [Sprint 8: Benchmarks PT-BR](#sprint-8-benchmarks-pt-br)
11. [Sprint 9: Documentação Final](#sprint-9-documentação-final)
12. [Sprint 10: Deploy Gradual](#sprint-10-deploy-gradual)
13. [Comandos Úteis](#comandos-úteis)
14. [Checklist Geral](#checklist-geral)

---

## 🎯 VISÃO GERAL

### Objetivo
Integrar **F5-TTS** como segundo motor TTS, mantendo **XTTS v2** como default, com seleção via `TTS_ENGINE_DEFAULT` env var.

### Princípios

1. **Zero Breaking Changes** - API pública mantém compatibilidade 100%
2. **TDD Rigoroso** - Testes ANTES da implementação (Red-Green-Refactor)
3. **Graceful Degradation** - F5-TTS falha → XTTS (fallback automático)
4. **Incremental & Safe** - Cada sprint entrega valor, mantém estabilidade
5. **Opt-in** - F5-TTS é opcional (`TTS_ENGINE_DEFAULT=xtts` por padrão)

### Timeline Estimado

```
┌─────────────────────────────────────────────────────────────┐
│ FASE 1: FUNDAÇÃO (Sprints 1-3)         | 7-9 dias          │
├─────────────────────────────────────────────────────────────┤
│ Sprint 1: Interface + Factory           | 2-3 dias          │
│ Sprint 2: F5TtsEngine Implementation    | 3-4 dias          │
│ Sprint 3: XttsEngine Refactor           | 2 dias            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ FASE 2: INTEGRAÇÃO (Sprints 4-5)       | 5-6 dias          │
├─────────────────────────────────────────────────────────────┤
│ Sprint 4: Processor + API Integration   | 2-3 dias          │
│ Sprint 5: Unit Tests Complete           | 3 dias            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ FASE 3: VALIDAÇÃO (Sprints 6-8)        | 6 dias            │
├─────────────────────────────────────────────────────────────┤
│ Sprint 6: Integration Tests             | 2 dias            │
│ Sprint 7: E2E Tests                     | 2 dias            │
│ Sprint 8: PT-BR Benchmarks              | 2 dias            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ FASE 4: FINALIZAÇÃO (Sprints 9-10)     | 1 dia + 2 semanas │
├─────────────────────────────────────────────────────────────┤
│ Sprint 9: Documentation                 | 1 dia             │
│ Sprint 10: Gradual Rollout              | 2 semanas         │
└─────────────────────────────────────────────────────────────┘

TOTAL: ~4-6 semanas (18-24 dias úteis + 2 semanas rollout)
```

---

## 🧪 METODOLOGIA TDD

### Ciclo Red-Green-Refactor

```
┌─────────────────────────────────────────┐
│ 1. RED: Escrever teste que FALHA       │
│    - Define comportamento esperado      │
│    - Teste deve falhar (código não      │
│      existe ainda)                      │
│    - Validar que teste detecta falhas   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 2. GREEN: Implementar código MÍNIMO    │
│    - Fazer teste passar                │
│    - Não otimizar ainda                │
│    - Código mais simples possível      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 3. REFACTOR: Melhorar código           │
│    - Limpar duplicações                │
│    - Otimizar performance              │
│    - Adicionar documentação            │
│    - Manter testes GREEN               │
└──────────────┬──────────────────────────┘
               │
               └──────> [Próximo teste]
```

### Comandos de Teste

```bash
# Rodar todos os testes
pytest -v

# Rodar testes de uma sprint específica
pytest tests/unit/engines/ -v

# Rodar com coverage
pytest --cov=app --cov-report=html --cov-report=term

# Rodar apenas testes marcados
pytest -m "unit" -v
pytest -m "integration" -v
pytest -m "e2e" -v

# Watch mode (re-run em mudanças)
pytest-watch

# Rodar teste específico
pytest tests/unit/engines/test_f5tts_engine.py::test_basic_synthesis -v
```

---

## 🚀 SPRINT 1: Interface Base + Factory Pattern

**Duração:** 2-3 dias  
**Objetivo:** Criar fundação arquitetural (interface abstrata + factory)

### 1.1. PRÉ-REQUISITOS

- [x] PHASE-1-XTTS-ANALYSIS.md completo
- [x] IMPLEMENTATION_F5TTS.md completo
- [x] Ambiente de desenvolvimento configurado
- [ ] Branch criada: `feature/f5tts-multi-engine`

### 1.2. TAREFAS

#### 1.2.1. RED - Escrever Testes (2-3 horas)

**Arquivo:** `tests/unit/engines/test_base_interface.py` (NOVO)

```python
"""
Testes para interface TTSEngine
Red phase: Todos devem FALHAR (interface não existe)
"""
import pytest
from app.engines.base import TTSEngine
from app.models import VoiceProfile, QualityProfile


def test_tts_engine_is_abstract():
    """TTSEngine não pode ser instanciada diretamente"""
    with pytest.raises(TypeError):
        engine = TTSEngine()


def test_tts_engine_requires_generate_dubbing():
    """Subclasse deve implementar generate_dubbing()"""
    
    class IncompleteEngine(TTSEngine):
        pass
    
    with pytest.raises(TypeError):
        engine = IncompleteEngine()


def test_tts_engine_requires_clone_voice():
    """Subclasse deve implementar clone_voice()"""
    
    class IncompleteEngine(TTSEngine):
        async def generate_dubbing(self, *args, **kwargs):
            pass
    
    with pytest.raises(TypeError):
        engine = IncompleteEngine()


def test_tts_engine_requires_get_supported_languages():
    """Subclasse deve implementar get_supported_languages()"""
    
    class IncompleteEngine(TTSEngine):
        async def generate_dubbing(self, *args, **kwargs):
            pass
        
        async def clone_voice(self, *args, **kwargs):
            pass
    
    with pytest.raises(TypeError):
        engine = IncompleteEngine()


def test_tts_engine_complete_implementation():
    """Implementação completa deve funcionar"""
    
    class CompleteEngine(TTSEngine):
        @property
        def engine_name(self):
            return 'test'
        
        @property
        def sample_rate(self):
            return 24000
        
        async def generate_dubbing(self, *args, **kwargs):
            return b'audio', 1.0
        
        async def clone_voice(self, *args, **kwargs):
            return VoiceProfile(...)
        
        def get_supported_languages(self):
            return ['en', 'pt']
    
    engine = CompleteEngine()
    assert engine.engine_name == 'test'
    assert engine.sample_rate == 24000


@pytest.mark.asyncio
async def test_tts_engine_generate_dubbing_signature():
    """generate_dubbing() tem assinatura correta"""
    
    class TestEngine(TTSEngine):
        # ... implementação mínima
        
        async def generate_dubbing(
            self,
            text: str,
            language: str,
            voice_profile = None,
            quality_profile = QualityProfile.BALANCED,
            speed: float = 1.0,
            **kwargs
        ):
            return b'', 0.0
    
    engine = TestEngine()
    audio, duration = await engine.generate_dubbing(
        text="Test",
        language="en"
    )
    assert isinstance(audio, bytes)
    assert isinstance(duration, float)
```

**Arquivo:** `tests/unit/engines/test_factory.py` (NOVO)

```python
"""
Testes para factory pattern
Red phase: Todos devem FALHAR (factory não existe)
"""
import pytest
from unittest.mock import patch, MagicMock
from app.engines.factory import (
    create_engine,
    create_engine_with_fallback,
    clear_engine_cache,
    _ENGINE_CACHE
)
from app.engines.base import TTSEngine
from app.exceptions import TTSEngineException


def test_create_engine_xtts(settings):
    """Factory cria engine XTTS"""
    engine = create_engine('xtts', settings)
    
    assert engine is not None
    assert engine.engine_name == 'xtts'
    assert isinstance(engine, TTSEngine)


def test_create_engine_f5tts(settings):
    """Factory cria engine F5-TTS"""
    engine = create_engine('f5tts', settings)
    
    assert engine is not None
    assert engine.engine_name == 'f5tts'
    assert isinstance(engine, TTSEngine)


def test_create_engine_invalid():
    """Factory levanta erro para engine inválido"""
    with pytest.raises(ValueError, match="Unknown engine type"):
        create_engine('invalid_engine', {})


def test_create_engine_caches_instances(settings):
    """Factory cacheia engines (singleton)"""
    clear_engine_cache()  # Limpa cache
    
    engine1 = create_engine('xtts', settings)
    engine2 = create_engine('xtts', settings)
    
    assert engine1 is engine2  # Mesma instância


def test_create_engine_force_recreate(settings):
    """Factory recria engine quando force_recreate=True"""
    clear_engine_cache()
    
    engine1 = create_engine('xtts', settings)
    engine2 = create_engine('xtts', settings, force_recreate=True)
    
    assert engine1 is not engine2  # Instâncias diferentes


def test_create_engine_with_fallback_success(settings):
    """Fallback retorna engine primário quando sucesso"""
    engine = create_engine_with_fallback('xtts', settings)
    assert engine.engine_name == 'xtts'


def test_create_engine_with_fallback_to_xtts(settings):
    """Fallback usa XTTS quando F5-TTS falha"""
    with patch('app.engines.factory.F5TtsEngine', side_effect=Exception("F5-TTS error")):
        engine = create_engine_with_fallback('f5tts', settings, fallback_engine='xtts')
        assert engine.engine_name == 'xtts'  # Fallback


def test_create_engine_with_fallback_all_fail(settings):
    """Fallback levanta erro quando todos engines falham"""
    with patch('app.engines.factory.XttsEngine', side_effect=Exception("XTTS error")):
        with pytest.raises(TTSEngineException, match="All engines failed"):
            create_engine_with_fallback('xtts', settings)


def test_clear_engine_cache_specific():
    """Limpa cache de engine específico"""
    # Mock cache
    _ENGINE_CACHE['xtts'] = MagicMock()
    _ENGINE_CACHE['f5tts'] = MagicMock()
    
    clear_engine_cache('xtts')
    
    assert 'xtts' not in _ENGINE_CACHE
    assert 'f5tts' in _ENGINE_CACHE


def test_clear_engine_cache_all():
    """Limpa todo cache"""
    _ENGINE_CACHE['xtts'] = MagicMock()
    _ENGINE_CACHE['f5tts'] = MagicMock()
    
    clear_engine_cache()
    
    assert len(_ENGINE_CACHE) == 0
```

**Executar testes (devem FALHAR):**
```bash
pytest tests/unit/engines/test_base_interface.py -v
pytest tests/unit/engines/test_factory.py -v

# Esperado: TODOS FALHAM (módulos não existem)
```

#### 1.2.2. GREEN - Implementar Código (4-6 horas)

**Arquivo:** `app/engines/__init__.py` (NOVO)

```python
"""
TTS Engines Package
Multi-engine architecture for audio-voice service
"""
from .base import TTSEngine
from .factory import create_engine, create_engine_with_fallback, clear_engine_cache

__all__ = [
    'TTSEngine',
    'create_engine',
    'create_engine_with_fallback',
    'clear_engine_cache',
]
```

**Arquivo:** `app/engines/base.py` (NOVO)

```python
"""
Base interface for TTS engines
All engines must implement this interface
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
            language: Language code (pt, pt-BR, en, etc.)
            voice_profile: Optional voice profile for cloning
            quality_profile: Quality preset (balanced, expressive, stable)
            speed: Speech speed (0.5-2.0)
            **kwargs: Engine-specific parameters (enable_rvc, rvc_model, etc.)
        
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
            InvalidAudioException: If audio invalid
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List[str]: Language codes (e.g. ['en', 'pt', 'pt-BR'])
        """
        pass
    
    @property
    @abstractmethod
    def engine_name(self) -> str:
        """
        Engine identifier.
        
        Returns:
            str: Engine name ('xtts', 'f5tts', etc.)
        """
        pass
    
    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """
        Output sample rate.
        
        Returns:
            int: Sample rate in Hz (e.g. 24000)
        """
        pass
```

**Arquivo:** `app/engines/factory.py` (NOVO)

```python
"""
Factory for creating TTS engines with singleton caching
"""
import logging
from typing import Dict, Optional
from .base import TTSEngine
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
    """
    # Check cache
    if not force_recreate and engine_type in _ENGINE_CACHE:
        logger.info(f"Using cached engine: {engine_type}")
        return _ENGINE_CACHE[engine_type]
    
    logger.info(f"Creating new engine: {engine_type}")
    
    try:
        if engine_type == 'xtts':
            # Import apenas quando necessário (lazy import)
            from .xtts_engine import XttsEngine
            
            engine = XttsEngine(
                device=settings['tts_engines']['xtts'].get('device'),
                fallback_to_cpu=settings['tts_engines']['xtts'].get('fallback_to_cpu', True),
                model_name=settings['tts_engines']['xtts']['model_name']
            )
        elif engine_type == 'f5tts':
            # Import apenas quando necessário (lazy import)
            from .f5tts_engine import F5TtsEngine
            
            engine = F5TtsEngine(
                device=settings['tts_engines']['f5tts'].get('device'),
                fallback_to_cpu=settings['tts_engines']['f5tts'].get('fallback_to_cpu', True),
                model_name=settings['tts_engines']['f5tts']['model_name']
            )
        else:
            raise ValueError(
                f"Unknown engine type: {engine_type}. "
                f"Supported: xtts, f5tts"
            )
        
        # Cache engine
        _ENGINE_CACHE[engine_type] = engine
        logger.info(f"✅ Engine {engine_type} created and cached")
        
        return engine
    
    except Exception as e:
        logger.error(f"Failed to create engine {engine_type}: {e}", exc_info=True)
        raise TTSEngineException(
            f"Engine initialization failed: {engine_type}"
        ) from e


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
    
    Raises:
        TTSEngineException: If all engines fail
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
                logger.error(
                    f"Fallback engine {fallback_engine} also failed: {fallback_error}",
                    exc_info=True
                )
                raise TTSEngineException(
                    "All engines failed to initialize"
                ) from fallback_error
        else:
            raise TTSEngineException(
                f"Primary engine {engine_type} failed to initialize"
            ) from e


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

**Executar testes (devem PASSAR):**
```bash
pytest tests/unit/engines/test_base_interface.py -v
pytest tests/unit/engines/test_factory.py -v

# Esperado: TODOS PASSAM (GREEN)
```

#### 1.2.3. REFACTOR - Melhorar Código (1-2 horas)

- [ ] Adicionar docstrings detalhadas
- [ ] Adicionar type hints completos
- [ ] Adicionar logging em pontos críticos
- [ ] Revisar nomes de variáveis
- [ ] Verificar PEP8 compliance

```bash
# Code quality checks
ruff check app/engines/
mypy app/engines/
black app/engines/
```

### 1.3. CRITÉRIOS DE ACEITAÇÃO

- [ ] Interface `TTSEngine` criada com todos métodos abstratos
- [ ] Factory `create_engine()` funcional
- [ ] Factory `create_engine_with_fallback()` com graceful degradation
- [ ] Singleton cache funcionando
- [ ] Todos os testes GREEN (100% passing)
- [ ] Coverage ≥90% em `engines/base.py` e `engines/factory.py`
- [ ] Documentação completa (docstrings)
- [ ] Code quality checks passing (ruff, mypy, black)

### 1.4. ENTREGÁVEIS

```
app/engines/
├── __init__.py          (NOVO - 10 linhas)
├── base.py              (NOVO - 90 linhas)
└── factory.py           (NOVO - 120 linhas)

tests/unit/engines/
├── __init__.py          (NOVO)
├── conftest.py          (NOVO - fixtures)
├── test_base_interface.py (NOVO - 80 linhas)
└── test_factory.py      (NOVO - 120 linhas)
```

### 1.5. RISCOS

| Risco | Mitigação |
|-------|-----------|
| Lazy imports causam overhead | Testes de performance ao final |
| Cache pode causar memory leaks | Implementar TTL ou max_size |
| ABC não detecta todos erros | Testes rigorosos de interface |

---

## 🔥 SPRINT 2: Implementação F5TtsEngine

**Duração:** 3-4 dias  
**Objetivo:** Implementar F5-TTS engine completo (interface TTSEngine)

### 2.1. PRÉ-REQUISITOS

- [x] Sprint 1 completo (interface + factory)
- [ ] F5-TTS instalado: `pip install f5-tts`
- [ ] Whisper instalado: `pip install faster-whisper`
- [ ] CUDA disponível (ou CPU para testes)

### 2.2. TAREFAS

#### 2.2.1. RED - Escrever Testes (4-6 horas)

**Arquivo:** `tests/unit/engines/test_f5tts_engine.py` (NOVO)

```python
"""
Testes para F5TtsEngine
Red phase: Testes devem FALHAR (engine não existe)
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock, AsyncMock
from app.engines.f5tts_engine import F5TtsEngine
from app.engines.base import TTSEngine
from app.models import VoiceProfile, QualityProfile
from app.exceptions import TTSEngineException, InvalidAudioException


@pytest.fixture
def f5tts_engine():
    """Fixture para F5TtsEngine"""
    with patch('app.engines.f5tts_engine.F5TTS'):
        engine = F5TtsEngine(device='cpu')
        return engine


def test_f5tts_is_tts_engine(f5tts_engine):
    """F5TtsEngine implementa TTSEngine"""
    assert isinstance(f5tts_engine, TTSEngine)


def test_f5tts_engine_name(f5tts_engine):
    """Engine name é 'f5tts'"""
    assert f5tts_engine.engine_name == 'f5tts'


def test_f5tts_sample_rate(f5tts_engine):
    """Sample rate é 24kHz"""
    assert f5tts_engine.sample_rate == 24000


def test_f5tts_supported_languages(f5tts_engine):
    """Retorna linguagens suportadas"""
    langs = f5tts_engine.get_supported_languages()
    assert 'en' in langs
    assert 'pt' in langs
    assert 'pt-BR' in langs
    assert len(langs) >= 10  # Multilíngue


@pytest.mark.asyncio
async def test_f5tts_basic_synthesis(f5tts_engine):
    """Síntese básica sem voice cloning"""
    # Mock TTS.infer
    mock_audio = np.random.randn(24000 * 2)  # 2s audio
    f5tts_engine.tts.infer = MagicMock(return_value=mock_audio)
    
    audio_bytes, duration = await f5tts_engine.generate_dubbing(
        text="Hello world",
        language="en"
    )
    
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0
    assert duration > 0
    assert f5tts_engine.tts.infer.called


@pytest.mark.asyncio
async def test_f5tts_with_voice_cloning(f5tts_engine, tmp_path):
    """Síntese com voice cloning"""
    # Cria áudio fake
    ref_audio = tmp_path / "reference.wav"
    import soundfile as sf
    sf.write(ref_audio, np.random.randn(24000 * 5), 24000)
    
    # Cria VoiceProfile com ref_text
    profile = VoiceProfile(
        id='test',
        name='Test Voice',
        language='en',
        source_audio_path=str(ref_audio),
        profile_path=str(ref_audio),
        ref_text="This is reference text",
        created_at=...,
        expires_at=...
    )
    
    # Mock TTS.infer
    mock_audio = np.random.randn(24000 * 3)
    f5tts_engine.tts.infer = MagicMock(return_value=mock_audio)
    
    audio_bytes, duration = await f5tts_engine.generate_dubbing(
        text="Clone this voice",
        language="en",
        voice_profile=profile
    )
    
    assert len(audio_bytes) > 0
    # Verifica que ref_text foi passado
    call_args = f5tts_engine.tts.infer.call_args
    assert call_args[1]['ref_text'] == "This is reference text"


@pytest.mark.asyncio
async def test_f5tts_auto_transcribe_when_no_ref_text(f5tts_engine, tmp_path):
    """Auto-transcreve quando VoiceProfile.ref_text=None"""
    ref_audio = tmp_path / "reference.wav"
    import soundfile as sf
    sf.write(ref_audio, np.random.randn(24000 * 5), 24000)
    
    profile = VoiceProfile(
        id='test',
        name='Test',
        language='en',
        source_audio_path=str(ref_audio),
        profile_path=str(ref_audio),
        ref_text=None,  # Trigger auto-transcription
        ...
    )
    
    # Mock Whisper
    with patch.object(f5tts_engine, '_auto_transcribe', new_callable=AsyncMock) as mock_transcribe:
        mock_transcribe.return_value = "Auto transcribed text"
        
        # Mock TTS
        f5tts_engine.tts.infer = MagicMock(return_value=np.zeros(24000))
        
        await f5tts_engine.generate_dubbing(
            text="Test",
            language="en",
            voice_profile=profile
        )
        
        # Verifica que auto-transcrição foi chamada
        assert mock_transcribe.called
        assert mock_transcribe.call_args[0][0] == str(ref_audio)


@pytest.mark.asyncio
async def test_f5tts_quality_profile_mapping(f5tts_engine):
    """Quality profiles são mapeados para parâmetros F5-TTS"""
    # Balanced
    params = f5tts_engine._map_quality_profile(QualityProfile.BALANCED)
    assert params['nfe_step'] == 32
    assert params['cfg_strength'] == 2.0
    
    # Expressive
    params = f5tts_engine._map_quality_profile(QualityProfile.EXPRESSIVE)
    assert params['nfe_step'] == 50  # Higher quality
    assert params['cfg_strength'] > 2.0
    
    # Stable
    params = f5tts_engine._map_quality_profile(QualityProfile.STABLE)
    assert params['nfe_step'] == 16  # Faster


@pytest.mark.asyncio
async def test_f5tts_rvc_integration(f5tts_engine):
    """F5-TTS integra com RVC"""
    # Mock TTS
    f5tts_engine.tts.infer = MagicMock(return_value=np.zeros(24000))
    
    # Mock RVC
    f5tts_engine.rvc_client = MagicMock()
    f5tts_engine.rvc_client.convert_audio = AsyncMock(
        return_value=(np.zeros(24000), 1.0)
    )
    
    from app.models import RvcModel, RvcParameters
    rvc_model = RvcModel(id='test', name='Test RVC', ...)
    rvc_params = RvcParameters()
    
    audio_bytes, duration = await f5tts_engine.generate_dubbing(
        text="Test",
        language="en",
        enable_rvc=True,
        rvc_model=rvc_model,
        rvc_params=rvc_params
    )
    
    # RVC foi chamado
    assert f5tts_engine.rvc_client.convert_audio.called


@pytest.mark.asyncio
async def test_f5tts_clone_voice_with_ref_text(f5tts_engine, tmp_path):
    """clone_voice() cria VoiceProfile com ref_text"""
    ref_audio = tmp_path / "voice.wav"
    import soundfile as sf
    sf.write(ref_audio, np.random.randn(24000 * 5), 24000)
    
    profile = await f5tts_engine.clone_voice(
        audio_path=str(ref_audio),
        language="en",
        voice_name="Test Voice",
        ref_text="This is the reference text"
    )
    
    assert profile.ref_text == "This is the reference text"
    assert profile.name == "Test Voice"


@pytest.mark.asyncio
async def test_f5tts_clone_voice_auto_transcribe(f5tts_engine, tmp_path):
    """clone_voice() auto-transcreve quando ref_text=None"""
    ref_audio = tmp_path / "voice.wav"
    import soundfile as sf
    sf.write(ref_audio, np.random.randn(24000 * 5), 24000)
    
    with patch.object(f5tts_engine, '_auto_transcribe', new_callable=AsyncMock) as mock:
        mock.return_value = "Auto transcribed"
        
        profile = await f5tts_engine.clone_voice(
            audio_path=str(ref_audio),
            language="en",
            voice_name="Test",
            ref_text=None
        )
        
        assert mock.called
        assert profile.ref_text == "Auto transcribed"


@pytest.mark.asyncio
async def test_f5tts_invalid_audio_too_short(f5tts_engine, tmp_path):
    """Áudio muito curto levanta InvalidAudioException"""
    ref_audio = tmp_path / "short.wav"
    import soundfile as sf
    sf.write(ref_audio, np.random.randn(24000), 24000)  # 1s (mínimo 3s)
    
    with pytest.raises(InvalidAudioException, match="too short"):
        await f5tts_engine.clone_voice(
            audio_path=str(ref_audio),
            language="en",
            voice_name="Test"
        )


def test_f5tts_empty_text_error(f5tts_engine):
    """Texto vazio levanta ValueError"""
    with pytest.raises(ValueError, match="Empty text"):
        await f5tts_engine.generate_dubbing(text="", language="en")
```

**Executar testes (devem FALHAR):**
```bash
pytest tests/unit/engines/test_f5tts_engine.py -v

# Esperado: TODOS FALHAM (F5TtsEngine não existe)
```

#### 2.2.2. GREEN - Implementar F5TtsEngine (8-12 horas)

**Arquivo:** `app/engines/f5tts_engine.py` (NOVO - ~400 linhas)

```python
"""
F5-TTS Engine Implementation
Flow Matching Diffusion TTS for maximum expressiveness
"""
# Ver IMPLEMENTATION_F5TTS.md linhas 700-1100 para código completo
# Implementar conforme especificação
```

**Arquivo:** `requirements-f5tts.txt` (NOVO)

```txt
# F5-TTS dependencies
f5-tts>=1.1.9
faster-whisper>=0.10.0

# Already installed (verify versions)
torch>=2.0.0
torchaudio>=2.0.0
soundfile>=0.12.0
numpy>=1.24.0
```

**Instalar dependências:**
```bash
pip install -r requirements-f5tts.txt
```

**Executar testes (devem PASSAR):**
```bash
pytest tests/unit/engines/test_f5tts_engine.py -v

# Esperado: TODOS PASSAM (GREEN)
```

#### 2.2.3. REFACTOR - Melhorar Código (2-3 horas)

- [ ] Adicionar logging detalhado
- [ ] Otimizar auto-transcription (cache)
- [ ] Melhorar error handling
- [ ] Adicionar validações de input
- [ ] Documentação completa

### 2.3. CRITÉRIOS DE ACEITAÇÃO

- [ ] F5TtsEngine implementa interface TTSEngine
- [ ] `generate_dubbing()` funciona com/sem voice cloning
- [ ] `clone_voice()` cria VoiceProfile com ref_text
- [ ] Auto-transcription com Whisper (fallback)
- [ ] Quality profiles mapeados
- [ ] RVC integration funcional
- [ ] Todos os testes GREEN (100%)
- [ ] Coverage ≥85% em `f5tts_engine.py`

### 2.4. ENTREGÁVEIS

```
app/engines/
└── f5tts_engine.py      (NOVO - ~400 linhas)

tests/unit/engines/
└── test_f5tts_engine.py (NOVO - ~250 linhas)

requirements-f5tts.txt   (NOVO - 10 linhas)
```

### 2.5. RISCOS

| Risco | Mitigação |
|-------|-----------|
| F5-TTS não instalável | Testar em ambiente limpo primeiro |
| Whisper muito lento | Usar modelo "base" (rápido) |
| VRAM insuficiente | Fallback para CPU automático |

---

## ♻️ SPRINT 3: Refatoração XttsEngine

**Duração:** 2 dias  
**Objetivo:** Refatorar `xtts_client.py` → `engines/xtts_engine.py`

### 3.1. PRÉ-REQUISITOS

- [x] Sprint 1 completo (interface)
- [x] Sprint 2 completo (F5-TTS)

### 3.2. TAREFAS

#### 3.2.1. RED - Adaptar Testes Existentes (2-3 horas)

**Copiar e adaptar testes:**
```bash
# Copiar testes existentes
cp tests/unit/test_xtts_client_init.py tests/unit/engines/test_xtts_engine_init.py
cp tests/unit/test_xtts_client_dubbing.py tests/unit/engines/test_xtts_engine_dubbing.py
```

**Modificar imports:**
```python
# ANTES:
from app.xtts_client import XTTSClient

# DEPOIS:
from app.engines.xtts_engine import XttsEngine
from app.engines.base import TTSEngine
```

**Adicionar teste de interface:**
```python
def test_xtts_is_tts_engine():
    """XttsEngine implementa TTSEngine"""
    engine = XttsEngine(device='cpu')
    assert isinstance(engine, TTSEngine)
    assert engine.engine_name == 'xtts'
```

**Executar testes (devem FALHAR):**
```bash
pytest tests/unit/engines/test_xtts_engine_*.py -v

# Esperado: FALHAM (XttsEngine não existe)
```

#### 3.2.2. GREEN - Refatorar XTTS Client (4-6 horas)

**Arquivo:** `app/engines/xtts_engine.py` (NOVO)

```python
"""
XTTS v2 Engine Implementation
Refactored from xtts_client.py to implement TTSEngine interface
"""
from .base import TTSEngine

# COPIAR código completo de app/xtts_client.py
# MUDANÇAS:
# 1. Renomear: XTTSClient → XttsEngine
# 2. Herdar de TTSEngine
# 3. Adicionar @property engine_name → return 'xtts'
# 4. Adaptar clone_voice() para aceitar ref_text (ignorar para XTTS)
# 5. Manter TODO código existente (RVC, resilience, etc.)

class XttsEngine(TTSEngine):
    """XTTS v2 TTS engine implementation"""
    
    @property
    def engine_name(self) -> str:
        return 'xtts'
    
    @property
    def sample_rate(self) -> int:
        return 24000
    
    # ... resto do código de xtts_client.py (404 linhas)
    # Ver PHASE-1-XTTS-ANALYSIS.md para código completo
```

**Marcar xtts_client.py como deprecated:**
```python
# app/xtts_client.py
"""
DEPRECATED: Use app.engines.xtts_engine.XttsEngine instead
This module is kept for backward compatibility only
"""
import warnings
from .engines.xtts_engine import XttsEngine

warnings.warn(
    "xtts_client.XTTSClient is deprecated, use engines.xtts_engine.XttsEngine",
    DeprecationWarning,
    stacklevel=2
)

# Alias para backward compatibility
XTTSClient = XttsEngine
```

**Executar testes (devem PASSAR):**
```bash
pytest tests/unit/engines/test_xtts_engine_*.py -v

# Esperado: TODOS PASSAM (GREEN)
```

#### 3.2.3. REFACTOR - Limpar Código (2 horas)

- [ ] Remover duplicações
- [ ] Melhorar logging
- [ ] Atualizar docstrings
- [ ] Verificar type hints

### 3.3. CRITÉRIOS DE ACEITAÇÃO

- [ ] XttsEngine implementa interface TTSEngine
- [ ] Backward compatibility mantida (XTTSClient = XttsEngine)
- [ ] Todos os testes existentes ainda PASSAM
- [ ] Novos testes de interface PASSAM
- [ ] Coverage mantido (≥90%)
- [ ] Deprecation warning adicionado

### 3.4. ENTREGÁVEIS

```
app/engines/
└── xtts_engine.py       (NOVO - ~420 linhas)

app/xtts_client.py       (MODIFICADO - deprecated)

tests/unit/engines/
├── test_xtts_engine_init.py    (NOVO - copiado)
└── test_xtts_engine_dubbing.py (NOVO - copiado)
```

---

## 🔗 SPRINT 4: Integração Processor + API

**Duração:** 2-3 dias  
**Objetivo:** Integrar factory pattern em processor.py e main.py

### 4.1. TAREFAS

#### 4.1.1. RED - Testes de Integração (3-4 horas)

**Arquivo:** `tests/integration/test_processor_multi_engine.py` (NOVO)

```python
"""
Testes de integração: VoiceProcessor com multi-engine
"""
import pytest
from app.processor import VoiceProcessor
from app.models import Job, JobMode, JobStatus, QualityProfile


@pytest.mark.asyncio
async def test_processor_uses_xtts_by_default(settings):
    """Processor usa XTTS quando job.tts_engine=None"""
    settings['tts_engine_default'] = 'xtts'
    processor = VoiceProcessor(lazy_load=False)
    processor.job_store = MagicMock()
    
    job = Job(
        id='test',
        mode=JobMode.DUBBING,
        status=JobStatus.QUEUED,
        text="Test",
        source_language="en",
        quality_profile=QualityProfile.BALANCED,
        tts_engine=None,  # Usa default
    )
    
    # Mock engine.generate_dubbing
    with patch.object(processor.engine, 'generate_dubbing', new_callable=AsyncMock) as mock:
        mock.return_value = (b'audio', 1.0)
        
        await processor.process_dubbing_job(job)
        
        assert job.tts_engine_used == 'xtts'
        assert mock.called


@pytest.mark.asyncio
async def test_processor_uses_f5tts_when_specified(settings):
    """Processor usa F5-TTS quando job.tts_engine='f5tts'"""
    processor = VoiceProcessor(lazy_load=False)
    processor.job_store = MagicMock()
    
    job = Job(
        id='test',
        mode=JobMode.DUBBING,
        tts_engine='f5tts',  # Override
        text="Test",
        source_language="en",
        ...
    )
    
    with patch('app.engines.factory.create_engine_with_fallback') as mock_factory:
        mock_factory.return_value.generate_dubbing = AsyncMock(return_value=(b'', 1.0))
        mock_factory.return_value.engine_name = 'f5tts'
        
        await processor.process_dubbing_job(job)
        
        # Factory foi chamado com 'f5tts'
        assert mock_factory.call_args[0][0] == 'f5tts'
        assert job.tts_engine_used == 'f5tts'


@pytest.mark.asyncio
async def test_processor_fallback_to_xtts_on_f5tts_error(settings):
    """Processor faz fallback para XTTS quando F5-TTS falha"""
    processor = VoiceProcessor(lazy_load=False)
    
    job = Job(tts_engine='f5tts', ...)
    
    with patch('app.engines.factory.create_engine_with_fallback') as mock_factory:
        # Simula F5-TTS falha, fallback para XTTS
        xtts_engine = MagicMock()
        xtts_engine.engine_name = 'xtts'
        xtts_engine.generate_dubbing = AsyncMock(return_value=(b'', 1.0))
        mock_factory.return_value = xtts_engine
        
        await processor.process_dubbing_job(job)
        
        # Fallback para XTTS
        assert job.tts_engine_used == 'xtts'
```

**Arquivo:** `tests/integration/test_api_multi_engine.py` (NOVO)

```python
"""
Testes de integração: API com multi-engine
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_create_job_with_default_engine(client: TestClient):
    """POST /jobs sem tts_engine usa default"""
    response = client.post(
        "/jobs",
        data={
            "text": "Test",
            "source_language": "en",
            "mode": "dubbing",
            "quality_profile": "balanced",
            # tts_engine: não fornecido (usa default)
        }
    )
    
    assert response.status_code == 200
    job = response.json()
    assert job['tts_engine'] is None  # Não override


def test_create_job_with_xtts_override(client: TestClient):
    """POST /jobs com tts_engine='xtts'"""
    response = client.post(
        "/jobs",
        data={
            "text": "Test",
            "source_language": "en",
            "mode": "dubbing",
            "tts_engine": "xtts",  # Override
        }
    )
    
    assert response.status_code == 200
    job = response.json()
    assert job['tts_engine'] == 'xtts'


def test_create_job_with_f5tts_override(client: TestClient):
    """POST /jobs com tts_engine='f5tts'"""
    response = client.post(
        "/jobs",
        data={
            "text": "Test",
            "source_language": "en",
            "mode": "dubbing",
            "tts_engine": "f5tts",
        }
    )
    
    assert response.status_code == 200
    job = response.json()
    assert job['tts_engine'] == 'f5tts'


def test_create_job_with_invalid_engine(client: TestClient):
    """POST /jobs com tts_engine inválido retorna 400"""
    response = client.post(
        "/jobs",
        data={
            "text": "Test",
            "source_language": "en",
            "mode": "dubbing",
            "tts_engine": "invalid_engine",
        }
    )
    
    assert response.status_code == 400
    assert "Invalid tts_engine" in response.json()['detail']


def test_clone_voice_with_ref_text(client: TestClient, tmp_path):
    """POST /voices/clone com ref_text"""
    audio_file = tmp_path / "voice.wav"
    # Cria áudio fake
    import soundfile as sf
    sf.write(audio_file, np.random.randn(24000 * 5), 24000)
    
    with open(audio_file, 'rb') as f:
        response = client.post(
            "/voices/clone",
            data={
                "voice_name": "Test Voice",
                "language": "en",
                "ref_text": "This is the reference text",  # NOVO
            },
            files={"audio_file": f}
        )
    
    assert response.status_code == 200
    profile = response.json()
    assert profile['ref_text'] == "This is the reference text"
```

**Executar testes (devem FALHAR):**
```bash
pytest tests/integration/test_processor_multi_engine.py -v
pytest tests/integration/test_api_multi_engine.py -v

# Esperado: FALHAM (modificações não feitas)
```

#### 4.1.2. GREEN - Modificar processor.py e main.py (4-6 horas)

**Ver IMPLEMENTATION_F5TTS.md Parte 3 (linhas 1100-1300) para código completo**

Modificações principais:
1. `processor.py`: Usar factory em `_load_engine()`
2. `processor.py`: Adicionar `engine_type` parameter
3. `processor.py`: Setar `job.tts_engine_used`
4. `main.py`: Adicionar `tts_engine` param em `/jobs`
5. `main.py`: Adicionar `ref_text` param em `/voices/clone`
6. `config.py`: Adicionar seção `tts_engines`
7. `models.py`: Adicionar campos `tts_engine`, `tts_engine_used`, `ref_text`

**Executar testes (devem PASSAR):**
```bash
pytest tests/integration/test_processor_multi_engine.py -v
pytest tests/integration/test_api_multi_engine.py -v

# Esperado: TODOS PASSAM (GREEN)
```

#### 4.1.3. REFACTOR - Melhorar Integração (2 horas)

- [ ] Adicionar validação de engine_type
- [ ] Melhorar logging de audit trail
- [ ] Documentar novos parâmetros API
- [ ] Atualizar OpenAPI schema

### 4.3. CRITÉRIOS DE ACEITAÇÃO

- [ ] `processor.py` usa factory pattern
- [ ] `main.py` aceita `tts_engine` parameter
- [ ] `main.py` aceita `ref_text` em clone
- [ ] `config.py` tem seção `tts_engines`
- [ ] `models.py` tem novos campos
- [ ] Todos os testes integration PASSAM
- [ ] API backward compatible (parâmetros opcionais)

### 4.4. ENTREGÁVEIS

```
app/processor.py     (MODIFICADO - ~250 linhas)
app/main.py          (MODIFICADO - ~1050 linhas)
app/config.py        (MODIFICADO - ~260 linhas)
app/models.py        (MODIFICADO - ~470 linhas)

tests/integration/
├── test_processor_multi_engine.py (NOVO - 100 linhas)
└── test_api_multi_engine.py       (NOVO - 120 linhas)
```

---

## ✅ SPRINT 5-10: Resumo

**(Detalhamento completo omitido por brevidade - seguir mesmo padrão TDD)**

### Sprint 5: Testes Unitários Completos (3 dias)
- Coverage ≥90% em todos engines
- Testes de edge cases
- Testes de error handling

### Sprint 6: Testes de Integração (2 dias)
- Engine switching
- Fallback scenarios
- RVC com ambos engines

### Sprint 7: Testes E2E (2 dias)
- Pipeline completo XTTS + RVC
- Pipeline completo F5-TTS + RVC
- Multi-engine em paralelo

### Sprint 8: Benchmarks PT-BR (2 dias)
- Qualidade F5-TTS vs XTTS em PT-BR
- Performance comparison
- VRAM usage comparison

### Sprint 9: Documentação Final (1 dia)
- README atualizado
- API docs
- Migration guide

### Sprint 10: Deploy Gradual (2 semanas)
- Alpha: 5% tráfego F5-TTS
- Beta: 25% tráfego
- GA: 100% disponível (opt-in)

---

## 🛠️ COMANDOS ÚTEIS

```bash
# Criar branch
git checkout -b feature/f5tts-multi-engine

# Instalar dependências
pip install -r requirements-f5tts.txt

# Rodar testes
pytest -v                                    # Todos
pytest tests/unit/engines/ -v               # Engines only
pytest tests/integration/ -v                # Integration
pytest -m "not slow" -v                     # Skip slow tests

# Coverage
pytest --cov=app/engines --cov-report=html

# Code quality
ruff check app/
mypy app/
black app/

# Deploy
docker-compose -f docker-compose-gpu.yml up --build
```

---

## ✅ CHECKLIST GERAL

### Fase 1: Fundação
- [ ] Sprint 1: Interface + Factory (2-3 dias)
- [ ] Sprint 2: F5TtsEngine (3-4 dias)
- [ ] Sprint 3: XttsEngine Refactor (2 dias)

### Fase 2: Integração
- [ ] Sprint 4: Processor + API (2-3 dias)
- [ ] Sprint 5: Unit Tests (3 dias)

### Fase 3: Validação
- [ ] Sprint 6: Integration Tests (2 dias)
- [ ] Sprint 7: E2E Tests (2 dias)
- [ ] Sprint 8: PT-BR Benchmarks (2 dias)

### Fase 4: Finalização
- [ ] Sprint 9: Documentation (1 dia)
- [ ] Sprint 10: Gradual Rollout (2 semanas)

### Quality Gates
- [ ] Coverage ≥90% em engines
- [ ] Coverage ≥80% em integration
- [ ] Zero breaking changes na API
- [ ] Backward compatibility 100%
- [ ] Performance degradation <10%
- [ ] PT-BR quality validated

---

**Status:** ✅ **SPRINTS-F5TTS.MD - COMPLETO**  
**Próximo:** Executar Sprint 1

---

_Documento gerado por Engenheiro(a) Sênior de Áudio e Backend_  
_Data: 27 de Novembro de 2025_  
_Versão: 1.0_
