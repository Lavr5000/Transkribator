"""Shared pymorphy MorphAnalyzer singleton.

Provides a single MorphAnalyzer instance shared across phonetics.py and
morphology.py, saving ~50MB RAM and ~1.5s startup time.

Tries pymorphy2 first, then pymorphy3 (API-compatible fork maintained for
Python 3.11+). The fallback happens at CONSTRUCTION time, not import time:
on modern Python pymorphy2 can import fine and still fail inside
MorphAnalyzer() (it uses long-removed inspect.getargspec).
"""

import logging

logger = logging.getLogger("transkribator")

_morph_instance = None
_morph_failed = False


def get_morph():
    """Get or create the shared MorphAnalyzer instance.

    Returns:
        MorphAnalyzer instance (pymorphy2 or pymorphy3), or None if neither
        library is installed/working.
    """
    global _morph_instance, _morph_failed
    if _morph_instance is not None or _morph_failed:
        return _morph_instance

    for module_name in ("pymorphy2", "pymorphy3"):
        try:
            module = __import__(module_name)
            _morph_instance = module.MorphAnalyzer()
            logger.info("MORPH_READY | analyzer=%s", module_name)
            return _morph_instance
        except Exception as e:
            logger.warning("MORPH_INIT_FAILED | module=%s | %s", module_name, e)

    _morph_failed = True
    logger.warning(
        "MORPH_UNAVAILABLE | phonetics/morphology corrections disabled. "
        "Install with: pip install pymorphy3"
    )
    return None
