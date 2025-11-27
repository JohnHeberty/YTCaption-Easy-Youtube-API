"""
Base interface for TTS engines
All engines must implement this interface

This module defines the abstract base class that all TTS engines must inherit from.
It ensures a consistent API across different TTS implementations (XTTS, F5-TTS, etc.)

Example:
    >>> class MyEngine(TTSEngine):
    ...     @property
    ...     def engine_name(self) -> str:
    ...         return 'my_engine'
    ...     
    ...     async def generate_dubbing(self, text, language, **kwargs):
    ...         # Implementation here
    ...         return audio_bytes, duration

Author: Audio Voice Service Team
Date: November 27, 2025
Sprint: 1 - Multi-Engine Foundation
"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional, List
import logging

from ..models import VoiceProfile, QualityProfile

logger = logging.getLogger(__name__)


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
        ...
    
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
        ...
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List[str]: Language codes (e.g. ['en', 'pt', 'pt-BR'])
        """
        ...
    
    @property
    @abstractmethod
    def engine_name(self) -> str:
        """
        Engine identifier.
        
        Returns:
            str: Engine name ('xtts', 'f5tts', etc.)
        """
        ...
    
    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """
        Output sample rate.
        
        Returns:
            int: Sample rate in Hz (e.g. 24000)
        """
        ...
