from __future__ import annotations

"""
Portuguese (PT-BR) text normalizer for TTS pronunciation improvement.

The Chatterbox TTS model has a BPE vocabulary heavily biased toward English.
Portuguese accented characters (ç, ã, é, ó, etc.) are always tokenized as
individual unigram tokens without subword context, causing incorrect pronunciation.

This normalizer converts accented characters to their phonetic equivalents
before the text reaches the Chatterbox model, improving pronunciation accuracy.

Usage:
    from app.services.pt_br_normalizer import normalize_pt_br
    normalized = normalize_pt_br("você não sabe o que é um lição")
    # → "voce nao sabe o que e um licom"
"""

import re
from common.log_utils import get_logger

logger = get_logger(__name__)

# Character-level mapping: accented char → base letter (remove diacritics)
# Tildes: ã→a, õ→o (remove nasal marker — Chatterbox handles pronunciation)
# C-cedilla: ç→c (most common issue)
# Everything else: just strip the accent mark
_CHAR_MAP: dict[str, str] = {
    # C-cedilla
    'ç': 'c', 'Ç': 'C',
    # Tildes
    'ã': 'a', 'Ã': 'A',
    'õ': 'o', 'Õ': 'O',
    # Acutes
    'á': 'a', 'Á': 'A',
    'é': 'e', 'É': 'E',
    'í': 'i', 'Í': 'I',
    'ó': 'o', 'Ó': 'O',
    'ú': 'u', 'Ú': 'U',
    # Circumflex
    'â': 'a', 'Â': 'A',
    'ê': 'e', 'Ê': 'E',
    'î': 'i', 'Î': 'I',
    'ô': 'o', 'Ô': 'O',
    'û': 'u', 'Û': 'U',
    # Grave
    'à': 'a', 'À': 'A',
    # Umlaut
    'ü': 'u', 'Ü': 'U',
}

# Build translation table
_TRANS_TABLE = str.maketrans(_CHAR_MAP)


def normalize_pt_br(text: str) -> str:
    """Normalize PT-BR text for improved TTS pronunciation.

    Converts accented characters to phonetic equivalents to work around
    Chatterbox BPE tokenizer limitations with Portuguese diacritics.

    Args:
        text: Input text with Portuguese accented characters.

    Returns:
        Normalized text with phonetic equivalents.
    """
    if not text:
        return text

    normalized = text.translate(_TRANS_TABLE)

    if normalized != text:
        logger.debug("Text normalized: '%s' → '%s'", text[:50], normalized[:50])

    return normalized
