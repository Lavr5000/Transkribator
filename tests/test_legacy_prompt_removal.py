"""Legacy prompt removal (Этап 0, r1-13): the leaked "Диктовка..." phrase
must be gone by default and only restorable via legacy_prompt_removed=False."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backends import groq_backend as groq_backend_mod
from src.backends.groq_backend import GroqBackend

LEGACY_PHRASE = "Диктовка на русском языке."


def _make_backend_with_fake_client(legacy_prompt_removed):
    groq_backend_mod._last_failure_mono = 0.0  # module-level cooldown state — reset for isolation
    backend = GroqBackend(legacy_prompt_removed=legacy_prompt_removed)
    fake_client = MagicMock()
    fake_client.audio.transcriptions.create.return_value = MagicMock(text="привет")
    backend._client = fake_client
    return backend, fake_client


def test_default_omits_legacy_prompt():
    backend, fake_client = _make_backend_with_fake_client(legacy_prompt_removed=True)
    import numpy as np
    backend.transcribe(np.zeros(1600, dtype=np.float32), sample_rate=16000)
    _, kwargs = fake_client.audio.transcriptions.create.call_args
    assert kwargs["prompt"] is None
    assert backend.last_prompt_sent is None


def test_flag_off_restores_legacy_prompt():
    backend, fake_client = _make_backend_with_fake_client(legacy_prompt_removed=False)
    import numpy as np
    backend.transcribe(np.zeros(1600, dtype=np.float32), sample_rate=16000)
    _, kwargs = fake_client.audio.transcriptions.create.call_args
    assert kwargs["prompt"] == LEGACY_PHRASE
    assert backend.last_prompt_sent == LEGACY_PHRASE
