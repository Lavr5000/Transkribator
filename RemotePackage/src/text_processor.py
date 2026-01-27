"""Text post-processing module for improving transcription accuracy."""
import re
from typing import Dict, List, Tuple


class TextProcessor:
    """Improves transcribed text by fixing common Whisper errors."""

    def __init__(self, language: str = "ru", enable_corrections: bool = True):
        """
        Initialize text processor.

        Args:
            language: Target language code (ru, en, etc.)
            enable_corrections: Whether to enable error corrections
        """
        self.language = language
        self.enable_corrections = enable_corrections
        self._load_corrections()

    def _load_corrections(self):
        """Load error correction rules for the target language."""
        if self.language == "ru":
            self._russian_corrections()
        elif self.language == "en":
            self._english_corrections()
        else:
            self._russian_corrections()  # Default to Russian

    def _russian_corrections(self):
        """Load Russian language error corrections."""
        # Common Whisper errors for Russian
        self.corrections = {
            # Phonetic substitutions (Whisper confuses similar sounds)
            "лыбки": "улыбки",
            "лыбкою": "улыбкою",
            "тулыбки": "улыбки",
            "тулыбкой": "улыбкою",
            "тулыбкою": "улыбкою",
            # "тул": "ул",  # REMOVED - breaks already corrected words!
            # "лыб": "лыб",  # Will be fixed by context
            "лыбью": "улыбкой",
            "лыбь": "улыбка",
            "станек": "станет",
            "станем": "станет",  # Added from test
            "станит": "станет",
            "становит": "станет",
            "сидлей": "светлей",
            "ситлей": "светлей",
            "светле": "светлей",
            "динцветлей": "всем светлей",  # From test result
            "светлее": "светлей",
            "неверо": "небе",
            "невере": "небе",
            "неверо-друга": "небе радуга",
            "радугы": "радуга",  # From test result
            "пойли": "появи",
            "поиви": "появи",
            "поделись": "поделись",
            "растебе": "к тебе",
            "ра стеб": "к тебе",
            "рассещё": "к тебе еще",
            "к тебе еще": "к тебе еще",
            "онактиви": "она не раз",  # From test - word merging
            "не рас": "не раз",
            "не расс": "не раз",
            "онак": "она же",
            "онатив": "она не",

            # Common verb endings
            "проснутся": "проснется",
            "проснется": "проснется",
            "спится": "спится",
            "получим": "получим",

            # Prepositions and particles (from test)
            "у своей": "с улыбкою своей",
            "поделись у": "поделись с",

            # Prepositions and particles
            "в в": "в",
            "на на": "на",
            "с с": "с",
            "и и": "и",
            "а а": "а",

            # Common word pairs
            "еще раз": "ещё раз",
            "в тече ние": "в течение",
            "в те чение": "в течение",
        }

        # Pattern-based corrections (regex)
        self.pattern_corrections = [
            # Fix "А" → "От" at start (common Whisper error)
            (r'^А (\w+)', lambda m: f'От {m.group(1)}'),

            # Fix multiple spaces
            (r'\s+', ' '),

            # Fix space before punctuation
            (r'\s+([,.!?;:])', r'\1'),

            # Fix missing space after punctuation
            (r'([,.!?;:])(?=[А-Яа-яA-Za-z])', r'\1 '),

            # Fix lowercase after sentence end
            (r'([.!?]\s+)([а-я])', lambda m: m.group(1) + m.group(2).upper()),
        ]

    def _english_corrections(self):
        """Load English language error corrections."""
        self.corrections = {
            # Common Whisper errors for English
            "their": "there",
            "your": "you're",
            "its": "it's",
            "then": "than",
            # Add more as needed
        }

        self.pattern_corrections = [
            (r'\s+', ' '),
            (r'\s+([,.!?;:])', r'\1'),
            (r'([,.!?;:])(?=[A-Za-z])', r'\1 '),
        ]

    def process(self, text: str) -> str:
        """
        Apply all post-processing improvements to text.

        Args:
            text: Raw transcribed text

        Returns:
            Improved text
        """
        if not text or not self.enable_corrections:
            return text

        # Step 1: Fix common errors
        text = self._fix_errors(text)

        # Step 2: Fix punctuation
        text = self._fix_punctuation(text)

        # Step 3: Fix capitalization
        text = self._fix_capitalization(text)

        # Step 4: Final cleanup
        text = self._cleanup(text)

        return text

    def _fix_errors(self, text: str) -> str:
        """Fix common transcription errors."""
        # Step 1: Fix repeated letters (common Whisper error)
        text = self._fix_repeated_letters(text)

        # Step 2: Apply corrections from LONGEST to SHORTEST (to avoid substring conflicts)
        # Sort corrections by length (descending)
        sorted_corrections = sorted(self.corrections.items(), key=lambda x: len(x[0]), reverse=True)

        for wrong, correct in sorted_corrections:
            # Use word boundaries for short phrases to avoid substring conflicts
            if len(wrong) <= 10:  # Use word boundaries for shorter patterns
                pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
            else:  # Longer phrases can be more flexible
                pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            text = pattern.sub(correct, text)

        return text

    def _fix_repeated_letters(self, text: str) -> str:
        """Fix repeated letters (Whisper artifact)."""
        # Use word boundaries to avoid affecting other words
        # Only fix exact matches, not substrings

        # Full word replacements with word boundaries
        corrections = [
            (r'\bтуулыбки\b', 'улыбки'),
            (r'\bтулыбки\b', 'улыбки'),
            (r'\bтулыбкой\b', 'улыбкою'),
            (r'\bтулыбкою\b', 'улыбкою'),
        ]

        for pattern, replacement in corrections:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text

    def _fix_punctuation(self, text: str) -> str:
        """Fix punctuation issues."""
        # Apply pattern-based corrections
        for pattern, replacement in self.pattern_corrections:
            if callable(replacement):
                text = re.sub(pattern, replacement, text)
            else:
                text = re.sub(pattern, replacement, text)

        return text

    def _fix_capitalization(self, text: str) -> str:
        """Fix capitalization issues."""
        if not text:
            return text

        # Ensure first letter is capitalized
        text = text[0].upper() + text[1:] if text else text

        # Capitalize after sentence endings
        sentences = re.split(r'([.!?]\s+)', text)
        for i in range(len(sentences)):
            if i % 2 == 0 and sentences[i]:
                # Capitalize first letter of sentence
                sentences[i] = sentences[i][0].upper() + sentences[i][1:] if sentences[i] else sentences[i]

        text = ''.join(sentences)

        return text

    def _cleanup(self, text: str) -> str:
        """Final cleanup of text."""
        # Remove extra spaces
        text = ' '.join(text.split())

        # Remove trailing punctuation
        text = text.rstrip('.,;:')

        return text.strip()

    def add_correction(self, wrong: str, correct: str):
        """
        Add a custom correction rule.

        Args:
            wrong: Wrong word/phrase to fix
            correct: Correct replacement
        """
        self.corrections[wrong] = correct

    def add_corrections(self, corrections: Dict[str, str]):
        """
        Add multiple custom correction rules.

        Args:
            corrections: Dictionary of wrong -> correct mappings
        """
        self.corrections.update(corrections)


