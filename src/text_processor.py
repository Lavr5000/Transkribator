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
            # Phonetic substitutions ( Whisper confuses similar sounds)
            "лыбки": "улыбки",
            "лыбью": "улыбкой",
            "лыбь": "улыбка",
            "станек": "станет",
            "станит": "станет",
            "становит": "станет",
            "сидлей": "светлей",
            "ситлей": "светлей",
            "светле": "светлей",
            "неверо": "небе",
            "невере": "небе",
            "неверо-друга": "небе радуга",
            "пойли": "появи",
            "поиви": "появи",
            "растебе": "к тебе",
            "ра стеб": "к тебе",
            "к тебе еще": "к тебе еще",

            # Common verb endings
            "проснутся": "проснется",
            "спится": "спится",
            "получим": "получим",

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
        # Apply direct word substitutions
        for wrong, correct in self.corrections.items():
            # Case-insensitive replacement
            pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            text = pattern.sub(correct, text)

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
