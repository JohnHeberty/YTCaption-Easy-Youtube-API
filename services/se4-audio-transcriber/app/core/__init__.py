"""Core configuration and constants."""
from __future__ import annotations

from .config import CoreSettings, get_core, get_settings, get_supported_languages, is_language_supported, get_whisper_models
from .logging_config import setup_logging

__all__ = [
    "CoreSettings",
    "get_core",
    "get_settings",
    "get_supported_languages",
    "is_language_supported",
    "get_whisper_models",
    "setup_logging",
]
