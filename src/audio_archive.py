"""Opt-in raw-audio archive (Этап 0, item 6; research plan Phase 0.2).

Default OFF. When enabled (`Config.audio_archive`), each recording is
written to a local-only corpus for later research use (retrospective
corpus, challenge-set review, etc.) — never uploaded, never referenced by
default logs.

State machine per file: writing → sealed → referenced → prunable.
    writing    — a temp file exists on disk, not yet in the index. A crash
                 here leaves an orphan temp file, cleaned up by
                 sweep_orphans() at the next startup.
    sealed     — write finished (fsync'd, atomically renamed), indexed.
                 Eligible for retention pruning.
    referenced — pinned by a corpus manifest or an in-flight experiment;
                 retention never touches these.
    prunable   — marked by enforce_retention() for deletion on the next
                 pass; deletion only ever happens from this state.

Encryption: Windows DPAPI (`CryptProtectData`, user-scope) is ON by default
(Config.audio_archive_dpapi) — the archive will contain dictated passwords
with near-certainty (the history sample already did). Threat model: this
protects against disk theft, an unencrypted backup copy, and another local
admin account. It does NOT protect against: another process running as the
same user, or the machine itself being compromised. Recovery only works for
the same Windows user account on the same machine — a reinstall or profile
loss makes the archive permanently unreadable. That tradeoff is the
consent text's job to state, not this module's.
"""
import io
import json
import logging
import os
import threading
import time
import wave
from pathlib import Path
from typing import Optional
from uuid import uuid4

import numpy as np
import platformdirs

logger = logging.getLogger("transkribator")

RETENTION_MAX_UTTERANCES = 500
RETENTION_MAX_AGE_DAYS = 7

try:
    import win32crypt
    DPAPI_AVAILABLE = True
except ImportError:
    DPAPI_AVAILABLE = False


def _get_archive_dir() -> Path:
    d = Path(platformdirs.user_config_dir("WhisperTyping", "WhisperTyping")) / "audio_archive"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _dpapi_encrypt(data: bytes) -> bytes:
    return win32crypt.CryptProtectData(data, "transkribator-audio-archive", None, None, None, 0)


def _dpapi_decrypt(data: bytes) -> bytes:
    return win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]


