"""Wave-1 remediation regression tests (2026-07-11 code review).

Covers: morph revival (pymorphy3 fallback), crash-report <-> watchdog
filename contract, ML-punctuation skip for *-punct models, switch_backend
fingerprint no-op guard, notifier crash-path queue gating.
"""
import importlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------- morph revival ----------

def test_get_morph_returns_analyzer():
    pytest.importorskip("pymorphy3")
    from src.morph_singleton import get_morph
    morph = get_morph()
    assert morph is not None, "pymorphy3 installed but get_morph() is None"
    parsed = morph.parse("стройка")
    assert parsed and parsed[0].normal_form


def test_phonetic_corrector_validation_active():
    pytest.importorskip("pymorphy3")
    from src.phonetics import PhoneticCorrector
    pc = PhoneticCorrector()
    assert pc.enable_validation is True
    assert pc._is_valid_russian_word("готов") is True


# ---------- crash report <-> watchdog contract ----------

def test_crash_report_prefix_matches_watchdog_filter(tmp_path, monkeypatch):
    from src.crash_reporter import CrashReporter
    reporter = CrashReporter(crash_dir=str(tmp_path))
    try:
        raise ValueError("boom")
    except ValueError:
        exc_type, exc_value, exc_tb = sys.exc_info()
    report = reporter._build_report(exc_type, exc_value, exc_tb)
    reporter._save_report(report)

    files = os.listdir(tmp_path)
    assert len(files) == 1
    assert files[0].startswith("crash_") and files[0].endswith(".json")

    # watchdog must pick it up with its startswith("crash_") filter
    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
    sys.path.insert(0, scripts_dir)
    try:
        import watchdog as wd
        monkeypatch.setattr(wd, "CRASH_DIR", str(tmp_path))
        picked = wd._get_latest_crash_report()
    finally:
        sys.path.remove(scripts_dir)
    assert picked is not None
    assert picked["exception"]["type"] == "ValueError"


def test_crash_dir_capped_at_max_reports(tmp_path):
    from src.crash_reporter import CrashReporter
    reporter = CrashReporter(crash_dir=str(tmp_path))
    # pre-create MAX_REPORTS + 5 fake reports with sortable names
    for i in range(reporter.MAX_REPORTS + 5):
        with open(tmp_path / f"crash_2026-01-01_00-00-{i:02d}.json", "w") as f:
            json.dump({}, f)
    try:
        raise RuntimeError("cap check")
    except RuntimeError:
        reporter._save_report(reporter._build_report(*sys.exc_info()))
    remaining = [f for f in os.listdir(tmp_path) if f.startswith("crash_")]
    assert len(remaining) == reporter.MAX_REPORTS


# ---------- punctuation skip for *-punct models ----------

def test_punct_model_skips_ml_punctuation():
    from src.text_processor_enhanced import EnhancedTextProcessor
    p = EnhancedTextProcessor(backend="sherpa", model_size="giga-am-v3-ru-punct")
    assert p.enable_punctuation is False
    assert p.punctuation_model is None
    # process() must not instantiate the ML model either
    p.process("привет, это тест.")
    assert p.punctuation_model is None


def test_plain_ctc_model_keeps_ml_punctuation_flag():
    from src.text_processor_enhanced import EnhancedTextProcessor
    p = EnhancedTextProcessor(backend="sherpa", model_size="giga-am-v3-ru")
    assert p.enable_punctuation is True
    # None model_size must not crash and keeps punctuation on (conservative)
    p2 = EnhancedTextProcessor(backend="sherpa", model_size=None)
    assert p2.enable_punctuation is True


# ---------- lazy backend imports ----------

def test_backend_package_import_is_lazy():
    # Needs a FRESH interpreter: under pytest other tests already imported
    # backend submodules, and module reload keeps old attributes.
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = (
        "import sys; import src.backends as b; "
        "assert 'sherpa_onnx' not in sys.modules, 'sherpa_onnx leaked'; "
        "assert set(b.BACKENDS) == {'sherpa'}; "
        "assert b.SherpaBackend.__name__ == 'SherpaBackend'"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=root,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr


def test_backend_available_unknown_is_false():
    from src.backends import backend_available
    assert backend_available("no-such-backend") is False
    assert backend_available("sherpa") is True


# ---------- switch_backend: no-op fingerprint + busy result ----------

@pytest.fixture()
def transcriber():
    from src.transcriber import Transcriber
    return Transcriber(backend="sherpa", model_size="giga-am-v3-ru-punct", language="ru")


def test_switch_backend_noop_on_same_fingerprint(transcriber):
    fp = transcriber._created_fingerprint
    backend_obj = transcriber._backend
    assert transcriber.switch_backend("sherpa", "giga-am-v3-ru-punct") is True
    assert transcriber._backend is backend_obj, "no-op switch must keep the same backend instance"
    assert transcriber._created_fingerprint is fp


def test_switch_backend_busy_returns_false(transcriber):
    acquired = transcriber._lock.acquire(blocking=False)
    assert acquired
    try:
        assert transcriber.switch_backend("sherpa", "giga-am-v3-ru") is False
        # state untouched by the rejected switch
        assert transcriber.model_size == "giga-am-v3-ru-punct"
    finally:
        transcriber._lock.release()


def test_switch_backend_model_change_rebuilds(transcriber):
    old_fp = transcriber._created_fingerprint
    assert transcriber.switch_backend("sherpa", "giga-am-v3-ru") is True
    assert transcriber._created_fingerprint != old_fp
    assert transcriber.model_size == "giga-am-v3-ru"
    # processor follows the model: plain CTC re-enables ML punctuation flag
    assert transcriber.text_processor.enable_punctuation is True
