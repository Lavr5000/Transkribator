"""VAD must initialise in the frozen build, where huggingface_hub is excluded.

Negative control: with the `from huggingface_hub import snapshot_download` line
at the top of _get_vad_model_dir(), this test fails with ModuleNotFoundError.
"""
import builtins
import sys

import pytest


@pytest.fixture
def no_huggingface_hub(monkeypatch):
    """Simulate the frozen build: huggingface_hub is not importable."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "huggingface_hub" or name.startswith("huggingface_hub."):
            raise ModuleNotFoundError("No module named 'huggingface_hub'")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "huggingface_hub", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_vad_model_dir_resolves_without_huggingface_hub(no_huggingface_hub, tmp_path, monkeypatch):
    from src.backends.sherpa_backend import SherpaBackend

    backend = SherpaBackend.__new__(SherpaBackend)

    vad_dir = tmp_path / "models" / "sherpa" / "silero-vad"
    vad_dir.mkdir(parents=True)
    (vad_dir / "silero_vad.onnx").write_bytes(b"fake onnx")

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    result = SherpaBackend._get_vad_model_dir(backend)

    assert result == vad_dir
    assert (result / "silero_vad.onnx").exists()


def test_download_branch_still_reports_missing_hub(no_huggingface_hub, tmp_path, monkeypatch):
    """Model absent + no hub: warn and return the dir, never raise."""
    from src.backends.sherpa_backend import SherpaBackend

    backend = SherpaBackend.__new__(SherpaBackend)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    result = SherpaBackend._get_vad_model_dir(backend)

    assert result == tmp_path / "models" / "sherpa" / "silero-vad"
