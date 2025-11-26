"""
Validators module - Validação robusta de inputs para F5-TTS
"""
import re
import logging
from pathlib import Path
from typing import Optional
import soundfile as sf

from .exceptions import InvalidAudioException
from .models import VoiceProfile

logger = logging.getLogger(__name__)


def normalize_text_ptbr(text: str) -> str:
    """
    Normaliza texto para F5-TTS pt-BR com validação robusta.
    
    Requirements (HuggingFace firstpixel/F5-TTS-pt-br):
    - Lowercase
    - Números convertidos para palavras
    - Apenas caracteres do vocabulário (2545 tokens)
    
    Args:
        text: Texto a normalizar
        
    Returns:
        Texto normalizado pronto para F5-TTS
        
    Raises:
        ValueError: Se texto inválido
    """
    if not text or not isinstance(text, str):
        raise ValueError("Text must be non-empty string")
    
    text = text.strip()
    if not text:
        raise ValueError("Text cannot be empty after strip")
    
    # Lowercase (pt-BR requirement)
    text = text.lower()
    
    # Converter números para palavras (HuggingFace requirement)
    try:
        from num2words import num2words
        
        def replace_number(match):
            try:
                num_str = match.group()
                # Converter para palavras em português
                words = num2words(int(num_str), lang='pt_BR')
                return words
            except Exception as e:
                logger.warning(f"Failed to convert number '{num_str}': {e}")
                return num_str  # fallback: manter número original
        
        text = re.sub(r'\d+', replace_number, text)
    except ImportError:
        logger.warning("num2words not installed, skipping number conversion")
    except Exception as e:
        logger.warning(f"Number conversion failed: {e}, continuing...")
    
    # Remover caracteres não-suportados (vocab pt-BR: a-z, acentos, pontuação básica)
    text = re.sub(r'[^\w\s\.\,\!\?\-àáâãçéêíóôõú]', '', text)
    
    # Remover espaços múltiplos
    text = re.sub(r'\s+', ' ', text).strip()
    
    if not text:
        raise ValueError("Text is empty after normalization")
    
    return text


def validate_audio_path(path: str, min_duration: float = 1.0, max_duration: float = 60.0) -> None:
    """
    Valida áudio de referência com checks robustos.
    
    Args:
        path: Caminho do arquivo de áudio
        min_duration: Duração mínima em segundos
        max_duration: Duração máxima em segundos
        
    Raises:
        InvalidAudioException: Se áudio inválido
    """
    if not path or not isinstance(path, str):
        raise InvalidAudioException("Audio path must be non-empty string")
    
    audio_path = Path(path)
    
    if not audio_path.exists():
        raise InvalidAudioException(f"Audio file not found: {path}")
    
    if not audio_path.is_file():
        raise InvalidAudioException(f"Path is not a file: {path}")
    
    file_size = audio_path.stat().st_size
    if file_size == 0:
        raise InvalidAudioException(f"Audio file is empty: {path}")
    
    # Validar formato e duração
    try:
        info = sf.info(str(audio_path))
        
        if info.duration < min_duration:
            raise InvalidAudioException(
                f"Audio too short: {info.duration:.1f}s < {min_duration}s"
            )
        
        if info.duration > max_duration:
            logger.warning(
                f"Audio very long: {info.duration:.1f}s > {max_duration}s, "
                f"consider trimming for better quality"
            )
        
        # Validar sample rate
        if info.samplerate < 16000:
            logger.warning(
                f"Low sample rate: {info.samplerate} Hz, "
                f"F5-TTS works best with 24kHz+"
            )
        
    except Exception as e:
        raise InvalidAudioException(f"Invalid audio file '{path}': {e}") from e


def validate_voice_profile(profile: Optional[VoiceProfile]) -> None:
    """
    Valida VoiceProfile antes de usar em TTS.
    
    Args:
        profile: VoiceProfile a validar
        
    Raises:
        InvalidAudioException: Se profile inválido
    """
    if not profile:
        raise InvalidAudioException("VoiceProfile is required")
    
    if not profile.reference_audio_path:
        raise InvalidAudioException(
            f"VoiceProfile {profile.id} missing reference_audio_path"
        )
    
    # Validar arquivo de áudio
    validate_audio_path(profile.reference_audio_path, min_duration=1.0, max_duration=15.0)
    
    # Validar reference_text
    if not profile.reference_text:
        logger.warning(
            f"VoiceProfile {profile.id} missing reference_text, "
            f"will use fallback during inference"
        )
    elif not isinstance(profile.reference_text, str):
        raise InvalidAudioException(
            f"reference_text must be string, got {type(profile.reference_text)}"
        )
    elif len(profile.reference_text.strip()) < 3:
        logger.warning(
            f"VoiceProfile {profile.id} has very short reference_text "
            f"({len(profile.reference_text)} chars), quality may be affected"
        )


def validate_inference_params(
    text: str,
    speed: float = 1.0,
    nfe_step: int = 16
) -> None:
    """
    Valida parâmetros de inferência.
    
    Args:
        text: Texto a sintetizar
        speed: Velocidade (0.5-2.0 recomendado)
        nfe_step: NFE steps (8-32 recomendado)
        
    Raises:
        ValueError: Se parâmetros inválidos
    """
    # Validar texto
    if not text or not isinstance(text, str):
        raise ValueError("Text must be non-empty string")
    
    if len(text.strip()) < 3:
        raise ValueError(f"Text too short: {len(text)} chars")
    
    if len(text) > 5000:
        logger.warning(
            f"Very long text ({len(text)} chars), "
            f"consider splitting for better quality"
        )
    
    # Validar speed
    if not isinstance(speed, (int, float)):
        raise ValueError(f"Speed must be numeric, got {type(speed)}")
    
    if speed <= 0 or speed > 3.0:
        raise ValueError(f"Speed out of range: {speed} (valid: 0.1-3.0)")
    
    if speed < 0.5 or speed > 2.0:
        logger.warning(
            f"Speed {speed} outside optimal range (0.5-2.0), "
            f"quality may be affected"
        )
    
    # Validar NFE steps
    if not isinstance(nfe_step, int):
        raise ValueError(f"nfe_step must be int, got {type(nfe_step)}")
    
    if nfe_step < 4 or nfe_step > 64:
        raise ValueError(f"nfe_step out of range: {nfe_step} (valid: 4-64)")
    
    if nfe_step < 8:
        logger.warning(
            f"Very low NFE steps ({nfe_step}), "
            f"quality will be poor. Recommended: 16-32"
        )
