"""
Audio Normalization Service Package
"""
from __future__ import annotations
from typing import Any

# Lazy import to avoid circular dependencies
def get_app() -> Any:
    from .main import app
    return app

__all__ = ['get_app']
