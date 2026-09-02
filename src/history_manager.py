"""History manager for storing transcriptions.

Schema v2 (Этап 0 модернизации v3, fixes B8): every new row is written with
`schema_version: 2` and the fields below. `duration` is FROZEN in storage —
old readers keep working — but is DEPRECATED in code: the only sanctioned
accessor is the `api_elapsed_s` property on `TranscriptionEntry`. A
repo-wide grep-guard test (tests/test_history_schema_v2.py) fails on any new
`.duration` read outside this file.

Field semantics (units / nullability / source clock):
    schema_version    int, 1 for legacy rows (absent key), 2 for new rows.
    duration           float, seconds. Legacy name = API elapsed time. Frozen.
    audio_duration_s   float|None, seconds of actual recorded audio (samples/rate,
                       after trim once trimming exists). None on legacy rows.
    rtf                float|None = duration / audio_duration_s. None if
                       audio_duration_s is unknown or zero.
    rms_dbfs, peak_dbfs float|None, dBFS of the recorded audio.
    flags              list[str], subset of {"clipping", "low_signal",
                       "capture_degraded"}.
    dropped_frames     int, queue.Full + input-overflow count for this recording.
    used_fallback      bool, kept from the cloud era; always False since 2.4.0.
    fallback_reason    str|None, short cause tag when used_fallback is True.
    device_api         str|None, capture host API actually used (e.g. "mme", "wasapi").
    prompt_version     int|None, opaque local version ID of the prompt sent (versions.py).
    dictionary_version int|None, opaque local version ID of the user dictionary in effect.
    trigger_id         str|None, correlates this row with event-log gate/no-send records.
"""
import dataclasses
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import platformdirs


@dataclass
class TranscriptionEntry:
    """Single transcription entry. See module docstring for field semantics."""
    text: str
    timestamp: str
    duration: float  # legacy field, frozen — read via .api_elapsed_s, never directly
    backend: str
    model: str
    word_count: int
    schema_version: int = 1
    audio_duration_s: Optional[float] = None
    rtf: Optional[float] = None
    rms_dbfs: Optional[float] = None
    peak_dbfs: Optional[float] = None
    flags: List[str] = field(default_factory=list)
    dropped_frames: int = 0
    used_fallback: bool = False
    fallback_reason: Optional[str] = None
    device_api: Optional[str] = None
    prompt_version: Optional[int] = None
    dictionary_version: Optional[int] = None
    trigger_id: Optional[str] = None

    @property
    def api_elapsed_s(self) -> float:
        """The one sanctioned accessor for the legacy `duration` field (r1-10)."""
        return self.duration


_KNOWN_FIELDS = {f.name for f in dataclasses.fields(TranscriptionEntry)}


class HistoryManager:
    """Manages transcription history with auto-cleanup."""

    def __init__(self, max_entries: int = 50):
        """
        Initialize history manager.

        Args:
            max_entries: Maximum number of entries to keep (default: 50)
        """
        self.max_entries = max_entries
        self._history: List[TranscriptionEntry] = []
        self._history_file = self._get_history_file()
        self._load_history()

    def _get_history_file(self) -> Path:
        """Get the history file path."""
        config_dir = Path(platformdirs.user_config_dir("WhisperTyping", "WhisperTyping"))
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "history.json"

    @staticmethod
    def _entry_from_dict(raw: dict) -> TranscriptionEntry:
        """Tolerant construction: unknown keys ignored (forward compat),
        missing new-schema keys fall back to their dataclass default
        (backward compat with v1 rows)."""
        kwargs = {k: v for k, v in raw.items() if k in _KNOWN_FIELDS}
        return TranscriptionEntry(**kwargs)

    def _load_history(self):
        """Load history from file. Each row is parsed independently — one
        corrupt row is skipped, not the whole file (v1 behavior discarded
        everything on a single bad KeyError)."""
        if not self._history_file.exists():
            return
        try:
            with open(self._history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._history = []
            return

        entries = []
        for raw in data:
            try:
                entries.append(self._entry_from_dict(raw))
            except (KeyError, TypeError):
                continue
        self._history = entries

    def _save_history(self):
        """Save history to file."""
        with open(self._history_file, "w", encoding="utf-8") as f:
            json.dump([asdict(entry) for entry in self._history], f, indent=2, ensure_ascii=False)

    def add_entry(
        self,
        text: str,
        duration: float,
        backend: str,
        model: str,
        *,
        audio_duration_s: Optional[float] = None,
        rms_dbfs: Optional[float] = None,
        peak_dbfs: Optional[float] = None,
        flags: Optional[List[str]] = None,
        dropped_frames: int = 0,
        used_fallback: bool = False,
        fallback_reason: Optional[str] = None,
        device_api: Optional[str] = None,
        prompt_version: Optional[int] = None,
        dictionary_version: Optional[int] = None,
        trigger_id: Optional[str] = None,
    ):
        """
        Add a new transcription entry (always written as schema v2).

        Args:
            text: Transcribed text
            duration: API elapsed time in seconds (legacy name, see api_elapsed_s)
            backend: Backend used (sherpa)
            model: Model used
            audio_duration_s..trigger_id: schema-v2 fields, see module docstring
        """
        word_count = len(text.split())
        rtf = (duration / audio_duration_s) if audio_duration_s else None

        entry = TranscriptionEntry(
            text=text,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration=duration,
            backend=backend,
            model=model,
            word_count=word_count,
            schema_version=2,
            audio_duration_s=audio_duration_s,
            rtf=rtf,
            rms_dbfs=rms_dbfs,
            peak_dbfs=peak_dbfs,
            flags=flags or [],
            dropped_frames=dropped_frames,
            used_fallback=used_fallback,
            fallback_reason=fallback_reason,
            device_api=device_api,
            prompt_version=prompt_version,
            dictionary_version=dictionary_version,
            trigger_id=trigger_id,
        )

        self._history.append(entry)

        # Remove oldest entries if over limit
        while len(self._history) > self.max_entries:
            self._history.pop(0)

        self._save_history()

    def get_history(self) -> List[TranscriptionEntry]:
        """Get all history entries (newest first)."""
        return list(reversed(self._history))

    def clear_history(self):
        """Clear all history."""
        self._history.clear()
        self._save_history()

    def search_history(self, query: str) -> List[TranscriptionEntry]:
        """Search history entries by text content."""
        if not query:
            return self.get_history()
        query_lower = query.lower()
        return [
            entry for entry in reversed(self._history)
            if query_lower in entry.text.lower()
        ]

    def get_stats(self) -> dict:
        """Get statistics about history."""
        total_words = sum(entry.word_count for entry in self._history)
        total_duration = sum(entry.api_elapsed_s for entry in self._history)
        avg_duration = total_duration / len(self._history) if self._history else 0

        return {
            "total_entries": len(self._history),
            "total_words": total_words,
            "total_duration": total_duration,
            "avg_duration": avg_duration
        }
