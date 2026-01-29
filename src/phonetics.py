"""Phonetic corrections for Russian ASR output.

Handles voiced/unvoiced consonant substitutions common in ASR:
- Word-end devoicing: неверо -> небе
- Pre-voiced assimilation: готов (ASR: "кото")
"""
import re
from typing import Optional

# Try to import pymorphy2 for vocabulary validation
try:
    from pymorphy2 import MorphAnalyzer
    PYMORPHY_AVAILABLE = True
except ImportError:
    PYMORPHY_AVAILABLE = False
    print("[WARNING] pymorphy2 not installed. Vocabulary validation disabled. Install with: pip install pymorphy2")


# Voiced/unvoiced consonant pairs in Russian
VOICED_UNVOICED_MAP = {
    'б': 'п', 'п': 'б',
    'в': 'ф', 'ф': 'в',
    'г': 'к', 'к': 'г',
    'д': 'т', 'т': 'д',
    'ж': 'ш', 'ш': 'ж',
    'з': 'с', 'с': 'з',
}

# Voiced consonants (that devoice at word end)
VOICED_CONSONANTS = set('бвгджз')

# Unvoiced consonants (that may voice before voiced consonants)
UNVOICED_CONSONANTS = set('пфкшст')


class PhoneticCorrector:
    """Corrects phonetic errors in Russian ASR output.

    Focuses on voiced/unvoiced consonant substitutions with vocabulary
    validation to avoid over-correction.
    """

    # Class-level singleton for MorphAnalyzer (expensive to create)
    _morph = None

    def __init__(self, enable_validation: bool = True):
        """Initialize phonetic corrector.

        Args:
            enable_validation: Whether to validate corrections against vocabulary.
                             If False, applies corrections more aggressively.
        """
        self.enable_validation = enable_validation and PYMORPHY_AVAILABLE

        # Lazy-load MorphAnalyzer on first use
        if self.enable_validation and PhoneticCorrector._morph is None:
            PhoneticCorrector._morph = MorphAnalyzer()

    def _is_valid_russian_word(self, word: str) -> bool:
        """Check if word is valid Russian vocabulary.

        Args:
            word: Word to check (lowercase, no punctuation)

        Returns:
            True if word exists in Russian vocabulary
        """
        if not self.enable_validation or not PhoneticCorrector._morph:
            return True  # Assume valid if validation disabled

        if not word:
            return False

        # Parse with pymorphy2
        parsed = PhoneticCorrector._morph.parse(word)

        # Word is valid if it has at least one parse with high confidence
        # Score > 0.1 indicates a legitimate morphological analysis
        return any(p.score > 0.1 for p in parsed)

    def fix_word_end_devoicing(self, text: str) -> str:
        """Fix word-end devoicing/voicing errors.

        Russian rule: Voiced consonants devoice at word end (готов -> готов).
        ASR error: Sometimes gets wrong variant (неверо instead of небе).

        Strategy:
        1. For words ending in voiced consonant: try unvoiced variant
        2. For words ending in unvoiced consonant: try voiced variant
        3. Apply substitution only if:
           - Original word NOT in vocabulary AND
           - Substituted word IS in vocabulary

        Examples:
            неверо -> небе (if неверо invalid, небе valid)
            кодов -> кодов (both valid, don't correct)
        """
        if not text:
            return text

        words = text.split()
        corrected_words = []

        for word in words:
            # Extract leading/trailing punctuation
            match = re.match(r'^([^а-яА-ЯёЁ]*)([а-яА-ЯёЁ]+)([^а-яА-ЯёЁ]*)$', word)
            if not match:
                corrected_words.append(word)
                continue

            prefix, core, suffix = match.groups()
            lower_core = core.lower()

            # Skip short words (likely prepositions, particles)
            if len(lower_core) <= 2:
                corrected_words.append(word)
                continue

            corrected_core = core
            last_char = lower_core[-1]

            # Case 1: Word ends in voiced consonant -> try unvoiced
            if last_char in VOICED_CONSONANTS:
                unvoiced = VOICED_UNVOICED_MAP[last_char]
                candidate = lower_core[:-1] + unvoiced

                if not self._is_valid_russian_word(lower_core) and self._is_valid_russian_word(candidate):
                    corrected_core = self._preserve_case(core, candidate)

            # Case 2: Word ends in unvoiced consonant -> try voiced
            elif last_char in UNVOICED_CONSONANTS:
                voiced = VOICED_UNVOICED_MAP[last_char]
                candidate = lower_core[:-1] + voiced

                if not self._is_valid_russian_word(lower_core) and self._is_valid_russian_word(candidate):
                    corrected_core = self._preserve_case(core, candidate)

            corrected_words.append(prefix + corrected_core + suffix)

        return ' '.join(corrected_words)

    def fix_pre_voiced_assimilation(self, text: str) -> str:
        """Fix pre-voiced assimilation errors within words.

        Russian rule: Voiced consonants devoice before voiceless consonants
        (отбивка -> отпивка, but written with voiced then unvoiced).

        ASR error: May incorrectly devoice or miss assimilation.

        Focus on common patterns where ASR makes mistakes:
        - Affricates and clusters
        - Word-internal consonant sequences

        Examples:
            готов (ASR: "кото" - д devoiced before в, but ASR kept it)
        """
        if not text:
            return text

        words = text.split()
        corrected_words = []

        for word in words:
            # Extract leading/trailing punctuation
            match = re.match(r'^([^а-яА-ЯёЁ]*)([а-яА-ЯёЁ]+)([^а-яА-ЯёЁ]*)$', word)
            if not match:
                corrected_words.append(word)
                continue

            prefix, core, suffix = match.groups()
            corrected_core = core

            # Find consonant clusters within word
            # Pattern: voiced + unvoiced or unvoiced + voiced
            for i in range(len(core) - 1):
                char1, char2 = core[i].lower(), core[i + 1].lower()

                # Skip if not both consonants
                if not (char1 in VOICED_CONSONANTS or char1 in UNVOICED_CONSONANTS):
                    continue
                if not (char2 in VOICED_CONSONANTS or char2 in UNVOICED_CONSONANTS):
                    continue

                # Case: voiced consonant followed by unvoiced
                # Russian: voiced devoices before unvoiced (готВот -> готфот)
                # ASR may get this wrong
                if char1 in VOICED_CONSONANTS and char2 in UNVOICED_CONSONANTS:
                    # Try voicing the second consonant
                    # Example: кото (ASR error for готов)
                    unvoiced_char2 = char2
                    voiced_char2 = VOICED_UNVOICED_MAP.get(unvoiced_char2)

                    if voiced_char2:
                        candidate = core[:i+1] + voiced_char2 + core[i+2:]
                        lower_core = core.lower()
                        lower_candidate = candidate.lower()

                        # Apply if original invalid and candidate valid
                        if not self._is_valid_russian_word(lower_core) and self._is_valid_russian_word(lower_candidate):
                            corrected_core = self._preserve_case(core, lower_candidate)
                            break

            corrected_words.append(prefix + corrected_core + suffix)

        return ' '.join(corrected_words)

    def process(self, text: str) -> str:
        """Apply all phonetic corrections to text.

        Processing order:
        1. Word-end devoicing/voicing corrections
        2. Pre-voiced assimilation corrections

        Args:
            text: Input text from ASR

        Returns:
            Text with phonetic corrections applied
        """
        if not text:
            return text

        # Step 1: Fix word-end devoicing
        text = self.fix_word_end_devoicing(text)

        # Step 2: Fix pre-voiced assimilation
        text = self.fix_pre_voiced_assimilation(text)

        return text

    @staticmethod
    def _preserve_case(original: str, corrected: str) -> str:
        """Preserve original capitalization pattern.

        Args:
            original: Original word with casing
            corrected: Corrected word (lowercase)

        Returns:
            Corrected word with original casing pattern
        """
        if not original or not corrected:
            return corrected

        # All uppercase
        if original.isupper():
            return corrected.upper()

        # All lowercase
        if original.islower():
            return corrected

        # First letter capitalized (Title case)
        if original[0].isupper() and original[1:].islower():
            return corrected.capitalize()

        # Mixed case - preserve pattern character by character
        result = []
        for i, char in enumerate(corrected):
            if i < len(original):
                if original[i].isupper():
                    result.append(char.upper())
                else:
                    result.append(char.lower())
            else:
                result.append(char)

        return ''.join(result)


def fix_voiced_unvoiced(text: str, enable_validation: bool = True) -> str:
    """Convenience function to fix voiced/unvoiced consonant errors.

    Args:
        text: Input text from ASR
        enable_validation: Whether to validate against vocabulary

    Returns:
        Text with phonetic corrections applied

    Example:
        >>> fix_voiced_unvoiced("неверо в небе")
        "небе в небе"
    """
    corrector = PhoneticCorrector(enable_validation=enable_validation)
    return corrector.process(text)
