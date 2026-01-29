"""Proper noun recognition and capitalization."""
import json
import re
from pathlib import Path
from typing import Set, Dict, List


class ProperNounDict:
    """Load and manage proper noun dictionaries for ASR post-processing.

    Provides fast O(1) lookup for proper nouns (cities, names, countries)
    to capitalize known entities that ASR outputs in lowercase.
    """

    def __init__(self, data_dir: str = None):
        """
        Initialize proper noun dictionary.

        Args:
            data_dir: Path to data directory containing JSON files.
                     If None, uses src/data/ relative to this file.
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        else:
            data_dir = Path(data_dir)

        self._lookup: Set[str] = set()
        self._variants: Dict[str, str] = {}  # variant -> canonical
        self._stats = {
            "cities": 0,
            "names": 0,
            "countries": 0,
            "total": 0
        }

        # Load all dictionaries
        self._load_cities(data_dir / "cities.json")
        self._load_names(data_dir / "names.json")
        self._load_countries(data_dir / "countries.json")

        print(f"[INFO] ProperNounDict loaded: {self._stats}")

    def _load_json(self, path: Path) -> List[Dict]:
        """
        Load JSON file or return empty list.

        Args:
            path: Path to JSON file

        Returns:
            Parsed JSON content or empty list if file not found
        """
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARNING] Failed to load {path}: {e}")
                return []
        else:
            print(f"[WARNING] File not found: {path}")
            return []

    def _load_cities(self, path: Path):
        """Load cities from JSON and populate lookup sets."""
        entries = self._load_json(path)
        self._stats["cities"] = len(entries)

        for entry in entries:
            name = entry.get("name", "")
            variants = entry.get("variants", [])

            # Add canonical name
            self._lookup.add(name.lower())

            # Add all variants
            for variant in variants:
                self._lookup.add(variant.lower())
                # Map variant to canonical form for capitalization
                if variant.lower() != name.lower():
                    self._variants[variant.lower()] = name

    def _load_names(self, path: Path):
        """Load names from JSON and populate lookup sets."""
        entries = self._load_json(path)
        self._stats["names"] = len(entries)

        for entry in entries:
            name = entry.get("name", "")
            variants = entry.get("variants", [])

            # Add canonical name
            self._lookup.add(name.lower())

            # Add all variants
            for variant in variants:
                self._lookup.add(variant.lower())
                # Map variant to canonical form for capitalization
                if variant.lower() != name.lower():
                    self._variants[variant.lower()] = name

    def _load_countries(self, path: Path):
        """Load countries from JSON and populate lookup sets."""
        entries = self._load_json(path)
        self._stats["countries"] = len(entries)

        for entry in entries:
            name = entry.get("name", "")
            variants = entry.get("variants", [])

            # Add canonical name
            self._lookup.add(name.lower())

            # Add all variants
            for variant in variants:
                self._lookup.add(variant.lower())
                # Map variant to canonical form for capitalization
                if variant.lower() != name.lower():
                    self._variants[variant.lower()] = name

        # Update total
        self._stats["total"] = len(self._lookup)

    def is_proper_noun(self, word: str) -> bool:
        """
        Check if word is a known proper noun.

        Args:
            word: Word to check (case-insensitive)

        Returns:
            True if word is in proper noun dictionary
        """
        return word.lower() in self._lookup

    def get_canonical(self, word: str) -> str:
        """
        Get canonical form of proper noun.

        Args:
            word: Word to canonicalize

        Returns:
            Canonical form with proper capitalization
        """
        lower = word.lower()
        if lower in self._variants:
            return self._variants[lower]
        return word

    def capitalize_known(self, text: str) -> str:
        """
        Capitalize known proper nouns in text.

        Preserves punctuation and only capitalizes entities in dictionary.
        Words not in dictionary are left unchanged.

        Args:
            text: Input text to process

        Returns:
            Text with known proper nouns capitalized

        Examples:
            >>> pn = ProperNounDict()
            >>> pn.capitalize_known("я живу в москве")
            'я живу в Москве'
            >>> pn.capitalize_known("привет меня зовут денис")
            'привет меня зовут Denis'
        """
        words = text.split()

        for i, word in enumerate(words):
            # Remove punctuation for checking (but preserve for output)
            clean = re.sub(r'[^\w]', '', word)

            if clean and self.is_proper_noun(clean):
                # Get canonical form
                canonical = self.get_canonical(clean)

                # Capitalize preserving punctuation
                # Find where the clean word starts in the original word
                clean_start = word.lower().find(clean.lower())
                if clean_start != -1:
                    # Reconstruct word with canonical form
                    prefix = word[:clean_start]
                    suffix = word[clean_start + len(clean):]
                    words[i] = prefix + canonical + suffix

        return ' '.join(words)

    def get_stats(self) -> Dict[str, int]:
        """
        Get dictionary statistics.

        Returns:
            Dictionary with counts by category
        """
        return self._stats.copy()


# Singleton instance for reuse
_instance = None


def get_proper_noun_dict() -> ProperNounDict:
    """
    Get singleton instance of ProperNounDict.

    Returns:
        Shared ProperNounDict instance
    """
    global _instance
    if _instance is None:
        _instance = ProperNounDict()
    return _instance
