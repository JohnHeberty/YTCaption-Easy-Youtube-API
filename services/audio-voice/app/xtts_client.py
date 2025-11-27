"""
DEPRECATED: xtts_client.py - Use app.engines.xtts_engine.XttsEngine instead

This module is DEPRECATED and maintained only for backward compatibility.
It will be removed in a future version.

For new code, use:
    from app.engines import XttsEngine
    
Sprint: 3 - XTTS Refactoring
Status: DEPRECATED (backward compatibility alias)
"""
import warnings

# Issue deprecation warning
warnings.warn(
    "xtts_client.XTTSClient is deprecated. Use app.engines.xtts_engine.XttsEngine instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import new implementation and create backward compatibility alias
from .engines.xtts_engine import XttsEngine

# Backward compatibility alias
XTTSClient = XttsEngine

__all__ = ['XTTSClient']
