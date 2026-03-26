"""Tests for safe backend switching with rollback (Phase 5)."""

import os
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_mock_backend(name="mock"):
    """Create a mock backend with BaseBackend interface."""
    backend = MagicMock()
    backend.model_size = name
    backend.unload_model = MagicMock()
    return backend


@pytest.fixture
def transcriber():
    """Transcriber with mocked backend — no real model loading."""
    mock_backend = _make_mock_backend("sherpa")
    mock_cls = MagicMock(return_value=mock_backend)

    with patch("transcriber.get_backend", return_value=mock_cls):
        with patch("transcriber.get_reporter", return_value=None):
            from transcriber import Transcriber
            t = Transcriber(backend="sherpa", model_size="v3", enable_post_processing=False)
            return t


class TestBackendSwitch:
    def test_switch_success(self, transcriber):
        """Successful switch updates backend and unloads old one."""
        old_backend_instance = transcriber._backend

        new_mock = _make_mock_backend("whisper")
        new_cls = MagicMock(return_value=new_mock)

        with patch("transcriber.get_backend", return_value=new_cls):
            with patch("transcriber.get_reporter", return_value=None):
                transcriber.switch_backend("whisper", "base")

        assert transcriber.backend_name == "whisper"
        assert transcriber.model_size == "base"
        assert transcriber._backend is new_mock
        # Old backend should be unloaded AFTER new one is confirmed
        old_backend_instance.unload_model.assert_called_once()

    def test_switch_failure_rollback(self, transcriber):
        """On failure, old backend and state are restored."""
        old_backend_instance = transcriber._backend
        old_name = transcriber.backend_name
        old_model = transcriber.model_size
        old_processor = transcriber.text_processor

        # Make get_backend return a class that raises on instantiation
        failing_cls = MagicMock(side_effect=RuntimeError("Model load failed"))

        with patch("transcriber.get_backend", return_value=failing_cls):
            with patch("transcriber.get_reporter", return_value=None):
                with pytest.raises(RuntimeError, match="Model load failed"):
                    transcriber.switch_backend("whisper", "base")

        # State should be rolled back
        assert transcriber.backend_name == old_name
        assert transcriber.model_size == old_model
        assert transcriber._backend is old_backend_instance
        assert transcriber.text_processor is old_processor
        # Old backend should NOT be unloaded (it's restored)
        old_backend_instance.unload_model.assert_not_called()

    def test_switch_preserves_processor(self, transcriber):
        """Text processor matches new backend after switch."""
        new_mock = _make_mock_backend("whisper")
        new_cls = MagicMock(return_value=new_mock)

        with patch("transcriber.get_backend", return_value=new_cls):
            with patch("transcriber.get_reporter", return_value=None):
                transcriber.switch_backend("whisper", "base")

        # Whisper uses AdvancedTextProcessor (not Enhanced)
        from text_processor import AdvancedTextProcessor
        assert isinstance(transcriber.text_processor, AdvancedTextProcessor)

    def test_concurrent_switch_locked(self, transcriber):
        """Concurrent switch calls are serialized by lock."""
        results = []
        barrier = threading.Barrier(2, timeout=5)

        def slow_switch(name):
            try:
                barrier.wait()
                new_mock = _make_mock_backend(name)
                new_cls = MagicMock(return_value=new_mock)
                with patch("transcriber.get_backend", return_value=new_cls):
                    with patch("transcriber.get_reporter", return_value=None):
                        transcriber.switch_backend("sherpa", "v3")
                results.append(f"{name}_ok")
            except Exception as e:
                results.append(f"{name}_err:{e}")

        t1 = threading.Thread(target=slow_switch, args=("t1",))
        t2 = threading.Thread(target=slow_switch, args=("t2",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # Both should complete (serialized, not deadlocked)
        assert len(results) == 2
        assert all("ok" in r for r in results)
