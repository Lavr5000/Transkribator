"""History manager for storing transcriptions."""
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List
import platformdirs


@dataclass
class TranscriptionEntry:
    """Single transcription entry."""
    text: str
    timestamp: str
    duration: float
    backend: str
    model: str
    word_count: int


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

    def _load_history(self):
        """Load history from file."""
        if self._history_file.exists():
            try:
                with open(self._history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._history = [
                        TranscriptionEntry(
                            text=entry["text"],
                            timestamp=entry["timestamp"],
                            duration=entry["duration"],
                            backend=entry["backend"],
                            model=entry["model"],
                            word_count=entry["word_count"]
                        )
                        for entry in data
                    ]
            except (json.JSONDecodeError, KeyError, TypeError):
                self._history = []

    def _save_history(self):
        """Save history to file."""
        with open(self._history_file, "w", encoding="utf-8") as f:
            json.dump([asdict(entry) for entry in self._history], f, indent=2, ensure_ascii=False)

    def add_entry(self, text: str, duration: float, backend: str, model: str):
        """
        Add a new transcription entry.

        Args:
            text: Transcribed text
            duration: Processing time in seconds
            backend: Backend used (whisper, sherpa, etc.)
            model: Model used
        """
        word_count = len(text.split())

        entry = TranscriptionEntry(
            text=text,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration=duration,
            backend=backend,
            model=model,
            word_count=word_count
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

    def get_stats(self) -> dict:
        """Get statistics about history."""
        total_words = sum(entry.word_count for entry in self._history)
        total_duration = sum(entry.duration for entry in self._history)
        avg_duration = total_duration / len(self._history) if self._history else 0

        return {
            "total_entries": len(self._history),
            "total_words": total_words,
            "total_duration": total_duration,
            "avg_duration": avg_duration
        }
