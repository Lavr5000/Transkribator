"""Tests for the opt-in audio archive (Этап 0, item 6)."""
import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio_archive import AudioArchive, DPAPI_AVAILABLE, _dpapi_encrypt, _dpapi_decrypt


def _sine(seconds=0.5, sr=16000):
    t = np.linspace(0, seconds, int(sr * seconds), dtype=np.float32)
    return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_save_then_read_round_trips(tmp_path):
    archive = AudioArchive(dpapi_enabled=False, archive_dir=tmp_path)
    audio = _sine()
    file_id = archive.save(audio, 16000)
    assert file_id is not None

    data = archive.read(file_id)
    assert data is not None
    assert data[:4] == b"RIFF"  # valid WAV container


def test_no_temp_file_left_after_successful_save(tmp_path):
    archive = AudioArchive(dpapi_enabled=False, archive_dir=tmp_path)
    archive.save(_sine(), 16000)
    assert not list(tmp_path.glob("tmp_*"))
    assert list(tmp_path.glob("sealed_*"))


def test_orphan_temp_file_swept_on_construction(tmp_path):
    (tmp_path / "tmp_orphan123").write_bytes(b"partial-write-from-a-crash")
    archive = AudioArchive(dpapi_enabled=False, archive_dir=tmp_path)  # sweep runs in __init__
    assert not list(tmp_path.glob("tmp_*"))


def test_index_entry_dropped_when_backing_file_missing(tmp_path):
    archive = AudioArchive(dpapi_enabled=False, archive_dir=tmp_path)
    file_id = archive.save(_sine(), 16000)
    (tmp_path / archive._index[file_id]["filename"]).unlink()

    archive2 = AudioArchive(dpapi_enabled=False, archive_dir=tmp_path)  # reconciles on init
    assert file_id not in archive2._index


def test_retention_prunes_over_cap_but_never_referenced(tmp_path):
    archive = AudioArchive(dpapi_enabled=False, archive_dir=tmp_path)
    ids = [archive.save(_sine(0.05), 16000) for _ in range(5)]
    archive.mark_referenced(ids[0])  # pin the oldest

    deleted = archive.enforce_retention(max_utterances=2, max_age_days=365)

    # referenced entry is excluded from the cap pool entirely: 4 sealed - cap 2 = 2 deleted.
    assert deleted == 2
    assert ids[0] in archive._index  # referenced survives
    assert archive._index[ids[0]]["state"] == "referenced"
    assert len(archive._index) == 3  # 1 referenced + 2 sealed kept under the cap


def test_retention_prunes_expired_entries(tmp_path):
    archive = AudioArchive(dpapi_enabled=False, archive_dir=tmp_path)
    file_id = archive.save(_sine(0.05), 16000)
    archive._index[file_id]["created_ts"] = time.time() - 8 * 86400  # 8 days old

    deleted = archive.enforce_retention(max_utterances=500, max_age_days=7)

    assert deleted == 1
    assert file_id not in archive._index


@pytest.mark.skipif(not DPAPI_AVAILABLE, reason="pywin32 not available on this machine")
def test_dpapi_round_trip():
    plaintext = b"contains a dictated PIN: 1234"
    encrypted = _dpapi_encrypt(plaintext)
    assert encrypted != plaintext
    assert _dpapi_decrypt(encrypted) == plaintext


@pytest.mark.skipif(not DPAPI_AVAILABLE, reason="pywin32 not available on this machine")
def test_save_with_dpapi_enabled_round_trips(tmp_path):
    archive = AudioArchive(dpapi_enabled=True, archive_dir=tmp_path)
    audio = _sine()
    file_id = archive.save(audio, 16000)
    assert archive._index[file_id]["encrypted"] is True

    raw_on_disk = (tmp_path / archive._index[file_id]["filename"]).read_bytes()
    assert raw_on_disk[:4] != b"RIFF"  # ciphertext, not a readable WAV

    decrypted = archive.read(file_id)
    assert decrypted[:4] == b"RIFF"
