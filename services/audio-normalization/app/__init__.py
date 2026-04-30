"""
Audio Normalization Service Package
"""

# Lazy import to avoid circular dependencies
def get_app():
    from .main import app
    return app

__all__ = ['get_app']
