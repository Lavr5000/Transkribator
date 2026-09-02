"""Developer credential loading — environment-first, no hardcoded paths.

All lookups check os.environ first. Optionally, the TRANSKRIBATOR_KEYSTORE
environment variable may point to a directory containing a ``.env`` file
(``NAME=value`` lines). Without that variable nothing is read from disk, so
a clean install never touches machine-specific paths.

The only consumer is main.py, which injects HF_TOKEN so a SOURCE install can
download models from HuggingFace. The released build ships the model, so this
path never runs there.
"""
import os
from pathlib import Path
from typing import Optional


def keystore_dir() -> Optional[Path]:
    """Directory with dev credentials, or None when not configured."""
    p = os.environ.get("TRANSKRIBATOR_KEYSTORE")
    return Path(p) if p else None


def load_env_var(name: str) -> Optional[str]:
    """Return env var value; on miss, try KEYSTORE/.env (best-effort)."""
    val = os.environ.get(name)
    if val:
        return val
    ks = keystore_dir()
    if ks:
        env_file = ks / ".env"
        try:
            if env_file.exists():
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith(f"{name}="):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            os.environ[name] = val
                            return val
        except OSError:
            pass
    return None