class AudioArchive:
    """Local-only, opt-in raw-audio corpus with crash-safe writes."""

    def __init__(self, dpapi_enabled: bool = True, archive_dir: Optional[Path] = None):
        self.dpapi_enabled = dpapi_enabled and DPAPI_AVAILABLE
        if dpapi_enabled and not DPAPI_AVAILABLE:
            logger.warning("AUDIO_ARCHIVE_DPAPI_UNAVAILABLE | pywin32 missing, storing unencrypted")
        self._dir = archive_dir or _get_archive_dir()
        self._index_path = self._dir / "archive_index.json"
        self._lock = threading.Lock()
        self._index = self._load_index()
        self.sweep_orphans()

    # -- index persistence -------------------------------------------------

    def _load_index(self) -> dict:
        if not self._index_path.exists():
            return {}
        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    # -- crash safety --------------------------------------------------------

    def sweep_orphans(self) -> int:
        """Delete temp files left over from a crash (writing→sealed never
        completed) and drop index entries whose backing file is gone.
        Called once at construction (process start)."""
        removed = 0
        with self._lock:
            for tmp_file in self._dir.glob("tmp_*"):
                try:
                    tmp_file.unlink()
                    removed += 1
                except OSError as e:
                    logger.debug("AUDIO_ARCHIVE_ORPHAN_SWEEP_FAILED | %s: %s", tmp_file.name, e)

            stale_ids = [
                file_id for file_id, meta in self._index.items()
                if not (self._dir / meta["filename"]).exists()
            ]
            for file_id in stale_ids:
                del self._index[file_id]
            if stale_ids:
                self._save_index()
        if removed:
            logger.info("AUDIO_ARCHIVE_ORPHAN_SWEEP | removed=%d", removed)
        return removed

    # -- write ---------------------------------------------------------------

    def save(self, audio: np.ndarray, sample_rate: int) -> Optional[str]:
        """Crash-safe write: temp name → fsync → atomic rename → index update
        (in that order). Returns the file_id, or None on any failure (never
        raises — archive failures must not break dictation)."""
        file_id = uuid4().hex
        try:
            data = _audio_to_wav_bytes(audio, sample_rate)
            encrypted = self.dpapi_enabled
            if encrypted:
                data = _dpapi_encrypt(data)

            suffix = ".wav.enc" if encrypted else ".wav"
            tmp_path = self._dir / f"tmp_{file_id}"
            sealed_name = f"sealed_{file_id}{suffix}"
            sealed_path = self._dir / sealed_name

            # O_BINARY: Windows os.open() defaults to CRT text mode, which
            # rewrites 0x0A bytes and would corrupt arbitrary binary data
            # (DPAPI ciphertext, WAV PCM samples) containing that byte.
            open_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            fd = os.open(str(tmp_path), open_flags)
            try:
                os.write(fd, data)
                os.fsync(fd)
            finally:
                os.close(fd)

            os.replace(tmp_path, sealed_path)  # atomic on the same volume

            with self._lock:
                self._index[file_id] = {
                    "state": "sealed",
                    "created_ts": time.time(),
                    "filename": sealed_name,
                    "encrypted": encrypted,
                }
                self._save_index()
            return file_id
        except OSError as e:
            logger.warning("AUDIO_ARCHIVE_SAVE_FAILED | %s", e)
            return None

    # -- read ------------------------------------------------------------

    def read(self, file_id: str) -> Optional[bytes]:
        """Decrypted WAV bytes, or None if missing/unreadable. Never raises —
        a corrupt or undecryptable entry is skipped, not fatal (r1-18)."""
        with self._lock:
            meta = self._index.get(file_id)
        if meta is None:
            return None
        path = self._dir / meta["filename"]
        try:
            data = path.read_bytes()
        except OSError as e:
            logger.warning("AUDIO_ARCHIVE_READ_FAILED | %s: %s", file_id, e)
            return None
        if meta.get("encrypted"):
            try:
                data = _dpapi_decrypt(data)
            except Exception as e:  # pywintypes.error on wrong user/machine
                logger.warning("AUDIO_ARCHIVE_DECRYPT_FAILED | %s: %s", file_id, e)
                return None
        return data

    # -- state transitions -----------------------------------------------

    def mark_referenced(self, file_id: str) -> None:
        """Pin an entry so retention never deletes it (corpus manifest,
        in-flight experiment)."""
        with self._lock:
            if file_id in self._index:
                self._index[file_id]["state"] = "referenced"
                self._save_index()

    # -- retention ---------------------------------------------------------

    def enforce_retention(
        self,
        max_utterances: int = RETENTION_MAX_UTTERANCES,
        max_age_days: int = RETENTION_MAX_AGE_DAYS,
    ) -> int:
        """Mark over-cap/expired sealed entries as prunable, then delete
        every prunable entry. Never touches `referenced` entries. Returns
        the number of files deleted."""
        with self._lock:
            now = time.time()
            max_age_s = max_age_days * 86400

            prunable_candidates = [
                (file_id, meta) for file_id, meta in self._index.items()
                if meta["state"] in ("sealed", "prunable")
            ]
            prunable_candidates.sort(key=lambda kv: kv[1]["created_ts"])

            for file_id, meta in prunable_candidates:
                if now - meta["created_ts"] > max_age_s:
                    meta["state"] = "prunable"
            over_cap = len(prunable_candidates) - max_utterances
            if over_cap > 0:
                for file_id, meta in prunable_candidates[:over_cap]:
                    meta["state"] = "prunable"

            to_delete = [fid for fid, meta in self._index.items() if meta["state"] == "prunable"]
            deleted = 0
            for file_id in to_delete:
                meta = self._index.pop(file_id)
                try:
                    (self._dir / meta["filename"]).unlink(missing_ok=True)
                    deleted += 1
                except OSError as e:
                    logger.debug("AUDIO_ARCHIVE_PRUNE_FAILED | %s: %s", file_id, e)

            if to_delete:
                self._save_index()
            return deleted
