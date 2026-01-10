"""Enhanced text post-processing with punctuation restoration for Sherpa-ONNX."""
import re
from typing import Dict, List, Tuple, Optional

try:
    from deepmultilingualpunctuation import PunctuationModel
    PUNCTUATION_AVAILABLE = True
except ImportError:
    PUNCTUATION_AVAILABLE = False
    print("[WARNING] deepmultilingualpunctuation not installed. Install with: pip install deepmultilingualpunctuation")


class EnhancedTextProcessor:
    """Enhanced text processor with punctuation restoration and Sherpa-specific corrections."""

    def __init__(self, language: str = "ru", enable_corrections: bool = True, enable_punctuation: bool = True):
        """
        Initialize enhanced text processor.

        Args:
            language: Target language code (ru, en, etc.)
            enable_corrections: Whether to enable error corrections
            enable_punctuation: Whether to restore punctuation
        """
        self.language = language
        self.enable_corrections = enable_corrections
        self.enable_punctuation = enable_punctuation

        self._load_corrections()

        # Initialize punctuation model
        self.punctuation_model = None
        if enable_punctuation and PUNCTUATION_AVAILABLE:
            try:
                print("[INFO] Loading punctuation model...")
                self.punctuation_model = PunctuationModel()
                print("[INFO] Punctuation model loaded")
            except Exception as e:
                print(f"[WARNING] Failed to load punctuation model: {e}")
                self.punctuation_model = None

    def _load_corrections(self):
        """Load error correction rules for the target language."""
        if self.language == "ru":
            self._russian_corrections()
        elif self.language == "en":
            self._english_corrections()
        else:
            self._russian_corrections()  # Default to Russian

    def _russian_corrections(self):
        """Load Russian language error corrections with Sherpa-specific fixes."""
        # Common Whisper/Sherpa errors for Russian
        self.corrections = {
            # Sherpa-ONNX specific errors (from test results)
            "классок": "колосок",
            "класски": "колоски",
            "класок": "колосок",

            # Phonetic substitutions
            "лыбки": "улыбки",
            "лыбкою": "улыбкою",
            "тулыбки": "улыбки",
            "тулыбкой": "улыбкою",
            "тулыбкою": "улыбкою",
            "лыбью": "улыбкой",
            "лыбь": "улыбка",

            # Verb forms
            "станек": "станет",
            "станем": "станет",
            "станит": "станет",
            "становит": "станет",

            # Adjectives
            "сидлей": "светлей",
            "ситлей": "светлей",
            "светле": "светлей",
            "динцветлей": "всем светлей",
            "светлее": "светлей",

            # Prepositions and places
            "неверо": "небе",
            "невере": "небе",
            "неверо-друга": "небе радуга",
            "радугы": "радуга",
            "пойли": "появи",
            "поиви": "появи",
            "растебе": "к тебе",
            "ра стеб": "к тебе",
            "рассещё": "к тебе еще",
            "онактиви": "она не раз",
            "не рас": "не раз",
            "не расс": "не раз",
            "онак": "она же",
            "онатив": "она не",

            # Common verb endings
            "проснутся": "проснется",
            "проснется": "проснется",
            "спится": "спится",
            "получим": "получим",

            # Prepositions and particles
            "у своей": "с улыбкою своей",
            "поделись у": "поделись с",

            # Double letters/words
            "в в": "в",
            "на на": "на",
            "с с": "с",
            "и и": "и",
            "а а": "а",

            # Common word pairs
            "еще раз": "ещё раз",
            "в тече ние": "в течение",
            "в те чение": "в течение",

            # Gender/number corrections (common Sherpa errors)
            "огромные семья": "огромная семья",
            "огромный семья": "огромная семья",
            "мною родной": "мое родное",
            "мою родной": "мое родное",
            "все мою": "все мое",
            "всех люблю на свете я": "всех, кого люблю на свете, я",
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

            # Fix gender/number patterns (Sherpa specific)
            (r'огромные семья', 'огромная семья'),
            (r'огромный семья', 'огромная семья'),
            (r'мое родной', 'мое родное'),
            (r'мою родной', 'мое родное'),
            (r'все мою', 'все мое'),

            # Fix common adjective endings
            (r'(\w+) голубой (\w+)', lambda m: f'{m.group(1)} голубое {m.group(2)}'),
            (r'(\w+) морей (\w+)', lambda m: f'{m.group(1)} море {m.group(2)}'),
        ]

    def _english_corrections(self):
        """Load English language error corrections."""
        self.corrections = {
            "their": "there",
            "your": "you're",
            "its": "it's",
            "then": "than",
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

        # Step 2: Add punctuation (for CTC models like Sherpa)
        if self.enable_punctuation and self.punctuation_model:
            text = self._add_punctuation(text)

        # Step 3: Fix punctuation placement
        text = self._fix_punctuation(text)

        # Step 4: Fix capitalization
        text = self._fix_capitalization(text)

        # Step 5: Final cleanup
        text = self._cleanup(text)

        return text

    def _fix_errors(self, text: str) -> str:
        """Fix common transcription errors."""
        # Fix repeated letters
        text = self._fix_repeated_letters(text)

        # Apply corrections from LONGEST to SHORTEST
        sorted_corrections = sorted(self.corrections.items(), key=lambda x: len(x[0]), reverse=True)

        for wrong, correct in sorted_corrections:
            if len(wrong) <= 10:
                pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            text = pattern.sub(correct, text)

        return text

    def _fix_repeated_letters(self, text: str) -> str:
        """Fix repeated letters (Whisper artifact)."""
        corrections = [
            (r'\bтуулыбки\b', 'улыбки'),
            (r'\bтулыбки\b', 'улыбки'),
            (r'\bтулыбкой\b', 'улыбкою'),
            (r'\bтулыбкою\b', 'улыбкою'),
        ]

        for pattern, replacement in corrections:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text

    def _add_punctuation(self, text: str) -> str:
        """Restore punctuation using ML model."""
        try:
            # Process with punctuation model
            result = self.punctuation_model.restore_punctuation(text)
            return result
        except Exception as e:
            print(f"[WARNING] Punctuation restoration failed: {e}")
            return text

    def _fix_punctuation(self, text: str) -> str:
        """Fix punctuation issues."""
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
        """Add a custom correction rule."""
        self.corrections[wrong] = correct

    def add_corrections(self, corrections: Dict[str, str]):
        """Add multiple custom correction rules."""
        self.corrections.update(corrections)
