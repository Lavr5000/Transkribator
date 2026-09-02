"""Structured event log — Этап 0, item 5 (r1-28).

Append-only JSONL, text-free BY CONSTRUCTION: callers pass only enum-like
strings, numbers, booleans and IDs (never transcript text or raw audio —
that privacy rule is global, r1-19). Size-bounded with single-backup
rotation; writes are counted in the instrumentation-overhead measurement
(Этап 0 acceptance) because they run off the audio callback but still cost
disk I/O on the calling thread.
"""
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
import platformdirs

logger = logging.getLogger("transkribator")

MAX_BYTES = 5 * 1024 * 1024  # 5 MB before rotation

_lock = threading.Lock()


def _get_event_log_path() -> Path:
    d = Path(platformdirs.user_config_dir("WhisperTyping", "WhisperTyping"))
    d.mkdir(parents=True, exist_ok=True)
    return d / "events.jsonl"


def log_event(event_type: str, **fields) -> None:
    """Append one structured, text-free event row.

    Args:
        event_type: short enum-like tag, e.g. "capture_open", "queue_drop",
            "fallback", "gate_decision", "archive_state", "config_migration".
        **fields: structured values only (str/int/float/bool/None) — no
            transcript text, no raw audio, no absolute user paths.
    """
    row = {"ts": datetime.now(timezone.utc).isoformat(), "event": event_type, **fields}
    path = _get_event_log_path()
    try:
        with _lock:
            if path.exists() and path.stat().st_size > MAX_BYTES:
                backup = path.with_suffix(".jsonl.1")
                path.replace(backup)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        logger.debug("EVENT_LOG_WRITE_FAILED | %s", e)
