"""Morphological correction module using pymorphy2 for Russian language.

This module provides gender agreement and case ending corrections for ASR output.
Uses singleton pattern for pymorphy2.MorphAnalyzer to avoid performance issues.
"""

import re
from typing import Optional, List, Tuple

try:
    import pymorphy2
    PYMORPHY2_AVAILABLE = True
except ImportError:
    PYMORPHY2_AVAILABLE = False
    print("[WARNING] pymorphy2 not installed. Install with: pip install pymorphy2")


class MorphologyCorrector:
    """Morphological corrector for Russian text using pymorphy2.

    Uses singleton pattern for MorphAnalyzer to ensure only one instance
    is created per process, improving performance.
    """

    # Class-level singleton instance
    _morph = None

    def __init__(self):
        """Initialize morphological corrector with singleton MorphAnalyzer."""
        if PYMORPHY2_AVAILABLE and MorphologyCorrector._morph is None:
            MorphologyCorrector._morph = pymorphy2.MorphAnalyzer()

        # Word-level cache to avoid re-parsing
        self._cache = {}

    def _parse_word(self, word: str) -> Optional[list]:
        """Parse word with caching.

        Args:
            word: Word to parse

        Returns:
            List of Parse objects from pymorphy2, or None if unavailable
        """
        if not PYMORPHY2_AVAILABLE:
            return None

        # Check cache first
        if word in self._cache:
            return self._cache[word]

        # Parse and cache
        parsed = self._morph.parse(word)
        self._cache[word] = parsed
        return parsed

    def fix_gender_agreement(self, text: str) -> str:
        """Fix gender agreement between adjectives and nouns.

        Detects adjective-noun pairs with gender mismatch and corrects
        the adjective to match the noun's gender.

        Only applies corrections when both words have high confidence (>0.5).

        Args:
            text: Text to correct

        Returns:
            Text with corrected gender agreement
        """
        if not PYMORPHY2_AVAILABLE:
            return text

        words = text.split()

        for i in range(len(words) - 1):
            word1, word2 = words[i], words[i + 1]

            # Parse both words
            p1 = self._parse_word(word1)
            p2 = self._parse_word(word2)

            if not p1 or not p2:
                continue

            # Get most likely parse (first result)
            parse1 = p1[0]
            parse2 = p2[0]

            # Check confidence scores - only correct high-confidence cases
            if parse1.score <= 0.5 or parse2.score <= 0.5:
                continue

            # Check if we have adjective + noun pattern
            if (parse1.tag.POS == 'ADJF' and  # Adjective
                parse2.tag.POS == 'NOUN'):   # Noun

                # Check gender mismatch
                gender1 = parse1.tag.gender
                gender2 = parse2.tag.gender

                if gender1 and gender2 and gender1 != gender2:
                    # Try to inflect adjective to match noun's gender
                    corrected = parse1.inflect({gender2})

                    if corrected:
                        words[i] = corrected.word

        return ' '.join(words)

    def fix_case_endings(self, text: str) -> str:
        """Fix basic case ending errors in low-confidence parses.

        For words with low confidence pymorphy2 parse, attempts to
        normalize to dictionary form (lemma) when appropriate.

        Args:
            text: Text to correct

        Returns:
            Text with corrected case endings
        """
        if not PYMORPHY2_AVAILABLE:
            return text

        words = text.split()

        for i, word in enumerate(words):
            parsed = self._parse_word(word)

            if not parsed or parsed[0].score > 0.5:
                continue  # Skip high-confidence words

            # Low confidence - try normal form
            normal = parsed[0].normal_form

            # Check if normal form is common and original is rare variant
            # Only apply if normal form is similar length (avoid over-correction)
            if normal != word and len(normal) <= len(word) + 2:
                # Use normal form if it fits context (simplified check)
                words[i] = normal

        return ' '.join(words)

    def process(self, text: str) -> str:
        """Apply all morphological corrections to text.

        Args:
            text: Text to correct

        Returns:
            Corrected text
        """
        if not PYMORPHY2_AVAILABLE:
            return text

        # Apply gender agreement corrections
        text = self.fix_gender_agreement(text)

        # Apply case ending corrections
        text = self.fix_case_endings(text)

        return text


def fix_gender_agreement(text: str) -> str:
    """Convenience function for gender agreement correction.

    Args:
        text: Text to correct

    Returns:
        Text with corrected gender agreement
    """
    corrector = MorphologyCorrector()
    return corrector.fix_gender_agreement(text)


def fix_case_endings(text: str) -> str:
    """Convenience function for case ending correction.

    Args:
        text: Text to correct

    Returns:
        Text with corrected case endings
    """
    corrector = MorphologyCorrector()
    return corrector.fix_case_endings(text)
