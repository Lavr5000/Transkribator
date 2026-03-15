"""Shared pymorphy2 MorphAnalyzer singleton.

Provides a single MorphAnalyzer instance shared across phonetics.py and morphology.py,
saving ~50MB RAM and ~1.5s startup time.
"""

try:
    import pymorphy2
    PYMORPHY2_AVAILABLE = True
except ImportError:
    PYMORPHY2_AVAILABLE = False
    print("[WARNING] pymorphy2 not installed. Install with: pip install pymorphy2")

_morph_instance = None


def get_morph():
    """Get or create the shared MorphAnalyzer instance.

    Returns:
        pymorphy2.MorphAnalyzer instance, or None if pymorphy2 is not installed.
    """
    global _morph_instance
    if PYMORPHY2_AVAILABLE and _morph_instance is None:
        _morph_instance = pymorphy2.MorphAnalyzer()
    return _morph_instance