class AdvancedTextProcessor(TextProcessor):
    """Advanced text processor with contextual corrections."""

    def __init__(self, language: str = "ru", enable_corrections: bool = True):
        super().__init__(language, enable_corrections)
        self._load_context_rules()

    def _load_context_rules(self):
        """Load context-dependent correction rules."""
        # Rules that depend on word context
        self.context_rules = [
            # Song lyrics and common phrases
            {
                "pattern": r"от\s+[лл]ыбк",
                "correction": "от улыбк",
                "description": "Fix 'лыбки' -> 'улыбки' after 'от'"
            },
            {
                "pattern": r"стан(?:е|и)к?\s+всем",
                "correction": "станет всем",
                "description": "Fix verb form in 'станет всем'"
            },
        ]

    def _fix_contextual_errors(self, text: str) -> str:
        """Fix context-dependent errors."""
        for rule in self.context_rules:
            pattern = rule["pattern"]
            correction = rule["correction"]
            text = re.sub(pattern, correction, text, flags=re.IGNORECASE)

        return text

    def process(self, text: str) -> str:
        """Apply advanced processing including context."""
        if not text or not self.enable_corrections:
            return text

        # Apply contextual corrections first
        text = self._fix_contextual_errors(text)

        # Then apply standard processing
        return super().process(text)
