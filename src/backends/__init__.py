"""Speech recognition backend for GolosText.

Since 2.4.0 there is exactly one: SherpaBackend (Sherpa-ONNX with GigaAM
models, tuned for Russian). The three engines removed in 2.4.0 — two local
ones that were never once selected in production, and the cloud one retired
on 2026-08-24 after 24 timeouts — are gone from the product path and live in
the git history at tag `cleanup-base-2026-09-02`.

The import stays lazy so importing this package does not pull sherpa_onnx.
"""
import importlib
import importlib.util

from .base import BaseBackend

__all__ = [
    "BaseBackend",
    "SherpaBackend",
    "BACKENDS",
    "get_backend",
    "backend_available",
]

# Backend registry: name -> (submodule, class name, core import the backend needs)
BACKENDS = {
    "sherpa": ("sherpa_backend", "SherpaBackend", "sherpa_onnx"),
}

_CLASS_TO_NAME = {cls: name for name, (_, cls, _) in BACKENDS.items()}


def get_backend(backend_name: str) -> type:
    """Get backend class by name (imports the backend module on demand).

    Raises:
        ValueError: If backend is not found
    """
    if backend_name not in BACKENDS:
        raise ValueError(
            f"Unknown backend: {backend_name}. "
            f"Available backends: {', '.join(BACKENDS.keys())}"
        )
    module_name, class_name, _ = BACKENDS[backend_name]
    module = importlib.import_module(f".{module_name}", __name__)
    return getattr(module, class_name)


def backend_available(backend_name: str) -> bool:
    """True when the backend's core dependency is importable."""
    if backend_name not in BACKENDS:
        return False
    dep = BACKENDS[backend_name][2]
    try:
        return importlib.util.find_spec(dep) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def __getattr__(name):  # PEP 562 — keep `from src.backends import SherpaBackend` working
    if name in _CLASS_TO_NAME:
        return get_backend(_CLASS_TO_NAME[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
