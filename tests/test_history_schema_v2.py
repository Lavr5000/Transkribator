"""Tests for history schema v2 (Этап 0, план модернизации v3)."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.history_manager import HistoryManager, TranscriptionEntry

REPO_ROOT = Path(__file__).parent.parent
GUARDED_FILE = REPO_ROOT / "src" / "history_manager.py"


def test_new_entries_carry_all_v2_fields(tmp_path, monkeypatch):
    """add_entry() always writes schema_version=2 with the full field set."""
    hm = HistoryManager.__new__(HistoryManager)
    hm.max_entries = 50
    hm._history = []
    hm._history_file = tmp_path / "history.json"

    hm.add_entry(
        "текст", 1.2, "groq", "whisper-large-v3-turbo",
        audio_duration_s=2.0, rms_dbfs=-40.0, peak_dbfs=-10.0,
        flags=["clipping"], dropped_frames=1, used_fallback=False,
        fallback_reason=None, device_api="wasapi",
        prompt_version=1, dictionary_version=3, trigger_id="abc123",
    )

    entry = hm.get_history()[0]
    assert entry.schema_version == 2
    assert entry.api_elapsed_s == 1.2
    assert entry.audio_duration_s == 2.0
    assert entry.rtf == pytest.approx(0.6)
    assert entry.rms_dbfs == -40.0
    assert entry.peak_dbfs == -10.0
    assert entry.flags == ["clipping"]
    assert entry.dropped_frames == 1
    assert entry.device_api == "wasapi"
    assert entry.prompt_version == 1
    assert entry.dictionary_version == 3
    assert entry.trigger_id == "abc123"

    # Round-trips through disk unchanged.
    hm2 = HistoryManager.__new__(HistoryManager)
    hm2.max_entries = 50
    hm2._history = []
    hm2._history_file = hm._history_file
    hm2._load_history()
    assert hm2.get_history()[0].trigger_id == "abc123"


def test_v1_reader_tolerates_v2_row(tmp_path):
    """A v1-shaped reader (only knows the original 6 fields) must not choke
    on a v2 row written by the current code — construction ignores unknown
    keys and defaults absent ones."""
    v2_row = {
        "text": "привет", "timestamp": "2026-07-27 10:00:00", "duration": 0.9,
        "backend": "groq", "model": "whisper-large-v3-turbo", "word_count": 1,
        "schema_version": 2, "audio_duration_s": 1.5, "rtf": 0.6,
        "trigger_id": "xyz",
    }
    v1_only_fields = {"text", "timestamp", "duration", "backend", "model", "word_count"}
    legacy_kwargs = {k: v for k, v in v2_row.items() if k in v1_only_fields}
    entry = TranscriptionEntry(**legacy_kwargs)
    assert entry.api_elapsed_s == 0.9
    assert entry.schema_version == 1  # default for a row without the key


def test_v1_file_loads_with_schema_version_1(tmp_path):
    """A pre-v2 history.json (no new keys at all) loads without error and
    each entry reports schema_version 1."""
    legacy_file = tmp_path / "history.json"
    legacy_file.write_text(json.dumps([{
        "text": "старая запись", "timestamp": "2026-01-01 00:00:00",
        "duration": 2.1, "backend": "sherpa", "model": "giga-am-v3-ru",
        "word_count": 2,
    }]), encoding="utf-8")

    hm = HistoryManager.__new__(HistoryManager)
    hm.max_entries = 50
    hm._history = []
    hm._history_file = legacy_file
    hm._load_history()

    entries = hm.get_history()
    assert len(entries) == 1
    assert entries[0].schema_version == 1
    assert entries[0].api_elapsed_s == 2.1
    assert entries[0].audio_duration_s is None


def test_corrupt_row_skipped_not_whole_file(tmp_path):
    """One malformed row must not discard the rest of the history (v1 bug:
    a single KeyError wiped `_history` entirely)."""
    f = tmp_path / "history.json"
    f.write_text(json.dumps([
        {"text": "good", "timestamp": "t", "duration": 1.0, "backend": "b", "model": "m", "word_count": 1},
        {"garbage": True},
    ]), encoding="utf-8")

    hm = HistoryManager.__new__(HistoryManager)
    hm.max_entries = 50
    hm._history = []
    hm._history_file = f
    hm._load_history()

    assert len(hm.get_history()) == 1
    assert hm.get_history()[0].text == "good"


def test_grep_guard_no_new_duration_reads():
    """`.duration` is deprecated in code (r1-10) — the only sanctioned
    accessor is `TranscriptionEntry.api_elapsed_s`, defined in
    history_manager.py. No other file may read `.duration` off a history
    entry (or anything else named that way)."""
    pattern = re.compile(r"\.duration\b")
    offenders = []
    for py_file in (REPO_ROOT / "src").rglob("*.py"):
        if py_file.resolve() == GUARDED_FILE.resolve():
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(text):
            offenders.append(str(py_file.relative_to(REPO_ROOT)))
    assert not offenders, f"New `.duration` reads found (use .api_elapsed_s instead): {offenders}"
