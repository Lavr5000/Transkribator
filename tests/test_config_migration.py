"""Config migration 2.3 -> 2.4 (A3).

Two things must hold for an owner upgrading in place:

1. A stored config full of fields whose code no longer exists must NOT reset
   the whole file. Before this migration `Config(**data)` raised TypeError on
   the first unknown key and silently fell back to defaults — losing the
   hotkey, the mouse button and the lifetime counters (961 087 words).
2. The migration touches no hardware. It runs on every start, in headless CI
   and here, where `sounddevice` is not importable at all.
"""

import builtins
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import CONFIG_VERSION, Config

# A realistic 2.3 config: cloud backend, cloud model, remote flag, Telegram
# credentials, a PortAudio device index, and the owner's real settings.
LEGACY = {
    "backend": "groq",
    "model_size": "whisper-large-v3-turbo",
    "enable_remote_fallback": True,
    "telegram_api_id": "123456",
    "telegram_api_hash": "deadbeef",
    "telegram_chat_id": "-1001234567890",
    "audio_device": 3,
    "hotkey": "ctrl+alt+z",
    "mouse_button": "x1",
    "enable_mouse_button": True,
    "total_words": 961087,
    "total_recordings": 16548,
    "total_seconds_saved": 1234.5,
    "quality_profile": "quality",
}


def test_legacy_config_keeps_the_owner_settings():
    cfg = Config(**Config.migrate(dict(LEGACY)))

    assert cfg.hotkey == "ctrl+alt+z"
    assert cfg.mouse_button == "x1" and cfg.enable_mouse_button is True
    assert cfg.total_words == 961087
    assert cfg.total_recordings == 16548
    assert cfg.total_seconds_saved == 1234.5
    assert cfg.quality_profile == "quality"


def test_legacy_config_lands_on_the_only_backend():
    cfg = Config(**Config.migrate(dict(LEGACY)))
    assert cfg.backend == "sherpa"
    assert cfg.model_size == "giga-am-v3-ru-punct"
    assert cfg.config_version == CONFIG_VERSION


def test_removed_fields_are_dropped_and_device_index_is_renamed():
    data = Config.migrate(dict(LEGACY))
    for gone in ("enable_remote_fallback", "telegram_api_id", "telegram_api_hash",
                 "telegram_chat_id", "audio_device"):
        assert gone not in data, gone

    cfg = Config(**data)
    assert cfg.audio_device_legacy_index == 3, "the index survives for one resolution"
    assert cfg.audio_device_name == "" and cfg.audio_hostapi == ""


def test_a_valid_sherpa_config_is_left_alone():
    keep = {"backend": "sherpa", "model_size": "giga-am-v3-ru", "hotkey": "ctrl+shift+space"}
    cfg = Config(**Config.migrate(dict(keep)))
    assert cfg.backend == "sherpa"
    assert cfg.model_size == "giga-am-v3-ru", "a real Sherpa model must not be reset"


def test_migration_runs_without_sounddevice(monkeypatch):
    """No PortAudio, no device enumeration — pure schema work."""
    real_import = builtins.__import__

    def _no_sounddevice(name, *args, **kwargs):
        if name.split(".")[0] in ("sounddevice", "_sounddevice", "soundfile"):
            raise ImportError(f"{name} is not installed on this machine")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_sounddevice)
    monkeypatch.delitem(sys.modules, "sounddevice", raising=False)

    cfg = Config(**Config.migrate(dict(LEGACY)))
    assert cfg.backend == "sherpa"
    assert cfg.audio_device_legacy_index == 3


def test_load_of_a_legacy_file_does_not_reset_it(tmp_path, monkeypatch):
    """End to end through Config.load(), the path that used to lose the config."""
    monkeypatch.setattr(Config, "get_config_dir", classmethod(lambda cls: tmp_path))
    (tmp_path / "config.json").write_text(json.dumps(LEGACY), encoding="utf-8")

    cfg = Config.load()
    assert cfg.hotkey == "ctrl+alt+z", "the upgrade must not reset the config"
    assert cfg.total_words == 961087
    assert cfg.backend == "sherpa"
