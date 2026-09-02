"""Opaque local version IDs for prompt/dictionary content (Этап 0, r1-12/r1-29).

A content hash of a short secret vocabulary is reversible by enumeration, so
versions are plain monotonic per-install integers, not hashes. The actual
content is snapshotted locally (content-addressed, not just hashed) so a
version ID can be resolved back to what was actually sent — but the snapshot
never leaves the machine and is never logged.

Captured at request-creation time (not at read time) so concurrent edits to
the prompt/dictionary never misattribute an in-flight transcription.
"""
import json
import threading
from pathlib import Path
import platformdirs


def _get_versions_dir() -> Path:
    d = Path(platformdirs.user_config_dir("WhisperTyping", "WhisperTyping")) / "versions"
    d.mkdir(parents=True, exist_ok=True)
    return d


class VersionStore:
    """One append-only snapshot log per content kind (e.g. "prompt", "dictionary").

    Each line: {"version": int, "content": <the actual artefact>}. A new line
    is appended only when content differs from the last snapshot; otherwise
    the existing version is returned unchanged.
    """

    def __init__(self, kind: str, versions_dir: Path = None):
        self.kind = kind
        self._dir = versions_dir or _get_versions_dir()
        self._file = self._dir / f"{kind}_versions.jsonl"
        self._lock = threading.Lock()

    def _read_last(self):
        if not self._file.exists():
            return None
        last = None
        with open(self._file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = json.loads(line)
                except json.JSONDecodeError:
                    continue
        return last

    def get_or_create_version(self, content) -> int:
        """Return the version ID for `content`, creating a new one if it
        differs from the last recorded snapshot."""
        with self._lock:
            last = self._read_last()
            if last is not None and last.get("content") == content:
                return last["version"]
            new_version = (last["version"] + 1) if last else 1
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps({"version": new_version, "content": content}, ensure_ascii=False) + "\n")
            return new_version


def canonical_dictionary(user_dictionary: list) -> str:
    """Stable text form of the user dictionary for version comparison."""
    return json.dumps(user_dictionary or [], ensure_ascii=False, sort_keys=True)


_prompt_store = VersionStore("prompt")
_dictionary_store = VersionStore("dictionary")


def prompt_version(prompt_text: str) -> int:
    """Version ID for the prompt actually sent (empty string when none)."""
    return _prompt_store.get_or_create_version(prompt_text or "")


def dictionary_version(user_dictionary: list) -> int:
    """Version ID for the user dictionary actually in effect."""
    return _dictionary_store.get_or_create_version(canonical_dictionary(user_dictionary))
